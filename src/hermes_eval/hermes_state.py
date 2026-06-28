"""Gray-box reader for real ~/.hermes/ state (PRD 5.2.1 method C, 5.2.3).

Produces the snapshot dict consumed by RuleEvaluator / StateEvaluator:
    {available, memory_md, memory_md_chars, user_md, skills_created, memory_writes,
     prior_session_linked}

Reads are defensive: a missing home returns {"available": False}, and any
single unreadable file is skipped without failing the whole snapshot.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

MEMORY_BUDGET_CHARS = 2200  # PRD 6.4


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):  # PRD 6.2: skip bad files
        return ""


class HermesStateReader:
    def __init__(self, home: Path | str):
        self.home = Path(home)

    def _skills(self) -> list[str]:
        skills_dir = self.home / "skills"
        if not skills_dir.is_dir():
            return []
        names = []
        for entry in sorted(skills_dir.iterdir()):
            if entry.name.startswith("."):
                continue
            names.append(entry.stem if entry.is_file() else entry.name)
        return names

    def _session_linked(self, session_id: Optional[str]) -> bool:
        if not session_id:
            return False
        db = self.home / "sessions" / "sessions.db"
        if not db.is_file():
            return False
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                row = conn.execute(
                    "SELECT parent_id FROM sessions WHERE id=?", (session_id,)
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            return False
        return bool(row and row[0])

    def snapshot(self, session_id: Optional[str] = None) -> dict:
        if not self.home.is_dir():
            return {"available": False}

        memory_md = _read_text(self.home / "memory.md")
        user_md = _read_text(self.home / "user.md")

        writes = [
            line.strip()
            for line in (memory_md + "\n" + user_md).splitlines()
            if line.strip()
        ]

        return {
            "available": True,
            "memory_md": memory_md,
            "memory_md_chars": len(memory_md),
            "user_md": user_md,
            "skills_created": self._skills(),
            "memory_writes": writes,
            "prior_session_linked": self._session_linked(session_id),
        }
