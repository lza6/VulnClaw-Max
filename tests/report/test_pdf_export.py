"""PDF export: real rendering when reportlab is installed, clear error when not."""

from __future__ import annotations

import pytest


def _markdown() -> str:
    return "\n".join(
        [
            "# VulnClaw Report",
            "",
            "## 1. Overview",
            "",
            "| Item | Details |",
            "|------|------|",
            "| Target | https://example.com |",
            "",
            "## 2. Findings",
            "",
            "### 2.1 SQL Injection — [High]",
            "",
            "- Evidence: `id=1' OR 1=1--`",
            "- Remediation: use parameterized queries",
            "",
            "```http",
            "GET /item?id=1 HTTP/1.1",
            "Host: example.com",
            "```",
        ]
    )


def test_export_pdf_without_the_optional_extra_raises_an_actionable_error(monkeypatch, tmp_path):
    import vulnclaw.report.pdf_exporter as exporter

    monkeypatch.setattr(exporter, "_HAVE_REPORTLAB", False)

    with pytest.raises(RuntimeError, match="vulnclaw\\[pdf\\]"):
        exporter.export_pdf(_markdown(), tmp_path / "report.pdf")


def test_export_pdf_writes_a_real_pdf(tmp_path):
    exporter = pytest.importorskip("vulnclaw.report.pdf_exporter")
    if not getattr(exporter, "_HAVE_REPORTLAB", False):
        pytest.skip("reportlab is not installed")

    out = tmp_path / "report.pdf"
    exporter.export_pdf(_markdown(), out, title="VulnClaw Report")

    assert out.is_file()
    data = out.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 1000
