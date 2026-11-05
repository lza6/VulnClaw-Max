"""MCP lifecycle internals: fetch constraints, session caching, result rendering.

The SDK transports are replaced with in-memory doubles: these tests pin VulnClaw's
own session bookkeeping (cache keyed by loop, teardown order, error wrapping),
not the MCP SDK.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import vulnclaw.mcp.lifecycle as lifecycle
from vulnclaw.config.domain_models import TaskConstraints
from vulnclaw.config.schema import MCPServerConfig, VulnClawConfig
from vulnclaw.mcp.lifecycle import MCPLifecycleManager


def _manager(**servers) -> MCPLifecycleManager:
    config = VulnClawConfig()
    for name, transport in servers.items():
        config.mcp.servers[name] = MCPServerConfig(name=name, transport=transport)
    return MCPLifecycleManager(config)


# ── Fetch constraint enforcement ─────────────────────────────────────


def _constrained(**constraints) -> MCPLifecycleManager:
    manager = _manager()
    manager.set_task_constraints(TaskConstraints(**constraints))
    return manager


def test_fetch_passes_when_no_constraints_are_set():
    manager = _manager()
    assert manager._check_fetch_constraints({"url": "https://example.com/x"}) is None


def test_fetch_passes_without_a_url():
    manager = _constrained(allowed_hosts=["only.example"])
    assert manager._check_fetch_constraints({}) is None


def test_fetch_rejects_a_host_outside_the_allowlist():
    manager = _constrained(allowed_hosts=["only.example"])
    result = manager._check_fetch_constraints({"url": "https://evil.example/x"})

    assert result is not None
    assert result["ok"] is False
    assert result["error_type"] == "constraint_violation"
    assert "outside allowed scope" in result["message"]


def test_fetch_rejects_a_blocked_host():
    manager = _constrained(blocked_hosts=["blocked.example"])
    result = manager._check_fetch_constraints({"url": "https://blocked.example/x"})

    assert result is not None
    assert "is blocked by task constraints" in result["message"]


def test_fetch_rejects_a_path_outside_the_allowlist():
    manager = _constrained(allowed_paths=["/api"])
    result = manager._check_fetch_constraints({"url": "https://example.com/admin"})

    assert result is not None
    assert "Path /admin is outside allowed scope" in result["message"]


def test_fetch_rejects_a_blocked_path():
    manager = _constrained(blocked_paths=["/internal"])
    result = manager._check_fetch_constraints({"url": "https://example.com/internal"})

    assert result is not None
    assert "is blocked by task constraints for url" in result["message"]


def test_fetch_rejects_a_port_outside_the_allowlist():
    manager = _constrained(allowed_ports=[443])
    result = manager._check_fetch_constraints({"url": "http://example.com:8080/x"})

    assert result is not None
    assert "Port 8080 is outside allowed scope" in result["message"]


def test_fetch_rejects_a_blocked_port():
    manager = _constrained(blocked_ports=[22])
    result = manager._check_fetch_constraints({"url": "http://example.com:22/x"})

    assert result is not None
    assert "Port 22 is blocked by task constraints" in result["message"]


def test_fetch_allows_a_url_inside_the_scope():
    manager = _constrained(
        allowed_hosts=["example.com"], allowed_paths=["/api"], allowed_ports=[443]
    )
    assert manager._check_fetch_constraints({"url": "https://example.com/api"}) is None
    # Paths are matched exactly, so a deeper path stays outside the scope.
    assert manager._check_fetch_constraints({"url": "https://example.com/api/items"}) is not None


# ── Loop exception handler ───────────────────────────────────────────


def test_loop_handler_is_not_installed_without_a_running_loop():
    manager = _manager()
    manager._install_loop_exception_handler()
    assert manager._loop_exception_handler_loop is None


@pytest.mark.asyncio
async def test_loop_handler_swallows_benign_shutdown_noise_and_forwards_the_rest():
    loop = asyncio.get_running_loop()
    forwarded: list[dict] = []
    loop.set_exception_handler(lambda _loop, context: forwarded.append(context))

    manager = _manager()
    manager._install_loop_exception_handler()
    handler = loop.get_exception_handler()
    assert handler is not None
    # Re-installing on the same loop is the idempotent fast path.
    manager._install_loop_exception_handler()

    # Benign: cancelled work, anyio cancel-scope noise, async-generator close noise.
    handler(loop, {"exception": asyncio.CancelledError()})
    handler(loop, {"message": "Attempted to exit cancel scope in a different task"})
    handler(loop, {"message": "an error occurred during closing of asynchronous generator"})
    assert forwarded == []

    # A destroyed-but-pending task is a real leak and must reach the previous handler.
    handler(loop, {"message": "Task was destroyed but it is pending"})
    assert [item["message"] for item in forwarded] == ["Task was destroyed but it is pending"]

    handler(loop, {"message": "boom", "exception": ValueError("boom")})
    assert forwarded[-1]["message"] == "boom"
    loop.set_exception_handler(None)


@pytest.mark.asyncio
async def test_loop_handler_defaults_to_the_loop_default_handler():
    manager = _manager()
    manager._install_loop_exception_handler()
    loop = asyncio.get_running_loop()
    handler = loop.get_exception_handler()

    seen: list[dict] = []
    loop.set_exception_handler(None)
    original_default = loop.default_exception_handler
    loop.default_exception_handler = lambda context: seen.append(context)  # type: ignore[method-assign]
    try:
        handler(loop, {"message": "unhandled"})
    finally:
        loop.default_exception_handler = original_default  # type: ignore[method-assign]

    assert seen and seen[0]["message"] == "unhandled"


# ── Call result rendering ────────────────────────────────────────────


def test_render_call_result_handles_none_and_structured_only():
    manager = _manager()
    assert manager._render_mcp_call_result(None) == ("", None, False)

    structured = SimpleNamespace(structuredContent={"a": 1}, isError=False, content=None)
    text, payload, is_error = manager._render_mcp_call_result(structured)
    assert payload == {"a": 1}
    assert is_error is False
    assert "a" in text


def test_render_call_result_flattens_every_content_type():
    manager = _manager()
    result = SimpleNamespace(
        structuredContent=None,
        isError=True,
        content=[
            SimpleNamespace(type="text", text="hello"),
            SimpleNamespace(type="image", mimeType="image/png"),
            SimpleNamespace(type="resource_link", uri="file:///tmp/a", name="a.txt"),
            SimpleNamespace(type="audio"),
        ],
    )

    text, payload, is_error = manager._render_mcp_call_result(result)

    assert is_error is True
    assert payload is None
    assert "hello" in text
    assert "[image:image/png]" in text
    assert "[resource:a.txt]" in text
    assert "audio" in str(text)


def test_render_call_result_falls_back_to_structured_content():
    manager = _manager()
    result = SimpleNamespace(
        structuredContent={"ok": True},
        isError=False,
        content=[SimpleNamespace(type="text", text="")],
    )

    text, payload, is_error = manager._render_mcp_call_result(result)

    assert payload == {"ok": True}
    assert "{'ok': True}" in text
    assert is_error is False


# ── Fetch helpers ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (None, True, True),
        (False, True, False),
        ("YES", False, True),
        ("off", True, False),
        ("maybe", False, True),
        (0, True, False),
    ],
)
def test_coerce_fetch_bool(value, default, expected):
    assert MCPLifecycleManager._coerce_fetch_bool(value, default) is expected


def _fetch_request(**overrides) -> dict:
    request = {"method": "GET", "url": "https://example.com/a", "max_body_chars": 20}
    request.update(overrides)
    return request


class _FakeResponse:
    def __init__(self, *, text: str = "body", status: int = 200, headers=None, url="https://example.com/a", history=(), payload=None):
        self.text = text
        self.status_code = status
        self.headers = headers if headers is not None else {"content-type": "text/plain"}
        self.url = url
        self.history = list(history)
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def test_format_fetch_response_reports_redirects_and_truncation():
    manager = _manager()
    response = _FakeResponse(
        text="x" * 60,
        url="https://example.com/b",
        history=[SimpleNamespace(status_code=301)],
    )
    request = _fetch_request(max_body_chars=20, tls_retry=True, body_mode="json")

    text = manager._format_fetch_response(response, request)

    assert "Final URL: https://example.com/b" in text
    assert "Redirects: 301 -> 200" in text
    assert "TLS verification failed" in text
    assert "Request body mode: json" in text
    assert "truncated from 60" in text


def test_format_fetch_response_pretty_prints_json():
    manager = _manager()
    response = _FakeResponse(
        text='{"a": 1}',
        headers={"content-type": "application/json"},
        payload={"a": 1},
    )

    text = manager._format_fetch_response(response, _fetch_request(max_body_chars=0))

    assert "JSON:" in text
    assert '"a": 1' in text


def test_format_fetch_response_ignores_broken_json():
    manager = _manager()
    response = _FakeResponse(text="{not json", headers={"content-type": "application/json"})

    text = manager._format_fetch_response(response, _fetch_request())

    assert "JSON:" not in text


# ── SDK attachability + teardown ─────────────────────────────────────


def test_sdk_attachability_depends_on_the_transport_and_sdk_symbols(monkeypatch):
    manager = _manager(
        stdio={"type": "stdio", "command": "noop"},
        sse={"type": "sse", "url": "http://127.0.0.1:9876/sse"},
        http={"type": "streamable-http", "url": "http://127.0.0.1:8000/mcp"},
        weird={"type": "carrier-pigeon"},
    )

    assert manager._is_sdk_attachable("stdio") is True
    assert manager._is_sdk_attachable("sse") is True
    assert manager._is_sdk_attachable("http") is True
    assert manager._is_sdk_attachable("weird") is False
    assert manager._is_sdk_attachable("missing") is False

    monkeypatch.setattr(lifecycle, "stdio_client", None)
    assert manager._is_sdk_attachable("stdio") is False


@pytest.mark.asyncio
async def test_aclose_session_meta_closes_session_then_transport():
    order: list[str] = []

    class _Closable:
        def __init__(self, label: str):
            self.label = label

        async def __aexit__(self, *_args):
            order.append(self.label)

    manager = _manager()
    await manager._aclose_session_meta({"kind": "persistent-stdio", "session": _Closable("session"), "context_manager": _Closable("cm")})
    assert order == ["session", "cm"]

    # Non-persistent metadata is left alone.
    order.clear()
    await manager._aclose_session_meta({"kind": "one-shot", "session": _Closable("session")})
    assert order == []


@pytest.mark.asyncio
async def test_aclose_session_meta_swallows_benign_but_not_real_errors():
    class _Benign:
        async def __aexit__(self, *_args):
            raise asyncio.CancelledError()

    class _Real:
        async def __aexit__(self, *_args):
            raise RuntimeError("real")

    manager = _manager()
    await manager._aclose_session_meta({"kind": "persistent-sse", "session": _Benign()})

    with pytest.raises(RuntimeError, match="real"):
        await manager._aclose_session_meta({"kind": "persistent-sse", "session": _Real()})


# ── SDK session caching ──────────────────────────────────────────────


class _FakeTransport:
    def __init__(self, *_args, **_kwargs):
        self.exited = False

    async def __aenter__(self):
        return ("read-stream", "write-stream")

    async def __aexit__(self, *_args):
        self.exited = True


class _FakeSession:
    instances: list["_FakeSession"] = []
    fail_initialize = False

    def __init__(self, read_stream, write_stream):
        self.read_stream = read_stream
        self.write_stream = write_stream
        self.initialized = False
        self.exit_calls = 0
        self.calls: list[tuple[str, dict]] = []
        _FakeSession.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        self.exit_calls += 1

    async def initialize(self):
        if _FakeSession.fail_initialize:
            raise RuntimeError("initialize failed")
        return SimpleNamespace(protocolVersion="1")

    async def list_tools(self):
        return SimpleNamespace(
            tools=[
                {"name": "alpha", "description": "first", "inputSchema": {"type": "object"}},
                {"name": "", "description": "nameless"},
            ]
        )

    async def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments or {}))
        return SimpleNamespace(isError=False, content=[SimpleNamespace(type="text", text="ok")])


@pytest.fixture
def fake_sdk(monkeypatch):
    _FakeSession.instances = []
    _FakeSession.fail_initialize = False
    monkeypatch.setattr(lifecycle, "stdio_client", _FakeTransport)
    monkeypatch.setattr(lifecycle, "sse_client", _FakeTransport)
    monkeypatch.setattr(lifecycle, "streamablehttp_client", _FakeTransport)
    monkeypatch.setattr(lifecycle, "ClientSession", _FakeSession)
    monkeypatch.setattr(lifecycle, "StdioServerParameters", lambda **kwargs: SimpleNamespace(**kwargs))
    return _FakeSession


@pytest.mark.asyncio
async def test_persistent_stdio_session_is_created_cached_and_reused(fake_sdk):
    manager = _manager(stdio={"type": "stdio", "command": "noop"})

    session = await manager._get_or_create_persistent_stdio_session("stdio")
    cached = await manager._get_or_create_persistent_stdio_session("stdio")

    assert session is cached
    meta = manager._mcp_clients["stdio"]
    assert meta["kind"] == "persistent-stdio"
    assert meta["session"] is session
    assert meta["context_manager"] is not None


@pytest.mark.asyncio
async def test_persistent_stdio_session_cleans_up_when_initialize_fails(monkeypatch):
    manager = _manager(stdio={"type": "stdio", "command": "noop"})
    monkeypatch.setattr(lifecycle, "stdio_client", _FakeTransport)
    monkeypatch.setattr(lifecycle, "ClientSession", _FakeSession)
    monkeypatch.setattr(lifecycle, "StdioServerParameters", lambda **kwargs: SimpleNamespace(**kwargs))
    _FakeSession.instances = []
    _FakeSession.fail_initialize = True

    with pytest.raises(RuntimeError, match="initialize failed"):
        await manager._get_or_create_persistent_stdio_session("stdio")

    assert _FakeSession.instances[0].exit_calls == 1
    assert "stdio" not in manager._mcp_clients


@pytest.mark.asyncio
async def test_persistent_stdio_session_requires_config():
    manager = _manager()
    with pytest.raises(RuntimeError, match="missing MCP config"):
        await manager._get_or_create_persistent_stdio_session("ghost")


@pytest.mark.asyncio
async def test_persistent_sse_session_requires_a_url(fake_sdk):
    manager = _manager(sse={"type": "sse"})
    with pytest.raises(RuntimeError, match="missing url"):
        await manager._get_or_create_persistent_sse_session("sse")


@pytest.mark.asyncio
async def test_persistent_sse_session_wraps_failures_with_details(fake_sdk, monkeypatch):
    manager = _manager(sse={"type": "sse", "url": "http://127.0.0.1:9876/sse"})
    _FakeSession.fail_initialize = True

    with pytest.raises(RuntimeError, match="sse session for sse failed: initialize failed"):
        await manager._get_or_create_persistent_sse_session("sse")


@pytest.mark.asyncio
async def test_persistent_sse_session_marks_the_server_healthy(fake_sdk):
    manager = _manager(sse={"type": "sse", "url": "http://127.0.0.1:9876/sse"})

    session = await manager._get_or_create_persistent_sse_session("sse")
    again = await manager._get_or_create_persistent_sse_session("sse")

    assert session is again
    assert manager._mcp_clients["sse"]["kind"] == "persistent-sse"
    assert manager._mcp_clients["sse"]["config"].name == "sse"


@pytest.mark.asyncio
async def test_persistent_sse_requires_the_sdk(monkeypatch):
    manager = _manager(sse={"type": "sse", "url": "http://127.0.0.1:9876/sse"})
    monkeypatch.setattr(lifecycle, "sse_client", None)

    with pytest.raises(RuntimeError, match="SDK is not installed"):
        await manager._get_or_create_persistent_sse_session("sse")


@pytest.mark.asyncio
async def test_call_stdio_server_uses_the_sdk_session(fake_sdk):
    manager = _manager(stdio={"type": "stdio", "command": "noop"})

    result = await manager._call_stdio_server("stdio", "echo", {"text": "hi"})

    assert result.content[0].text == "ok"
    assert _FakeSession.instances[0].calls == [("echo", {"text": "hi"})]


@pytest.mark.asyncio
async def test_call_stdio_server_requires_config():
    manager = _manager()
    with pytest.raises(RuntimeError, match="missing MCP config"):
        await manager._call_stdio_server("ghost", "echo", {})


@pytest.mark.asyncio
async def test_get_or_create_session_dispatches_on_transport(fake_sdk):
    manager = _manager(
        stdio={"type": "stdio", "command": "noop"},
        sse={"type": "sse", "url": "http://127.0.0.1:9876/sse"},
    )

    stdio_session = await manager._get_or_create_session("stdio")
    sse_session = await manager._get_or_create_session("sse")

    assert stdio_session is not sse_session
    assert manager._mcp_clients["stdio"]["kind"] == "persistent-stdio"
    assert manager._mcp_clients["sse"]["kind"] == "persistent-sse"
