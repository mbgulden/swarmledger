"""Tests for CausalProjector and ANSIVisualizer in swarmledger.distiller."""

import pytest

from swarmledger.core.node import EventType
from swarmledger.distiller.projector import CausalBlock, CausalProjector
from swarmledger.distiller.visualizer import ANSIVisualizer
from swarmledger.storage.engine import StorageEngine


@pytest.fixture()
def engine(tmp_path):
    return StorageEngine(db_path=tmp_path / "ledger.db")


@pytest.fixture()
def projector(engine):
    return CausalProjector(engine)


def _append(engine, span, event_type, payload, parents=None):
    return engine.append_node(span, event_type, "agent", payload, parent_node_ids=parents)


def test_project_empty_span(projector):
    block = projector.project_span("span_missing")
    assert block.root_event == "EMPTY"
    assert block.nodes_count == 0
    assert block.final_status == "UNKNOWN"
    assert block.is_thrashing is False
    assert isinstance(block, CausalBlock)


def test_project_committed_span(projector, engine):
    n1 = _append(engine, "span_p1", EventType.PROMPT, {"prompt": "go"})
    n2 = _append(engine, "span_p1", EventType.MUTATE, {"file": "a.py"}, [n1.node_id])
    n3 = _append(engine, "span_p1", EventType.PROOF, {"proof_id": "prf_1", "target_path": "a.py"}, [n2.node_id])
    n4 = _append(engine, "span_p1", EventType.GATE, {"tier": "TIER_2", "escalation_score": 0.8}, [n3.node_id])
    _append(engine, "span_p1", EventType.COMMIT, {"status": "COMMITTED"}, [n4.node_id])

    block = projector.project_span("span_p1")
    assert block.final_status == "COMMITTED"
    assert block.root_event == "PROMPT"
    assert block.nodes_count == 5
    assert block.mutations == ["a.py"]
    assert block.proofs == ["prf_1 (a.py)"]
    assert block.decisions == ["TIER_2 [E=0.8]"]
    assert block.is_thrashing is False


def test_project_aborted_span(projector, engine):
    n1 = _append(engine, "span_p2", EventType.PROMPT, {"prompt": "go"})
    _append(engine, "span_p2", EventType.ABORT, {"status": "ABORTED"}, [n1.node_id])
    block = projector.project_span("span_p2")
    assert block.final_status == "ABORTED"


def test_detect_semantic_thrashing_ping_pong(projector, engine):
    span = "span_thrash"
    parent = None
    for i, checksum in enumerate(["aaa", "bbb", "aaa", "bbb"]):
        n = _append(
            engine, span, EventType.MUTATE,
            {"resource": "file:auth.py", "ast_checksum": checksum},
            [parent.node_id] if parent else None,
        )
        parent = n

    block = projector.project_span(span)
    assert block.is_thrashing is True
    assert block.final_status == "THRASHER_HALTED"
    assert block.thrashing_reason is not None
    assert "Ping-Pong" in block.thrashing_reason
    assert "file:auth.py" in block.thrashing_reason


def test_no_thrashing_when_targets_differ(projector):
    nodes = []
    from swarmledger.core.node import LedgerNode
    import time

    for i in range(4):
        nodes.append(
            LedgerNode(
                node_id=f"n{i}", span_id="s", parent_node_ids=[], lamport_seq=i + 1,
                event_type=EventType.MUTATE, agent_id="a",
                payload={"resource": f"file:f{i}.py", "ast_checksum": "same"},
                timestamp=time.time(), node_hash=f"h{i}",
            )
        )
    assert projector.detect_semantic_thrashing(nodes) is None


def test_no_thrashing_below_window(projector):
    from swarmledger.core.node import LedgerNode
    import time

    nodes = [
        LedgerNode(
            node_id=f"n{i}", span_id="s", parent_node_ids=[], lamport_seq=i + 1,
            event_type=EventType.MUTATE, agent_id="a",
            payload={"resource": "file:auth.py", "ast_checksum": "aaa"},
            timestamp=time.time(), node_hash="h",
        )
        for i in range(3)
    ]
    assert projector.detect_semantic_thrashing(nodes) is None


def test_visualizer_empty_span():
    assert ANSIVisualizer.render_tree([]) == "  (Empty Span DAG)"


def test_visualizer_renders_badges_hashes_and_parents(engine):
    n1 = _append(engine, "span_v", EventType.PROMPT, {"prompt": "x"})
    n2 = _append(engine, "span_v", EventType.SAGA_STEP, {"step_name": "s1", "state": "done"}, [n1.node_id])

    tree = ANSIVisualizer.render_tree(engine.get_span_nodes("span_v"))
    assert "SWARMLEDGER MERKLE DAG TRACE" in tree
    assert "span_v" in tree
    assert "[PROMPT    ]" in tree
    assert "[SAGA_STEP ]" in tree
    assert n2.node_hash[:8] in tree
    assert "(root)" in tree
    assert n1.node_id[:8] in tree  # child shows parent prefix


def test_visualizer_handles_missing_hash(engine):
    n1 = engine.append_node("span_vh", EventType.PROMPT, "u", {})
    nodes = engine.get_span_nodes("span_vh")
    nodes[0].node_hash = None
    tree = ANSIVisualizer.render_tree(nodes)
    assert "nohash" in tree
