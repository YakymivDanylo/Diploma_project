# Use Cases: Consensus & Node Network (Epic 3)

> Based on [PRD](../PRD.md) — Epic 3: Consensus & Node Network

> Updated 2026-09-07 (v1.3 pass): Revised UC-1, UC-4, UC-14 to align with PRD v1.3 (architecture-review polish, FINAL). Key changes: `IssuerRegistry` (UC-1-D) is redefined from "which issuer identity(ies) this node signs as" into a **network-wide** `issuer_id → public_key` trust store covering every issuer identity used anywhere in the network, since it also backs verification of OTHER nodes' `DocumentRecord` signatures (Epic 2 UC-4's new explicit signature-check step) — for this thesis's scope the demo network uses a single shared issuer identity across all nodes; UC-4's PBFT forward-to-primary branch is clarified to state which `issuer_id` ends up on the record (the network's single shared issuer identity, signed by whichever node received and signed the submission — never the forwarded-to primary's identity); the key resolver constructed/injected in UC-14 (and consumed by UC-3, UC-6, UC-8, UC-12) is now explicitly time-aware — `resolve_node_key(node_id, at_timestamp)` / `resolve_issuer_key(issuer_id, at_timestamp)` — rather than a single-valued map, since a single-valued map cannot represent both a retired and an active key for the same identity; UC-4-E6's duplicate-hash rejection and UC-4-EC2's concurrent-submission lock scenario are updated to explicitly state the broadened scope — a `hash` already present in the current pending batch/mempool is also rejected with `409`, not only a hash already in a finalized block — making UC-4-EC2's lock scenario a direct, explicit consequence of this rule rather than an implicit exception. No use cases were removed; numbering is unchanged.
>
> Updated 2026-09-07 (v1.2 pass): Revised UC-1, UC-3, UC-4, UC-5, UC-6, UC-12, UC-13 and added UC-14 to align with PRD v1.2 (second architecture-review round). Key changes: `POST /documents` (UC-4) now explicitly accepts an UNSIGNED `{hash, metadata}` body — the node signs the resulting `DocumentRecord` server-side with its configured `IssuerKeyPair` (confirmed architectural decision), and rejects with `409 Conflict` any `hash` already present in ANY finalized block (single, authoritative duplicate-hash policy — no more "return earliest match" ambiguity, see UC-13-EC1); each node now also loads a boot-time `IssuerRegistry` (`issuer_id → public_key`) alongside the existing `ValidatorSet`, and `ValidatorSet` gains a per-entry `retired_at` field so rotated validator keys stay resolvable (UC-1-C, UC-1-D, new UC-14); the hashed preimage's `proposer_id` (present for BOTH PoW and PBFT) is now the single source of truth for proposer identity — PBFT's `sealed_consensus.primary_id` is removed (UC-5, UC-6); chain-sync (UC-3) and the `GET /node/info` validity cache (UC-12) now explicitly run the SAME full Epic 2 validation checklist — including PBFT `commit_signatures[]` quorum verification — via an injected key resolver/`expected_difficulty`/`ValidatorSet` (new UC-14); `GET /node/info` (UC-12) now reads from a continuously, incrementally-updated validity cache rather than performing a full revalidation on every call; the fork tie-break rule (UC-3-EC1) is now explicitly PoW-only — a same-height PBFT fork is a Byzantine-fault event, never silently tie-broken. No existing use cases were removed; numbering is unchanged except for the new UC-14 at the end.
>
> Updated 2026-09-07 (v1.1 pass): Revised UC-1, UC-3, UC-4, UC-5, UC-6, UC-7, UC-8, UC-9 and added UC-12, UC-13 to align with PRD v1.1 (post architecture-review). Key changes: a static, boot-time `ValidatorSet` is now distinct from the dynamic `PeerInfo` gossip registry and is the sole basis for PBFT quorum counting (closes C-4); each node is now both a WS server and WS client via a `PeerConnectionManager` with reconnect/backoff (closes M-5); PBFT view-change is documented as an explicit simplified round-robin mechanism (closes M-6); the primary's own pre-prepare counts toward its own prepare quorum (closes M-7); crash faults and Byzantine faults are now distinguished failure classes (closes M-9); fork tie-break is lowest-tip-hash-only; chain-sync requires full revalidation on divergence before the local tip (closes M-14); `GET /chain` requires pagination; `POST /blocks/submit` is renamed `POST /documents`; `GET /documents/search` is renamed/relocated to `GET /documents/{hash}` (owned by Epic 3, new UC-13); a new `GET /node/info` endpoint is added (new UC-12); and a standard error envelope plus Pydantic validation (hash pattern, metadata size limit) applies across endpoints (closes M-11). No existing use cases were removed; numbering is unchanged except for the two additions at the end.

This document covers the multi-node network layer built on top of Epic 2's core library: peer registration/discovery, REST chain synchronization, WebSocket block/PBFT-message broadcast, the PoW and PBFT consensus implementations, and the docker-compose multi-node deployment. Actors include node processes (self and peers), the network operator (running docker-compose), and adversarial/byzantine nodes (base rejection behavior — full attack scenarios are exercised in Epic 5).

**Cross-cutting API contract (PRD FR-19, closes M-11):** every REST endpoint in this document returns errors using a single JSON envelope: `{"error": {"code": "<machine_readable_code>", "message": "<human_readable_message>", "details": {...}}}`. All request bodies are validated with Pydantic models; hash-valued fields (`document_hash`, `previous_hash`, `block_hash`, etc.) must match `^[0-9a-f]{64}$`; `DocumentRecord.metadata` has a server-enforced maximum size, with oversized metadata rejected as a validation error. Error flows below reference this envelope rather than restating its shape each time.

---

## UC-1: Node Startup and Peer Registration

**Actor**: Node process (self), peer node
**Preconditions**: Node process starts with configuration specifying its own identity, a list of known/seed peers (for `PeerInfo`), and — independently — its boot-time `ValidatorSet` (see UC-1-C below)
**Trigger**: Node startup, or an explicit `POST /peers/register` call from another node

**Scope note (closes C-4):** this use case governs the dynamic `PeerInfo` gossip registry only — connectivity and broadcast fan-out. It has no effect whatsoever on PBFT quorum counting. Quorum (2f+1) is computed exclusively over the separate, static `ValidatorSet` described in UC-1-C and referenced by UC-6; growing `PeerInfo` via registration never changes the quorum threshold.

### Primary Flow (Happy Path)
1. Node A calls `POST /peers/register` on node B with `{node_id, host, port, public_key}` (the `public_key` here is A's `NodeKeyPair` public key, used for peer/transport authentication — not the `IssuerKeyPair`).
2. Node B adds A to its `PeerInfo` peer list (recording `last_seen`) and returns its current peer list to A.
3. Node A merges B's returned peer list into its own known peers (basic gossip-style discovery).

**Postconditions**: Node A is aware of node B and of B's other known peers via `PeerInfo`; B is aware of A. `ValidatorSet` membership and PBFT quorum threshold are unaffected by this flow.

### Alternative Flows
- **UC-1-A: Startup with multiple seed peers** — node registers sequentially with each configured seed peer at startup, accumulating peer knowledge from each.
- **UC-1-C: Static `ValidatorSet` boot configuration (closes C-4; extended in v1.2 with `retired_at`)** — independently of any `POST /peers/register` traffic, each node loads a fixed, static `ValidatorSet` from boot-time config: a list of validator node identities/`NodeKeyPair` public keys, with a fixed `n` (size) and derived `f` (`n ≥ 3f + 1`). The node logs its `ValidatorSet` (`n`, `f`) at boot. The `ValidatorSet` is never mutated at runtime and is never derived from or updated by `PeerInfo` registrations — it is the sole input to PBFT quorum counting (UC-6). Each entry carries a nullable `retired_at` (epoch-ms) field (v1.2, NEW): when a validator's `NodeKeyPair` is rotated or the validator is removed, its old entry is marked `retired_at` rather than deleted, so its public key remains resolvable — via the key resolver constructed in UC-14 — for verifying `proposer_signature`/`commit_signatures` on blocks it produced/attested to BEFORE the rotation.
- **UC-1-D: `IssuerRegistry` boot configuration (NEW in v1.2; scope broadened and redefined in v1.3, closes second-round CRITICAL — key registries)** — each node also loads a static, boot-time `IssuerRegistry`: `issuer_id → public_key`. **v1.3: this is redefined as a network-wide trust store** covering every issuer identity used anywhere in the network — NOT merely "which issuer identity(ies) this node itself signs as." It serves two roles: (a) identifying which `issuer_id` this node signs new `DocumentRecord`s as when it produces them via `POST /documents` (UC-4), AND (b) supplying the issuer-half of the key resolver used by Epic 2's chain-validation function to VERIFY `DocumentRecord` signatures found in blocks received from ANY node in the network (Epic 2's new explicit per-block signature-check step). **For this thesis's scope, the demo network uses a single shared issuer identity configured identically across all nodes** — the simplest legitimate choice for a prototype representing one issuing authority — while the registry's schema remains a general `issuer_id → public_key` map to support a future multi-issuer extension without a contract change. The node logs its loaded `IssuerRegistry` (`issuer_id`) at boot, alongside its `ValidatorSet` (UC-1-C). Together, `IssuerRegistry` and `ValidatorSet` back the injected, time-aware key resolver constructed in UC-14 and consumed by every Epic 2 chain-validation call this node makes (UC-3, UC-6, UC-12).

### Error Flows
- **UC-1-E1: Seed peer unreachable at startup** — the configured seed peer's container/process is not yet up (common during docker-compose cold start). Node retries with backoff rather than crashing or giving up permanently.
- **UC-1-E2: Duplicate registration** — the same `node_id` registers again (e.g., after a restart). System updates the existing `PeerInfo` entry's `last_seen`/`host`/`port` rather than creating a duplicate entry.
- **UC-1-E3: Malformed registration payload** — missing `public_key` or `host`, or a `public_key` that fails Pydantic validation. System returns a 400-level validation error using the standard error envelope (PRD FR-19).

### Edge Cases
- **UC-1-EC1**: A node attempts to register itself (`node_id` equals the receiving node's own id). System rejects/ignores the self-registration.
- **UC-1-EC2**: Peer list grows very large due to many registrations (potential Sybil flood, see Epic 5). The base engine must not crash or exhaust memory; rate-limiting/admission control beyond basic registration is documented as an explicit known gap addressed only at the level Epic 5 measures, not hardened further per PRD's non-goals for this epic. Critically, since `PeerInfo` growth never affects `ValidatorSet`-based quorum (see Scope note above), even an unbounded `PeerInfo` flood cannot bias PBFT consensus outcomes — it can at most affect connectivity/broadcast load.

### Data Requirements
- **Input**: `{node_id, host, port, public_key}`.
- **Output**: Peer's current `PeerInfo` list.
- **Side Effects**: `PeerInfo` registry updated on both sides (in-memory, and/or persisted `PeerInfo` records). `ValidatorSet` is never written by this flow.

---

## UC-2: List Known Peers

**Actor**: Node process (self), or an operator/monitoring tool
**Preconditions**: None
**Trigger**: `GET /peers`

### Primary Flow (Happy Path)
1. Caller requests `GET /peers`.
2. Node returns its current list of known `PeerInfo` records. This endpoint reflects `PeerInfo` only — it does NOT reflect `ValidatorSet` membership; the static validator list is exposed instead via `GET /node/info` (UC-12).

**Postconditions**: Caller has an up-to-date view of the node's known `PeerInfo` peers.

### Error Flows
- **UC-2-E1**: Node has not yet registered with anyone (fresh start). Returns an empty list — not an error.

### Data Requirements
- **Input**: None.
- **Output**: List of `PeerInfo` (`node_id`, `host`, `port`, `public_key`, `last_seen`).

---

## UC-3: Chain Synchronization

**Actor**: Node process (requesting node), peer node (source of truth for this request)
**Preconditions**: Two or more nodes online; local chains may differ in length/content
**Trigger**: A node requests `GET /chain` from a peer — periodically, on startup, or upon detecting it is behind (e.g., a broadcast referenced a block it doesn't recognize)

### Primary Flow (Happy Path)
1. Node A requests `GET /chain` (optionally paginated via `?from=&to=`, see UC-3-D) from node B.
2. A validates B's returned chain using Epic 2's chain-validation function (Epic 2 UC-4), invoked with **A's own injected key resolver, `expected_difficulty` (PoW), and `ValidatorSet` (PBFT)** — constructed and maintained per UC-14 — never by having Epic 2 look up keys/policy itself.
3. A determines whether B's chain is a **simple, non-diverging extension** of A's local chain (i.e., B's chain shares A's current tip as an ancestor) or **diverges before A's local tip**:
   - **Simple extension**: A validates only the new blocks incrementally from its current tip forward (Epic 2 UC-4-A), using the identical injected resolver/checklist.
   - **Diverging fork (closes M-14)**: A runs Epic 2's full chain-validation function over B's *entire* incoming chain from genesis (or at minimum from the divergence point back through genesis-linked ancestry) — incremental from-the-tip validation is explicitly insufficient and MUST NOT be used in this case, since it would fail to re-verify the ancestry below the divergence point.
   - **Single validation checklist, always (v1.2, closes second-round MAJOR)**: whichever mode runs, the checklist is the SAME one used for live proposal validation (UC-6/UC-8) and for refreshing the `GET /node/info` validity cache (UC-12) — for PBFT chains this explicitly includes `commit_signatures[]` quorum verification (≥2f+1 over the injected `ValidatorSet`, `failure_type = "quorum"` on failure). Chain-sync never uses a lighter or partial check.
4. If B's chain is valid and longer (PoW: longest-valid-chain rule; PBFT: higher latest-finalized-height rule) than A's own, A adopts B's chain, replacing its local state.

**Postconditions**: A's local chain reflects the most advanced valid chain it has observed, or remains unchanged if no peer offered a better one.

### Alternative Flows
- **UC-3-A: Range-based sync** — A requests only blocks after its current tip index, rather than the full chain, for efficiency on long chains. This is valid only for the simple-extension case (step 3); a diverging fork always triggers full revalidation regardless of range requested.
- **UC-3-B: PBFT finalized-height rule** — under PBFT, the comparison uses latest-finalized-height rather than raw chain length, since PBFT blocks are only adopted once finalized by quorum (counted over the `ValidatorSet`, see UC-6).
- **UC-3-D: Paginated `GET /chain` (PRD FR-18)** — `GET /chain` supports `?from=<index>&to=<index>` to return a bounded range of blocks, with a server-enforced maximum page size; a request for a full historical sync on a long chain is expected to be issued as multiple paginated requests rather than one unbounded dump.

### Error Flows
- **UC-3-E1: Peer's chain fails validation** — B's returned chain fails Epic 2's hash-chain/signature checks (any `failure_type`). A rejects the entire sync attempt, keeps its own local chain, and flags B as a potentially malicious/faulty peer (used by Epic 5's tamper/Sybil detection).
- **UC-3-E2: Peer unreachable or timeout** — the sync request times out or the connection fails. A's sync attempt fails gracefully; A continues operating on its local chain and retries later.
- **UC-3-E3: Malformed/truncated response** — B's response is not valid JSON or is truncated mid-transfer, or fails Pydantic validation. A rejects the response (via the standard error envelope, PRD FR-19) without crashing.
- **UC-3-E4: Requested page range exceeds the server-enforced maximum** — A (or any caller) requests a `?from=&to=` range larger than the configured max page size. B returns either a truncated page (fewer blocks than requested) or a validation error, per its documented policy — never an unbounded full-chain dump.

### Edge Cases
- **UC-3-EC1: Fork with equal-length, differing valid chains — tie-break scope restricted to PoW only (v1.2, closes second-round MAJOR)** — this behaves differently per algorithm:
  - **PoW**: two peers report chains of equal valid length but different content — an expected, benign occurrence under PoW. The deterministic tie-break rule is: select the chain whose tip has the **lowest `block_hash`** (unsigned integer / lexicographic hex comparison) — this is the ONLY tie-break rule, and it applies **exclusively to PoW chains**. "First-observed" or any other node-local/order-dependent tie-break is explicitly disallowed, since it would make different nodes converge on different chains under identical global state (PRD FR-17).
  - **PBFT (v1.2 — this tie-break rule MUST NOT be applied)**: because PBFT finalization already requires a `2f+1` quorum, two *different, independently finalized* blocks at the same height is not a normal fork — it is only possible if the quorum was corrupted (e.g., equivocating validators, UC-6-E2). A node that observes two differently-finalized blocks at the same height on a PBFT chain MUST NOT silently pick one by lowest-hash or any other tie-break; it MUST report/log the condition as a **Byzantine-fault/safety-violation event** (per UC-6-E2's Byzantine-fault reporting) and surface it via `quorum_status` in `GET /node/info` (UC-12).
- **UC-3-EC2**: A sync request arrives while the node is mid-mining or mid-PBFT-round. The in-progress consensus state must not be corrupted by a concurrent chain replacement; the node handles this as a defined transition (e.g., abandon and restart the in-progress round against the newly adopted chain).
- **UC-3-EC3**: Node is far behind (many blocks) and requests a full historical sync via repeated paginated `GET /chain?from=&to=` requests (UC-3-D). Large-transfer/timeout handling must not hang indefinitely.

### Data Requirements
- **Input**: Requesting node's current tip/height (for range sync); optional `?from=&to=` pagination parameters; peer's full/partial chain in response.
- **Output**: Updated local chain (if adopted).
- **Side Effects**: Local chain state may be replaced; persistence (Epic 2 UC-8) triggered on adoption.

---

## UC-4: Submit a Document for Issuance — Unsigned Request, Server-Side Signing, Duplicate Rejection

**Actor**: Client (Epic 4 web UI, or an automated script — including Epic 5 attack scripts)
**Preconditions**: Node is online, connected to the network, and has a configured `IssuerKeyPair` and `IssuerRegistry` entry (UC-1-D)
**Trigger**: `POST /documents` (renamed from `POST /blocks/submit` in PRD v1.1; **v1.2 — confirmed architectural decision**: the request body is UNSIGNED `{hash, metadata}` — `hash` is the SHA-256 hex of the document content, computed client-side by Epic 4's Issue page; `metadata` is subject to the FR-19 size cap. The endpoint does NOT accept a pre-signed `DocumentRecord` or any client-supplied `signature` field — the browser/UI never touches `IssuerKeyPair` private-key material.)

### Primary Flow (Happy Path — PoW)
1. Node receives the unsigned `{hash, metadata}` submission.
2. Node checks whether `hash` already appears in ANY finalized block anywhere in its local chain, OR is already present in the node's current pending batch/mempool awaiting inclusion in a not-yet-finalized block (v1.3 broadening) — see UC-4-E6 for the rejection path if so.
3. Node assembles `{document_hash: hash, issuer_id: <this node's configured IssuerRegistry issuer_id, UC-1-D>, issued_at: <now, epoch-ms>, metadata}` and **signs it server-side with the node's configured `IssuerKeyPair` private key** (Epic 2 UC-1/UC-9) to produce the full signed `DocumentRecord` — the node performs this signing step itself; the client never supplies or sees a signature.
4. Node adds the signed record to its local pending-batch/mempool.
5. Node begins mining (UC-5) toward finalizing a block containing this batch.
6. Node responds to the caller with an accepted/queued acknowledgment (finalization is asynchronous).

### Primary Flow (Happy Path — PBFT)
1. Node receives the unsigned submission and performs the duplicate-hash check and server-side signing exactly as steps 2–3 above — **the receiving node signs the record with its own configured `IssuerRegistry` `issuer_id`, regardless of which node ends up proposing the block**. Since this thesis's demo network configures a single shared issuer identity identically across all nodes (UC-1-D), the resulting `DocumentRecord.issuer_id` is that one shared network-wide issuer identity either way — it is determined by the node that received and signed the submission, not by whichever node later proposes/primary-drives the containing block.
2. If this node is the current primary/leader for the active view, it initiates a proposal round (UC-6) including this already-signed batch.
3. If this node is not the primary, it forwards the **already-signed** `DocumentRecord` (not the raw unsigned submission) to the known primary (or queues it until it becomes primary via a future view) — the record's `issuer_id`/`signature` were fixed at step 1 by the receiving node and are never re-signed or reassigned by the primary that eventually proposes the block.
4. Node responds to the caller with an accepted/queued acknowledgment.

**Postconditions**: The submission is accepted for asynchronous processing; a signed `DocumentRecord` now exists in the node's pending batch, produced entirely server-side; actual finalization is tracked separately (UC-5/UC-6/UC-7, and observed by the caller via Epic 4's confirmation flow).

### Alternative Flows
- **UC-4-A**: Batch of multiple documents submitted together, vs. a single-document submission — both follow the identical flow, differing only in batch size, and each hash is independently checked for duplicates (step 2) before batching.

### Error Flows
- **UC-4-E1: Client supplies a `signature` field** — the request body includes a `signature` (or any pre-signed `DocumentRecord` shape) rather than the plain `{hash, metadata}` contract. Node rejects with a 400-level Pydantic validation error in the standard error envelope (PRD FR-19); this enforces the unsigned-submission contract, not merely documents it (v1.2).
- **UC-4-E2: No reachable primary under PBFT** — the node is not primary, and the known primary is unreachable (e.g., down, no view-change completed yet). Node either queues the submission for retry or returns an explicit "no primary available" error — behavior must be deterministic and documented, not silently dropped.
- **UC-4-E3: Empty/malformed request** — a submission missing `hash` or `metadata` entirely. Rejected with a 400-level validation error.
- **UC-4-E4: Node not yet synced** — the node is mid-shutdown or has not completed initial chain sync. Submission is rejected with a retry-later status rather than being accepted into an inconsistent local state.
- **UC-4-E5: Malformed hash or oversized metadata (closes M-11)** — `hash` does not match the Pydantic-enforced pattern `^[0-9a-f]{64}$`, or `metadata` exceeds the server-enforced maximum byte-length cap. Node rejects the entire submission with a 400-level validation error in the standard error envelope, before any duplicate check or queueing — since metadata is broadcast to every peer, this closes an otherwise-unbounded DoS/amplification vector.
- **UC-4-E6: Duplicate hash — `409 Conflict` (v1.2, single authoritative policy, closes prior ambiguity; scope broadened in v1.3)** — `hash` already appears in ANY finalized block anywhere in the local chain, **OR is already present in the node's current pending batch/mempool awaiting inclusion in a not-yet-finalized block (v1.3 — broadened from "finalized block" only, to match the batch-level duplicate check in Epic 2 FR-5 and to cover concurrent-submission races before a block is finalized)**. Node rejects with `409 Conflict` via the standard error envelope (PRD FR-19) — before assembling or signing any `DocumentRecord`, and before Epic 2's batch/Merkle construction is ever invoked for that hash (Epic 2 UC-2-E3 covers the separate, within-batch duplicate case). This is the single, authoritative duplicate-document-hash rule for the whole system: no "return the earliest match" behavior, no silent deduplication, no "duplicates legal within a batch" exception anywhere, and no window where the same hash can be queued twice while pending.

### Edge Cases
- **UC-4-EC1 (v1.2 — redefined; see UC-4-E6 for the normative behavior)**: A submission whose `hash` was already finalized in a prior block, or is already sitting in the pending batch/mempool (v1.3), is, by definition, always and only handled via the `409` rejection in UC-4-E6 — there is no alternate "no-op" or silent-success behavior for this case.
- **UC-4-EC2 (v1.3 — now a direct, explicit consequence of UC-4-E6's broadened scope, not an implicit exception)**: Concurrent submissions arrive at the same node simultaneously, including two submissions for the *same* `hash` racing each other. Because UC-4-E6's duplicate check now explicitly covers the pending batch/mempool (not only finalized blocks), the node's per-hash or global submission lock — serializing the duplicate-check-then-sign-then-queue sequence — is the mechanism that makes this rule enforceable under concurrency: without it, two concurrent submissions for the same hash could each observe "not yet pending" and both pass the check before either is queued. With the lock in place, only one submission can win the check-then-queue sequence; the loser observes `409` per UC-4-E6 (now correctly attributed to the "already in pending batch/mempool" branch, not a race-condition double-issuance).

### Data Requirements
- **Input**: `{hash, metadata}` (unsigned).
- **Output**: Acknowledgment (accepted/queued/rejected with `409`/`400`).
- **Side Effects**: A signed `DocumentRecord` is produced server-side (using the node's `IssuerKeyPair`) and added to the pending-batch/mempool; mining or proposal round initiated.

---

## UC-5: Proof-of-Work Block Mining and Broadcast

**Actor**: Node process (self, running in PoW mode)
**Preconditions**: Node has a pending batch (UC-4); PoW difficulty is configured
**Trigger**: Mining begins automatically after a batch is accepted

### Primary Flow (Happy Path)
1. Node repeatedly varies the `sealed_consensus.nonce` field within the hashed preimage (Epic 2 UC-2), recomputing `block_hash`, until the hash meets the configured `sealed_consensus.difficulty` target (e.g., N leading zero bits).
2. Upon success, node attaches the `proposer_signature` attestation field (a `NodeKeyPair` signature over the winning preimage, Epic 2 UC-2 step 7) and finalizes the block locally (Epic 2 UC-3 append).
3. Node broadcasts the finalized, attested block to all connected peers over `WS /ws/blocks`, via its `PeerConnectionManager`'s outbound connections (see UC-7).

**Postconditions**: Block is finalized on the originating node and broadcast to the network.

### Alternative Flows
- **UC-5-A**: Difficulty is changed via configuration (no code changes); resulting time-to-finalize measurably scales with difficulty (verifiable via the metrics endpoint, UC-9).

### Error Flows
- **UC-5-E1: Lost the race** — while this node is still mining, it receives a valid competing block for the same height from a peer first. Node abandons its own in-progress mining attempt, adopts the peer's block (via UC-7), and re-queues its own pending batch if it was not included in the winning block.
- **UC-5-E2: Broadcast delivery failure** — the broadcast does not reach some peers (network partition, WS disconnect). Those peers catch up later via chain sync (UC-3) rather than being permanently stuck.

### Edge Cases
- **UC-5-EC1**: Two nodes find a valid nonce at nearly the same time (temporary fork). Resolved later via the longest-valid-chain rule during the next chain sync (UC-3).
- **UC-5-EC2**: Extremely low/zero difficulty (test configuration) — immediate finalization; still produces a fully valid block.
- **UC-5-EC3**: Extremely high difficulty causing long mining times — the mining loop must remain interruptible if a peer's competing block arrives (ties to UC-5-E1), rather than blocking indefinitely on a stale target.

### Data Requirements
- **Input**: Pending batch, current difficulty, current chain tip.
- **Output**: Finalized `Block` with hashed preimage `proposer_id` (this node's `node_id`, v1.2 — present in the preimage for both PoW and PBFT) and `sealed_consensus = {nonce, difficulty}`, plus attestation field `proposer_signature` attached after hashing.
- **Side Effects**: Local chain append; WebSocket broadcast; metrics recorded (UC-9), including a per-node hash-rate sample.

---

## UC-6: PBFT Block Proposal and Commit

**Actor**: Node process (primary and replica roles), byzantine/faulty node (adversarial variant)
**Preconditions**: A `ValidatorSet` of n ≥ 4 members is configured at boot (UC-1-C) and online; the current view has a designated primary
**Trigger**: The primary receives a submission (UC-4) and initiates a consensus round

**Quorum scope (closes C-4):** every quorum count in this use case (`2f+1` prepares, `2f+1` commits) is computed **exclusively over the static `ValidatorSet`** loaded at boot — never over the dynamic `PeerInfo` registry (UC-1), regardless of how many additional peers have registered. `n` and `f` are fixed for the process lifetime.

### Primary Flow (Happy Path)
1. Primary broadcasts `pre-prepare(block_candidate, view, seq)` to all `ValidatorSet` members over `WS /ws/pbft`, using its `PeerConnectionManager`'s outbound connections (see UC-7) so delivery does not depend on which side initiated the underlying WebSocket connection.
2. Each `ValidatorSet` replica validates the candidate block (Epic 2 hash-chain + `proposer_signature` checks); if valid, it broadcasts `prepare` to all other `ValidatorSet` members.
3. Each node collects `prepare` messages from `ValidatorSet` members; upon reaching 2f+1 matching prepares (for the same view/seq/block) counted over the `ValidatorSet`, it moves to the commit phase and broadcasts `commit`. **Quorum-counting rule (closes M-7, explicit):** the primary's own `pre-prepare` message counts as its implicit vote toward its own prepare quorum — the primary does not separately send itself a `prepare` message to be counted; this is standard PBFT semantics and must be implemented unambiguously.
4. Each node collects `commit` messages from `ValidatorSet` members; upon reaching 2f+1 matching commits (again counted over the `ValidatorSet`), it finalizes the block locally (Epic 2 UC-3 append) and the block is now committed at this node.

**Postconditions**: The block is finalized identically and deterministically on every correct (non-faulty) `ValidatorSet` member.

### Alternative Flows
- **UC-6-A: Replica (non-primary) role** — a node only responds to `pre-prepare`/other nodes' `prepare`/`commit` messages; it does not initiate.
- **UC-6-B: Successful round with f=1 tolerated fault among n=4** — see UC-6-EC1.
- **UC-6-F: `PeerConnectionManager` bidirectional connectivity (closes M-5)** — each `ValidatorSet` member's `PeerConnectionManager` maintains outbound WebSocket connections to every other `ValidatorSet` member (and every `PeerInfo` peer) in addition to accepting inbound connections, so `pre-prepare`/`prepare`/`commit` fan-out reaches all parties regardless of which node initiated the connection. On connection loss, the manager reconnects with capped exponential backoff and exposes per-peer connection health (surfaced via `GET /node/info`, UC-12).

### Error / Byzantine Flows
- **UC-6-E1: Primary proposes an invalid block** — the candidate fails Epic 2's signature/hash-chain checks. Replicas reject at the `pre-prepare` stage and do not send `prepare`. The round fails to reach quorum; a **view-change** is triggered — see UC-6-D for the concrete simplified mechanism now specified.
- **UC-6-E2: Equivocating byzantine node (Byzantine fault — safety risk)** — a faulty `ValidatorSet` member sends conflicting `prepare`/`commit` messages to different peers for the same (view, seq) but different claimed block hashes. Honest nodes count votes only per exact-matching (view, seq, block_hash) tuple and deduplicate/ignore additional or conflicting messages from the same `node_id` beyond the first counted vote, preventing double-counting toward quorum. This is logged/reported as an **equivocation/Byzantine event**, distinct from a crash-fault report (see UC-6-E5), surfaced in `quorum_status` (UC-12) and in metrics/logs (PRD FR-15, closes M-9).
- **UC-6-E3: Commit without valid prepare quorum** — a byzantine node sends a `commit` message without the protocol having actually reached prepare-quorum. Honest nodes enforce protocol-phase ordering and ignore/reject such out-of-sequence commits.
- **UC-6-E4: Quorum timeout** — 2f+1 matching messages (over the `ValidatorSet`) are never reached within a configured timeout (network issue, or too many faulty/silent nodes). The round times out and the simplified view-change (UC-6-D) is initiated, rather than hanging indefinitely.
- **UC-6-E5: Fault tolerance exceeded — crash fault (liveness loss, not Byzantine)** — 2 of 4 `ValidatorSet` members are stopped/unresponsive (f=2 exceeds the tolerated f=1 for n=4). The network cannot reach 2f+1=3 matching commits. The system explicitly reports **loss of quorum due to unreachable peers** (a crash-fault / liveness classification, e.g. `quorum_status` reflecting "insufficient responsive replicas") — distinct and separately labeled from the Byzantine/equivocation classification in UC-6-E2 (closes M-9) — rather than silently hanging with no observable state (directly matches the Epic 3 acceptance criterion). No wrong block is ever finalized in this case; consensus simply stalls.

### Simplified View-Change (closes M-6 — documented, intentional simplification)
- **UC-6-D: Deterministic round-robin view-change.** Primary election is `primary = view_number mod n`, computed over the `ValidatorSet`. When the current primary fails to drive a round to completion within a configured timeout (UC-6-E1 or UC-6-E4), nodes increment the view number and deterministically select the next primary via the round-robin formula. This implementation explicitly does **NOT** include a state-transfer, checkpoint, or watermark protocol as found in full PBFT specifications — this is an intentional, scoped-down simplification for the thesis prototype, documented here and at the implementation site, not an undocumented gap.

### Edge Cases
- **UC-6-EC1**: Exactly 1 of 4 `ValidatorSet` members is stopped (f=1, tolerated — a crash fault within tolerance). Consensus still finalizes correctly using the remaining 3 members' matching commits (directly matches the Epic 3 acceptance criterion); this is reported as normal operation, not as any fault event.
- **UC-6-EC2**: Repeated primary failures cause successive view-changes ("view-change storm") under the round-robin mechanism (UC-6-D). Since there is no checkpoint/watermark protocol, the system must eventually converge on a working primary within the `ValidatorSet` or clearly and persistently report the failure condition rather than looping silently forever.
- **UC-6-EC3**: A `prepare`/`commit` message is duplicated or arrives out of order due to WebSocket-level retransmission (including from the bidirectional `PeerConnectionManager` connections, UC-6-F). Protocol handling is idempotent — a duplicate message does not corrupt the vote count or cause double-processing.

### Data Requirements
- **Input**: Candidate block (hashed preimage), view number, sequence number, per-message `NodeKeyPair` signatures from `ValidatorSet` members.
- **Output**: Finalized `Block` with hashed preimage `proposer_id` (the primary's `node_id` for this round — v1.2, the single source of truth for proposer identity, present in the preimage for both PoW and PBFT) and `sealed_consensus = {view_number}` (`primary_id` is intentionally NOT duplicated here in v1.2, since `proposer_id` already covers it), plus attestation fields `proposer_signature` and `commit_signatures[]` (≥2f+1 `ValidatorSet` attestations, attached after hashing) — or an explicit round-failure/quorum-loss status distinguishing crash-fault vs. Byzantine-fault causes.
- **Side Effects**: Local chain append on success; metrics recorded (round-trip/message counts, UC-9); view-change state updated on failure per UC-6-D.

---

## UC-7: New Block Broadcast and Peer Adoption

**Actor**: Node process (broadcasting node), peer nodes (receiving)
**Preconditions**: Each node's `PeerConnectionManager` (PRD FR-12, closes M-5) has established WebSocket connections to its peers — every node is simultaneously a WS server (accepting inbound connections) and a WS client (maintaining outbound connections to every `PeerInfo` peer and every `ValidatorSet` member)
**Trigger**: A node finalizes a new block (via UC-5 or UC-6)

### Primary Flow (Happy Path)
1. The finalizing node's `PeerConnectionManager` pushes the new block over `WS /ws/blocks` to all connected peers in real time, using whichever connection direction (inbound or outbound) is currently established for each peer — fan-out is not limited to peers that happened to dial in.
2. Each receiving peer validates the block (Epic 2 hash-chain + `proposer_signature` checks) against its own current tip.
3. If valid and it correctly extends the peer's current tip, the peer appends it directly (a fast path that avoids a full chain-sync round-trip).

**Postconditions**: All connected, correctly-functioning peers converge on the same new tip shortly after broadcast.

### Alternative Flows
- **UC-7-A: Reconnect-with-backoff fallback (closes M-5)** — a peer whose WS connection was temporarily down misses the broadcast; the `PeerConnectionManager` on both sides reconnects automatically with capped exponential backoff, and once reconnected the peer falls back to REST chain-sync (UC-3) to catch up on any missed blocks. Per-peer connection health (up/reconnecting/down) is exposed for metrics (UC-9) and `GET /node/info` (UC-12).

### Error Flows
- **UC-7-E1: Broadcast block fails validation on a receiving peer** — bad `proposer_signature`/hash-chain link. The peer rejects the block outright: it does NOT append it and does NOT re-broadcast it further, and flags/logs the originating peer as a source of an invalid block (directly matches the Epic 3 acceptance criterion "rejects it and does not re-broadcast it").
- **UC-7-E2: Broadcast block does not extend the peer's current tip** — the peer is behind, or on a differing fork. The peer does not use the fast-append path; instead it falls back to full chain-sync (UC-3), which applies the full-revalidation rule if the divergence is before the peer's tip (UC-3 step 3).

### Edge Cases
- **UC-7-EC1**: The same broadcast block arrives twice (duplicate delivery), e.g. once over an inbound and once over an outbound `PeerConnectionManager` connection to the same peer. Handling is idempotent — the second copy is a no-op if the block is already appended.
- **UC-7-EC2**: Many peer connections receive the broadcast simultaneously (fan-out over both inbound and outbound connections). No data race or state corruption occurs in the per-node append logic under this concurrent load.

### Data Requirements
- **Input**: Finalized, attested `Block` pushed over WebSocket.
- **Output**: Peer's local chain updated (on success) or unchanged (on rejection/fallback).
- **Side Effects**: Local chain append; possible fallback chain-sync request; `PeerConnectionManager` reconnect/backoff state updated on connection loss.

---

## UC-8: Reject Invalid or Unsigned Proposals/Blocks

**Actor**: Node process (validating any inbound block/proposal, regardless of source: peer broadcast, PBFT pre-prepare, or chain-sync response)
**Preconditions**: Node is online and receiving an inbound block/proposal message
**Trigger**: Any incoming block or proposal message

### Primary Flow (Happy Path)
1. Node runs Epic 2's `proposer_signature` verification (the proposing/broadcasting node signed the block's canonical preimage, which now includes `proposer_id`, with its `NodeKeyPair`) and hash-chain validation (including, for PBFT, `commit_signatures[]` verification against `ValidatorSet` members), using the node's injected key resolver/`expected_difficulty`/`ValidatorSet` constructed per UC-14, before accepting.
2. If all checks pass, the block/proposal is accepted and processed per the relevant flow (UC-6 for PBFT messages, UC-7 for direct broadcasts).

**Postconditions**: Only cryptographically authenticated, structurally valid blocks/proposals are ever accepted or propagated.

### Error Flows (this use case is primarily its own error-path validator)
- **UC-8-E1: Unsigned proposal** — the incoming message has no `proposer_signature` field, or it is empty. Rejected outright without further processing (matches the NFR requiring authenticated node-to-node messages).
- **UC-8-E2: Signature by an unrecognized key** — the proposal is signed by a `NodeKeyPair` that does not belong to any known peer/`ValidatorSet` member's public key (spoofing attempt). Rejected.
- **UC-8-E3: Valid signature, broken chain-link** — the `proposer_signature` checks out, but the block's `previous_hash` or `merkle_root` is inconsistent with the chain it claims to extend. Rejected with `failure_type = "link"` or `"merkle"` (Epic 2 UC-4).
- **UC-8-E4: Conflicting finalization at the same index (equivocation)** — the proposal conflicts with a block this node has already finalized at the same index. Rejected; the first-finalized block wins, and the conflicting proposal is not processed further. If the conflicting proposals came from a `ValidatorSet` member, this is logged as a Byzantine/equivocation event (UC-6-E2), distinct from a crash-fault report.

### Edge Cases
- **UC-8-EC1**: A proposal arrives from a `node_id` not present in the receiving node's `PeerInfo` list (never registered, per UC-1) nor in its `ValidatorSet` (for PBFT messages). Rejected unless/until registration/`ValidatorSet` membership is established.
- **UC-8-EC2**: A previously valid but now-stale proposal (for an index that has since been finalized by other means) is replayed later. Rejected as stale/duplicate; not re-processed as if new.

### Data Requirements
- **Input**: Inbound block/proposal message, sender's claimed identity/signature.
- **Output**: Accept (pass to UC-6/UC-7) or reject (with reason).
- **Side Effects**: None on rejection (no chain mutation, no re-broadcast); logging/flagging of the offending peer for later analysis (used by Epic 5).

---

## UC-9: Consensus Metrics Retrieval

**Actor**: Client (Epic 4 UI, Epic 5 chart-generation scripts, or an operator)
**Preconditions**: Node has processed zero or more blocks
**Trigger**: `GET /metrics/consensus`

### Primary Flow (Happy Path)
1. Caller requests `GET /metrics/consensus`.
2. Node returns per-block finalization timestamps, per-block time-to-finalize, and algorithm-specific counters (PoW: hash attempts and a node-local hash-rate sample, used by Epic 5's hash-power-share Sybil metric; PBFT: message round-trip counts).

**Postconditions**: Caller has data sufficient to compute/plot finalization-latency comparisons (feeds Epic 5's charts).

### Alternative Flows
- **UC-9-A: Range query** — caller requests metrics for only the last N blocks, if a range parameter is supported.

### Error Flows
- **UC-9-E1**: No blocks finalized yet (fresh node). Returns an empty metrics array/list — not an error.

### Edge Cases
- **UC-9-EC1**: Metrics requested while a block/round is mid-flight (not yet finalized). Only completed blocks are included; the in-progress round is excluded from the response, not reported with partial/misleading data.
- **UC-9-EC2**: Extremely high difficulty produces very large hash-attempt counts. No integer overflow or truncation in the reported value.

### Data Requirements
- **Input**: Optional range parameters.
- **Output**: List of `ConsensusMetric` (`block_index`, `algorithm`, `proposed_at`, `finalized_at`, `attempts_or_rounds`, and — PoW only — `hash_rate`).
- **Side Effects**: None (read-only).

---

## UC-10: Docker-Compose Multi-Node Network Bootstrap

**Actor**: Network operator (thesis author) running `docker-compose up`
**Preconditions**: A `docker-compose.yml` defines a configurable number of node services (minimum 4) on a shared Docker network
**Trigger**: `docker-compose up`

### Primary Flow (Happy Path)
1. All configured node containers start.
2. Each node auto-registers with its configured seed peer(s) (UC-1).
3. Within a short convergence window, the network reaches full (or near-full) peer awareness across all nodes.
4. Each node is reachable at a distinct host:port.

**Postconditions**: An n-node network is operational and ready to accept submissions (UC-4).

### Alternative Flows
- **UC-10-A**: Scaling to more than the minimum 4 nodes via a configurable count.

### Error Flows
- **UC-10-E1: Port conflict** — two containers are configured to bind the same host port. `docker-compose up` fails to start with a clear error surfaced to the operator.
- **UC-10-E2: One container fails to start (crash loop)** — e.g., misconfiguration in one node's environment. The remaining nodes continue operating with a reduced peer set and do not hang indefinitely waiting for the failed node.

### Edge Cases
- **UC-10-EC1**: Configured node count is below the safe minimum for the configured PBFT fault tolerance (n < 3f+1 for the intended f). The system documents/warns about this invalid fault-tolerance configuration at startup rather than silently running an under-provisioned, unsafe PBFT cluster.

### Data Requirements
- **Input**: `docker-compose.yml`, per-node environment/config (consensus mode, seed peers, difficulty, etc.).
- **Output**: Running multi-container network.
- **Side Effects**: Container creation, shared Docker network creation.

---

## UC-11: Consensus Mode Configuration at Startup

**Actor**: Node process (self, at startup), operator (supplying config)
**Preconditions**: Node configuration (environment variable or config file) specifies the desired consensus mode
**Trigger**: Node process startup

### Primary Flow (Happy Path)
1. Node reads its configured consensus mode (`pow` or `pbft`) at startup.
2. Node initializes the corresponding consensus engine implementation.
3. For the lifetime of the process, the node's behavior (mining loop vs. proposal/prepare/commit rounds) follows the configured mode.

**Postconditions**: The same codebase runs correctly in either mode, enabling reproducible A/B comparison for the thesis.

### Error Flows
- **UC-11-E1: Invalid/unrecognized mode value** — e.g., a typo in config. Node fails to start with a clear, explicit error (fail-fast) rather than silently defaulting to an unintended mode.
- **UC-11-E2: Missing config entirely** — no consensus mode specified. Node applies a documented, explicit default (e.g., PoW) rather than behaving unpredictably; if no safe default is defined, the node instead fails fast with a clear message — this default-vs-fail-fast choice must be documented and consistent across the codebase.

### Edge Cases
- **UC-11-EC1: Mixed-mode cluster misconfiguration** — some nodes are started as `pow`, others as `pbft`, within what was intended to be a single homogeneous cluster. Nodes must detect and reject fundamentally incompatible blocks/messages from mismatched-mode peers (e.g., a PoW node receiving PBFT `pre-prepare` messages, or a PBFT node receiving a PoW-style nonce-only block) rather than silently corrupting their local consensus state or crashing unhandled.

### Data Requirements
- **Input**: Consensus-mode configuration value.
- **Output**: Initialized consensus engine (PoW or PBFT).
- **Side Effects**: None beyond process initialization.

---

## UC-12: Query Node Status via `GET /node/info` (NEW, closes M-10)

**Actor**: Client (Epic 4 UI for consensus-mode/chain-validity display, Epic 5 attack scripts for verification, or an operator/monitoring tool)
**Preconditions**: Node is online (any state — including a freshly started node with zero blocks)
**Trigger**: `GET /node/info`

### Primary Flow (Happy Path)
1. Caller requests `GET /node/info`.
2. Node returns a single-call health/identity summary: `{node_id, algorithm, n, f, node_public_key, tip_index, chain_valid, first_invalid_index, quorum_status}`.
   - `node_id`, `algorithm` (`"pow"`|`"pbft"`), `n`/`f` (from the node's `ValidatorSet`, UC-1-C — for PoW nodes `n`/`f` reflect the configured `ValidatorSet` size even though PoW does not use it for quorum), `node_public_key` (this node's `NodeKeyPair` public key).
   - `tip_index`, `chain_valid`, `first_invalid_index` — **v1.2: read from a continuously, incrementally-updated validity cache**, NOT recomputed by a full chain revalidation on every call. The cache is updated whenever a block is appended or the chain is replaced via sync (UC-3/UC-14), using the identical Epic 2 UC-4 checklist (injected resolver, `expected_difficulty`/`ValidatorSet`, including PBFT `commit_signatures[]` quorum verification) that backs live proposal validation and chain-sync — so the *content* of the check is identical to a full revalidation, but the *cost* of this endpoint is independent of chain length (closes second-round MINOR — prior revalidation-cost concern).
   - `quorum_status` — for PBFT, distinguishes healthy quorum vs. crash-fault quorum loss (UC-6-E5) vs. Byzantine/equivocation event detected (UC-6-E2), per PRD FR-15 (closes M-9), and now also reflects the Byzantine-fault event of a same-height PBFT fork (UC-3-EC1, v1.2); for PoW, reflects mining/liveness status.

**Postconditions**: Caller has an authoritative, single-request snapshot of the node's identity, chain health, and consensus status, served at a cost independent of chain length.

### Alternative Flows
- **UC-12-A: Fresh node, zero blocks beyond genesis finalized** — `tip_index` reflects only the genesis block (never a zero-block/empty chain, v1.2 — genesis always exists from process startup), `chain_valid = true` (validity cache initialized at boot per Epic 2 UC-4-EC1/EC2), `quorum_status` reflects normal/idle state. This endpoint remains cheap and meaningful even before any blocks beyond genesis exist — closing the prior "empty metrics list on a fresh node" ambiguity that `GET /metrics/consensus` alone had for mode/status determination, and requiring no expensive computation to answer.

### Error Flows
- **UC-12-E1: Chain is invalid at query time** — the validity cache reports `chain_valid = false` and `first_invalid_index` populated with the index of the earliest failing block (last computed by the same Epic 2 UC-4 checklist, on the append/sync event that introduced the failure). This is a normal, well-formed response (HTTP 200), not an endpoint failure — it reports a genuine chain-health problem for the caller to act on.

### Edge Cases
- **UC-12-EC1**: Node is mid-view-change (PBFT) at query time. `quorum_status` reflects the in-progress view-change condition rather than a misleading "healthy" or "lost" binary state.
- **UC-12-EC2**: A PoW node reports `n`/`f` from its configured `ValidatorSet` even though PoW consensus never uses `ValidatorSet` for quorum — this is intentional (the field exists uniformly across both algorithms for a consistent response shape) and must not be misread as PoW having PBFT-style quorum semantics.
- **UC-12-EC3 (NEW, v1.2)**: `GET /node/info` is called repeatedly on a node with a very long chain (hundreds of blocks). Latency does not measurably scale with chain length, since the endpoint reads the pre-computed validity cache rather than re-running full chain validation per call — this is directly testable by comparing call latency on a short vs. long chain.

### Data Requirements
- **Input**: None.
- **Output**: `{node_id, algorithm, n, f, node_public_key, tip_index, chain_valid, first_invalid_index, quorum_status}`.
- **Side Effects**: None (read-only; reads the incrementally-maintained validity cache, updated by UC-3/UC-5/UC-6/UC-14's append/sync flows — never triggers a fresh full chain-validation pass itself).

---

## UC-13: Document Lookup by Hash via `GET /documents/{hash}` (relocated from Epic 4, renamed from `GET /documents/search?hash=`)

**Actor**: Client (Epic 4's Verify page, Epic 5 attack/verification scripts, or any direct API caller)
**Preconditions**: Node is online with a local chain (possibly genesis-only)
**Trigger**: `GET /documents/{hash}`, where `{hash}` is a path parameter validated against `^[0-9a-f]{64}$` (PRD FR-19)

### Primary Flow (Happy Path — found)
1. Caller requests `GET /documents/{hash}` with a well-formed 64-character hex hash.
2. Node searches its local chain for a `DocumentRecord` matching `document_hash`.
3. If found, node returns HTTP 200 with: issuer identity (`issuer_id`), issuance timestamp (`issued_at`), the containing block's `index`, and Merkle-inclusion-proof data (sibling hash path, per Epic 2 UC-5) sufficient for the caller to independently verify inclusion against the block's `merkle_root`.

**Postconditions**: Caller has a complete, independently-verifiable record of the document's issuance, without needing to fetch the full chain.

### Alternative Flows
- **UC-13-A: Not found** — the hash does not match any `DocumentRecord` on this node's local chain. Node returns HTTP 404 via the standard error envelope (PRD FR-19), explicitly distinguishing "not found" from a server error — the prior v1.0 `GET /documents/search?hash=` query-parameter shape returned an ambiguous empty/200 response for this case, which this endpoint's 404 semantics now correct.

### Error Flows
- **UC-13-E1: Malformed hash path parameter** — the `{hash}` segment does not match `^[0-9a-f]{64}$` (wrong length, non-hex characters, uppercase, etc.). Node rejects the request with a 400-level Pydantic validation error in the standard error envelope, before performing any chain search.
- **UC-13-E2: Node's local chain is itself invalid at lookup time** — the node's chain fails validation (Epic 2 UC-4). The node still attempts the lookup but the response should be considered alongside `GET /node/info`'s `chain_valid`/`first_invalid_index` fields (UC-12) — a "found" result from a node with a known-invalid chain is not authoritative and callers (e.g., Epic 4) are expected to cross-check `GET /node/info` before trusting a "found" result at face value.

### Edge Cases
- **UC-13-EC1 (v1.2 — redefined; duplicates across finalized blocks are now structurally impossible)**: Under the v1.2 single duplicate-hash policy (UC-4-E6), a `document_hash` can never appear in two different finalized blocks — `POST /documents` rejects any resubmission of an already-finalized hash with `409` before it ever reaches batch construction. This endpoint therefore never needs "earliest match" tie-break logic; if a lookup were ever to find the same `document_hash` in two blocks, that would indicate a data-integrity bug (e.g., the `409` check was bypassed via direct chain-store mutation, see Epic 5 UC-4) and should be surfaced as an inconsistency, not silently resolved by returning "the first one."
- **UC-13-EC2**: The containing block's document-record content was tampered with in storage (Epic 2 UC-7 scenario). The endpoint still returns "found" with the (now-inconsistent) stored data, but the returned Merkle-proof data fails independent verification against the block's stored `merkle_root` when checked by the caller — demonstrating that this endpoint reports raw stored data plus proof material, and it is the caller's (or Epic 4's) responsibility to verify the proof, not an implicit guarantee of validity baked into a "found" response.

### Data Requirements
- **Input**: `hash` path parameter.
- **Output**: `{issuer_id, issued_at, block_index, merkle_proof}` (found) or HTTP 404 error envelope (not found).
- **Side Effects**: None (read-only).

---

## UC-14: Construct and Inject the Key Resolver for Chain Validation (NEW in v1.2, closes second-round CRITICAL — key registries; resolver contract made time-aware in v1.3)

**Actor**: Node process (self) — an internal, cross-cutting mechanism consumed by UC-3 (chain sync), UC-6 (PBFT commit), UC-8 (proposal rejection), and UC-12 (`GET /node/info` validity cache)
**Preconditions**: The node has loaded its `IssuerRegistry` (UC-1-D) and `ValidatorSet` (UC-1-C, including any `retired_at`-marked entries) at boot
**Trigger**: Node boot, and any subsequent change to `ValidatorSet`/`IssuerRegistry` configuration

### Primary Flow (Happy Path)
1. At boot, the node reads its `IssuerRegistry` (`issuer_id → public_key`, network-wide per v1.3 — UC-1-D) and its full `ValidatorSet` (`node_id → public_key`, including entries with a non-null `retired_at`).
2. The node constructs a single combined **key resolver** object exposing two time-aware functions (v1.3 — the resolver contract is time-aware, not single-valued, because a single-valued `node_id`/`issuer_id → public_key` map cannot represent both a retired and a currently-active key for the same identity): `resolve_node_key(node_id, at_timestamp) → public_key` (covering both active and retired `ValidatorSet` entries, selecting whichever key was active — per `retired_at` — at `at_timestamp`) and `resolve_issuer_key(issuer_id, at_timestamp) → public_key` (from `IssuerRegistry`, likewise selecting the issuer key active at `at_timestamp` where an issuer key has a rotation history).
3. The node injects this resolver — plus, for PoW mode, its boot-configured `expected_difficulty`, and for PBFT mode, its `ValidatorSet` (`n`, `f`, and the node-key resolver) — into every call it makes to Epic 2's chain-validation function (Epic 2 UC-4): chain-sync validation (UC-3), live proposal/block validation (UC-6/UC-8), and the validity-cache refresh backing `GET /node/info` (UC-12). Each call passes the relevant block's own `timestamp` as `at_timestamp`.
4. Epic 2's chain-validation function never looks up keys or policy itself (no registry access, no network call) — it only ever receives this resolver/difficulty/`ValidatorSet` as injected parameters, preserving the dependency direction Epic 3 → Epic 2 only.

**Postconditions**: Every Epic 2 chain-validation call this node makes — regardless of trigger (proposal, sync, cache refresh) — uses the identical, up-to-date resolver, so validation results are consistent across all call sites.

### Alternative Flows
- **UC-14-A: Resolver rebuild on `ValidatorSet`/`IssuerRegistry` change** — if the node's configuration is updated at runtime (e.g., an operator-triggered reload after a validator rotation), the node reconstructs the combined resolver from the updated registries and the change takes effect for all subsequent validation calls; in-flight validations already using the prior resolver snapshot are not retroactively invalidated.

### Error Flows
- **UC-14-E1: Requested `node_id`/`issuer_id` not present in either registry** — `resolve_node_key`/`resolve_issuer_key` returns "not found" for that key at any `at_timestamp` rather than throwing or defaulting to `None`-as-valid; the calling Epic 2 validation treats this as a signature failure (`failure_type = "signature"`, Epic 2 UC-4-EC5).
- **UC-14-E2: `IssuerRegistry` or `ValidatorSet` config file missing/malformed at boot** — node fails to start with a clear, explicit error (fail-fast), since an incomplete resolver would silently weaken chain-validation guarantees for every subsequent call.

### Edge Cases
- **UC-14-EC1**: A `ValidatorSet` entry is retired (`retired_at` set) but its `NodeKeyPair` public key is still present in the resolver's map. `resolve_node_key(node_id, at_timestamp)` called with a timestamp at or before `retired_at` still returns the old key, so blocks proposed/attested to before the rotation continue to validate successfully (Epic 2 UC-4-EC-style historical validation); the entry is excluded from active `n`/`f` quorum-member counting (UC-6) but remains resolvable for signature checks. Called with a timestamp after rotation, the resolver returns the new active key for that same `node_id` — demonstrating the resolver's time-aware contract (Epic 3 acceptance criterion: `resolve_node_key` returns two different keys for the same `node_id` at two different `at_timestamp` values straddling the rotation).
- **UC-14-EC2**: A single node is configured with more than one `IssuerRegistry` entry (multi-issuer support, general case even though this thesis's scope typically configures one shared issuer identity across all nodes). `resolve_issuer_key` correctly disambiguates by `issuer_id`, not by node identity.

### Data Requirements
- **Input**: `IssuerRegistry` config (network-wide, v1.3), `ValidatorSet` config (including `retired_at` entries), boot-time `expected_difficulty` (PoW) / `ValidatorSet` (PBFT).
- **Output**: A combined, injectable, time-aware key-resolver object (`resolve_node_key(node_id, at_timestamp) → public_key`, `resolve_issuer_key(issuer_id, at_timestamp) → public_key`) plus the algorithm-specific injected parameters, consumed by every Epic 2 UC-4 call site.
- **Side Effects**: None persistent — an in-memory construct, rebuilt on config change (UC-14-A).
