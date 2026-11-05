"""Example VulnClaw plugin: flag Set-Cookie values missing security attributes.

Install it into the same environment as VulnClaw::

    pip install ./examples/plugins/vulnclaw-plugin-demo

The ``vulnclaw.plugins`` entry point then makes the plugin visible to
``vulnclaw plugins list --external`` and to the Web UI plugin inventory.
"""

from __future__ import annotations

from vulnclaw.plugins import (
    PluginContext,
    PluginFinding,
    PluginResult,
    PluginStage,
    RiskLevel,
    VulnPlugin,
)

REQUIRED_FLAGS = ("Secure", "HttpOnly", "SameSite")


class CookieFlagsPlugin(VulnPlugin):
    plugin_id = "demo.web.cookie_flags"
    name = "Cookie Security Flags"
    version = "0.1.0"
    description = (
        "Analyze supplied Set-Cookie header values and flag cookies missing "
        "Secure, HttpOnly or SameSite."
    )
    stages = (PluginStage.DISCOVERY, PluginStage.VERIFICATION)
    default_risk = RiskLevel.LOW
    requires_target = False
    tags = ("web", "cookies", "example")
    permissions = ()

    def run(self, context: PluginContext) -> PluginResult:
        raw = context.options.get("set_cookie") or []
        values = raw if isinstance(raw, (list, tuple)) else [raw]
        findings: list[PluginFinding] = []
        for value in values:
            cookie = str(value).strip()
            if not cookie:
                continue
            lowered = cookie.lower()
            missing = [flag for flag in REQUIRED_FLAGS if flag.lower() not in lowered]
            if not missing:
                continue
            risk = RiskLevel.MEDIUM if len(missing) == len(REQUIRED_FLAGS) else self.default_risk
            findings.append(
                PluginFinding(
                    title=f"Cookie missing {', '.join(missing)} flag(s)",
                    risk=risk,
                    target=context.target,
                    vuln_type="insecure-cookie",
                    description=(
                        "Cookie attributes below are absent, which weakens session "
                        "confidentiality or CSRF resistance."
                    ),
                    evidence={"set_cookie": cookie, "missing": missing},
                    remediation=f"Add {' / '.join(missing)} to the Set-Cookie response.",
                    confidence=0.9,
                )
            )
        if not values:
            return PluginResult.skipped_result(
                self.plugin_id,
                "No set_cookie option supplied; nothing to analyze.",
                stage=context.stage,
            )
        return PluginResult(
            plugin_id=self.plugin_id,
            stage=context.stage,
            findings=findings,
            messages=[
                f"Analyzed {len(values)} cookie value(s); {len(findings)} flagged."
            ],
        )


__all__ = ["CookieFlagsPlugin"]
