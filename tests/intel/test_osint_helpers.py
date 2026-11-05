"""Pure OSINT formatting/validation helpers."""

from __future__ import annotations

from vulnclaw.intel.osint import (
    DNSRecord,
    OSINTReport,
    SubdomainResult,
    WHOISResult,
    clean_domain,
    format_report,
    is_valid_subdomain,
    normalize_url,
)


def test_domain_normalization():
    assert clean_domain("https://WWW.Example.com/path:443") == "example.com"
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("http://x") == "http://x"
    assert is_valid_subdomain("a.example.com") is True
    assert is_valid_subdomain("bad_subdomain") is False
    assert is_valid_subdomain("") is False


def test_format_report():
    report = OSINTReport(
        domain="example.com",
        subdomains=[SubdomainResult(subdomain="a.example.com", ip="1.2.3.4", source="dns")],
        dns_records=[DNSRecord(record_type="A", value="1.2.3.4", ttl=300)],
        emails=["a@example.com"],
        whois=WHOISResult(domain="example.com", registrar="Reg", creation_date="2020", expiration_date="2030", name_servers=["ns1"]),
    )
    text = format_report(report)
    assert "# OSINT Report: example.com" in text
    assert "a.example.com" in text
    assert "WHOIS" in text
