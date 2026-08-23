"""
Hermetic Test Suite for SwarmLedger Cryptographic Merkle DAG & Causal Provenance.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
import pytest

from swarmledger.core.canonical import canonicalize
from swarmledger.core.hasher import MerkleHasher
from swarmledger.core.node import EventType, LedgerNode
from swarmledger.distiller.projector import CausalProjector
from swarmledger.distiller.visualizer import ANSIVisualizer
from swarmledger.storage.auditor import CryptographicAuditor
from swarmledger.storage.engine import StorageEngine


def test_rfc8785_canonical_serialization_invariance():
    # 1. Unordered dictionary with nested structures and floats
    payload_a = {
        "z_key": 42,
        "a_key": "test string",
        "nested": {
            "num": 3.14159,
            "b_list": [3, 2, 1],
            "flag": True
        }
    }
    payload_b = {
        "nested": {
            "flag": True,
            "num": 3.14159,
            "b_list": [3, 2, 1]
        },
        "a_key": "test string",
        "z_key": 42
    }

    bytes_a = canonicalize(payload_a)
    bytes_b = canonicalize(payload_b)

    # Must produce identical canonical bytes
    assert bytes_a == bytes_b
    assert b": " not in bytes_a  # No delimiter whitespace
    assert b", " not in bytes_a
    assert bytes_a.startswith(b'{"a_key":"test string"')


def test_multi_parent_dag_and_lamport_clock():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "ledger.db"
        engine = StorageEngine(db_path=db_path)

        span_id = "span_workflow_1"

        # 1. Root Prompt
        root = engine.append_node(
            span_id=span_id,
            event_type=EventType.PROMPT,
            agent_id="human_user",
            payload={"prompt": "Refactor auth logic"}
        )
        assert root.lamport_seq == 1
        assert root.parent_node_ids == []

        # 2. Parallel Branch A: Agent 1 Leases Auth
        branch_a = engine.append_node(
            span_id=span_id,
            event_type=EventType.LEASE,
            agent_id="agent_1",
            payload={"resource": "file:auth.py", "mode": "X"},
            parent_node_ids=[root.node_id]
        )
        assert branch_a.lamport_seq == 2

        # 3. Parallel Branch B: Agent 2 Leases Tests
        branch_b = engine.append_node(
            span_id=span_id,
            event_type=EventType.LEASE,
            agent_id="agent_2",
            payload={"resource": "file:tests.py", "mode": "X"},
            parent_node_ids=[root.node_id]
        )
        assert branch_b.lamport_seq == 2

        # 4. Multi-Parent Join Node: Commit Barrier
        join_node = engine.append_node(
            span_id=span_id,
            event_type=EventType.COMMIT,
            agent_id="hypervisor",
            payload={"action": "MERGE_BRANCHES"},
            parent_node_ids=[branch_a.node_id, branch_b.node_id]
        )
        assert join_node.lamport_seq == 3
        assert set(join_node.parent_node_ids) == {branch_a.node_id, branch_b.node_id}

        # Verify integrity
        auditor = CryptographicAuditor(engine)
        report = auditor.verify_span(span_id)
        assert report.passed is True
        assert report.verified_nodes == 4


def test_tamper_detection_on_historical_payload_mutation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "ledger.db"
        engine = StorageEngine(db_path=db_path)

        span_id = "span_tamper_test"

        n1 = engine.append_node(span_id, EventType.PROMPT, "user", {"msg": "clean"})
        n2 = engine.append_node(span_id, EventType.PROOF, "agent", {"proof_id": "prf_123", "target_path": "auth.py"}, [n1.node_id])

        auditor = CryptographicAuditor(engine)
        assert auditor.verify_span(span_id).passed is True

        # Malicious actor tampers with n1 payload directly in SQLite
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE ledger_nodes SET payload_json = ? WHERE node_id = ?;", (json.dumps({"msg": "hacked"}), n1.node_id))
        conn.commit()
        conn.close()

        # Audit must detect tampering immediately
        tamper_report = auditor.verify_span(span_id)
        assert tamper_report.passed is False
        assert len(tamper_report.violations) >= 1
        assert tamper_report.violations[0].node_id == n1.node_id
        assert tamper_report.violations[0].error_type == "TamperMismatchError"


def test_causal_projector_and_ansi_visualizer():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "ledger.db"
        engine = StorageEngine(db_path=db_path)

        span_id = "span_vis_test"
        n1 = engine.append_node(span_id, EventType.PROMPT, "user", {"prompt": "Fix bug"})
        n2 = engine.append_node(span_id, EventType.PROOF, "proof_bot", {"proof_id": "prf_abc", "target_path": "server.py"}, [n1.node_id])
        n3 = engine.append_node(span_id, EventType.GATE, "gate_bot", {"tier": "TIER_1_AUTO", "escalation_score": 0.05}, [n2.node_id])
        n4 = engine.append_node(span_id, EventType.COMMIT, "hypervisor", {"status": "COMMITTED"}, [n3.node_id])

        projector = CausalProjector(engine)
        block = projector.project_span(span_id)
        assert block.final_status == "COMMITTED"
        assert len(block.proofs) == 1
        assert len(block.decisions) == 1

        nodes = engine.get_span_nodes(span_id)
        tree_str = ANSIVisualizer.render_tree(nodes)
        assert "SWARMLEDGER MERKLE DAG TRACE" in tree_str
        assert "PROOF" in tree_str
        assert "COMMIT" in tree_str