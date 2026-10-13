"""Tests for filtering, search, and pagination in ``search.py``."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import search  # noqa: E402


def make_record(conference="ICRA", year=2025, title="", authors="",
                session="", keywords="", abstract=""):
    return {
        "conference": conference, "year": year, "title": title,
        "authors": authors, "session": session, "keywords": keywords,
        "abstract": abstract, "affiliation": "", "links": {},
    }


RECORDS = [
    make_record(title="SLAM odometry", abstract="lidar based mapping",
                keywords="SLAM", session="SLAM 1"),
    make_record(conference="IROS", year=2024, title="Grasping objects",
                abstract="robotic manipulation", keywords="grasping",
                session="Manipulation"),
    make_record(conference="MICCAI", year=2023, title="Tumor segmentation",
                abstract="medical imaging with deep learning",
                keywords="segmentation", session="Diagnosis"),
]


def test_keyword_search_matches_title_case_insensitive():
    result = search.search(RECORDS, q="slam")
    assert result["total"] == 1
    assert result["results"][0]["title"] == "SLAM odometry"


def test_keyword_search_matches_abstract():
    result = search.search(RECORDS, q="manipulation")
    assert result["total"] == 1
    assert result["results"][0]["title"] == "Grasping objects"


def test_keyword_search_matches_keywords_field():
    result = search.search(RECORDS, q="segmentation")
    assert result["total"] == 1
    assert result["results"][0]["conference"] == "MICCAI"


def test_conference_filter():
    result = search.search(RECORDS, conference="IROS")
    assert result["total"] == 1
    assert result["results"][0]["conference"] == "IROS"


def test_year_filter_accepts_int_or_str():
    assert search.search(RECORDS, year=2023)["total"] == 1
    assert search.search(RECORDS, year="2023")["total"] == 1


def test_multi_value_conference_filter():
    result = search.search(RECORDS, conference=["ICRA", "IROS"])
    assert result["total"] == 2


def test_combined_filters_are_anded():
    assert search.search(RECORDS, conference="ICRA", q="grasping")["total"] == 0
    assert search.search(RECORDS, conference="IROS", q="grasping")["total"] == 1


def test_keyword_filter_matches_session():
    result = search.search(RECORDS, keyword="diagnosis")
    assert result["total"] == 1
    assert result["results"][0]["conference"] == "MICCAI"


def test_no_match_returns_empty():
    result = search.search(RECORDS, q="nonexistent term")
    assert result["total"] == 0
    assert result["results"] == []


def test_pagination_first_page():
    many = [make_record(title=f"Paper {i}") for i in range(120)]
    result = search.search(many, page=1, page_size=50)
    assert result["total"] == 120
    assert len(result["results"]) == 50
    assert result["page"] == 1


def test_pagination_last_partial_page():
    many = [make_record(title=f"Paper {i}") for i in range(120)]
    result = search.search(many, page=3, page_size=50)
    assert len(result["results"]) == 20


def test_pagination_out_of_range_returns_empty_with_total():
    many = [make_record(title=f"Paper {i}") for i in range(10)]
    result = search.search(many, page=99, page_size=50)
    assert result["total"] == 10
    assert result["results"] == []


def test_page_size_is_capped():
    many = [make_record(title=f"Paper {i}") for i in range(500)]
    result = search.search(many, page_size=99999)
    assert result["page_size"] == search.MAX_PAGE_SIZE


def test_invalid_page_defaults_to_one():
    result = search.search(RECORDS, page="abc")
    assert result["page"] == 1


def test_facets():
    result = search.facets(RECORDS)
    assert result["conferences"] == ["ICRA", "IROS", "MICCAI"]
    assert result["years"] == [2025, 2024, 2023]


def test_filter_records_returns_all_matches_unpaginated():
    many = [make_record(title=f"Paper {i}") for i in range(250)]
    assert len(search.filter_records(many, q="paper")) == 250
    assert search.filter_records(RECORDS, conference="IROS")[0]["title"] == \
        "Grasping objects"


def test_to_csv_columns_and_quoting():
    import csv
    import io

    record = make_record(conference="MICCAI", year=2026, title='A "quoted", title',
                         authors="Doe, Jane; Roe, Rick", session="Seg",
                         keywords="MRI", abstract="line one\nline two")
    record["links"] = {"pdf": "http://x/p.pdf", "code": "http://x/code"}
    rows = list(csv.reader(io.StringIO(search.to_csv([record]))))
    assert rows[0] == search.EXPORT_COLUMNS
    assert rows[1] == ['A "quoted", title', "Doe, Jane; Roe, Rick",
                       "MICCAI 2026", "Seg", "MRI", "http://x/p.pdf",
                       "http://x/code", "", "", "line one\nline two"]
