# 机器接口说明

GitHub Pages 发布时会生成一个期次索引，以及每一期独立的结构化概要 JSON。机器人先从
索引确定最新一期，再读取该期概要并使用其中的 HTML 地址跳转到报告页面。

站点根地址：

```text
https://ai-weekly-report.github.io/agent-security-insights/
```

## 发布清单

```text
GET /agent-security-insights/publication-manifest.json
```

发布清单只做索引，不重复保存概要正文。`latest_issue` 是最新一期的 `slug`；机器人在
`issues[]` 中找到同一 slug，即可取得对应的 `summary_absolute_url`。

```json
{
  "schema_version": 1,
  "site_url": "https://ai-weekly-report.github.io/agent-security-insights/",
  "latest_issue": "2026-08-15_2026-09-14",
  "issues": [
    {
      "slug": "2026-08-15_2026-09-14",
      "issue": "2026 年 9 月刊",
      "title": "AI 智能体安全与隐私行业观察",
      "period_start": "2026-08-15",
      "period_end": "2026-09-14",
      "published_at": "2026-09-18",
      "page_url": "issues/2026-08-15_2026-09-14/",
      "pdf_url": "issues/2026-08-15_2026-09-14/report.pdf",
      "summary_url": "issues/2026-08-15_2026-09-14/summary.json",
      "page_absolute_url": "https://ai-weekly-report.github.io/agent-security-insights/issues/2026-08-15_2026-09-14/",
      "pdf_absolute_url": "https://ai-weekly-report.github.io/agent-security-insights/issues/2026-08-15_2026-09-14/report.pdf",
      "summary_absolute_url": "https://ai-weekly-report.github.io/agent-security-insights/issues/2026-08-15_2026-09-14/summary.json"
    }
  ],
  "generated_at": "2026-09-18T00:00:00+00:00",
  "source_commit": "..."
}
```

`issues[]` 按 `published_at` 从新到旧排列，但机器人应使用 `latest_issue` 匹配 slug，
不要依赖最新一期永远位于数组第一个元素。

## 每期概要

```text
GET /agent-security-insights/issues/<slug>/summary.json
```

每期概要是该期 summary 的正式机器数据源。

```json
{
  "schema_version": 1,
  "slug": "2026-08-15_2026-09-14",
  "issue": "2026 年 9 月刊",
  "title": "AI 智能体安全与隐私行业观察",
  "period_start": "2026-08-15",
  "period_end": "2026-09-14",
  "published_at": "2026-09-18",
  "url": "https://ai-weekly-report.github.io/agent-security-insights/issues/2026-08-15_2026-09-14/",
  "pdf_url": "https://ai-weekly-report.github.io/agent-security-insights/issues/2026-08-15_2026-09-14/report.pdf",
  "summary": [
    {
      "title": "手机操作权限",
      "text": "豆包公布 SAEP 协议，允许应用声明拒绝智能体操作。"
    }
  ],
  "generated_at": "2026-09-18T00:00:00+00:00",
  "source_commit": "..."
}
```

## 机器人读取流程

```text
GET publication-manifest.json
        ↓
读取 latest_issue
        ↓
在 issues[] 中查找相同 slug
        ↓
GET issue.summary_absolute_url
        ↓
显示 summary[]，并把 url 作为“阅读全文”链接
```

## JavaScript 示例

```javascript
const root =
  "https://ai-weekly-report.github.io/agent-security-insights/";

const manifestResponse = await fetch(`${root}publication-manifest.json`, {
  headers: { Accept: "application/json" },
});
if (!manifestResponse.ok) {
  throw new Error(`Manifest request failed: ${manifestResponse.status}`);
}

const manifest = await manifestResponse.json();
if (manifest.schema_version !== 1) {
  throw new Error(`Unsupported schema: ${manifest.schema_version}`);
}

const issue = manifest.issues.find(
  item => item.slug === manifest.latest_issue
);
if (!issue) {
  throw new Error("Latest issue not found in manifest");
}

const summaryResponse = await fetch(issue.summary_absolute_url, {
  headers: { Accept: "application/json" },
});
if (!summaryResponse.ok) {
  throw new Error(`Summary request failed: ${summaryResponse.status}`);
}

const issueSummary = await summaryResponse.json();
const message = [
  `【${issueSummary.issue}】`,
  "",
  ...issueSummary.summary.flatMap(item => [
    `▌${item.title}`,
    item.text,
    "",
  ]),
  `阅读全文：${issueSummary.url}`,
].join("\n");
```

## Python 示例

```python
import requests

root = "https://ai-weekly-report.github.io/agent-security-insights/"

manifest_response = requests.get(
    f"{root}publication-manifest.json",
    timeout=15,
)
manifest_response.raise_for_status()
manifest = manifest_response.json()

issue = next(
    item
    for item in manifest["issues"]
    if item["slug"] == manifest["latest_issue"]
)

summary_response = requests.get(issue["summary_absolute_url"], timeout=15)
summary_response.raise_for_status()
issue_summary = summary_response.json()

for item in issue_summary["summary"]:
    print(f"【{item['title']}】")
    print(item["text"])

print("阅读全文：", issue_summary["url"])
```

## 字段兼容与更新检测

`schema_version` 当前为 `1`。新增可选字段不会提升版本；删除字段、改变字段类型或改变
字段语义时才发布新的 schema 版本。机器人应忽略不认识的字段。

机器人可记录发布清单的 `source_commit`，或记录最新概要的 `slug`。值没有变化时不要
重复推送。

GitHub Pages 允许跨域读取，并可能设置最长约 10 分钟的公共缓存。轮询程序建议：

- 每 5 至 10 分钟读取一次 `publication-manifest.json`；
- 保存响应的 `ETag`，后续发送 `If-None-Match`；
- 收到 `304 Not Modified` 时不解析、不重复发送；
- 设置请求超时，并在网络错误时退避重试。
