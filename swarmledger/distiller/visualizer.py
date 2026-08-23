"""
ANSI Terminal Visualizer for SwarmLedger DAG Graphs.
"""

from __future__ import annotations

from typing import List

from swarmledger.core.node import LedgerNode
from swarmledger.storage.engine import StorageEngine


class ANSIVisualizer:
    """
    Renders visual ASCII/ANSI lineage trees for a span.
    """

    @classmethod
    def render_tree(cls, nodes: List[LedgerNode]) -> str:
        if not nodes:
            return "  (Empty Span DAG)"

        lines = []
        lines.append("=" * 76)
        lines.append(f" 🌳 SWARMLEDGER MERKLE DAG TRACE (Span: {nodes[0].span_id})")
        lines.append("=" * 76)

        for idx, node in enumerate(nodes):
            is_last = (idx == len(nodes) - 1)
            prefix = "└── " if is_last else "├── "
            indent = "    " * max(0, min(node.lamport_seq - 1, 3))

            # Format event badge
            badge = f"[{node.event_type.value:<10}]"
            short_hash = node.node_hash[:8] if node.node_hash else "nohash"
            parents_str = f"<- ({', '.join(p[:8] for p in node.parent_node_ids)})" if node.parent_node_ids else "(root)"

            desc = ""
            if node.event_type.value == "LEASE":
                desc = f"{node.payload.get('action')} on {node.payload.get('resource')}"
            elif node.event_type.value == "PROOF":
                desc = f"{node.payload.get('proof_id')} -> {node.payload.get('target_path')}"
            elif node.event_type.value == "GATE":
                desc = f"{node.payload.get('tier')} E={node.payload.get('escalation_score')}"
            elif node.event_type.value == "SAGA_STEP":
                desc = f"Step '{node.payload.get('step_name')}' state={node.payload.get('state')}"
            elif node.event_type.value in ["COMMIT", "ABORT"]:
                desc = f"Transaction {node.payload.get('status')}"
            else:
                desc = str(node.payload)[:30]

            lines.append(f" {indent}{prefix}{badge} seq={node.lamport_seq} | {short_hash} | {desc} {parents_str}")

        lines.append("=" * 76)
        return "\n".join(lines)