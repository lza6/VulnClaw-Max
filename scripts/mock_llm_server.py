"""OpenAI-compatible mock server that reproduces real LLM failure modes.

The mock drives the real ``openai`` SDK over HTTP, so failure classification is
tested against provider wire formats instead of hand-built exceptions. No paid
request is ever made.

Manual use::

    python scripts/mock_llm_server.py --port 8765
    # base_url=http://127.0.0.1:8765/v1, model=mock-429

Scenario selection order: the ``X-Mock-Scenario`` header, the ``mock-<scenario>``
model name, then ``ok``. Scenarios: ``ok``, ``stream_ok``, ``tool``, ``401``,
``403``, ``429``, ``500``, ``timeout``, ``malformed``, ``empty_choices``,
``drop``, ``retry_then_ok``, ``hang``.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

SCENARIOS = (
    "ok",
    "stream_ok",
    "tool",
    "401",
    "403",
    "429",
    "500",
    "timeout",
    "malformed",
    "empty_choices",
    "drop",
    "retry_then_ok",
    "hang",
)

_HANG_SECONDS = 1.0


def _completion_payload(model: str, content: str = "mock ok") -> dict[str, Any]:
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
    }


def _tool_payload(model: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-mock-tool",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_mock",
                            "type": "function",
                            "function": {
                                "name": "http_request",
                                "arguments": '{"url": "http://127.0.0.1:1/"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 8, "total_tokens": 19},
    }


def _error_payload(message: str, kind: str, code: str | None = None) -> dict[str, Any]:
    return {"error": {"message": message, "type": kind, "code": code}}


class MockLLMServer(ThreadingHTTPServer):
    """Threaded mock server that also records every received request."""

    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        timeout_seconds: float = 1.0,
        retry_failures: int = 2,
    ) -> None:
        super().__init__(address, _MockHandler)
        self.timeout_seconds = timeout_seconds
        self.retry_failures = retry_failures
        self.requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._retry_attempts = 0

    @property
    def base_url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}/v1"

    def record(self, scenario: str, body: dict[str, Any]) -> None:
        with self._lock:
            self.requests.append({"scenario": scenario, "body": body})

    def next_retry_attempt(self) -> int:
        with self._lock:
            self._retry_attempts += 1
            return self._retry_attempts


def scenario_from_request(body: dict[str, Any], header: str | None) -> str:
    if header:
        return header.strip().lower()
    model = str(body.get("model") or "")
    if model.lower().startswith("mock-"):
        return model[5:].strip().lower()
    return "ok"


class _MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: MockLLMServer

    def log_message(self, *_args: Any) -> None:  # keep pytest output clean
        pass

    def do_POST(self) -> None:  # noqa: N802 - http.server contract
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._send_json(404, _error_payload("unknown path", "invalid_request_error"))
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {}

        scenario = scenario_from_request(body, self.headers.get("X-Mock-Scenario"))
        model = str(body.get("model") or "mock")
        self.server.record(scenario, body)

        if scenario == "ok":
            self._send_json(200, _completion_payload(model))
        elif scenario == "tool":
            self._send_json(200, _tool_payload(model))
        elif scenario == "stream_ok":
            self._send_stream(model)
        elif scenario == "401":
            self._send_json(
                401,
                _error_payload(
                    "Incorrect API key provided: sk-mock-secret-123456",
                    "invalid_request_error",
                    "invalid_api_key",
                ),
            )
        elif scenario == "403":
            self._send_json(
                403,
                _error_payload("Permission denied for this model", "permission_error"),
            )
        elif scenario == "429":
            self._send_json(
                429,
                _error_payload(
                    "Rate limit reached for requests", "rate_limit_error", "rate_limit_exceeded"
                ),
            )
        elif scenario == "500":
            self._send_json(500, _error_payload("Internal server error", "server_error"))
        elif scenario == "timeout":
            time.sleep(self.server.timeout_seconds)
            self._send_json(200, _completion_payload(model))
        elif scenario == "hang":
            time.sleep(_HANG_SECONDS)
            self._send_json(200, _completion_payload(model))
        elif scenario == "malformed":
            self._send_raw(200, b"<html>not a completion</html>", "text/html")
        elif scenario == "empty_choices":
            self._send_json(200, {"choices": [], "usage": None})
        elif scenario == "drop":
            self.close_connection = True
        elif scenario == "retry_then_ok":
            attempt = self.server.next_retry_attempt()
            if attempt <= self.server.retry_failures:
                self._send_json(500, _error_payload("Internal server error", "server_error"))
            else:
                self._send_json(200, _completion_payload(model))
        else:
            self._send_json(
                400,
                _error_payload(f"unknown scenario: {scenario}", "invalid_request_error"),
            )

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        self._send_raw(
            status,
            json.dumps(payload).encode("utf-8"),
            "application/json",
        )

    def _send_raw(self, status: int, body: bytes, content_type: str) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            # The client already gave up (timeout scenario) - nothing to send.
            pass

    def _send_stream(self, model: str) -> None:
        chunks = [
            {"delta": {"role": "assistant", "content": "mock "}, "finish_reason": None},
            {"delta": {"content": "ok"}, "finish_reason": None},
            {"delta": {}, "finish_reason": "stop"},
        ]
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for chunk in chunks:
                payload = {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, **chunk}],
                }
                self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except OSError:
            pass


def start_mock_llm_server(
    *,
    port: int = 0,
    timeout_seconds: float = 1.0,
    retry_failures: int = 2,
) -> MockLLMServer:
    """Start the mock on a daemon thread and return the running server."""

    server = MockLLMServer(
        ("127.0.0.1", port),
        timeout_seconds=timeout_seconds,
        retry_failures=retry_failures,
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout-seconds", type=float, default=3.0)
    parser.add_argument("--retry-failures", type=int, default=2)
    args = parser.parse_args()

    server = start_mock_llm_server(
        port=args.port,
        timeout_seconds=args.timeout_seconds,
        retry_failures=args.retry_failures,
    )
    print(f"mock LLM listening on {server.base_url}")
    print("scenarios: " + ", ".join(SCENARIOS))
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
