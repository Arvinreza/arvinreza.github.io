#!/usr/bin/env python3
"""Validate the manually maintained CSV before GitHub Pages deployment."""
from __future__ import annotations
import csv
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
CSV=ROOT/"data/publications_manual.csv"
REQUIRED=["year","authors","title","publication_details","doi","publication_url","preprint_url","data_url","related_url","related_label","full_text_url"]
URL_COLUMNS=["publication_url","preprint_url","data_url","related_url","full_text_url"]


def main():
    with CSV.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if not rows:
        raise ValueError("Publications CSV is empty")
    if any(k not in rows[0] for k in REQUIRED):
        raise ValueError("Required column missing from publications CSV")
    years=[]
    dois=set()
    for n,row in enumerate(rows,2):
        for key in ("year","authors","title"):
            if not (row.get(key) or "").strip():
                raise ValueError(f"Line {n}: missing {key}")
        year=int(row["year"])
        if year<1900 or year>2100:
            raise ValueError(f"Line {n}: implausible publication year {year}")
        years.append(year)
        doi=row["doi"].strip().lower()
        if doi:
            if not re.fullmatch(r"10\.\d{4,9}/\S+",doi,re.I):
                raise ValueError(f"Line {n}: invalid DOI {doi}")
            if doi in dois:
                raise ValueError(f"Line {n}: duplicate DOI {doi}")
            dois.add(doi)
        for key in URL_COLUMNS:
            value=(row.get(key) or "").strip()
            if value and urlsplit(value).scheme not in ("http","https"):
                raise ValueError(f"Line {n}: invalid URL in {key}")
        if row.get("related_label") and not row.get("related_url"):
            raise ValueError(f"Line {n}: related_label needs related_url")
    if years!=sorted(years,reverse=True):
        raise ValueError("Publications must be sorted by descending year")
    for path in ["index.html","assets/style.css","assets/site.js","assets/profile.jpg"]:
        if not (ROOT/path).is_file():
            raise ValueError(f"Required site asset missing: {path}")
    print(f"Validation PASS: {len(rows)} publications, years {min(years)}–{max(years)}, {len(dois)} DOIs")


if __name__=="__main__":
    main()
