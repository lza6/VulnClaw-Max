"""Pure solver helper functions."""

from __future__ import annotations

from vulnclaw.agent.solver import (
    _after_marker,
    _cited_evidence_ids,
    _first_reason_line,
    _goal_wants_flag,
    _has_marker,
    _is_observation_only_turn,
    extract_json,
)


def test_json_and_markers():
    assert extract_json('prefix {"a": 1} suffix') == {"a": 1}
    assert extract_json("no json") is None
    assert extract_json("[1,2]") is None
    assert _cited_evidence_ids("see e001 e002 e001") == ["e001", "e002"]
    assert _after_marker("abc: x", ("abc:",)) == "x"
    assert _after_marker("abc", ("z",)) == ""
    assert _has_marker("abc", ("a",)) is True
    assert _first_reason_line("<thinking>no</thinking>\nreason") == "reason"
    assert _goal_wants_flag("capture the flag") is True
    assert _goal_wants_flag("scan a site") is False


def test_observation_only_turn():
    assert _is_observation_only_turn(["evidence_list"], 0) is True
    assert _is_observation_only_turn(["nmap_scan"], 1) is False
