"""Tests for the swarmledger CLI (hermetic: HOME redirected to a tmp dir)."""

import json
import sqlite3
from argparse import Namespace
from pathlib import Path

import pytest

from swarmledger import cli
from swarmledger.core.node import EventType
from swarmledger.storage.engine import StorageEngine


@pytest.fixture()
def home_db(tmp_path, monkeypatch):
    """Redirect Path.home() so the CLI's default DB lives in a tmp dir."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path / ".swarmledger" / "ledger.db"


def _seed(home_db):
    engine = StorageEngine()  # uses patched home
    n1 = engine.append_node("span_cli", EventType.PROMPT, "user", {"prompt": "seed"})
    n2 = engine.append_node("span_cli", EventType.COMMIT, "hv", {"status": "COMMITTED"}, [n1.node_id])
    return engine, n1, n2


def test_help_lists_subcommands(capsys, monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["swarmledger", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("log", "tree", "trace", "audit"):
        assert cmd in out


def test_version_flag(capsys, monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["swarmledger", "--version"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert "swarmledger" in capsys.readouterr().out


def test_log_empty_ledger(home_db, capsys):
    assert cli.cmd_log(Namespace(span=None, limit=20)) == 0
    assert "No ledger spans recorded" in capsys.readouterr().out


def test_log_span(home_db, capsys):
    _, n1, _ = _seed(home_db)
    assert cli.cmd_log(Namespace(span="span_cli", limit=20)) == 0
    out = capsys.readouterr().out
    assert "SWARMLEDGER NODE LOG" in out
    assert n1.node_id in out


def test_log_defaults_to_latest_span(home_db, capsys):
    _seed(home_db)
    assert cli.cmd_log(Namespace(span=None, limit=1)) == 0
    out = capsys.readouterr().out
    assert "(2 records)" in out  # header counts total; --limit only trims displayed rows


def test_tree_renders_span(home_db, capsys):
    _, n1, _ = _seed(home_db)
    assert cli.cmd_tree(Namespace(span_id="span_cli")) == 0
    out = capsys.readouterr().out
    assert "SWARMLEDGER MERKLE DAG TRACE" in out
    assert n1.node_id[:8] in out


def test_trace_node(home_db, capsys):
    _, n1, _ = _seed(home_db)
    assert cli.cmd_trace(Namespace(node_id=n1.node_id)) == 0
    out = capsys.readouterr().out
    assert "SWARMLEDGER NODE TRACE" in out
    assert n1.node_id in out


def test_trace_missing_node_returns_1(home_db, capsys):
    assert cli.cmd_trace(Namespace(node_id="nod_missing")) == 1
    assert "not found" in capsys.readouterr().out


def test_audit_span_passes(home_db, capsys):
    _seed(home_db)
    assert cli.cmd_audit(Namespace(span="span_cli")) == 0
    assert "PASSED" in capsys.readouterr().out


def test_audit_span_failure_reports_details_not_crash(home_db, capsys):
    """Regression: cmd_audit used v.message (AttributeError); must use v.details."""
    _, n1, _ = _seed(home_db)
    conn = sqlite3.connect(str(home_db))
    conn.execute(
        "UPDATE ledger_nodes SET payload_json = ? WHERE node_id = ?;",
        (json.dumps({"prompt": "evil"}), n1.node_id),
    )
    conn.commit()
    conn.close()

    assert cli.cmd_audit(Namespace(span="span_cli")) == 1
    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "TamperMismatchError" in out


def test_audit_all_spans(home_db, capsys):
    """Regression: cmd_audit called non-existent auditor.audit_all()."""
    _seed(home_db)
    assert cli.cmd_audit(Namespace(span=None)) == 0
    out = capsys.readouterr().out
    assert "ALL SPANS PASSED" in out


def test_audit_all_spans_empty_ledger(home_db, capsys):
    assert cli.cmd_audit(Namespace(span=None)) == 0
    assert "Empty ledger" in capsys.readouterr().out


def test_audit_all_spans_with_corruption_returns_1(home_db, capsys):
    _, n1, _ = _seed(home_db)
    conn = sqlite3.connect(str(home_db))
    conn.execute("UPDATE ledger_nodes SET node_hash = ? WHERE node_id = ?;", ("f" * 64, n1.node_id))
    conn.commit()
    conn.close()

    assert cli.cmd_audit(Namespace(span=None)) == 1
    assert "corrupted" in capsys.readouterr().out
