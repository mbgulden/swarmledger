"""Tests for MerkleHasher in swarmledger.core.hasher."""

from swarmledger.core.hasher import MerkleHasher
from swarmledger.core.node import EventType, LedgerNode


def _node(**overrides):
    kwargs = dict(
        node_id="nod_test",
        span_id="span_x",
        parent_node_ids=[],
        lamport_seq=1,
        event_type=EventType.PROMPT,
        agent_id="agent_1",
        payload={"prompt": "hello"},
    )
    kwargs.update(overrides)
    return LedgerNode(**kwargs)


def test_compute_hash_is_deterministic():
    n = _node()
    assert MerkleHasher.compute_hash(n) == MerkleHasher.compute_hash(n)


def test_compute_hash_is_hex_sha256():
    h = MerkleHasher.compute_hash(_node())
    assert len(h) == 64
    int(h, 16)  # valid hex


def test_parent_hash_order_does_not_change_hash():
    a = _node(parent_node_ids=["p1", "p2"])
    b = _node(parent_node_ids=["p2", "p1"])
    assert MerkleHasher.compute_hash(a, ["p1", "p2"]) == MerkleHasher.compute_hash(b, ["p2", "p1"])


def test_explicit_parent_hashes_override_node_parents():
    n = _node(parent_node_ids=["p1"])
    h_default = MerkleHasher.compute_hash(n)
    h_explicit = MerkleHasher.compute_hash(n, ["zz_top"])
    assert h_default != h_explicit


def test_hash_changes_when_any_field_changes():
    base = MerkleHasher.compute_hash(_node())
    assert MerkleHasher.compute_hash(_node(payload={"prompt": "different"})) != base
    assert MerkleHasher.compute_hash(_node(lamport_seq=2)) != base
    assert MerkleHasher.compute_hash(_node(agent_id="agent_2")) != base
    assert MerkleHasher.compute_hash(_node(event_type=EventType.COMMIT)) != base


def test_verify_node_integrity_passes_for_sealed_node():
    n = _node(parent_node_ids=[])
    n.node_hash = MerkleHasher.compute_hash(n)
    assert MerkleHasher.verify_node_integrity(n) is True


def test_verify_node_integrity_passes_with_parent_hashes():
    n = _node(parent_node_ids=["p1", "p2"])
    n.node_hash = MerkleHasher.compute_hash(n, ["p1", "p2"])
    assert MerkleHasher.verify_node_integrity(n, ["p1", "p2"]) is True
    # Wrong parent hashes must fail even though the hash itself is well-formed
    assert MerkleHasher.verify_node_integrity(n, ["p1", "evil"]) is False


def test_verify_node_integrity_fails_when_payload_tampered():
    n = _node()
    n.node_hash = MerkleHasher.compute_hash(n)
    n.payload = {"prompt": "tampered"}
    assert MerkleHasher.verify_node_integrity(n) is False


def test_verify_node_integrity_fails_when_hash_missing():
    n = _node()
    n.node_hash = None
    assert MerkleHasher.verify_node_integrity(n) is False
