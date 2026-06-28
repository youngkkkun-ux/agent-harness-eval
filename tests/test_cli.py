"""Tests for the CLI entry points."""
from hermes_eval import cli


TASK_DIR = "task_library"


def test_cmd_list_outputs_tasks(capsys):
    rc = cli.main(["list", "--tasks", TASK_DIR])
    out = capsys.readouterr().out
    assert rc == 0
    assert "mem-001" in out
    assert "con-001" in out


def test_cmd_run_demo_produces_report(capsys, tmp_path):
    db = tmp_path / "eval.db"
    rc = cli.main([
        "run", "--tasks", TASK_DIR, "--task", "ins-003",
        "--demo", "--db", str(db), "--model", "demo-model",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ins-003" in out
    assert db.exists()


def test_cmd_report_after_run(capsys, tmp_path):
    db = tmp_path / "eval.db"
    cli.main(["run", "--tasks", TASK_DIR, "--task", "ins-003", "--demo",
              "--db", str(db), "--model", "demo-model"])
    capsys.readouterr()
    rc = cli.main(["report", "--db", str(db), "--tasks", TASK_DIR])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Harness" in out


def test_unknown_task_errors(capsys, tmp_path):
    rc = cli.main(["run", "--tasks", TASK_DIR, "--task", "does-not-exist",
                   "--demo", "--db", str(tmp_path / "x.db")])
    assert rc != 0
