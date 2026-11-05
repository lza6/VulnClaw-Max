"""Network scan pure helpers."""

from __future__ import annotations

from vulnclaw.agent.network_scan import (
    _dedupe_services,
    _ports_from_prior_recon,
    _safe_int,
    _severity_rank,
    classify_weak_link,
    deescalate_nmap_argv,
    nmap_failure_needs_deescalation,
    parse_nmap_xml_structured,
    summarize_network_scan,
    target_is_private_literal,
    without_privileged_nmap_args,
)


def test_small_helpers():
    assert _safe_int("3") == 3
    assert _safe_int("bad") == 0
    assert _severity_rank("Critical") < _severity_rank("Low")
    assert target_is_private_literal("127.0.0.1") is True
    assert target_is_private_literal("8.8.8.8") is False
    assert isinstance(_ports_from_prior_recon({"ports": [80, 443]}), str)
    assert _dedupe_services([], [{"port": 80}]) == [{"port": 80}]


def test_nmap_helpers():
    assert "-sT" in without_privileged_nmap_args(("-sS", "-Pn", "--version-light"))
    assert deescalate_nmap_argv(["nmap", "-sS", "x"])[1] == "-sT"
    assert nmap_failure_needs_deescalation("Operation not permitted") is True
    assert nmap_failure_needs_deescalation("host down") is False


def test_parse_and_summarize():
    xml = """<nmaprun><host><status state="up"/><address addr="127.0.0.1"/><ports><port portid="80" protocol="tcp"><state state="open"/><service name="http" product="nginx" version="1"/></port></ports></host></nmaprun>"""
    structured = parse_nmap_xml_structured(xml, "example.com")
    assert structured["hosts"]
    weak = classify_weak_link({"port": 80, "service": "http", "product": "nginx", "version": "1"})
    assert weak is None or isinstance(weak, dict)
    text = summarize_network_scan(structured)
    assert isinstance(text, str)
