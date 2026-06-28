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


def test_cmd_learn(capsys, tmp_path):
    rc = cli.main(["learn", "--tasks", TASK_DIR, "--task", "mem-001",
                   "--rounds", "3", "--demo", "--db", str(tmp_path / "l.db")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "学习曲线" in out
    assert "Run3" in out
    assert "学习循环专项指标" in out          # PRD 3.3 metrics block
    assert "skill_creation_rate" in out


def test_cmd_consistency(capsys, tmp_path):
    rc = cli.main(["consistency", "--tasks", TASK_DIR, "--task", "mem-001",
                   "--repeats", "3", "--demo", "--db", str(tmp_path / "co.db")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "一致性" in out
    assert "mem-001" in out


def test_cmd_compare(capsys, tmp_path):
    rc = cli.main(["compare", "--tasks", TASK_DIR, "--layer", "instructions",
                   "--field", "skill_enabled", "--demo", "--db", str(tmp_path / "c.db")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "对比" in out
    assert "skill_enabled=on" in out
