# Test Cases: Attack Resistance Testing (Epic 5)

> Based on [PRD](../PRD.md) and [Use Cases](../use-cases/attack_resistance_testing_use_cases.md)

This document covers the attack scenario scripts and reporting pipeline run against the real Epic 3 docker-compose network: Sybil attacks against both PoW and PBFT, backdating/tampering attacks, attack-run data recording, and comparison-chart/findings generation (PRD Epic 5). Every UC scenario in `attack_resistance_testing_use_cases.md` (v1.3) is mapped below. Given this thesis's central contribution, extra weight is given to: measuring the Sybil attack against PoW by hash-power share (not node count) and confirming an attacker cannot lower difficulty (FR-24 rejects it), confirming a Sybil attack against PBFT via mere peer registration fails to inflate quorum (proves the `ValidatorSet`/`PeerInfo` separation from Epic 3), the backdating/tampering test's use of an out-of-band trusted key resolver (never the attacked node's own key-store), the separate attacker Docker image/component (never hooks in the honest node), the distinct crash-fault (liveness) vs. Byzantine-fault (safety) reporting, and comparison charts rendered on separate axes/panels for PoW vs. PBFT.

---

## 1. Run Sybil Attack Scenario Against a PoW Network (UC-1)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-1.1 | UC-1 primary | Spin up N attacker containers (from the separate attacker image), have them join and attempt to out-hash/flood at the network's honestly-configured difficulty | Attack outcome (disrupted / not disrupted) is recorded, indexed by the attacker's measured hash-power share (from per-container hash-rate) — never by raw node count |
| TC-1.2 | UC-1 step 3 (v1.3 reframing, central FR-24 cross-check) | Attacker mines and submits a block at a self-chosen, artificially LOW declared difficulty (cheaper to produce) | Block is rejected outright with `failure_type = "difficulty"` before it could ever count as a disruptive "win" — confirms an attacker cannot lower the effective difficulty |
| TC-1.3 | UC-1-A (M-13 closure) | Inspect the honest-node Docker image/codebase for attacker-mode conditionals, flags, or hooks | None found; the attacker's mining-bias/flooding behavior exists only in a separate Dockerfile/image and compose service that imports and overrides Epic 3's consensus engine from the outside |
| TC-1.4 | UC-1-B | Run the scenario repeatedly across a swept range of attacker hash-power configurations | Results bracket the minimum disruptive hash-power share via linear sweep or binary search |
| TC-1.5 | UC-1-E1 | Attacker containers fail to join the network (registration rejected or containers unreachable) | Run is aborted/retried and explicitly marked inconclusive/infra-failure — never silently recorded as "attack failed" |
| TC-1.6 | UC-1-E2 | Honest network crashes entirely during the attack (unintended side effect, e.g. resource exhaustion) | Run is flagged inconclusive, not counted as attacker success |
| TC-1.7 | UC-1-EC1 | Run with attacker hash-power share = 0 (baseline/control, no attackers or zero mining effort) | Confirms normal operation as a comparison baseline; expected outcome is "no disruption" |
| TC-1.8 | UC-1-EC2 | Run with attacker hash-power share at or above a simple majority of total network hash power | Expected to succeed in disrupting PoW consensus, validating the theoretical hash-power-majority expectation from Epic 1's research |

---

## 2. Run Sybil Attack Scenario Against a PBFT Network (UC-2)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-2.1 | UC-2 primary | Deploy N attacker containers occupying N of the n boot-time `ValidatorSet` seats (controlled-experiment redeployment) | Attacker seats are counted as `ValidatorSet` members for this run's quorum, distinct from mere `PeerInfo` registration |
| TC-2.2 | UC-2 primary | Run the attack and classify the outcome | Fork/invalid-block-finalized outcomes are classified as Byzantine/safety; stalled-finalization/quorum-loss outcomes are classified as crash/liveness, read from `GET /node/info`'s `quorum_status` |
| TC-2.3 | UC-2-A | Sweep the attacker `ValidatorSet` seat fraction across a range | Results bracket the minimum disruptive seat fraction for PBFT |
| TC-2.4 | UC-2-B (safety risk) | Attacker-controlled `ValidatorSet` members send conflicting `prepare`/`commit` votes to different honest peers, at/below the theoretical boundary `f = floor((n-1)/3)` | Honest vote-deduplication prevents any wrong block from being finalized; safety is preserved (result recorded distinctly from UC-2-C) |
| TC-2.5 | UC-2-C (liveness risk) | Attacker-controlled `ValidatorSet` members simply stop responding (no equivocation), tested at/below and above f | At/below f: consensus continues finalizing correctly. Above f: consensus stalls and reports quorum loss — labeled as a liveness failure, never conflated with a Byzantine/equivocation finding |
| TC-2.6 | UC-2-E1 | Test f=2 attacker-controlled seats against a fixed n=4 cluster (violates `n ≥ 3f+1`) | Run is recorded as an intentional, clearly-labeled boundary/over-limit test point — NOT reported as an implementation vulnerability |
| TC-2.7 | UC-2-EC1 | Set attacker seat fraction exactly at the theoretical safety boundary `f = floor((n-1)/3)` (Byzantine variant) | Consensus is NOT disrupted, confirming the theoretical guarantee; a contrary result is itself flagged as a critical must-report finding |
| TC-2.8 | UC-2-EC2 (central C-4 negative-control test) | Attacker containers register via `POST /peers/register` in large numbers WITHOUT ever being included in the boot-time `ValidatorSet` config | Zero effect on the PBFT quorum threshold or consensus outcomes — proves `PeerInfo`-only Sybil registration is structurally powerless against PBFT |

---

## 3. Determine Sybil-Resistance Threshold (UC-3)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-3.1 | UC-3 primary | Aggregate all UC-1/UC-2 run outcomes for a given consensus mode | Minimum disruptive attacker fraction is identified and reported on the algorithm-appropriate axis (PoW: hash-power share; PBFT: `ValidatorSet` seat fraction) — computed and reported independently, never merged into one shared metric |
| TC-3.2 | UC-3-E1 | No successful disruption is found within the tested bounds | Explicitly documented as "no threshold found within the tested range," never silently omitted from results |
| TC-3.3 | UC-3-EC1 | The measured threshold differs from the theoretical/literature expectation (implementation breaks earlier than the theoretical bound) | Recorded and discussed as a valid, important finding — never hidden or re-run until it "passes" |

---

## 4. Backdating/Tampering — Direct Chain-Store Mutation (UC-4)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-4.1 | UC-4 primary | Directly mutate a document record's timestamp/content, or a block's stored hash, in a node's persisted chain-store file, bypassing the API | Mutation is applied entirely outside the normal API path |
| TC-4.2 | UC-4 primary (v1.3 correction) | Trigger re-validation after the mutation via a node restart, or via an append/sync event | Re-validation runs and picks up the mutation — there is no periodic validation cycle to "wait for" |
| TC-4.3 | UC-4 primary (central M-2 mechanism test) | Run chain-validation using the harness's OWN injected key resolver, built from the out-of-band trust-anchor file(s), instead of the resolver Epic 3 would construct from the attacked node's local `IssuerRegistry`/`ValidatorSet` | Validation correctly reports invalid at the correct block index with the expected `failure_type`, using the out-of-band resolver |
| TC-4.4 | UC-4 primary | Verify the tampered document/chain via Epic 3's API directly: `GET /documents/{hash}` and `GET /node/info` | Both endpoints report the tampered document/chain as invalid/not-found, end-to-end, with no dependency on Epic 4's UI |
| TC-4.5 | UC-4-A | Mutate only non-hash metadata (e.g., recipient name), leaving `document_hash` unchanged | Detection confirms stored-hash-vs-content consistency is actually enforced by validation |
| TC-4.6 | UC-4-B | Mutate content AND recompute the block's own stored hash to match | Confirms hash-chain-only validation alone would be insufficient; `proposer_signature` verification is the necessary second detection layer |
| TC-4.7 | UC-4-E1 (central M-1 closure test) | Mutate a preimage field (`timestamp`, `index`, `previous_hash`, `merkle_root`, or consensus fields) at ANY block position and recompute `block_hash` to match | `proposer_signature` verification, checked against the out-of-band `NodeKeyPair` trust-anchor, independently catches the tamper regardless of position; if it fails to catch this, it is recorded as a critical security finding, never silently passed over |
| TC-4.8 | UC-4-E2 (central M-2 test) | Tamper document-record content and re-sign it with an attacker-controlled key | Verification against the out-of-band trusted `IssuerKeyPair` public key rejects the forged signature; the script explicitly asserts it used the out-of-band key source, not the attacked node's local key-store |
| TC-4.9 | UC-4-E2 (regression guard) | Attempt to run the same tamper scenario using the attacked node's OWN local key-store as the verification source instead of the out-of-band anchor | Test harness never falls back to the local key-store — this negative check confirms the M-2 requirement's implementation is not silently bypassable |
| TC-4.10 | UC-4-EC1 | Tamper a very early (near-genesis) block, and separately the most recently finalized block | Detection works identically regardless of the tampered block's position in the chain |
| TC-4.11 | UC-4-EC2 | Introduce multiple simultaneous tamper points in a single run | Validation correctly reports the EARLIEST failing index and `failure_type`; a follow-up scan after resolving the earliest issue reveals the subsequent ones |

---

## 5. Backdating/Tampering — Mid-Chain Block Injection (UC-5)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-5.1 | UC-5 primary | Construct a forged block with a falsified earlier timestamp positioned to appear mid-chain | Block is constructed with internally-consistent-looking but falsified content |
| TC-5.2 | UC-5-A (offline) | Insert the forged block via a direct chain-store file edit, then restart/reload the node | Node rejects it at chain-validation time (index/`previous_hash` sequencing broken or non-monotonic timestamp), with `failure_type = "structural"` or `"link"` |
| TC-5.3 | UC-5-B (online) | Attempt to introduce the forged block via live network broadcast or PBFT proposal | `proposer_signature` verification fails immediately (attacker lacks the honest node's `NodeKeyPair`); proposal is rejected and not re-broadcast, without even needing to reach the hash-chain-link check |
| TC-5.4 | UC-5-A | Repeat the offline path explicitly as its own isolated test (direct store-file edit + node restart/reload) | Same rejection outcome as TC-5.2, run in isolation |
| TC-5.5 | UC-5-B | Repeat the online path explicitly as its own isolated test (live broadcast/PBFT proposal attempt) | Same rejection outcome as TC-5.3, directly exercising Epic 3's real-time rejection path |
| TC-5.6 | UC-5-E1 | Attempt to renumber/shift all subsequent block indices to make the forged sequencing appear valid | Requires forging and re-signing every downstream block's preimage, which is only possible by compromising the honest node's `NodeKeyPair` (and the issuer's `IssuerKeyPair` for document content) — demonstrated as impractical; honest peers' full chain-sync revalidation (since the rewritten chain diverges before their tip) also rejects the rewritten version |
| TC-5.7 | UC-5-EC1 (central monotonicity test) | Inject a block with a falsified chronologically-earlier timestamp that is otherwise fully hash-consistent and carries a forged-but-internally-consistent `proposer_signature` (requiring a full downstream rewrite per TC-5.6) | Rejected via the non-monotonic-timestamp check with `failure_type = "structural"`, independent of and in addition to the honest-peer chain-sync rejection (second independent layer); a monotonicity check that fails to catch this is itself flagged as a critical finding |

---

## 6. Record Attack Run Outcome (UC-6)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-6.1 | UC-6 primary | Complete a run from any of UC-1/UC-2/UC-4/UC-5 | A row is appended to the results dataset recording `attack_type`, `consensus_mode`, `attacker_metric` (PoW: hash-power share; PBFT: `ValidatorSet` seat fraction — on the algorithm-appropriate field, never merged into one generic "fraction" column), `failure_class` where applicable, `hash_rate_sample` (PoW only), `outcome`, and `time_to_detection` where applicable |
| TC-6.2 | UC-6-E1 | The dataset file write fails (disk full / permission error) | Script surfaces a clear, explicit error; the run's outcome is NOT silently lost or treated as recorded |
| TC-6.3 | UC-6-EC1 | Re-run the same scenario/parameters a second time | A new row is appended rather than overwriting the prior record, preserving full run history |

---

## 7. Generate Comparison Charts (UC-7)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-7.1 | UC-7 primary | Run chart generation against a results dataset containing both PoW and PBFT finalization-latency data | A PoW-vs-PBFT block-finalization-latency chart is produced across varying difficulty/network sizes |
| TC-7.2 | UC-7 primary (central M-8 closure test) | Run chart generation against a results dataset containing both PoW and PBFT Sybil-attack outcomes | Sybil-resistance-threshold results are rendered as TWO SEPARATE PANELS — PoW (x-axis: attacker hash-power share) and PBFT (x-axis: attacker `ValidatorSet` seat fraction) — never merged onto a single shared node-count axis |
| TC-7.3 | UC-7 primary | Inspect the generated chart output files | Charts are exported as static image files (matplotlib/plotly) suitable for direct thesis inclusion |
| TC-7.4 | UC-7-A | Re-run the chart script against previously captured data with no new attack runs performed | Charts regenerate identically from the stored data, for thesis-defense reproducibility |
| TC-7.5 | UC-7-E1 | Run chart generation when the dataset is missing required fields/rows for a chart (e.g., no PBFT runs recorded yet) | Script explicitly reports which chart could not be generated and why, rather than silently producing a misleading empty/partial chart |
| TC-7.6 | UC-7-EC1 | Run the chart script twice on identical, unchanged input data | Produces byte-identical (or visually identical) output charts |

---

## 8. Produce Written Findings Summary (UC-8)

| # | Use Case | Test Case | Expected Result |
|---|----------|-----------|-----------------|
| TC-8.1 | UC-8 primary | Review the compiled written findings summary | Maps attack type → outcome → consensus mode for every completed scenario |
| TC-8.2 | UC-8 primary | Review the summary's treatment of Epic 1's research | Explicitly cross-references Epic 1's theoretical/literature expectations against the measured results from UC-1 through UC-5 |
| TC-8.3 | UC-8 primary (central non-comparability statement) | Review the summary's framing of Sybil-resistance results | Explicitly states that PoW's hash-power-share metric and PBFT's `ValidatorSet`-seat-fraction metric are measured on different axes and are not directly comparable node-for-node; crash-fault (liveness) and Byzantine-fault (safety) findings for PBFT are reported as distinct classes, never merged into one generic "fault" category |
| TC-8.4 | UC-8-E1 | Measured results contradict Epic 1's theoretical expectations | The discrepancy is explicitly documented and discussed as a finding requiring analysis, never omitted or silently smoothed over |
| TC-8.5 | UC-8-EC1 | Insufficient runs were completed to draw a confident conclusion for one consensus mode | Summary explicitly states this limitation rather than overstating confidence in an under-tested claim |
