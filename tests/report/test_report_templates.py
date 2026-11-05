"""Report template variants: pentest (default), executive, ctf."""

from __future__ import annotations

import pytest

from vulnclaw.agent.context import SessionState, VulnerabilityFinding


def _session() -> SessionState:
    state = SessionState(target="https://shop.example.com")
    finding = VulnerabilityFinding(
        title="SQL Injection",
        severity="Critical",
        vuln_type="SQLi",
        description="Login form is injectable.",
        evidence="admin' OR 1=1-- bypassed authentication",
        remediation="Use parameterized queries.",
    )
    finding.verified = True
    finding.verification_status = "verified"
    state.add_finding(finding)
    state.add_step("probe /login", action="curl", target="https://shop.example.com/login")
    return state


@pytest.fixture(autouse=True)
def _chinese_reports(monkeypatch):
    import vulnclaw.report.generator as generator
    import vulnclaw.report.variants as variants

    monkeypatch.setattr(generator, "current_lang", lambda: "zh")
    monkeypatch.setattr(variants, "current_lang", lambda: "zh")


def test_pentest_is_the_default_template(tmp_path):
    from vulnclaw.report.generator import generate_report

    content = generate_report(_session(), str(tmp_path / "r.md")).read_text(encoding="utf-8")

    assert "## 3. 详细发现" in content
    assert "已验证漏洞定位与复现信息" in content


def test_executive_template_drops_reproduction_detail(tmp_path):
    from vulnclaw.report.generator import generate_report

    content = (
        generate_report(_session(), str(tmp_path / "r.md"), template="executive")
        .read_text(encoding="utf-8")
    )

    assert "渗透测试执行摘要" in content
    assert "风险总览" in content
    assert "关键风险" in content
    assert "SQL Injection" in content
    # Management output must not leak exploitation detail.
    assert "已验证漏洞定位与复现信息" not in content
    assert "admin' OR 1=1" not in content
    assert "目标历史治理上下文" not in content


def test_ctf_template_leads_with_the_exploit_chain(tmp_path):
    from vulnclaw.report.generator import generate_report

    content = (
        generate_report(_session(), str(tmp_path / "r.md"), template="ctf")
        .read_text(encoding="utf-8")
    )

    assert "CTF 挑战报告" in content
    assert "利用链" in content
    assert "probe /login" in content
    assert "复现步骤" in content


def test_english_templates_are_localized(tmp_path, monkeypatch):
    import vulnclaw.report.generator as generator
    import vulnclaw.report.variants as variants

    monkeypatch.setattr(generator, "current_lang", lambda: "en")
    monkeypatch.setattr(variants, "current_lang", lambda: "en")

    executive = generator.generate_report(
        _session(), str(tmp_path / "e.md"), template="executive"
    ).read_text(encoding="utf-8")
    ctf = generator.generate_report(_session(), str(tmp_path / "c.md"), template="ctf").read_text(
        encoding="utf-8"
    )

    assert "Executive Summary" in executive
    assert "CTF Challenge Report" in ctf


def test_unknown_template_is_rejected(tmp_path):
    from vulnclaw.report.generator import generate_report

    with pytest.raises(ValueError, match="unknown report template"):
        generate_report(_session(), str(tmp_path / "r.md"), template="freestyle")


def test_target_state_report_honors_template(tmp_path):
    from vulnclaw.report.generator import generate_report_from_target_state

    raw = _session().model_dump(mode="json")
    path = generate_report_from_target_state(
        raw, output_path=str(tmp_path / "t.md"), template="executive"
    )

    content = path.read_text(encoding="utf-8")
    assert "渗透测试执行摘要" in content
    # Target-state reports carry a governance appendix; the executive variant
    # must still drop it.
    assert "目标历史治理上下文" not in content
