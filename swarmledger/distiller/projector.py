"""
Semantic Projection & Causal Attention Distiller for SwarmLedger.
Compresses granular mechanical DAG events into high-level causal blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from swarmledger.core.node import EventType, LedgerNode
from swarmledger.storage.engine import StorageEngine


@dataclass
class CausalBlock:
    span_id: str
    root_event: str
    nodes_count: int
    mutations: List[str]
    proofs: List[str]
    decisions: List[str]
    final_status: str


class CausalProjector:
    """
    Projects a high-level causal narrative from granular DAG events.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine

    def project_span(self, span_id: str) -> CausalBlock:
        nodes = self.engine.get_span_nodes(span_id)
        if not nodes:
            return CausalBlock(span_id, "EMPTY", 0, [], [], [], "UNKNOWN")

        mutations = []
        proofs = []
        decisions = []
        final_status = "ACTIVE"

        for n in nodes:
            if n.event_type == EventType.MUTATE:
                mutations.append(n.payload.get("file", n.payload.get("resource", "file")))
            elif n.event_type == EventType.PROOF:
                proofs.append(f"{n.payload.get('proof_id')} ({n.payload.get('target_path')})")
            elif n.event_type == EventType.GATE:
                decisions.append(f"{n.payload.get('tier')} [E={n.payload.get('escalation_score')}]")
            elif n.event_type == EventType.COMMIT:
                final_status = "COMMITTED"
            elif n.event_type == EventType.ABORT:
                final_status = "ABORTED"

        return CausalBlock(
            span_id=span_id,
            root_event=nodes[0].event_type.value,
            nodes_count=len(nodes),
            mutations=mutations,
            proofs=proofs,
            decisions=decisions,
            final_status=final_status
        )