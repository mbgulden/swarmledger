"""
SwarmSaga Ecosystem Bridge for SwarmLedger.
Ingests saga transactions, forward steps, and rollback compensations into the Merkle DAG.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from swarmledger.core.node import EventType, LedgerNode
from swarmledger.storage.engine import StorageEngine


class SwarmsagaLedgerBridge:
    """
    Ingests SwarmSaga transaction events into SwarmLedger.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine

    def record_step(
        self,
        span_id: str,
        tx_id: str,
        step_name: str,
        state: str,
        agent_id: str,
        is_pivot: bool = False,
        parent_node_ids: Optional[list[str]] = None
    ) -> LedgerNode:
        payload = {
            "tx_id": tx_id,
            "step_name": step_name,
            "state": state,
            "is_pivot": is_pivot
        }
        return self.engine.append_node(
            span_id=span_id,
            event_type=EventType.SAGA_STEP,
            agent_id=agent_id,
            payload=payload,
            parent_node_ids=parent_node_ids,
            synchronous=True
        )

    def record_final_commit(
        self,
        span_id: str,
        tx_id: str,
        agent_id: str,
        parent_node_ids: Optional[list[str]] = None
    ) -> LedgerNode:
        payload = {
            "tx_id": tx_id,
            "status": "COMMITTED"
        }
        return self.engine.append_node(
            span_id=span_id,
            event_type=EventType.COMMIT,
            agent_id=agent_id,
            payload=payload,
            parent_node_ids=parent_node_ids,
            synchronous=True
        )

    def record_abort(
        self,
        span_id: str,
        tx_id: str,
        reason: str,
        agent_id: str,
        parent_node_ids: Optional[list[str]] = None
    ) -> LedgerNode:
        payload = {
            "tx_id": tx_id,
            "status": "ABORTED",
            "reason": reason
        }
        return self.engine.append_node(
            span_id=span_id,
            event_type=EventType.ABORT,
            agent_id=agent_id,
            payload=payload,
            parent_node_ids=parent_node_ids,
            synchronous=True
        )