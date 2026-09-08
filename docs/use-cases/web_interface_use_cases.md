# Use Cases: Web Interface (Epic 4)

> Based on [PRD](../PRD.md) — Epic 4: Web Interface (React)

> Updated 2026-09-07 (v1.3 pass): Revised UC-1-E4, UC-2-E2 to align with PRD v1.3 (architecture-review polish, FINAL). Key change: the `409 Conflict` duplicate-hash rejection surfaced by the UI now also covers a `hash` already present in the node's current pending batch/mempool, not only a hash already in a finalized block (Epic 3 FR-22, v1.3 broadening) — the UI's duplicate-submission error handling is unaffected in shape, since it already treats any `409` response uniformly as a distinct duplicate-submission error. No use cases were removed; numbering is unchanged.
>
> Updated 2026-09-07 (v1.2 pass): Revised UC-1, UC-2, UC-7 to align with PRD v1.2 (second architecture-review round). Key changes: the Issue-page submission (UC-1/UC-2) explicitly confirms the node performs `IssuerKeyPair` signing server-side upon receiving the unsigned `{hash, metadata}` body — no remaining ambiguity about "who signs"; a new `409` duplicate-hash error flow is added to UC-1/UC-2, replacing the prior generic "node rejects the submission" language with the single, authoritative duplicate-document-hash policy (Epic 3 FR-22); "chain has zero blocks / no genesis yet" language is removed from UC-7-EC1 — the chain is never empty, genesis always exists; UC-7 and UC-9 clarify that `GET /node/info` is backed by an incrementally-updated cache, so polling/auto-refresh does not imply expensive per-request full revalidation. No use cases were removed; numbering is unchanged.
>
> Updated 2026-09-07 (v1.1 pass): Revised UC-1, UC-2, UC-4, UC-5, UC-7, UC-9 to align with PRD v1.1 (post architecture-review). Key changes: submission endpoint renamed `POST /blocks/submit` → `POST /documents`; lookup endpoint renamed/relocated `GET /documents/search?hash=` → `GET /documents/{hash}` (now owned by Epic 3, with proper HTTP 404 semantics for "not found"); the chain-validity display (UC-7) now sources `chain_valid`/`first_invalid_index` from Epic 3's new `GET /node/info` endpoint instead of a gap with no backing endpoint; the consensus-mode badge (UC-9) now sources from `GET /node/info` instead of `GET /metrics/consensus`, avoiding the empty-metrics-list-on-a-fresh-node ambiguity. No use cases were removed; numbering is unchanged.

This document covers the React single-page application: the Issue page, the Verify page, and the Chain Visualization page, all consuming Epic 3's node API (and indirectly Epic 2's cryptographic guarantees). Actors are end users acting as an issuer, a verifier, or a demo/thesis presenter. No authentication system exists in this prototype (documented as a deliberate, explicit scope reduction per the PRD).

---

## UC-1: Issue Document via File Upload

**Actor**: Issuer (user in browser)
**Preconditions**: Web app is loaded and configured against a reachable node's API base URL; the node/network is running
**Trigger**: User opens the Issue page, selects a file, enters metadata, and submits

### Primary Flow (Happy Path)
1. User selects a file via the file picker or drag-and-drop.
2. Browser computes the file's SHA-256 hash client-side using the Web Crypto API (matching Epic 2's hashing scheme) — the raw file is never transmitted to the server.
3. User enters minimal metadata: recipient identifier and document title.
4. Frontend calls Epic 3's `POST /documents` (renamed from `POST /blocks/submit` in PRD v1.1) with an **UNSIGNED** `{hash, metadata}` body — no signature or key material of any kind is included or computed by the browser.
5. The node receives the unsigned body and, server-side, assembles and signs the full `DocumentRecord` using its own configured `IssuerKeyPair` (v1.2 confirmed architectural decision, Epic 3 UC-4) before responding.
6. Node responds with an accepted/queued acknowledgment.
7. UI transitions to a "pending confirmation" state (see UC-3).

**Postconditions**: A document-issuance submission is queued at the node level; the browser never uploaded the raw file and never generated, held, or transmitted any issuer signature or private-key material — this is a hard constraint enforced end-to-end (v1.2), not merely an implementation choice left open.

### Alternative Flows
- **UC-1-A: Drag-and-drop vs. file-picker click** — both trigger the same downstream hashing/submission flow from step 2.
- **UC-1-B: Very large file** — hashing is performed via streaming/chunked reads through the Web Crypto API so the UI thread is not blocked during hashing.

### Error Flows
- **UC-1-E1: No file selected and no hash provided** — form submitted with the required input missing. Client-side validation blocks submission and shows an inline error; no network request is made.
- **UC-1-E2: Submission request fails** — the node is unreachable or the network request errors out. UI shows a clear error state; it does NOT show a false "success"/"pending" state.
- **UC-1-E3: Node rejects the submission** — e.g., malformed payload at the API level (defensive case; a client-supplied `signature` field would also be rejected here per Epic 3 UC-4-E1, though the UI never constructs one). UI surfaces the node's reported rejection reason to the user rather than a generic failure.
- **UC-1-E4: Duplicate document hash — `409 Conflict` (v1.2, closes prior ambiguity; scope broadened in v1.3)** — the node rejects the submission with `409` because `hash` already appears in a previously finalized block, **or is already present in the node's current pending batch/mempool awaiting inclusion in a not-yet-finalized block (v1.3 broadening)** (Epic 3 UC-4-E6, the single authoritative duplicate-hash policy). The UI surfaces this as a **distinct, explicit duplicate-submission error** — never a silent no-op, never a masked/automatic retry, and never conflated with UC-1-E2's generic network-failure state — regardless of whether the duplicate was already finalized or merely still pending.

### Edge Cases
- **UC-1-EC1**: Empty file (0 bytes) is uploaded. A hash is still computed (SHA-256 of the empty byte string) and submitted; this is treated as a valid, if unusual, input rather than being specially rejected by the client.
- **UC-1-EC2**: The identical file is uploaded twice (duplicate issuance attempt). The UI submits normally; the node rejects the second submission with `409` (UC-1-E4), and the UI surfaces that rejection clearly rather than silently retrying, hiding it, or showing a false success.

### Data Requirements
- **Input**: File bytes (browser-local only), recipient identifier, document title.
- **Output**: Client-computed SHA-256 hash sent to the node.
- **Side Effects**: A `POST /documents` network call; no persistent client-side state beyond in-page UI state.

---

## UC-2: Issue Document via Pasted Hash

**Actor**: Issuer (user in browser)
**Preconditions**: Same as UC-1; user already has a pre-computed hash (e.g., computed out-of-band)
**Trigger**: User pastes a hash string instead of uploading a file, enters metadata, and submits

### Primary Flow (Happy Path)
1. User pastes a hash string into the hash input field.
2. User enters metadata (recipient identifier, document title).
3. Frontend validates the hash is a well-formed 64-character hex string.
4. Frontend calls `POST /documents` (renamed from `POST /blocks/submit` in PRD v1.1) with an **UNSIGNED** `{hash, metadata}` body, identical to UC-1 step 4 onward — the node signs the resulting `DocumentRecord` server-side with its `IssuerKeyPair` (UC-1 step 5).

**Postconditions**: Same as UC-1.

### Error Flows
- **UC-2-E1: Invalid hash format** — the pasted string is not a valid 64-character hex SHA-256 hash (wrong length, non-hex characters, or empty). Client-side validation blocks submission with an inline error; no request is sent.
- **UC-2-E2: Duplicate document hash — `409 Conflict`** — same as UC-1-E4: the node rejects with `409` because the pasted hash already appears in a previously finalized block, or is already present in the current pending batch/mempool (v1.3 broadening). The UI surfaces this as a distinct duplicate-submission error, not a silent no-op or masked retry.

### Edge Cases
- **UC-2-EC1**: Pasted hash contains uppercase hex characters or surrounding whitespace. Input is normalized (trimmed, lowercased) before validation and submission.

### Data Requirements
- **Input**: Pasted hash string, recipient identifier, document title.
- **Output**: Normalized hash sent to the node.
- **Side Effects**: Same as UC-1.

---

## UC-3: Track Issuance Confirmation

**Actor**: Issuer (user in browser), Epic 3 node (source of finalization events)
**Preconditions**: A submission was already accepted by the node (UC-1 or UC-2 completed)
**Trigger**: Automatically begins immediately after a successful submission

### Primary Flow (Happy Path)
1. UI opens/uses a WebSocket connection to `WS /ws/blocks` (or falls back to polling) to watch for new finalized blocks.
2. When a finalized block containing the submitted hash is observed, the UI displays a confirmation showing the block's index and hash.

**Postconditions**: User sees explicit confirmation that their document is now part of a finalized block.

### Alternative Flows
- **UC-3-A: WebSocket vs. polling** — if a WebSocket connection is unavailable, the UI falls back to periodically polling `GET /chain` (or an equivalent status source) for the same result.

### Error Flows
- **UC-3-E1: Finalization does not occur within a reasonable timeout** — e.g., the node is stuck, or PBFT has lost quorum (Epic 3 UC-6-E5). The UI shows an explicit "still pending / possible network issue" state after a timeout, rather than spinning indefinitely with no feedback.
- **UC-3-E2: WebSocket connection drops mid-wait** — UI detects the drop and automatically falls back to polling (UC-3-A) without requiring the user to reload the page.

### Edge Cases
- **UC-3-EC1**: User navigates away from the Issue page before confirmation arrives. No crash occurs on unmount/cleanup; a subsequent visit to the Verify page can independently confirm the document's status using UC-4/UC-5.

### Data Requirements
- **Input**: Submitted hash (tracked locally in UI state), WebSocket/polling stream of finalized blocks.
- **Output**: Displayed block index + block hash confirmation.
- **Side Effects**: None persistent (UI-state only).

---

## UC-4: Verify Document via File Upload

**Actor**: Verifier (user in browser)
**Preconditions**: Web app is connected to a node with an existing chain
**Trigger**: User uploads a file on the Verify page

### Primary Flow (Happy Path)
1. User uploads a file.
2. Browser computes SHA-256 client-side (same mechanism as UC-1).
3. Frontend queries `GET /documents/{hash}` (relocated to Epic 3 and renamed from `GET /documents/search?hash=` in PRD v1.1).
4. UI displays: found/not-found (an HTTP 404 response from the API is mapped directly to "not found" — the endpoint's 404 semantics are the authoritative signal, not an inferred empty-body case), issuer identity, issuance timestamp, and containing block index, plus the Merkle-proof validity result (UC-6).

**Postconditions**: User sees a definitive verification result for the uploaded document.

### Alternative Flows
- **UC-4-A**: This flow shares its downstream query/result-display logic (steps 3–4) with UC-5 (pasted-hash entry point).

### Error Flows
- **UC-4-E1: API unreachable during search** — the node cannot be reached. UI shows a clear error/retry state, distinct from a "not found" result — the two must never be visually or semantically conflated.
- **UC-4-E2: Malformed API response** — the response does not match the expected schema. UI shows a graceful error state without crashing.

### Edge Cases
- **UC-4-EC1**: Hash not found anywhere on the chain (document was never issued) — the API responds HTTP 404 via the standard error envelope. UI shows an explicit "not found" result, clearly distinguished from an error state (UC-4-E1) and from a "found but invalid" state (UC-4-EC2); a 404 must never be conflated with UC-4-E1's network/API-unreachable error state.
- **UC-4-EC2**: A document's record exists on-chain under the same key/index but its stored content/metadata was tampered with in the backing store (the tamper detection scenario). The Merkle-proof verification (UC-6) fails; the UI must display an explicit "invalid" result — NOT "valid" and NOT silently treated the same as "not found" — demonstrating end-to-end tamper detection through the UI (matches the Epic 4 acceptance criterion).

### Data Requirements
- **Input**: File bytes (browser-local), client-computed hash.
- **Output**: `GET /documents/{hash}` query and its result rendered in the UI (200 + data, or 404 → "not found").
- **Side Effects**: None persistent.

---

## UC-5: Verify Document via Pasted Hash

**Actor**: Verifier (user in browser)
**Preconditions**: Same as UC-4
**Trigger**: User pastes a hash string on the Verify page instead of uploading a file

### Primary Flow (Happy Path)
Identical to UC-4 from step 3 onward, using a user-pasted hash instead of a client-computed one.

### Error Flows
- **UC-5-E1: Invalid hash format entered** — the pasted string is not a valid 64-character hex SHA-256 hash. Client-side validation blocks the query with an inline error before any API call is made.

### Edge Cases
- Inherits UC-4-EC1 and UC-4-EC2 once a syntactically valid hash is submitted.

### Data Requirements
- **Input**: Pasted hash string.
- **Output**: Same as UC-4.
- **Side Effects**: None persistent.

---

## UC-6: View Merkle Inclusion Proof Result

**Actor**: Verifier (user in browser), viewing the result of UC-4/UC-5
**Preconditions**: A search already returned a "found" document along with proof-supporting data from the API
**Trigger**: Automatically triggered as part of rendering the verify result

### Primary Flow (Happy Path)
1. UI (or the server, per the architect's chosen split) verifies the Merkle inclusion proof against the block's stored `merkle_root` (Epic 2 UC-5).
2. UI displays a clear "valid" indicator/badge when the proof checks out.

**Postconditions**: User sees a cryptographically-grounded valid/invalid indicator, not just a "found" flag.

### Alternative Flows
- **UC-6-A: Client-side verification** — the browser independently recomputes and checks the proof using data returned by the API.
- **UC-6-B: Server-side verification** — the server performs the check and returns a boolean plus supporting proof data for transparency; the UI simply renders the reported result.

### Error Flows
- **UC-6-E1: Proof data missing/incomplete in the API response** — the UI shows an explicit "unable to verify proof" state rather than defaulting to (or implying) "valid" in the absence of data.

### Edge Cases
- **UC-6-EC1**: Proof verification fails despite the document being reported "found" (e.g., corrupted chain-store data — see UC-4-EC2). The UI prominently shows "invalid" — this is the key UI-level tamper-detection behavior required by the Epic 4 acceptance criteria.

### Data Requirements
- **Input**: Proof data (sibling hash path) and claimed `merkle_root`, or a pre-computed boolean from the server.
- **Output**: Valid/invalid indicator rendered in the UI.
- **Side Effects**: None.

---

## UC-7: View Chain Visualization

**Actor**: Any user, typically the thesis presenter during a live demo
**Preconditions**: The currently selected node is reachable; its chain has one or more blocks (at minimum the genesis block — the chain is never empty, v1.2)
**Trigger**: User navigates to the Chain Visualization page

### Primary Flow (Happy Path)
1. UI fetches `GET /chain` (optionally paginated via `?from=&to=`, per Epic 3's pagination requirement) from the currently selected node.
2. UI fetches `GET /node/info` (Epic 3, new endpoint) from the same node to obtain `chain_valid` and `first_invalid_index` — this is a cheap call backed by Epic 3's incrementally-updated validity cache (v1.2), not a full chain revalidation, so it is safe to call on every page load and on every auto-refresh (UC-7-A) without a per-request cost that scales with chain length.
3. UI renders each block in sequence (index, timestamp, document count) as a connected chain diagram.
4. UI derives and displays a per-block validity indicator (valid/tampered) using `GET /node/info`'s `chain_valid`/`first_invalid_index` fields as the authoritative data source — previously this had no backing endpoint (an architecture gap); the block at `first_invalid_index` (when `chain_valid = false`) is flagged, and all blocks before it are shown valid.

**Postconditions**: The current chain state and its validity are visually represented, suitable for live demonstration and thesis screenshots.

### Alternative Flows
- **UC-7-A: Live auto-refresh** — the visualization updates automatically as new blocks are broadcast over WebSocket, without requiring a manual refresh.

### Error Flows
- **UC-7-E1: Selected node unreachable** — `GET /chain` or `GET /node/info` fails. UI shows an explicit error state; it does NOT silently continue displaying a stale chain as if it were current.

### Edge Cases
- **UC-7-EC1 (v1.2 — corrected; the chain is never empty)**: Chain has only the genesis block (freshly started network, no documents issued yet). UI renders the single genesis block correctly, per the normal rendering path — there is no "zero blocks / no genesis yet" state to special-case, since genesis exists in every node's chain from process startup (PRD FR-1). This is the minimum valid state the visualization must handle, not an empty state.
- **UC-7-EC2**: A block in the backing store has been manually corrupted (used for a live tamper demo). The visualization correctly flags that specific block as invalid while still correctly rendering at least 5 sequential blocks overall (matches the Epic 4 acceptance criterion directly).
- **UC-7-EC3**: Very long chain (100+ blocks). Rendering remains responsive via pagination/virtualization/scrolling rather than degrading or freezing the page.

### Data Requirements
- **Input**: `GET /chain` response and `GET /node/info` response (`chain_valid`, `first_invalid_index`) from the selected node.
- **Output**: Rendered block-chain diagram with per-block validity indicators.
- **Side Effects**: None persistent.

---

## UC-8: Switch Node Selector on Visualization Page

**Actor**: Thesis presenter / user
**Preconditions**: Multiple nodes are configured/known (Epic 3's multi-node network)
**Trigger**: User selects a different node from a selector/dropdown on the Chain Visualization page

### Primary Flow (Happy Path)
1. User selects a different node from the node selector.
2. UI re-fetches `GET /chain` from the newly selected node's URL.
3. UI re-renders the visualization for the newly selected node's chain, without a full page reload.
4. UI updates the consensus-mode badge (UC-9) to reflect the newly selected node's reported mode.

**Postconditions**: The visualization reflects a different node's independent chain view, without navigating away from the page.

### Error Flows
- **UC-8-E1: Newly selected node is unreachable** — an explicit error is shown scoped to that selection; the UI does not silently keep showing the previously selected node's data as if the switch succeeded.

### Edge Cases
- **UC-8-EC1**: Switching reveals a fork — the newly selected node's chain differs from the previously viewed node's chain at some block index (used to visually demonstrate consensus divergence). The UI renders each node's chain independently and accurately; it must NOT attempt to merge or reconcile the two views into one.

### Data Requirements
- **Input**: Selected node's URL/identifier.
- **Output**: Re-rendered chain visualization and updated consensus badge for the newly selected node.
- **Side Effects**: None persistent (client-side navigation only).

---

## UC-9: View Active Consensus Mode Badge

**Actor**: Any user viewing any page that surfaces network state (primarily the Chain Visualization page)
**Preconditions**: The currently viewed node is reachable
**Trigger**: Page load, or a node-selection change (UC-8)

### Primary Flow (Happy Path)
1. UI fetches the currently selected node's reported consensus algorithm via Epic 3's `GET /node/info` (new endpoint, PRD v1.1) — `algorithm` field — rather than `GET /metrics/consensus`. This avoids the prior empty-metrics-list-on-a-fresh-node problem: `GET /node/info` always reports the node's configured algorithm immediately, even before any blocks beyond genesis have been finalized (unlike `GET /metrics/consensus`, whose result list is empty on a fresh node and cannot be used to infer the algorithm). Since `GET /node/info` is backed by an incrementally-updated validity cache (v1.2, Epic 3), this call is cheap regardless of how frequently the badge re-fetches it (e.g., on every node switch, UC-8) and never triggers a full chain revalidation.
2. UI displays a badge (e.g., "PoW" or "PBFT") reflecting that node's active algorithm.

**Postconditions**: The user always knows which consensus algorithm the currently viewed network/node is running.

### Error Flows
- **UC-9-E1**: The `GET /node/info` endpoint is unreachable. Badge shows an explicit "unknown" state rather than a stale or guessed label.

### Edge Cases
- **UC-9-EC1**: Nodes in the same demo network are misconfigured with different consensus modes (Epic 3 UC-11-EC1). The badge correctly and independently reflects each node's own reported mode as the user switches between them (UC-8), rather than caching/reusing a previously displayed mode.
- **UC-9-EC2**: A freshly started node with zero blocks beyond genesis is selected. The badge still correctly displays the node's configured algorithm immediately (sourced from `GET /node/info`, which is available regardless of block count), rather than showing "unknown" or blank as would happen if sourced from `GET /metrics/consensus`'s empty result list.

### Data Requirements
- **Input**: Selected node's `GET /node/info` response (`algorithm` field).
- **Output**: Rendered mode badge.
- **Side Effects**: None.
