"""First-run wizard flows: stage planning, Java/Burp provisioning, IO helpers.

Every external effect (subprocess, winget, browser launch, port probe) is faked:
these tests pin the wizard's decisions, not the local machine's toolchain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vulnclaw.cli import wizard


class FakeConsole:
    """Minimal Rich console double that feeds scripted answers."""

    def __init__(self, answers: list[str] | None = None, *, is_terminal: bool = False):
        self.answers = list(answers or [])
        self.lines: list[str] = []
        self.is_terminal = is_terminal
        self.cleared = 0

    def print(self, *args, **_kwargs) -> None:
        self.lines.append(" ".join(str(arg) for arg in args))

    def input(self, _prompt: str = "") -> str:
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)

    def clear(self) -> None:
        self.cleared += 1

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _ui(answers: list[str] | None = None) -> tuple[wizard._WizardUi, FakeConsole]:
    console = FakeConsole(answers)
    return wizard._WizardUi(console=console), console


def _status(**overrides) -> wizard.SetupStatus:
    status = wizard.SetupStatus()
    for key, value in overrides.items():
        setattr(status, key, value)
    return status


class _Proc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ── UX helpers ───────────────────────────────────────────────────────


def test_clear_noop_when_not_a_terminal():
    ui, console = _ui()
    ui.clear()
    # Non-terminal consoles must not emit escape-sequence clears.
    assert console.cleared == 0


def test_clear_forces_platform_clear_on_terminal(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(wizard.platform, "system", lambda: "Windows")
    monkeypatch.setattr(wizard.os, "system", lambda command: calls.append(command) or 0)
    console = FakeConsole(is_terminal=True)
    ui = wizard._WizardUi(console=console)

    ui.clear()

    assert calls == ["cls"]
    assert console.cleared == 1


def test_banner_and_stage_progress_render_the_plan():
    ui, console = _ui()
    status = _status(llm_ready=True, language="en")

    ui.banner(status)
    ui.begin("Prerequisites", 1)
    ui.finish(["done"])

    assert "VulnClaw first-run wizard" in console.text
    assert "Already configured" in console.text
    assert "Still needed" in console.text
    assert "Prerequisites" in console.text
    assert "done" in console.text
    assert ui.index == 1


def test_ask_falls_back_to_the_default_on_eof_and_blank():
    console = FakeConsole([])
    assert wizard._ask(console, "Provider", default="openai") == "openai"

    blank = FakeConsole([""])
    assert wizard._ask(blank, "Provider", default="openai") == "openai"

    answered = FakeConsole(["anthropic"])
    assert wizard._ask(answered, "Provider", default="openai") == "anthropic"


def test_confirm_honours_defaults_and_yes():
    assert wizard._confirm(FakeConsole([""]), "Start?", default=True) is True
    assert wizard._confirm(FakeConsole([""]), "Start?", default=False) is False
    assert wizard._confirm(FakeConsole(["y"]), "Start?") is True
    assert wizard._confirm(FakeConsole(["no"]), "Start?") is False


def test_ask_secret_returns_empty_on_interrupt(monkeypatch):
    import getpass

    console = FakeConsole([])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": " sk-secret ")
    assert wizard._ask_secret(console, "API key") == "sk-secret"

    def boom(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr(getpass, "getpass", boom)
    assert wizard._ask_secret(console, "API key") == ""


def test_pause_swallows_eof():
    wizard._pause(FakeConsole([]), "Continue")


# ── Java detection and provisioning ──────────────────────────────────


def test_detect_java_path_uses_java_home(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard.shutil, "which", lambda _name: None)
    home = tmp_path / "jdk"
    (home / "bin").mkdir(parents=True)
    binary = home / "bin" / ("java.exe" if wizard.platform.system() == "Windows" else "java")
    binary.write_text("", encoding="utf-8")
    monkeypatch.setenv("JAVA_HOME", str(home))

    assert wizard.detect_java_path() == str(binary)


def test_ensure_java_accepts_a_supported_runtime(monkeypatch, tmp_path):
    binary = tmp_path / "java"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setattr(wizard, "detect_java_path", lambda: str(binary))
    monkeypatch.setattr(wizard, "java_meets_minimum", lambda *_args, **_kwargs: True)
    status = _status(java=None)
    console = FakeConsole([])

    java, error = wizard.ensure_java(console, status)

    assert java == str(binary)
    assert error == ""
    assert status.java == str(binary)


def test_ensure_java_installs_temurin_via_winget(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    found = tmp_path / "jdk-17" / "bin" / "java"
    found.parent.mkdir(parents=True)
    found.write_text("", encoding="utf-8")

    monkeypatch.setattr(wizard.platform, "system", lambda: "Windows")
    monkeypatch.setattr(wizard.shutil, "which", lambda name: "C:/winget.exe" if name == "winget" else None)
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: True)
    scans = {"count": 0}

    def scan():
        scans["count"] += 1
        return None if scans["count"] == 1 else str(found)

    monkeypatch.setattr(wizard, "detect_java_path", scan)
    monkeypatch.setattr(wizard, "java_meets_minimum", lambda *_args, **_kwargs: True)

    def fake_run(args, **_kwargs):
        calls.append(args)
        return _Proc(0)

    monkeypatch.setattr(wizard.subprocess, "run", fake_run)
    status = _status(java=None)
    console = FakeConsole([])

    java, error = wizard.ensure_java(console, status)

    assert calls and calls[0][1] == "install"
    assert "EclipseAdoptium.Temurin.17.JDK" in calls[0]
    assert java == str(found)
    assert "Java found" in console.text


def test_ensure_java_reports_path_refresh_when_binary_is_not_visible(monkeypatch):
    monkeypatch.setattr(wizard.platform, "system", lambda: "Windows")
    monkeypatch.setattr(wizard.shutil, "which", lambda name: "C:/winget.exe" if name == "winget" else None)
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: True)
    monkeypatch.setattr(wizard, "detect_java_path", lambda: None)
    monkeypatch.setattr(wizard.subprocess, "run", lambda *_a, **_k: _Proc(1, stderr="already installed"))
    console = FakeConsole([])

    java, error = wizard.ensure_java(console, _status(java=None))

    assert java is None
    assert "restart shell" in error
    assert "winget exit 1" in console.text


def test_ensure_java_offers_the_download_page_when_no_winget(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(wizard.platform, "system", lambda: "Linux")
    monkeypatch.setattr(wizard.shutil, "which", lambda _name: None)
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: True)
    monkeypatch.setattr(wizard, "_open_url", lambda url: opened.append(url))
    monkeypatch.setattr(wizard, "detect_java_path", lambda: None)
    console = FakeConsole([])

    java, error = wizard.ensure_java(console, _status(java=None))

    assert java is None
    assert "no Java 17+ found" in error
    assert opened and opened[0].startswith("https://adoptium.net")


def test_ensure_java_rejects_an_old_runtime(monkeypatch):
    monkeypatch.setattr(wizard.platform, "system", lambda: "Linux")
    monkeypatch.setattr(wizard.shutil, "which", lambda _name: None)
    monkeypatch.setattr(wizard, "detect_java_path", lambda: "/usr/bin/java8")
    monkeypatch.setattr(wizard, "java_meets_minimum", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(wizard, "_java_major_version", lambda _bin: 8)
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: False)
    status = _status(java="/usr/bin/java8")
    console = FakeConsole([])

    java, _error = wizard.ensure_java(console, status)

    assert java is None
    assert status.java is None
    assert "Java 8" in console.text


# ── Stage orchestration ──────────────────────────────────────────────


def test_stage_prereqs_lists_tool_availability(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "node" else None)
    monkeypatch.setattr(wizard, "detect_java_path", lambda: None)
    monkeypatch.setattr(wizard, "detect_chrome_path", lambda: None)
    ui, console = _ui()

    status = wizard._stage_prereqs(ui, _status())

    assert status.node == "/usr/bin/node"
    assert status.npx is None
    assert "Node.js" in console.text
    assert "Install Node.js LTS" in console.text


def test_stage_chrome_skips_when_debug_endpoint_is_live(monkeypatch):
    ui, _console = _ui()
    result = wizard.WizardResult()
    status = _status(chrome_debug_live=True, chrome_path="/usr/bin/chrome", debug_port=9333)

    port, chrome, profile, returned = wizard._stage_chrome(ui, status, result)

    assert port == 9333
    assert chrome == "/usr/bin/chrome"
    assert profile == wizard.CHROME_PROFILE
    assert returned.chrome_debug_live is True
    assert result.skipped and "Chrome debug" in result.skipped[0]


def test_stage_chrome_launches_an_explicit_path(monkeypatch, tmp_path):
    launched: list[tuple[str, int]] = []
    monkeypatch.setattr(wizard, "CHROME_PROFILE", tmp_path / "profile")
    monkeypatch.setattr(
        wizard,
        "launch_chrome_debug",
        lambda chrome, *, port, user_data_dir: launched.append((chrome, port)) or True,
    )
    monkeypatch.setattr(wizard, "port_open", lambda host, port: True)
    ui, console = _ui(["/opt/chrome"])

    port, chrome, _profile, status = wizard._stage_chrome(ui, _status(), wizard.WizardResult())

    assert chrome == "/opt/chrome"
    assert launched == [("/opt/chrome", wizard.DEFAULT_DEBUG_PORT)]
    assert status.chrome_debug_live is True
    assert "DevTools live" in console.text


def test_stage_chrome_warns_when_chrome_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "CHROME_PROFILE", tmp_path / "profile")
    monkeypatch.setattr(wizard, "port_open", lambda host, port: False)
    ui, console = _ui([""])

    _port, chrome, _profile, status = wizard._stage_chrome(ui, _status(), wizard.WizardResult())

    assert chrome is None
    assert status.chrome_debug_live is False
    assert "Chrome not found" in console.text
    assert "not up yet" in console.text


def test_stage_chrome_devtools_skips_when_already_configured():
    ui, _console = _ui()
    result = wizard.WizardResult()
    status = _status(chrome_devtools_enabled=True, chrome_devtools_url="http://127.0.0.1:9222")

    config, _status_out = wizard._stage_chrome_devtools(
        ui, wizard.VulnClawConfig(), status, 9222, result
    )

    assert result.skipped == ["chrome-devtools MCP"]
    assert config.mcp.servers.get("chrome-devtools") is None


def test_stage_chrome_devtools_enables_the_server_when_missing():
    ui, console = _ui()
    result = wizard.WizardResult()
    status = _status(chrome_devtools_enabled=False, npx=None)

    config, status_out = wizard._stage_chrome_devtools(
        ui, wizard.VulnClawConfig(), status, 9222, result
    )

    server = config.mcp.servers["chrome-devtools"]
    assert server.enabled is True
    assert status_out.chrome_devtools_enabled is True
    assert "npx missing" in console.text


def test_stage_burp_skips_when_sse_is_live():
    ui, _console = _ui()
    result = wizard.WizardResult()

    config, _status_out = wizard._stage_burp(
        ui, wizard.VulnClawConfig(), _status(burp_enabled=True, burp_sse_live=True), result
    )

    assert result.skipped == ["Burp MCP"]


def test_stage_burp_skips_rebuild_when_the_jar_is_ready():
    ui, _console = _ui()
    result = wizard.WizardResult()

    _config, status = wizard._stage_burp(
        ui,
        wizard.VulnClawConfig(),
        _status(burp_enabled=True, burp_jar=Path("burp-mcp-all.jar"), burp_sse_live=False),
        result,
    )

    assert "JAR ready" in result.skipped[0]
    assert status.burp_enabled is True


def test_stage_burp_skipped_by_the_operator(monkeypatch):
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: False)
    ui, console = _ui([])

    config, status = wizard._stage_burp(
        ui, wizard.VulnClawConfig(), _status(burp_enabled=False), wizard.WizardResult()
    )

    assert config.mcp.servers.get("burp") is None
    assert status.burp_enabled is False
    assert "Skipped Burp" in console.text


def test_stage_burp_reports_a_missing_java(monkeypatch):
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: True)
    monkeypatch.setattr(wizard, "ensure_java", lambda con, status: (None, "no java"))
    ui, console = _ui([])

    _config, status = wizard._stage_burp(
        ui, wizard.VulnClawConfig(), _status(burp_enabled=False), wizard.WizardResult()
    )

    assert status.burp_enabled is False
    assert "Cannot build Burp MCP: no java" in console.text


def test_stage_burp_reports_a_failed_build(monkeypatch):
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: True)
    monkeypatch.setattr(wizard, "ensure_java", lambda con, status: ("/usr/bin/java", ""))
    monkeypatch.setattr(
        wizard, "ensure_burp_mcp_jar", lambda *, console, status: (False, None, "gradle failed")
    )
    ui, console = _ui([])

    _config, status = wizard._stage_burp(
        ui, wizard.VulnClawConfig(), _status(burp_enabled=False), wizard.WizardResult()
    )

    assert status.burp_enabled is False
    assert "gradle failed" in console.text


def test_stage_burp_enables_config_after_a_successful_build(monkeypatch, tmp_path):
    jar = tmp_path / "burp-mcp-all.jar"
    jar.write_text("", encoding="utf-8")
    monkeypatch.setattr(wizard, "ensure_java", lambda con, status: (str(tmp_path / "java"), ""))
    monkeypatch.setattr(
        wizard, "ensure_burp_mcp_jar", lambda *, console, status: (True, jar, "")
    )
    monkeypatch.setattr(wizard, "port_open", lambda host, port: False)
    # Confirm the install, decline opening the JAR folder afterwards.
    confirmations = {"count": 0}

    def confirm_install(con, question, default=False):
        confirmations["count"] += 1
        return confirmations["count"] == 1

    monkeypatch.setattr(wizard, "_confirm", confirm_install)
    ui, console = _ui([])

    config, status = wizard._stage_burp(
        ui, wizard.VulnClawConfig(), _status(burp_enabled=False), wizard.WizardResult()
    )

    assert status.burp_enabled is True
    assert config.mcp.servers["burp"].enabled is True
    assert "JAR ready" in console.text
    assert "One manual Burp step remains" in console.text


def test_stage_llm_sets_the_ollama_placeholder(monkeypatch):
    monkeypatch.setattr(wizard, "_ask", lambda con, prompt, default="": "ollama")
    monkeypatch.setattr(wizard, "has_llm_credentials", lambda _llm: True)
    ui, console = _ui([])

    config, status = wizard._stage_llm(
        ui, wizard.VulnClawConfig(), _status(llm_ready=False), wizard.WizardResult()
    )

    assert config.llm.provider == "ollama"
    assert config.llm.api_key
    assert status.llm_ready is True
    assert "Ollama placeholder API key set" in console.text


def test_stage_language_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(wizard, "_ask", lambda con, prompt, default="": "klingon")
    ui, console = _ui([])
    config = wizard.VulnClawConfig()
    config.session.language = "auto"

    updated, status = wizard._stage_language(
        ui, config, _status(language="auto"), wizard.WizardResult()
    )

    assert updated.session.language == "en"
    assert status.language == "en"
    assert "session.language → en" in console.text


# ── Burp JAR provisioning ────────────────────────────────────────────


def test_ensure_burp_mcp_jar_copies_an_existing_jar_to_the_stable_path(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    existing = tmp_path / "Downloads" / wizard.BURP_JAR_NAME
    existing.parent.mkdir()
    existing.write_text("jar", encoding="utf-8")
    monkeypatch.setattr(wizard, "find_burp_jar", lambda: existing)
    console = FakeConsole([])

    ok, jar, error = wizard.ensure_burp_mcp_jar(console=console, status=_status())

    assert ok is True and error == ""
    assert jar == tmp_path / "tools" / wizard.BURP_JAR_NAME
    assert jar.is_file()


def test_ensure_burp_mcp_jar_requires_git(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "find_burp_jar", lambda: None)
    monkeypatch.setattr(wizard.shutil, "which", lambda _name: None)

    ok, jar, error = wizard.ensure_burp_mcp_jar(console=FakeConsole([]), status=_status(git=None))

    assert ok is False and jar is None
    assert "git not found" in error


def test_ensure_burp_mcp_jar_requires_java(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "find_burp_jar", lambda: None)
    monkeypatch.setattr(wizard.shutil, "which", lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.setattr(wizard, "detect_java_path", lambda: None)

    ok, jar, error = wizard.ensure_burp_mcp_jar(console=FakeConsole([]), status=_status())

    assert ok is False and jar is None
    assert "java not found" in error


def test_ensure_burp_mcp_jar_clones_and_builds(monkeypatch, tmp_path):
    tools = tmp_path / "tools"
    repo = tmp_path / "burp-mcp"
    monkeypatch.setattr(wizard, "TOOLS_DIR", tools)
    monkeypatch.setattr(wizard, "BURP_MCP_DIR", repo)
    monkeypatch.setattr(wizard, "find_burp_jar", lambda: None)
    monkeypatch.setattr(wizard.shutil, "which", lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.setattr(wizard, "detect_java_path", lambda: "/usr/lib/jvm/jdk-17/bin/java")
    monkeypatch.setattr(wizard.platform, "system", lambda: "Linux")
    built = repo / "build" / "libs" / wizard.BURP_JAR_NAME

    commands: list[object] = []

    def fake_run(args, **kwargs):
        commands.append(args)
        if args[:2] == ["git", "clone"]:
            (repo / "build" / "libs").mkdir(parents=True)
            (repo / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
            built.write_text("jar", encoding="utf-8")
        return _Proc(0)

    monkeypatch.setattr(wizard.subprocess, "run", fake_run)
    monkeypatch.setattr(wizard, "find_burp_jar", lambda: built if built.is_file() else None)
    console = FakeConsole([])

    ok, jar, error = wizard.ensure_burp_mcp_jar(console=console, status=_status())

    assert ok is True, error
    assert jar == tools / wizard.BURP_JAR_NAME
    assert any(isinstance(cmd, list) and cmd[:2] == ["git", "clone"] for cmd in commands)
    assert any(isinstance(cmd, list) and "embedProxyJar" in cmd for cmd in commands)
    assert "JAVA_HOME" in console.text


def test_ensure_burp_mcp_jar_reports_a_clone_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "BURP_MCP_DIR", tmp_path / "burp-mcp")
    monkeypatch.setattr(wizard, "find_burp_jar", lambda: None)
    monkeypatch.setattr(wizard.shutil, "which", lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.setattr(wizard, "detect_java_path", lambda: "/usr/bin/java")
    monkeypatch.setattr(wizard.subprocess, "run", lambda *_a, **_k: _Proc(128, stderr="boom"))

    ok, jar, error = wizard.ensure_burp_mcp_jar(console=FakeConsole([]), status=_status())

    assert ok is False and jar is None
    assert "git clone failed" in error


def test_ensure_burp_mcp_jar_requires_the_gradle_wrapper(monkeypatch, tmp_path):
    repo = tmp_path / "burp-mcp"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "BURP_MCP_DIR", repo)
    monkeypatch.setattr(wizard, "find_burp_jar", lambda: None)
    monkeypatch.setattr(wizard.shutil, "which", lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.setattr(wizard, "detect_java_path", lambda: "/usr/bin/java")
    monkeypatch.setattr(wizard.platform, "system", lambda: "Linux")

    ok, jar, error = wizard.ensure_burp_mcp_jar(console=FakeConsole([]), status=_status())

    assert ok is False and jar is None
    assert "gradle wrapper missing" in error


# ── MCP reload + launchers ───────────────────────────────────────────


def test_reload_mcp_without_a_manager():
    ui, console = _ui([])
    result = wizard.WizardResult()

    assert wizard._reload_mcp(ui, wizard.VulnClawConfig(), None, result) is False
    assert "No live MCP manager" in console.text


class _FakeRegistry:
    def __init__(self):
        self.registered: list[str] = []

    def register_server(self, name: str) -> None:
        self.registered.append(name)


class _FakeMCPManager:
    def __init__(self, *, attach: bool = True):
        self.config = None
        self.registry = _FakeRegistry()
        self._attach = attach

    def _start_server(self, _name, _server):
        return self._attach


def test_reload_mcp_attaches_enabled_servers():
    ui, console = _ui([])
    config = wizard.VulnClawConfig()
    config = wizard.enable_chrome_devtools(config, browser_url="http://127.0.0.1:9222")
    manager = _FakeMCPManager()

    assert wizard._reload_mcp(ui, config, manager, wizard.WizardResult()) is True
    assert manager.registry.registered == ["chrome-devtools"]
    assert "attached: chrome-devtools" in console.text


def test_reload_mcp_reports_partial_attach():
    ui, console = _ui([])
    config = wizard.enable_chrome_devtools(wizard.VulnClawConfig(), browser_url="http://127.0.0.1:9222")
    manager = _FakeMCPManager(attach=False)

    assert wizard._reload_mcp(ui, config, manager, wizard.WizardResult()) is False
    assert "attach incomplete" in console.text


def test_launch_chrome_debug_reports_spawn_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard.platform, "system", lambda: "Linux")

    def boom(*_args, **_kwargs):
        raise OSError("no chrome")

    monkeypatch.setattr(wizard.subprocess, "Popen", boom)

    assert wizard.launch_chrome_debug("/nope", port=9222, user_data_dir=tmp_path / "p") is False


def test_launch_chrome_debug_spawns_with_remote_debugging(monkeypatch, tmp_path):
    seen: dict = {}
    monkeypatch.setattr(wizard.platform, "system", lambda: "Linux")

    def fake_popen(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(wizard.subprocess, "Popen", fake_popen)

    assert wizard.launch_chrome_debug("/usr/bin/chrome", port=9333, user_data_dir=tmp_path / "p") is True
    assert "--remote-debugging-port=9333" in seen["args"]
    assert seen["kwargs"]["start_new_session"] is True


def test_open_url_and_path_use_the_platform_launcher(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    monkeypatch.setattr(wizard.platform, "system", lambda: "Linux")
    monkeypatch.setattr(wizard.subprocess, "Popen", lambda args: calls.append(args))

    wizard._open_url("https://example.com")
    wizard._open_path(tmp_path)

    assert calls[0] == ["xdg-open", "https://example.com"]
    assert calls[1][0] == "xdg-open"


def test_detect_chrome_path_falls_back_to_path_lookup(monkeypatch):
    monkeypatch.setattr(wizard.platform, "system", lambda: "Linux")
    monkeypatch.setattr(wizard.shutil, "which", lambda name: "/usr/bin/chromium" if name == "chromium" else None)

    assert wizard.detect_chrome_path() == "/usr/bin/chromium"


# ── Whole-wizard runs ────────────────────────────────────────────────


def test_run_setup_wizard_completes_and_writes_the_env(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(wizard, "WIZARD_ENV", tmp_path / "wizard.env")
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "CHROME_PROFILE", tmp_path / "chrome")
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: True)
    monkeypatch.setattr(wizard, "_stage_prereqs", lambda ui, status: status)
    monkeypatch.setattr(wizard, "_stage_llm", lambda ui, config, status, result: (config, status))
    monkeypatch.setattr(wizard, "_stage_language", lambda ui, config, status, result: (config, status))
    monkeypatch.setattr(
        wizard, "_stage_chrome", lambda ui, status, result: (9222, "/usr/bin/chrome", tmp_path / "p", status)
    )
    monkeypatch.setattr(
        wizard, "_stage_chrome_devtools", lambda ui, config, status, port, result: (config, status)
    )
    monkeypatch.setattr(wizard, "_stage_burp", lambda ui, config, status, result: (config, status))
    monkeypatch.setattr(wizard, "_reload_mcp", lambda ui, config, manager, result: True)
    monkeypatch.setattr(wizard, "save_config", lambda _config: None)
    monkeypatch.setattr(wizard, "detect_setup_status", lambda _config=None, **_kwargs: _status())
    monkeypatch.setattr(wizard, "load_config", lambda: wizard.VulnClawConfig())

    result = wizard.run_setup_wizard(console=FakeConsole([]))

    assert result.completed is True
    assert result.restarted_mcp is True
    assert any("Setup complete" in message for message in result.messages)
    env_file = tmp_path / "wizard.env"
    assert env_file.is_file()
    assert "CHROME_PATH=/usr/bin/chrome" in env_file.read_text(encoding="utf-8")


def test_run_setup_wizard_can_be_cancelled(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "_confirm", lambda con, question, default=False: False)
    monkeypatch.setattr(wizard, "detect_setup_status", lambda _config=None, **_kwargs: _status())
    monkeypatch.setattr(wizard, "load_config", lambda: wizard.VulnClawConfig())
    console = FakeConsole([])

    result = wizard.run_setup_wizard(console=console)

    assert result.completed is False
    assert result.messages == ["Setup cancelled."]
    assert "Setup cancelled" not in console.text


def test_run_setup_wizard_handles_keyboard_interrupt(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "detect_setup_status", lambda _config=None, **_kwargs: _status(llm_ready=True))
    monkeypatch.setattr(wizard, "load_config", lambda: wizard.VulnClawConfig())

    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(wizard, "_confirm", interrupt)
    console = FakeConsole([])

    result = wizard.run_setup_wizard(console=console)

    assert result.completed is False
    assert result.messages == ["Cancelled."]
    assert "Wizard cancelled" in console.text


def test_port_open_reports_closed_ports():
    # Port 1 on loopback is never a listening service in CI or on a workstation.
    assert wizard.port_open("127.0.0.1", 1, timeout=0.2) is False


def test_parse_java_major_handles_both_schemes():
    assert wizard._parse_java_major('openjdk version "17.0.9" 2023-10-17') == 17
    assert wizard._parse_java_major('java version "1.8.0_301"') == 8
    assert wizard._parse_java_major("no version here") is None


@pytest.mark.parametrize("system", ["Windows", "Darwin", "Linux"])
def test_clear_never_raises_on_any_platform(monkeypatch, system):
    monkeypatch.setattr(wizard.platform, "system", lambda: system)
    monkeypatch.setattr(wizard.os, "system", lambda _cmd: 0)
    ui = wizard._WizardUi(console=FakeConsole(is_terminal=True))

    ui.clear()
