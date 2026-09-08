# Test Cases: Consensus & Node Network (Epic 3)

> Based on [PRD](../PRD.md) and [Use Cases](../use-cases/consensus_network_use_cases.md)

This document covers the multi-node network layer: peer registration/discovery, REST chain synchronization, WebSocket block/PBFT-message broadcast, PoW and PBFT consensus, and docker-compose deployment (PRD Epic 3). Every UC scenario in `consensus_network_use_cases.md` (v1.3) is mapped below. Given this thesis's central contribution, extra weight is given to: the `ValidatorSet` vs. `PeerInfo` separation (Sybil-registering extra peers must NOT inflate quorum), the PBFT quorum-counting rule (primary's own pre-prepare counts toward its own prepare), the simplified round-robin view-change, the PoW-only fork tie-break (a same-height PBFT fork is a Byzantine event, never silently resolved), full chain revalidation on divergent-fork sync vs. incremental on strict extension, `GET /node/info`'s incrementally-updated validity cache, and the error envelope / input validation / CORS / pagination cross-cutting requirements.

---

## 1. Node Startup and Peer Registration (UC-1)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-1.1 | UC-1 primary | Node A registers with node B via `POST /peers/register` with `{node_id, host, port, public_key}` | B adds A to its `PeerInfo` list (records `last_seen`) and returns its current peer list; A merges it |
| TC-1.2 | UC-1-A | Node starts with multiple configured seed peers | Node registers sequentially with each, accumulating peer knowledge from each |
| TC-1.3 | UC-1-C (core C-4 test) | Node boots with a fixed `ValidatorSet` config (`n`, derived `f`) | `ValidatorSet` is logged at boot; is never mutated at runtime; is never derived from or updated by `PeerInfo` registrations |
| TC-1.4 | UC-1-C | A `ValidatorSet` entry is rotated (old key marked `retired_at`, new key added) | Old entry is retained (not deleted) with `retired_at` set; remains resolvable for historical signature verification |
| TC-1.5 | UC-1-D | Node boots with a configured `IssuerRegistry` (`issuer_id → public_key`) | Registry is loaded and logged at boot alongside `ValidatorSet` |
| TC-1.6 | UC-1-D | Inspect `IssuerRegistry` configuration across all nodes in the demo network | Every node is configured with the identical single shared `issuer_id`/public key (thesis-scope decision) |
| TC-1.7 | UC-1-E1 | Configured seed peer's container is not yet reachable at startup (cold-start race) | Node retries with backoff; does not crash or give up permanently |
| TC-1.8 | UC-1-E2 | The same `node_id` registers again (e.g., after restart) | Existing `PeerInfo` entry's `last_seen`/`host`/`port` is updated; no duplicate entry created |
| TC-1.9 | UC-1-E3 | Registration payload is missing `public_key` or `host`, or `public_key` fails Pydantic validation | Rejected with a 400-level validation error in the standard error envelope |
| TC-1.10 | UC-1-EC1 | A node attempts to register itself (`node_id` equals the receiving node's own id) | Self-registration is rejected/ignored |
| TC-1.11 | UC-1-EC2 (core C-4 test) | Flood a node with a very large number of `POST /peers/register` calls (Sybil-style `PeerInfo` growth) | Node does not crash or exhaust memory; critically, the PBFT quorum threshold (verified via UC-6) remains completely unaffected by this growth |

---

## 2. List Known Peers (UC-2)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-2.1 | UC-2 primary | Call `GET /peers` on a node with several registered peers | Returns the current `PeerInfo` list only; does NOT reflect `ValidatorSet` membership |
| TC-2.2 | UC-2-E1 | Call `GET /peers` on a freshly started node with no registrations | Returns an empty list, not an error |

---

## 3. Chain Synchronization (UC-3)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-3.1 | UC-3 primary (simple extension) | Node B's chain is a strict, non-diverging extension of node A's current tip | A validates only the new blocks incrementally from its tip forward; adopts B's chain if valid and longer |
| TC-3.2 | UC-3 primary (M-14 closure) | Node B's chain diverges from node A's local chain before A's current tip | A runs FULL chain-validation from genesis over B's entire incoming chain — incremental from-the-tip validation is never used for this case |
| TC-3.3 | UC-3 primary (single checklist) | Compare the validation checklist actually executed during chain-sync against the checklist executed during live proposal validation and `GET /node/info` cache refresh, for a PBFT chain | Identical checklist (including `commit_signatures[]` quorum verification) is used in all three; chain-sync never applies a lighter check |
| TC-3.4 | UC-3-A | A node requests only blocks after its current tip index (range sync) for a simple-extension case | Efficient partial sync succeeds; if the same request instead reveals a divergence before the tip, full revalidation is triggered regardless of the range originally requested |
| TC-3.5 | UC-3-B | Compare two PBFT chains of differing raw length but where the shorter one has a higher finalized height | The finalized-height rule (not raw length) determines which chain is adopted |
| TC-3.6 | UC-3-D | Request `GET /chain?from=10&to=20` | Returns exactly that bounded range of blocks, subject to the server-enforced max page size |
| TC-3.7 | UC-3-E1 | Peer B returns a chain that fails Epic 2's hash-chain/signature checks | A rejects the entire sync attempt, keeps its own local chain, and flags B as a potentially malicious/faulty peer |
| TC-3.8 | UC-3-E2 | Sync request to peer B times out / connection fails | A's sync attempt fails gracefully; A continues on its local chain and retries later |
| TC-3.9 | UC-3-E3 | Peer B's response is not valid JSON, is truncated mid-transfer, or fails Pydantic validation | A rejects the response via the standard error envelope, without crashing |
| TC-3.10 | UC-3-E4 | A caller requests a `?from=&to=` range larger than the configured max page size | B returns either a truncated page or a validation error — never an unbounded full-chain dump |
| TC-3.11 | UC-3-EC1 (PoW tie-break) | Two peers report equal-length, differing valid PoW chains | The chain whose tip has the LOWEST `block_hash` (unsigned-integer/lexicographic-hex comparison) is deterministically selected, regardless of arrival order ("first-observed" tie-break is never used) |
| TC-3.12 | UC-3-EC1 (PBFT — MUST NOT tie-break) | Two differently-finalized blocks are observed at the same height on a PBFT chain | The node MUST NOT silently pick one via lowest-hash or any tie-break; it reports/logs the condition as a Byzantine-fault/safety-violation event and surfaces it via `quorum_status` |
| TC-3.13 | UC-3-EC2 | A sync request arrives while the node is mid-mining or mid-PBFT-round | The in-progress consensus round is abandoned/restarted cleanly against the newly adopted chain; no corrupted state results |
| TC-3.14 | UC-3-EC3 | A node far behind performs a full historical sync via repeated paginated `GET /chain?from=&to=` requests | Large-transfer/timeout handling completes without hanging indefinitely |

---

## 4. Submit a Document for Issuance (UC-4)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-4.1 | UC-4 primary — PoW | Submit `{hash, metadata}` to a PoW node | Node duplicate-checks, server-side signs with its `IssuerKeyPair`, queues the record, begins mining, and responds with an accepted/queued acknowledgment |
| TC-4.2 | UC-4 primary — PBFT | Submit `{hash, metadata}` to a non-primary PBFT node | Receiving node performs the duplicate check and signs the record itself (with its own configured `issuer_id`); forwards the ALREADY-SIGNED record to the primary; `issuer_id`/`signature` are never reassigned by the eventual proposer |
| TC-4.3 | UC-4-A | Submit a batch of multiple documents together vs. a single document | Both follow the identical flow; each hash is independently duplicate-checked before batching |
| TC-4.4 | UC-4-E1 | Submit a request body that includes a `signature` field (or any pre-signed `DocumentRecord` shape) | Rejected with a 400-level Pydantic validation error in the standard error envelope |
| TC-4.5 | UC-4-E2 | Submit to a non-primary PBFT node whose known primary is unreachable | Node either queues for retry or returns an explicit "no primary available" error — never silently dropped |
| TC-4.6 | UC-4-E3 | Submit a request missing `hash` or `metadata` entirely | Rejected with a 400-level validation error |
| TC-4.7 | UC-4-E4 | Submit to a node mid-shutdown or not yet done with initial chain sync | Rejected with a retry-later status rather than accepted into an inconsistent local state |
| TC-4.8 | UC-4-E5 | Submit a `hash` that does not match `^[0-9a-f]{64}$` | Rejected with a 400-level validation error, before any duplicate check |
| TC-4.9 | UC-4-E5 | Submit `metadata` exceeding the server-enforced maximum byte-length cap | Rejected with a 400-level validation error, before any duplicate check or queueing |
| TC-4.10 | UC-4-E6 (finalized) | Submit a `hash` that already appears in a finalized block anywhere in the local chain | Rejected with `409 Conflict` via the standard error envelope; no `DocumentRecord` is assembled or signed |
| TC-4.11 | UC-4-E6 (v1.3 broadened — pending/mempool) | Submit a `hash` that is already present in the node's current pending batch/mempool but NOT yet finalized | Also rejected with `409 Conflict` — verifies the v1.3-broadened duplicate-check scope |
| TC-4.12 | UC-4-EC1 | Submit a hash matching a finalized or pending duplicate | Always and only handled via the `409` rejection path (TC-4.10/TC-4.11) — there is no alternate no-op/silent-success behavior |
| TC-4.13 | UC-4-EC2 (concurrency) | Fire two concurrent submissions for the SAME hash at the same node simultaneously | The per-hash/global submission lock ensures only one wins the check-then-sign-then-queue sequence; the loser receives `409` |

---

## 5. Proof-of-Work Block Mining and Broadcast (UC-5)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-5.1 | UC-5 primary | Node mines a pending batch to find a nonce satisfying the configured difficulty | `block_hash` meets the target, `proposer_signature` attached, block finalized locally, broadcast over `WS /ws/blocks` |
| TC-5.2 | UC-5-A | Change the configured difficulty (no code changes) and remine | Time-to-finalize measurably scales with difficulty, verifiable via `GET /metrics/consensus` |
| TC-5.3 | UC-5-E1 | While node is still mining, a valid competing block for the same height arrives from a peer | Node abandons its own mining attempt, adopts the peer's block, re-queues its own pending batch if not included |
| TC-5.4 | UC-5-E2 | Broadcast fails to reach some peers (network partition/WS disconnect) | Those peers catch up later via chain sync rather than being permanently stuck |
| TC-5.5 | UC-5-EC1 | Two nodes find a valid nonce at nearly the same time | Temporary fork is resolved later via the longest-valid-chain rule during the next chain sync |
| TC-5.6 | UC-5-EC2 | Configure extremely low/zero difficulty | Immediate finalization; block is still fully valid |
| TC-5.7 | UC-5-EC3 | Configure extremely high difficulty | Mining loop remains interruptible when a peer's competing block arrives, rather than blocking indefinitely |

---

## 6. PBFT Block Proposal and Commit (UC-6)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-6.1 | UC-6 primary | Run a full pre-prepare → prepare → commit round on an n=4, f=1 `ValidatorSet` | Block is finalized identically and deterministically on every correct member |
| TC-6.2 | UC-6 (core C-4 test) | Register many additional `PeerInfo` peers, then run a normal PBFT round | The quorum threshold (2f+1) is unaffected; it is computed exclusively over the static `ValidatorSet`, never over `PeerInfo` count |
| TC-6.3 | UC-6 step 3 (M-7 closure) | Observe the primary's own vote-counting during a round it proposes | The primary's own `pre-prepare` counts as its implicit `prepare` vote — it does not separately send itself a `prepare` message to reach 2f+1 |
| TC-6.4 | UC-6-A | Configure a node as a pure replica (never primary in the tested round) | Node only responds to `pre-prepare`/`prepare`/`commit`; it never initiates a round |
| TC-6.5 | UC-6-B / UC-6-EC1 | Stop exactly 1 of 4 `ValidatorSet` members (f=1, within tolerance) | Consensus still finalizes correctly using the remaining 3 members' matching commits; reported as normal operation, not a fault event |
| TC-6.6 | UC-6-F | Establish connections where one peer only dialed inbound and another only outbound | Fan-out (`pre-prepare`/`prepare`/`commit`) reaches both regardless of connection direction; connection loss triggers reconnect with capped exponential backoff; per-peer health is exposed via `GET /node/info` |
| TC-6.7 | UC-6-E1 | Primary proposes a block that fails Epic 2's signature/hash-chain checks | Replicas reject at `pre-prepare`, send no `prepare`; round fails to reach quorum; a view-change is triggered |
| TC-6.8 | UC-6-E2 (central Byzantine test) | A faulty `ValidatorSet` member sends conflicting `prepare`/`commit` messages (same view/seq, different claimed `block_hash`) to different peers | Honest nodes count votes only per exact-matching (view, seq, block_hash) tuple, dedupe/ignore extra votes from the same `node_id`; event is logged as an equivocation/Byzantine event, distinct from a crash-fault report |
| TC-6.9 | UC-6-E3 | A byzantine node sends a `commit` without the protocol having reached prepare-quorum | Honest nodes enforce phase ordering and ignore/reject the out-of-sequence commit |
| TC-6.10 | UC-6-E4 | 2f+1 matching messages are never reached within the configured timeout | Round times out; simplified view-change (UC-6-D) is initiated rather than hanging indefinitely |
| TC-6.11 | UC-6-E5 (central crash-vs-Byzantine test) | Stop 2 of 4 `ValidatorSet` members (f=2, exceeding tolerated f=1) | Network cannot reach 2f+1=3 commits; system reports loss-of-quorum as a distinct CRASH-fault/liveness classification (never conflated with UC-6-E2's Byzantine label); no wrong block is ever finalized |
| TC-6.12 | UC-6-D | Current primary fails to drive a round to completion within timeout | Nodes increment the view number and deterministically select `primary = view_number mod n`; behavior documented as intentionally lacking state-transfer/checkpoint/watermark protocol |
| TC-6.13 | UC-6-EC2 | Repeated primary failures trigger successive view-changes ("view-change storm") | System eventually converges on a working primary within the `ValidatorSet`, or persistently and clearly reports the failure condition — never loops silently forever |
| TC-6.14 | UC-6-EC3 | A `prepare`/`commit` message is duplicated or arrives out of order (WS-level retransmission) | Protocol handling is idempotent; duplicate message does not corrupt the vote count or cause double-processing |

---

## 7. New Block Broadcast and Peer Adoption (UC-7)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-7.1 | UC-7 primary | Node finalizes a new block and pushes it over `WS /ws/blocks` to all connected peers | Each valid, correctly-extending peer fast-appends the block without a full chain-sync round-trip |
| TC-7.2 | UC-7-A | A peer's WS connection was temporarily down during a broadcast | `PeerConnectionManager` reconnects with capped exponential backoff; peer falls back to REST chain-sync to catch up; per-peer connection health is exposed |
| TC-7.3 | UC-7-E1 | Broadcast block fails validation on a receiving peer (bad signature/hash-chain link) | Peer rejects the block outright: does not append, does not re-broadcast, and flags/logs the originating peer |
| TC-7.4 | UC-7-E2 | Broadcast block does not extend the receiving peer's current tip (peer behind or on a differing fork) | Peer falls back to full chain-sync, applying the full-revalidation rule if the divergence is before the peer's tip |
| TC-7.5 | UC-7-EC1 | The same broadcast block arrives twice (once inbound, once outbound connection to the same peer) | Handling is idempotent; the second copy is a no-op since the block is already appended |
| TC-7.6 | UC-7-EC2 | Many peer connections receive the same broadcast simultaneously (high fan-out) | No data race or state corruption occurs in the per-node append logic |

---

## 8. Reject Invalid or Unsigned Proposals/Blocks (UC-8)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-8.1 | UC-8 primary | Validate an inbound block/proposal (peer broadcast, PBFT pre-prepare, or chain-sync response) using the node's injected resolver/`expected_difficulty`/`ValidatorSet` | Only passes and is accepted/processed if all checks succeed |
| TC-8.2 | UC-8-E1 | Inbound message has no `proposer_signature` field, or it is empty | Rejected outright without further processing |
| TC-8.3 | UC-8-E2 | Proposal is signed by a `NodeKeyPair` not belonging to any known peer/`ValidatorSet` member's public key | Rejected as a spoofing attempt |
| TC-8.4 | UC-8-E3 | `proposer_signature` checks out, but `previous_hash` or `merkle_root` is inconsistent with the claimed chain | Rejected with `failure_type = "link"` or `"merkle"` |
| TC-8.5 | UC-8-E4 | A proposal conflicts with a block already finalized by this node at the same index (equivocation) | Rejected; first-finalized block wins; if the conflicting proposal came from a `ValidatorSet` member, logged as a Byzantine/equivocation event |
| TC-8.6 | UC-8-EC1 | A proposal arrives from a `node_id` not in `PeerInfo` nor `ValidatorSet` | Rejected unless/until registration/`ValidatorSet` membership is established |
| TC-8.7 | UC-8-EC2 | A previously valid but now-stale proposal (for an already-finalized index) is replayed | Rejected as stale/duplicate; not reprocessed as new |

---

## 9. Consensus Metrics Retrieval (UC-9)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-9.1 | UC-9 primary | Call `GET /metrics/consensus` on a node that has finalized several blocks | Returns per-block finalization timestamps, time-to-finalize, and algorithm-specific counters (PoW: hash attempts + hash-rate; PBFT: message round-trip counts) |
| TC-9.2 | UC-9-A | Call the metrics endpoint with a range parameter (if supported) requesting only the last N blocks | Returns only the requested range |
| TC-9.3 | UC-9-E1 | Call `GET /metrics/consensus` on a fresh node with no finalized blocks | Returns an empty array/list, not an error |
| TC-9.4 | UC-9-EC1 | Call the endpoint while a block/round is mid-flight | Only completed blocks are included; the in-progress round is excluded, not reported with partial/misleading data |
| TC-9.5 | UC-9-EC2 | Configure extremely high difficulty producing very large hash-attempt counts | Reported value has no integer overflow or truncation |

---

## 10. Docker-Compose Multi-Node Network Bootstrap (UC-10)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-10.1 | UC-10 primary | Run `docker-compose up` with the minimum 4-node configuration | All containers start; each auto-registers with seed peers; network converges to full peer awareness; each node reachable at a distinct host:port |
| TC-10.2 | UC-10-A | Scale the compose config to more than 4 nodes | Network starts and converges correctly at the larger size |
| TC-10.3 | UC-10-E1 | Configure two containers to bind the same host port | `docker-compose up` fails to start with a clear error surfaced to the operator |
| TC-10.4 | UC-10-E2 | One container is misconfigured and crash-loops | Remaining nodes continue operating with a reduced peer set; no indefinite hang |
| TC-10.5 | UC-10-EC1 | Configure a node count below the safe minimum for the intended PBFT fault tolerance (`n < 3f+1`) | System documents/warns about the invalid fault-tolerance configuration at startup rather than silently running unsafe |

---

## 11. Consensus Mode Configuration at Startup (UC-11)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-11.1 | UC-11 primary | Start a node with `pow` configured, and separately with `pbft` configured | Node initializes the corresponding engine and follows that mode's behavior for the process lifetime |
| TC-11.2 | UC-11-E1 | Configure an invalid/unrecognized mode value (typo) | Node fails to start with a clear, explicit error; never silently defaults to an unintended mode |
| TC-11.3 | UC-11-E2 | Start a node with no consensus mode specified | Node applies its documented explicit default, or fails fast with a clear message if no safe default is defined |
| TC-11.4 | UC-11-EC1 | Mix `pow`-configured and `pbft`-configured nodes in what was intended to be one homogeneous cluster | Nodes detect and reject incompatible blocks/messages from mismatched-mode peers; no silent state corruption or unhandled crash |

---

## 12. Query Node Status via `GET /node/info` (UC-12)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-12.1 | UC-12 primary | Call `GET /node/info` on a running node | Returns all of `{node_id, algorithm, n, f, node_public_key, tip_index, chain_valid, first_invalid_index, quorum_status}` with correct values |
| TC-12.2 | UC-12 primary (validity cache) | Append/sync a new block, then immediately call `GET /node/info` | `chain_valid`/`first_invalid_index` reflect the cached state updated by the append/sync event, not a freshly recomputed full revalidation |
| TC-12.3 | UC-12-A | Call `GET /node/info` on a freshly started node with zero blocks beyond genesis | `tip_index` reflects the genesis block; `chain_valid = true`; `quorum_status` reflects normal/idle state |
| TC-12.4 | UC-12-E1 | Call `GET /node/info` while the validity cache reports the chain invalid | Returns HTTP 200 (not an endpoint failure) with `chain_valid = false` and `first_invalid_index` populated |
| TC-12.5 | UC-12-EC1 | Call `GET /node/info` while the node is mid-view-change (PBFT) | `quorum_status` reflects the in-progress view-change condition, not a misleading binary healthy/lost state |
| TC-12.6 | UC-12-EC2 | Call `GET /node/info` on a PoW node | Reports `n`/`f` from its configured `ValidatorSet` even though unused for PoW quorum — must not be misread as PBFT-style quorum semantics |
| TC-12.7 | UC-12-EC3 (central cache-cost test) | Measure `GET /node/info` latency on a short chain vs. a chain of several hundred blocks | Latency does not measurably scale with chain length |
| TC-12.8 | Cross-check (FR-25/FR-26) | Present a PBFT block with insufficient `commit_signatures[]` via both a chain-sync request AND a `GET /node/info` cache read | Both paths report `failure_type = "quorum"` / `chain_valid = false` consistently |

---

## 13. Document Lookup by Hash via `GET /documents/{hash}` (UC-13)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-13.1 | UC-13 primary | Request `GET /documents/{hash}` for a hash present on-chain | Returns HTTP 200 with issuer identity, issuance timestamp, containing block index, and Merkle-inclusion-proof data |
| TC-13.2 | UC-13-A | Request `GET /documents/{hash}` for a hash never issued | Returns HTTP 404 via the standard error envelope, explicitly distinguishing "not found" from a server error |
| TC-13.3 | UC-13-E1 | Request with a malformed hash path parameter (wrong length/non-hex/uppercase) | Rejected with a 400-level Pydantic validation error, before any chain search |
| TC-13.4 | UC-13-E2 | Request a lookup on a node whose chain is itself invalid at query time | The lookup is still attempted and returns raw stored data; caller is expected to cross-check `GET /node/info`'s `chain_valid`/`first_invalid_index` before trusting the "found" result |
| TC-13.5 | UC-13-EC1 | (Structural-integrity check) Force (via direct chain-store mutation) a `document_hash` to appear in two different finalized blocks and look it up | Surfaced as a data-integrity inconsistency, never silently resolved via "return the earliest match" |
| TC-13.6 | UC-13-EC2 | Look up a hash whose containing block's document-record content was tampered with in storage | Endpoint still returns "found" with the (inconsistent) stored data, but the returned Merkle-proof data fails independent verification against the block's stored `merkle_root` |

---

## 14. Construct and Inject the Key Resolver for Chain Validation (UC-14)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-14.1 | UC-14 primary | At boot, node reads `IssuerRegistry` and full `ValidatorSet` (including `retired_at` entries) | Constructs a combined resolver exposing `resolve_node_key(node_id, at_timestamp)` and `resolve_issuer_key(issuer_id, at_timestamp)` |
| TC-14.2 | UC-14 primary | Trigger chain-sync validation, live proposal validation, and the `GET /node/info` cache refresh in sequence | All three call sites receive the SAME resolver instance and the same injected `expected_difficulty`/`ValidatorSet`, each passing the relevant block's own `timestamp` as `at_timestamp` |
| TC-14.3 | UC-14 primary (dependency direction) | Inspect Epic 2's chain-validation function during any of the above calls | The function performs no registry lookup and no network call itself — it only ever receives injected parameters |
| TC-14.4 | UC-14-A | Update `ValidatorSet`/`IssuerRegistry` config at runtime (simulated operator reload) | Node reconstructs the combined resolver; subsequent validation calls use the updated resolver; in-flight validations using the prior snapshot are not retroactively invalidated |
| TC-14.5 | UC-14-E1 | `resolve_node_key`/`resolve_issuer_key` is asked to resolve an identity present in neither registry | Returns "not found" rather than throwing or defaulting to `None`-as-valid; calling validation treats this as `failure_type = "signature"` |
| TC-14.6 | UC-14-E2 | Start a node with a missing or malformed `IssuerRegistry`/`ValidatorSet` config file | Node fails to start with a clear, explicit error (fail-fast) |
| TC-14.7 | UC-14-EC1 (central time-aware resolver test) | Call `resolve_node_key(node_id, at_timestamp)` with a timestamp at/before a validator's `retired_at`, and again with a timestamp after the rotation | Returns the OLD key for the pre-rotation timestamp and the NEW key for the post-rotation timestamp for the same `node_id`; the retired entry is excluded from active `n`/`f` quorum-member counting but remains resolvable for signature checks |
| TC-14.8 | UC-14-EC2 | Configure a node with more than one `IssuerRegistry` entry (multi-issuer, general case) | `resolve_issuer_key` correctly disambiguates by `issuer_id`, not by node identity |

---

## 15. Cross-Cutting: Error Envelope, Input Validation, CORS, and Pagination

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-EV.1 | FR-19 | Trigger a validation error on each REST endpoint (`/peers/register`, `/documents`, `/chain`, `/node/info`, `/documents/{hash}`) | Every error response uses the exact `{"error": {"code", "message", "details"}}` envelope shape |
| TC-EV.2 | FR-19 | Submit a malformed hash-valued field (`document_hash`, `previous_hash`, `block_hash`) to every endpoint that accepts one | All are validated against `^[0-9a-f]{64}$` and rejected uniformly when malformed |
| TC-EV.3 | FR-19 | Submit `DocumentRecord.metadata` at, just under, and just over the server-enforced max byte-length cap | Within-limit accepted; over-limit rejected with a validation error |
| TC-EV.4 | NFR (CORS) | Send a cross-origin request from Epic 4's configured frontend origin, and separately from an unconfigured origin | Configured origin is allowed; CORS is tunable per environment (dev/demo) via config, not hardcoded to one origin |
| TC-EV.5 | FR-18 | Call `GET /chain` with no pagination parameters on a chain longer than the server's max page size | Never returns an unbounded full-chain dump; response is capped at the server-enforced max page size |
