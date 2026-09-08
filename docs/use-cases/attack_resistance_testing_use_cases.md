# Use Cases: Attack Resistance Testing (Epic 5)

> Based on [PRD](../PRD.md) — Epic 5: Attack Resistance Testing

> Updated 2026-09-07 per PRD v1.3: Revised UC-1, UC-4, UC-5 to align with PRD v1.3 (architecture-review polish, FINAL) and to catch up this file, which had remained stale at v1.1 while the other three use-case documents advanced through v1.2/v1.3. Epic 5's own functional requirements did not change between v1.1 and v1.3, but this file's scenarios interact directly with Epic 2/3 mechanisms that did change, and several passages had drifted out of sync with the current design. Key changes: **UC-1 step 3** is reframed — under PRD FR-24, a node enforces `expected_difficulty` and rejects any block whose declared `difficulty` doesn't match it (`failure_type = "difficulty"`), so "controlled difficulty" is no longer described as an attacker lever for disrupting PoW consensus; the only lever an attacker actually controls is its own **hash power/rate**, not the difficulty target itself (an attacker cannot submit blocks at a self-chosen lower difficulty and have them accepted). **UC-4 and UC-5** now make explicit that the Epic 2 chain-validation call invoked by these scenarios takes an **injected key resolver** (Epic 2 FR-6/UC-4, Epic 3 FR-23/UC-14) — this is exactly the mechanism the test harness uses to plug in the out-of-band trusted issuer/node public keys (the M-2 trust-anchor requirement) rather than the resolver Epic 3 would normally construct from its own local `IssuerRegistry`/`ValidatorSet`. **UC-4 step 2** is corrected: the prior "wait for its next validation cycle" language did not match the actual design (PRD FR-26: the validity cache updates only on a block-append or chain-sync event, and no periodic validation cycle exists) — the step now describes triggering re-validation via an append/sync event or a node restart. No use cases were removed; numbering is unchanged.
>
> Updated 2026-09-07: Revised UC-1, UC-2, UC-3, UC-4, UC-5, UC-6, UC-7, UC-8 to align with PRD v1.1 (post architecture-review). Key changes: Byzantine/adversarial node behavior must now be implemented as a separate attacker component/image importing Epic 3's consensus engine as a library, never as env-flag hooks in the honest node (closes M-13); PoW Sybil-resistance is now measured/framed by hash-power share, not node-count share, with PoW and PBFT results shown on separate, non-comparable chart panels (closes M-8); PBFT Sybil-resistance is explicitly framed as attacker-controlled `ValidatorSet` seat fraction, and mere `PeerInfo` registration is confirmed to have zero quorum effect (closes C-4); tamper/backdating signature verification must use an out-of-band trusted issuer public key, never the attacked node's own key-store (closes M-2); attack verification goes through Epic 3's API directly (`GET /documents/{hash}`, `GET /node/info`) rather than requiring browser automation through the UI, with manual UI demonstration kept as a separate optional note (MINOR); crash-fault vs. Byzantine-fault scenarios are now explicitly distinguished, matching Epic 3's classification; the mid-chain injection timestamp-monotonicity edge case (UC-5-EC1) is corrected — Epic 2 now enforces `Block.timestamp` monotonicity, closing what was previously documented as a known scope gap. No use cases were removed; numbering is unchanged.

This document covers the attack scenario scripts and reporting pipeline run against the real Epic 3 docker-compose network: Sybil attacks (against both PoW and PBFT), backdating/tampering attacks (direct chain-store mutation and mid-chain block injection), attack-run data recording, and comparison-chart/findings generation. Actors are the thesis author/operator running scripts, attacker-controlled node processes (simulated adversaries reusing Epic 3's node code as a library), and the honest network under test. This epic is a research/reporting deliverable — its scripts are not integrated into the Epic 4 UI, but its scenarios directly exercise Epic 2's tamper-detection and Epic 3's consensus/rejection guarantees, so adversarial flows are treated with the same rigor as a production security test suite.

---

## UC-1: Run Sybil Attack Scenario Against a PoW Network

**Actor**: Attack script / operator
**Preconditions**: A docker-compose PoW network (Epic 3) is running with a known honest node count and known per-node hash-rate (sourced from Epic 3's `GET /metrics/consensus`); a separate attacker Docker image/component exists (see UC-1-A below)
**Trigger**: Operator runs the Sybil attack script with parameter N (number of attacker-controlled node containers) against the PoW network

### Primary Flow (Happy Path — attack executes to a conclusive result)
1. Script spins up N additional attacker-controlled containers built from a **separate attacker Docker image** (closes M-13) that imports Epic 3's consensus engine as a library and overrides the relevant mining/message-handling hooks (e.g., subclassing/monkey-patching) — never an environment-flag conditional inside the honest-node image.
2. Attacker nodes register as `PeerInfo` peers with the honest network (Epic 3 UC-1); registration alone has no bearing on PoW's resistance mechanism.
3. Attacker nodes attempt to bias/disrupt block finalization — e.g., out-hashing honest miners at the network's honestly-configured difficulty, or flooding competing block proposals — contributing a measured, controlled **hash-power share** to the network. **(v1.3 reframing)** The difficulty target itself is never an attacker-controlled lever: per PRD FR-24, every node validates that a block's `sealed_consensus.difficulty` equals its own injected `expected_difficulty`, so an attacker cannot submit blocks mined at a self-chosen, lower difficulty to cheaply out-produce honest miners — any such block is rejected outright with `failure_type = "difficulty"` (Epic 2 UC-4-E7) before it could ever count as a "win." The only lever the attacker actually controls is its own **hash power/rate** (more/faster mining hardware or containers) at the network's real, shared difficulty — not a self-declared difficulty value.
4. Script observes and records whether the attack caused a fork, stalled finalization, or got an attacker-authored/invalid block finalized, and records the attacker's **hash-power share** (not raw node-count fraction) at the time of the outcome, sourced from each container's reported hash-rate (Epic 3's `GET /metrics/consensus`).

**Postconditions**: A conclusive outcome (disruption succeeded or failed) is recorded for this run, indexed by attacker hash-power share against PoW — never reported on the same axis as PBFT's `ValidatorSet`-seat-fraction metric (UC-2), since the two algorithms' Sybil-resistance mechanisms are structurally different (PRD M-8).

### Alternative Flows
- **UC-1-A: Separate attacker image/component (closes M-13)** — the attacker's mining-bias and flooding behavior is packaged as its own Dockerfile/image and its own docker-compose service, distinct from the honest-node image. The honest-node codebase contains no attacker-mode conditionals, flags, or hooks; the attacker image achieves its behavior purely by importing and overriding Epic 3's consensus engine library from the outside.
- **UC-1-B: Threshold sweep** — the scenario is run repeatedly across varying N/hash-power configurations (linear sweep or binary search) to bracket the minimum disruptive hash-power share.

### Error Flows
- **UC-1-E1: Attacker containers fail to join the network** — peer registration is rejected or the attacker containers are unreachable (infrastructure failure, not a genuine attack outcome). The run is aborted/retried and explicitly marked as inconclusive/infra-failure — it must NOT be silently recorded as "attack failed."
- **UC-1-E2: Honest network crashes entirely during the attack** — an unintended side effect (e.g., resource exhaustion) rather than the intended consensus-level disruption. The run is flagged inconclusive, not counted as attacker success.

### Edge Cases
- **UC-1-EC1**: Attacker hash-power share = 0 (control/baseline run, no attackers present, or attacker containers configured at zero mining effort). Used to confirm normal operation as a comparison baseline; expected outcome is "no disruption."
- **UC-1-EC2**: Attacker hash-power share reaches or exceeds a simple majority of total network hash power (which may require fewer or more than N=honest-node-count attacker containers, depending on per-container mining configuration — node count alone is not the controlling variable). Expected to succeed in disrupting PoW consensus, validating the well-known hash-power-majority theoretical expectation referenced from Epic 1's research.

### Data Requirements
- **Input**: Attacker node count N (control parameter for container count), per-attacker-container hash-rate configuration (attacker-controlled — mining effort/rate only; the difficulty target is fixed by the honest network's `expected_difficulty` and is never attacker-configurable, v1.3), PoW network configuration (shared `expected_difficulty`, honest node count and hash-rate).
- **Output**: A recorded run outcome including measured attacker hash-power share (see UC-6).
- **Side Effects**: Additional Docker containers created (from the separate attacker image) and torn down; honest network state potentially forked/disrupted for the duration of the run.

---

## UC-2: Run Sybil Attack Scenario Against a PBFT Network

**Actor**: Attack script / operator
**Preconditions**: A docker-compose PBFT network (Epic 3) is running with a known `ValidatorSet` size n and its implied fault tolerance f; a separate attacker Docker image/component exists (mirrors UC-1-A)
**Trigger**: Operator runs the Sybil attack script with parameter N (attacker-controlled `ValidatorSet` seats) against the PBFT network

**Metric framing (closes M-8, C-4):** because PBFT's Sybil-resistance is closed-membership-based (Epic 3 C-4), the controlling variable here is the **fraction of attacker-controlled `ValidatorSet` seats**, not raw attacker node/container count and not `PeerInfo` peer-registration count. This is measured and reported on a separate chart axis/panel from PoW's hash-power-share metric (UC-1) — the two are never directly comparable node-for-node.

### Primary Flow (Happy Path)
1. Script deploys N attacker-controlled containers built from the **separate attacker image** (UC-1-A) and configures the test network so that these N containers occupy N of the n total `ValidatorSet` seats (a controlled-experiment redeployment with the attacker nodes included in the boot-time `ValidatorSet` config for this run) — this is required because mere `PeerInfo` registration (see UC-2-EC2) grants no quorum-voting weight under PRD C-4.
2. Attacker `ValidatorSet` members attempt disruption via PBFT-specific behavior, explicitly separated into two distinct failure-class scenarios (see Alternative Flows UC-2-B/UC-2-C): **Byzantine equivocation** (colluding minority/majority voting, equivocating `prepare`/`commit` messages, Epic 3 UC-6-E2) — a safety-risk scenario — or **crash/silent-fault** (refusing to participate, going unresponsive) — a liveness-risk scenario.
3. Script observes and records whether the attack caused a fork or an invalid block being finalized (Byzantine/safety outcome) versus a stalled finalization / reported quorum loss (crash/liveness outcome), reading the distinguishing classification from Epic 3's `GET /node/info` `quorum_status` field (PRD FR-15, closes M-9) rather than inferring it indirectly.

**Postconditions**: A conclusive outcome is recorded for this attacker `ValidatorSet` seat fraction N/n against PBFT, labeled with its failure class (Byzantine vs. crash) where applicable.

### Alternative Flows
- **UC-2-A: Threshold sweep** — same threshold-sweep alternative as UC-1-B, run against PBFT instead, sweeping attacker `ValidatorSet` seat fraction rather than hash-power share.
- **UC-2-B: Byzantine equivocation attacker variant (safety risk)** — attacker-controlled `ValidatorSet` members send conflicting `prepare`/`commit` votes to different honest peers for the same (view, seq). Expected outcome at or below the theoretical boundary (f = floor((n−1)/3)): honest nodes' vote-deduplication (Epic 3 UC-6-E2) prevents any wrong block from being finalized — safety is preserved even though some rounds may be slower. This must be recorded and reported distinctly from UC-2-C's outcome.
- **UC-2-C: Crash/silent-fault attacker variant (liveness risk)** — attacker-controlled `ValidatorSet` members simply stop responding (no equivocation, just silence). Expected outcome at or below f: consensus continues finalizing correctly (Epic 3 UC-6-EC1). Above f: consensus stalls and reports quorum loss (Epic 3 UC-6-E5) — this is a liveness failure, not a safety failure, and must be reported/labeled as such, never conflated with a Byzantine/equivocation finding.

### Error Flows
- **UC-2-E1: Cluster size not adjusted for the tested fault count** — e.g., testing f=2 attacker-controlled `ValidatorSet` seats against a fixed n=4 cluster, which structurally violates PBFT's `n ≥ 3f+1` safety assumption regardless of any implementation quality. This must be run and recorded as an intentional, clearly-labeled boundary/over-limit test point — NOT reported as an implementation "vulnerability" when it disrupts consensus, since the safety guarantee was never claimed to hold there.

### Edge Cases
- **UC-2-EC1**: Attacker `ValidatorSet` seat fraction is set exactly at the theoretical PBFT safety boundary (f = floor((n−1)/3)). Expected outcome is that consensus is NOT disrupted (Byzantine variant, UC-2-B), confirming the theoretical guarantee holds in the real implementation — a result contrary to this expectation is itself a critical, must-report finding (see UC-3-EC1).
- **UC-2-EC2: Negative control — attacker registers as `PeerInfo` peers only, without any `ValidatorSet` seats (verifies C-4 closure)**. Attacker containers register via `POST /peers/register` in large numbers but are never included in the boot-time `ValidatorSet` config. Expected outcome: zero effect on the PBFT quorum threshold or on consensus outcomes — the quorum is verifiably computed only over the static `ValidatorSet` (Epic 3 UC-1, UC-6), demonstrating that `PeerInfo`-only Sybil registration is structurally powerless against PBFT, unlike a naive node-count-based quorum scheme.

### Data Requirements
- **Input**: Attacker-controlled `ValidatorSet` seat count N, PBFT cluster configuration (n, resulting f, view-change timeout), failure-class selection (Byzantine equivocation vs. crash/silent).
- **Output**: A recorded run outcome including attacker `ValidatorSet` seat fraction and failure class (see UC-6).
- **Side Effects**: Same as UC-1.

---

## UC-3: Determine Sybil-Resistance Threshold

**Actor**: Attack script / operator (aggregation/analysis step)
**Preconditions**: Multiple UC-1/UC-2 runs have completed across a range of attacker fractions N, for a given consensus mode
**Trigger**: Run after a sweep of scenarios for a given mode is complete

### Primary Flow (Happy Path)
1. Script aggregates all recorded run outcomes (UC-6) for the target consensus mode.
2. Script identifies the minimum attacker fraction at which disruption first succeeded — for PoW, this is a **hash-power share**; for PBFT, this is an **attacker-controlled `ValidatorSet` seat fraction**. These two thresholds are computed and reported independently and are never merged into a single shared metric (PRD M-8).
3. Script records this value as the mode's measured Sybil-resistance threshold, on its algorithm-appropriate axis.

**Postconditions**: A single threshold value (or explicit "not found within bounds") exists per consensus mode on its own metric axis, ready for chart generation as two separate panels (UC-7).

### Error Flows
- **UC-3-E1: No successful disruption found within tested bounds** — e.g., testing only ran up to N = honest node count and PBFT correctly never broke because the test never exceeded the theoretical `n ≥ 3f+1` boundary. This is documented explicitly as "no threshold found within the tested range" — matching the PRD's acceptance-criteria wording — and is NOT silently omitted from the results.

### Edge Cases
- **UC-3-EC1**: The measured threshold differs from the literature/theoretical expectation (e.g., the real implementation breaks earlier than the theoretical bound due to an implementation defect). This is itself a valid and important finding to record and discuss — it must not be treated as a test failure to be hidden or re-run until it "passes."

### Data Requirements
- **Input**: Aggregated run outcomes for a given consensus mode.
- **Output**: Threshold value (or explicit "not found" marker) per mode.
- **Side Effects**: Feeds the results dataset used by UC-7.

---

## UC-4: Backdating/Tampering — Direct Chain-Store Mutation

**Actor**: Attack script / operator, acting with local filesystem access to a node's persisted store (simulating an attacker with storage-level access, or accidental corruption)
**Preconditions**: A node has a finalized chain containing at least one genuinely issued document; a **separately-stored, read-only trusted issuer public key** file exists (a trust-anchor config maintained outside the attacked node's own key-store directory)
**Trigger**: Script directly edits the node's persisted chain-store file (JSON/SQLite) to alter a document record's timestamp/content, or a block's stored hash — entirely bypassing the API

**Trust-anchor requirement (closes M-2):** all signature verification performed by this scenario — for both `DocumentRecord` (`IssuerKeyPair`) signatures and block-level `proposer_signature` (`NodeKeyPair`) checks — MUST use a public key read from the separately-stored, out-of-band trust-anchor config, never from the attacked node's own key-store directory. An attacker with filesystem access on the attacked node could otherwise swap both the record/block and the corresponding public key together, silently invalidating the test. **Injected-resolver connection point (made explicit in this v1.3 pass):** concretely, this requirement is satisfied because Epic 2's chain-validation function (UC-4) never looks up keys itself — it always takes an **injected key resolver** (`resolve_node_key(node_id, at_timestamp)` / `resolve_issuer_key(issuer_id, at_timestamp)`, per Epic 2 FR-6/UC-4 and Epic 3 FR-23/UC-14) as a parameter. This is exactly the seam the test harness uses: it constructs its own resolver backed by the out-of-band trust-anchor file(s) and injects that resolver into the validation call, instead of using the resolver Epic 3 would normally build from the attacked node's own local `IssuerRegistry`/`ValidatorSet` (UC-1-C/UC-1-D). This is what structurally prevents the attacker's key-store swap from invalidating the test.

### Primary Flow (Happy Path — detection succeeds)
1. Script mutates a target field directly in the chain-store file.
2. Script triggers re-validation via an append/sync event or a node restart (**v1.3 correction**: the node's validity cache updates only on a block-append or chain-sync event (PRD FR-26) — there is no periodic validation cycle to "wait for." The script therefore either (a) restarts the node so it re-validates the loaded chain on startup (Epic 2 UC-8 step 3), or (b) triggers a chain-sync/append event against the node — e.g., by having a peer broadcast a new block or by issuing a sync request — so the incremental validity-cache update path (Epic 3 UC-3/UC-14) runs and picks up the mutation).
3. Script runs Epic 2's chain-validation (Epic 2 UC-4) — invoked with the harness's own **injected key resolver** built from the out-of-band trusted public key(s) (see the Injected-resolver connection point above), not the attacked node's local resolver — and confirms it reports invalid at the correct block index with the expected `failure_type`.
4. Script also verifies through Epic 3's API directly — `GET /documents/{hash}` (Epic 3 UC-13) and `GET /node/info` (Epic 3 UC-12, checking `chain_valid`/`first_invalid_index`) — and confirms the tampered document/chain is reported invalid/not-found end-to-end via the API (closes the prior Epic 5 → Epic 4 UI-automation dependency). An optional, separate, non-blocking manual demonstration through Epic 4's UI (Epic 4 UC-4/UC-5/UC-6) may additionally be performed for live thesis-defense illustration, but is not required for the scenario's pass/fail determination.

**Postconditions**: The tamper attempt is recorded as detected (or, if not detected, recorded as a critical security finding — see error flow below).

### Alternative Flows
- **UC-4-A: Metadata-only mutation** — only non-hash metadata (e.g., recipient name) is altered, leaving `document_hash` unchanged, testing whether stored-hash-vs-content consistency is actually enforced by validation.
- **UC-4-B: Sophisticated attacker — content mutated AND the block's own stored hash recomputed to match** — tests whether hash-chain-only validation is insufficient on its own and whether signature verification (Epic 2 UC-6, and now `proposer_signature` per UC-4-E1 below) is required as the necessary second detection layer. This is a deliberately designed, critical edge case for the thesis (directly derived from Epic 2 UC-7's dual-layer analysis).

### Error Flows
- **UC-4-E1: Block-level field tampering (any position) with self-consistently recomputed `block_hash`** — the attacker mutates a preimage field (`timestamp`, `index`, `previous_hash`, `merkle_root`, or consensus fields) and recomputes `block_hash` to match. Under PRD v1.1, hash-chain link checks may pass at the tip (nothing downstream to contradict it), but `proposer_signature` verification (Epic 2 UC-4-E5), checked against the out-of-band `NodeKeyPair` trust-anchor entry, independently catches the tamper at **any block position**, not only the tip — this closes what was previously documented as a tip-block-only gap (Epic 2 M-1 closure). **If `proposer_signature` verification ALSO fails to catch this case, it must be recorded as a critical security finding for the thesis, not silently passed over or treated as an expected/acceptable gap.**
- **UC-4-E2: Document-record content tampering with re-signed record using an attacker-controlled key** — the scenario confirms that verification against the out-of-band trusted `IssuerKeyPair` public key (never the attacked node's own key-store) rejects the forged signature (Epic 2 UC-6-E3). If verification instead reads the public key from the attacked node's local key-store and that key-store was also compromised/swapped by the attacker, the test would produce a false "valid" result — this is precisely the flaw the out-of-band trust-anchor requirement (closes M-2) is designed to prevent, and the script must assert it is using the out-of-band key source, not the node's local one.

### Edge Cases
- **UC-4-EC1**: Tampering targets a very early block (near genesis) vs. the most recently finalized block. Detection must work identically regardless of the tampered block's position in the chain (a direct consequence of `proposer_signature`'s position-independent coverage, UC-4-E1).
- **UC-4-EC2**: Multiple simultaneous tamper points are introduced in a single run (to confirm detection doesn't stop checking after the first failure and miss additional corruption). Validation must still correctly report the earliest failing index and its `failure_type` per Epic 2 UC-4's contract, and a follow-up scan after resolving/removing the earliest issue should be able to reveal subsequent ones.

### Data Requirements
- **Input**: Target node's chain-store file path, mutation details (field, target block/record), out-of-band trusted `IssuerKeyPair`/`NodeKeyPair` public key file path.
- **Output**: Recorded detection outcome (detected at index X with `failure_type` / undetected — critical finding), confirmed via direct API calls (`GET /documents/{hash}`, `GET /node/info`).
- **Side Effects**: The target node's persisted chain-store file is mutated (destructive to that node's state for the duration of the test; typically run against a disposable test instance). The out-of-band trust-anchor file itself is never mutated by this scenario.

---

## UC-5: Backdating/Tampering — Mid-Chain Block Injection

**Actor**: Attack script / operator
**Preconditions**: An existing finalized chain with multiple blocks; a **separately-stored, read-only trusted issuer/node public key** config exists (mirrors UC-4's out-of-band trust-anchor requirement, closes M-2)
**Trigger**: Script constructs a new block intended to be inserted between two existing blocks, carrying a falsified (earlier) timestamp, and attempts to get it accepted

**Injected-resolver connection point (made explicit in this v1.3 pass, mirrors UC-4):** any chain-validation call this scenario runs directly (offline path) invokes Epic 2's UC-4 function with the harness's own **injected key resolver** built from the out-of-band trust-anchor config, not the resolver Epic 3 would build from the attacked node's local `IssuerRegistry`/`ValidatorSet` — the same seam UC-4 relies on. The online path additionally exercises the honest node's own resolver (Epic 3 UC-14) at real-time rejection.

### Primary Flow (Happy Path — injection is rejected)
1. Script constructs the forged block with a falsified timestamp positioned to appear mid-chain.
2. Script attempts to introduce it either via direct chain-store file edit (offline) or via live network broadcast/PBFT proposal (online, exercising Epic 3 UC-7/UC-8's rejection path directly). In the online case, the attacker does not hold the honest node's `NodeKeyPair` private key, so the forged block cannot carry a valid `proposer_signature`.
3. Honest node(s) reject the injected block — at chain-validation time, triggered via a node restart or an append/sync event rather than any periodic cycle (v1.3, mirrors UC-4 step 2's correction; PRD FR-26) (index/`previous_hash` sequencing broken, or non-monotonic `timestamp`, `failure_type = "structural"`/`"link"`) and/or at broadcast-receipt time (Epic 3 UC-8: `proposer_signature` verification fails immediately since the attacker lacks the `NodeKeyPair`, so the proposal is rejected and not re-broadcast, without even needing to reach the hash-chain-link check). For the offline path, validation is invoked with the harness's own injected out-of-band resolver (see above); for the online path, the honest node's own boot-constructed resolver (Epic 3 UC-14) is what performs the real-time rejection.

**Postconditions**: The injection attempt fails to become part of any honest node's canonical chain; the attempt is recorded as detected/blocked.

### Alternative Flows
- **UC-5-A: Offline injection** — direct store-file edit followed by node restart/reload.
- **UC-5-B: Online injection** — live broadcast or PBFT proposal attempt, directly exercising Epic 3's real-time `proposer_signature`-based rejection path rather than only the reload-time validator.

### Error Flows
- **UC-5-E1: Attacker renumbers/shifts all subsequent block indices to make sequencing appear valid** — this necessarily changes the content (and therefore the recomputed hash and required `proposer_signature`) of every downstream block, since each block's own hash is derived from its content including its index and `previous_hash`, and each block's `proposer_signature` covers exactly that preimage. Confirming this cascading requirement (the attacker would have to forge and re-sign every single downstream block's preimage, which is only possible if they also compromise the honest node's `NodeKeyPair` private key — see Epic 2 UC-9 — and, for document-record content, the issuer's `IssuerKeyPair`) demonstrates that wholesale chain rewriting is impractical at the single-node level. Additionally, honest peers holding the pre-injection chain reject the rewritten version during chain-sync comparison (Epic 3 UC-3): since the rewritten chain diverges before the peer's local tip, the peer runs **full chain revalidation from genesis** (Epic 3 UC-3 step 3, closes M-14) rather than incremental validation, and the forged chain fails either the longest-valid-chain/latest-finalized-height rule or fails full validation outright.

### Edge Cases
- **UC-5-EC1: Corrected in PRD v1.1 — timestamp monotonicity is now enforced.** The injected block carries a falsified, chronologically-earlier timestamp than its claimed `previous_hash` target's timestamp, but is otherwise fully hash-consistent and carries a forged-but-internally-consistent `proposer_signature` scenario (i.e., a fully sophisticated attacker who redid all downstream hashes/signatures per UC-5-E1, which per that error flow requires compromising the honest node's `NodeKeyPair`). Under PRD v1.1, Epic 2's chain validation now enforces `Block.timestamp` non-decreasing monotonicity (Epic 2 UC-4-E6) as part of structural validation — **this is no longer a documented scope gap**: the scenario now explicitly confirms that a non-monotonic-timestamp injection is rejected with `failure_type = "structural"`, independent of and in addition to the pre-existing honest-peer chain-sync rejection (their own longer/differently-built honest chain, per Epic 3 UC-3, still rejects the forged fork via the normal adoption rule as a second, independent layer). A monotonicity check failing to catch such an injection is now itself a critical finding to record, not an acceptable gap.

### Data Requirements
- **Input**: Target chain state, forged block content, injection method (offline/online), out-of-band trusted `IssuerKeyPair`/`NodeKeyPair` public key file path (for the offline path's injected resolver).
- **Output**: Recorded detection/rejection outcome (including `failure_type` where applicable), and confirmation that the timestamp-monotonicity check (UC-5-EC1) functions as specified.
- **Side Effects**: Target node's chain-store file mutated (offline path) and/or network messages sent (online path); run typically against a disposable test instance.

---

## UC-6: Record Attack Run Outcome

**Actor**: Attack script (automated, invoked at the end of every run from UC-1, UC-2, UC-4, or UC-5)
**Preconditions**: An attack run has just completed (conclusively or inconclusively)
**Trigger**: Automatic, at the end of each run

### Primary Flow (Happy Path)
1. Script appends a row to the results dataset (CSV/JSON) recording: `attack_type`, `consensus_mode`, `attacker_metric` (PoW: hash-power share; PBFT: attacker-controlled `ValidatorSet` seat fraction — recorded on the algorithm-appropriate field, never merged into one generic "fraction" column), `failure_class` where applicable (Byzantine/equivocation vs. crash/silent-fault — Epic 3's crash-vs-Byzantine distinction, UC-2-B/UC-2-C), `hash_rate_sample` (PoW runs only — a per-node hash-rate sample, per-run, matches the Epic 5 acceptance criterion), `outcome` (detected/blocked vs. succeeded, or inconclusive per UC-1-E1/E2), and `time_to_detection` where applicable.

**Postconditions**: The results dataset gains one durable record of this run, usable for both threshold aggregation (UC-3) and chart generation (UC-7).

### Error Flows
- **UC-6-E1: Dataset file write fails** — e.g., disk full or permission error. The script surfaces a clear, explicit error; the run's outcome is NOT silently lost or treated as if it had been recorded.

### Edge Cases
- **UC-6-EC1**: The same scenario/parameters are re-run (e.g., for reproducibility or to gather more samples). A new row is appended rather than overwriting the prior record, preserving a full run history.

### Data Requirements
- **Input**: Run metadata and outcome from the completed attack scenario.
- **Output**: Appended row in the results dataset.
- **Side Effects**: Filesystem write to the results dataset file.

---

## UC-7: Generate Comparison Charts

**Actor**: Operator, running the chart-generation script
**Preconditions**: The results dataset (UC-6) and Epic 3's metrics data are available
**Trigger**: Operator runs the chart-generation script

### Primary Flow (Happy Path)
1. Script reads the recorded results dataset and Epic 3 metrics data.
2. Script produces at least: (a) a PoW-vs-PBFT block-finalization-latency chart across varying difficulty/network sizes, and (b) a Sybil-resistance-threshold chart rendered as **two separate panels** — one for PoW (x-axis: attacker hash-power share) and one for PBFT (x-axis: attacker-controlled `ValidatorSet` seat fraction) — never merged into a single shared node-count axis, since that would misrepresent PoW's actual resistance mechanism (closes M-8).
3. Charts are exported as static image files (matplotlib/plotly) suitable for direct inclusion in the thesis document.

**Postconditions**: At least 2 comparison charts exist, generated from recorded attack/metric data, with the Sybil-resistance chart's two panels never directly overlaid on one shared axis (matches the Epic 5 acceptance criterion).

### Alternative Flows
- **UC-7-A: Regeneration from previously captured data** — the script is re-run against already-recorded data (no new attack runs performed), for reproducibility during thesis defense.

### Error Flows
- **UC-7-E1: Dataset missing required fields/rows for a chart** — e.g., no PBFT runs have been recorded yet when generating the PBFT comparison series. The script explicitly reports which chart could not be generated and why, rather than silently producing a misleading empty or partial chart.

### Edge Cases
- **UC-7-EC1: Reproducibility check** — re-running the chart script twice on identical, unchanged input data produces byte-identical (or visually identical) output charts, confirming the reproducibility requirement (matches the Epic 5 NFR).

### Data Requirements
- **Input**: Results dataset (UC-6), Epic 3 metrics data (Epic 3 UC-9).
- **Output**: Static chart image files.
- **Side Effects**: Filesystem writes (chart image files).

---

## UC-8: Produce Written Findings Summary

**Actor**: Thesis author (manual/editorial step, informed by UC-1 through UC-7's outputs)
**Preconditions**: All planned attack runs and chart generation are complete
**Trigger**: End-of-epic reporting step

### Primary Flow (Happy Path)
1. Author compiles a written summary mapping attack type → outcome → consensus mode.
2. Author explicitly cross-references Epic 1's theoretical/literature expectations against the measured results from UC-1 through UC-5.
3. Author explicitly notes that PoW's Sybil-resistance (hash-power share) and PBFT's Sybil-resistance (`ValidatorSet` seat fraction) are measured on different axes and are not directly comparable node-for-node (PRD M-8), and that crash-fault (liveness) and Byzantine-fault (safety) findings for PBFT are reported as distinct classes, not merged into one generic "fault" category (PRD M-9).

**Postconditions**: A written summary of findings exists, suitable for direct inclusion in the thesis results chapter (matches the Epic 5 acceptance criterion).

### Error Flows
- **UC-8-E1: Measured results contradict Epic 1's theoretical expectations** — the discrepancy is explicitly documented and discussed as a finding requiring analysis, rather than omitted or silently smoothed over to match expectations.

### Edge Cases
- **UC-8-EC1**: Insufficient runs were completed to draw a confident conclusion for one consensus mode (e.g., time-constrained testing). The summary explicitly states this limitation rather than overstating confidence in an under-tested claim.

### Data Requirements
- **Input**: All recorded run outcomes (UC-6), threshold determinations (UC-3), and generated charts (UC-7).
- **Output**: Written findings summary (thesis section/document).
- **Side Effects**: None (documentation artifact only).
