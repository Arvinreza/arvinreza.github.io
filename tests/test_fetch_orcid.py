import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fetch_orcid import (deduplicate, entry_from_group, extract_doi, merge_manual, normalize_doi,
                         title_key, year_from_orcid)


class TestORCIDNormalization(unittest.TestCase):
    def setUp(self):
        self.summary = {
            "title": {"title": {"value": "Sample Research Article"}},
            "journal-title": {"value": "Journal of Testing"},
            "publication-date": {"year": {"value": "2025"}},
            "publication-type": "journal-article",
            "external-ids": {"external-id": [{"external-id-type": "doi", "external-id-value": "https://doi.org/10.1234/ABC"}]},
            "url": {"value": "https://example.org/paper"},
        }

    def test_normalizes_doi(self):
        self.assertEqual(normalize_doi("DOI: 10.1234/ABC"), "10.1234/abc")
        self.assertEqual(normalize_doi("https://doi.org/10.1234/ABC"), "10.1234/abc")
        self.assertEqual(normalize_doi("javascript:alert(1)"), "")

    def test_extracts_orcid_work(self):
        work = entry_from_group({"work-summary": [self.summary]})
        self.assertEqual(work["title"], "Sample Research Article")
        self.assertEqual(work["year"], 2025)
        self.assertEqual(work["venue"], "Journal of Testing")
        self.assertEqual(work["type_label"], "Journal article")
        self.assertEqual(work["doi"], "10.1234/abc")

    def test_group_level_doi(self):
        summary = {**self.summary, "external-ids": {"external-id": []}}
        group = {"work-summary": [summary], "external-ids": {"external-id": [{"external-id-type": "doi", "external-id-value": "10.2345/DEF"}]}}
        self.assertEqual(extract_doi(summary, group), "10.2345/def")

    def test_deduplicate(self):
        a = entry_from_group({"work-summary": [self.summary]})
        b = dict(a)
        b["authors"] = ["A. Author"]
        result = deduplicate([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["authors"], ["A. Author"])

    def test_year_validation(self):
        self.assertEqual(year_from_orcid({"publication-date": {"year": {"value": "2027"}}}), 2027)
        self.assertIsNone(year_from_orcid({"publication-date": {"year": {"value": "n/a"}}}))

    def test_manual_overrides(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            path = Path(temp) / "manual.json"
            path.write_text(json.dumps([{"title": "Sample Research Article", "doi": "10.1234/ABC", "venue": "Corrected journal"}]))
            result = merge_manual([entry_from_group({"work-summary": [self.summary]})], path)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["venue"], "Corrected journal")


if __name__ == "__main__":
    unittest.main()
