#!/usr/bin/env python3
"""Build a deterministic publication list from public ORCID works.

Public ORCID works determine inclusion; Crossref only enriches DOI metadata.
Manual additions/overrides go in data/manual_publications.json.
No third-party Python packages or secrets are required for ordinary public reads.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ORCID_ID = "0000-0002-9630-9680"
ORCID_ENDPOINT = f"https://pub.orcid.org/v3.0/{ORCID_ID}/works"
CROSSREF_ENDPOINT = "https://api.crossref.org/works/"
ROOT = Path(__file__).resolve().parents[1]
TYPE_LABELS = {
    "journal-article": "Journal article", "journal-issue": "Journal issue",
    "preprint": "Preprint", "posted-content": "Preprint", "working-paper": "Working paper",
    "book": "Book", "edited-book": "Edited book", "book-chapter": "Book chapter",
    "book-section": "Book chapter", "conference-paper": "Conference paper",
    "conference-abstract": "Conference abstract", "dissertation": "Thesis",
    "thesis": "Thesis", "report": "Report", "dataset": "Dataset",
    "research-tool": "Research tool", "other": "Other research output",
}
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def get_json(url: str, token: str | None = None, timeout: int = 20, tries: int = 3, accept: str = "application/json") -> dict:
    headers = {
        "Accept": accept,
        "User-Agent": "Koplenig-publications-site/1.0 (https://github.com/Koplenig/koplenig.github.io)",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_error = None
    for attempt in range(tries):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            last_error = exc
            status = getattr(exc, "code", None)
            if status and status not in (429, 500, 502, 503, 504):
                break
            if attempt < tries - 1:
                time.sleep(attempt + 1)
    raise RuntimeError(f"GET {url}: {last_error}") from last_error


def nested_text(obj, *path) -> str:
    for key in path:
        if not isinstance(obj, dict):
            return ""
        obj = obj.get(key)
    return obj.strip() if isinstance(obj, str) else ""


def year_from_orcid(summary: dict) -> int | None:
    value = nested_text(summary, "publication-date", "year", "value")
    return int(value) if len(value) == 4 and value.isdigit() and 1500 <= int(value) <= 2100 else None


def normalize_doi(value: str | None) -> str:
    value = (value or "").strip()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", value, flags=re.I)
    value = value.strip()
    return value.lower() if DOI_RE.fullmatch(value) else ""


def extract_doi(summary: dict, group: dict | None = None) -> str:
    for source in (summary, group or {}):
        values = (source.get("external-ids") or {}).get("external-id") or []
        for item in values:
            if (item.get("external-id-type") or "").lower() == "doi":
                doi = normalize_doi(item.get("external-id-value") or "")
                if doi:
                    return doi
    return ""


def entry_from_group(group: dict) -> dict | None:
    summaries = group.get("work-summary") or []
    if not isinstance(summaries, list):
        return None
    valid = [s for s in summaries if isinstance(s, dict) and nested_text(s, "title", "title", "value")]
    if not valid:
        return None
    def score(item):
        return sum((4 if extract_doi(item, group) else 0, 2 if year_from_orcid(item) else 0,
                    1 if nested_text(item, "journal-title", "value") else 0))
    summary = max(valid, key=score)
    doi = extract_doi(summary, group)
    raw_type = summary.get("publication-type") or summary.get("type") or "other"
    title = nested_text(summary, "title", "title", "value")
    subtitle = nested_text(summary, "title", "subtitle", "value")
    if subtitle and subtitle.casefold() not in title.casefold():
        title += ": " + subtitle
    url = nested_text(summary, "url", "value")
    if not url.startswith(("https://", "http://")):
        url = ""
    return {
        "title": title, "year": year_from_orcid(summary),
        "type_label": TYPE_LABELS.get(raw_type, str(raw_type).replace("-", " ").capitalize()),
        "doi": doi, "url": url, "venue": nested_text(summary, "journal-title", "value"),
        "authors": [], "volume": "", "issue": "", "pages": "", "source": "orcid",
    }


def title_key(record: dict) -> str:
    return re.sub(r"[^\w]+", "", (record.get("title") or "").casefold())


def deduplicate(entries: list[dict]) -> list[dict]:
    """Deduplicate ORCID source records; prefer records with fuller metadata."""
    by_key: dict[str, dict] = {}
    for entry in entries:
        doi = normalize_doi(entry.get("doi"))
        key = "doi:" + doi if doi else "title:" + title_key(entry)
        if not key or key == "title:":
            continue
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = dict(entry)
            continue
        for field in ("title", "year", "doi", "url", "venue", "authors", "volume", "issue", "pages", "type_label"):
            if not existing.get(field) and entry.get(field):
                existing[field] = entry[field]
    return list(by_key.values())


def crossref_metadata(doi: str) -> dict:
    url = CROSSREF_ENDPOINT + quote(doi, safe="/")
    mailto = os.environ.get("CROSSREF_MAILTO", "").strip()
    if mailto:
        url += "?" + urlencode({"mailto": mailto})
    try:
        data = get_json(url, timeout=9, tries=1).get("message") or {}
    except Exception as exc:
        print(f"Crossref enrichment unavailable for {doi}: {exc}", file=sys.stderr)
        return {}
    authors = []
    for a in data.get("author") or []:
        if not isinstance(a, dict):
            continue
        name = " ".join(p for p in ((a.get("given") or "").strip(), (a.get("family") or "").strip()) if p)
        name = name or (a.get("name") or "").strip()
        if name:
            authors.append(name)
    venue = data.get("container-title") or []
    venue = venue[0] if isinstance(venue, list) and venue else (venue if isinstance(venue, str) else "")
    year = None
    for date_key in ("published", "published-print", "published-online", "issued", "created"):
        date = (data.get(date_key) or {}).get("date-parts") or []
        if date and date[0] and isinstance(date[0][0], int):
            year = date[0][0]
            break
    return {
        "authors": authors, "venue": venue, "volume": data.get("volume") or "",
        "issue": data.get("issue") or "", "pages": data.get("page") or data.get("article-number") or "",
        "year": year,
    }


def enrich(entries: list[dict], workers: int = 4) -> None:
    doi_entries = {e["doi"]: e for e in entries if e.get("doi")}
    if not doi_entries:
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(crossref_metadata, doi): doi for doi in doi_entries}
        for future in as_completed(futures):
            item = doi_entries[futures[future]]
            extra = future.result()
            for field in ("authors", "venue", "volume", "issue", "pages", "year"):
                if extra.get(field) and not item.get(field):
                    item[field] = extra[field]


def merge_manual(entries: list[dict], manual_path: Path) -> list[dict]:
    if not manual_path.is_file():
        return entries
    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    if not isinstance(manual, list):
        raise ValueError("data/manual_publications.json must contain a JSON array")
    for addition in manual:
        if not isinstance(addition, dict) or not addition.get("title"):
            raise ValueError("Each manual record requires a title")
        addition = dict(addition)
        addition["doi"] = normalize_doi(addition.get("doi"))
        addition.setdefault("source", "manual")
        addition.setdefault("type_label", "Research output")
        addition.setdefault("authors", [])
        match = next((e for e in entries if addition["doi"] and e.get("doi") == addition["doi"]), None)
        if not match:
            match = next((e for e in entries if title_key(e) == title_key(addition)), None)
        if match:
            match.update({k: v for k, v in addition.items() if v is not None and v != ""})
        else:
            entries.append(addition)
    return deduplicate(entries)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=ROOT / "data/publications.json")
    ap.add_argument("--no-crossref", action="store_true", help="Use ORCID metadata only")
    args = ap.parse_args()
    token = os.environ.get("ORCID_ACCESS_TOKEN") or None
    print(f"Fetching public ORCID works from {ORCID_ID}…")
    try:
        payload = get_json(ORCID_ENDPOINT, token=token, accept="application/vnd.orcid+json")
        groups = payload.get("group")
        if not isinstance(groups, list):
            raise ValueError("ORCID API response has no work groups")
        entries = deduplicate([item for group in groups if (item := entry_from_group(group))])
        print(f"Found {len(entries)} deduplicated ORCID works in {len(groups)} groups")
    except Exception as exc:
        if args.output.is_file():
            try:
                cached = json.loads(args.output.read_text(encoding="utf-8"))
                if cached.get("publications"):
                    print(f"WARNING: ORCID refresh failed; keeping cached {len(cached['publications'])} works: {exc}", file=sys.stderr)
                    return 0
            except (ValueError, OSError, TypeError):
                pass
        print(f"ERROR: ORCID refresh failed, no usable cache: {exc}", file=sys.stderr)
        return 1
    if not args.no_crossref:
        enrich(entries)
    entries = merge_manual(entries, ROOT / "data/manual_publications.json")
    entries.sort(key=lambda e: (-(e.get("year") or 0), (e.get("title") or "").casefold()))
    result = {
        "orcid": ORCID_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "publications": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} works to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
