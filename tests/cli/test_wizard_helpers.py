"""Pure helpers from the first-run wizard."""

from __future__ import annotations

from vulnclaw.cli import wizard


def test_plan_from_status():
    status = wizard.SetupStatus(llm_ready=True, language="zh", burp_enabled=True)
    plan = wizard.plan_from_status(status)
    assert "LLM credentials" in plan["ready"]
    assert "Burp MCP" in plan["todo"]
    assert any("language" in item for item in plan["ready"])


def test_java_helpers(monkeypatch, tmp_path):
    assert wizard._parse_java_major('openjdk version "17.0.9"') == 17
    assert wizard._parse_java_major('java version "1.8.0_301"') == 8
    assert wizard._parse_java_major("no version") is None

    java_bin = tmp_path / "jdk" / "bin" / "java.exe"
    java_bin.parent.mkdir(parents=True)
    java_bin.write_text("", encoding="utf-8")
    assert wizard.java_home_from_binary(str(java_bin)) == str(tmp_path / "jdk")

    monkeypatch.setattr(wizard, "_java_major_version", lambda _bin: 17)
    assert wizard.java_meets_minimum("java") is True
    monkeypatch.setattr(wizard, "_java_major_version", lambda _bin: None)
    assert wizard.java_meets_minimum("java") is False


def test_detect_setup_status(monkeypatch, tmp_path):
    from vulnclaw.config.schema import VulnClawConfig

    config = VulnClawConfig()
    monkeypatch.setattr(wizard, "detect_chrome_path", lambda: "/chrome")
    monkeypatch.setattr(wizard, "port_open", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(wizard, "find_burp_jar", lambda: None)
    monkeypatch.setattr(wizard, "detect_java_path", lambda: None)
    monkeypatch.setattr(wizard.shutil, "which", lambda _name: None)

    status = wizard.detect_setup_status(config, debug_port=9999)

    assert status.chrome_path == "/chrome"
    assert status.debug_port == 9999
    assert status.chrome_debug_live is False
    assert status.java is None


def test_find_burp_jar_and_write_env(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "BURP_MCP_DIR", tmp_path / "burp")
    monkeypatch.setattr(wizard, "BURP_JAR_NAME", "burp.jar")
    assert wizard.find_burp_jar() is None
    jar = tmp_path / "tools" / "burp.jar"
    jar.parent.mkdir(parents=True)
    jar.write_text("x", encoding="utf-8")
    assert wizard.find_burp_jar() == jar

    env_file = tmp_path / "wizard.env"
    monkeypatch.setattr(wizard, "WIZARD_ENV", env_file)
    wizard._write_wizard_env({"JAVA_HOME": "/jdk", "NONE": None})
    wizard._write_wizard_env({"CHROME": "/chrome"})
    text = env_file.read_text(encoding="utf-8")
    assert "JAVA_HOME=/jdk" in text
    assert "CHROME=/chrome" in text


def test_port_open_closed_port():
    assert wizard.port_open("127.0.0.1", 9, timeout=0.1) is False
