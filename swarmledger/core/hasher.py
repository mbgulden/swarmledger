"""
Deterministic Merkle Hasher for SwarmLedger.
Computes cryptographic digests over parent hashes, sequence, event type, and canonical payloads.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional

from swarmledger.core.canonical import canonicalize
from swarmledger.core.node import LedgerNode


class MerkleHasher:
    """
    Computes and verifies cryptographic hashes for DAG nodes.
    """

    @classmethod
    def compute_hash(
        cls,
        node: LedgerNode,
        parent_hashes: Optional[List[str]] = None
    ) -> str:
        """
        Calculates Node Hash:
        SHA256(Sorted Parent Hashes || LamportSeq || EventType || AgentID || CanonicalPayloadBytes)
        """
        parents = parent_hashes if parent_hashes is not None else (node.parent_node_ids or [])
        parents_sorted = sorted(parents)
        parents_chunk = ",".join(parents_sorted).encode("utf-8")
        seq_chunk = str(node.lamport_seq).encode("utf-8")
        event_chunk = node.event_type.value.encode("utf-8")
        agent_chunk = node.agent_id.encode("utf-8")
        payload_bytes = canonicalize(node.payload)

        hasher = hashlib.sha256()
        hasher.update(parents_chunk)
        hasher.update(b"|")
        hasher.update(seq_chunk)
        hasher.update(b"|")
        hasher.update(event_chunk)
        hasher.update(b"|")
        hasher.update(agent_chunk)
        hasher.update(b"|")
        hasher.update(payload_bytes)

        return hasher.hexdigest()

    @classmethod
    def verify_node_integrity(
        cls,
        node: LedgerNode,
        parent_hashes: Optional[List[str]] = None
    ) -> bool:
        """Asserts that node.node_hash matches the computed hash from fields and payload."""
        if not node.node_hash:
            return False
        expected = cls.compute_hash(node, parent_hashes)
        return node.node_hash == expected