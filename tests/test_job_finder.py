import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from job_finder import select_jobs


class SelectionTests(unittest.TestCase):
    def test_filter_and_deduplicate(self):
        base = {"title": "Python Developer", "companyName": "Example", "guid": "https://example.org/job/1", "excerpt": "Remote role", "locationRestrictions": []}
        raw = [base, {**base, "guid": "https://example.org/job/1?ref=other"}, {**base, "title": "Python Intern", "guid": "https://example.org/job/2"}]
        config = {"include_any": ["python"], "exclude_any": ["intern"], "max_results": 50}
        result = select_jobs(raw, config)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "https://example.org/job/1")


if __name__ == "__main__":
    unittest.main()

