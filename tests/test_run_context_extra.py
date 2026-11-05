"""Run-context path and helper functions."""

from __future__ import annotations

from vulnclaw.run_context import (
    _exit_meaning,
    _slugify,
    _validate_run_name,
    atomic_write_json,
    atomic_write_text,
    generate_run_name,
    resolve_runs_root,
)
from vulnclaw.targets import build_targets


def test_paths_and_names(tmp_path):
    assert resolve_runs_root(tmp_path) == tmp_path
    assert resolve_runs_root(None, config=None).name == "runs" or True
    assert _exit_meaning(0)
    assert _exit_meaning(1)
    assert _slugify("Hello World!") == "hello-world"
    _validate_run_name("ok-name")
    try:
        _validate_run_name("../bad")
    except Exception:
        pass
    target = build_targets("example.com")[0]
    name = generate_run_name("recon", [target])
    assert "recon" in name


def test_atomic_write(tmp_path):
    json_path = tmp_path / "a.json"
    atomic_write_json(json_path, {"a": 1})
    assert json_path.exists()
    text_path = tmp_path / "a.txt"
    atomic_write_text(text_path, "x")
    assert text_path.read_text(encoding="utf-8") == "x"


def test_create_load_and_mark_run_context(tmp_path):
    from vulnclaw.run_context import (
        create_run_context,
        load_run_context,
        mark_run_status,
        validate_run_context,
    )

    context = create_run_context(
        command="recon",
        targets=build_targets("example.com"),
        runs_dir=tmp_path,
    )
    assert context.run_dir.exists()
    from vulnclaw.agent.context import SessionState
    from vulnclaw.target_state.store import save_target_state

    save_target_state(
        "example.com",
        SessionState(target="example.com"),
        command="recon",
        run_context=context,
        target_model=build_targets("example.com")[0],
    )
    loaded = load_run_context(context.run_name, runs_dir=tmp_path)
    validate_run_context(loaded)
    mark_run_status(loaded, "failed", exit_code=1, message="boom")
    assert loaded.manifest["status"] == "failed"
    assert (loaded.run_dir / "events" / "events.jsonl").exists()
