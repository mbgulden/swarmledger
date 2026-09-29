"""Tests for the ecosystem bridges in swarmledger.bridges (hermetic temp DBs)."""

import pytest

from swarmledger.bridges.gate_bridge import SwarmgateLedgerBridge
from swarmledger.bridges.lock_bridge import SwarmlockLedgerBridge
from swarmledger.bridges.proof_bridge import SwarmproofLedgerBridge
from swarmledger.bridges.saga_bridge import SwarmsagaLedgerBridge
from swarmledger.core.node import EventType
from swarmledger.storage.auditor import CryptographicAuditor
from swarmledger.storage.engine import StorageEngine


@pytest.fixture()
def engine(tmp_path):
    return StorageEngine(db_path=tmp_path / "ledger.db")


def test_lock_bridge_records_lease_acquired(engine):
    bridge = SwarmlockLedgerBridge(engine)
    n = bridge.record_lease_acquired("span_lock", "file:auth.py", "X", 42, "agent_1", tx_id="tx1")
    assert n.event_type == EventType.LEASE
    assert n.payload["action"] == "LEASE_ACQUIRED"
    assert n.payload["resource"] == "file:auth.py"
    assert n.payload["mode"] == "X"
    assert n.payload["fencing_token"] == 42
    assert n.payload["tx_id"] == "tx1"
    assert engine.get_node(n.node_id) is not None


def test_lock_bridge_records_lease_released(engine):
    bridge = SwarmlockLedgerBridge(engine)
    n = bridge.record_lease_released("span_lock", "file:auth.py", "agent_1", committed=False)
    assert n.event_type == EventType.LEASE
    assert n.payload["action"] == "LEASE_RELEASED"
    assert n.payload["committed"] is False


def test_proof_bridge_records_proof(engine):
    bridge = SwarmproofLedgerBridge(engine)
    n = bridge.record_proof(
        "span_proof", "prf_9", "auth.py", "abc123", ["oracle_ast", "oracle_exec"], "proof_bot"
    )
    assert n.event_type == EventType.PROOF
    assert n.payload["proof_id"] == "prf_9"
    assert n.payload["target_path"] == "auth.py"
    assert n.payload["ast_checksum"] == "abc123"
    assert n.payload["oracles_passed"] == ["oracle_ast", "oracle_exec"]
    assert n.payload["status"] == "VERIFIED"


def test_gate_bridge_records_decision(engine):
    bridge = SwarmgateLedgerBridge(engine)
    n = bridge.record_decision(
        "span_gate", "dec_1", "file:auth.py", 0.75, "TIER_2", "gate_bot", proof_id="prf_9"
    )
    assert n.event_type == EventType.GATE
    assert n.payload["decision_id"] == "dec_1"
    assert n.payload["escalation_score"] == 0.75
    assert n.payload["tier"] == "TIER_2"
    assert n.payload["proof_id"] == "prf_9"


def test_saga_bridge_records_full_lifecycle(engine):
    bridge = SwarmsagaLedgerBridge(engine)
    step = bridge.record_step("span_saga", "tx_1", "charge_card", "DONE", "agent_1", is_pivot=True)
    assert step.event_type == EventType.SAGA_STEP
    assert step.payload["step_name"] == "charge_card"
    assert step.payload["state"] == "DONE"
    assert step.payload["is_pivot"] is True

    commit = bridge.record_final_commit("span_saga", "tx_1", "agent_1", [step.node_id])
    assert commit.event_type == EventType.COMMIT
    assert commit.payload["status"] == "COMMITTED"
    assert commit.parent_node_ids == [step.node_id]

    abort = bridge.record_abort("span_saga2", "tx_2", "card declined", "agent_1")
    assert abort.event_type == EventType.ABORT
    assert abort.payload["status"] == "ABORTED"
    assert abort.payload["reason"] == "card declined"


def test_bridges_produce_auditable_span(engine):
    lock = SwarmlockLedgerBridge(engine)
    proof = SwarmproofLedgerBridge(engine)
    gate = SwarmgateLedgerBridge(engine)
    saga = SwarmsagaLedgerBridge(engine)

    n1 = lock.record_lease_acquired("span_eco", "file:auth.py", "X", 1, "a1")
    n2 = proof.record_proof("span_eco", "prf_1", "auth.py", "ck", ["o1"], "a2", [n1.node_id])
    n3 = gate.record_decision("span_eco", "d1", "file:auth.py", 0.1, "TIER_1", "a3", parent_node_ids=[n2.node_id])
    saga.record_final_commit("span_eco", "tx", "a4", [n3.node_id])

    report = CryptographicAuditor(engine).verify_span("span_eco")
    assert report.passed is True
    assert report.verified_nodes == 4
