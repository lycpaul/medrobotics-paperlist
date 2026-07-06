#!/usr/bin/env python3
"""Scrape an IPCAI accepted-paper list (title + authors) into a CSV.

IPCAI publishes its program on a Google Sites page
(``sites.google.com/view/ipcai<year>/program``). There is no per-paper detail
page, so no abstract, PDF link, or keywords are available -- only the title,
author list, and (when present) the section heading the paper was listed
under (e.g. "Accepted regular paper submissions" vs a long-abstract track).

Google Sites serves the page's content pre-rendered as plain HTML (a paste
from a Google Doc), so no JavaScript execution is needed -- it just needs to
be parsed carefully. Each program entry is a run of bold (``font-weight:
700``) spans holding the title, optionally prefixed with a non-bold
``#<id>`` paper number, followed by a plain-weight author line. The exact
markup shape differs by year:

  * 2024/2025: title and authors are separate ``<p>`` paragraphs.
  * 2026: title and authors share one ``<p>`` paragraph (separated by a
    ``<br>``).

Both shapes are handled by accumulating bold vs. plain text per paragraph and
deciding, per paragraph, whether the plain-weight text is a bare paper-number
marker (-> authors follow in the next paragraph) or the author line itself.
Section headings (``<h2>``) are tracked to fill the ``Session`` column.

Output columns:
    Title, Authors, Session, Abstract, PDF, Paper Page

``Abstract`` and ``PDF`` are always empty (not published for IPCAI).
``Paper Page`` is the program page URL for that year. Only the Python
standard library is used.

Examples:
    python scripts/scrape_ipcai.py                 # all years 2024-2026
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
    "2024": "https://sites.google.com/view/ipcai2024/program",
    "2025": "https://sites.google.com/view/ipcai2025/program",
    "2026": "https://sites.google.com/view/ipcai2026/program",
}

YEARS = ("2024", "2025", "2026")

ID_MARKER_RE = re.compile(r"^#?\s*\d+$")
LEADING_ID_RE = re.compile(r"^#\s*\d+\s*")
WS_RE = re.compile(r"\s+")


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

    Bold (``font-weight: 700``) runs are titles; plain-weight runs are either
    a bare ``#<id>`` marker (real authors follow in the next paragraph) or
    the author line itself (when it shares the paragraph with the title).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.papers: list[dict] = []
        self._bold_stack: list[bool] = []
        self._block: str | None = None  # "p" or "h2", or None outside both
        self._spans: list[tuple[bool, str]] = []
        self._skip_depth = 0  # inside <script>/<style>
        self._session = ""
        self._pending_title: str | None = None
        self._pending_session = ""

    # -- tag handling ---------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = dict(attrs)
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if tag == "span":
            style = attrs_d.get("style") or ""
            m = re.search(r"font-weight:\s*(\d+)", style)
            if m:
                bold = int(m.group(1)) >= 700
            else:
                bold = self._bold_stack[-1] if self._bold_stack else False
            self._bold_stack.append(bold)
        elif tag in ("p", "h2") and self._block is None:
            self._block = tag
            self._spans = []

    def handle_startendtag(self, tag: str, attrs) -> None:
        # e.g. <br/>; no special handling needed beyond what handle_starttag does
        self.handle_starttag(tag, attrs)
        if tag == "span":
            self._bold_stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "span" and self._bold_stack:
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
            return

        if not bold_str and not plain_str:
            return

        if bold_str:
            title = LEADING_ID_RE.sub("", bold_str).strip()
            if len(title) < 8 or " " not in title:
                return  # too short to be a real title; likely stray UI text
            if not plain_str or ID_MARKER_RE.match(plain_str):
                self._pending_title = title
                self._pending_session = self._session
            else:
                self._emit(title, plain_str, self._session)
                self._pending_title = None
        elif self._pending_title is not None and plain_str:
            self._emit(self._pending_title, plain_str, self._pending_session)
            self._pending_title = None

    def _emit(self, title: str, authors_raw: str, session: str) -> None:
        self.papers.append({"title": title, "authors": split_authors(authors_raw), "session": session})


def split_authors(raw: str) -> list[str]:
    raw = raw.strip()
    parts = raw.split(";") if ";" in raw else raw.split(",")
    return [clean(p) for p in parts if clean(p)]


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
    log(f"Fetching IPCAI {year}: {url} ...")
    html_text = get_html_cached(url, year, cache_dir)

    parser = ProgramParser()
    parser.feed(html_text)
    papers = parser.papers
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
    ap.add_argument("--year", help="single IPCAI edition (default: all 2024-2026)")
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
