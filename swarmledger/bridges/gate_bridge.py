"""
SwarmGate Ecosystem Bridge for SwarmLedger.
Ingests Escalation Scores, Attention Tiers, and human decision cards into the Merkle DAG.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from swarmledger.core.node import EventType, LedgerNode
from swarmledger.storage.engine import StorageEngine


class SwarmgateLedgerBridge:
    """
    Ingests SwarmGate attention governance events into SwarmLedger.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine

    def record_decision(
        self,
        span_id: str,
        decision_id: str,
        resource: str,
        escalation_score: float,
        tier: str,
        agent_id: str,
        proof_id: Optional[str] = None,
        parent_node_ids: Optional[list[str]] = None
    ) -> LedgerNode:
        payload = {
            "decision_id": decision_id,
            "resource": resource,
            "escalation_score": escalation_score,
            "tier": tier,
            "proof_id": proof_id
        }
        return self.engine.append_node(
            span_id=span_id,
            event_type=EventType.GATE,
            agent_id=agent_id,
            payload=payload,
            parent_node_ids=parent_node_ids,
            synchronous=True
        )