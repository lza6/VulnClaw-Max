"""Pure recon extraction/classification helpers."""

from __future__ import annotations

from vulnclaw.agent.recon_tools import (
    _classify_unauth,
    _dedup_cap,
    _host_of,
    _is_auth_wall,
    _parse_auth_header,
    extract_from_js,
)


def test_extract_from_js():
    js = """
    fetch('/api/User/list');
    const url = "https://api.example.com/v1/items";
    const secret = "AKIAIOSFODNN7EXAMPLE";
    localStorage.setItem("token", "abc");
    """
    result = extract_from_js(js, base_host="example.com")
    assert "https://api.example.com/v1/items" in result["urls"]
    assert any("/api/User/list" in path for path in result["paths"])
    assert "api.example.com" in result["domains"]
    assert result["secrets"]


def test_auth_header_and_wall():
    assert _parse_auth_header("") == {}
    assert _parse_auth_header("Cookie: a=b") == {"Cookie": "a=b"}
    assert _parse_auth_header("token123") == {"Authorization": "Bearer token123"}
    assert _parse_auth_header({"a": 1}) == {"a": "1"}
    assert _is_auth_wall("<input type='password'>") is True
    assert _is_auth_wall("<html>hello</html>") is False


def test_classify_unauth():
    assert _classify_unauth(401, "", "")[1] is False
    assert _classify_unauth(302, "", "")[1] is False
    assert _classify_unauth(404, "", "")[1] is False
    assert _classify_unauth(405, "", "")[1] is False
    assert _classify_unauth(200, "", "")[1] is False
    assert _classify_unauth(200, '{"a":1}', "application/json")[1] is True
    assert _classify_unauth(200, "<html>x</html>", "text/html")[1] is False
    assert _classify_unauth(200, "plain", "text/plain")[1] is True
    assert _classify_unauth(500, "", "")[0].startswith("?")


def test_host_and_dedup():
    assert _host_of("https://Example.com:8443/x") == "example.com"
    assert _host_of("not a url") == "not a url"
    assert _dedup_cap(["a", "a", "b"], 2) == ["a", "b"]
