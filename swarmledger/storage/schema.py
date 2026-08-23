"""
SwarmLedger Database Schema and Index Definitions.
"""

LEDGER_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS ledger_nodes (
    node_id TEXT PRIMARY KEY,
    span_id TEXT NOT NULL,
    lamport_seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    capability_token_hash TEXT,
    payload_json TEXT NOT NULL,
    timestamp REAL NOT NULL,
    node_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_edges (
    parent_node_id TEXT NOT NULL,
    child_node_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    PRIMARY KEY (parent_node_id, child_node_id),
    FOREIGN KEY(child_node_id) REFERENCES ledger_nodes(node_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ledger_spans (
    span_id TEXT PRIMARY KEY,
    root_node_id TEXT,
    head_node_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'SEALED')),
    merkle_root_hash TEXT,
    created_at REAL NOT NULL,
    sealed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_nodes_span ON ledger_nodes(span_id);
CREATE INDEX IF NOT EXISTS idx_nodes_event ON ledger_nodes(event_type);
CREATE INDEX IF NOT EXISTS idx_nodes_seq ON ledger_nodes(lamport_seq);
CREATE INDEX IF NOT EXISTS idx_edges_child ON ledger_edges(child_node_id);
"""