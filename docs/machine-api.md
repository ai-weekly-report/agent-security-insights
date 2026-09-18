# 机器接口说明

GitHub Pages 发布时会同时生成结构化 JSON，供机器人、消息推送服务和其他自动化程序
读取概要并跳转到对应 HTML。机器人不需要解析网页 DOM，也不需要直接读取 Markdown。

站点根地址：

```text
https://ai-weekly-report.github.io/agent-security-insights/
```

## 接口

### 最新一期

```text
GET /agent-security-insights/latest.json
```

返回最新一期的元数据、结构化概要、HTML 地址和 PDF 地址。只需要展示最新内容的机器人
优先使用此接口。

### 全部期次

```text
GET /agent-security-insights/publication-manifest.json
```

返回所有已发布期次。每个 `issues[]` 项均包含 `summary`、网页地址、PDF 地址和独立概要
接口地址。

### 每期概要

```text
GET /agent-security-insights/issues/<slug>/summary.json
```

用于读取指定历史期次。`slug` 可以从发布清单的 `issues[].slug` 获得。

## 最新一期格式

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
  "summary_url": "https://ai-weekly-report.github.io/agent-security-insights/issues/2026-08-15_2026-09-14/summary.json",
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

## 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | integer | 接口结构版本；当前为 `1` |
| `slug` | string | 期次稳定标识 |
| `issue` | string | 面向读者的期刊名称 |
| `title` | string | 报告标题 |
| `period_start` | string | 观察周期开始日期，`YYYY-MM-DD` |
| `period_end` | string | 观察周期结束日期，`YYYY-MM-DD` |
| `published_at` | string | 发布日期，`YYYY-MM-DD` |
| `url` | string | 对应 HTML 绝对地址 |
| `pdf_url` | string | 对应 PDF 绝对地址 |
| `summary_url` | string | 本期概要 JSON 绝对地址 |
| `summary` | array | 概要条目列表 |
| `summary[].title` | string | 概要条目标题 |
| `summary[].text` | string | 去除 Markdown 标记后的纯文本内容 |
| `generated_at` | string | 本次构建时间，ISO 8601 |
| `source_commit` | string | 生成内容对应的 Git 提交 SHA |

新增可选字段不会提升 `schema_version`。删除字段、改变字段类型或改变字段语义时才会发布
新的 schema 版本。机器人应忽略不认识的字段，并在不支持的主版本出现时停止处理。

## JavaScript 示例

```javascript
const endpoint =
  "https://ai-weekly-report.github.io/agent-security-insights/latest.json";

const response = await fetch(endpoint, {
  headers: { Accept: "application/json" },
});

if (!response.ok) {
  throw new Error(`Request failed: ${response.status}`);
}

const latest = await response.json();

if (latest.schema_version !== 1) {
  throw new Error(`Unsupported schema: ${latest.schema_version}`);
}

const message = [
  `【${latest.issue}】`,
  "",
  ...latest.summary.flatMap(item => [
    `▌${item.title}`,
    item.text,
    "",
  ]),
  `阅读全文：${latest.url}`,
].join("\n");
```

## Python 示例

```python
import requests

endpoint = (
    "https://ai-weekly-report.github.io/"
    "agent-security-insights/latest.json"
)
response = requests.get(endpoint, timeout=15)
response.raise_for_status()
latest = response.json()

if latest["schema_version"] != 1:
    raise RuntimeError("unsupported schema version")

for item in latest["summary"]:
    print(f"【{item['title']}】")
    print(item["text"])

print("阅读全文：", latest["url"])
```

## 更新检测

机器人应记录最近处理过的 `slug` 或 `source_commit`。二者没有变化时不要重复推送。

GitHub Pages 当前允许跨域读取，并可能设置最长约 10 分钟的公共缓存。轮询程序建议：

- 每 5 至 10 分钟读取一次 `latest.json`；
- 保存响应的 `ETag`，后续发送 `If-None-Match`；
- 收到 `304 Not Modified` 时不解析、不重复发送；
- 设置请求超时，并在网络错误时退避重试。
