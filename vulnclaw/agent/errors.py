"""Typed agent errors that presentation layers can act on."""

from __future__ import annotations

import re

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1***"),
    (
        re.compile(
            r"(?i)((?:api[_ -]?key|access[_ -]?token|token)"
            r"(?:\s*[:=]\s*|\s+provided:\s*))[A-Za-z0-9._\-]{8,}"
        ),
        r"\1***",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9._\-]{8,}\b"), "***"),
)


_AUTH_FAILURE_MARKERS = (
    "incorrect api key",
    "invalid api key",
    "invalid_api_key",
    "authentication",
    "unauthorized",
    "permission denied",
    "401",
    "403",
)


def is_auth_failure(text: str) -> bool:
    """Whether an LLM error means the credential/authorization is unusable."""
    lowered = str(text).lower()
    return any(marker in lowered for marker in _AUTH_FAILURE_MARKERS)


def redact_secrets(text: str) -> str:
    """Remove credential-shaped substrings before an error reaches logs or UI."""
    redacted = str(text)
    for pattern, replacement in _REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class LLMInvocationError(RuntimeError):
    """An LLM call failed in a way the task layer must treat as a task failure."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "",
        provider: str = "",
        cause: BaseException | None = None,
        fatal: bool = True,
    ) -> None:
        super().__init__(redact_secrets(message))
        self.stage = stage
        self.provider = provider
        self.cause = cause
        self.fatal = fatal

    def __str__(self) -> str:
        message = super().__str__()
        if self.stage:
            return f"{message} (stage={self.stage})"
        return message
