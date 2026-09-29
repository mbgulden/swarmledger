# 📒 SwarmLedger

[![CI](https://github.com/mbgulden/swarmledger/actions/workflows/ci.yml/badge.svg)](https://github.com/mbgulden/swarmledger/actions)
[![PyPI version](https://img.shields.io/badge/pypi-v0.1.0-blue.svg)](https://pypi.org/project/swarmledger/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Cryptographic Merkle DAG & Causal Provenance Ledger for Multi-Agent Swarms**  
> *Tamper-evident, write-ahead causal state for agent hypervisors — every lease, mutation, proof, gate decision, and saga step sealed into a verifiable hash chain.*

---

## 💡 Why SwarmLedger?

Multi-agent swarms generate thousands of events — tool calls, file edits, locks, approvals, rollbacks. When something goes wrong (or right), you need answers:

- **What happened, in what causal order?** SwarmLedger appends every event to a Merkle DAG with Lamport clocks, so causality is recorded, not inferred.
- **Was the history tampered with?** Each node is SHA-256 sealed over its parents, sequence, event type, agent, and RFC 8785-canonical payload. The zero-trust auditor re-verifies every byte.
- **Is an agent stuck in a loop?** The causal projector distills granular events into a narrative and flags semantic thrashing (agents ping-ponging edits with net-zero effect).
- **Who did what across primitives?** Ecosystem bridges ingest SwarmLock, SwarmProof, SwarmGate, and SwarmSaga events into one unified ledger.

---

## 🏛️ Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │            AI Agent Swarm                    │
                    │   (leases, mutations, proofs, decisions)     │
                    └──────────────────────┬───────────────────────┘
                                           │  1. Record
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │           Ecosystem Bridges                  │
                    │  SwarmLock · SwarmProof · SwarmGate · SwarmSaga│
                    └──────────────────────┬───────────────────────┘
                                           │  2. Seal
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │      StorageEngine (SQLite, WAL mode)        │
                    │  - RFC 8785 canonical payloads               │
                    │  - SHA-256 Merkle DAG + Lamport clocks       │
                    │  - Dual path: sync critical / async batch    │
                    └──────────────────────┬───────────────────────┘
                                           │  3. Verify & distill
                                           ▼
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
   CryptographicAuditor                CausalProjector + ANSIVisualizer
   (tamper + fork detection)           (narrative + thrash detection)
```

---

## ✨ Key Capabilities

| Capability | How it works |
|---|---|
| **RFC 8785 canonical serialization** | `canonicalize()` produces byte-for-byte deterministic JSON (sorted keys, no whitespace, deterministic floats); NaN/Infinity are rejected. |
| **Merkle DAG sealing** | `MerkleHasher` computes SHA-256 over sorted parent hashes, Lamport seq, event type, agent ID, and canonical payload. |
| **Causal Lamport clocks** | Each node gets `max(parent seqs) + 1`; spans auto-link to the current span head when no parents are given. |
| **Dual-path storage** | Critical events (`LEASE`, `PROOF`, `GATE`, `COMMIT`, `ABORT`) are written synchronously; everything else is micro-batched by a background flusher. SQLite WAL, default DB at `~/.swarmledger/ledger.db`. |
| **Zero-trust audit** | `CryptographicAuditor.verify_span()` checks every node's hash and the Genesis topological-depth invariant, reporting `TAMPER_MISMATCH` and `POISONED_LAMPORT_CHAIN` violations. |
| **Semantic thrash detection** | `CausalProjector` spots agents cycling the same resource with alternating checksums ("ping-pong loop") and projects span narratives (`COMMITTED` / `ABORTED` / `THRASHER_HALTED`). |
| **ANSI DAG visualizer** | `ANSIVisualizer.render_tree()` prints terminal lineage trees for any span. |
| **9 event types** | `PROMPT`, `DELEGATE`, `LEASE`, `MUTATE`, `PROOF`, `GATE`, `SAGA_STEP`, `COMMIT`, `ABORT`. |

---

## 📦 Installation

```bash
pip install swarmledger
```

*Pure Python standard library. Zero runtime dependencies.*

Or install from source:

```bash
git clone https://github.com/mbgulden/swarmledger.git
cd swarmledger
pip install -e ".[dev]"   # dev extras: pytest, ruff, build, twine
```

---

## 🚀 Quick Start

### 1. Record events with the Python SDK

```python
from swarmledger.core.node import EventType
from swarmledger.storage.engine import StorageEngine

engine = StorageEngine()  # ~/.swarmledger/ledger.db

root = engine.append_node("span_deploy_1", EventType.PROMPT, "human",
                          {"prompt": "Refactor auth logic"})
lease = engine.append_node("span_deploy_1", EventType.LEASE, "agent_1",
                           {"resource": "file:auth.py", "mode": "X"})
mut = engine.append_node("span_deploy_1", EventType.MUTATE, "agent_1",
                         {"file": "auth.py", "ast_checksum": "abc123"},
                         parent_node_ids=[lease.node_id])
engine.append_node("span_deploy_1", EventType.COMMIT, "hypervisor",
                   {"status": "COMMITTED"}, parent_node_ids=[mut.node_id])

print(f"Sealed {mut.node_id} -> {mut.node_hash[:12]}")
```

### 2. Audit the span (fail-closed)

```python
from swarmledger.storage.auditor import CryptographicAuditor

report = CryptographicAuditor(engine).verify_span("span_deploy_1")
print("PASSED" if report.passed else "FAILED", f"({report.verified_nodes} nodes)")
for v in report.violations:
    print(v.violation_type, v.node_id, v.details)
```

### 3. Project the causal narrative

```python
from swarmledger.distiller.projector import CausalProjector

block = CausalProjector(engine).project_span("span_deploy_1")
print(block.final_status)   # COMMITTED
print(block.mutations)      # ['auth.py']
print(block.is_thrashing)   # False
```

### 4. Use the CLI

```bash
swarmledger log --span span_deploy_1      # node log
swarmledger tree span_deploy_1            # ANSI Merkle DAG tree
swarmledger trace nod_abc123              # inspect one node
swarmledger audit --span span_deploy_1    # cryptographic audit
swarmledger audit                         # audit every span
swarmledger --version
```

---

## 🔌 Ecosystem Bridges

One ledger for every swarm primitive. Each bridge appends cryptographically sealed events:

| Bridge | Source | Methods |
|---|---|---|
| `SwarmlockLedgerBridge` | SwarmLock | `record_lease_acquired()`, `record_lease_released()` |
| `SwarmproofLedgerBridge` | SwarmProof | `record_proof()` (certificates, AST checksums, oracle receipts) |
| `SwarmgateLedgerBridge` | SwarmGate | `record_decision()` (escalation scores, attention tiers) |
| `SwarmsagaLedgerBridge` | SwarmSaga | `record_step()`, `record_final_commit()`, `record_abort()` |

```python
from swarmledger.bridges.lock_bridge import SwarmlockLedgerBridge

bridge = SwarmlockLedgerBridge(engine)
bridge.record_lease_acquired("span_x", "file:auth.py", "X", fencing_token=42,
                             agent_id="agent_1", tx_id="tx_1")
```

---

## 🗺️ Swarm Ecosystem

SwarmLedger is Stage 5 of the Swarm Suite Agent Hypervisor stack and part of the **Swarm Primitives Ecosystem**:

- 🔒 **SwarmLock**: Tokenized, non-blocking distributed advisory locks.
- 🛡️ **SwarmProof**: Truth Oracle, evidence ledgers, and anti-hallucination gates.
- 📒 **SwarmLedger**: Cryptographic Merkle DAG & causal provenance ledger (this package).
- 🚦 **SwarmGate**: Attention governance and escalation tiers.
- 🔀 **SwarmSaga**: Distributed saga transactions.

---

## 🧪 Development

```bash
pip install -e ".[dev]"
pytest tests/ -v          # 80 tests
ruff check .              # lint
python -m build && twine check dist/*   # package validation
```

---

## 📄 License

MIT © Michael Gulden
