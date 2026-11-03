#!/usr/bin/env python3
"""Extract one publication CSV from the IDS Mannheim author bibliography.

This retains distinct versions/preprints, drops only the HTML's repeated
collapsed/expanded display fragments, and keeps the source's own publication years.
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import Request, urlopen
import csv
import re

URL = "https://pub.ids-mannheim.de/autoren/ids/koplenig.html"
OUT = Path(__file__).resolve().parents[1] / "data/publications_ids.csv"
FIELDNAMES = [
    "year", "authors", "title", "publication_details", "doi",
    "publication_url", "ids_repository_url", "full_text_url",
    "full_reference", "source_url",
]


def clean(text):
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def title_and_details(biblio: str, dd) -> tuple[str, str]:
    # Ordinary journal articles and book chapters have 'In:' as delimiter.
    m = re.search(r"([.?!])\s+In:\s+", biblio)
    if m:
        suffix = m.group(1) if m.group(1) != "." else ""
        return biblio[: m.start()].strip() + suffix, biblio[m.start() + len(m.group(1)) + 1 :].strip()

    # A minority of dissertations, preprints, software and other standalone
    # items do not have an 'In:'. These use a publisher/location delimiter.
    m = re.search(
        r"([.?!])\s+(?=(?:Dissertation\.|Arbeitspapier\.|"
        r"(?:Charlottesville(?:, VA)?|Ithaca, NY|Mannheim|Oxford|Berlin/Boston|"
        r"Bozen|OSF Preprints|Stata program|\(=)\b))",
        biblio
    )
    if m:
        suffix = m.group(1) if m.group(1) != "." else ""
        return biblio[: m.start()].strip() + suffix, biblio[m.end() :].strip()

    # Titles linked directly at the beginning of the bibliographic item
    # provide an additional reliable boundary when present.
    first_tag = next((c for c in dd.children if getattr(c, "name", None) is not None), None)
    if first_tag and first_tag.name == "a":
        text = clean(first_tag.get_text(" ", strip=True))
        if len(text) >= 18 and biblio.startswith(text):
            return text.rstrip(" ."), biblio[len(text):].lstrip(" .")

    # Fallback: preserve the entire original item and flag for review below.
    return "", biblio


def parse_row(dt, dd):
    byline = clean(dt.get_text(" ", strip=True))
    match = re.fullmatch(r"(.+?) \((\d{4})\):", byline)
    if not match:
        raise ValueError(f"Unexpected author/year line: {byline}")
    authors, year = match.group(1), int(match.group(2))

    # Remove only trailing arrow links; links embedded within the actual
    # bibliographic description are retained as text.
    bibliography = clean(dd.get_text(" ", strip=True).split(" → ")[0])
    title, details = title_and_details(bibliography, dd)
    urls = {}
    for link in dd.find_all("a", href=True):
        href = urljoin(URL, link["href"])
        label = clean(link.get_text(" ", strip=True)).lower()
        if label == "ids-publikationsserver":
            urls.setdefault("ids_repository_url", href)
        elif label == "text":
            urls.setdefault("full_text_url", href)
        elif label in ("verlag", "datenbank", "externes repositorium"):
            urls.setdefault("publication_url", href)

        path = unquote(urlsplit(href).path).lstrip("/")
        if "doi.org" in urlsplit(href).netloc.lower():
            if path.startswith("10."):
                urls.setdefault("doi", path)
                urls["publication_url"] = "https://doi.org/" + path

    # If there is no external publisher link, use the IDS record as the main link.
    urls.setdefault("publication_url", urls.get("ids_repository_url") or urls.get("full_text_url") or "")

    return {
        "year": year,
        "authors": authors.replace("/", "; "),
        "title": title,
        "publication_details": details,
        "doi": urls.get("doi", ""),
        "publication_url": urls.get("publication_url", ""),
        "ids_repository_url": urls.get("ids_repository_url", ""),
        "full_text_url": urls.get("full_text_url", ""),
        "full_reference": f"{byline} {bibliography}",
        "source_url": URL,
    }


def extract(html: bytes) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    # The two *_0 views show abbreviated duplicates; use only full *_1.
    for container, expected_count in [("pubm_1", 2), ("pubb_1", 75)]:
        div = soup.find("div", id=container)
        if div is None:
            raise ValueError(f"Expected bibliography container #{container} missing")
        dl = div.find("dl", class_="pub_xdb_entry")
        if dl is None:
            raise ValueError(f"Bibliography list missing from #{container}")
        dt_elements = dl.find_all("dt", recursive=False)
        dd_elements = dl.find_all("dd", recursive=False)
        if len(dt_elements) != expected_count or len(dd_elements) != expected_count:
            raise ValueError(
                f"Count mismatch for #{container}: {len(dt_elements)} author lines, "
                f"{len(dd_elements)} references, expected {expected_count}"
            )
        records.extend(parse_row(dt, dd) for dt, dd in zip(dt_elements, dd_elements))

    # The source has 77 independent bibliographic records, including variant versions.
    if len(records) != 77:
        raise ValueError(f"Expected 77 source entries, found {len(records)}")
    if any(not r["title"] for r in records):
        for r in records:
            if not r["title"]:
                print("MISSING TITLE EXTRACTION:", r["year"], r["full_reference"][:240])
        raise ValueError("Title extraction incomplete; refusing to publish inaccurate CSV")
    # Preserve source order within year; sort only by year as requested.
    return sorted(records, key=lambda r: -r["year"])


def main():
    request = Request(URL, headers={"User-Agent": "Mozilla/5.0 (Academic bibliography import; https://github.com/Koplenig/koplenig.github.io)"})
    with urlopen(request, timeout=40) as response:
        html = response.read()
    records = extract(html)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)
    print(f"Wrote {len(records)} IDS publications to {OUT}")
    print("Years:", dict(sorted(Counter(r["year"] for r in records).items(), reverse=True)))
    print("With DOI:", sum(bool(r["doi"]) for r in records))
    print("With source-specific URL:", sum(bool(r["publication_url"]) for r in records))
    for r in records[:5]:
        print(f"  {r['year']}: {r['title']}")

if __name__ == "__main__":
    main()
