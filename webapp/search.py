"""Search, filter, paginate, and export the in-memory paper records.

Pure functions over a list of normalized records (see ``loader.py``). No state,
no I/O — easy to test in isolation.
"""

from __future__ import annotations

import csv
import io

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 250


def _as_set(values):
    """Normalize a filter argument into a set of non-empty strings."""
    if values is None:
        return set()
    if isinstance(values, (str, int)):
        values = [values]
    return {str(v).strip() for v in values if str(v).strip()}


def _matches(record, q, conferences, years, keyword):
    if conferences and record["conference"] not in conferences:
        return False
    if years and str(record["year"]) not in years:
        return False
    if q:
        haystack = " ".join((
            record["title"], record["abstract"], record["keywords"])).lower()
        if q not in haystack:
            return False
    if keyword:
        haystack = " ".join((record["keywords"], record["session"])).lower()
        if keyword not in haystack:
            return False
    return True


def filter_records(records, q="", conference=None, year=None, keyword=""):
    """Return every record matching the filters, in source order.

    ``q`` matches (case-insensitively) across title/abstract/keywords;
    ``keyword`` matches across keywords/session. ``conference`` and ``year`` are
    exact-match filters that accept a single value or a list (OR within a
    field, AND across fields).
    """
    q = (q or "").strip().lower()
    keyword = (keyword or "").strip().lower()
    conferences = _as_set(conference)
    years = _as_set(year)
    return [r for r in records if _matches(r, q, conferences, years, keyword)]


def search(records, q="", conference=None, year=None, keyword="",
           page=1, page_size=DEFAULT_PAGE_SIZE):
    """Filter ``records`` and return one page of results.

    Returns ``{"total", "page", "page_size", "results"}``. Filter arguments are
    as for ``filter_records``.
    """
    matched = filter_records(records, q, conference, year, keyword)
    total = len(matched)

    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    page = max(page, 1)

    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": matched[start:end],
    }


def facets(records):
    """Return distinct sorted conferences and years for filter dropdowns."""
    conferences = sorted({r["conference"] for r in records})
    years = sorted({r["year"] for r in records}, reverse=True)
    return {"conferences": conferences, "years": years}


EXPORT_COLUMNS = ["Title", "Authors", "Venue", "Session", "Keywords", "PDF",
                  "Code", "Dataset", "Paper Page", "Abstract"]


def to_csv(records):
    """Serialize records to CSV text (with header) for download."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for r in records:
        links = r.get("links") or {}
        writer.writerow([
            r["title"],
            r["authors"],
            f"{r['conference']} {r['year']}",
            r["session"],
            r["keywords"],
            links.get("pdf", ""),
            links.get("code", ""),
            links.get("dataset", ""),
            links.get("paper_page", ""),
            r["abstract"],
        ])
    return buffer.getvalue()
