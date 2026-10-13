# Paper List Search Web App

A small local web app to search and filter the repository's accepted-paper
lists (ICRA, IROS, MICCAI, MIDL). A Flask backend digests the `_with_Abstract.csv`
files into one unified in-memory index and serves a single-page frontend.

## Features

- **Keyword search** across title, abstract, and keywords (case-insensitive).
- **Filter by conference and year** (multi-select).
- **Filter by keyword / session / topic.**
- **Links** to PDF / code / dataset / paper page where available (mainly MICCAI
  and MIDL).
- **Paginated** results with a total count; choose 10, 50, 100, or 250 per
  page (remembered across visits).
- Click any row to expand its **abstract**.
- **Export CSV** downloads every result of the current search (all pages) with
  title, authors, venue, session, keywords, PDF/code/dataset/page links, and
  abstract.

## Run

```bash
pip install -r requirements.txt        # installs Flask
python app.py                          # serves http://127.0.0.1:5000/
```

Options: `--host`, `--port`, `--debug`.

The CSV files are read from the conference directories (`../ICRA`, `../IROS`,
`../MICCAI`, `../MIDL`) at startup; ~20k papers load in a second or two.

## API

| Endpoint | Description |
| --- | --- |
| `GET /` | Single-page UI. |
| `GET /api/facets` | Distinct conferences and years for the dropdowns. |
| `GET /api/search` | `q`, `conference` (repeatable), `year` (repeatable), `keyword`, `page`, `page_size` (1–250, default 50). Returns `{total, page, page_size, results[]}`. |
| `GET /api/export` | Same filters as `/api/search` (no paging); downloads all matches as `paperlist_export.csv` (UTF-8 with BOM). |

## Layout

```
webapp/
├── app.py          # Flask routes + startup CSV load
├── loader.py       # CSV -> normalized records (per-file schema handling)
├── search.py       # filter / search / paginate / CSV export
├── static/         # index.html, app.js, style.css
└── tests/          # pytest unit tests for loader and search
```

The per-file schema mapping lives in `loader.py` (`_PROFILES`, plus shared
MICCAI/MIDL profiles); it mirrors the "CSV file structure" table in the
repository root `README.md`. Schema quirks (headerless files, `Keywords:` /
`Abstract:` prefixes, the MICCAI/MIDL link columns, and non-UTF-8 bytes in one
file) are all handled there.

## Tests

```bash
pip install pytest
cd webapp && python -m pytest tests/ -q
```
