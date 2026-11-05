"""ContextManager message/vault helpers."""

from __future__ import annotations

from vulnclaw.agent.context import ContextManager, PentestPhase, SessionState
from vulnclaw.agent.memory import MemoryStore


def _manager(tmp_path):
    return ContextManager(
        max_history=3,
        max_tokens=50,
        search_max_chars=200,
        memory_store=MemoryStore(store_dir=tmp_path / "memory"),
    )


def test_message_lifecycle(tmp_path):
    manager = _manager(tmp_path)
    manager.add_user_message("hello")
    manager.add_assistant_message("world")
    manager.add_system_message("system")
    manager.add_message({"role": "user", "content": "x" * 500})
    assert manager.get_messages()
    manager.trim_messages(max_messages=1)
    assert manager.get_messages()
    manager.compact_messages(max_recent=1)
    manager.reset()
    assert manager.get_messages() == []


def test_vault_and_state_helpers(tmp_path):
    manager = _manager(tmp_path)
    manager.vault_output_dir = tmp_path
    assert manager.ensure_vault() is not None
    state = SessionState(target="example.com")
    state.advance_phase(PentestPhase.RECON)
    assert state.phase == PentestPhase.RECON
    state.set_active_skill_selection({"skill": "x"})
    state.record_loaded_reference("x", "ref")
    assert isinstance(state.get_constraints_prompt_block(), str)
