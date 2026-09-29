"""Tests for StorageEngine in swarmledger.storage.engine (hermetic temp DBs)."""

import json
import sqlite3
import time
from pathlib import Path

import pytest

from swarmledger.core.node import EventType
from swarmledger.storage.engine import StorageEngine


@pytest.fixture()
def engine(tmp_path):
    return StorageEngine(db_path=tmp_path / "ledger.db")


def test_first_node_in_span_is_seq_1_with_no_parents(engine):
    n = engine.append_node("span_a", EventType.PROMPT, "user", {"p": "hi"})
    assert n.lamport_seq == 1
    assert n.parent_node_ids == []
    assert n.node_hash is not None
    assert n.node_id.startswith("nod_")


def test_implicit_parent_links_to_span_head(engine):
    root = engine.append_node("span_b", EventType.PROMPT, "user", {})
    child = engine.append_node("span_b", EventType.DELEGATE, "agent", {})
    assert child.parent_node_ids == [root.node_id]
    assert child.lamport_seq == 2


def test_explicit_parents_take_precedence_over_span_head(engine):
    root = engine.append_node("span_c", EventType.PROMPT, "user", {})
    mid = engine.append_node("span_c", EventType.MUTATE, "agent", {})
    other = engine.append_node("span_d", EventType.PROMPT, "user", {})
    child = engine.append_node(
        "span_c", EventType.COMMIT, "hv", {}, parent_node_ids=[root.node_id, other.node_id]
    )
    assert set(child.parent_node_ids) == {root.node_id, other.node_id}
    assert mid.node_id not in child.parent_node_ids
    assert child.lamport_seq == 2  # max parent seq (1) + 1


def test_get_node_miss_returns_none(engine):
    assert engine.get_node("nod_does_not_exist") is None


def test_get_node_roundtrip(engine):
    n = engine.append_node(
        "span_e", EventType.LEASE, "agent", {"resource": "r"}, capability_token_hash="cth"
    )
    got = engine.get_node(n.node_id)
    assert got is not None
    assert got.node_id == n.node_id
    assert got.event_type == EventType.LEASE
    assert got.payload == {"resource": "r"}
    assert got.capability_token_hash == "cth"
    assert got.node_hash == n.node_hash
    assert got.lamport_seq == n.lamport_seq


def test_get_span_nodes_returns_in_lamport_order(engine):
    engine.append_node("span_f", EventType.PROMPT, "u", {})
    engine.append_node("span_f", EventType.MUTATE, "a", {})
    engine.append_node("span_f", EventType.COMMIT, "h", {})
    nodes = engine.get_span_nodes("span_f")
    assert [n.lamport_seq for n in nodes] == [1, 2, 3]
    assert nodes[1].parent_node_ids == [nodes[0].node_id]


def test_get_span_nodes_empty_for_unknown_span(engine):
    assert engine.get_span_nodes("span_nope") == []


def test_list_spans_tracks_head_and_root(engine):
    root = engine.append_node("span_g", EventType.PROMPT, "u", {})
    child = engine.append_node("span_g", EventType.MUTATE, "a", {})
    spans = {s["span_id"]: s for s in engine.list_spans()}
    assert spans["span_g"]["root_node_id"] == root.node_id
    assert spans["span_g"]["head_node_id"] == child.node_id
    assert spans["span_g"]["merkle_root_hash"] == child.node_hash
    assert spans["span_g"]["status"] == "ACTIVE"


def test_critical_events_written_synchronously_even_when_async_requested(engine):
    for et in (EventType.LEASE, EventType.PROOF, EventType.GATE, EventType.COMMIT, EventType.ABORT):
        n = engine.append_node("span_h", et, "a", {}, synchronous=False)
        assert engine.get_node(n.node_id) is not None, f"{et} should bypass the async queue"


def test_async_append_lands_after_microbatch_flush(engine):
    n = engine.append_node("span_i", EventType.PROMPT, "u", {"k": "v"}, synchronous=False)
    # Not yet visible until the background flusher writes the batch.
    deadline = time.time() + 10
    while time.time() < deadline:
        got = engine.get_node(n.node_id)
        if got is not None:
            break
        time.sleep(0.05)
    assert got is not None
    assert got.payload == {"k": "v"}


def test_nodes_persist_across_engine_instances(tmp_path):
    db = tmp_path / "ledger.db"
    e1 = StorageEngine(db_path=db)
    n = e1.append_node("span_j", EventType.PROMPT, "u", {"x": 1})
    e2 = StorageEngine(db_path=db)
    got = e2.get_node(n.node_id)
    assert got is not None
    assert got.payload == {"x": 1}


def test_db_path_parent_dirs_created(tmp_path):
    deep = tmp_path / "a" / "b" / "ledger.db"
    engine = StorageEngine(db_path=deep)
    engine.append_node("span_k", EventType.PROMPT, "u", {})
    assert deep.exists()
