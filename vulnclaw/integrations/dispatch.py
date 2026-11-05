"""Integration export for findings: webhook, Jira and DefectDojo."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import httpx

IntegrationKind = Literal["webhook", "jira", "defectdojo"]


@dataclass
class IntegrationConfig:
    name: str
    kind: IntegrationKind
    url: str
    token: str = ""
    project_key: str = ""
    enabled: bool = True
    timeout: float = 10.0
    retries: int = 3
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class DeliveryResult:
    name: str
    ok: bool
    attempts: int
    status_code: int | None = None
    error: str = ""


def _idempotency_key(target: str, run_name: str, finding: dict[str, Any]) -> str:
    seed = f"{target}:{run_name}:{finding.get('title', '')}:{finding.get('severity', '')}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def adf_document(lines: list[str]) -> dict[str, Any]:
    """Build an Atlassian Document Format body for a Jira Cloud v3 field.

    ``/rest/api/3/issue`` rejects plain strings for rich-text fields, so every
    Jira description this module sends is wrapped as ADF paragraphs.
    """
    content = [
        {"type": "paragraph", "content": [{"type": "text", "text": str(line)}]}
        for line in lines
        if str(line).strip()
    ]
    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": "(no detail)"}]}]
    return {"type": "doc", "version": 1, "content": content}


def _finding_payload(config: IntegrationConfig, target: str, run_name: str, finding: dict[str, Any]) -> dict[str, Any]:
    if config.kind == "jira":
        description = adf_document(
            [
                str(item)
                for item in (
                    finding.get("description", ""),
                    finding.get("evidence", ""),
                    finding.get("remediation", ""),
                )
                if item
            ]
        )
        return {
            "fields": {
                "project": {"key": config.project_key},
                "summary": f"[VulnClaw] {finding.get('title', 'Finding')}",
                "description": description,
                "issuetype": {"name": "Bug"},
            }
        }
    if config.kind == "defectdojo":
        return {
            "title": finding.get("title", "Finding"),
            "severity": str(finding.get("severity", "Info")),
            "description": finding.get("description", ""),
            "active": True,
            "verified": bool(finding.get("verified")),
        }
    return {
        "source": "vulnclaw",
        "target": target,
        "run_name": run_name,
        "finding": finding,
    }


def _endpoint(config: IntegrationConfig) -> str:
    if config.kind == "jira":
        return config.url.rstrip("/") + "/rest/api/3/issue"
    if config.kind == "defectdojo":
        return config.url.rstrip("/") + "/api/v2/findings/"
    return config.url


# A run lifecycle notification is not a finding: Jira gets one issue per run and
# DefectDojo gets one engagement, so the resource path differs from delivery.
_RUN_EVENT_PATHS = {"jira": "/rest/api/3/issue", "defectdojo": "/api/v2/engagements/"}


def run_event_endpoint(config: IntegrationConfig) -> str:
    """Endpoint that accepts a run lifecycle notification for this kind."""
    path = _RUN_EVENT_PATHS.get(config.kind)
    return config.url.rstrip("/") + path if path else config.url


def _headers(config: IntegrationConfig, idempotency_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json", **config.headers}
    headers.setdefault("Idempotency-Key", idempotency_key)
    if config.kind == "jira":
        headers.setdefault("Authorization", f"Bearer {config.token}")
    elif config.kind == "defectdojo":
        headers.setdefault("Authorization", f"Token {config.token}")
    elif config.token:
        headers.setdefault("Authorization", f"Bearer {config.token}")
    return headers


def _post_with_retry(
    config: IntegrationConfig,
    *,
    endpoint: str,
    payload: dict[str, Any],
    idempotency_key: str,
    http: httpx.Client,
    sleep: Callable[[float], None],
) -> DeliveryResult:
    """POST one payload, retrying 5xx/429 and transport failures."""
    attempts = 0
    last_status: int | None = None
    last_error = ""
    ok = False
    max_attempts = max(1, config.retries)
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        try:
            response = http.post(
                endpoint,
                json=payload,
                headers=_headers(config, idempotency_key),
            )
            last_status = response.status_code
            if 200 <= response.status_code < 300:
                ok = True
                break
            last_error = f"HTTP {response.status_code}"
            if response.status_code < 500 and response.status_code != 429:
                break
        except httpx.HTTPError as exc:
            last_error = str(exc)
        if attempt < max_attempts:
            sleep(min(0.1 * attempt, 1.0))
    return DeliveryResult(
        name=config.name,
        ok=ok,
        attempts=attempts,
        status_code=last_status,
        error="" if ok else last_error,
    )


def dispatch_findings(
    config: IntegrationConfig,
    *,
    target: str,
    run_name: str,
    findings: list[dict[str, Any]],
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[DeliveryResult]:
    """Deliver every finding, retrying retriable failures."""
    results: list[DeliveryResult] = []
    owns_client = client is None
    http = client or httpx.Client(timeout=config.timeout)
    try:
        for finding in findings:
            key = _idempotency_key(target, run_name, finding)
            results.append(
                _post_with_retry(
                    config,
                    endpoint=_endpoint(config),
                    payload=_finding_payload(config, target, run_name, finding),
                    idempotency_key=key,
                    http=http,
                    sleep=sleep,
                )
            )
    finally:
        if owns_client:
            http.close()
    return results


def dispatch_notification(
    config: IntegrationConfig,
    *,
    payload: dict[str, Any],
    idempotency_key: str,
    endpoint: str | None = None,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> DeliveryResult:
    """Deliver one run lifecycle notification."""
    owns_client = client is None
    http = client or httpx.Client(timeout=config.timeout)
    try:
        return _post_with_retry(
            config,
            endpoint=endpoint or run_event_endpoint(config),
            payload=payload,
            idempotency_key=idempotency_key,
            http=http,
            sleep=sleep,
        )
    finally:
        if owns_client:
            http.close()
