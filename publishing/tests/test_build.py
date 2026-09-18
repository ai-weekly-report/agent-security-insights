import json
import tempfile
import unittest
from pathlib import Path

from publishing import build


class BuildModelTests(unittest.TestCase):
    def test_theme_bootstrap_uses_saved_or_system_preference(self):
        script = build.theme_bootstrap_script()
        self.assertIn("agent-security-insights-theme", script)
        self.assertIn("prefers-color-scheme: dark", script)
        self.assertIn("document.documentElement.dataset.theme", script)

    def test_embedded_summary_drops_repository_navigation_link(self):
        summary = "# 本期概要\n\n### 重点\n\n内容。\n\n[阅读完整报告](report.md)\n"
        self.assertNotIn("report.md", build.normalize_summary(summary))

    def test_discovers_published_issues_and_excludes_drafts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            published = root / "2026" / "2026-08-15_2026-09-14"
            draft = root / "2026" / "2026-09-15_2026-09-21"
            for issue, status in ((published, "published"), (draft, "draft")):
                issue.mkdir(parents=True)
                (issue / "report.md").write_text(
                    "---\n"
                    "title: AI 观察\n"
                    "issue: 2026 年 9 月刊\n"
                    "period_start: 2026-08-15\n"
                    "period_end: 2026-09-14\n"
                    f"published_at: 2026-09-18\nstatus: {status}\nslug: {issue.name}\n"
                    "---\n\n# AI 观察\n\n正文。\n",
                    encoding="utf-8",
                )
                (issue / "summary.md").write_text("# 概要\n\n摘要。\n", encoding="utf-8")

            issues = build.discover_issues(root)

            self.assertEqual([item.slug for item in issues], [published.name])
            self.assertEqual(issues[0].title, "AI 观察")
            self.assertEqual(issues[0].summary_path, published / "summary.md")

    def test_latest_issue_uses_publication_date(self):
        issues = [
            build.Issue(
                title="旧期",
                issue_name="旧期",
                period_start="2026-08-01",
                period_end="2026-08-07",
                published_at="2026-08-08",
                slug="old",
                status="published",
                description="",
                directory=Path("old"),
                report_path=Path("old/report.md"),
                summary_path=Path("old/summary.md"),
            ),
            build.Issue(
                title="新期",
                issue_name="新期",
                period_start="2026-07-01",
                period_end="2026-07-31",
                published_at="2026-09-18",
                slug="new",
                status="published",
                description="",
                directory=Path("new"),
                report_path=Path("new/report.md"),
                summary_path=Path("new/summary.md"),
            ),
        ]

        self.assertEqual(build.latest_issue(issues).slug, "new")

    def test_manifest_contains_stable_issue_urls(self):
        issue = build.Issue(
            title="T",
            issue_name="2026 年 9 月刊",
            period_start="2026-08-15",
            period_end="2026-09-14",
            published_at="2026-09-18",
            slug="2026-08-15_2026-09-14",
            status="published",
            description="",
            directory=Path("reports/2026/2026-08-15_2026-09-14"),
            report_path=Path("report.md"),
            summary_path=Path("summary.md"),
        )

        manifest = build.manifest_payload([issue], "https://example.test/agent-security-insights/")

        self.assertEqual(manifest["latest_issue"], issue.slug)
        self.assertEqual(
            manifest["issues"][0]["page_url"],
            "issues/2026-08-15_2026-09-14/",
        )
        self.assertTrue(manifest["issues"][0]["pdf_url"].endswith("/report.pdf"))
        json.dumps(manifest, ensure_ascii=False)

    def test_issue_assets_do_not_publish_dotfiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            issue = root / "issue"
            destination = root / "site"
            (issue / "assets").mkdir(parents=True)
            (issue / "assets" / ".gitkeep").write_text("", encoding="utf-8")
            (issue / "assets" / "figure.txt").write_text("figure", encoding="utf-8")
            destination.mkdir()
            model = build.Issue(
                title="T",
                issue_name="T",
                period_start="2026-08-15",
                period_end="2026-09-14",
                published_at="2026-09-18",
                slug="t",
                status="published",
                description="",
                directory=issue,
                report_path=issue / "report.md",
                summary_path=issue / "summary.md",
            )

            build.copy_issue_assets(model, destination)

            self.assertTrue((destination / "assets" / "figure.txt").is_file())
            self.assertFalse((destination / "assets" / ".gitkeep").exists())

    def test_pdffonts_parser_handles_font_types_with_spaces(self):
        output = """name type encoding emb sub uni object ID
---- ---- -------- --- --- --- ---------
ABC+Font CID Type 0C Identity-H yes yes yes 4 0
"""
        self.assertEqual(build.embedded_font_states(output), [True])


if __name__ == "__main__":
    unittest.main()
