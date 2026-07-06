"""Tests for schema normalization in ``loader.py``."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import loader  # noqa: E402


def write_csv(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_parse_filename():
    assert loader.parse_filename("ICRA2025_Paper_List_with_Abstract.csv") == (
        "ICRA", 2025)
    assert loader.parse_filename(
        "/a/b/MICCAI2021_Paper_List_with_Abstract.csv") == ("MICCAI", 2021)
    assert loader.parse_filename("not_a_paper_file.csv") is None


def test_icra2023_with_header_and_organisation(tmp_path):
    path = write_csv(tmp_path, "ICRA2023_Paper_List_with_Abstract.csv",
                     "Title,Authors,Organisation,Session,Abstract\n"
                     "My Paper,\"Doe, Jane\",MIT,SLAM 1,An abstract here.\n")
    [rec] = loader.load_file(path)
    assert rec["conference"] == "ICRA"
    assert rec["year"] == 2023
    assert rec["title"] == "My Paper"
    assert rec["affiliation"] == "MIT"
    assert rec["session"] == "SLAM 1"
    assert rec["abstract"] == "An abstract here."
    assert rec["keywords"] == ""


def test_icra2024_headerless(tmp_path):
    path = write_csv(tmp_path, "ICRA2024_Paper_List_with_Abstract.csv",
                     "Gauge Reading,\"Doe, J\",ETH Zurich,Automation,Body.\n")
    [rec] = loader.load_file(path)
    assert rec["title"] == "Gauge Reading"
    assert rec["affiliation"] == "ETH Zurich"
    assert rec["session"] == "Automation"
    assert rec["abstract"] == "Body."


def test_icra2025_prefix_stripping_and_trailing_columns(tmp_path):
    path = write_csv(tmp_path, "ICRA2025_Paper_List_with_Abstract.csv",
                     "Session,Paper Title,Author List, Keywords, Abstract,,,\n"
                     "SLAM 1,POMDP Paper,\"Yotam, T\","
                     "\"Keywords: SLAM, Planning\","
                     "\"Abstract: Decision making.\",,,\n")
    [rec] = loader.load_file(path)
    assert rec["title"] == "POMDP Paper"
    assert rec["session"] == "SLAM 1"
    assert rec["keywords"] == "SLAM, Planning"
    assert rec["abstract"] == "Decision making."


def test_icra2026_with_affiliation(tmp_path):
    path = write_csv(tmp_path, "ICRA2026_Paper_List_with_Abstract.csv",
                     "Session,Paper Title,Author List,Affiliation, Keywords, "
                     "Abstract\n"
                     "Session 1,STS Paper,\"Mahdi, A\",Waterloo,"
                     "\"Keywords: HRI\",\"Abstract: STS transfer.\"\n")
    [rec] = loader.load_file(path)
    assert rec["title"] == "STS Paper"
    assert rec["affiliation"] == "Waterloo"
    assert rec["keywords"] == "HRI"
    assert rec["abstract"] == "STS transfer."


def test_iros2023_headerless_prefixed(tmp_path):
    path = write_csv(tmp_path, "IROS2023_Paper_List_with_Abstract.csv",
                     " Radar Transformer,\"Zeller, M, CARIAD\","
                     "\"Keywords: Segmentation\",\"Abstract: Scene.\"\n")
    [rec] = loader.load_file(path)
    assert rec["title"] == "Radar Transformer"  # leading space stripped
    assert rec["keywords"] == "Segmentation"
    assert rec["abstract"] == "Scene."


def test_iros2024_empty_keyword_abstract(tmp_path):
    path = write_csv(tmp_path, "IROS2024_Paper_List_with_Abstract.csv",
                     "Hologram Design,\"Liu, Q\",,\n")
    [rec] = loader.load_file(path)
    assert rec["title"] == "Hologram Design"
    assert rec["keywords"] == ""
    assert rec["abstract"] == ""


def test_miccai_links(tmp_path):
    path = write_csv(tmp_path, "MICCAI2025_Paper_List_with_Abstract.csv",
                     "Title,Authors,Topics,Abstract,Code,Dataset,PDF,"
                     "Paper Page\n"
                     "Tokenizer,\"Li, S\",CT; Diagnosis,Body text,"
                     "http://code,http://data,http://pdf,http://page\n")
    [rec] = loader.load_file(path)
    assert rec["conference"] == "MICCAI"
    assert rec["session"] == "CT; Diagnosis"  # Topics -> session
    assert rec["links"]["code"] == "http://code"
    assert rec["links"]["dataset"] == "http://data"
    assert rec["links"]["pdf"] == "http://pdf"
    assert rec["links"]["paper_page"] == "http://page"


def test_ipcai_links(tmp_path):
    path = write_csv(tmp_path, "IPCAI2025_Paper_List_with_Abstract.csv",
                     "Title,Authors,Session,Abstract,PDF,Paper Page\n"
                     "Catheter Detection,\"Xi, L;Ma, Y\","
                     "Accepted regular paper submissions,,,http://page\n")
    [rec] = loader.load_file(path)
    assert rec["conference"] == "IPCAI"
    assert rec["session"] == "Accepted regular paper submissions"
    assert rec["abstract"] == ""
    assert rec["links"]["pdf"] == ""
    assert rec["links"]["paper_page"] == "http://page"


def test_rows_without_title_are_skipped(tmp_path):
    path = write_csv(tmp_path, "ICRA2024_Paper_List_with_Abstract.csv",
                     ",\"Doe, J\",ETH,Automation,Body.\n"
                     "Real Paper,\"Doe, J\",ETH,Automation,Body.\n")
    records = loader.load_file(path)
    assert len(records) == 1
    assert records[0]["title"] == "Real Paper"


def test_multiline_abstract_parsed_with_csv_reader(tmp_path):
    path = write_csv(tmp_path, "ICRA2023_Paper_List_with_Abstract.csv",
                     "Title,Authors,Organisation,Session,Abstract\n"
                     "P,\"Doe, J\",MIT,S,\"Line one.\nLine two.\"\n")
    [rec] = loader.load_file(path)
    assert "Line one." in rec["abstract"]
    assert "Line two." in rec["abstract"]
