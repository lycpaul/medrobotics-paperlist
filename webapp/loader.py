"""Load the conference ``_with_Abstract.csv`` files into normalized records.

The CSV files have heterogeneous schemas (column order differs, some have no
header row, and 2025/IROS files prefix cell values with ``Keywords: `` /
``Abstract: ``). This module isolates all of that: it maps every source file to
one uniform record shape so the rest of the app sees consistent data.

See the repository ``README.md`` ("CSV file structure") for the source schemas.
"""

from __future__ import annotations

import csv
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)

# Conference directories live next to this package's parent.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFERENCES = ("ICRA", "IROS", "MICCAI", "MIDL", "IPCAI")

# Some abstracts are very large; allow big CSV fields.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

# Field keys used in a profile's column list. "_" means "ignore this column".
# A profile is the ordered list of field keys matching the file's columns.
_PROFILES = {
    ("ICRA", 2023): {
        "header": True,
        "columns": ["title", "authors", "affiliation", "session", "abstract"],
    },
    ("ICRA", 2024): {
        "header": False,
        "columns": ["title", "authors", "affiliation", "session", "abstract"],
    },
    ("ICRA", 2025): {
        "header": True,
        "columns": ["session", "title", "authors", "keywords", "abstract"],
    },
    ("ICRA", 2026): {
        "header": True,
        "columns": ["session", "title", "authors", "affiliation", "keywords",
                    "abstract"],
    },
    ("IROS", 2023): {
        "header": False,
        "columns": ["title", "authors", "keywords", "abstract"],
    },
    ("IROS", 2024): {
        "header": False,
        "columns": ["title", "authors", "keywords", "abstract"],
    },
    ("IROS", 2025): {
        "header": True,
        "columns": ["session", "title", "authors", "keywords", "abstract"],
    },
}

# All MICCAI editions share one schema.
_MICCAI_PROFILE = {
    "header": True,
    "columns": ["title", "authors", "session", "abstract", "code", "dataset",
                "pdf", "paper_page"],
}

# All MIDL editions share one schema. The TL;DR column has no normalized field,
# and community-implementation links are surfaced via the "code" link slot.
_MIDL_PROFILE = {
    "header": True,
    "columns": ["title", "authors", "session", "keywords", "_", "abstract",
                "code", "pdf", "paper_page"],
}

# All IPCAI editions share one schema. Abstract/PDF are always empty (not
# published on the source program page).
_IPCAI_PROFILE = {
    "header": True,
    "columns": ["title", "authors", "session", "abstract", "pdf", "paper_page"],
}

_FILENAME_RE = re.compile(r"^([A-Za-z]+)(\d{4})_Paper_List_with_Abstract\.csv$")
_PREFIX_RE = re.compile(r"^\s*(?:keywords|abstract)\s*:\s*", re.IGNORECASE)

_LINK_FIELDS = ("pdf", "code", "dataset", "paper_page")


def _open_text(path):
    """Open a CSV for reading, tolerating non-UTF-8 bytes in a few files.

    Most files are UTF-8 (some with a BOM). A handful contain stray bytes from
    Windows-1252; we fall back to that, then to a lossless latin-1 read so a
    single bad byte never aborts a load.
    """
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            handle = open(path, "r", encoding=encoding, newline="")
            handle.read()
            handle.seek(0)
            return handle
        except UnicodeDecodeError:
            handle.close()
    # latin-1 decodes any byte, so this is effectively unreachable.
    return open(path, "r", encoding="latin-1", newline="")


def parse_filename(filename):
    """Return ``(conference, year)`` from a CSV filename, or ``None``."""
    match = _FILENAME_RE.match(os.path.basename(filename))
    if not match:
        return None
    return match.group(1).upper(), int(match.group(2))


def _profile_for(conference, year):
    if conference == "MICCAI":
        return _MICCAI_PROFILE
    if conference == "MIDL":
        return _MIDL_PROFILE
    if conference == "IPCAI":
        return _IPCAI_PROFILE
    return _PROFILES.get((conference, year))


def _strip_prefix(value):
    """Remove a leading ``Keywords:`` / ``Abstract:`` label from a cell."""
    return _PREFIX_RE.sub("", value).strip()


def _row_to_record(row, profile, conference, year):
    """Map one raw CSV row to a normalized record, or ``None`` if unusable."""
    columns = profile["columns"]
    fields = {key: "" for key in (
        "title", "authors", "session", "keywords", "abstract", "affiliation")}
    links = {key: "" for key in _LINK_FIELDS}

    for index, key in enumerate(columns):
        if key == "_" or index >= len(row):
            continue
        value = (row[index] or "").strip()
        if key in ("keywords", "abstract"):
            value = _strip_prefix(value)
        if key in _LINK_FIELDS:
            links[key] = value
        elif key in fields:
            fields[key] = value

    if not fields["title"]:
        return None  # a row with no title is not a usable paper record

    return {
        "conference": conference,
        "year": year,
        "title": fields["title"],
        "authors": fields["authors"],
        "session": fields["session"],
        "keywords": fields["keywords"],
        "abstract": fields["abstract"],
        "affiliation": fields["affiliation"],
        "links": links,
    }


def load_file(path):
    """Load one CSV file into a list of normalized records."""
    parsed = parse_filename(path)
    if parsed is None:
        logger.warning("Skipping unrecognized filename: %s", path)
        return []
    conference, year = parsed
    profile = _profile_for(conference, year)
    if profile is None:
        logger.warning("No schema profile for %s %s; skipping %s",
                       conference, year, path)
        return []

    records = []
    skipped = 0
    with _open_text(path) as handle:
        reader = csv.reader(handle)
        if profile["header"]:
            next(reader, None)  # discard the header row
        for row in reader:
            if not row:
                continue
            record = _row_to_record(row, profile, conference, year)
            if record is None:
                skipped += 1
                continue
            records.append(record)

    if skipped:
        logger.warning("%s: skipped %d malformed/empty row(s)", path, skipped)
    logger.info("%s: loaded %d records", path, len(records))
    return records


def discover_csv_files(repo_root=REPO_ROOT):
    """Return the paths of all ``_with_Abstract.csv`` files in the repo."""
    paths = []
    for conference in CONFERENCES:
        directory = os.path.join(repo_root, conference)
        if not os.path.isdir(directory):
            logger.warning("Missing conference directory: %s", directory)
            continue
        for name in sorted(os.listdir(directory)):
            if name.endswith("_with_Abstract.csv"):
                paths.append(os.path.join(directory, name))
    return paths


def load_all(repo_root=REPO_ROOT):
    """Load every conference CSV into one combined list of records."""
    records = []
    for path in discover_csv_files(repo_root):
        records.extend(load_file(path))
    logger.info("Loaded %d total records", len(records))
    return records
