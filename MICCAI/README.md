# MICCAI Paper Lists

Accepted-paper lists for the **MICCAI** (International Conference on Medical
Image Computing and Computer Assisted Intervention) conference. Each year's data
is provided as a `MICCAI<YEAR>_Paper_List_with_Abstract.csv` file containing the
full records including abstracts.

## Statistics

| Year | Papers | Topic categories | With code | With dataset |
| --- | --- | --- | --- | --- |
| 2026 | 1,165 | 81 | 856 | 462 |
| 2025 | 1,027 | 59 | 710 | 375 |
| 2024 | 856 | 69 | 581 | 310 |
| 2023 | 730 | 57 | 467 | 285 |
| 2022 | 573 | 55 | 336 | 211 |
| 2021 | 531 | 52 | 271 | 166 |

"Topic categories" is the number of distinct labels in the `Topics` column;
each paper carries several. Across every year the most common topics are
**Image Segmentation**, **Computer-Aided Diagnosis**, and **MRI** imaging.
Accepted-paper counts have grown steadily (531 → 1,165), as has the share of
papers releasing code (≈51% → ≈73%).

> Note: MICCAI 2025 reformatted its topic labels into a hierarchical
> "Area -> Subtopic" form (earlier years use a flatter "Area - Subtopic"), so
> the category counts are not strictly comparable across the 2024/2025 boundary.
> MICCAI 2026 keeps the hierarchical form but adds more subtopics and tweaks
> some spellings (e.g. `Computer-Aided Diagnosis`, `CT / X-ray` vs. 2025's
> `Computer Aided Diagnosis`, `CT / X-Ray`), so match labels case- and
> hyphen-insensitively when comparing 2025 and 2026.

## Sources & credits

The data in this directory is built from the official MICCAI accepted-paper
pages. All credit for the original paper listings goes to the MICCAI Society and
the respective conference organizers.

| Year | Source |
| --- | --- |
| MICCAI 2026 | https://papers.miccai.org/miccai-2026/ |
| MICCAI 2025 | https://papers.miccai.org/miccai-2025/ |
| MICCAI 2024 | https://papers.miccai.org/miccai-2024/ |
| MICCAI 2023 | https://conferences.miccai.org/2023/papers/ |
| MICCAI 2022 | https://conferences.miccai.org/2022/papers/ |
| MICCAI 2021 | https://miccai2021.org/openaccess/paperlinks/index.html |

## CSV columns

Every `MICCAI<YEAR>_Paper_List_with_Abstract.csv` has a header row and the same
eight columns:

| Column | Description |
| --- | --- |
| `Title` | Paper title. |
| `Authors` | `;`-separated authors, `Last, First`. |
| `Topics` | `; `-separated topic categories (may be empty if none were listed). |
| `Abstract` | Full abstract. |
| `Code` | `;`-separated code-repository URL(s); empty when not provided. |
| `Dataset` | `;`-separated dataset URL(s); empty when not provided. |
| `PDF` | Open-access PDF link (2024 – 2026), or the DOI / SpringerLink (2021 – 2023, which have no open-access PDF). |
| `Paper Page` | The per-paper detail page the record was scraped from. |

## Regenerating the data

The CSVs are produced by [`../scripts/scrape_miccai.py`](../scripts/scrape_miccai.py)
(Python standard library only — no dependencies). The hosting and HTML layout
changed across editions, so the scraper picks a site profile per year
automatically; years without an explicit entry (such as 2026) fall back to the
modern `papers.miccai.org/miccai-<year>/` layout.

```bash
python scripts/scrape_miccai.py --year 2026      # any year 2021–2026
python scripts/scrape_miccai.py --year 2025 --limit 10   # quick smoke test
```

Downloaded pages are cached under `MICCAI/.cache/<year>/`, so re-runs and
interrupted runs are fast and resumable. Useful flags: `--workers`, `--delay`,
`--out`, `--cache-dir`.
