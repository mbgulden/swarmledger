"""
SwarmLock Ecosystem Bridge for SwarmLedger.
Ingests lease acquisitions, fencing tokens, and releases into the Merkle DAG.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from swarmledger.core.node import EventType, LedgerNode
from swarmledger.storage.engine import StorageEngine


class SwarmlockLedgerBridge:
    """
    Ingests SwarmLock events into SwarmLedger.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine

    def record_lease_acquired(
        self,
        span_id: str,
        resource: str,
        mode: str,
        fencing_token: int,
        agent_id: str,
        tx_id: Optional[str] = None,
        parent_node_ids: Optional[list[str]] = None
    ) -> LedgerNode:
        payload = {
            "action": "LEASE_ACQUIRED",
            "resource": resource,
            "mode": mode,
            "fencing_token": fencing_token,
            "tx_id": tx_id
        }
        return self.engine.append_node(
            span_id=span_id,
            event_type=EventType.LEASE,
            agent_id=agent_id,
            payload=payload,
            parent_node_ids=parent_node_ids,
            synchronous=True
        )

    def record_lease_released(
        self,
        span_id: str,
        resource: str,
        agent_id: str,
        tx_id: Optional[str] = None,
        committed: bool = True,
        parent_node_ids: Optional[list[str]] = None
    ) -> LedgerNode:
        payload = {
            "action": "LEASE_RELEASED",
            "resource": resource,
            "committed": committed,
            "tx_id": tx_id
        }
        return self.engine.append_node(
            span_id=span_id,
            event_type=EventType.LEASE,
            agent_id=agent_id,
            payload=payload,
            parent_node_ids=parent_node_ids,
            synchronous=True
        )