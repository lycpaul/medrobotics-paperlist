# IROS Paper Lists

Accepted-paper lists for the **IROS** (IEEE/RSJ International Conference on
Intelligent Robots and Systems) conference. For 2023 – 2025 there is a Markdown
table (`IROS<YEAR>_Paper_List.md`) for quick browsing and a
`IROS<YEAR>_Paper_List_with_Abstract.csv` with the full records including
abstracts; 2026 has the CSV only.

## Statistics

| Year | Papers | Program sessions |
| --- | --- | --- |
| 2026 | 1,929 | 348 |
| 2025 | 2,675 | 359 |
| 2024 | 1,587 | — |
| 2023 | 1,704 | — |

"Program sessions" counts the distinct session/track labels papers are grouped
under. The 2023 and 2024 lists don't carry session labels, so it isn't
computable for those years; the 2023 list does include a summary table spanning
**34 keyword categories** (e.g. Planning, Motion and Path Planning,
Reinforcement Learning, Grasping).

The 2026 list also records each paper's presentation **type**: 1,308 Lightning
Talks, 578 Focused Sessions, 32 Award Candidates, and 11 Special Sessions.
20 of the 1,929 papers have no abstract on the program site, so their
`Abstract` cell is empty.

## Sources & credits

IROS 2026 is scraped directly from the official
[IROS 2026 program site](https://2026.ieee-iros.org/program/paper-index/) by
[`../scripts/scrape_iros.py`](../scripts/scrape_iros.py) (see below).

The 2023 – 2025 data is collected from the official IROS conference program
pages and is sourced from the following community-maintained paper-list
repositories. All credit for the original compilation goes to their authors.

| Year | Original repository | Author |
| --- | --- | --- |
| IROS 2025 | [DoongLi/IROS2025-Paper-List](https://github.com/DoongLi/IROS2025-Paper-List) | [Dong Li (@DoongLi)](https://github.com/DoongLi) |
| IROS 2024 | [ryanbgriffiths/IROS2024PaperList](https://github.com/ryanbgriffiths/IROS2024PaperList) | [Ryan Griffiths (@ryanbgriffiths)](https://github.com/ryanbgriffiths) |
| IROS 2023 | [ryanbgriffiths/IROS2023PaperList](https://github.com/ryanbgriffiths/IROS2023PaperList) | [Ryan Griffiths (@ryanbgriffiths)](https://github.com/ryanbgriffiths) |

If you use these lists, please consider starring and crediting the original
repositories above.

## Regenerating the 2026 data

`IROS2026_Paper_List_with_Abstract.csv` is produced by
[`../scripts/scrape_iros.py`](../scripts/scrape_iros.py) (Python standard
library only — no dependencies). It reads the JSON embedded in two program
pages, the paper index (title, authors, keywords, session, type) and the
contributed-talks page (abstracts), and joins them on paper number. Columns:

`Session, Type, Paper Title, Author List, Keywords, Abstract`

`Author List` and `Keywords` are `;`-separated. The raw pages are cached in
`IROS/.cache/` (git-ignored); pass `--refresh` to re-download them.

```bash
python scripts/scrape_iros.py               # IROS 2026
python scripts/scrape_iros.py --refresh     # ignore the HTML cache
python scripts/scrape_iros.py --limit 5     # quick smoke test
```
