"""Builtin tool helpers that gate execution: AST guard, nmap parsing, probes."""

from __future__ import annotations

import pytest

from vulnclaw.agent import builtin_tools

# ── AST sandbox-bypass guard ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("exec('import os; os.system(\"id\")')", "exec/eval/compile"),
        ("eval('1+1')", "exec/eval/compile"),
        ("compile('x=1', '<s>', 'exec')", "exec/eval/compile"),
        ("import importlib\nimportlib.import_module('os')", "importlib.import_module"),
        ("__import__('socket')", "__import__"),
        ("getattr(__builtins__, 'open')", "getattr on __builtins__"),
        ("import socket as s\ngetattr(s, 'socket')", "getattr on module 'socket'"),
        ("x = __builtins__", "__builtins__ access"),
        ("import os\nos.__builtins__", "__builtins__ access"),
    ],
)
def test_ast_guard_flags_bypass_patterns(code, expected):
    reason = builtin_tools._ast_check_sandbox_bypass(code)

    assert reason is not None
    assert expected in reason


@pytest.mark.parametrize(
    "code",
    [
        "print('hello')",
        "import json\ndata = json.loads('{}')",
        "def f(x):\n    return x + 1",
        "this is not python at all (",
    ],
)
def test_ast_guard_allows_ordinary_code(code):
    assert builtin_tools._ast_check_sandbox_bypass(code) is None


# ── nmap output parsing ──────────────────────────────────────────────

_NMAP_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.1.2.3" addrtype="ipv4"/>
    <hostname type="user" name="box.local"/>
    <ports>
      <port protocol="tcp" portid="443">
        <state state="open"/>
        <service name="https" product="nginx" version="1.24" tunnel="ssl"/>
        <script id="ssl-cert" output="self signed"/>
      </port>
    </ports>
  </host>
  <runstats><finished elapsed="3.20" summary="Nmap done"/></runstats>
</nmaprun>
"""


def test_parse_nmap_xml_renders_hosts_ports_and_scripts():
    public_xml = _NMAP_XML.replace("10.1.2.3", "203.0.113.9")
    text = builtin_tools.parse_nmap_xml(public_xml, "203.0.113.9")

    assert "nmap 扫描结果 — 203.0.113.9" in text
    assert "203.0.113.9 (box.local) — up" in text
    assert "TCP   443/s" in text
    assert "nginx 1.24" in text
    assert "ssl-cert: self signed" in text
    assert "完成时间: 3.20s | Nmap done" in text


def test_parse_nmap_xml_flags_reserved_addresses():
    text = builtin_tools.parse_nmap_xml(_NMAP_XML, "10.1.2.3")

    assert "保留地址" in text


def test_parse_nmap_xml_passes_through_non_xml_output():
    text = builtin_tools.parse_nmap_xml("nmap: command not found", "example.com")

    assert text.startswith("nmap 原始输出:")
    assert "command not found" in text


def test_parse_nmap_xml_tolerates_broken_xml():
    text = builtin_tools.parse_nmap_xml("<nmaprun><host>", "example.com")

    assert text.startswith("nmap 原始输出:")


def test_parse_nmap_xml_handles_an_empty_document():
    text = builtin_tools.parse_nmap_xml("<nmaprun></nmaprun>", "example.com")

    assert text.startswith("nmap 扫描结果 — example.com")
    assert "完成时间" not in text


# ── parser/filter differential candidates ────────────────────────────

_SERIALIZED = 'O:8:"stdClass":1:{s:1:"a";s:1:"b";}'


def test_runtime_diff_candidates_generates_length_mutations():
    candidates = builtin_tools._runtime_diff_candidates(
        {"payload": _SERIALIZED, "mutations": ["signed_lengths", "uppercase_string_type"]}
    )
    labels = [label for label, _value in candidates]

    assert labels[0] == "original"
    assert "signed object/class lengths" in labels
    assert "uppercase string token" in labels
    # Mutations must actually change the payload.
    assert all(value != _SERIALIZED for label, value in candidates[1:])


def test_runtime_diff_candidates_accepts_a_single_mutation_string():
    candidates = builtin_tools._runtime_diff_candidates(
        {"payload": _SERIALIZED, "mutations": "leading_zero_lengths"}
    )

    assert any(label == "zero-padded object/class lengths" for label, _ in candidates)


def test_runtime_diff_candidates_merges_and_dedupes_explicit_candidates():
    candidates = builtin_tools._runtime_diff_candidates(
        {
            "payload": "abc",
            "mutations": [],
            "candidates": [
                {"payload": "abc", "label": "duplicate"},
                {"value": "xyz"},
                "plain",
                {"payload": ""},
            ],
        }
    )

    assert candidates == [("original", "abc"), ("candidate 2", "xyz"), ("candidate 3", "plain")]


def test_runtime_diff_candidates_is_empty_without_a_payload():
    assert builtin_tools._runtime_diff_candidates({}) == []
