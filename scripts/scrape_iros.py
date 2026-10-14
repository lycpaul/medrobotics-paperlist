#!/usr/bin/env python3
"""Scrape an IROS accepted-paper list (with abstracts) into a CSV.

The IROS 2026 program site (``2026.ieee-iros.org/program/``) is a static site
whose pages embed their data as ``<script type="application/json">`` blobs, so
no JavaScript execution is needed -- the JSON just has to be pulled out of the
HTML. Two pages are combined:

  * ``paper-index/`` carries ``pi-data``: one record per paper with the paper
    number (``pn``), title, authors, keywords, session and presentation type
    (Award Candidates / Special Sessions / Focused Sessions / Lightning Talks).
    It has no abstracts.
  * ``contributed_talks/`` carries ``schedule-data``: every talk grouped by
    view (``F`` = focused/award/special sessions, ``L`` = lightning talks) and
    session, each with its abstract.

Records are joined on the paper number. The standalone
``assets/schedule_data.json`` the site references is not publicly fetchable
(HTTP 403), hence reading the copy embedded in the page.

A few abstracts contain inline HTML (``<i>``, ``<b>``, ``<u>``, ``<sup>``,
``<sub>``) alongside literal comparisons such as ``p < 0.001``, so only those
known tags are stripped; ``<sup>``/``<sub>`` are rendered as ``^``/``_``
(e.g. ``cm<sup>2</sup>`` -> ``cm^2``). A handful of papers have no abstract
on the source site; their Abstract cell is left empty.

Output columns (the IROS 2025 layout plus ``Type``):
    Session, Type, Paper Title, Author List, Keywords, Abstract

``Author List`` is ``;``-separated ``Last, First`` names and ``Keywords`` is
``;``-separated (individual keywords may themselves contain commas). Rows are
ordered by type (awards first), then session, then talk order within the
session. Only the Python standard library is used.

The raw HTML is cached under ``IROS/.cache/`` so re-runs are offline; pass
``--refresh`` to re-download (the program site is updated as the conference
approaches).

Examples:
    python scripts/scrape_iros.py                 # IROS 2026
    python scripts/scrape_iros.py --refresh       # ignore the HTML cache
    python scripts/scrape_iros.py --limit 5       # quick smoke test
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Per-year program-site pages. Earlier IROS lists in this repo come from
# community-maintained repos (see IROS/README.md), not from this scraper.
SITES = {
    "2026": {
        "index_url": "https://2026.ieee-iros.org/program/paper-index/",
        "talks_url": "https://2026.ieee-iros.org/program/contributed_talks/",
    },
}

YEARS = ("2026",)

# Awards and special sessions first, then the regular tracks.
_TYPE_RANK = {
    "Award Candidates": 0,
    "Special Sessions": 1,
    "Focused Sessions": 2,
    "Lightning Talks": 3,
}

WS_RE = re.compile(r"\s+")
SUP_RE = re.compile(r"<sup>(.*?)</sup>", re.IGNORECASE | re.DOTALL)
SUB_RE = re.compile(r"<sub>(.*?)</sub>", re.IGNORECASE | re.DOTALL)
# Only known formatting tags, so literal "<0.5 mm" / "p < 0.001" survive.
INLINE_TAG_RE = re.compile(r"</?(?:i|b|u|em|strong|br)\s*/?>", re.IGNORECASE)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def fetch(url: str, retries: int = 4, timeout: int = 120) -> str:
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


def get_html_cached(url: str, path: str, refresh: bool) -> str:
    if not refresh and os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    html_text = fetch(url)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    return html_text


def embedded_json(html_text: str, script_id: str):
    """Parse the JSON inside ``<script id="<script_id>">`` (any attr order)."""
    m = re.search(
        rf'<script\b[^>]*\bid="{re.escape(script_id)}"[^>]*>(.*?)</script>',
        html_text,
        re.DOTALL,
    )
    if not m:
        raise ValueError(f'no <script id="{script_id}"> block found')
    return json.loads(m.group(1))


def clean(text: str) -> str:
    return WS_RE.sub(" ", text or "").strip()


def clean_abstract(text: str) -> str:
    text = SUP_RE.sub(r"^\1", text or "")
    text = SUB_RE.sub(r"_\1", text)
    text = INLINE_TAG_RE.sub("", text)
    return clean(html.unescape(text))


def join_list(raw: str) -> str:
    """Normalize a ``"; "``-separated source list to ``;``-separated."""
    return ";".join(p for p in (clean(x) for x in (raw or "").split(";")) if p)


def abstracts_by_pn(schedule: dict) -> dict[str, str]:
    """Map paper number -> abstract across every view/session of the talks."""
    out: dict[str, str] = {}
    for view in schedule.get("views", {}).values():
        for talks in view.get("themes", {}).values():
            for talk in talks:
                pn = str(talk.get("pn", "")).strip()
                if pn:
                    out[pn] = clean_abstract(talk.get("abstract", ""))
    return out


def scrape_year(year: str, repo_root: str, cache_dir: str, limit: int,
                refresh: bool) -> int:
    cfg = SITES[year]
    log(f"Fetching IROS {year} paper index: {cfg['index_url']} ...")
    index_html = get_html_cached(
        cfg["index_url"], os.path.join(cache_dir, f"{year}_paper_index.html"), refresh
    )
    log(f"Fetching IROS {year} contributed talks: {cfg['talks_url']} ...")
    talks_html = get_html_cached(
        cfg["talks_url"], os.path.join(cache_dir, f"{year}_contributed_talks.html"), refresh
    )

    try:
        index = embedded_json(index_html, "pi-data")
        abstracts = abstracts_by_pn(embedded_json(talks_html, "schedule-data"))
    except (ValueError, json.JSONDecodeError) as err:
        log(f"  Could not parse IROS {year} -- the page structure may have changed: {err}")
        return 0

    papers = []
    for rec in index:
        pn = str(rec.get("pn", "")).strip()
        title = clean(rec.get("title", ""))
        if not title:
            continue
        papers.append({
            "pn": pn,
            "title": title,
            "authors": join_list(rec.get("authors", "")),
            "keywords": join_list(rec.get("keywords", "")),
            "session": clean(rec.get("session", "")),
            "type": clean(rec.get("type", "")),
            "talk_number": rec.get("talk_number") or 0,
            "abstract": abstracts.get(pn, ""),
        })
    papers.sort(key=lambda p: (_TYPE_RANK.get(p["type"], 9), p["session"].lower(),
                               p["talk_number"], p["title"].lower()))

    if not papers:
        log(f"  No papers parsed for IROS {year} -- the page structure may have changed.")
        return 0

    missing = [p["pn"] for p in papers if p["pn"] not in abstracts]
    if missing:
        log(f"  ! {len(missing)} paper(s) absent from the contributed-talks data: "
            f"{', '.join(missing[:10])}{' ...' if len(missing) > 10 else ''}")
    if limit:
        papers = papers[:limit]

    out_path = os.path.join(repo_root, "IROS", f"IROS{year}_Paper_List_with_Abstract.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Session", "Type", "Paper Title", "Author List", "Keywords", "Abstract"])
        for p in papers:
            writer.writerow([p["session"], p["type"], p["title"], p["authors"],
                             p["keywords"], p["abstract"]])

    n_abs = sum(1 for p in papers if p["abstract"])
    n_sessions = len({p["session"] for p in papers})
    log(f"  Wrote {len(papers)} papers to {out_path} "
        f"({n_abs} with abstracts, {n_sessions} sessions).")
    return len(papers)


def main() -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", default="2026", help="IROS edition (default 2026)")
    ap.add_argument("--cache-dir", help="raw-HTML cache dir (default: IROS/.cache)")
    ap.add_argument("--refresh", action="store_true",
                    help="re-download the pages even if they are cached")
    ap.add_argument("--limit", type=int, default=0,
                    help="only write the first N papers (0 = all)")
    args = ap.parse_args()

    if args.year not in SITES:
        log(f"Unknown IROS year: {args.year} (known: {', '.join(YEARS)})")
        return 2

    cache_dir = args.cache_dir or os.path.join(repo_root, "IROS", ".cache")
    os.makedirs(os.path.join(repo_root, "IROS"), exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    total = scrape_year(args.year, repo_root, cache_dir, args.limit, args.refresh)
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
