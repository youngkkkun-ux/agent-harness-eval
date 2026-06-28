"""Tests for reading real ~/.hermes/ state (PRD 5.2.1 method C / 5.2.3)."""
import sqlite3

from hermes_eval.hermes_state import HermesStateReader, MEMORY_BUDGET_CHARS


def test_missing_home_unavailable(tmp_path):
    snap = HermesStateReader(tmp_path / "nope").snapshot()
    assert snap == {"available": False}


def test_reads_memory_and_skills(tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "memory.md").write_text("user prefers httpx over requests\n", encoding="utf-8")
    skills = home / "skills"
    (skills / "use_httpx").mkdir(parents=True)
    (skills / "use_httpx" / "SKILL.md").write_text("# use httpx", encoding="utf-8")
    (skills / "lint_python").mkdir()

    snap = HermesStateReader(home).snapshot()
    assert snap["available"] is True
    assert "httpx" in snap["memory_md"]
    assert snap["memory_md_chars"] == len("user prefers httpx over requests\n")
    assert set(snap["skills_created"]) == {"use_httpx", "lint_python"}
    assert any("httpx" in w for w in snap["memory_writes"])


def test_includes_user_md_in_memory_writes(tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "user.md").write_text("likes golang\n", encoding="utf-8")
    snap = HermesStateReader(home).snapshot()
    assert any("golang" in w for w in snap["memory_writes"])


def test_budget_chars_reported(tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "memory.md").write_text("x" * (MEMORY_BUDGET_CHARS + 100), encoding="utf-8")
    snap = HermesStateReader(home).snapshot()
    assert snap["memory_md_chars"] > MEMORY_BUDGET_CHARS


def test_session_link_from_sqlite(tmp_path):
    home = tmp_path / ".hermes"
    (home / "sessions").mkdir(parents=True)
    db = home / "sessions" / "sessions.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sessions (id TEXT, parent_id TEXT)")
    conn.execute("INSERT INTO sessions VALUES ('s2', 's1')")
    conn.commit()
    conn.close()
    snap = HermesStateReader(home).snapshot(session_id="s2")
    assert snap["prior_session_linked"] is True


def test_encoding_error_skipped(tmp_path):
    # PRD 6.2: bad encoding -> skip file, stay available
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "memory.md").write_bytes(b"\xff\xfe bad bytes")
    snap = HermesStateReader(home).snapshot()
    assert snap["available"] is True  # does not crash
