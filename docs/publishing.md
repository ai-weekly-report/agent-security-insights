# 网页与 PDF 发布

本仓库以每一期的 `report.md` 和 `summary.md` 为内容源，生成总首页、每期网页、
每期 PDF、方法说明页面和机器可读的发布清单。所有产物写入 `site/`，不进入 Git。

## 期次结构

```text
reports/<年份>/<观察开始日期>_<观察结束日期>/
├── report.md
├── summary.md
└── assets/
```

`report.md` 顶部需要包含以下 Pandoc YAML 元数据：

```yaml
---
title: "AI 智能体安全与隐私行业观察"
issue: "2026 年 9 月刊"
period_start: "2026-08-15"
period_end: "2026-09-14"
published_at: "2026-09-18"
reading_time: "约 10—15 分钟"
slug: "2026-08-15_2026-09-14"
status: "published"
description: "本期报告说明。"
---
```

`status: draft` 的期次不会进入网站。`summary.md` 是共享概要源，会显示在网站首页、
期次网页顶部和 PDF 顶部；其面向 GitHub 阅读的 `[阅读完整报告](report.md)` 链接会在
生成网页和 PDF 时自动移除，避免产物中出现源码相对链接。

## 本地构建

需要：

- Python 3；
- Pandoc 3.10.1 或兼容版本；
- XeLaTeX；
- TeX Live 的 `ctex`、Fandol 字体、`titlesec`、`fancyhdr` 和 `enumitem`；
- Poppler 的 `pdfinfo` 和 `pdffonts`。

在仓库根目录运行：

```bash
publishing/build.sh
```

脚本在临时目录生成全部内容，验证 HTML、PDF、A4 页面尺寸和字体嵌入后，才替换
仓库根目录的 `site/`。构建完成后可启动任意静态文件服务器，例如：

```bash
python3 -m http.server 8000 --directory site
```

然后访问 `http://127.0.0.1:8000/`。

## 发布路径

```text
site/
├── index.html
├── latest.json
├── publication-manifest.json
├── assets/
│   ├── site.css
│   ├── site.js
│   └── icons.svg
├── methodology/index.html
└── issues/<slug>/
    ├── index.html
    ├── report.pdf
    └── summary.json
```

`latest.json` 保存最新一期结构化概要与 HTML/PDF 地址；`publication-manifest.json`
保存全部期次及概要；每期 `summary.json` 提供独立历史接口。这些文件属于 Pages 产物，
不进入 Git。完整格式见 [机器接口说明](machine-api.md)。

## 日间与夜间模式

首页、期次页和编写方法页共用同一主题系统：

- 首次访问时读取系统的 `prefers-color-scheme` 偏好；
- 页面在加载 CSS 前同步设置主题，避免先亮后暗的闪烁；
- 用户手动选择保存在 `localStorage` 的 `agent-security-insights-theme`；
- 保存过选择后，以用户选择为准；没有保存时继续跟随系统主题变化；
- 浅色模式显示月亮图标，表示可切换到夜间；暗色模式显示太阳图标，表示可切换到日间；
- PDF 和目录按钮使用图标加可见文字，主题按钮使用图标和可访问标签。

## GitHub Actions

`.github/workflows/pages.yml` 在 Pull Request 中构建和验证但不部署；`main` 分支相关
内容变化或手动触发时，构建相同的 `site/`，上传 Pages artifact 并部署。工作流不会
生成提交或修改 README。

构建和部署任务都会把网站、最新一期、PDF、归档、期次数量和源提交写入 GitHub Actions
Job Summary。首次发布前，需要在仓库 Pages 设置中把 Source 选择为 GitHub Actions。

## README 与生成产物

README 保留可以直接访问的 Markdown、概要、方法说明和专题仓库链接，不维护生成 PDF
链接。仓库中的 `reports/**/report.pdf`、`site/` 和 TeX 中间文件均由 `.gitignore`
排除。
