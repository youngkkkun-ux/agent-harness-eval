"""Result Store: SQLite + FTS5 persistence (PRD 5.4)."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import EvalResult, RunConfig, RunRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS eval_configs (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    config_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    config_id       TEXT NOT NULL,
    session_id      TEXT,
    response        TEXT,
    record_json     TEXT NOT NULL,
    tool_calls_json TEXT,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    duration_sec    REAL,
    error           TEXT,
    started_at      TEXT,
    ended_at        TEXT
);
CREATE TABLE IF NOT EXISTS eval_results (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL,
    task_id             TEXT NOT NULL,
    overall_score       REAL NOT NULL,
    passed              INTEGER NOT NULL,
    result_json         TEXT NOT NULL,
    critique            TEXT,
    actionable_feedback TEXT,
    evaluated_at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learning_curves (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL,
    config_id   TEXT NOT NULL,
    run_number  INTEGER NOT NULL,
    run_id      TEXT NOT NULL,
    score       REAL,                   -- nullable: failed rounds are breakpoints (PRD 6.3)
    recorded_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS runs_fts USING fts5(
    id UNINDEXED,
    task_id,
    response
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResultStore:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")  # PRD 6.3 concurrency
        self.conn.execute("PRAGMA busy_timeout=10000")
        self._init_schema()

    def _init_schema(self):
        # PRD 6.3: corrupt DB -> rebuild.
        if not self.integrity_ok():
            self.conn.close()
            backup = Path(self.path).with_suffix(".corrupt")
            Path(self.path).rename(backup)
            self.conn = sqlite3.connect(self.path)
            self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def integrity_ok(self) -> bool:
        try:
            row = self.conn.execute("PRAGMA integrity_check").fetchone()
            return row is not None and row[0] == "ok"
        except sqlite3.DatabaseError:
            return False

    # ---------- configs ----------

    def save_config(self, name: str, config: RunConfig, *,
                    description: str = "", config_id: Optional[str] = None) -> str:
        cid = config_id or uuid.uuid4().hex
        self.conn.execute(
            "INSERT OR REPLACE INTO eval_configs(id,name,description,config_json,created_at)"
            " VALUES(?,?,?,?,?)",
            (cid, name, description, config.model_dump_json(), _now()),
        )
        self.conn.commit()
        return cid

    # ---------- runs ----------

    def save_run(self, run: RunRecord, config_id: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO runs(id,task_id,config_id,session_id,response,"
            "record_json,tool_calls_json,input_tokens,output_tokens,duration_sec,"
            "error,started_at,ended_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run.run_id, run.task_id, config_id, run.session_id, run.response,
                run.model_dump_json(),
                json.dumps([tc.model_dump() for tc in run.tool_calls]),
                run.input_tokens, run.output_tokens, run.duration_seconds,
                run.error,
                run.started_at.isoformat() if run.started_at else None,
                run.ended_at.isoformat() if run.ended_at else None,
            ),
        )
        self.conn.execute("DELETE FROM runs_fts WHERE id=?", (run.run_id,))
        self.conn.execute(
            "INSERT INTO runs_fts(id,task_id,response) VALUES(?,?,?)",
            (run.run_id, run.task_id, run.response or ""),
        )
        self.conn.commit()

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        row = self.conn.execute(
            "SELECT record_json FROM runs WHERE id=?", (run_id,)
        ).fetchone()
        return RunRecord(**json.loads(row["record_json"])) if row else None

    def search_runs(self, query: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT id FROM runs_fts WHERE runs_fts MATCH ?", (query,)
        ).fetchall()
        return [r["id"] for r in rows]

    # ---------- results ----------

    def save_result(self, result: EvalResult):
        self.conn.execute(
            "INSERT OR REPLACE INTO eval_results(id,run_id,task_id,overall_score,"
            "passed,result_json,critique,actionable_feedback,evaluated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex, result.run_id, result.task_id,
                result.overall_score, int(result.passed),
                result.model_dump_json(), result.critique,
                result.actionable_feedback,
                (result.evaluated_at or datetime.now(timezone.utc)).isoformat(),
            ),
        )
        self.conn.commit()

    def get_result(self, run_id: str) -> Optional[EvalResult]:
        row = self.conn.execute(
            "SELECT result_json FROM eval_results WHERE run_id=? ORDER BY evaluated_at DESC",
            (run_id,),
        ).fetchone()
        return EvalResult(**json.loads(row["result_json"])) if row else None

    def all_results(self) -> list[EvalResult]:
        rows = self.conn.execute("SELECT result_json FROM eval_results").fetchall()
        return [EvalResult(**json.loads(r["result_json"])) for r in rows]

    # ---------- learning curves ----------

    def record_learning_point(self, task_id: str, config_id: str, *,
                              run_number: int, run_id: str, score: Optional[float]):
        self.conn.execute(
            "INSERT INTO learning_curves(task_id,config_id,run_number,run_id,score,"
            "recorded_at) VALUES(?,?,?,?,?,?)",
            (task_id, config_id, run_number, run_id, score, _now()),
        )
        self.conn.commit()

    def get_learning_curve(self, task_id: str, config_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT run_number,run_id,score FROM learning_curves"
            " WHERE task_id=? AND config_id=? ORDER BY run_number",
            (task_id, config_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
