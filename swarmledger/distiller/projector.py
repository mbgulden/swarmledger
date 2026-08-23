"""
Semantic Projection & Causal Attention Distiller for SwarmLedger.
Compresses granular mechanical DAG events and detects AST Semantic Thrashing loops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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
    is_thrashing: bool = False
    thrashing_reason: Optional[str] = None


class CausalProjector:
    """
    Projects high-level causal narrative from granular DAG events and detects semantic thrashing loops.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine

    def detect_semantic_thrashing(self, nodes: List[LedgerNode], window_size: int = 4) -> Optional[str]:
        """
        Detects if an agent is trapped in a net-zero semantic loop (modifying and reverting same AST/resource).
        """
        mutate_nodes = [n for n in nodes if n.event_type in [EventType.MUTATE, EventType.PROOF]]
        if len(mutate_nodes) < window_size:
            return None

        # Check last N mutations for identical or alternating targets/checksums
        recent = mutate_nodes[-window_size:]
        targets = [n.payload.get("resource") or n.payload.get("target_path") for n in recent]
        checksums = [n.payload.get("ast_checksum") or n.node_hash for n in recent]

        # 1. Repeated identical target cycling
        if len(set(targets)) == 1 and targets[0] is not None:
            # Check if checksums alternate (A -> B -> A -> B)
            if len(set(checksums)) <= 2 and len(checksums) >= 4:
                return f"Semantic Ping-Pong Loop: Agent repeated cyclical edits on '{targets[0]}' with net-zero structural delta."

        return None

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

        thrashing_reason = self.detect_semantic_thrashing(nodes)

        return CausalBlock(
            span_id=span_id,
            root_event=nodes[0].event_type.value,
            nodes_count=len(nodes),
            mutations=mutations,
            proofs=proofs,
            decisions=decisions,
            final_status="THRASHER_HALTED" if thrashing_reason else final_status,
            is_thrashing=(thrashing_reason is not None),
            thrashing_reason=thrashing_reason
        )