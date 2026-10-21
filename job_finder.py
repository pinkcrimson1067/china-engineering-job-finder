"""A small, dependency-free personal job discovery tool."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

API_URL = "https://himalayas.app/jobs/api/search"
USER_AGENT = "personal-job-finder/0.1 (personal job discovery)"


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("配置文件顶层必须是 JSON 对象")
    for key in ("queries", "include_any", "exclude_any"):
        value = config.get(key, [])
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            raise ValueError(f"{key} 必须是字符串列表")
        config[key] = [x.strip() for x in value if x.strip()]
    feeds = config.get("rss_feeds", [])
    if not isinstance(feeds, list) or any(not isinstance(x, dict) or not isinstance(x.get("url"), str) or not x["url"].startswith("https://") for x in feeds):
        raise ValueError("rss_feeds 必须是含 HTTPS url 的对象列表")
    config["rss_feeds"] = feeds
    if not config["queries"] and not feeds:
        raise ValueError("queries 或 rss_feeds 至少配置一项")
    if not isinstance(config.get("country", ""), str):
        raise ValueError("country 必须是字符串")
    if not isinstance(config.get("worldwide_only", False), bool):
        raise ValueError("worldwide_only 必须是布尔值")
    for key, default, maximum in (("max_pages_per_query", 1, 5), ("max_results", 50, 500)):
        value = config.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError(f"{key} 必须是 1 到 {maximum} 的整数")
        config[key] = value
    return config


def fetch_jobs(config: dict) -> list[dict]:
    jobs = []
    for query in config["queries"]:
        for page in range(1, config["max_pages_per_query"] + 1):
            params = {"q": query, "sort": "recent", "page": page}
            if config.get("country"):
                params["country"] = config["country"]
            if config.get("worldwide_only"):
                params["worldwide"] = "true"
            url = API_URL + "?" + urllib.parse.urlencode(params)
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.load(response)
            batch = payload.get("jobs")
            if not isinstance(batch, list):
                raise ValueError("职位 API 响应缺少 jobs 列表")
            jobs.extend(batch)
            if not batch:
                break
    for feed in config["rss_feeds"]:
        request = urllib.request.Request(feed["url"], headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"})
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read()
        declared = re.search(br"<\?xml[^>]*encoding=[\"']([^\"']+)", raw[:200], re.I)
        encoding = declared.group(1).decode("ascii").lower() if declared else "utf-8"
        decoded = raw.decode("gb18030" if encoding in ("gb2312", "gbk", "gb18030") else encoding)
        decoded = re.sub(r"(<\?xml[^>]*encoding=)[\"'][^\"']+[\"']", r'\1"utf-8"', decoded, count=1)
        root = ET.fromstring(decoded)
        for item in root.findall(".//item"):
            link = item.findtext("link") or item.findtext("guid") or ""
            title = item.findtext("title") or urllib.parse.unquote(link.rstrip("/").rsplit("/", 1)[-1]).removesuffix(".html").replace("-", " ")
            pub_date = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date")
            try:
                published = (datetime.fromisoformat(pub_date) if "T" in pub_date else parsedate_to_datetime(pub_date)).date().isoformat() if pub_date else ""
            except (TypeError, ValueError):
                published = ""
            jobs.append({"title": title, "companyName": "", "guid": link, "excerpt": item.findtext("description") or "", "source": feed.get("name", "RSS"), "published": published})
    return jobs


def plain_text(value: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))).strip()


def normalize(job: dict) -> dict | None:
    if not isinstance(job, dict):
        return None
    title = plain_text(job.get("title"))
    company = plain_text(job.get("companyName"))
    link = job.get("guid") or job.get("applicationLink")
    if not title or not isinstance(link, str) or not link.startswith("https://"):
        return None
    return {
        "id": link.split("?", 1)[0],
        "title": title,
        "company": company,
        "location": ", ".join(job.get("locationRestrictions") or []) or "未注明/全球",
        "type": plain_text(job.get("employmentType")),
        "published": job.get("published") or (datetime.fromtimestamp(job["pubDate"], timezone.utc).date().isoformat() if isinstance(job.get("pubDate"), (int, float)) else ""),
        "summary": plain_text(job.get("excerpt"))[:280],
        "url": link,
        "source": job.get("source", "Himalayas"),
    }


def select_jobs(raw: list[dict], config: dict) -> list[dict]:
    selected = {}
    includes = [x.casefold() for x in config["include_any"]]
    excludes = [x.casefold() for x in config["exclude_any"]]
    for item in raw:
        job = normalize(item)
        if not job:
            continue
        haystack = " ".join(job[k] for k in ("title", "company", "summary")).casefold()
        if includes and not any(term in haystack for term in includes):
            continue
        if any(term in haystack for term in excludes):
            continue
        selected.setdefault(job["id"], job)
    results = []
    for job in selected.values():
        if job["source"] == "SinoJobs·职位订阅":
            request = urllib.request.Request(job["url"], headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=25) as response:
                detail = response.read().decode("utf-8", errors="replace")
            heading = re.search(r"<h1[^>]*>(.*?)</h1>", detail, re.I | re.S)
            if heading:
                job["title"] = plain_text(heading.group(1))
            match = re.search(r"<h3>City:</h3>\s*<p>(.*?)</p>", detail, re.I | re.S)
            city = plain_text(match.group(1)) if match else ""
            if "China" not in city and "中国" not in city:
                continue
            job["location"] = city
        results.append(job)
        if len(results) >= config["max_results"]:
            break
    return results


def write_reports(jobs: list[dict], output: Path, only_new: bool) -> tuple[int, int]:
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "seen.json"
    seen = set(json.loads(state_path.read_text(encoding="utf-8"))) if state_path.exists() else set()
    new_count = sum(job["id"] not in seen for job in jobs)
    for job in jobs:
        job["status"] = "NEW" if job["id"] not in seen else "SEEN"
    shown = [job for job in jobs if job["status"] == "NEW"] if only_new else jobs
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["# 职位搜索结果", "", f"运行时间：{now}；匹配：{len(jobs)}；本次新发现：{new_count}。", "", "来源见各条记录。点击原始链接确认岗位、工作地点和截止时间。", ""]
    for job in shown:
        title = job["title"].replace("[", "\\[").replace("]", "\\]")
        lines.extend([f"## [{title}](<{job['url']}>)" + (f" — {job['company']}" if job['company'] else ""), "", f"- 状态：{job['status']}；来源：{job['source']}；发布日期：{job['published'] or '未知'}", f"- 地点/限制：{job['location']}；类型：{job['type'] or '未注明'}", f"- 摘要：{job['summary'] or 'RSS 未提供，请打开原文'}", ""])
    if not shown:
        lines.append("本次没有符合条件的新职位。" if only_new else "本次没有符合条件的职位。")
    (output / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (output / "latest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        columns = ["status", "title", "company", "location", "type", "published", "summary", "url", "source"]
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(shown)
    state_path.write_text(json.dumps(sorted(seen | {j["id"] for j in jobs}), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(shown), new_count


def main() -> int:
    parser = argparse.ArgumentParser(description="搜索职位并生成本地报告")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--only-new", action="store_true")
    args = parser.parse_args()
    try:
        config = read_config(args.config)
        jobs = select_jobs(fetch_jobs(config), config)
        shown, new_count = write_reports(jobs, args.config.parent / "output", args.only_new)
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print(f"运行失败：{exc}", file=sys.stderr)
        return 1
    print(f"完成：报告 {shown} 条，本次新发现 {new_count} 条；见 {args.config.parent / 'output' / 'latest.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

