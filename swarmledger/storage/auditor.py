"""
Cryptographic Merkle DAG Auditor for SwarmLedger.
Performs zero-trust verification of DAG nodes, hashes, parent lineages, and payload integrity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from swarmledger.core.hasher import MerkleHasher
from swarmledger.core.node import LedgerNode
from swarmledger.storage.engine import StorageEngine


@dataclass
class AuditViolation:
    node_id: str
    error_type: str
    expected_hash: str
    actual_hash: str
    message: str


@dataclass
class AuditReport:
    verified_nodes: int
    passed: bool
    violations: List[AuditViolation]


class CryptographicAuditor:
    """
    Audits the append-only Merkle DAG for cryptographic integrity and tamper detection.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine

    def verify_span(self, span_id: str) -> AuditReport:
        nodes = self.engine.get_span_nodes(span_id)
        violations: List[AuditViolation] = []

        node_map: Dict[str, LedgerNode] = {n.node_id: n for n in nodes}

        for node in nodes:
            # 1. Fetch parent hashes
            parent_hashes = []
            for p_id in node.parent_node_ids:
                p_node = node_map.get(p_id) or self.engine.get_node(p_id)
                if p_node:
                    parent_hashes.append(p_node.node_hash or "")
                else:
                    violations.append(AuditViolation(
                        node_id=node.node_id,
                        error_type="MissingParentError",
                        expected_hash="",
                        actual_hash=node.node_hash or "",
                        message=f"Parent node '{p_id}' not found in DAG"
                    ))

            # 2. Re-compute hash
            expected = MerkleHasher.compute_hash(node, parent_hashes)
            if node.node_hash != expected:
                violations.append(AuditViolation(
                    node_id=node.node_id,
                    error_type="TamperMismatchError",
                    expected_hash=expected,
                    actual_hash=node.node_hash or "",
                    message=f"Cryptographic hash mismatch for node '{node.node_id}'. Stored={node.node_hash}, Computed={expected}"
                ))

        return AuditReport(
            verified_nodes=len(nodes),
            passed=(len(violations) == 0),
            violations=violations
        )

    def audit_all(self) -> Dict[str, AuditReport]:
        spans = self.engine.list_spans()
        reports = {}
        for s in spans:
            span_id = s["span_id"]
            reports[span_id] = self.verify_span(span_id)
        return reports