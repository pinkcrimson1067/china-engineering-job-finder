# 自己维护的找工作工具

[![Tests](https://github.com/pinkcrimson1067/china-engineering-job-finder/actions/workflows/tests.yml/badge.svg)](https://github.com/pinkcrimson1067/china-engineering-job-finder/actions/workflows/tests.yml)

这个小项目查询公开招聘 RSS，按关键词筛选、记录已见公告，并生成 Markdown 和 CSV。默认订阅 [SinoJobs RSS](https://www.sinojobs.com/cn/shiyong-sinojobs/rss-dingyue.html) 和[高层次人才网的 RSS 分类](https://www.gccrcw.com/rssmap.html)。SinoJobs 的匹配结果会进一步读取职位详情，仅保留地点字段明确含 China/中国的职位。另一来源可能是招聘公告而非单一岗位，申请前要打开原文核对地点、条件和截止时间。

## 运行

需要 Python 3.10+，无第三方依赖。在本目录执行：

```powershell
Copy-Item config.example.json config.json
python job_finder.py --config config.json
```

先编辑 `config.json`：`rss_feeds` 是要订阅的公开 RSS 地址；`include_any` 是标题/公司/摘要必须命中的词，留空则不过滤；`exclude_any` 是排除词。默认关键词对应机械、流体和实验研发，全国不设城市过滤。高层次人才网的 RSS 没有结构化地点字段，仍须阅读原公告。

如果要查海外远程职位，可另在 `queries` 填入英文词；这会调用 [Himalayas 公开 API](https://himalayas.app/docs/remote-jobs-api)。`country` 和 `worldwide_only` 只作用于该 API。

每次执行会覆写 `output/latest.md` 和 `output/latest.csv`，并更新 `output/seen.json`。报告会标记 `NEW` 和 `SEEN`。可用 `--only-new` 只在报告中保留新发现的职位。若请求失败，程序会报错，不会把已有结果冒充本次结果。

```powershell
python job_finder.py --config config.json --only-new
```

## 每天自动运行（Windows）

在本目录执行以下命令会创建当前用户的每日任务（09:00）。先手动跑通，再启用计划任务。

```powershell
.\schedule.ps1
```

要修改运行时间，执行 `.\schedule.ps1 -At '08:30'`。在“任务计划程序”中可找到 `PersonalJobFinder`。报告留在本机 `output` 目录；任务不会自动发邮件或投递。

## 维护与扩展

- 代码入口：`job_finder.py`。职位源解析集中在 `fetch_jobs()`，可添加其他符合使用条款的 API。
- 配置示例：`config.example.json`。把自己的 `config.json` 留在本地；公开仓库不要包含简历、联系方式或访问密钥。
- 验证：`python -m unittest discover -s tests -v`。
- 数据来源：配置中的 RSS 和可选的 Himalayas API。请通过每条记录的原始链接查看并申请。每日运行一次即可。

本工具是一个新项目原型。公开发布、持续维护、用户采用情况，都要以后真实发生并留下记录；创建仓库本身不构成 OpenAI 开源维护者计划的入选资格。

代码以 [MIT 许可证](LICENSE) 开放。欢迎提交问题和改进；请勿在公开问题中上传简历或其他个人信息。

