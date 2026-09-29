"""Tests for CryptographicAuditor in swarmledger.storage.auditor."""

import json
import sqlite3

import pytest

from swarmledger.core.node import EventType
from swarmledger.storage.auditor import (
    AuditReport,
    AuditViolation,
    CryptographicAuditor,
)
from swarmledger.storage.engine import StorageEngine


@pytest.fixture()
def engine(tmp_path):
    return StorageEngine(db_path=tmp_path / "ledger.db")


@pytest.fixture()
def auditor(engine):
    return CryptographicAuditor(engine)


def _clean_span(engine, span_id="span_ok"):
    n1 = engine.append_node(span_id, EventType.PROMPT, "user", {"msg": "start"})
    n2 = engine.append_node(span_id, EventType.MUTATE, "agent", {"file": "a.py"}, [n1.node_id])
    n3 = engine.append_node(span_id, EventType.COMMIT, "hv", {"status": "COMMITTED"}, [n2.node_id])
    return n1, n2, n3


def test_empty_span_passes_with_zero_nodes(auditor):
    report = auditor.verify_span("span_empty")
    assert report.passed is True
    assert report.verified_nodes == 0
    assert report.violations == []


def test_clean_span_passes(auditor, engine):
    _clean_span(engine)
    report = auditor.verify_span("span_ok")
    assert report.passed is True
    assert report.verified_nodes == 3
    assert isinstance(report, AuditReport)


def test_payload_tampering_detected(auditor, engine, tmp_path):
    n1, _, _ = _clean_span(engine)
    db_path = tmp_path / "ledger.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE ledger_nodes SET payload_json = ? WHERE node_id = ?;",
        (json.dumps({"msg": "hacked"}), n1.node_id),
    )
    conn.commit()
    conn.close()

    report = auditor.verify_span("span_ok")
    assert report.passed is False
    assert len(report.violations) == 1
    v = report.violations[0]
    assert v.node_id == n1.node_id
    assert v.error_type == "TamperMismatchError"
    assert v.violation_type == "TAMPER_MISMATCH"
    assert isinstance(v, AuditViolation)


def test_node_hash_tampering_detected(auditor, engine, tmp_path):
    n1, _, _ = _clean_span(engine)
    db_path = tmp_path / "ledger.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE ledger_nodes SET node_hash = ? WHERE node_id = ?;",
        ("0" * 64, n1.node_id),
    )
    conn.commit()
    conn.close()

    report = auditor.verify_span("span_ok")
    assert report.passed is False
    assert any(v.violation_type == "TAMPER_MISMATCH" for v in report.violations)


def test_poisoned_lamport_chain_detected(auditor, engine, tmp_path):
    _, n2, _ = _clean_span(engine)
    db_path = tmp_path / "ledger.db"
    conn = sqlite3.connect(str(db_path))
    # Forge a lamport seq detached from Genesis topological depth (2 -> 99)
    conn.execute(
        "UPDATE ledger_nodes SET lamport_seq = 99 WHERE node_id = ?;", (n2.node_id,)
    )
    conn.commit()
    conn.close()

    report = auditor.verify_span("span_ok")
    assert report.passed is False
    poisoned = [v for v in report.violations if v.violation_type == "POISONED_LAMPORT_CHAIN"]
    # Forging n2's seq to 99 poisons n2 AND its child n3, whose expected depth
    # is derived from the (forged) claimed parent sequence.
    assert len(poisoned) == 2
    forged = [v for v in poisoned if v.node_id == n2.node_id][0]
    assert "99" in forged.details


def test_violation_type_defaults_to_error_type():
    v = AuditViolation(node_id="n", error_type="SomeError", details="d")
    assert v.violation_type == "SomeError"
