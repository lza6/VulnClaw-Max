"""Config helpers: overlay, value coercion, provider presets."""

from __future__ import annotations

import pytest

from vulnclaw.config.schema import VulnClawConfig
from vulnclaw.config.settings import (
    _overlay_env,
    apply_llm_form,
    apply_provider_preset,
    list_providers,
    normalize_base_url,
    provider_form_values,
)


def test_overlay_env_applies_llm_and_session(monkeypatch):
    config = VulnClawConfig()
    monkeypatch.setenv("VULNCLAW_LLM_API_KEY", "k")
    monkeypatch.setenv("VULNCLAW_LLM_API_KEYS", "a,b")
    monkeypatch.setenv("VULNCLAW_LLM_BASE_URL", "https://example/v1")
    monkeypatch.setenv("VULNCLAW_LLM_MODEL", "m")
    monkeypatch.setenv("VULNCLAW_LLM_PROVIDER", "custom")
    monkeypatch.setenv("VULNCLAW_LLM_MAX_TOKENS", "123")
    monkeypatch.setenv("VULNCLAW_LLM_TEMPERATURE", "0.5")
    monkeypatch.setenv("VULNCLAW_SESSION_MAX_ROUNDS", "7")
    monkeypatch.setenv("VULNCLAW_SESSION_SHOW_THINKING", "true")
    monkeypatch.setenv("VULNCLAW_SAFETY_PYTHON_EXECUTE_ENABLED", "true")

    result = _overlay_env(config)

    assert result.llm.api_key == "k"
    assert result.llm.api_keys == ["a", "b"]
    assert result.llm.base_url == "https://example/v1"
    assert result.llm.model == "m"
    assert result.llm.max_tokens == 123
    assert result.session.max_rounds == 7
    assert result.session.show_thinking is True


def test_set_config_value_coerces_types(monkeypatch):
    import vulnclaw.config.settings as settings

    config = VulnClawConfig()
    saved = {}
    monkeypatch.setattr(settings, "load_config", lambda: config)
    monkeypatch.setattr(settings, "save_config", lambda cfg: saved.setdefault("cfg", cfg))

    settings.set_config_value("session.max_rounds", "9")
    settings.set_config_value("session.show_thinking", "true")
    settings.set_config_value("llm.temperature", "0.2")
    settings.set_config_value("llm.api_keys", "a,b")

    assert config.session.max_rounds == 9
    assert config.session.show_thinking is True
    assert config.llm.temperature == 0.2
    assert config.llm.api_keys == ["a", "b"]
    assert saved["cfg"] is config


def test_normalize_base_url_boundaries():
    assert normalize_base_url(None) == ""
    assert normalize_base_url(" https://example.com/v1/ ") == "https://example.com/v1"
    with pytest.raises(ValueError):
        normalize_base_url("ftp://example.com")
    with pytest.raises(ValueError):
        normalize_base_url("https://user:pass@example.com")
    with pytest.raises(ValueError):
        normalize_base_url("https://example.com?v=1")


def test_provider_presets_and_form_values():
    providers = list_providers()
    assert providers
    assert any(item["provider"] == "openai" for item in providers)
    values = provider_form_values("openai")
    assert values["base_url"]
    with pytest.raises(ValueError):
        provider_form_values("nope")

    config = VulnClawConfig()
    apply_provider_preset(config, "deepseek")
    assert config.llm.provider == "deepseek"
    apply_provider_preset(config, "unknown-provider")
    assert config.llm.provider == "unknown-provider"


def test_apply_llm_form_validates():
    config = VulnClawConfig()
    apply_llm_form(config, provider="openai", base_url="", model="")
    assert config.llm.model
    with pytest.raises(ValueError):
        apply_llm_form(config, provider="custom", base_url="", model="")
    with pytest.raises(ValueError):
        apply_llm_form(config, provider="custom", base_url="https://x", model="")
    with pytest.raises(ValueError):
        apply_llm_form(config, provider="nope", base_url="https://x", model="m")


def test_fetch_provider_models_errors(monkeypatch):
    from vulnclaw.config.settings import fetch_provider_models

    assert fetch_provider_models("", "") == []
    monkeypatch.setattr("vulnclaw.config.settings.make_openai_client", lambda **_k: (_ for _ in ()).throw(RuntimeError("x")))
    assert fetch_provider_models("https://x", "k") == []


def test_set_config_value_dict_branch(monkeypatch):
    import vulnclaw.config.settings as settings
    from vulnclaw.config.schema import (
        MCPServerConfig,
        MCPServersConfig,
        MCPTransportConfig,
        VulnClawConfig,
    )

    server = MCPServerConfig(
        name="fetch",
        enabled=True,
        transport=MCPTransportConfig(type="stdio", command="x"),
    )
    config = VulnClawConfig(mcp=MCPServersConfig(servers={"fetch": server}))
    saved = {}
    monkeypatch.setattr(settings, "load_config", lambda: config)
    monkeypatch.setattr(settings, "save_config", lambda cfg: saved.setdefault("cfg", cfg))

    settings.set_config_value("mcp.servers.fetch.enabled", "false")
    assert config.mcp.servers["fetch"].enabled is False
