"""
Causal Merkle DAG Node and Event Types for SwarmLedger.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    PROMPT = "PROMPT"
    DELEGATE = "DELEGATE"
    LEASE = "LEASE"
    MUTATE = "MUTATE"
    PROOF = "PROOF"
    GATE = "GATE"
    SAGA_STEP = "SAGA_STEP"
    COMMIT = "COMMIT"
    ABORT = "ABORT"


@dataclass
class LedgerNode:
    node_id: str
    span_id: str
    parent_node_ids: List[str]
    lamport_seq: int
    event_type: EventType
    agent_id: str
    payload: Dict[str, Any]
    capability_token_hash: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    node_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LedgerNode:
        event_type = EventType(data["event_type"])
        return cls(
            node_id=data["node_id"],
            span_id=data["span_id"],
            parent_node_ids=data.get("parent_node_ids", []),
            lamport_seq=int(data["lamport_seq"]),
            event_type=event_type,
            agent_id=data["agent_id"],
            payload=data.get("payload", {}),
            capability_token_hash=data.get("capability_token_hash"),
            timestamp=float(data.get("timestamp", time.time())),
            node_hash=data.get("node_hash")
        )