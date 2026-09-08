# Use Cases: Blockchain Core Engine (Epic 2)

> Based on [PRD](../PRD.md) — Epic 2: Custom Blockchain Engine (Core)

> Updated 2026-09-07 (v1.3 pass): Revised UC-1, UC-2, UC-3, UC-4, UC-6, UC-8 to align with PRD v1.3 (architecture-review polish, FINAL). Key changes: UC-4's Primary Flow gains an explicit checklist step verifying each block's `DocumentRecord`(s) signature via the injected issuer resolver (`resolve_issuer_key(issuer_id, at_timestamp)`), failing with `failure_type = "signature"` on mismatch — previously only implied by the `failure_type` description, never stated as a checklist step; the injected resolver throughout UC-4/UC-6 is now explicitly time-aware — `resolve_node_key(node_id, at_timestamp)` / `resolve_issuer_key(issuer_id, at_timestamp)` — rather than a single-valued map, since a single-valued map cannot represent both a retired and an active key for the same identity; UC-1-EC1/UC-2-E3/UC-2-EC2's duplicate-hash cross-reference is broadened to note the check also covers Epic 3's pending batch/mempool, not only finalized blocks; UC-3-A's genesis description and UC-4's Genesis Exemption are made more concrete — genesis's `algorithm` field is the reserved literal `"genesis"` (never `"pow"`/`"pbft"`), explicitly exempt from every algorithm-specific check (PoW difficulty/target, PBFT quorum), not merely block index 0 as an implicit special case; UC-8 gains a new edge case (UC-8-EC3) documenting that restarting a node with a changed `expected_difficulty` against its OLD persisted chain correctly fails validation with `failure_type = "difficulty"` — this is expected/by-design behavior for starting a fresh benchmark run, not a bug. No use cases were removed; numbering is unchanged.
>
> Updated 2026-09-07 (v1.2 pass): Revised UC-1, UC-2, UC-3, UC-4, UC-6, UC-7, UC-9 to align with PRD v1.2 (second architecture-review round). Key changes: the hashed canonical preimage now includes `proposer_id` for BOTH PoW and PBFT, and PBFT's redundant `sealed_consensus.primary_id` is removed — `proposer_id` is the single source of truth for proposer identity (UC-2, UC-4); chain validation (UC-4) now explicitly receives an INJECTED key resolver (`node_id → public_key`, `issuer_id → public_key`, backed by Epic 3's `ValidatorSet`/`IssuerRegistry`, FR-23) plus (PoW) an injected `expected_difficulty` and (PBFT) an injected `ValidatorSet`, and never looks up keys/policy itself; UC-4 gains explicit PoW target/difficulty verification (`failure_type = "difficulty"`) and PBFT `commit_signatures[]` quorum verification (`failure_type = "quorum"`); the genesis exemption from the `proposer_signature`/`proposer_id` check is now explicit-by-definition rather than implicit (UC-3-A, UC-4); `GENESIS_MERKLE_ROOT` is stated as a fixed, well-known constant computed once from zero leaves; batch-level duplicate `document_hash` is now an explicit rejection, not a caller-level policy note (UC-2-E3); `document_records` is clarified as its own field group — never part of the hashed preimage, covered exclusively via `merkle_root` (UC-2); "empty chain is trivially valid" language is removed — the chain is never empty, genesis always exists from node startup (UC-4-EC1 redefined); UC-1's actor is corrected to the backend node process (server-side signing at submission time, per Epic 3 FR-22), never browser/UI tooling. No use cases were removed; numbering is unchanged.
>
> Updated 2026-09-07 (v1.1 pass): Revised UC-1, UC-2, UC-3, UC-4, UC-5, UC-6, UC-7, UC-8, UC-9 to align with PRD v1.1 (post architecture-review). Key changes: deterministic shared genesis block replaces per-node genesis policy (closes C-1); `Block` now splits into a hashed canonical preimage vs. attestation fields added after hashing, with `proposer_signature` (closes C-2); the issuer key pair is split into `IssuerKeyPair` (signs `DocumentRecord`s) and `NodeKeyPair` (signs blocks / peer auth) (closes C-3); Merkle tree construction uses RFC 6962-style domain separation instead of last-leaf duplication (closes C-5); chain validation now reports a `failure_type` (`hash`/`link`/`merkle`/`signature`/`structural`) and detects block-level field tampering via `proposer_signature`, closing the previous tip-block-only gap (closes M-1); `Block.timestamp` must be non-decreasing (new structural check); a canonical serialization spec (closes M-3) is referenced wherever hashing/signing occurs. No use cases were removed; numbering is unchanged.

This document covers the in-process blockchain library: document records, block structure, Merkle trees, hash-chain validation, digital signatures, tamper detection, and persistence. It has no network-facing API (that is Epic 3) — actors here are the calling code (issuer tooling, the Epic 3 node process, or a test harness), not end users.

All hashing and signing described below operates on the canonical byte serialization defined by PRD FR-4: JSON object keys sorted lexicographically, no insignificant whitespace, UTF-8 encoding, all timestamps as integer epoch-milliseconds, and all hash/signature/public-key fields as lowercase hex. This canonical form is a single shared utility used by every use case in this document that computes or verifies a hash or signature.

---

## UC-1: Create and Sign a Document Record

**Actor**: The backend node process, invoked server-side at document-submission time (Epic 3 FR-22/UC-4) — **never** the browser/UI or any client-side tooling, which never generates, holds, or transmits `IssuerKeyPair` private-key material (v1.2 confirmed architectural decision)
**Preconditions**: The node has a valid, boot-configured `IssuerKeyPair` (see UC-9) — distinct from the node's own `NodeKeyPair`
**Trigger**: A request to create a new `DocumentRecord` for a document hash plus metadata (in practice, an accepted, unsigned `{hash, metadata}` submission per Epic 3 UC-4)

### Primary Flow (Happy Path)
1. Caller supplies a SHA-256 document hash (or raw document bytes to be hashed) plus `issuer_id` (the node's own configured `IssuerRegistry` issuer identity, Epic 3 FR-23), `issued_at` timestamp, and metadata (e.g., recipient identifier, document title).
2. System validates the hash is a well-formed 64-character hex SHA-256 digest.
3. System assembles a `DocumentRecord` with the supplied fields.
4. System signs the record's canonical byte representation (per PRD FR-4) using the `IssuerKeyPair` private key (ECDSA P-256 or RSA ≥2048-bit). This is always the `IssuerKeyPair`, never a node's `NodeKeyPair` — a compromised `NodeKeyPair` must never be usable to forge a `DocumentRecord` signature.
5. System attaches the resulting `signature` to the record and returns it.

**Postconditions**: A signed `DocumentRecord` exists in memory, ready to be included in a block batch (UC-2).

### Alternative Flows
- **UC-1-A: Hash computed from raw bytes** — caller supplies raw document bytes instead of a pre-computed hash; system computes SHA-256 internally before proceeding at step 2.
- **UC-1-B: Optional IPFS pointer** — caller supplies an `ipfs_cid` value; system stores it on the record but treats it as fully optional (absent/null by default, per PRD Global Out-of-Scope).

### Error Flows
- **UC-1-E1: Malformed hash** — supplied hash is not 64 hex characters (wrong length or non-hex characters). System rejects the request with a validation error; no record is created.
- **UC-1-E2: Signing key unavailable** — the `IssuerKeyPair` private key cannot be loaded (missing key store, corrupted key file). System returns a signing error; no partially-signed record is returned.
- **UC-1-E3: Missing required field** — `document_hash`, `issuer_id`, or `issued_at` is missing/empty. System rejects with a validation error identifying the missing field.

### Edge Cases
- **UC-1-EC1**: The same document hash is issued twice by the same issuer (duplicate issuance). This function itself does not check chain-wide history — that is enforced one layer up, at submission time: Epic 3's `POST /documents` (FR-22) rejects with `409 Conflict` any `hash` already present in ANY finalized block anywhere in the chain **OR already present in the node's current pending batch/mempool awaiting inclusion in a not-yet-finalized block (v1.3 — broadened from "finalized block" only, to cover concurrent-submission races)**, before this record-creation flow (or Epic 2 UC-2's batch/Merkle construction) is ever invoked a second time for that hash. This is the single, authoritative duplicate-hash policy for the whole system — there is no "duplicates legal within a batch" or "return the earliest match" behavior anywhere.
- **UC-1-EC2**: Very large metadata payload (e.g., long free-text title). System accepts it; no arbitrary size limit is imposed at this layer (bounded only by storage NFRs).
- **UC-1-EC3**: Hash string has the correct length (64 chars) but contains non-hex characters (e.g., uppercase `G`, punctuation). Rejected under UC-1-E1.

### Data Requirements
- **Input**: `document_hash` (or raw bytes), `issuer_id`, `issued_at`, `metadata`, `IssuerKeyPair` private key reference.
- **Output**: Signed `DocumentRecord` object.
- **Side Effects**: None persisted yet (persistence occurs when the record is included in a block and the chain is saved, UC-8).

---

## UC-2: Build a Block from a Batch of Document Records (Merkle Tree Construction)

**Actor**: Calling system (Epic 3 node process, or a test harness for Epic 2)
**Preconditions**: One or more signed `DocumentRecord`s (UC-1) are ready to be batched
**Trigger**: A request to build a new candidate block from a batch of records

### Primary Flow (Happy Path)
1. Caller supplies a batch of N (N ≥ 1) signed document records, the previous block's hash, and the next block index.
2. System verifies each record's signature (UC-6) before inclusion; any record failing verification aborts the batch (see UC-2-E2).
3. System computes a domain-separated leaf hash for each record: `leaf_hash = H(0x00 || canonical_bytes(record))` (RFC 6962-style leaf domain separation).
4. System builds a Merkle tree bottom-up over the leaf hashes using domain-separated internal-node hashing: `internal_hash = H(0x01 || left_hash || right_hash)`. When a tree level has an odd number of nodes, the unpaired node is carried up unchanged to the next level (standard unbalanced-tree promotion) — the last leaf/node is never duplicated. This produces a single `merkle_root`.
5. System assembles the block's **hashed canonical preimage**: `index`, `timestamp`, `previous_hash`, `merkle_root`, `proposer_id` (the `node_id` of the block's proposer — present in the preimage for BOTH PoW and PBFT, v1.2; the single source of truth for proposer identity), `algorithm` (`"pow"` | `"pbft"`), and `sealed_consensus` (PoW: `{nonce, difficulty}`; PBFT: `{view_number}` — `primary_id` is intentionally NOT duplicated here since `proposer_id` above already covers it; populated later by Epic 3's consensus round). The batch of `document_records` is its own separate field group — grouped neither with the hashed preimage nor with the attestation fields — stored alongside the block for retrieval/display, but its integrity is covered *exclusively* via `merkle_root`; it is never itself part of the hashed preimage bytes (v1.2 clarification, fixes a prior ambiguous grouping).
6. System computes `block_hash` as SHA-256 over the canonical byte serialization (PRD FR-4) of the preimage fields only (including `proposer_id`) — `document_records`, `block_hash` itself, and any attestation fields are never part of the hashed bytes.
7. System returns the candidate (not-yet-appended, not-yet-attested) `Block`: preimage populated and `block_hash` computed. The **attestation fields** — `proposer_signature` (a `NodeKeyPair` signature over the canonical preimage, see UC-9) and, for PBFT only, `commit_signatures[]` — are attached strictly *after* hashing, typically by the Epic 3 layer that holds the proposing node's `NodeKeyPair`, and are never covered by `block_hash`.

**Postconditions**: A candidate `Block` with a correct, independently-recomputable `merkle_root` and `block_hash` exists, ready for chain append (UC-3) and/or consensus finalization (Epic 3), pending attestation.

### Alternative Flows
- **UC-2-A: Single-document batch (N=1)** — Merkle root construction degenerates to a single leaf; the "root" equals the domain-separated leaf hash itself (`H(0x00 || record_bytes)`). Still independently verifiable via UC-5.
- **UC-2-B: Odd number of leaves at a tree level** — the unpaired node is promoted unchanged to the next level rather than being paired with a duplicate of itself; this promotion rule is applied consistently at every level and proof generation (UC-5) accounts for it. This construction prevents the CVE-2012-2459-class second-preimage/duplication collision that affects naive last-leaf-duplication schemes.

### Error Flows
- **UC-2-E1: Empty batch** — a build request with zero document records is rejected; a block cannot be built with no data (the deterministic genesis block, whose `merkle_root` is the fixed constant for zero leaves, is a separate reserved case defined by PRD FR-1 — not produced via this flow).
- **UC-2-E2: Invalid record in batch** — one or more records in the batch fail signature verification (UC-6). System rejects the entire batch build and reports which record(s)/index(es) failed, rather than silently dropping the bad record and continuing.
- **UC-2-E3: Duplicate hash within the same batch (v1.2 — now an explicit rejection)** — two records in the same batch carry the identical `document_hash`. System MUST reject the batch build outright (never silently deduplicate or accept it) — this is the within-batch half of the system's single, authoritative duplicate-document-hash policy (PRD FR-5); the chain-wide half (a hash already finalized in ANY prior block, OR already present in the current pending batch/mempool — v1.3 broadening) is enforced one layer up, by Epic 3's `POST /documents` before this batch/Merkle-construction flow is even invoked (see Epic 3 FR-22, UC-1-EC1 above).

### Edge Cases
- **UC-2-EC1**: Very large batch (hundreds of documents). Merkle build completes in better-than-O(n²) time (per NFR) and produces a correct root.
- **UC-2-EC2**: Two leaves with identical hash values within the same batch. This can no longer occur as a *successful* build outcome (v1.2 — UC-2-E3 rejects it outright); this edge case now documents the rejection path itself, not a "still builds successfully" scenario. (Duplicate leaves across *different, already-finalized* blocks are structurally impossible too, since Epic 3's chain-wide 409 rejection at submission — which also covers the pending batch/mempool, v1.3 — prevents a hash from ever appearing in a second block or being queued twice.)
- **UC-2-EC3**: Canonical-serialization reproducibility — given the same input record/preimage structure, two independent calls (or two separate implementations, per PRD FR-4's test-vector requirement) produce byte-identical canonical serialization and therefore an identical `block_hash`/leaf hash.

### Data Requirements
- **Input**: Batch of signed `DocumentRecord`s, `previous_hash`, `index`.
- **Output**: Candidate `Block` (unpersisted, unattested) with hashed preimage fields, `merkle_root`, and `block_hash` populated; `proposer_signature`/`commit_signatures[]` populated later by attestation.
- **Side Effects**: None persisted at this stage.

---

## UC-3: Append Block to Chain (Hash-Chain Linking)

**Actor**: Calling system (Epic 3 node process after consensus finalization, or direct single-node test harness)
**Preconditions**: A valid chain exists (at minimum, the genesis block — the chain is never empty, v1.2); a candidate block (UC-2) is ready
**Trigger**: An append/commit call for a finalized candidate block

### Primary Flow (Happy Path)
1. System reads the current chain's tip block (genesis itself, if no blocks beyond genesis exist yet — see UC-3-A; the chain is never in a zero-block state).
2. System confirms the candidate block's `previous_hash` matches the recomputed hash of the current tip.
3. System confirms the candidate block's `index` is exactly `tip.index + 1`.
4. System appends the candidate block to the in-memory chain.
5. System triggers persistence (UC-8) so the new tip survives a restart.

**Postconditions**: Chain length increases by one; the new block becomes the tip; the chain remains valid per UC-4.

### Alternative Flows
- **UC-3-A: Genesis block append** — every node's chain begins with the **deterministic, shared genesis block** defined as a fixed constant in project config (PRD FR-1), constructed the very first time the node starts (the chain is never actually empty at any point after process startup, v1.2): `index = 0`, a fixed `timestamp` constant (`GENESIS_TIMESTAMP_MS`, defined once and never computed at runtime), `previous_hash = "0" * 64` (64 hex-zero characters), `merkle_root = GENESIS_MERKLE_ROOT` — a fixed hex constant defined once in config, conceptually the domain-separated hash of zero leaves per UC-2's Merkle spec, computed once at implementation time and hardcoded/configured identically on every node (never recomputed per node), and the same `algorithm`/`sealed_consensus` placeholder values on every node — **`algorithm` is set to the reserved literal `"genesis"`** (never `"pow"` or `"pbft"`), and `sealed_consensus` is an empty/placeholder object; this reserved literal is explicitly exempt, by definition, from every algorithm-specific check performed by UC-4 (the PoW difficulty/target check and the PBFT quorum check both skip a block whose `algorithm == "genesis"` by definition, not merely "block index 0" as an implicit special case) — and **sentinel `proposer_id = null`/empty and `proposer_signature = null`/empty** — genesis has no proposer, and these sentinel values are explicitly, by-definition EXEMPT from the `proposer_signature`/`proposer_id` check performed by UC-4 (v1.2 — not merely an implicit special case). This genesis block is never computed per-node or left to node-local policy — every node in a network appends byte-for-byte the same genesis block, verifiable by comparing `block_hash` at boot.

### Error Flows
- **UC-3-E1: Stale previous-hash reference** — the candidate's `previous_hash` no longer matches the current tip (e.g., another block was appended concurrently, or the candidate was built against outdated state). System rejects the append; caller must rebuild the candidate against the new tip.
- **UC-3-E2: Non-sequential index** — the candidate's `index` skips ahead or duplicates an existing index. System rejects the append.

### Edge Cases
- **UC-3-EC1**: Concurrent append attempts for the same next index (race condition, e.g., two consensus paths finalizing "simultaneously"). System enforces atomic check-and-append semantics so only one append succeeds; the loser is rejected per UC-3-E1/E2 and must resync.
- **UC-3-EC2**: Genesis-block equality across independently started nodes — two nodes started with no configuration beyond the shared genesis constants (no network communication required) independently construct byte-identical genesis blocks and compute an identical `block_hash`, directly verifying the Epic 2 acceptance criterion for C-1 closure. A node started with a mismatched/customized genesis constant is an explicit misconfiguration, not a supported "per-node genesis policy."

### Data Requirements
- **Input**: Candidate `Block`, current chain state.
- **Output**: Updated in-memory chain with new tip.
- **Side Effects**: Persistence write (UC-8).

---

## UC-4: Validate Chain Integrity

**Actor**: Calling system (on startup, after receiving a peer's chain in Epic 3, or on-demand from Epic 4's chain visualization)
**Preconditions**: A chain (ordered list of blocks, at minimum the genesis block — never empty, v1.2) is available, either local or received externally; the caller supplies an **INJECTED, time-aware key resolver** — `resolve_node_key(node_id, at_timestamp) → public_key`, covering current AND retired `NodeKeyPair` public keys and selecting whichever key was active at the given timestamp; and `resolve_issuer_key(issuer_id, at_timestamp) → public_key`, likewise selecting the issuer key active at the given timestamp (v1.3: a single-valued `node_id/issuer_id → public_key` map cannot represent both a retired and a currently-active key for the same identity, so the resolver contract MUST accept a timestamp) — plus, for PoW chains, an injected `expected_difficulty`, and for PBFT chains, an injected `ValidatorSet` (`n`, `f`, and the node-key resolver) — all built and supplied by the caller (Epic 3 FR-23/FR-24). **This function never looks up keys or policy itself** (no registry access, no network call); the resolver/difficulty/`ValidatorSet` are plain injected data, keeping this library free of any network dependency and preserving the dependency direction Epic 3 → Epic 2 only.
**Trigger**: A validation call

### Primary Flow (Happy Path)
1. For each block from genesis (index 0) to the tip, in order — except genesis, which is checked only per the Genesis Exemption below:
   a. Recompute the block's `block_hash` from its canonical hashed preimage (`index`, `timestamp`, `previous_hash`, `merkle_root`, `proposer_id`, `algorithm`, `sealed_consensus`) and compare to the stored `block_hash`.
   b. Compare the block's stored `previous_hash` to the recomputed hash of the prior block.
   c. Recompute the `merkle_root` from the block's `document_records` (using the domain-separated Merkle construction, UC-2) and compare to the stored `merkle_root`.
   d. Verify the block's `proposer_signature` (an attestation field, outside the preimage) against the public key returned by `resolve_node_key(proposer_id, block.timestamp)` from the **injected resolver** (a `NodeKeyPair` public key, possibly a retired one — see Epic 3's `ValidatorSet.retired_at` extension), over the canonical preimage bytes (now including `proposer_id`). This independently catches tampering of any preimage field — `index`, `timestamp`, `previous_hash`, `merkle_root`, `proposer_id`, or consensus fields — regardless of the block's position in the chain, closing the previous tip-block-only gap (PRD M-1).
   e. **(v1.3, explicit checklist step)** Verify each `DocumentRecord` in the block's batch: its `signature` must verify against the public key returned by `resolve_issuer_key(document_record.issuer_id, block.timestamp)` from the injected resolver. This step is now an explicit, always-performed part of the checklist — previously it was only implied by the `"signature"` failure-type description below, never stated as a check the function actually performs.
   f. Confirm `Block.timestamp` is non-decreasing relative to the prior block's `timestamp` (monotonicity check).
   g. **PoW blocks only (`algorithm == "pow"`)**: confirm `block_hash`, treated as an unsigned integer, numerically satisfies the target derived from `sealed_consensus.difficulty` (a genuine proof-of-work check, not merely a hash-format check), AND confirm `sealed_consensus.difficulty` equals the injected `expected_difficulty` — an arbitrary self-declared difficulty is rejected (v1.2, closes second-round MAJOR).
   h. **PBFT blocks only (`algorithm == "pbft"`)**: confirm `commit_signatures[]` contains signatures from at least `2f+1` distinct `ValidatorSet` members (resolved via `resolve_node_key(..., block.timestamp)`), each validly signing the block's canonical preimage (v1.2, closes second-round MAJOR). This is the SAME check whether the chain arrived via a live consensus round or via chain-sync/full-revalidation/the `GET /node/info` validity cache (see Epic 3 UC-3, UC-12).
2. If all blocks pass all applicable checks, the chain is reported valid.

**Genesis exemption (v1.2, explicit by definition; made concrete in v1.3):** the genesis block (`index = 0`), identified by its reserved `algorithm = "genesis"` literal (see UC-3-A), is exempt from the `proposer_signature`/`proposer_id` check (step 1d) by definition, per its sentinel `proposer_id = null`/`proposer_signature = null` values (UC-3-A) — this is not an implicit special case triggered by "no prior block," but an explicit rule. It is likewise exempt, by the same `algorithm == "genesis"` definition, from every algorithm-specific check (step 1g's PoW difficulty/target check and step 1h's PBFT quorum check both skip it outright, never merely because "index == 0"). Genesis is instead checked only for byte-identical equality against the shared `GENESIS_TIMESTAMP_MS`/`GENESIS_MERKLE_ROOT`/`previous_hash = "0"*64` constants (UC-3-A).

**Postconditions**: A result object is returned per UC-4's Data Requirements; on failure, the index of the first invalid block and the specific `failure_type` are reported. The chain's trust guarantee is **"this record existed no later than the block that contains it"** — not an absolute, unfalsifiable issuance-time claim — given the timestamp-monotonicity-only guarantee (per PRD FR-6).

### Alternative Flows
- **UC-4-A: Partial/incremental validation** — only a range of new blocks (e.g., blocks received since the last known-good tip during a chain-sync) is validated against a trusted starting point, rather than re-validating the entire chain from genesis every time. This is a caller-level (Epic 3) optimization for the *simple, non-diverging append* case only; when an incoming chain diverges from a known-good chain before its tip, the caller (Epic 3 chain-sync, UC-3) MUST invoke this function's full-chain mode from genesis rather than the incremental mode — the core validation function itself always supports full re-validation on request, using the identical injected-resolver/checklist regardless of mode (v1.2: this is also the exact checklist behind Epic 3's `GET /node/info` validity cache, UC-12 — never a lighter check).

### Error Flows
- **UC-4-E1: Block-hash mismatch** — a block's stored `block_hash` does not match a fresh recomputation over the canonical preimage (block content tampered). Reported invalid at that block's index, `failure_type = "hash"`.
- **UC-4-E2: Previous-hash mismatch** — a block's `previous_hash` does not match the prior block's recomputed hash (broken link, reordering, or injected block). Reported invalid at that block's index, `failure_type = "link"`.
- **UC-4-E3: Merkle-root mismatch** — a block's document records were altered without correspondingly updating the stored `block_hash` in a self-consistent way, causing the recomputed `merkle_root` to differ from the stored one. Reported invalid at that block's index, `failure_type = "merkle"`.
- **UC-4-E4: Structural chain error** — the chain contains duplicate or non-contiguous indices, or a malformed preimage. Reported invalid at that block's index, `failure_type = "structural"`, distinct from a content-tamper failure.
- **UC-4-E5: Signature failure — block-level or document-level** — either a block's `proposer_signature` fails to verify against the public key `resolve_node_key(proposer_id, block.timestamp)` returns (block-level field tampering, e.g. a tampered `timestamp`, `index`, `previous_hash`, or `proposer_id` with a self-consistently recomputed `block_hash`; step 1d), or a contained `DocumentRecord`'s signature fails to verify against the public key `resolve_issuer_key(issuer_id, block.timestamp)` returns (document-level tampering; step 1e, the explicit checklist step added in v1.3). Both are reported invalid at the affected block's index, `failure_type = "signature"`.
- **UC-4-E6: Non-monotonic timestamp** — a block's `timestamp` is strictly less than its predecessor's. Reported invalid at that block's index, `failure_type = "structural"`.
- **UC-4-E7: PoW target/difficulty violation (NEW, v1.2)** — either `block_hash` (as an unsigned integer) does not satisfy the target derived from its own declared `sealed_consensus.difficulty`, or `sealed_consensus.difficulty` does not equal the injected `expected_difficulty` (a self-declared, arbitrarily-low difficulty is rejected even if internally self-consistent). Reported invalid at that block's index, `failure_type = "difficulty"`.
- **UC-4-E8: PBFT commit-quorum violation (NEW, v1.2)** — a PBFT block's `commit_signatures[]` does not reach the `2f+1` threshold of distinct, validly-signing `ValidatorSet` members (resolved via the injected resolver). Reported invalid at that block's index, `failure_type = "quorum"`. This check runs identically whether the chain came from a live proposal round, a chain-sync response, or a `GET /node/info` validity-cache refresh (Epic 3 UC-3/UC-12).

### Edge Cases
- **UC-4-EC1**: Genesis-only chain (index 0 only, no blocks beyond genesis yet). This is the minimum possible valid chain state — **the chain is never actually empty**: genesis exists in every node's local chain from process startup onward (PRD FR-1, v1.2); "zero blocks" / "no genesis yet" is not a valid input state for this function. See UC-4-EC2 for the specific checks that apply to this minimal state.
- **UC-4-EC2**: Single-block chain (genesis only). Only the block-hash and (trivial) monotonicity checks apply (no prior block to link to or compare against); the genesis block's `proposer_id`/`proposer_signature` are the sentinel `null`/empty values and are explicitly exempt from step 1d per the Genesis Exemption above — not validated against any real `NodeKeyPair` from the injected resolver.
- **UC-4-EC3**: Very long chain (hundreds of blocks). Validation completes in better-than-O(n²) time (per NFR) without timing out.
- **UC-4-EC4**: Only the first block is corrupted vs. only the last (tip) block is corrupted. Validation must report the earliest failing index in both cases and must not "skip past" an early failure while still checking later blocks in a way that misreports which block is actually broken. For a tip-block-only tamper where the attacker also recomputes `block_hash` to match the tampered content, `proposer_signature` verification (UC-4-E5) is what still catches it — see UC-7 for the full defense-in-depth analysis.
- **UC-4-EC5 (NEW, v1.2)**: The injected resolver (`resolve_node_key`/`resolve_issuer_key`) is asked to resolve a `proposer_id`/`issuer_id` that is not present in its map at all (e.g., a genuinely unknown node/issuer, not merely a retired one). Verification fails closed (`invalid`, `failure_type = "signature"`) rather than throwing an unhandled error or defaulting to "valid."

### Data Requirements
- **Input**: Ordered list of `Block`s; injected, time-aware key resolver (`resolve_node_key(node_id, at_timestamp) → public_key` incl. retired entries, `resolve_issuer_key(issuer_id, at_timestamp) → public_key`); injected `expected_difficulty` (PoW chains); injected `ValidatorSet` (PBFT chains).
- **Output**: `{valid: bool, first_invalid_index: int | null, failure_type: "hash"|"link"|"merkle"|"signature"|"difficulty"|"quorum"|"structural"|null}`.
- **Side Effects**: None (read-only check).

---

## UC-5: Generate and Verify a Merkle Inclusion Proof

**Actor**: Calling system (Epic 3 node exposing lookups, or Epic 4's verify flow indirectly)
**Preconditions**: A block with a reconstructible Merkle tree structure exists
**Trigger**: A request for proof that a specific document hash is included in a specific block

### Primary Flow (Happy Path)
1. Caller supplies a `document_hash` and the target block (or its stored records).
2. System locates the corresponding domain-separated leaf (`H(0x00 || record_bytes)`, per UC-2) in the block's Merkle tree.
3. System generates the sibling-hash path (the inclusion proof) from that leaf up to the root, recording at each level whether the sibling is a left/right neighbor or the leaf/node was promoted unpaired (per UC-2-B).
4. System returns the proof alongside the block's stored `merkle_root`.
5. A verifier recomputes the root by combining the leaf with each sibling in the proof path using the domain-separated internal-node hash (`H(0x01 || left_hash || right_hash)`), or carrying the node up unchanged at any promoted level, and compares the result to the block's stored `merkle_root`.
6. If they match, the proof is reported valid.

**Postconditions**: A verifiable boolean result (valid/invalid) for "this document hash is included in this block" is produced, without requiring the full batch of documents to be present at verification time.

### Alternative Flows
- **UC-5-A: Verify-only using an externally supplied proof** — a proof previously generated (e.g., returned by an API in Epic 3/4) is verified independently of having the original block object, using only the leaf hash, the proof path, and the claimed `merkle_root`.

### Error Flows
- **UC-5-E1: Document hash not found in block** — the target document hash is not among the block's records. Proof generation fails with a clear "not found" result (not a crash, not a false proof).
- **UC-5-E2: Tampered proof** — one or more sibling hashes in the supplied proof path have been altered. Verification recomputes a root that does not match the claimed `merkle_root`; result is invalid.
- **UC-5-E3: Proof verified against the wrong root** — a proof generated for one block is verified against a different (e.g., stale or wrong) block's `merkle_root`. Result is invalid.

### Edge Cases
- **UC-5-EC1**: Single-document block (N=1). The proof path is empty; the "root" is the domain-separated leaf hash itself (`H(0x00 || record_bytes)`); verification is a direct equality check.
- **UC-5-EC2**: A document hash appears twice within the same batch (duplicate leaves). No longer a reachable state (v1.2 — UC-2-E3 rejects such a batch at build time, and Epic 3's chain-wide 409 policy prevents a hash from ever landing in two different blocks either), so proof generation/verification is never exercised against genuinely duplicate leaves in practice; retained here only to document why the domain-separated construction would have handled it safely had it been allowed.
- **UC-5-EC3**: The leaf/node involved was the unpaired node promoted unchanged at an odd tree level (per UC-2-B). Proof generation and verification correctly account for the promotion (no domain-separation hashing applied at that level for that node) and still produce a valid result.

### Data Requirements
- **Input**: `document_hash`, target block (or block's Merkle tree/records), or an externally supplied proof + claimed root for verify-only.
- **Output**: Proof structure (sibling hash path) and/or boolean verification result.
- **Side Effects**: None (read-only).

---

## UC-6: Verify a Document Record's Signature

**Actor**: Calling system (issuance-time self-check, block-build validation in UC-2, or Epic 4's verify flow)
**Preconditions**: A `DocumentRecord`, its claimed `signature`, and the `IssuerKeyPair` public key are available. This function itself takes the public key as a direct parameter (it does no lookup); when invoked as part of UC-4's chain validation, that public key is the one `resolve_issuer_key(issuer_id, block.timestamp)` returns from the caller's injected, time-aware resolver (backed by Epic 3's network-wide `IssuerRegistry`, FR-23) — Epic 2 never resolves `issuer_id → public_key` itself.
**Trigger**: A signature verification request

### Primary Flow (Happy Path)
1. System recomputes the canonical byte serialization (PRD FR-4) of the record's fields (excluding the signature itself).
2. System verifies the signature against the `IssuerKeyPair` public key using the appropriate algorithm (ECDSA P-256 or RSA, dispatched by key type). This is distinct from `proposer_signature` verification (UC-4-E5), which uses the block-proposing node's `NodeKeyPair` public key instead.
3. System returns `valid` if the cryptographic check passes.

**Postconditions**: A boolean signature-validity result is produced.

### Alternative Flows
- **UC-6-A: Algorithm auto-dispatch** — the verification function inspects the supplied public key's type and applies ECDSA or RSA verification accordingly, without the caller needing to specify which algorithm was used at signing time.

### Error Flows
- **UC-6-E1: Signature altered by a single byte** — verification fails (`invalid`).
- **UC-6-E2: Record content altered after signing** — any single field of the record (hash, issuer_id, issued_at, metadata) differs from what was originally signed. Verification fails (`invalid`).
- **UC-6-E3: Wrong public key supplied** — a public key belonging to a different issuer is used. Verification fails (`invalid`).
- **UC-6-E4: Malformed signature blob** — the signature value has the wrong length/encoding (not a crash-inducing case). System returns a handled `invalid` result rather than raising an unhandled exception.

### Edge Cases
- **UC-6-EC1**: Verification against a rotated/superseded key. Signatures made with an old key still verify successfully against that old public key; the system has no revocation/CRL mechanism (explicit, documented scope limitation — consistent with Epic 1's Blockcerts comparison noting revocation as a design dimension that this project's core does not implement).

### Data Requirements
- **Input**: `DocumentRecord` (or its canonical bytes), `signature`, `IssuerKeyPair` public key.
- **Output**: Boolean validity result.
- **Side Effects**: None (read-only).

---

## UC-7: Detect Tampering (Composite Defense-in-Depth Scenario)

**Actor**: System under attack (attacker or accidental corruption is the trigger source; the "actor" performing detection is the calling validation code)
**Preconditions**: A previously issued and finalized document record/block exists in persisted chain storage
**Trigger**: Direct mutation of persisted chain-store content, bypassing the normal API (accidental corruption, or a deliberate attack — this use case underlies Epic 5's tampering scenarios)

### Primary Flow (Happy Path — detection succeeds)
1. An external actor mutates one field (e.g., document-record metadata, or a block-level preimage field such as `timestamp`/`index`/`previous_hash`) directly in storage, without recomputing dependent hashes/signatures.
2. The chain is reloaded (UC-8).
3. Chain validation (UC-4) is run: the affected block's stored `merkle_root` and/or `block_hash` no longer matches a fresh recomputation, and/or its `proposer_signature` no longer verifies against the public key the injected resolver returns for its `proposer_id` (a `NodeKeyPair` public key — including a retired one, per Epic 3's `ValidatorSet.retired_at` extension, so a block signed before a key rotation still validates correctly against its resolver-returned key) → reported invalid at that block's index with the corresponding `failure_type` (`"hash"`/`"link"`/`"merkle"`/`"signature"`/`"difficulty"`/`"quorum"`/`"structural"`).
4. Independently, Merkle-proof verification (UC-5) for the affected document, and/or the `DocumentRecord`'s own signature verification against the `IssuerKeyPair` public key (UC-6), also fails where applicable.

**Postconditions**: A previously-valid chain is correctly flagged invalid, with the affected block identified.

### Alternative Flows
- **UC-7-A: Tamper the `previous_hash` field directly** — same detection path via UC-4-E2 (link mismatch) instead of UC-4-E1/E3.
- **UC-7-B: Tamper a middle block vs. the tip block** — detection must identify the correct index in both cases (see UC-4-EC4).

### Error Flows / Edge Cases (critical for thesis rigor)
- **UC-7-E1 / UC-7-EC1: Sophisticated tamper — attacker also recomputes the mutated block's own stored `block_hash` to match the new (tampered) content, at any block position.**
  - For a **middle block**: the next block's `previous_hash` was computed against the *original* hash, so it now mismatches the recomputed (new) hash of the tampered block → still caught by UC-4-E2 (link check), independent of the signature layer.
  - For the **tip block** (no downstream block exists to break the link): the hash-chain link check alone (UC-4-E2) cannot catch this, because there is nothing "downstream" to contradict the forged hash. **Under PRD v1.1/v1.2, this is no longer an unaddressed gap**: every block — tip or middle — carries its own `proposer_signature` over the canonical preimage (PRD FR-2, FR-6, closing M-1), and that preimage includes `proposer_id` (v1.2), so tampering the proposer identity itself is also covered. Since the attacker does not hold the proposing node's `NodeKeyPair` private key, recomputing `block_hash` to match the tampered content does not produce a valid `proposer_signature` for that new hash — verification fails (UC-4-E5, `failure_type = "signature"`), and the tamper is caught **regardless of block position**, not only via the document-record's `IssuerKeyPair` signature. This closes what was previously described as an intentional, tip-block-only gap in hash-chain-only validation.
  - If the mutated field is a `DocumentRecord` field (not a block-preimage field), the record's own `IssuerKeyPair` signature (UC-6) independently catches the tamper as a second, orthogonal layer — the original signature was computed over the original content and will no longer validate.
  - If a hypothetical attacker were to also re-sign the tampered block/record with a *different* key (their own, not the legitimate node's/issuer's), verification still fails against the *original, known* public key (`NodeKeyPair` for blocks, `IssuerKeyPair` for records, per UC-4-E5/UC-6-E3) — the known public key is the trust anchor, not anything derivable from the tampered data itself.
  - This dual-layer relationship (hash-chain link checks catch mid-chain structural tampering; `proposer_signature` now catches block-level field tampering at *any* position, including the tip; `IssuerKeyPair` signatures catch document-record content tampering) MUST be explicitly covered by tests, since it is a core thesis claim about tamper-evidence guarantees.
- **UC-7-EC2: Tip-block `Block.timestamp` tampered alone, with a self-consistently recomputed `block_hash`, no document-record change.** This is the scenario directly named by the Epic 2 acceptance criteria for M-1 closure: hash-chain checks (UC-4-E1/E2) pass (nothing downstream to contradict; the block's own recomputed hash is internally consistent), but `proposer_signature` verification fails (UC-4-E5) because the signature was computed over the original `timestamp` value. Detected with `failure_type = "signature"`, demonstrating block-level tamper detection independent of any document-record signature.

### Data Requirements
- **Input**: Chain storage before and after external mutation.
- **Output**: Invalid chain-validation result (with `failure_type`) and/or invalid Merkle-proof/signature result, with the affected block/document identified.
- **Side Effects**: None from validation itself (read-only); the tampering side effect is external to this use case (performed by the attacker/corruption source).

---

## UC-8: Persist and Reload Chain and Keys (Restart Durability)

**Actor**: Calling system (node process at startup/shutdown, or an explicit checkpoint call)
**Preconditions**: A node has an in-memory chain and/or key material
**Trigger**: Process shutdown/checkpoint (save), or process startup (load)

### Primary Flow (Happy Path)
1. On save: system serializes the full chain to local file-based storage (JSON or SQLite), the `IssuerKeyPair` to its own dedicated key-store file, and the `NodeKeyPair` to a separate dedicated key-store file — three independent logical stores.
2. On load: system deserializes the chain, `IssuerKeyPair`, and `NodeKeyPair` from those three files.
3. System runs chain validation (UC-4) on the loaded chain to confirm it is in a verifiable state before the node resumes normal operation.
4. Node state (chain + `IssuerKeyPair` + `NodeKeyPair`) is now identical to what it was before shutdown.

**Postconditions**: Chain state, `IssuerKeyPair`, and `NodeKeyPair` persist across a process restart and reload to an identical, verifiable state (matches Epic 2 acceptance criterion).

### Alternative Flows
- **UC-8-A: JSON vs. SQLite backend** — the underlying storage format is an implementation choice; the load/save contract (byte-for-byte equivalent verifiable state) is identical regardless of backend.

### Error Flows
- **UC-8-E1: Storage file missing on startup** — no prior chain file exists (fresh node). System initializes the chain with the single deterministic, shared genesis block (PRD FR-1, UC-3-A) — a fixed constant identical across all nodes, never a per-node-configured genesis policy — rather than crashing or leaving the chain undefined.
- **UC-8-E2: Storage file corrupted/unreadable** — the chain file exists but is truncated or contains invalid JSON/SQLite structure. System fails startup safely with a clear, specific error; it does NOT silently proceed with a partial or corrupt chain.
- **UC-8-E3: `IssuerKeyPair` store file missing** — no `IssuerKeyPair` key file exists but the chain file does (e.g., key file deleted independently). System fails fast with an explicit "issuer key material unavailable" error rather than silently generating a brand-new key pair (which would silently break issuer identity continuity for all prior issuances).
- **UC-8-E4: Loaded chain fails validation on startup** — the persisted chain itself was corrupted while the process was down (external tampering, e.g., Epic 5's direct chain-store mutation scenario). System reports the chain as invalid (via UC-4's result, including the failing block index and `failure_type`) and does not silently treat it as healthy; the node refuses to accept/propagate new blocks that would extend an already-broken chain until the condition is explicitly acknowledged/resolved by the operator.
- **UC-8-E5: `NodeKeyPair` store file missing** — no `NodeKeyPair` key file exists but the chain file does. System fails fast with an explicit "node key material unavailable" error, distinct from UC-8-E3's issuer-key error, rather than silently generating a new operational key (which would break the node's peer/transport identity and invalidate prior `proposer_signature`s attributed to it).

### Edge Cases
- **UC-8-EC1**: Concurrent read/write to the storage file from two processes (e.g., accidental double-start). Documented as an unsupported condition requiring file locking or single-writer enforcement at the storage layer.
- **UC-8-EC2**: Private key file permissions (best-effort NFR — key material for both `IssuerKeyPair` and `NodeKeyPair` should not be world-readable on the filesystem; not enforced by the library itself but documented as an operational requirement).
- **UC-8-EC3 (NEW, v1.3): Difficulty change requires a fresh chain.** A node is restarted with a changed configured `expected_difficulty` (e.g., to run a new comparative PoW benchmark) against its OLD persisted chain, which was mined at the previous difficulty. On startup, chain validation (UC-4) correctly FAILS with `failure_type = "difficulty"`, since every block's `sealed_consensus.difficulty` must equal the currently-injected `expected_difficulty` (Epic 3 FR-24). **This is expected/by-design behavior, not a bug**: changing the configured difficulty requires starting from a fresh chain/clean persisted store on every node in the network, not restarting against an old chain mined at a different difficulty.

### Data Requirements
- **Input**: In-memory `Chain`, `IssuerKeyPair`, and `NodeKeyPair` (save); storage file paths for all three logical stores (load).
- **Output**: Deserialized `Chain`, `IssuerKeyPair`, and `NodeKeyPair` matching the pre-shutdown state.
- **Side Effects**: Filesystem writes/reads across three independent stores.

---

## UC-9: Generate and Manage Key Pairs (IssuerKeyPair and NodeKeyPair)

**Actor**: Issuing authority / node operator
**Preconditions**: None for first-time generation
**Trigger**: A request to generate a new key pair (typically at issuer bootstrap for `IssuerKeyPair`, or at node bootstrap for `NodeKeyPair`)

PRD v1.1 (closes C-3) defines two independent key-pair types, generated and managed identically at the mechanical level but serving structurally distinct roles and stored separately (UC-8): `IssuerKeyPair` — the long-lived trust anchor that signs `DocumentRecord`s (UC-1) and is checked by Epic 4's verify flow and Epic 5's tamper tests; and `NodeKeyPair` — the per-node operational key that produces `proposer_signature` over a block's canonical preimage (UC-2) and authenticates the node at Epic 3's peer/transport layer. A compromised `NodeKeyPair` must never allow forging a `DocumentRecord` signature, and a compromised `IssuerKeyPair` must never be required for a node to participate in consensus.

### Primary Flow (Happy Path — `IssuerKeyPair`)
1. Operator requests `IssuerKeyPair` generation, specifying algorithm (ECDSA P-256, default) or RSA (≥2048-bit).
2. System generates the key pair using the `cryptography` library.
3. System persists the private key to a dedicated `IssuerKeyPair` key-store file, separate from chain data and from any `NodeKeyPair` store (see UC-8).
4. System exposes/returns the public key for distribution to verifiers (Epic 4) and to Epic 5's out-of-band trust-anchor config.

**Postconditions**: A fresh `IssuerKeyPair` exists; the private key is available for signing `DocumentRecord`s (UC-1); the public key is available for verification (UC-6). The public key is expected to be registered by Epic 3 in its boot-time `IssuerRegistry` (`issuer_id → public_key`, FR-23) so that Epic 2's injected key resolver (UC-4/UC-6) can resolve it — Epic 2 itself never reads or writes this registry.

### Alternative Flows
- **UC-9-A: Algorithm choice** — operator selects RSA instead of the ECDSA default at generation time (applies to both key-pair types).
- **UC-9-B: Generate a `NodeKeyPair`** — identical mechanical flow to the primary flow (steps 1–2), except: the private key is persisted to a dedicated `NodeKeyPair` key-store file, distinct from the `IssuerKeyPair` store; the public key is exposed/returned for use as this node's identity in Epic 3's `ValidatorSet`/`PeerInfo` registration and for `proposer_signature` verification by peers (UC-4-E5). A single node process typically generates/loads exactly one `IssuerKeyPair` (if it also acts as an issuer) and exactly one `NodeKeyPair` (always, to participate in consensus) — these are never the same key material.

### Error Flows
- **UC-9-E1: Key-store file already exists** — a prior key pair is already present at the target path (either `IssuerKeyPair` or `NodeKeyPair` store). System does NOT silently overwrite it; it requires an explicit confirmation/force flag, protecting against accidental loss of issuer or node identity.
- **UC-9-E2: Insufficient key size requested** — e.g., RSA 1024-bit requested. System rejects the request, enforcing the minimum 2048-bit floor (per NFR), for either key-pair type.
- **UC-9-E3: `NodeKeyPair` requested with an algorithm/parameters incompatible with block-signature verification expectations** — e.g., a key type the chain-validation layer cannot dispatch (UC-4-E5). System rejects the request rather than persisting an unusable node identity.

### Edge Cases
- **UC-9-EC1**: Key regeneration after prior issuances already exist under the old `IssuerKeyPair`. Old signatures remain verifiable against the old (now-superseded) public key; new issuances use the new key. The system has no built-in key-rotation/identity-linking mechanism — documented as an explicit scope limitation, not a defect.
- **UC-9-EC2**: `NodeKeyPair` regeneration after prior blocks were proposed/signed under the old key. Old `proposer_signature`s remain verifiable against the old (now-superseded) node public key during historical chain validation *because* Epic 3's `ValidatorSet` marks the old entry `retired_at` (v1.2, FR-23) rather than deleting it — the injected key resolver (UC-4) still resolves the old `node_id` to the old public key for old blocks. The node's active `ValidatorSet` entry must be updated to the new public key for the new key to be recognized going forward for new proposals; a stale active entry pointing at the old key would cause the node's *future* proposals to fail signature verification (UC-4-E5) at peers.

### Data Requirements
- **Input**: Algorithm choice, key-pair type (`IssuerKeyPair` | `NodeKeyPair`), key-store file path.
- **Output**: `IssuerKeyPair` or `NodeKeyPair` (private + public key material).
- **Side Effects**: Filesystem write to the corresponding dedicated key-store file.
