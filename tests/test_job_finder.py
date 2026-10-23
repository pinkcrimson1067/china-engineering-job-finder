import csv
import json
import tempfile
import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from job_finder import read_config, select_jobs, write_reports


class SelectionTests(unittest.TestCase):
    @staticmethod
    def job(title, number, excerpt=""):
        return {"title": title, "companyName": "Example", "guid": f"https://example.org/job/{number}", "excerpt": excerpt}

    def test_filter_and_deduplicate(self):
        base = {"title": "Python Developer", "companyName": "Example", "guid": "https://example.org/job/1", "excerpt": "Remote role", "locationRestrictions": []}
        raw = [base, {**base, "guid": "https://example.org/job/1?ref=other"}, {**base, "title": "Python Intern", "guid": "https://example.org/job/2"}]
        config = {"include_any": ["python"], "exclude_any": ["intern"], "max_results": 50}
        result = select_jobs(raw, config)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "https://example.org/job/1")

    def test_layers_groups_order_and_limit(self):
        raw = [self.job("机械工程师", 1), self.job("声学振动研发工程师", 2, "实验测量与信号处理"), self.job("CFD/PIV 流体实验研发", 3, "科学计算")]
        config = {"include_any": ["工程师", "CFD"], "exclude_any": [], "max_results": 2}
        jobs = select_jobs(raw, config)
        self.assertEqual([j["match_level"] for j in jobs], ["直接匹配", "相邻可迁移"])
        self.assertIn("流体/CFD/PIV", jobs[0]["match_groups"])
        self.assertIn("声学", jobs[1]["match_groups"])
        self.assertIn("振动", jobs[1]["match_groups"])
        self.assertIn("实验测量", jobs[1]["match_groups"])
        self.assertIn("信号处理", jobs[1]["match_groups"])
        self.assertGreater(jobs[0]["match_score"], jobs[1]["match_score"])

    def test_summary_only_and_skill_hints(self):
        raw = [self.job("研发工程师", 1, "发动机 CFD PIV Python MATLAB 有限元"), self.job("科学计算工程师", 2, "数值模拟")]
        config = {"include_any": [], "exclude_any": [], "known_skills": ["PIV", "Python"], "max_results": 50}
        jobs = {j["id"]: j for j in select_jobs(raw, config)}
        engine = jobs["https://example.org/job/1"]
        self.assertEqual(engine["match_level"], "相邻可迁移")
        self.assertIn("CFD", engine["missing_skills"])
        self.assertIn("MATLAB", engine["missing_skills"])
        self.assertNotIn("PIV", engine["missing_skills"])
        self.assertEqual(jobs["https://example.org/job/2"]["match_level"], "相邻可迁移")

    def test_tier_precedes_score(self):
        raw = [self.job("声学振动信号处理科学计算工程师", 1), self.job("PIV 工程师", 2)]
        config = {"include_any": [], "exclude_any": [], "max_results": 2}
        jobs = select_jobs(raw, config)
        self.assertEqual(jobs[0]["title"], "PIV 工程师")
        self.assertGreater(jobs[1]["match_score"], jobs[0]["match_score"])

    def test_report_columns_and_old_config(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            cfg = root / "config.json"
            cfg.write_text(json.dumps({"queries": [], "rss_feeds": [{"url": "https://example.org/rss"}], "include_any": ["mechanical"], "exclude_any": []}), encoding="utf-8")
            config = read_config(cfg)
            jobs = select_jobs([self.job("Mechanical Engineer", 1)], config)
            self.assertEqual(jobs[0]["match_level"], "低相关")
            self.assertIn("未评估", jobs[0]["missing_skills"])
            write_reports(jobs, root / "output", False)
            report = (root / "output" / "latest.md").read_text(encoding="utf-8")
            self.assertIn("命中组：机械通用", report)
            self.assertIn("技能差距提示：未评估", report)
            with (root / "output" / "latest.csv").open(encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["match_level"], "低相关")
            self.assertEqual(row["match_score"], "5")
            self.assertEqual(row["match_groups"], "机械通用")


if __name__ == "__main__":
    unittest.main()


