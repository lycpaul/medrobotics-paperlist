# IPCAI Paper Lists

Accepted-paper lists for the **IPCAI** (International Conference on Information
Processing in Computer-Assisted Interventions) conference. Each year's data is
provided as an `IPCAI<YEAR>_Paper_List_with_Abstract.csv` file. Both **regular
papers** and **long abstracts** are included where the program lists them.

> IPCAI's program pages list only each paper's **title and authors**. There is
> no per-paper page, so the `Abstract` and `PDF` columns exist only to match the
> other conferences' schema and are **always empty**. The file names keep the
> `_with_Abstract` suffix for the same reason.

## Statistics

| Year | Papers | Regular papers | Long abstracts | Unique authors |
| --- | --- | --- | --- | --- |
| 2026 | 99 | 75 | 24 | 522 |
| 2025 | 58 | 58 | 0 | 308 |
| 2024 | 62 | 50 | 12 | 324 |
| 2023 | 62 | 47 | 15 | 330 |
| 2022 | 39 | — | — | 256 |
| **Total** | **320** | | | |

> The 2022 program does not separate regular papers from long abstracts, so all
> 39 records fall under one heading. The 2026 long abstracts come from two
> tracks: 20 late-breaking research submissions and 4 journal-article
> presentations.

## `Session` values by year

The `Session` column holds the program heading a paper was listed under. The
headings differ from year to year:

| Year | `Session` values |
| --- | --- |
| 2026 | `Accepted regular paper submissions`, `Accepted Long Abstract Track 1: Late-breaking research submissions`, `Accepted Long Abstract Track 2: Journal article presentations submissions` |
| 2025 | `Accepted regular paper submissions` |
| 2024 | `Accepted regular paper submissions`, `Accepted long abstract submissions` |
| 2023 | Topic sessions (`Machine Learning for CAI`, `Surgical Simulation, Planning and Navigation`, `Computer Vision in Surgery`, `Robotics and Human-Computer Interaction`, `3D Reconstruction and Registration`), `Long Presentation Session (S6)`–`(S9)`, and `Long Abstracts` |
| 2022 | `Long Program Schedule` |

Only 2023 has topic labels in this column. In the other years it marks the
submission track only.

## Sources & credits

The data is built from the official IPCAI program pages (Google Sites). All
credit for the original paper listings goes to the IPCAI organizers and the
respective authors.

| Year | Source |
| --- | --- |
| IPCAI 2026 | https://sites.google.com/view/ipcai2026/program |
| IPCAI 2025 | https://sites.google.com/view/ipcai2025/program |
| IPCAI 2024 | https://sites.google.com/view/ipcai2024/program |
| IPCAI 2023 | https://sites.google.com/view/ipcai-2023/program |
| IPCAI 2022 | https://sites.google.com/view/ipcai2022/program |

## CSV columns

Every `IPCAI<YEAR>_Paper_List_with_Abstract.csv` has a header row and the same
six columns:

| Column | Description |
| --- | --- |
| `Title` | Paper title. |
| `Authors` | `;`-separated author names. Affiliations (2022/2023) and presenting-author `*` markers are removed. |
| `Session` | Program heading the paper was listed under (see above). |
| `Abstract` | Always empty (not published on the program page). |
| `PDF` | Always empty (not published on the program page). |
| `Paper Page` | The program page URL for that year (shared by every row). |

## Regenerating the data

The CSVs are produced by [`../scripts/scrape_ipcai.py`](../scripts/scrape_ipcai.py),
which uses only the Python standard library. Each edition's program page is
marked up differently, so the scraper uses a different parsing mode per year:

- **2024 – 2026 (`standard`)**: each title is a bold paragraph and the authors
  follow it.
- **2023 (`gated`)**: the page opens with a bold schedule section, so the
  scraper skips everything before the "Session Information" heading.
- **2022 (`id_suffix`)**: author lines are found by their trailing
  `[IPCAI-<n>]` tag, and the title is the bold paragraph just before each one.
  Papers listed twice on the source page are dropped.

```bash
python scripts/scrape_ipcai.py                # all years 2022-2026
python scripts/scrape_ipcai.py --year 2025    # a single edition
python scripts/scrape_ipcai.py --limit 5      # quick smoke test
```

Raw HTML is cached under `IPCAI/.cache/<year>.html`, so re-runs are fast.
Delete the cache to force a fresh fetch. If a year produces no papers, the page
layout has probably changed and the year's parsing mode needs updating.
