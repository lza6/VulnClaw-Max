"""Pure helpers in agent.builtin_tools."""

from __future__ import annotations

from types import SimpleNamespace

from vulnclaw.agent.builtin_tools import (
    _ast_check_sandbox_bypass,
    _bounded_float,
    _coerce_nonnegative_int,
    _cookies_need_exact_header,
    _extract_endpoints,
    _extract_html_surfaces,
    _jsonish_one_line,
    _masked_probe_headers,
    _object_or_none,
    _prepare_http_probe_request,
    _resolve_probe_url,
    _shell_argv,
    _source_signal_lines,
    _string_dict,
    build_openai_tools,
    enforce_host_path_constraints,
    enforce_port_constraints,
    infer_ports_from_nmap_args,
    is_reserved_ip,
    parse_nmap_xml,
    sanitized_exec_env,
    validate_scan_target,
)


def _agent(**constraints):
    from vulnclaw.agent.context import TaskConstraints

    return SimpleNamespace(
        session_state=SimpleNamespace(task_constraints=TaskConstraints(**constraints))
    )


def test_ast_sandbox_bypass_detection():
    assert _ast_check_sandbox_bypass("print(1)") is None
    assert "exec/eval" in _ast_check_sandbox_bypass("eval('1')")
    assert "importlib" in _ast_check_sandbox_bypass("import importlib; importlib.import_module('os')")
    assert "__builtins__" in _ast_check_sandbox_bypass("getattr(__builtins__, 'open')")
    assert _ast_check_sandbox_bypass("def broken(") is None


def test_shell_argv_and_env_sanitization(monkeypatch):
    argv = _shell_argv("echo hi", "cmd")
    assert argv[-1] == "echo hi"
    assert _shell_argv("x", "pwsh.exe")[-1] == "x"
    env = sanitized_exec_env({"PATH": "/bin", "BASH_ENV": "x", "DYLD_X": "y", "OK": "1"})
    assert env["PATH"] == "/bin" and env["OK"] == "1"
    assert "BASH_ENV" not in env and "DYLD_X" not in env
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_source_extract_helpers():
    source = "line1\nhighlight_file($x);\nline3"
    assert any("highlight_file" in line for line in _source_signal_lines(source))
    html = '<form action="/x"><input name="a"></form>'
    assert any(item.startswith("form:") for item in _extract_html_surfaces(html))
    assert "/x" in _extract_endpoints(html)


def test_ip_and_target_validation(monkeypatch):
    assert is_reserved_ip("127.0.0.1")[0] is True
    assert is_reserved_ip("10.1.2.3")[0] is True
    assert is_reserved_ip("8.8.8.8")[0] is False
    assert is_reserved_ip("not-an-ip") == (False, "")

    monkeypatch.setattr("socket.getaddrinfo", lambda *_a, **_k: [(2, 1, 6, "", ("127.0.0.1", 0))])
    assert "保留/内网地址" in validate_scan_target("localhost")
    monkeypatch.setattr("socket.getaddrinfo", lambda *_a, **_k: [(2, 1, 6, "", ("8.8.8.8", 0))])
    assert validate_scan_target("example.com") == ""


def test_parse_nmap_xml():
    raw = "plain nmap output\nline2"
    assert "nmap 原始输出" in parse_nmap_xml(raw, "example.com")
    xml = """<nmaprun><host><status state="up"/><address addr="127.0.0.1"/><hostname type="user" name="localhost"/><ports><port portid="80" protocol="tcp"><state state="open"/><service name="http" product="nginx" version="1"/></port></ports></host></nmaprun>"""
    text = parse_nmap_xml(xml, "example.com")
    assert "127.0.0.1" in text and "80/" in text
    assert "nmap 原始输出" in parse_nmap_xml("<bad", "x")


def test_constraints_and_port_inference():
    agent = _agent(allowed_ports=[443], blocked_ports=[22], allowed_hosts=["a.com"], blocked_hosts=["b.com"])
    assert enforce_port_constraints(agent, [80]) is not None
    assert enforce_port_constraints(agent, [22]) is not None
    assert enforce_port_constraints(agent, [443]) is None
    assert enforce_host_path_constraints(agent, host="c.com") is not None
    assert enforce_host_path_constraints(agent, host="b.com") is not None
    assert enforce_host_path_constraints(agent, host="a.com") is None
    assert enforce_port_constraints(_agent(), [80]) is None

    assert infer_ports_from_nmap_args({"ports": "80,443,8000-8002"}) == [80, 443, 8000, 8001, 8002]
    assert infer_ports_from_nmap_args({"ports": "bad,0,70000"}) == []
    assert infer_ports_from_nmap_args({"scan_type": "top_ports"}) == []


def test_probe_helpers():
    assert _bounded_float("x", 1, 3) == 1
    assert _bounded_float(9, 1, 3) == 3
    assert _coerce_nonnegative_int(-2) == 0
    assert _coerce_nonnegative_int("bad", default=4) == 4
    assert _resolve_probe_url("https://a.com/v1", "/x") == "https://a.com/x"
    assert _resolve_probe_url("https://a.com/v1", "https://b.com/x") == "https://b.com/x"
    assert _object_or_none({"a": 1}) == {"a": 1}
    assert _object_or_none(1) is None
    assert _string_dict({"a": 1}) == {"a": "1"}
    assert _jsonish_one_line({"a": 1})
    assert _masked_probe_headers({"Authorization": "x"})["Authorization"] == "[masked]"
    assert _cookies_need_exact_header({"a": "x;y"}) is True
    assert _cookies_need_exact_header({"a": "x"}) is False


def test_build_openai_tools_and_prepare_request():
    tools = build_openai_tools(None, include_subagent_tool=False)
    assert isinstance(tools, list) and tools
    assert build_openai_tools(None)
    agent = _agent()
    valid = _prepare_http_probe_request(agent, "https://example.com", 0, {"method": "GET"})
    assert valid["method"] == "GET"
    assert "error" in _prepare_http_probe_request(agent, "", 0, {"method": "TRACE"})
    assert "error" in _prepare_http_probe_request(agent, "", 0, {"method": "GET"})


def test_http_probe_helpers():
    import httpx

    from vulnclaw.agent.builtin_tools import (
        _body_with_optional_limit,
        _execute_one_http_probe,
        _extract_html_title,
        _format_http_probe_batch,
        _http_body_signals,
        _probe_request_surface_lines,
    )

    assert _extract_html_title("<title> Hello </title>") == "Hello"
    assert _extract_html_title("<p>x</p>") == ""
    assert "token" in _http_body_signals("a token here", 100)
    assert _body_with_optional_limit("abcdef", 3) == ("abc", True)
    assert _body_with_optional_limit("abc", 0) == ("abc", False)
    surface = _probe_request_surface_lines(
        {"method": "POST", "url": "https://x", "headers": {"A": "b"}, "cookies": {"c": "d"}, "json": {"a": 1}}
    )
    assert any("headers=" in line for line in surface)

    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="<title>T</title> token"))
    )
    item = _execute_one_http_probe(
        client, {"index": 0, "label": "l", "method": "GET", "url": "https://x"}, 100
    )
    assert item["status"] == 200 and item["title"] == "T"
    text = _format_http_probe_batch([item, {"index": 1, "error": "boom", "url": "https://y"}])
    assert "http_probe_batch results" in text and "ERROR" in text
