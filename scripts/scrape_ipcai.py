#!/usr/bin/env python3
"""Scrape an IPCAI accepted-paper list (title + authors) into a CSV.

IPCAI publishes its program on a Google Sites page
(``sites.google.com/view/ipcai<year>/program``). There is no per-paper detail
page, so no abstract, PDF link, or keywords are available -- only the title,
author list, and (when present) the section heading the paper was listed
under (e.g. "Accepted regular paper submissions" vs a long-abstract track).

Google Sites serves the page's content pre-rendered as plain HTML (a paste
from a Google Doc), so no JavaScript execution is needed -- it just needs to
be parsed carefully. Every edition lists title before authors, but the exact
markup shape -- and how to tell a real title apart from unrelated bold text
elsewhere on the page -- differs enough to need three parsing modes:

  * ``standard`` (2024-2026): a bold paragraph holds the title (optionally
    prefixed with a non-bold ``#<id>`` paper number), and the following
    plain-weight paragraph (or the same paragraph, for 2026) holds the
    authors.
  * ``gated`` (2023): same title-then-authors order and the same markup as
    2024-2026 (titles are either bare bold paragraphs -- some wrapped in a
    ``<ul><li>``, some not -- or a non-bold ``#<id>`` marker plus a bold
    title in one paragraph), but the page opens with a schedule/agenda
    preamble (session times, chairs) that is *also* bold and would otherwise
    be misread as titles. Paragraphs are ignored until the first ``<h2>``
    heading containing "Session Information" is seen; everything from there
    on is real paper content.
  * ``id_suffix`` (2022): titles are marked with ``<strong>`` rather than
    inline CSS, and the preamble has the same false-positive-bold problem as
    2023 but without the ``<li>`` wrapping to fall back on. Instead, authors
    are identified by their trailing ``[IPCAI-<n>]`` tag, and the title is
    whatever bold-only paragraph immediately preceded that author paragraph.

Section headings (``<h2>``) are tracked to fill the ``Session`` column.
Author affiliations embedded in the 2022/2023 author lists (e.g. ``Jane Doe
(MIT)``) and presenting-author ``*`` markers are stripped for consistency
with the affiliation-free 2024-2026 lists. A handful of 2022 papers are
listed twice on the source page; exact title+author duplicates are dropped.

Output columns:
    Title, Authors, Session, Abstract, PDF, Paper Page

``Abstract`` and ``PDF`` are always empty (not published for IPCAI).
``Paper Page`` is the program page URL for that year. Only the Python
standard library is used.

Examples:
    python scripts/scrape_ipcai.py                 # all years 2022-2026
    python scripts/scrape_ipcai.py --year 2025      # a single edition
    python scripts/scrape_ipcai.py --limit 5        # quick smoke test
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import csv
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

SITES = {
    "2022": "https://sites.google.com/view/ipcai2022/program",
    "2023": "https://sites.google.com/view/ipcai-2023/program",
    "2024": "https://sites.google.com/view/ipcai2024/program",
    "2025": "https://sites.google.com/view/ipcai2025/program",
    "2026": "https://sites.google.com/view/ipcai2026/program",
}

YEARS = ("2022", "2023", "2024", "2025", "2026")

# Per-year parser mode; see the module docstring for what each mode handles.
# Years not listed here use "standard".
_PARSER_CONFIG = {
    "2022": {"mode": "id_suffix", "id_suffix_re": re.compile(r"\[IPCAI-\d+\]\s*$")},
    "2023": {"mode": "gated", "gate_h2_re": re.compile(r"Session Information", re.IGNORECASE)},
}
_DEFAULT_CONFIG = {"mode": "standard"}

ID_MARKER_RE = re.compile(r"^#?\s*\d+$")
LEADING_ID_RE = re.compile(r"^#\s*\d+\s*")
WS_RE = re.compile(r"\s+")
TRAILING_STAR_RE = re.compile(r"\*+\s*$")
TRAILING_AFFILIATION_RE = re.compile(r"\s*\([^()]*\)\s*$")


def _config_for(year: str) -> dict:
    return _PARSER_CONFIG.get(year, _DEFAULT_CONFIG)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def fetch(url: str, retries: int = 4, timeout: int = 60) -> str:
    """GET ``url`` as text, retrying transient failures with backoff."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError) as err:
            last_err = err
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def clean(text: str) -> str:
    return WS_RE.sub(" ", text).strip()


class ProgramParser(HTMLParser):
    """Walk a Google-Sites-rendered program page and emit paper entries.

    Bold runs (``font-weight: 700`` inline style, or a ``<strong>``/``<b>``
    element) are title candidates; plain-weight runs are either a bare
    ``#<id>`` marker (real authors follow in the next paragraph), the author
    line itself (when it shares the paragraph with the title), or -- in
    ``id_suffix`` mode -- identified as the author line by a trailing
    ``[IPCAI-<n>]`` tag instead of by paragraph order.
    """

    def __init__(self, id_suffix_re: re.Pattern | None = None,
                 gate_h2_re: re.Pattern | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.papers: list[dict] = []
        self.id_suffix_re = id_suffix_re
        self.gate_h2_re = gate_h2_re
        self._gate_open = gate_h2_re is None
        self._bold_stack: list[bool] = []
        self._block: str | None = None  # "p" or "h2", or None outside both
        self._spans: list[tuple[bool, str]] = []
        self._skip_depth = 0  # inside <script>/<style>
        self._session = ""
        self._pending_title: str | None = None
        self._pending_session = ""
        self._last_bold_only: str | None = None  # id_suffix mode only

    # -- tag handling ---------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = dict(attrs)
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if tag in ("span", "strong", "b"):
            if tag == "span":
                style = attrs_d.get("style") or ""
                m = re.search(r"font-weight:\s*(\d+)", style)
                if m:
                    bold = int(m.group(1)) >= 700
                else:
                    bold = self._bold_stack[-1] if self._bold_stack else False
            else:
                bold = True
            self._bold_stack.append(bold)
        elif tag in ("p", "h2") and self._block is None:
            self._block = tag
            self._spans = []

    def handle_startendtag(self, tag: str, attrs) -> None:
        # e.g. <br/>; no special handling needed beyond what handle_starttag does
        self.handle_starttag(tag, attrs)
        if tag in ("span", "strong", "b"):
            self._bold_stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in ("span", "strong", "b") and self._bold_stack:
            self._bold_stack.pop()
        elif tag in ("p", "h2") and self._block == tag:
            self._process_block(tag)
            self._block = None
            self._spans = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth or self._block is None or not data:
            return
        bold = self._bold_stack[-1] if self._bold_stack else False
        self._spans.append((bold, data))

    # -- block-level entry extraction ------------------------------------
    def _process_block(self, block_type: str) -> None:
        bold_str = clean("".join(t for b, t in self._spans if b))
        plain_str = clean("".join(t for b, t in self._spans if not b))

        if block_type == "h2":
            header = bold_str or plain_str
            if header:
                self._session = header
                if self.gate_h2_re is not None and self.gate_h2_re.search(header):
                    self._gate_open = True
            return

        if not self._gate_open or (not bold_str and not plain_str):
            return

        if self.id_suffix_re is not None:
            self._process_id_suffix_block(bold_str, plain_str)
            return

        if bold_str:
            title = LEADING_ID_RE.sub("", bold_str).strip()
            if len(title) < 8 or " " not in title:
                return  # too short to be a real title; likely stray UI text
            if not plain_str or ID_MARKER_RE.match(plain_str):
                if self._pending_title is not None:
                    # The previous bold-only paragraph was never followed by
                    # an authors line, so it wasn't really a title -- it was
                    # a session/heading label (e.g. "Long Presentation
                    # Session (S6)") sitting outside any <h2>.
                    self._session = self._pending_title
                self._pending_title = title
                self._pending_session = self._session
            else:
                self._emit(title, plain_str, self._session)
                self._pending_title = None
        elif self._pending_title is not None and plain_str:
            self._emit(self._pending_title, plain_str, self._pending_session)
            self._pending_title = None

    def _process_id_suffix_block(self, bold_str: str, plain_str: str) -> None:
        if bold_str and not plain_str:
            title = LEADING_ID_RE.sub("", bold_str).strip()
            if len(title) >= 8 and " " in title:
                self._last_bold_only = title
            return
        if plain_str and self._last_bold_only is not None:
            m = self.id_suffix_re.search(plain_str)
            if m:
                self._emit(self._last_bold_only, plain_str[: m.start()].strip(), self._session)
                self._last_bold_only = None

    def _emit(self, title: str, authors_raw: str, session: str) -> None:
        self.papers.append({"title": title, "authors": split_authors(authors_raw), "session": session})


def clean_author_name(name: str) -> str:
    """Strip a presenting-author ``*`` and a trailing ``(Affiliation)``."""
    name = TRAILING_STAR_RE.sub("", name.strip()).strip()
    name = TRAILING_AFFILIATION_RE.sub("", name).strip()
    return name


def split_authors(raw: str) -> list[str]:
    raw = raw.strip()
    parts = raw.split(";") if ";" in raw else raw.split(",")
    names = (clean_author_name(clean(p)) for p in parts)
    return [n for n in names if n]


def dedupe_papers(papers: list[dict]) -> list[dict]:
    """Drop exact title+author duplicates, keeping first-seen order."""
    seen: set[tuple[str, tuple[str, ...]]] = set()
    deduped = []
    for p in papers:
        key = (p["title"], tuple(p["authors"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped


def get_html_cached(url: str, year: str, cache_dir: str) -> str:
    path = os.path.join(cache_dir, f"{year}.html")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    html_text = fetch(url)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    return html_text


def scrape_year(year: str, repo_root: str, cache_dir: str, limit: int) -> int:
    url = SITES[year]
    config = _config_for(year)
    log(f"Fetching IPCAI {year} ({config['mode']} mode): {url} ...")
    html_text = get_html_cached(url, year, cache_dir)

    parser = ProgramParser(
        id_suffix_re=config.get("id_suffix_re"),
        gate_h2_re=config.get("gate_h2_re"),
    )
    parser.feed(html_text)
    papers = dedupe_papers(parser.papers)
    if limit:
        papers = papers[:limit]

    if not papers:
        log(f"  No papers parsed for IPCAI {year} -- the page structure may have changed.")
        return 0

    out_path = os.path.join(repo_root, "IPCAI", f"IPCAI{year}_Paper_List_with_Abstract.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Title", "Authors", "Session", "Abstract", "PDF", "Paper Page"])
        for p in papers:
            writer.writerow([p["title"], ";".join(p["authors"]), p["session"], "", "", url])

    log(f"  Wrote {len(papers)} papers to {out_path}.")
    return len(papers)


def main() -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", help="single IPCAI edition (default: all 2022-2026)")
    ap.add_argument("--cache-dir", help="raw-HTML cache dir (default: IPCAI/.cache)")
    ap.add_argument("--limit", type=int, default=0,
                    help="only write the first N papers per year (0 = all)")
    args = ap.parse_args()

    years = [args.year] if args.year else list(YEARS)
    for y in years:
        if y not in SITES:
            log(f"Unknown IPCAI year: {y} (known: {', '.join(YEARS)})")
            return 2

    cache_dir = args.cache_dir or os.path.join(repo_root, "IPCAI", ".cache")
    os.makedirs(os.path.join(repo_root, "IPCAI"), exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    total = 0
    for y in years:
        total += scrape_year(y, repo_root, cache_dir, args.limit)
    log(f"Done. {total} papers across {len(years)} edition(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
