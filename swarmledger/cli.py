"""
SwarmLedger Command Line Interface (CLI).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from swarmledger.distiller.visualizer import ANSIVisualizer
from swarmledger.storage.auditor import CryptographicAuditor
from swarmledger.storage.engine import StorageEngine


def cmd_log(args: argparse.Namespace) -> int:
    engine = StorageEngine()
    if args.span:
        nodes = engine.get_span_nodes(args.span)
    else:
        spans = engine.list_spans()
        if not spans:
            print("  (No ledger spans recorded)")
            return 0
        nodes = engine.get_span_nodes(spans[0]["span_id"])

    print("=" * 78)
    print(f" 📜 SWARMLEDGER NODE LOG  ({len(nodes)} records)")
    print("=" * 78)
    print(f"  {'NODE ID':<16} {'SEQ':<5} {'EVENT':<12} {'HASH':<12} {'PAYLOAD'}")
    print("  " + "-" * 74)

    for n in nodes[:args.limit]:
        short_hash = n.node_hash[:10] if n.node_hash else "none"
        payload_preview = json.dumps(n.payload)[:30]
        print(f"  {n.node_id:<16} {n.lamport_seq:<5} {n.event_type.value:<12} {short_hash:<12} {payload_preview}")
    print("=" * 78)
    return 0


def cmd_tree(args: argparse.Namespace) -> int:
    engine = StorageEngine()
    nodes = engine.get_span_nodes(args.span_id)
    tree_str = ANSIVisualizer.render_tree(nodes)
    print(tree_str)
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    engine = StorageEngine()
    node = engine.get_node(args.node_id)
    if not node:
        print(f"Error: Node '{args.node_id}' not found.")
        return 1

    print("=" * 78)
    print(f" 🔍 SWARMLEDGER NODE TRACE: {node.node_id}")
    print("=" * 78)
    print(f"  Span ID:        {node.span_id}")
    print(f"  Lamport Seq:    {node.lamport_seq}")
    print(f"  Event Type:     {node.event_type.value}")
    print(f"  Agent ID:       {node.agent_id}")
    print(f"  Node Hash:      {node.node_hash}")
    print(f"  Parent Nodes:   {', '.join(node.parent_node_ids) or '(none)'}")
    print(f"  Timestamp:      {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(node.timestamp))}")
    print("-" * 78)
    print("  Payload:")
    print(json.dumps(node.payload, indent=2))
    print("=" * 78)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    engine = StorageEngine()
    auditor = CryptographicAuditor(engine)

    if args.span:
        print(f"🔒 Auditing span '{args.span}'...")
        report = auditor.verify_span(args.span)
        if report.passed:
            print(f"  ✅ PASSED: All {report.verified_nodes} nodes cryptographically sound.")
            return 0
        else:
            print(f"  ❌ FAILED: {len(report.violations)} cryptographic violations detected!")
            for v in report.violations:
                print(f"    - [{v.error_type}] Node {v.node_id}: {v.message}")
            return 1
    else:
        print("🔒 Auditing all spans in ledger...")
        all_reports = auditor.audit_all()
        if not all_reports:
            print("  (Empty ledger - zero spans to audit)")
            return 0

        failed = 0
        total_nodes = 0
        for span_id, rep in all_reports.items():
            total_nodes += rep.verified_nodes
            if not rep.passed:
                failed += 1
                print(f"  ❌ Span '{span_id}' corrupted ({len(rep.violations)} violations)")

        if failed == 0:
            print(f"  ✅ ALL SPANS PASSED: {len(all_reports)} spans ({total_nodes} nodes) cryptographically verified.")
            return 0
        else:
            print(f"  ❌ FAILED: {failed} corrupted span(s) found.")
            return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="swarmledger",
        description="SwarmLedger: Cryptographic Merkle DAG & Causal Provenance Ledger",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    p_log = sub.add_parser("log", help="Display node log for a span")
    p_log.add_argument("--span", help="Span ID")
    p_log.add_argument("--limit", type=int, default=20, help="Max nodes to display")
    p_log.set_defaults(func=cmd_log)

    # tree
    p_tree = sub.add_parser("tree", help="Render ANSI Merkle DAG tree for a span")
    p_tree.add_argument("span_id", help="Span ID to render")
    p_tree.set_defaults(func=cmd_tree)

    # trace
    p_trace = sub.add_parser("trace", help="Trace a node backward to root")
    p_trace.add_argument("node_id", help="Node ID to inspect")
    p_trace.set_defaults(func=cmd_trace)

    # audit
    p_aud = sub.add_parser("audit", help="Run cryptographic audit across spans")
    p_aud.add_argument("--span", help="Audit specific span")
    p_aud.set_defaults(func=cmd_audit)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()