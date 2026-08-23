"""
Zero-Trust Cryptographic Auditor for SwarmLedger.
Validates Merkle node integrity, RFC 8785 hashes, and Topological Genesis Depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from swarmledger.core.hasher import MerkleHasher
from swarmledger.core.node import LedgerNode
from swarmledger.storage.engine import StorageEngine


class TamperMismatchError(Exception):
    """Raised when a Merkle node hash does not match computed RFC 8785 payload."""
    pass


class MaliciousForkError(Exception):
    """Raised when a node attempts to forge sequence numbers detached from Genesis depth."""
    pass


@dataclass
class AuditViolation:
    node_id: str
    error_type: str
    details: str
    violation_type: str = ""

    def __post_init__(self):
        if not self.violation_type:
            self.violation_type = self.error_type


@dataclass
class AuditReport:
    span_id: str
    passed: bool
    verified_nodes: int
    violations: List[AuditViolation]


class CryptographicAuditor:
    """
    Audits Merkle DAG spans for byte-level tamper evidence and Genesis depth invariance.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine

    def verify_span(self, span_id: str) -> AuditReport:
        nodes = self.engine.get_span_nodes(span_id)
        if not nodes:
            return AuditReport(span_id, True, 0, [])

        violations: List[AuditViolation] = []
        node_map: Dict[str, LedgerNode] = {n.node_id: n for n in nodes}
        node_depths: Dict[str, int] = {}

        for n in nodes:
            # Look up parent hashes
            p_hashes = [node_map[p_id].node_hash for p_id in n.parent_node_ids if p_id in node_map]

            # 1. Byte-level Merkle integrity check
            if not MerkleHasher.verify_node_integrity(n, parent_hashes=p_hashes):
                violations.append(AuditViolation(
                    node_id=n.node_id,
                    error_type="TamperMismatchError",
                    details=f"RFC 8785 hash mismatch on {n.event_type.value}"
                ))

            # 2. Genesis Topological Depth Invariant check
            if not n.parent_node_ids:
                expected_seq = 1
            else:
                p_seqs = [node_depths.get(p_id, node_map[p_id].lamport_seq if p_id in node_map else 0) for p_id in n.parent_node_ids]
                expected_seq = max(p_seqs) + 1 if p_seqs else 1

            node_depths[n.node_id] = expected_seq

            if n.lamport_seq != expected_seq:
                violations.append(AuditViolation(
                    node_id=n.node_id,
                    error_type="PoisonedLamportChainError",
                    details=f"Claimed sequence {n.lamport_seq} != topological depth {expected_seq} from Genesis."
                ))

        passed = len(violations) == 0
        return AuditReport(span_id, passed, len(nodes), violations)