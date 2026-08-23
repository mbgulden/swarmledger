"""
SwarmProof Ecosystem Bridge for SwarmLedger.
Ingests Proof Certificates, AST checksums, and verification receipts into the Merkle DAG.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from swarmledger.core.node import EventType, LedgerNode
from swarmledger.storage.engine import StorageEngine


class SwarmproofLedgerBridge:
    """
    Ingests SwarmProof verification certificates into SwarmLedger.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine

    def record_proof(
        self,
        span_id: str,
        proof_id: str,
        target_path: str,
        ast_checksum: str,
        oracles_passed: List[str],
        agent_id: str,
        parent_node_ids: Optional[list[str]] = None
    ) -> LedgerNode:
        payload = {
            "proof_id": proof_id,
            "target_path": target_path,
            "ast_checksum": ast_checksum,
            "oracles_passed": oracles_passed,
            "status": "VERIFIED"
        }
        return self.engine.append_node(
            span_id=span_id,
            event_type=EventType.PROOF,
            agent_id=agent_id,
            payload=payload,
            parent_node_ids=parent_node_ids,
            synchronous=True
        )