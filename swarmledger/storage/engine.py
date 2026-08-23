"""
Dual-Path Storage Engine for SwarmLedger.
Synchronous critical path + asynchronous micro-batching for high-throughput append-only Merkle DAG.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from swarmledger.core.canonical import canonicalize
from swarmledger.core.hasher import MerkleHasher
from swarmledger.core.node import EventType, LedgerNode
from swarmledger.storage.schema import LEDGER_SCHEMA_SQL


class StorageEngine:
    """
    High-throughput SQLite storage engine for Merkle DAG nodes and spans.
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            base_dir = Path.home() / ".swarmledger"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = base_dir / "ledger.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._async_queue: queue.Queue = queue.Queue()
        self._stop_flusher = threading.Event()
        self._init_db()

        # Start async micro-batch flusher thread
        self._flusher_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self._flusher_thread.start()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript(LEDGER_SCHEMA_SQL)
                conn.commit()
            finally:
                conn.close()

    def append_node(
        self,
        span_id: str,
        event_type: EventType,
        agent_id: str,
        payload: Dict[str, Any],
        parent_node_ids: Optional[List[str]] = None,
        capability_token_hash: Optional[str] = None,
        synchronous: bool = True
    ) -> LedgerNode:
        """
        Appends a new cryptographically sealed node to the DAG.
        """
        parents = parent_node_ids or []
        parent_hashes = []

        with self._lock:
            conn = self._get_conn()
            try:
                # 1. Fetch parent hashes and determine next Lamport sequence
                max_seq = 0
                for p_id in parents:
                    row = conn.execute("SELECT node_hash, lamport_seq FROM ledger_nodes WHERE node_id = ?;", (p_id,)).fetchone()
                    if row:
                        parent_hashes.append(row["node_hash"])
                        max_seq = max(max_seq, row["lamport_seq"])

                # If no explicit parents, link to current span head
                if not parents:
                    head_row = conn.execute("SELECT head_node_id FROM ledger_spans WHERE span_id = ?;", (span_id,)).fetchone()
                    if head_row and head_row["head_node_id"]:
                        head_id = head_row["head_node_id"]
                        parents = [head_id]
                        row = conn.execute("SELECT node_hash, lamport_seq FROM ledger_nodes WHERE node_id = ?;", (head_id,)).fetchone()
                        if row:
                            parent_hashes = [row["node_hash"]]
                            max_seq = row["lamport_seq"]

                lamport_seq = max_seq + 1
                node_id = f"nod_{uuid.uuid4().hex[:12]}"
                now = time.time()

                node = LedgerNode(
                    node_id=node_id,
                    span_id=span_id,
                    parent_node_ids=parents,
                    lamport_seq=lamport_seq,
                    event_type=event_type,
                    agent_id=agent_id,
                    payload=payload,
                    capability_token_hash=capability_token_hash,
                    timestamp=now
                )

                node_hash = MerkleHasher.compute_hash(node, parent_hashes)
                node.node_hash = node_hash

                if synchronous or event_type in [EventType.LEASE, EventType.PROOF, EventType.GATE, EventType.COMMIT, EventType.ABORT]:
                    self._write_node_immediate(conn, node)
                    conn.commit()
                else:
                    self._async_queue.put(node)

                return node
            finally:
                conn.close()

    def _write_node_immediate(self, conn: sqlite3.Connection, node: LedgerNode) -> None:
        now = time.time()
        conn.execute("""
            INSERT INTO ledger_nodes (
                node_id, span_id, lamport_seq, event_type, agent_id,
                capability_token_hash, payload_json, timestamp, node_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            node.node_id, node.span_id, node.lamport_seq, node.event_type.value,
            node.agent_id, node.capability_token_hash, json.dumps(node.payload),
            node.timestamp, node.node_hash, now
        ))

        for p_id in node.parent_node_ids:
            conn.execute("""
                INSERT OR IGNORE INTO ledger_edges (parent_node_id, child_node_id, span_id)
                VALUES (?, ?, ?);
            """, (p_id, node.node_id, node.span_id))

        # Update span head
        span_row = conn.execute("SELECT span_id FROM ledger_spans WHERE span_id = ?;", (node.span_id,)).fetchone()
        if not span_row:
            conn.execute("""
                INSERT INTO ledger_spans (span_id, root_node_id, head_node_id, status, created_at)
                VALUES (?, ?, ?, 'ACTIVE', ?);
            """, (node.span_id, node.node_id, node.node_id, now))
        else:
            conn.execute("""
                UPDATE ledger_spans
                SET head_node_id = ?, merkle_root_hash = ?
                WHERE span_id = ?;
            """, (node.node_id, node.node_hash, node.span_id))

    def _flush_worker(self) -> None:
        while not self._stop_flusher.is_set():
            batch = []
            try:
                while len(batch) < 100:
                    node = self._async_queue.get_nowait()
                    batch.append(node)
            except queue.Empty:
                pass

            if batch:
                with self._lock:
                    conn = self._get_conn()
                    try:
                        for node in batch:
                            self._write_node_immediate(conn, node)
                        conn.commit()
                    finally:
                        conn.close()

            time.sleep(0.010)

    def get_node(self, node_id: str) -> Optional[LedgerNode]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM ledger_nodes WHERE node_id = ?;", (node_id,)).fetchone()
                if not row:
                    return None
                parents = [
                    r["parent_node_id"] for r in conn.execute(
                        "SELECT parent_node_id FROM ledger_edges WHERE child_node_id = ?;", (node_id,)
                    ).fetchall()
                ]
                d = dict(row)
                d["parent_node_ids"] = parents
                d["payload"] = json.loads(d["payload_json"])
                return LedgerNode.from_dict(d)
            finally:
                conn.close()

    def get_span_nodes(self, span_id: str) -> List[LedgerNode]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute("""
                    SELECT * FROM ledger_nodes WHERE span_id = ? ORDER BY lamport_seq ASC, timestamp ASC;
                """, (span_id,)).fetchall()
                nodes = []
                for r in rows:
                    parents = [
                        er["parent_node_id"] for er in conn.execute(
                            "SELECT parent_node_id FROM ledger_edges WHERE child_node_id = ?;", (r["node_id"],)
                        ).fetchall()
                    ]
                    d = dict(r)
                    d["parent_node_ids"] = parents
                    d["payload"] = json.loads(d["payload_json"])
                    nodes.append(LedgerNode.from_dict(d))
                return nodes
            finally:
                conn.close()

    def list_spans(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute("SELECT * FROM ledger_spans ORDER BY created_at DESC;").fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()