"""Flask app serving the paper-list search UI and JSON API.

Loads every conference CSV into memory once at startup, then answers search
queries against that in-memory list. Run with ``python app.py`` and open
http://127.0.0.1:5000/.
"""

from __future__ import annotations

import argparse
import logging

from flask import Flask, Response, jsonify, request, send_from_directory

import loader
import search

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", static_url_path="")

# Populated at startup by load_records().
RECORDS = []


def load_records():
    """Load all CSVs into the module-level RECORDS list."""
    global RECORDS
    RECORDS = loader.load_all()
    logger.info("Ready: %d papers loaded", len(RECORDS))


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/facets")
def api_facets():
    return jsonify(search.facets(RECORDS))


@app.route("/api/search")
def api_search():
    args = request.args
    result = search.search(
        RECORDS,
        q=args.get("q", ""),
        conference=args.getlist("conference"),
        year=args.getlist("year"),
        keyword=args.get("keyword", ""),
        page=args.get("page", 1),
        page_size=args.get("page_size", search.DEFAULT_PAGE_SIZE),
    )
    return jsonify(result)


@app.route("/api/export")
def api_export():
    """Download every paper matching the search filters as a CSV file."""
    args = request.args
    matched = search.filter_records(
        RECORDS,
        q=args.get("q", ""),
        conference=args.getlist("conference"),
        year=args.getlist("year"),
        keyword=args.get("keyword", ""),
    )
    # A UTF-8 BOM lets Excel detect the encoding of non-ASCII names.
    body = "﻿" + search.to_csv(matched)
    return Response(
        body,
        mimetype="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="paperlist_export.csv"'},
    )


def main():
    parser = argparse.ArgumentParser(description="Paper list search web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    cli = parser.parse_args()

    load_records()
    app.run(host=cli.host, port=cli.port, debug=cli.debug)


if __name__ == "__main__":
    main()
