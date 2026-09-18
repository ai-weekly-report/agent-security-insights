#!/usr/bin/env python3
"""Build the static issue site and per-issue PDFs."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


MARKDOWN_FORMAT = (
    "markdown+smart+pipe_tables+fenced_code_blocks+implicit_figures+raw_tex+"
    "link_attributes+header_attributes+auto_identifiers"
)
THEME_STORAGE_KEY = "agent-security-insights-theme"
FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
PDF_VARIABLES = (
    "documentclass=ctexart",
    "classoption=fontset=fandol",
    "papersize=a4",
    "colorlinks=true",
    "linkcolor=InsightTeal",
    "urlcolor=InsightBlue",
    "toccolor=InsightTeal",
)


@dataclass(frozen=True)
class Issue:
    title: str
    issue_name: str
    period_start: str
    period_end: str
    published_at: str
    slug: str
    status: str
    description: str
    directory: Path
    report_path: Path
    summary_path: Path
    reading_time: str = ""


def theme_bootstrap_script() -> str:
    return f"""<script data-theme-bootstrap>
    (() => {{
      const saved = localStorage.getItem(\"{THEME_STORAGE_KEY}\");
      const dark = window.matchMedia(\"(prefers-color-scheme: dark)\").matches;
      const theme = saved === \"dark\" || saved === \"light\" ? saved : (dark ? \"dark\" : \"light\");
      document.documentElement.dataset.theme = theme;
    }})();
  </script>"""


def _meta_text(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    value_type = value.get("t")
    content = value.get("c")
    if value_type == "MetaString" and isinstance(content, str):
        return content
    if value_type == "MetaBool":
        return "true" if content else "false"
    if value_type in {"MetaInlines", "MetaBlocks"} and isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("t")
            item_content = item.get("c")
            if item_type == "Str" and isinstance(item_content, str):
                pieces.append(item_content)
            elif item_type in {"Space", "SoftBreak", "LineBreak"}:
                pieces.append(" ")
            elif item_type == "Plain" and isinstance(item_content, list):
                pieces.append(_meta_text({"t": "MetaInlines", "c": item_content}))
        return "".join(pieces).strip()
    return ""


def parse_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    result = subprocess.run(
        ["pandoc", str(path), f"--from={MARKDOWN_FORMAT}", "--to=json"],
        check=True,
        capture_output=True,
        text=True,
    )
    document = json.loads(result.stdout)
    metadata = {key: _meta_text(value) for key, value in document.get("meta", {}).items()}
    return metadata, text[match.end() :]


def _required(metadata: dict[str, str], key: str, path: Path) -> str:
    value = metadata.get(key, "").strip()
    if not value:
        raise ValueError(f"Missing '{key}' in {path}")
    return value


def _validate_date(value: str, key: str, path: Path) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {key} '{value}' in {path}; expected YYYY-MM-DD") from exc


def _issue_from_report(report_path: Path) -> Issue:
    metadata, _ = parse_front_matter(report_path)
    required_keys = (
        "title",
        "issue",
        "period_start",
        "period_end",
        "published_at",
        "slug",
        "status",
    )
    values = {key: _required(metadata, key, report_path) for key in required_keys}
    for key in ("period_start", "period_end", "published_at"):
        _validate_date(values[key], key, report_path)
    if values["status"] not in {"published", "draft"}:
        raise ValueError(f"Invalid status '{values['status']}' in {report_path}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", values["slug"]):
        raise ValueError(f"Invalid slug '{values['slug']}' in {report_path}")

    summary_path = report_path.parent / "summary.md"
    if not summary_path.is_file():
        raise ValueError(f"Missing summary.md next to {report_path}")

    return Issue(
        title=values["title"],
        issue_name=values["issue"],
        period_start=values["period_start"],
        period_end=values["period_end"],
        published_at=values["published_at"],
        slug=values["slug"],
        status=values["status"],
        description=metadata.get("description", "").strip(),
        directory=report_path.parent,
        report_path=report_path,
        summary_path=summary_path,
        reading_time=metadata.get("reading_time", "").strip(),
    )


def discover_issues(reports_root: Path) -> list[Issue]:
    issues = [_issue_from_report(path) for path in sorted(reports_root.rglob("report.md"))]
    published = [issue for issue in issues if issue.status == "published"]
    slugs = [issue.slug for issue in published]
    if len(slugs) != len(set(slugs)):
        raise ValueError("Published issue slugs must be unique")
    return sorted(published, key=lambda issue: (issue.published_at, issue.slug), reverse=True)


def latest_issue(issues: list[Issue]) -> Issue:
    if not issues:
        raise ValueError("No published issues found")
    return max(issues, key=lambda issue: (issue.published_at, issue.slug))


def _without_front_matter(path: Path) -> str:
    return parse_front_matter(path)[1].strip() + "\n"


def _drop_first_h1(markdown: str) -> str:
    return re.sub(r"\A\s*#\s+[^\n]+\n+", "", markdown, count=1).strip() + "\n"


def normalize_summary(markdown: str) -> str:
    markdown = markdown.strip()
    markdown = re.sub(r"\A#\s+[^\n]+\n+", "", markdown, count=1)
    markdown = re.sub(
        r"\n*\[阅读完整报告\]\(report\.md\)\s*\Z",
        "",
        markdown,
    )
    if not re.match(r"\A##\s+本期概要\b", markdown):
        markdown = "## 本期概要\n\n" + markdown
    return markdown.strip() + "\n"


def _pandoc_document(markdown: str) -> dict[str, object]:
    result = subprocess.run(
        ["pandoc", f"--from={MARKDOWN_FORMAT}", "--to=json"],
        input=markdown,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _pandoc_text(node: object) -> str:
    pieces: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return

        node_type = value.get("t")
        content = value.get("c")
        if node_type == "Str" and isinstance(content, str):
            pieces.append(content)
        elif node_type in {"Space", "SoftBreak", "LineBreak"}:
            pieces.append(" ")
        elif node_type in {"Code", "Math"} and isinstance(content, list):
            if len(content) > 1 and isinstance(content[1], str):
                pieces.append(content[1])
        elif node_type in {"Link", "Image", "Span"} and isinstance(content, list):
            if len(content) > 1:
                visit(content[1])
        else:
            visit(content)

    visit(node)
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


def parse_summary_items(markdown: str) -> list[dict[str, str]]:
    document = _pandoc_document(normalize_summary(markdown))
    items: list[dict[str, str]] = []
    title = ""
    paragraphs: list[str] = []

    def flush() -> None:
        nonlocal title, paragraphs
        text = " ".join(paragraphs).strip()
        if title and text:
            items.append({"title": title, "text": text})
        title = ""
        paragraphs = []

    for block in document.get("blocks", []):
        if not isinstance(block, dict):
            continue
        block_type = block.get("t")
        content = block.get("c")
        if block_type == "Header" and isinstance(content, list) and content[0] == 3:
            flush()
            title = _pandoc_text(content[2])
        elif title and block_type in {"Para", "Plain", "BulletList", "OrderedList"}:
            text = _pandoc_text(content)
            if text:
                paragraphs.append(text)
    flush()
    return items


def _issue_summary_items(issue: Issue) -> list[dict[str, str]]:
    return parse_summary_items(_without_front_matter(issue.summary_path))


def _report_body(issue: Issue) -> str:
    return _drop_first_h1(_without_front_matter(issue.report_path))


def _summary_body(issue: Issue) -> str:
    return normalize_summary(_without_front_matter(issue.summary_path))


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _pandoc_variable_args(variables: tuple[str, ...]) -> list[str]:
    arguments: list[str] = []
    for variable in variables:
        arguments.extend(["--variable", variable])
    return arguments


def _pandoc_fragment(markdown: str, output: Path, *, resource_path: Path | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="agent-security-pandoc-") as temp_dir:
        source = Path(temp_dir) / "content.md"
        source.write_text(markdown, encoding="utf-8")
        command = [
            "pandoc",
            str(source),
            f"--from={MARKDOWN_FORMAT}",
            "--to=html5",
            "--output",
            str(output),
        ]
        if resource_path:
            command.extend(["--resource-path", str(resource_path)])
        _run(command)


def _headings_from_html(fragment: str) -> list[tuple[int, str, str]]:
    headings = []
    for match in re.finditer(r'<h([23]) id="([^"]+)">(.*?)</h\1>', fragment, re.DOTALL):
        text = re.sub(r"<[^>]+>", "", match.group(3))
        headings.append((int(match.group(1)), match.group(2), html.unescape(text)))
    return headings


def _toc_html(headings: list[tuple[int, str, str]]) -> str:
    if not headings:
        return ""
    items = []
    for level, anchor, text in headings:
        items.append(
            f'<li class="toc-level-{level}"><a href="#{html.escape(anchor)}">{html.escape(text)}</a></li>'
        )
    return (
        '<aside id="page-toc" class="issue-toc" aria-label="本页目录" data-page-toc>'
        '<div class="sidebar-heading">本页目录</div><ul>'
        + "".join(items)
        + "</ul></aside>"
    )


def _render_template(template: Path, values: dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", text)))
    if unresolved:
        raise ValueError(f"Unresolved template values in {template}: {', '.join(unresolved)}")
    return text


def copy_issue_assets(issue: Issue, destination: Path) -> None:
    assets = issue.directory / "assets"
    if assets.is_dir():
        output = destination / "assets"
        for source in assets.rglob("*"):
            relative = source.relative_to(assets)
            if any(part.startswith(".") for part in relative.parts):
                continue
            target = output / relative
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)


def _issue_urls(issue: Issue) -> dict[str, str]:
    prefix = f"issues/{issue.slug}/"
    return {
        "page_url": prefix,
        "pdf_url": prefix + "report.pdf",
        "summary_url": prefix + "summary.json",
    }


def manifest_payload(issues: list[Issue], site_url: str) -> dict[str, object]:
    latest = latest_issue(issues)
    site_url = site_url.rstrip("/") + "/"
    issue_payloads = []
    for issue in issues:
        urls = _issue_urls(issue)
        issue_payloads.append(
            {
                "issue": issue.issue_name,
                "title": issue.title,
                "period_start": issue.period_start,
                "period_end": issue.period_end,
                "published_at": issue.published_at,
                "slug": issue.slug,
                "page_url": urls["page_url"],
                "pdf_url": urls["pdf_url"],
                "summary_url": urls["summary_url"],
                "page_absolute_url": site_url + urls["page_url"],
                "pdf_absolute_url": site_url + urls["pdf_url"],
                "summary_absolute_url": site_url + urls["summary_url"],
                "summary": _issue_summary_items(issue),
            }
        )
    return {
        "schema_version": 1,
        "site_url": site_url,
        "latest_issue": latest.slug,
        "latest_url": site_url + "latest.json",
        "issues": issue_payloads,
    }


def _machine_issue_payload(issue: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "slug": issue["slug"],
        "issue": issue["issue"],
        "title": issue["title"],
        "period_start": issue["period_start"],
        "period_end": issue["period_end"],
        "published_at": issue["published_at"],
        "url": issue["page_absolute_url"],
        "pdf_url": issue["pdf_absolute_url"],
        "summary_url": issue["summary_absolute_url"],
        "summary": issue["summary"],
    }


def _write_machine_interfaces(site_root: Path, manifest: dict[str, object]) -> None:
    issues = manifest["issues"]
    if not isinstance(issues, list):
        raise ValueError("Manifest issues must be a list")

    latest_payload: dict[str, object] | None = None
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        payload = _machine_issue_payload(issue)
        payload["generated_at"] = manifest["generated_at"]
        payload["source_commit"] = manifest["source_commit"]
        output = site_root / str(issue["summary_url"])
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if issue["slug"] == manifest["latest_issue"]:
            latest_payload = payload

    if latest_payload is None:
        raise ValueError("Latest issue payload was not generated")
    (site_root / "latest.json").write_text(
        json.dumps(latest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_issue_html(issue: Issue, site_root: Path, templates: Path) -> None:
    output_dir = site_root / "issues" / issue.slug
    output_dir.mkdir(parents=True, exist_ok=True)
    copy_issue_assets(issue, output_dir)
    summary_file = output_dir / "summary.html"
    report_file = output_dir / "report.html"
    _pandoc_fragment(_summary_body(issue), summary_file, resource_path=issue.directory)
    _pandoc_fragment(_report_body(issue), report_file, resource_path=issue.directory)
    summary_html = summary_file.read_text(encoding="utf-8")
    report_html = report_file.read_text(encoding="utf-8")
    headings = _headings_from_html(report_html)
    page = _render_template(
        templates / "issue.html",
        {
            "TITLE": html.escape(issue.title),
            "ISSUE": html.escape(issue.issue_name),
            "PERIOD": html.escape(f"{issue.period_start}—{issue.period_end}"),
            "PUBLISHED_AT": html.escape(issue.published_at),
            "READING_TIME": html.escape(issue.reading_time),
            "DESCRIPTION": html.escape(issue.description),
            "SUMMARY": summary_html,
            "REPORT": report_html,
            "TOC": _toc_html(headings),
            "PDF_URL": "report.pdf",
            "THEME_BOOTSTRAP": theme_bootstrap_script(),
        },
    )
    (output_dir / "index.html").write_text(page, encoding="utf-8")
    summary_file.unlink()
    report_file.unlink()


def _write_pdf(issue: Issue, site_root: Path, templates: Path, work_root: Path) -> None:
    output_dir = site_root / "issues" / issue.slug
    output_dir.mkdir(parents=True, exist_ok=True)
    source = work_root / f"{issue.slug}.md"
    summary = _summary_body(issue)
    report = _report_body(issue)
    source.write_text(
        f"{summary}\n\n\\newpage\n\\tableofcontents\n\\newpage\n\n# 完整报告\n\n{report}",
        encoding="utf-8",
    )
    command = [
        "pandoc",
        str(source),
        f"--from={MARKDOWN_FORMAT}",
        "--to=latex",
        "--pdf-engine=xelatex",
        "--pdf-engine-opt=-halt-on-error",
        "--pdf-engine-opt=-file-line-error",
        *_pandoc_variable_args(PDF_VARIABLES),
        "--variable",
        "geometry=top=2.1cm,bottom=2.2cm,left=2.25cm,right=2.25cm",
        "--variable",
        "fontsize=11pt",
        "--include-in-header",
        str(templates / "header.tex"),
        "--metadata",
        f"title={issue.title}",
        "--metadata",
        f"subtitle={issue.issue_name}",
        "--metadata",
        f"date=观察周期：{issue.period_start}—{issue.period_end}",
        "--resource-path",
        str(issue.directory),
        "--output",
        str(output_dir / "report.pdf"),
    ]
    _run(command)


def _write_homepage(
    issues: list[Issue], site_root: Path, templates: Path, repository_url: str
) -> None:
    latest = latest_issue(issues)
    summary_file = site_root / "latest-summary.html"
    _pandoc_fragment(_summary_body(latest), summary_file, resource_path=latest.directory)
    summary_html = summary_file.read_text(encoding="utf-8")
    summary_file.unlink()
    archive = []
    for issue in issues:
        archive.append(
            "<li>"
            f'<a href="issues/{html.escape(issue.slug)}/">{html.escape(issue.issue_name)}</a>'
            f" <span>{html.escape(issue.period_start)}—{html.escape(issue.period_end)}</span>"
            f' <a href="issues/{html.escape(issue.slug)}/report.pdf">PDF</a>'
            "</li>"
        )
    page = _render_template(
        templates / "index.html",
        {
            "TITLE": html.escape(latest.title),
            "LATEST_ISSUE": html.escape(latest.issue_name),
            "LATEST_PERIOD": html.escape(f"{latest.period_start}—{latest.period_end}"),
            "SUMMARY": summary_html,
            "ARCHIVE": "".join(archive),
            "REPOSITORY_URL": html.escape(repository_url),
            "LATEST_SLUG": html.escape(latest.slug),
            "THEME_BOOTSTRAP": theme_bootstrap_script(),
        },
    )
    (site_root / "index.html").write_text(page, encoding="utf-8")


def _write_methodology(
    site_root: Path, templates: Path, source: Path, repository_url: str
) -> None:
    output_dir = site_root / "methodology"
    output_dir.mkdir(parents=True, exist_ok=True)
    fragment = output_dir / "methodology.html"
    _pandoc_fragment(source.read_text(encoding="utf-8"), fragment, resource_path=source.parent)
    page = _render_template(
        templates / "page.html",
        {
            "TITLE": "编写方法",
            "CONTENT": fragment.read_text(encoding="utf-8"),
            "CSS_PATH": "../assets/site.css",
            "HOME_PATH": "../",
            "REPOSITORY_URL": html.escape(repository_url),
            "THEME_BOOTSTRAP": theme_bootstrap_script(),
        },
    )
    (output_dir / "index.html").write_text(page, encoding="utf-8")
    fragment.unlink()


def verify_site(site_root: Path, issues: list[Issue]) -> None:
    required = [
        site_root / "index.html",
        site_root / "publication-manifest.json",
        site_root / "assets" / "site.css",
        site_root / "assets" / "site.js",
        site_root / "assets" / "icons.svg",
        site_root / "latest.json",
    ]
    for issue in issues:
        required.extend(
            [
                site_root / "issues" / issue.slug / "index.html",
                site_root / "issues" / issue.slug / "report.pdf",
                site_root / "issues" / issue.slug / "summary.json",
            ]
        )
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise ValueError("Missing generated outputs: " + ", ".join(missing))
    for path in (site_root / "index.html",) + tuple(
        site_root / "issues" / issue.slug / "index.html" for issue in issues
    ):
        content = path.read_text(encoding="utf-8")
        if "report.pdf" not in content and path.name == "index.html" and "issues/" in str(path):
            raise ValueError(f"Issue page has no PDF link: {path}")
    homepage = (site_root / "index.html").read_text(encoding="utf-8")
    for target in ("latest.json", "publication-manifest.json"):
        if target not in homepage:
            raise ValueError(f"Homepage has no machine interface link for {target}")


def verify_pdf(pdf_path: Path) -> None:
    info = subprocess.run(
        ["pdfinfo", str(pdf_path)], check=True, capture_output=True, text=True
    ).stdout
    page_match = re.search(r"^Pages:\s+(\d+)$", info, re.MULTILINE)
    if not page_match or int(page_match.group(1)) < 1:
        raise ValueError(f"PDF has no pages: {pdf_path}")
    size_match = re.search(r"^Page size:\s+([\d.]+) x ([\d.]+) pts \(A4\)$", info, re.MULTILINE)
    if not size_match:
        raise ValueError(f"PDF is not A4: {pdf_path}")

    fonts = subprocess.run(
        ["pdffonts", str(pdf_path)], check=True, capture_output=True, text=True
    ).stdout
    font_states = embedded_font_states(fonts)
    if not font_states:
        raise ValueError(f"PDF has no inspectable fonts: {pdf_path}")
    if not all(font_states):
        raise ValueError(f"PDF contains a non-embedded font: {pdf_path}")


def embedded_font_states(pdffonts_output: str) -> list[bool]:
    states: list[bool] = []
    for line in pdffonts_output.splitlines()[2:]:
        match = re.search(r"\s+(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", line)
        if match:
            states.append(match.group(1) == "yes")
    return states


def build(
    repo_root: Path,
    site_root: Path,
    build_root: Path,
    site_url: str,
    repository_url: str,
) -> dict[str, object]:
    reports_root = repo_root / "reports"
    templates = repo_root / "publishing" / "templates"
    staged = build_root / "site"
    work_root = build_root / "work"
    if build_root.exists():
        shutil.rmtree(build_root)
    staged.mkdir(parents=True)
    work_root.mkdir(parents=True)
    assets_dir = staged / "assets"
    assets_dir.mkdir()
    shutil.copy2(repo_root / "publishing" / "assets" / "site.css", assets_dir / "site.css")
    shutil.copy2(repo_root / "publishing" / "assets" / "site.js", assets_dir / "site.js")
    shutil.copy2(repo_root / "publishing" / "assets" / "icons.svg", assets_dir / "icons.svg")

    issues = discover_issues(reports_root)
    for index, issue in enumerate(issues):
        _write_issue_html(issue, staged, templates)
        _write_pdf(issue, staged, repo_root / "publishing" / "pdf", work_root)
        issue_dir = staged / "issues" / issue.slug
        html_path = issue_dir / "index.html"
        content = html_path.read_text(encoding="utf-8")
        previous_issue = issues[index + 1] if index + 1 < len(issues) else None
        next_issue = issues[index - 1] if index > 0 else None
        links = []
        if previous_issue:
            links.append(
                f'<a href="../{html.escape(previous_issue.slug)}/">上一期：{html.escape(previous_issue.issue_name)}</a>'
            )
        if next_issue:
            links.append(
                f'<a href="../{html.escape(next_issue.slug)}/">下一期：{html.escape(next_issue.issue_name)}</a>'
            )
        navigation = '<nav class="issue-navigation" aria-label="期次导航">' + " · ".join(links) + "</nav>"
        content = content.replace("<div class=\"issue-navigation-placeholder\"></div>", navigation)
        html_path.write_text(content, encoding="utf-8")
    _write_homepage(issues, staged, templates, repository_url)
    _write_methodology(
        staged, templates, repo_root / "docs" / "methodology.md", repository_url
    )
    manifest = manifest_payload(issues, site_url)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["source_commit"] = os.environ.get("GITHUB_SHA", "")
    _write_machine_interfaces(staged, manifest)
    (staged / "publication-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    verify_site(staged, issues)
    for issue in issues:
        verify_pdf(staged / "issues" / issue.slug / "report.pdf")
    if site_root.exists():
        shutil.rmtree(site_root)
    site_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staged), str(site_root))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--site-root", type=Path)
    parser.add_argument("--build-root", type=Path)
    parser.add_argument("--site-url", default=os.environ.get("SITE_BASE_URL"))
    parser.add_argument("--repository-url", default=os.environ.get("REPOSITORY_URL"))
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    config = json.loads((repo_root / "publishing" / "site.json").read_text(encoding="utf-8"))
    site_root = (args.site_root or repo_root / "site").resolve()
    build_root = (args.build_root or Path(tempfile.gettempdir()) / "agent-security-insights-build").resolve()
    manifest = build(
        repo_root,
        site_root,
        build_root,
        args.site_url or config["site_url"],
        args.repository_url or config["repository_url"],
    )
    latest = manifest["issues"][0]
    print(f"Published site: {manifest['site_url']}")
    print(f"Latest issue: {latest['page_absolute_url']}")
    print(f"Latest PDF: {latest['pdf_absolute_url']}")
    print(f"Latest JSON: {manifest['latest_url']}")
    print(f"Archive: {manifest['site_url']}#archive")


if __name__ == "__main__":
    main()
