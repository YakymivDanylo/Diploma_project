# Test Cases: Web Interface (Epic 4)

> Based on [PRD](../PRD.md) and [Use Cases](../use-cases/web_interface_use_cases.md)

This document covers the React single-page application: the Issue page, the Verify page, and the Chain Visualization page (PRD Epic 4). Every UC scenario in `web_interface_use_cases.md` (v1.3) is mapped below. Given this thesis's central contribution, extra weight is given to: the unsigned `{hash, metadata}` submission contract with node-side signing (the browser never handles the private key), correct `409` duplicate handling in the UI, clearly distinguishing "not found" (404) vs. "found but tampered/invalid" vs. "valid" in the verify flow, and the chain visualization sourcing validity strictly from `GET /node/info`'s cache.

---

## 1. Issue Document via File Upload (UC-1)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-1.1 | UC-1 primary | Select a file, enter metadata, submit | Browser computes SHA-256 client-side (Web Crypto API); raw file is never transmitted; `POST /documents` is called with an UNSIGNED `{hash, metadata}` body containing no signature/key material; UI transitions to a pending-confirmation state |
| TC-1.2 | UC-1-A | Trigger submission via drag-and-drop, and separately via file-picker click | Both entry points produce the identical downstream hashing/submission flow |
| TC-1.3 | UC-1-B | Upload a very large file | Hashing is performed via streaming/chunked Web Crypto API reads; the UI thread is not blocked |
| TC-1.4 | UC-1-E1 | Submit the form with no file selected and no hash provided | Client-side validation blocks submission with an inline error; no network request is made |
| TC-1.5 | UC-1-E2 | Submit while the node is unreachable / the network request errors | UI shows a clear error state; never shows a false "success"/"pending" state |
| TC-1.6 | UC-1-E3 | Node rejects the submission with a malformed-payload error at the API level | UI surfaces the node's actual reported rejection reason, not a generic failure message |
| TC-1.7 | UC-1-E4 (finalized duplicate) | Node rejects with `409` because `hash` already appears in a previously finalized block | UI shows a distinct, explicit duplicate-submission error — never a silent no-op, never a masked/automatic retry, never conflated with the generic network-failure state (UC-1-E2) |
| TC-1.8 | UC-1-E4 (v1.3 broadened — pending duplicate) | Node rejects with `409` because `hash` is already present in the node's pending batch/mempool (not yet finalized) | UI shows the identical distinct duplicate-submission error as TC-1.7, regardless of whether the duplicate was finalized or merely pending |
| TC-1.9 | UC-1-EC1 | Upload an empty file (0 bytes) | A hash is still computed (SHA-256 of the empty byte string) and submitted normally, not specially rejected by the client |
| TC-1.10 | UC-1-EC2 | Upload the identical file twice in succession | Second submission is sent normally; node rejects with `409`; UI surfaces the rejection clearly (no silent retry, hiding, or false success) |

---

## 2. Issue Document via Pasted Hash (UC-2)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-2.1 | UC-2 primary | Paste a well-formed 64-char hex hash, enter metadata, submit | Frontend validates the hash format, then calls `POST /documents` with an UNSIGNED `{hash, metadata}` body identical in shape to the file-upload flow |
| TC-2.2 | UC-2-E1 | Paste a string that is not a valid 64-character hex SHA-256 hash (wrong length, non-hex chars, or empty) | Client-side validation blocks submission with an inline error; no request is sent |
| TC-2.3 | UC-2-E2 | Node rejects with `409` (hash already finalized, or already pending per v1.3 broadening) | UI shows a distinct duplicate-submission error, not a silent no-op or masked retry |
| TC-2.4 | UC-2-EC1 | Paste a hash containing uppercase hex characters and/or surrounding whitespace | Input is normalized (trimmed, lowercased) before validation and submission |

---

## 3. Track Issuance Confirmation (UC-3)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-3.1 | UC-3 primary | Submit a document, then observe `WS /ws/blocks` for the finalizing block | When the block containing the submitted hash is observed, UI displays a confirmation with block index and hash |
| TC-3.2 | UC-3-A | WebSocket connection is unavailable from the start | UI falls back to periodically polling `GET /chain` (or equivalent) for the same result |
| TC-3.3 | UC-3-E1 | Finalization does not occur within a reasonable timeout (node stuck, or PBFT lost quorum) | UI shows an explicit "still pending / possible network issue" state after the timeout, not an indefinite spinner |
| TC-3.4 | UC-3-E2 | WebSocket connection drops mid-wait | UI detects the drop and automatically falls back to polling without requiring a page reload |
| TC-3.5 | UC-3-EC1 | User navigates away from the Issue page before confirmation arrives | No crash occurs on unmount/cleanup; a subsequent Verify-page visit can independently confirm the document's status |

---

## 4. Verify Document via File Upload (UC-4)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-4.1 | UC-4 primary | Upload a previously issued, unmodified file | UI computes SHA-256 client-side, queries `GET /documents/{hash}`, and displays found + issuer identity + issuance timestamp + block index + Merkle-proof "valid" |
| TC-4.2 | UC-4-A | Compare the downstream query/result-display code path with UC-5 (pasted-hash entry point) | Both entry points render identical found/not-found/invalid results for the same underlying hash |
| TC-4.3 | UC-4-E1 | API is unreachable during the search | UI shows a clear error/retry state, never visually or semantically conflated with a genuine "not found" result |
| TC-4.4 | UC-4-E2 | API returns a response that does not match the expected schema | UI shows a graceful error state without crashing |
| TC-4.5 | UC-4-EC1 | Upload a file whose hash was never issued (API returns 404) | UI shows an explicit "not found" result, clearly distinguished from the error state (TC-4.3) and from "found but invalid" (TC-4.6) |
| TC-4.6 | UC-4-EC2 (central end-to-end tamper test) | Verify a document whose on-chain record content/metadata was tampered with in the backing store | Merkle-proof verification fails; UI displays an explicit "invalid" result — NEVER "valid" and NEVER silently treated the same as "not found" |

---

## 5. Verify Document via Pasted Hash (UC-5)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-5.1 | UC-5 primary | Paste a well-formed hash on the Verify page for a previously issued, unmodified document | Query/result-display flow identical to UC-4 from step 3 onward; displays "valid" with correct issuer/timestamp/block index |
| TC-5.2 | UC-5-E1 | Paste an invalid hash format | Client-side validation blocks the query with an inline error before any API call is made |
| TC-5.3 | UC-5 (inherits UC-4-EC1/EC2) | Paste a never-issued hash, and separately a hash whose record was tampered with | Both cases render the identical "not found" / explicit "invalid" outcomes as the file-upload entry point (UC-4) |

---

## 6. View Merkle Inclusion Proof Result (UC-6)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-6.1 | UC-6 primary | A "found" search result includes proof-supporting data | Proof is verified against the block's stored `merkle_root`; a clear "valid" indicator/badge is displayed when it checks out |
| TC-6.2 | UC-6-A | Verification is performed client-side by the browser | Browser independently recomputes and checks the proof using API-returned data, producing the same result as server-side verification |
| TC-6.3 | UC-6-B | Verification is performed server-side | Server returns a boolean plus supporting proof data; UI simply renders the reported result |
| TC-6.4 | UC-6-E1 | API response is missing/incomplete proof data | UI shows an explicit "unable to verify proof" state, never defaulting to or implying "valid" |
| TC-6.5 | UC-6-EC1 (central UI-level tamper test) | Proof verification fails despite the document being reported "found" (corrupted chain-store data) | UI prominently shows "invalid" |

---

## 7. View Chain Visualization (UC-7)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-7.1 | UC-7 primary | Load the Chain Visualization page against a node with several blocks | UI fetches `GET /chain` (paginated) and `GET /node/info`, renders each block (index, timestamp, document count) as a connected diagram with a per-block validity indicator sourced from `chain_valid`/`first_invalid_index` |
| TC-7.2 | UC-7 primary (cache-cost) | Reload/auto-refresh the visualization repeatedly | `GET /node/info` calls remain cheap (backed by Epic 3's incrementally-updated cache), never scaling in cost with chain length |
| TC-7.3 | UC-7-A | A new block is broadcast over WebSocket while the page is open | Visualization updates automatically without a manual refresh |
| TC-7.4 | UC-7-E1 | The selected node becomes unreachable (`GET /chain` or `GET /node/info` fails) | UI shows an explicit error state; does NOT silently continue displaying a stale chain as if it were current |
| TC-7.5 | UC-7-EC1 | View a freshly started network whose chain has only the genesis block | UI renders the single genesis block correctly via the normal rendering path — no "zero blocks/no genesis yet" special case exists |
| TC-7.6 | UC-7-EC2 (central tamper-demo test) | Manually corrupt one block in the backing store | Visualization flags that specific block as invalid while still correctly rendering at least 5 sequential blocks overall |
| TC-7.7 | UC-7-EC3 | Load a very long chain (100+ blocks) | Rendering remains responsive via pagination/virtualization/scrolling rather than freezing or degrading |

---

## 8. Switch Node Selector on Visualization Page (UC-8)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-8.1 | UC-8 primary | Select a different node from the node selector | UI re-fetches `GET /chain` from the new node's URL, re-renders without a full page reload, and updates the consensus-mode badge |
| TC-8.2 | UC-8-E1 | Select a node that is unreachable | An explicit error is shown scoped to that selection; UI does not silently keep showing the previously selected node's data as if the switch succeeded |
| TC-8.3 | UC-8-EC1 | Switch to a node whose chain differs from the previously viewed node's at some block index (fork demonstration) | Each node's chain is rendered independently and accurately; the UI never attempts to merge or reconcile the two views |

---

## 9. View Active Consensus Mode Badge (UC-9)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-9.1 | UC-9 primary | Load a page showing the consensus-mode badge | Badge is sourced from `GET /node/info`'s `algorithm` field (not `GET /metrics/consensus`) and correctly displays "PoW" or "PBFT" |
| TC-9.2 | UC-9 primary (cache-cost) | Re-fetch the badge repeatedly (e.g., on frequent node switches) | Calls remain cheap, backed by Epic 3's incrementally-updated cache; never trigger a full chain revalidation |
| TC-9.3 | UC-9-E1 | `GET /node/info` is unreachable | Badge shows an explicit "unknown" state, never a stale or guessed label |
| TC-9.4 | UC-9-EC1 | Switch between nodes configured with different consensus modes | Badge correctly and independently reflects each node's own reported mode, never caching/reusing a previously displayed mode |
| TC-9.5 | UC-9-EC2 | Select a freshly started node with zero blocks beyond genesis | Badge still correctly displays the node's configured algorithm immediately, rather than showing "unknown" or blank |
