# Implementation Plan — Decentralized Document Verification System

**Project:** Дипломна робота — «Децентралізована система верифікації документів на основі власної реалізації блокчейн-технології»
**Source documents:** [PRD v1.3 (FINAL, architecture-approved)](PRD.md), [use cases](use-cases/), [QA test cases](qa/)
**Created:** 2026-09-07
**Audience:** the thesis author, writing all code by hand, solo, over a multi-month timeline.

---

## 0. How to read this plan

This is a **personal roadmap**, not an agent execution script. Slices are sized as **one solid work chunk each (roughly 1–2 weeks of part-time solo thesis work)**, not as agent-sized PRs. Each slice is still:

- independently testable and independently committable (1 slice = 1 commit or a small commit series),
- traced to the use cases and QA test cases it closes,
- ordered so that no slice depends on work from a later slice,
- flagged where an architecture or security review pass is worth doing before writing the code.

**Wave assignment is deliberately NOT performed.** Waves exist to let parallel agents own disjoint file sets; here a single human executes strictly sequentially. Section 5 lists the few places where slices *could* be reordered or interleaved if you want variety, but the default is: top to bottom.

### ID prefix convention (important — IDs collide across documents)

The four use-case files and the four QA files each restart numbering at `UC-1` / `TC-1.1`. This plan disambiguates with an epic prefix:

| Prefix | Use cases file | Test cases file |
|---|---|---|
| `E2-UC-…` / `BC-TC-…` | `use-cases/blockchain_core_use_cases.md` | `qa/blockchain_core_test_cases.md` |
| `E3-UC-…` / `CN-TC-…` | `use-cases/consensus_network_use_cases.md` | `qa/consensus_network_test_cases.md` |
| `E4-UC-…` / `WI-TC-…` | `use-cases/web_interface_use_cases.md` | `qa/web_interface_test_cases.md` |
| `E5-UC-…` / `AT-TC-…` | `use-cases/attack_resistance_testing_use_cases.md` | `qa/attack_resistance_testing_test_cases.md` |

### TDD discipline per slice

For every code slice: write the listed test cases as **failing tests first**, then implement until green, then commit. `Verify:` gives the exact command; `Done when:` gives the boolean that must hold.

### Tooling assumptions (established in Slice 1 / Slice 20 / Slice 24)

- Python 3.11+, `pytest`, `ruff` (lint), `mypy` (types), `cryptography`, `fastapi`, `uvicorn`, `websockets`, `pydantic` v2.
- Frontend: React + TypeScript + Vite, `vitest` + React Testing Library.
- Analysis: `matplotlib` (primary) and/or `plotly`, `pandas`.
- Deployment: Docker + docker compose v2 (`docker compose`, not `docker-compose`).
- Commands are written to run from the repository root on Windows PowerShell **and** POSIX shells.

---

## 1. Prerequisites verified

| Prerequisite | Status |
|---|---|
| **PRD** — `docs/PRD.md` | Present. v1.3, FINAL, architecture-approved. Covers all 5 epics: §1 Epic 1 (research), §2 Epic 2 (blockchain core), §3 Epic 3 (consensus & network), §4 Epic 4 (React UI), §5 Epic 5 (attack resistance). |
| **Use cases** | Present, 4 files, all synced to PRD v1.3. `blockchain_core_use_cases.md` — 9 top-level UCs (UC-1…UC-9); `consensus_network_use_cases.md` — 14 UCs (UC-1…UC-14); `web_interface_use_cases.md` — 9 UCs; `attack_resistance_testing_use_cases.md` — 8 UCs. **40 top-level scenarios** plus alternative/error/edge sub-flows. |
| **QA test cases** | Present, 4 files, all synced to PRD v1.3. `blockchain_core_test_cases.md` — 108 TCs; `consensus_network_test_cases.md` — 115 TCs; `web_interface_test_cases.md` — 48 TCs; `attack_resistance_testing_test_cases.md` — 51 TCs. **≈322 test cases total.** |
| **Architecture review** | **PASS.** PRD v1.2 passed the second review round with 5 sentence-level polish items; v1.3 applies them and is marked "FINAL, architecture-approved" with no further review round required. Security-priority list carried into this plan's `Pre-review` flags. |
| **Existing source code** | **None.** The repository currently contains only `README.md`, `.gitignore`, and `docs/`. Every file path in this plan is therefore new; `[new]` is stated explicitly and no phantom existing paths are referenced. |

---

## 2. Target repository layout

Created incrementally by the slices below; listed here once so the plan's file paths are coherent.

```
pyproject.toml                    # Slice 1
src/blockchain_core/              # Epic 2 — pure library, NEVER imports src/node
  canonical.py  hashing.py  keys.py  signing.py
  document_record.py  merkle.py  block.py  genesis.py
  chain.py  validation.py
  storage/chain_store.py  storage/key_store.py
src/node/                         # Epic 3 — FastAPI node; may import blockchain_core
  main.py  config.py  errors.py  schemas.py
  registries.py  key_resolver.py  validity_cache.py  mempool.py  sync.py  metrics.py
  api/{peers,chain,documents,node_info,metrics}.py
  peers/registry.py
  network/{connection_manager,ws_blocks,ws_pbft}.py
  consensus/{base,pow}.py
  consensus/pbft/{messages,engine,view_change}.py
config/{validators.json,issuers.json,node.env.example}
docker/node.Dockerfile  docker/attacker.Dockerfile  docker-compose.yml
tests/core/…  tests/node/…  tests/vectors/canonical_vectors.json
web/                              # Epic 4 — React SPA
  src/api/client.ts  src/lib/{hash,merkle}.ts
  src/components/ConsensusModeBadge.tsx
  src/pages/{IssuePage,VerifyPage,ChainVisualizationPage}.tsx
  src/hooks/useBlockStream.ts
  src/__tests__/…
attacks/                          # Epic 5 — separate artifacts, own image
  attacker_node/{__init__,overrides}.py
  harness/{recorder,trust_anchor,resolver}.py
  scenarios/{sybil_pow,sybil_pbft,tamper_store,inject_block}.py
  analysis/{thresholds,charts}.py
results/attack_runs.csv  results/charts/
docs/research/epic1_blockchain_comparison.md
docs/results/findings.md
```

**Hard architectural constraint (from PRD FR-6 / E3-UC-14):** `src/blockchain_core/` must never import from `src/node/`. Keys, `expected_difficulty`, and `ValidatorSet` are always **injected parameters**. This is checked explicitly in Slice 11.

---

## 3. Deliverables and slices

### D1 (Deliverable, not a TDD slice): Epic 1 — Research of blockchain systems

- **Epic:** 1. **Depends on:** nothing. **Est.:** 1–2 weeks of reading and writing.
- **Use cases:** none (documentation-only epic). **PRD:** §1, FR-1…FR-5.
- **Files:** `docs/research/epic1_blockchain_comparison.md` `[new]`
- **Changes:** Write a thesis-ready chapter section covering: (a) blockchain construction principles — block structure, hash linking, Merkle trees, consensus, node roles; (b) Blockcerts analysis — data model, hashing/anchoring approach, revocation, verification flow; (c) at least one further system (EBSI / OpenCerts) — optional but encouraged; (d) a comparison table across the 5 PRD FR-3 dimensions (data model, hashing scheme, consensus, revocation, verification flow); (e) at least 3 design decisions for Epics 2–3 explicitly traced to a research finding (SHA-256 choice, PoW-vs-PBFT comparison choice, Merkle batching); (f) rationale for building from scratch instead of reusing Hyperledger/Ethereum. Cite sources.
- **Verify:** `Get-Content docs/research/epic1_blockchain_comparison.md | Select-String -Pattern "Blockcerts","Merkle","Comparison"` (POSIX: `grep -E "Blockcerts|Merkle|Comparison" docs/research/epic1_blockchain_comparison.md`)
- **Done when:** the file exists, contains a comparison table with ≥2 systems × 5 dimensions, and contains a clearly labelled subsection listing ≥3 design decisions each with an explicit back-reference to a research finding. No code is produced by this item.
- **Pre-review:** none.

---

### Slice 1: Project scaffold + canonical serialization spec and test vectors

- **Epic:** 2. **Depends on:** D1 (design justification only — can start in parallel). **Est.:** ~1 week.
- **Use cases:** E2-UC-2-EC3 (canonical reproducibility); PRD FR-4 (cross-cutting).
- **Test cases:** BC-TC-CS.1, CS.2, CS.3, CS.4, CS.5; BC-TC-2.13.
- **Files:**
  - `pyproject.toml` `[new]`, `.gitignore` (extend existing), `README.md` (extend existing — add a "Repository layout / how to run tests" section)
  - `src/blockchain_core/__init__.py` `[new]`, `src/blockchain_core/canonical.py` `[new]`, `src/blockchain_core/hashing.py` `[new]`
  - `tests/core/test_canonical.py` `[new]`, `tests/vectors/canonical_vectors.json` `[new]`
- **Changes:** Set up the Python package, pytest/ruff/mypy config, and test layout. `canonical.py`: one and only one encoder — JSON, keys sorted lexicographically, no insignificant whitespace, UTF-8, timestamps as integer epoch-ms (reject ISO strings and floats), hash/signature/public-key fields lowercase hex (reject or normalize uppercase). `hashing.py`: `sha256_hex(bytes)` and `sha256_of_canonical(obj)` wrappers so no call site ever calls `hashlib` directly. Freeze a set of input-struct → expected-canonical-bytes → expected-SHA-256 vectors in `tests/vectors/canonical_vectors.json` and treat them as immutable from this point on.
- **Verify:** `python -m pytest tests/core/test_canonical.py -v && python -m mypy src/blockchain_core && python -m ruff check src tests`
- **Done when:** every vector in `canonical_vectors.json` round-trips to its exact expected byte string and hash (BC-TC-CS.1); canonicalizing the same struct twice yields byte-identical output (BC-TC-CS.2); a struct with a float/ISO timestamp is rejected (BC-TC-CS.4); a struct with uppercase hex is rejected or lowercased (BC-TC-CS.5); `grep -rn "hashlib" src/` returns matches only inside `hashing.py` (BC-TC-CS.3).
- **Pre-review:** **architect** — the canonical spec and the `blockchain_core`/`node` package boundary are frozen here and everything else hashes against them.

---

### Slice 2: Key pairs, signature primitives, and signed DocumentRecords

- **Epic:** 2. **Depends on:** Slice 1. **Est.:** ~1–1.5 weeks.
- **Use cases:** E2-UC-1 (+A, B, E1–E3, EC1–EC3), E2-UC-6 (+A, E1–E4, EC1), E2-UC-9 (+A, B, E1–E3, EC1, EC2).
- **Test cases:** BC-TC-1.1…1.10, BC-TC-6.1…6.7, BC-TC-9.1…9.8.
- **Files:** `src/blockchain_core/keys.py` `[new]`, `src/blockchain_core/signing.py` `[new]`, `src/blockchain_core/document_record.py` `[new]`, `src/blockchain_core/storage/__init__.py` `[new]`, `src/blockchain_core/storage/key_store.py` `[new]`, `tests/core/test_keys.py` `[new]`, `tests/core/test_document_record.py` `[new]`
- **Changes:** `keys.py`: `IssuerKeyPair` and `NodeKeyPair` as two distinct types (never interchangeable), generated via `cryptography`, ECDSA P-256 default, RSA ≥2048 optional, RSA <2048 rejected. `key_store.py`: each key pair persisted to its **own** file; refuse to overwrite an existing key file without an explicit force flag; set restrictive file permissions best-effort. `signing.py`: `sign(payload_obj, private_key)` and `verify(payload_obj, signature, public_key)` operating on Slice 1's canonical bytes, with algorithm auto-dispatch from the public-key type and a handled `invalid` (never an exception) for malformed signature blobs. `document_record.py`: build `{document_hash, issuer_id, issued_at, metadata, signature, ipfs_cid?}`, validate `^[0-9a-f]{64}$` on the hash, accept raw bytes as an alternative input, sign with `IssuerKeyPair` only. No duplicate checking at this layer (BC-TC-1.8).
- **Verify:** `python -m pytest tests/core/test_keys.py tests/core/test_document_record.py -v`
- **Done when:** a record signed with an `IssuerKeyPair` verifies against its public key and fails after any single-byte change to signature, `document_hash`, `issuer_id`, `issued_at`, or `metadata` (BC-TC-6.3/6.4); verification with a different issuer's key returns `invalid` (BC-TC-6.5); a malformed signature blob returns `invalid` without raising (BC-TC-6.6); RSA-1024 generation is rejected (BC-TC-9.5); generating over an existing key file without a force flag leaves the file untouched (BC-TC-9.4); `NodeKeyPair` and `IssuerKeyPair` never share key material or a store file (BC-TC-9.3).
- **Pre-review:** **security** — key-store handling and signature verification are on the architecture review's security-priority list. Confirm private keys are never logged and never leave their store files.

---

### Slice 3: Merkle tree with domain separation + inclusion proofs

- **Epic:** 2. **Depends on:** Slice 1 (canonical bytes), Slice 2 (record bytes). **Est.:** ~1 week.
- **Use cases:** E2-UC-2 steps 3–4 (+A, B), E2-UC-5 (+A, E1–E3, EC1–EC3).
- **Test cases:** BC-TC-2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.11; BC-TC-5.1…5.8.
- **Files:** `src/blockchain_core/merkle.py` `[new]`, `tests/core/test_merkle.py` `[new]`
- **Changes:** RFC 6962-style construction: leaf = `H(0x00 || canonical_bytes(record))`, internal = `H(0x01 || left || right)`. Odd node at a level is **promoted unchanged** — never duplicated. `build_root(records)`, `build_proof(records, document_hash)` returning a sibling path that records left/right position and promotion steps, and `verify_proof(leaf_or_record, proof, claimed_root)`. N=1 degenerates to the leaf hash itself with an empty proof path.
- **Verify:** `python -m pytest tests/core/test_merkle.py -v`
- **Done when:** leaf and internal hashes match the exact domain-separated formulas byte-for-byte (BC-TC-2.2/2.3); a batch crafted to collide under naive last-leaf duplication produces a **different** root under this construction (BC-TC-2.5); every one of N generated proofs verifies against the root, and altering any single sibling hash makes verification fail (BC-TC-5.1/5.4); a proof from block A fails against block B's root (BC-TC-5.5); a proof for a promoted unpaired node still verifies (BC-TC-5.8); a several-hundred-leaf build completes well under O(n²) (BC-TC-2.11).
- **Pre-review:** **security** — collision resistance / CVE-2012-2459 class is the reason this construction was specified; verify the domain separation is applied at every level and that no code path duplicates the last leaf.

---

### Slice 4: Block structure — hashed preimage vs. attestations, and batch build

- **Epic:** 2. **Depends on:** Slices 1–3. **Est.:** ~1 week.
- **Use cases:** E2-UC-2 (primary, steps 5–7; E1, E2, E3, EC1–EC3).
- **Test cases:** BC-TC-2.1, 2.8, 2.9, 2.10, 2.12, 2.13.
- **Files:** `src/blockchain_core/block.py` `[new]`, `tests/core/test_block.py` `[new]`
- **Changes:** Define `Block` with three explicitly separated field groups: **hashed preimage** (`index`, `timestamp`, `previous_hash`, `merkle_root`, `proposer_id`, `algorithm` ∈ {`"pow"`,`"pbft"`,`"genesis"`}, `sealed_consensus`), **batch content** (`document_records` — stored but never hashed into `block_hash`; covered only via `merkle_root`), and **attestations** attached after hashing (`block_hash`, `proposer_signature`, PBFT-only `commit_signatures[]`). `build_candidate_block(records, previous_hash, index, proposer_id, algorithm, sealed_consensus)`: verify every record's signature first, reject the whole batch on any failure (naming the offending index), reject an empty batch, reject a batch containing the same `document_hash` twice, then compute `merkle_root` and `block_hash` over the canonical preimage only. `attach_proposer_signature(block, node_key)` as a separate post-hash step.
- **Verify:** `python -m pytest tests/core/test_block.py -v`
- **Done when:** mutating `document_records` without rebuilding leaves `block_hash` unchanged while `merkle_root` recomputation diverges — proving records are outside the preimage (BC-TC-2.1); an empty batch is rejected (BC-TC-2.8); a batch with one bad-signature record is rejected and the failing index is reported (BC-TC-2.9); a batch with a repeated `document_hash` is rejected outright, never deduplicated (BC-TC-2.10/2.12); building the same preimage twice yields an identical `block_hash` (BC-TC-2.13).
- **Pre-review:** **architect** — the preimage/attestation split is the schema decision every later epic depends on; confirm `proposer_id` is inside the preimage for both algorithms and that `sealed_consensus.primary_id` does not exist.

---

### Slice 5: Deterministic genesis + hash-chain append

- **Epic:** 2. **Depends on:** Slice 4. **Est.:** ~1 week.
- **Use cases:** E2-UC-3 (+A, E1, E2, EC1, EC2).
- **Test cases:** BC-TC-3.1…3.8.
- **Files:** `src/blockchain_core/genesis.py` `[new]`, `src/blockchain_core/chain.py` `[new]`, `tests/core/test_chain_append.py` `[new]`, `tests/core/test_genesis.py` `[new]`
- **Changes:** `genesis.py`: fixed constants `GENESIS_TIMESTAMP_MS`, `GENESIS_MERKLE_ROOT` (computed once at implementation time from zero leaves per the Slice 3 spec, then **hardcoded** — never recomputed per node), `previous_hash = "0"*64`, `algorithm = "genesis"` (reserved literal), empty `sealed_consensus`, sentinel `proposer_id = null` and `proposer_signature = null`. `chain.py`: an in-memory `Chain` that is **never empty** — genesis exists from construction; `append(block)` performs an atomic check-and-append verifying `previous_hash == hash(tip)` and `index == tip.index + 1`, rejecting stale-previous-hash, index skips, and index duplicates.
- **Verify:** `python -m pytest tests/core/test_genesis.py tests/core/test_chain_append.py -v`
- **Done when:** two independently constructed `Chain` objects, sharing only the config constants and with no communication, produce an identical genesis `block_hash` (BC-TC-3.7 — closes C-1); genesis carries `algorithm = "genesis"` and both sentinels (BC-TC-3.2); appending with a stale `previous_hash`, a skipped index, or a duplicate index is rejected (BC-TC-3.3/3.4/3.5); two concurrent appends for the same next index leave exactly one winner (BC-TC-3.6); a node built with a modified genesis constant produces a visibly different `block_hash` and is documented as unsupported (BC-TC-3.8).
- **Pre-review:** none.

---

### Slice 6: Chain validation — core checklist with injected key resolver

- **Epic:** 2. **Depends on:** Slice 5. **Est.:** ~1.5–2 weeks (the single most important slice in Epic 2).
- **Use cases:** E2-UC-4 primary steps a–f, Genesis exemption, UC-4-A, E1–E6, EC1–EC5.
- **Test cases:** BC-TC-4.1, 4.3, 4.4, 4.5, 4.11, 4.12, 4.13, 4.14, 4.15, 4.16, 4.17, 4.18, 4.19, 4.20, 4.21, 4.24, 4.25, 4.26, 4.27, 4.27b, 4.28.
- **Files:** `src/blockchain_core/validation.py` `[new]`, `tests/core/test_validation_core.py` `[new]`
- **Changes:** `validate_chain(blocks, *, resolve_node_key, resolve_issuer_key, expected_difficulty=None, validator_set=None) -> {valid, first_invalid_index, failure_type}`. Both resolvers are **time-aware callables** `(identity, at_timestamp) -> public_key | NOT_FOUND`, supplied by the caller — this function performs **no registry lookup and no network call**. Per non-genesis block, in order: recompute `block_hash` over the canonical preimage (`"hash"`); check `previous_hash` against the prior block's recomputed hash (`"link"`); recompute `merkle_root` (`"merkle"`); verify `proposer_signature` against `resolve_node_key(proposer_id, block.timestamp)` (`"signature"`); verify **every** `DocumentRecord.signature` against `resolve_issuer_key(record.issuer_id, block.timestamp)` (`"signature"` — the explicit v1.3 checklist step); verify non-decreasing timestamp and contiguous non-duplicate indices (`"structural"`). Genesis (`algorithm == "genesis"`) is exempt from the proposer checks and compared only against the frozen constants. A resolver returning NOT_FOUND fails closed as `"signature"`, never raises, never defaults to valid. A genuinely zero-length input is rejected as an invalid input state. Report the **earliest** failing index. Algorithm-specific checks are stubs raising `NotImplementedError` only if reached — they are implemented in Slice 7 and must be wired before Epic 3 uses this function.
- **Verify:** `python -m pytest tests/core/test_validation_core.py -v`
- **Done when:** a correct chain returns `{valid: true, first_invalid_index: null, failure_type: null}` (BC-TC-4.1); each of the five tamper classes returns its exact `failure_type` — `"hash"` (BC-TC-4.13), `"link"` (BC-TC-4.14), `"merkle"` (BC-TC-4.15), `"signature"` (BC-TC-4.4/4.20), `"structural"` for duplicate index, index gap, and decreasing timestamp (BC-TC-4.16/4.17/4.21); **tampering the tip block's `timestamp` with a self-consistently recomputed `block_hash` is caught with `failure_type = "signature"`** (BC-TC-4.18 — the M-1 closure); the same tamper at a middle block is also caught (BC-TC-4.19); a genesis-only chain validates (BC-TC-4.25) and a zero-block input is rejected (BC-TC-4.24); a resolver returning two different keys for the same `node_id` at two timestamps straddling a rotation validates both pre- and post-rotation blocks (BC-TC-4.3); an unknown identity fails closed (BC-TC-4.28); the earliest failing index is reported for both an early-block and a tip-block corruption (BC-TC-4.27/4.27b); a several-hundred-block chain validates in better than O(n²) (BC-TC-4.26).
- **Pre-review:** **security** + **architect** — signature verification and the injected-resolver contract are both on the security-priority list, and this function's signature is the Epic 3 → Epic 2 dependency boundary.

---

### Slice 7: Chain validation — PoW difficulty/target and PBFT commit-quorum checks

- **Epic:** 2. **Depends on:** Slice 6. **Est.:** ~1 week.
- **Use cases:** E2-UC-4 steps g, h; UC-4-E7, UC-4-E8.
- **Test cases:** BC-TC-4.2, 4.6, 4.7, 4.8, 4.9, 4.10, 4.22, 4.23.
- **Files:** `src/blockchain_core/validation.py` (extend), `tests/core/test_validation_consensus.py` `[new]`
- **Changes:** For `algorithm == "pow"`: interpret `block_hash` as an unsigned integer and require it to **numerically** satisfy the target derived from `sealed_consensus.difficulty` (not a leading-zero-character count), **and** require `sealed_consensus.difficulty == expected_difficulty` (injected) — otherwise `failure_type = "difficulty"`. For `algorithm == "pbft"`: require `commit_signatures[]` to contain ≥ `2f+1` signatures from **distinct** `ValidatorSet` members, each resolved via `resolve_node_key(node_id, block.timestamp)` and each validly signing the canonical preimage; repeated signers count once — otherwise `failure_type = "quorum"`. Both checks skip `algorithm == "genesis"` by definition. Document that this is the single checklist reused by proposal-time, sync-time, and cache-refresh callers.
- **Verify:** `python -m pytest tests/core/test_validation_consensus.py -v`
- **Done when:** a block whose hash has the right leading-zero *format* but fails the numeric target is rejected (BC-TC-4.6); a block that satisfies its own self-declared low difficulty but whose difficulty ≠ injected `expected_difficulty` is rejected with `"difficulty"` (BC-TC-4.7); a block failing its own declared target is rejected with `"difficulty"` (BC-TC-4.22); a PBFT block with <2f+1 distinct signers is rejected with `"quorum"` (BC-TC-4.8); padding with a repeated signer does not reach quorum (BC-TC-4.9); a valid PBFT chain validates (BC-TC-4.2).
- **Pre-review:** **security** — PBFT quorum counting and PoW difficulty enforcement are both explicitly on the security-priority list; an error here silently invalidates the whole Epic 5 comparison.

---

### Slice 8: Persistence — chain store, key stores, restart durability

- **Epic:** 2. **Depends on:** Slices 5–7. **Est.:** ~1 week.
- **Use cases:** E2-UC-8 (+A, E1–E5, EC1–EC3).
- **Test cases:** BC-TC-8.1…8.10.
- **Files:** `src/blockchain_core/storage/chain_store.py` `[new]`, `src/blockchain_core/storage/key_store.py` (extend), `tests/core/test_persistence.py` `[new]`
- **Changes:** Three independent logical stores: chain, `IssuerKeyPair`, `NodeKeyPair`. Chain store as JSON first with the interface shaped so a SQLite backend can be dropped in behind the same contract. On load: deserialize, then run Slice 6/7 validation before the node resumes. Fresh start with no chain file → initialize with the deterministic genesis block. Corrupt/truncated chain file → fail startup with a specific error, never proceed partially. Missing issuer key file → fail fast with an "issuer key material unavailable" error; missing node key file → fail fast with a **distinctly worded** "node key material unavailable" error; never silently regenerate either. Loaded-but-invalid chain → surface the validation result and refuse to extend the chain. Document the single-writer/file-locking requirement.
- **Verify:** `python -m pytest tests/core/test_persistence.py -v`
- **Done when:** save → reload produces a chain that validates and keys that sign/verify identically to before (BC-TC-8.1); the same test passes against both storage backends behind one contract (BC-TC-8.2); a fresh node with no chain file starts at genesis (BC-TC-8.3); a truncated file fails startup with a specific error (BC-TC-8.4); missing issuer vs. missing node key produce two distinct error messages (BC-TC-8.5/8.7); a chain tampered while the process was down is reported invalid at startup with its failing index and `failure_type` (BC-TC-8.6); reloading a PoW chain under a changed `expected_difficulty` fails with `"difficulty"` and this is documented as by-design (BC-TC-8.10); key files are not world-readable (BC-TC-8.9).
- **Pre-review:** **security** — persistence and key-store handling are on the security-priority list.

---

### Slice 9: Tamper-detection composite suite (Epic 2 acceptance gate)

- **Epic:** 2. **Depends on:** Slices 6–8. **Est.:** ~1 week. Mostly tests; this slice is the evidence base for the thesis's core tamper-evidence claim.
- **Use cases:** E2-UC-7 (+A, B, E1/EC1, EC2).
- **Test cases:** BC-TC-7.1…7.10.
- **Files:** `tests/core/test_tamper_detection.py` `[new]`, `docs/research/epic1_blockchain_comparison.md` (extend — add a short "implemented guarantees vs. surveyed systems" paragraph once the guarantees are proven)
- **Changes:** End-to-end scenarios operating on a persisted chain file: mutate a record's metadata; mutate a block preimage field; mutate `previous_hash`; mutate a middle block **and** recompute its own `block_hash`; mutate the tip block and recompute its `block_hash`; mutate and re-sign with an attacker-owned key. Each scenario reloads from disk and asserts the layer that catches it. Add a short table in the test module docstring mapping scenario → detecting layer → `failure_type`, to be lifted into the thesis text.
- **Verify:** `python -m pytest tests/core/test_tamper_detection.py -v`
- **Done when:** the middle-block sophisticated tamper is caught via `"link"` (BC-TC-7.6); the **tip-block** sophisticated tamper is caught **exclusively** via `proposer_signature` with `"signature"` (BC-TC-7.7 — the central M-1 test); a record-field-only tamper is caught independently by the `IssuerKeyPair` signature (BC-TC-7.8); a tamper re-signed with the attacker's own key still fails against the known public key (BC-TC-7.9); the timestamp-only tip tamper with recomputed hash is caught with `"signature"` (BC-TC-7.10). **Epic 2 is done when this slice is green.**
- **Pre-review:** none (it consumes already-reviewed code) — but re-read the Epic 2 acceptance criteria list in PRD §2 and tick every box before moving on.

---

### Slice 10: Node skeleton — config, registries, error envelope, validation, CORS, mode selection

- **Epic:** 3. **Depends on:** Slice 9 (Epic 2 complete). **Est.:** ~1 week.
- **Use cases:** E3-UC-1-C, E3-UC-1-D, E3-UC-11 (+E1, E2, EC1), E3-UC-14-E2; cross-cutting FR-19 error envelope + Pydantic validation + CORS.
- **Test cases:** CN-TC-1.3, 1.5, 1.6, 11.1, 11.2, 11.3, 14.6, EV.1, EV.2, EV.3, EV.4.
- **Files:** `src/node/__init__.py` `[new]`, `src/node/main.py` `[new]`, `src/node/config.py` `[new]`, `src/node/errors.py` `[new]`, `src/node/schemas.py` `[new]`, `src/node/registries.py` `[new]`, `config/validators.json` `[new]`, `config/issuers.json` `[new]`, `config/node.env.example` `[new]`, `tests/node/test_config.py` `[new]`, `tests/node/test_error_envelope.py` `[new]`
- **Changes:** FastAPI app factory. `config.py`: `NODE_ID`, `CONSENSUS_MODE` (`pow`|`pbft`, fail-fast on an unrecognized value, one documented default-or-fail-fast policy for a missing value), `EXPECTED_DIFFICULTY`, key-store paths, seed peers, CORS origins (config-driven, not hardcoded), max page size, metadata byte cap. `registries.py`: load static `ValidatorSet` (`node_id`, `node_public_key`, nullable `retired_at`, network-wide `n`/`f` with `n ≥ 3f+1`) and network-wide `IssuerRegistry` (`issuer_id → public_key`); never mutated at runtime; never derived from peers; both logged at boot; missing/malformed config → fail fast. `errors.py`: one exception handler emitting `{"error": {"code", "message", "details"}}` for every error path. `schemas.py`: shared Pydantic types including the `^[0-9a-f]{64}$` hash constraint and the metadata size cap.
- **Verify:** `python -m pytest tests/node/test_config.py tests/node/test_error_envelope.py -v`
- **Done when:** boot logs contain the loaded `ValidatorSet` (`n`, `f`) and `IssuerRegistry` `issuer_id` (CN-TC-1.3/1.5); a malformed or missing registry file causes fail-fast startup (CN-TC-14.6); an invalid `CONSENSUS_MODE` fails startup with an explicit error rather than defaulting (CN-TC-11.2); every error response on every registered route matches the exact envelope shape (CN-TC-EV.1); a non-`^[0-9a-f]{64}$` hash and an over-cap metadata value are both rejected as validation errors (CN-TC-EV.2/EV.3); CORS allows the configured frontend origin and is changeable via config alone (CN-TC-EV.4).
- **Pre-review:** **architect** — registry shapes and config surface are consumed by every later Epic 3 slice.

---

### Slice 11: Time-aware key resolver, validity cache, and `GET /node/info`

- **Epic:** 3. **Depends on:** Slice 10. **Est.:** ~1 week.
- **Use cases:** E3-UC-14 (+A, E1, E2, EC1, EC2), E3-UC-12 (+A, E1, EC1–EC3).
- **Test cases:** CN-TC-14.1…14.8, CN-TC-12.1…12.8, CN-TC-1.4.
- **Files:** `src/node/key_resolver.py` `[new]`, `src/node/validity_cache.py` `[new]`, `src/node/api/__init__.py` `[new]`, `src/node/api/node_info.py` `[new]`, `tests/node/test_key_resolver.py` `[new]`, `tests/node/test_node_info.py` `[new]`
- **Changes:** `key_resolver.py`: build one combined resolver object from `ValidatorSet` (including `retired_at` entries) + `IssuerRegistry`, exposing `resolve_node_key(node_id, at_timestamp)` and `resolve_issuer_key(issuer_id, at_timestamp)`, each selecting the key active at that timestamp and returning an explicit NOT_FOUND (never `None`-as-valid, never an exception) for unknown identities. Rebuildable on config reload without retroactively invalidating in-flight validations. `validity_cache.py`: holds `{chain_valid, first_invalid_index, quorum_status, tip_index}`, initialized at boot and updated **incrementally on append/replace events only** — no periodic revalidation, no per-request full revalidation. `api/node_info.py`: `GET /node/info` returning `{node_id, algorithm, n, f, node_public_key, tip_index, chain_valid, first_invalid_index, quorum_status}` read from the cache.
- **Verify:** `python -m pytest tests/node/test_key_resolver.py tests/node/test_node_info.py -v`
- **Done when:** `resolve_node_key(node_id, t)` returns the **old** key for `t ≤ retired_at` and the **new** key for `t >` rotation, for the same `node_id` (CN-TC-14.7 — the central time-aware test); a retired entry is excluded from active `n`/`f` counting but stays resolvable (CN-TC-14.7); an unknown identity returns NOT_FOUND and the calling validation reports `"signature"` (CN-TC-14.5); `GET /node/info` returns all nine fields with correct values (CN-TC-12.1) and works on a genesis-only node with `chain_valid = true` (CN-TC-12.3); an invalid chain yields HTTP 200 with `chain_valid = false` plus `first_invalid_index` (CN-TC-12.4); measured `GET /node/info` latency on a several-hundred-block chain is within noise of the latency on a 2-block chain (CN-TC-12.7); a static check confirms `blockchain_core` contains no import of `src.node` and performs no registry lookup (CN-TC-14.3).
- **Pre-review:** **security** — the resolver is the trust anchor for every signature check in the system.

---

### Slice 12: Peer registry REST (`/peers`) and paginated `GET /chain`

- **Epic:** 3. **Depends on:** Slice 11. **Est.:** ~1 week.
- **Use cases:** E3-UC-1 (+A, E1–E3, EC1, EC2), E3-UC-2 (+E1), E3-UC-3-D, E3-UC-3-E4.
- **Test cases:** CN-TC-1.1, 1.2, 1.7…1.11, 2.1, 2.2, 3.6, 3.10, EV.5.
- **Files:** `src/node/peers/__init__.py` `[new]`, `src/node/peers/registry.py` `[new]`, `src/node/api/peers.py` `[new]`, `src/node/api/chain.py` `[new]`, `tests/node/test_peers.py` `[new]`, `tests/node/test_chain_api.py` `[new]`
- **Changes:** `PeerInfo` registry (`node_id`, `host`, `port`, `public_key` = the peer's `NodeKeyPair` public key, `last_seen`) — dynamic, gossip-populated, **structurally disconnected from `ValidatorSet`**. `POST /peers/register` merges/updates on re-registration rather than duplicating, rejects self-registration, rejects malformed payloads via the envelope, and returns the receiver's current peer list. `GET /peers` returns `PeerInfo` only (never `ValidatorSet`), empty list on a fresh node. Seed-peer registration at startup retries with backoff instead of crashing. `GET /chain?from=&to=` returns a bounded range with a server-enforced max page size and never an unbounded dump — including when called with no parameters.
- **Verify:** `python -m pytest tests/node/test_peers.py tests/node/test_chain_api.py -v`
- **Done when:** mutual registration leaves both nodes aware of each other and A merges B's list (CN-TC-1.1); re-registering the same `node_id` updates `last_seen`/`host`/`port` with no duplicate entry (CN-TC-1.8); self-registration is ignored (CN-TC-1.10); an unreachable seed peer triggers backoff retries, not a crash (CN-TC-1.7); flooding thousands of registrations neither crashes the node nor changes any quorum-related value (CN-TC-1.11 — asserted directly against `GET /node/info`'s `n`/`f`); `GET /chain` with no parameters on a chain longer than the max page size returns exactly the capped page (CN-TC-EV.5); an over-max requested range is truncated or rejected (CN-TC-3.10).
- **Pre-review:** **security** — peer registration is the Sybil attack surface Epic 5 targets; confirm registration can never touch `ValidatorSet` and that unbounded `PeerInfo` growth degrades only connectivity.

---

### Slice 13: `POST /documents` (server-side issuer signing, duplicate policy, mempool) and `GET /documents/{hash}`

- **Epic:** 3. **Depends on:** Slice 12. **Est.:** ~1–1.5 weeks.
- **Use cases:** E3-UC-4 (+A, E1–E6, EC1, EC2), E3-UC-13 (+A, E1, E2, EC1, EC2).
- **Test cases:** CN-TC-4.1…4.13, CN-TC-13.1…13.6.
- **Files:** `src/node/mempool.py` `[new]`, `src/node/api/documents.py` `[new]`, `tests/node/test_documents_submit.py` `[new]`, `tests/node/test_documents_lookup.py` `[new]`
- **Changes:** `POST /documents` accepts **only** `{hash, metadata}` — a body containing `signature` (or any pre-signed record shape) is a 400 validation error. Order of operations is fixed: validate shape/hash pattern/metadata cap → acquire a per-hash (or global) submission lock → reject `409 Conflict` if the hash is in **any finalized block OR the current pending batch/mempool** → assemble `{document_hash, issuer_id (from IssuerRegistry), issued_at (now, epoch-ms), metadata}` → sign server-side with the node's `IssuerKeyPair` → queue → release lock → return an accepted/queued acknowledgement. Under PBFT, a non-primary node signs with **its own** configured issuer identity and forwards the **already-signed** record to the primary; the proposer never re-signs or reassigns `issuer_id`. `GET /documents/{hash}` returns `{issuer_id, issued_at, block_index, merkle_proof}` on hit and HTTP 404 via the envelope on miss, with the path parameter validated before any chain search.
- **Verify:** `python -m pytest tests/node/test_documents_submit.py tests/node/test_documents_lookup.py -v`
- **Done when:** a valid submission produces a server-signed record whose signature verifies against the configured issuer public key, with no client involvement (CN-TC-4.1); a body containing `signature` is rejected 400 (CN-TC-4.4); a hash already finalized returns 409 and assembles/signs nothing (CN-TC-4.10); a hash already **pending in the mempool** also returns 409 (CN-TC-4.11 — the v1.3 broadening); two concurrent submissions of the same hash yield exactly one acceptance and one 409 (CN-TC-4.13); a malformed hash or over-cap metadata is rejected before the duplicate check (CN-TC-4.8/4.9); lookup returns 200 with a Merkle proof that verifies against the block's stored root (CN-TC-13.1) and a never-issued hash returns 404 via the envelope (CN-TC-13.2).
- **Pre-review:** **security** — server-side issuer signing, the unsigned-submission contract, and the duplicate-hash lock are all trust-boundary logic.

---

### Slice 14: PoW consensus engine + consensus metrics endpoint

- **Epic:** 3. **Depends on:** Slice 13. **Est.:** ~1 week.
- **Use cases:** E3-UC-5 (+A, E1, E2, EC1–EC3), E3-UC-9 (+A, E1, EC1, EC2).
- **Test cases:** CN-TC-5.1…5.7, CN-TC-9.1…9.5.
- **Files:** `src/node/consensus/__init__.py` `[new]`, `src/node/consensus/base.py` `[new]`, `src/node/consensus/pow.py` `[new]`, `src/node/metrics.py` `[new]`, `src/node/api/metrics.py` `[new]`, `tests/node/test_pow.py` `[new]`, `tests/node/test_metrics.py` `[new]`
- **Changes:** `base.py`: a small engine interface (`on_submission`, `on_inbound_block`, `start`, `stop`) both algorithms implement, so `CONSENSUS_MODE` selects one implementation. `pow.py`: an **interruptible** async mining loop varying `sealed_consensus.nonce` inside the preimage until the hash meets the configured target; on success attach `proposer_signature`, append locally, update the validity cache, and hand the block to the broadcast layer (wired in Slice 15). Abandon the loop and re-queue unincluded records when a valid competing block for the same height arrives. `metrics.py` + `GET /metrics/consensus`: `ConsensusMetric` rows (`block_index`, `algorithm`, `proposed_at`, `finalized_at`, `attempts_or_rounds`, PoW `hash_rate`), excluding in-flight rounds, empty list on a fresh node, no overflow/truncation on large attempt counts.
- **Verify:** `python -m pytest tests/node/test_pow.py tests/node/test_metrics.py -v`
- **Done when:** a mined block's hash satisfies the configured target, carries a valid `proposer_signature`, and passes Slice 7 validation (CN-TC-5.1); raising the configured difficulty with no code change measurably increases time-to-finalize as reported by `GET /metrics/consensus` (CN-TC-5.2); a competing valid block arriving mid-mining aborts the loop within one poll interval and re-queues the pending batch (CN-TC-5.3/5.7); the metrics endpoint returns per-block finalization time plus a per-node `hash_rate` sample (CN-TC-9.1) and an empty list on a fresh node (CN-TC-9.3).
- **Pre-review:** none.

---

### Slice 15: WebSocket layer — `PeerConnectionManager`, block broadcast, inbound authentication

- **Epic:** 3. **Depends on:** Slice 14. **Est.:** ~1.5 weeks.
- **Use cases:** E3-UC-7 (+A, E1, E2, EC1, EC2), E3-UC-8 (+E1–E4, EC1, EC2), E3-UC-6-F.
- **Test cases:** CN-TC-7.1…7.6, CN-TC-8.1…8.7, CN-TC-6.6.
- **Files:** `src/node/network/__init__.py` `[new]`, `src/node/network/connection_manager.py` `[new]`, `src/node/network/ws_blocks.py` `[new]`, `tests/node/test_connection_manager.py` `[new]`, `tests/node/test_block_broadcast.py` `[new]`
- **Changes:** `PeerConnectionManager`: each node is simultaneously a WS **server** (accepting inbound) and a WS **client** (maintaining outbound connections to every `PeerInfo` peer **and** every `ValidatorSet` member); fan-out uses whichever direction is established; reconnect with capped exponential backoff; per-peer health (`up`/`reconnecting`/`down`) exposed for metrics and `GET /node/info`. `ws_blocks.py`: `WS /ws/blocks` push on finalization; on receipt, run the **single** Slice 6/7 validation checklist with the Slice 11 resolver before doing anything else. Rejection rules: no/empty `proposer_signature` → reject; signature from a key not in `PeerInfo`/`ValidatorSet` → reject; valid signature but broken link/merkle → reject with the right `failure_type`; conflicting block at an already-finalized index → reject, first-finalized wins, and log an equivocation event if the sender is a validator; stale replay → reject. A rejected block is never appended and **never re-broadcast**. Duplicate delivery of an already-appended block is a no-op. A block that does not extend the local tip falls back to chain sync (implemented next slice — until then, log and skip).
- **Verify:** `python -m pytest tests/node/test_connection_manager.py tests/node/test_block_broadcast.py -v`
- **Done when:** a block broadcast by one node is fast-appended by peers connected in **either** direction (CN-TC-7.1/6.6); a downed connection reconnects with capped backoff and per-peer health is visible via `GET /node/info` (CN-TC-7.2); an unsigned block, a block signed by an unknown key, and a block with a broken link are each rejected **and not re-broadcast** (CN-TC-8.2/8.3/8.4, CN-TC-7.3); a duplicate arrival is a no-op (CN-TC-7.5); simultaneous high fan-out produces no state corruption in the append path (CN-TC-7.6).
- **Pre-review:** **security** — inbound block/proposal authentication is on the security-priority list; confirm there is exactly one validation entry point and no "trusted peer" shortcut.

---

### Slice 16: Chain synchronization and fork resolution

- **Epic:** 3. **Depends on:** Slice 15. **Est.:** ~1.5 weeks.
- **Use cases:** E3-UC-3 (+A, B, D, E1–E4, EC1–EC3).
- **Test cases:** CN-TC-3.1…3.5, 3.7, 3.8, 3.9, 3.11, 3.12, 3.13, 3.14; CN-TC-12.8.
- **Files:** `src/node/sync.py` `[new]`, `tests/node/test_chain_sync.py` `[new]`, `tests/node/test_fork_resolution.py` `[new]`
- **Changes:** Periodic/on-demand `GET /chain` from peers (paginated for long histories). Classify the incoming chain: **strict non-diverging extension** → validate incrementally from the local tip; **diverges before the local tip** → run **full validation from genesis** over the entire incoming chain, never incremental. Both modes use the identical Slice 6/7 checklist with the Slice 11 resolver — including PBFT `commit_signatures` quorum verification. Adoption rule: PoW longest-valid-chain; PBFT highest latest-finalized-height. Tie-break: **PoW only**, lowest tip `block_hash` as an unsigned integer — order-independent, never "first observed". **PBFT same-height differing finalized blocks must never be tie-broken**: log a Byzantine/safety-violation event and set `quorum_status` accordingly. On adoption, replace local state, persist, and update the validity cache. An in-progress mining/PBFT round is cleanly abandoned and restarted against the newly adopted chain.
- **Verify:** `python -m pytest tests/node/test_chain_sync.py tests/node/test_fork_resolution.py -v`
- **Done when:** a strict extension takes the incremental path and a divergent chain provably takes the **full-from-genesis** path (assert via an instrumented call counter — CN-TC-3.1/3.2, closes M-14); the checklist executed during sync is byte-for-byte the same function used at proposal time and cache refresh (CN-TC-3.3, CN-TC-12.8); two equal-length PoW chains resolve to the lowest tip hash **regardless of arrival order** (CN-TC-3.11); two differently-finalized PBFT blocks at the same height are **not** silently resolved and instead surface as a Byzantine event in `quorum_status` (CN-TC-3.12); an invalid peer chain is rejected wholesale with the local chain retained and the peer flagged (CN-TC-3.7); timeouts, truncated JSON, and long paginated catch-ups all fail or complete gracefully without hanging (CN-TC-3.8/3.9/3.14).
- **Pre-review:** **security** — chain-sync fork adoption is on the security-priority list; a wrong adoption rule silently defeats every tamper guarantee proven in Slice 9.

---

### Slice 17: PBFT three-phase protocol — pre-prepare / prepare / commit

- **Epic:** 3. **Depends on:** Slice 16. **Est.:** ~2 weeks (largest single slice).
- **Use cases:** E3-UC-6 primary (+A, B, F), quorum-scope note, E3-UC-6-E3, EC1, EC3.
- **Test cases:** CN-TC-6.1, 6.2, 6.3, 6.4, 6.5, 6.9, 6.14.
- **Files:** `src/node/consensus/pbft/__init__.py` `[new]`, `src/node/consensus/pbft/messages.py` `[new]`, `src/node/consensus/pbft/engine.py` `[new]`, `src/node/network/ws_pbft.py` `[new]`, `tests/node/test_pbft_rounds.py` `[new]`
- **Changes:** `messages.py`: `pre-prepare` / `prepare` / `commit` payloads keyed by `(view, seq, block_hash)`, each signed with the sender's `NodeKeyPair` and verified on receipt. `engine.py`: primary proposes a candidate block over `WS /ws/pbft` via `PeerConnectionManager`; replicas validate the candidate with the standard checklist before sending `prepare`; quorum is counted **exclusively over the static `ValidatorSet`**, never over `PeerInfo`; the primary's own `pre-prepare` counts as its implicit `prepare` vote (implemented and commented explicitly at the counting site); on 2f+1 matching commits the block is finalized, `commit_signatures[]` is attached as an attestation **after** hashing, the block is appended, the validity cache and metrics (round counts) are updated, and the block is broadcast. Message handling is idempotent under duplicate/out-of-order delivery; commits arriving without a preceding prepare-quorum are rejected on phase ordering.
- **Verify:** `python -m pytest tests/node/test_pbft_rounds.py -v`
- **Done when:** a full round on n=4/f=1 finalizes the identical block on every correct member, and the resulting block passes Slice 7's `commit_signatures` quorum check (CN-TC-6.1); registering many extra `PeerInfo` peers leaves the 2f+1 threshold and the round outcome unchanged (CN-TC-6.2 — the central C-4 test); the primary reaches quorum for its own proposal **without** sending itself a `prepare` (CN-TC-6.3); stopping exactly 1 of 4 members still finalizes and is reported as normal operation, not a fault (CN-TC-6.5); an out-of-sequence `commit` is rejected (CN-TC-6.9); duplicated/reordered messages do not double-count votes (CN-TC-6.14).
- **Pre-review:** **security** + **architect** — PBFT quorum logic is the top item on the security-priority list; review the counting rule, the distinct-signer requirement, and the message-authentication path before implementing.

---

### Slice 18: PBFT view-change, equivocation detection, crash-vs-Byzantine reporting

- **Epic:** 3. **Depends on:** Slice 17. **Est.:** ~1.5 weeks.
- **Use cases:** E3-UC-6-D (simplified view-change), E3-UC-6-E1, E2, E4, E5; E3-UC-6-EC2; E3-UC-12-EC1; E3-UC-15 semantics (crash vs. Byzantine).
- **Test cases:** CN-TC-6.7, 6.8, 6.10, 6.11, 6.12, 6.13; CN-TC-12.5; CN-TC-8.5.
- **Files:** `src/node/consensus/pbft/view_change.py` `[new]`, `src/node/consensus/pbft/engine.py` (extend), `src/node/validity_cache.py` (extend — `quorum_status` states), `tests/node/test_pbft_view_change.py` `[new]`, `tests/node/test_fault_classification.py` `[new]`
- **Changes:** Deterministic round-robin view-change `primary = view_number mod n` over the `ValidatorSet`, triggered by a configurable round timeout or by a primary proposing an invalid block. Explicitly **no** state-transfer, checkpoint, or watermark protocol — say so in a code comment at the implementation site and in the thesis text. Equivocation handling: count at most one vote per `node_id` per `(view, seq)`; a second, conflicting vote is discarded and logged as a **Byzantine/equivocation** event. `quorum_status` gains distinct states: healthy / view-change-in-progress / **crash-fault quorum loss** (insufficient responsive replicas) / **Byzantine event detected** — never conflated. A view-change storm must converge or persistently report the condition rather than looping silently.
- **Verify:** `python -m pytest tests/node/test_pbft_view_change.py tests/node/test_fault_classification.py -v`
- **Done when:** an invalid proposal from the primary yields no `prepare` votes and triggers a view change (CN-TC-6.7); a validator equivocating to different peers is deduplicated, cannot advance quorum, and is logged as a Byzantine event **distinct from** any crash report (CN-TC-6.8, CN-TC-8.5); stopping 2 of 4 members stalls finalization and reports **crash-fault** quorum loss with no wrong block ever finalized (CN-TC-6.11); a round timeout advances the view via `view_number mod n` (CN-TC-6.10/6.12); repeated primary failures converge or report persistently, never loop silently (CN-TC-6.13); `GET /node/info` during a view change reports the in-progress state rather than a binary healthy/lost (CN-TC-12.5).
- **Pre-review:** **security** — view-change and equivocation handling are both on the security-priority list, and Epic 5's PBFT scenarios measure exactly this code.

---

### Slice 19: Docker image and multi-node docker-compose network (Epic 3 acceptance gate)

- **Epic:** 3. **Depends on:** Slice 18. **Est.:** ~1 week.
- **Use cases:** E3-UC-10 (+A, E1, E2, EC1), E3-UC-11-EC1.
- **Test cases:** CN-TC-10.1…10.5, CN-TC-11.4, CN-TC-1.6.
- **Files:** `docker/node.Dockerfile` `[new]`, `docker-compose.yml` `[new]`, `config/validators.json` (extend — the 4-node demo set), `config/issuers.json` (extend — the single shared demo issuer), `tests/node/test_compose_smoke.py` `[new]`, `README.md` (extend — how to run the network)
- **Changes:** One honest-node image. Compose file defining ≥4 node services on a shared Docker network, each with a distinct host port, its own key-store volume, seed-peer wiring, and env-driven `CONSENSUS_MODE`/`EXPECTED_DIFFICULTY`. Warn loudly at boot when the configured node count violates `n ≥ 3f+1` for the intended `f`. Detect and reject fundamentally incompatible messages from a mismatched-mode peer instead of corrupting local state. A smoke test script that brings the network up, submits a document, and asserts convergence.
- **Verify:** `docker compose up -d --build; python -m pytest tests/node/test_compose_smoke.py -v; docker compose down -v`
- **Done when:** `docker compose up` starts ≥4 nodes, each logging its `ValidatorSet` (`n`, `f`) and shared `IssuerRegistry` `issuer_id`, each reachable on a distinct port, converging to full peer awareness (CN-TC-10.1, CN-TC-1.6); a document submitted to one node appears in a finalized block on **all** other nodes in **both** PoW and PBFT modes (Epic 3 acceptance criterion); one crash-looping container does not hang the rest (CN-TC-10.4); an `n < 3f+1` configuration warns at startup (CN-TC-10.5); a mixed pow/pbft cluster rejects incompatible messages without crashing (CN-TC-11.4). **Epic 3 is done when this slice is green** — re-check every PRD §3 acceptance box here.
- **Pre-review:** **architect** — container topology and volume/key placement affect Epic 5's attacker-image boundary.

---

### Slice 20: React app scaffold, API client, node selector, consensus-mode badge

- **Epic:** 4. **Depends on:** Slice 19. **Est.:** ~1 week.
- **Use cases:** E4-UC-9 (+E1, EC1, EC2); node-selection plumbing for E4-UC-8.
- **Test cases:** WI-TC-9.1…9.5.
- **Files:** `web/package.json` `[new]`, `web/vite.config.ts` `[new]`, `web/src/main.tsx` `[new]`, `web/src/App.tsx` `[new]`, `web/src/api/client.ts` `[new]`, `web/src/api/types.ts` `[new]`, `web/src/state/nodeSelection.ts` `[new]`, `web/src/components/ConsensusModeBadge.tsx` `[new]`, `web/src/__tests__/ConsensusModeBadge.test.tsx` `[new]`
- **Changes:** Vite + React + TypeScript app with routing for Issue / Verify / Chain pages. `client.ts`: typed wrappers for `POST /documents`, `GET /documents/{hash}`, `GET /chain`, `GET /node/info`, `GET /metrics/consensus`, plus a `WS /ws/blocks` subscriber; it must decode the `{"error": {...}}` envelope and expose `status` so callers can distinguish 400 / 404 / 409 / network failure. Node selection stored in app state (base URL per node, configurable list). `ConsensusModeBadge` sources `algorithm` from **`GET /node/info`**, never from `GET /metrics/consensus`.
- **Verify:** `npm --prefix web ci; npm --prefix web run test; npm --prefix web run build`
- **Done when:** the badge renders "PoW"/"PBFT" from `GET /node/info` (WI-TC-9.1); it shows an explicit "unknown" state when the endpoint is unreachable rather than a stale label (WI-TC-9.3); switching between nodes with different modes updates the badge independently with no cached carry-over (WI-TC-9.4); a freshly started genesis-only node still shows its configured algorithm immediately (WI-TC-9.5).
- **Pre-review:** **architect** — freeze the API client's error-discrimination contract (404 vs. 409 vs. network) here; every later UI slice depends on it.

---

### Slice 21: Issue page — client-side hashing, unsigned submission, 409 handling, confirmation tracking

- **Epic:** 4. **Depends on:** Slice 20. **Est.:** ~1.5 weeks.
- **Use cases:** E4-UC-1 (+A, B, E1–E4, EC1, EC2), E4-UC-2 (+E1, E2, EC1), E4-UC-3 (+A, E1, E2, EC1).
- **Test cases:** WI-TC-1.1…1.10, WI-TC-2.1…2.4, WI-TC-3.1…3.5.
- **Files:** `web/src/lib/hash.ts` `[new]`, `web/src/pages/IssuePage.tsx` `[new]`, `web/src/hooks/useBlockStream.ts` `[new]`, `web/src/__tests__/IssuePage.test.tsx` `[new]`, `web/src/__tests__/hash.test.ts` `[new]`
- **Changes:** `hash.ts`: SHA-256 over a file via the **Web Crypto API** with streaming/chunked reads so the UI thread never blocks; the raw file is never uploaded. Issue page: file-picker **and** drag-and-drop entry points sharing one downstream flow; a pasted-hash alternative with trim+lowercase normalization and `^[0-9a-f]{64}$` client validation; metadata fields (recipient identifier, document title). Submit an **unsigned** `{hash, metadata}` body — the browser must never construct a signature or hold key material. Error mapping: 409 → a distinct, explicit duplicate-submission message (never a silent no-op, never an auto-retry, never merged with the network-error state); other API rejections → surface the node's reported reason. `useBlockStream`: subscribe to `WS /ws/blocks`, fall back to polling `GET /chain` when the socket is unavailable or drops, show an explicit "still pending / possible network issue" state after a timeout, and clean up safely on unmount.
- **Verify:** `npm --prefix web run test -- IssuePage hash`
- **Done when:** submitting a file issues exactly one `POST /documents` whose body contains only `hash` and `metadata` and no signature field, with no request carrying the file bytes (WI-TC-1.1); a 409 renders a duplicate-specific error distinct from the network-error state (WI-TC-1.7/1.8/1.10, WI-TC-2.3); an empty form is blocked client-side with no request sent (WI-TC-1.4); a 0-byte file still hashes and submits (WI-TC-1.9); a pasted uppercase/whitespace hash is normalized before submission (WI-TC-2.4); confirmation shows block index and hash on the WS path and on the polling fallback (WI-TC-3.1/3.2/3.4); a timeout yields an explicit pending state rather than an endless spinner (WI-TC-3.3); unmounting mid-wait does not crash (WI-TC-3.5).
- **Pre-review:** **security** — confirm end-to-end that no private-key material or signature can originate in the browser (a hard PRD constraint).

---

### Slice 22: Verify page — lookup, found/not-found/invalid states, Merkle proof result

- **Epic:** 4. **Depends on:** Slice 21. **Est.:** ~1 week.
- **Use cases:** E4-UC-4 (+A, E1, E2, EC1, EC2), E4-UC-5 (+E1), E4-UC-6 (+A, B, E1, EC1).
- **Test cases:** WI-TC-4.1…4.6, WI-TC-5.1…5.3, WI-TC-6.1…6.5.
- **Files:** `web/src/lib/merkle.ts` `[new]`, `web/src/pages/VerifyPage.tsx` `[new]`, `web/src/__tests__/VerifyPage.test.tsx` `[new]`, `web/src/__tests__/merkle.test.ts` `[new]`
- **Changes:** File-upload and pasted-hash entry points sharing one downstream query/render path. `GET /documents/{hash}`: HTTP 404 maps to an explicit **"not found"**, an unreachable API maps to a **separate** error/retry state, and the two must never be visually or semantically merged. `merkle.ts`: a browser-side re-implementation of the domain-separated proof verification from Slice 3 (leaf `H(0x00||…)`, internal `H(0x01||left||right)`, unpaired promotion) validated against fixtures generated from the Python implementation, so the "valid" badge is cryptographically grounded rather than a trust-the-server flag. Missing/incomplete proof data → "unable to verify proof", never a default "valid".
- **Verify:** `npm --prefix web run test -- VerifyPage merkle`
- **Done when:** an unmodified issued document renders "valid" with correct issuer, timestamp, and block index (WI-TC-4.1/5.1); a never-issued hash renders "not found" and an unreachable API renders a distinct error state (WI-TC-4.5/4.3); **a document whose on-chain record was tampered with renders an explicit "invalid" — never "valid" and never "not found"** (WI-TC-4.6/6.5, the central end-to-end tamper test); missing proof data renders "unable to verify proof" (WI-TC-6.4); the browser-side proof verification agrees with the Python implementation on every shared fixture, including single-leaf and promoted-node cases (WI-TC-6.2).
- **Pre-review:** none.

---

### Slice 23: Chain visualization page, node selector, live refresh (Epic 4 acceptance gate)

- **Epic:** 4. **Depends on:** Slice 22. **Est.:** ~1–1.5 weeks.
- **Use cases:** E4-UC-7 (+A, E1, EC1–EC3), E4-UC-8 (+E1, EC1).
- **Test cases:** WI-TC-7.1…7.7, WI-TC-8.1…8.3.
- **Files:** `web/src/pages/ChainVisualizationPage.tsx` `[new]`, `web/src/components/BlockCard.tsx` `[new]`, `web/src/components/NodeSelector.tsx` `[new]`, `web/src/__tests__/ChainVisualizationPage.test.tsx` `[new]`
- **Changes:** Fetch `GET /chain` (paginated) plus `GET /node/info` from the selected node; render a connected chain diagram with index, timestamp, and document count per block. Validity indicators come **strictly** from `chain_valid`/`first_invalid_index` — the block at `first_invalid_index` is flagged and everything before it is shown valid. Node selector re-fetches and re-renders without a full page reload and updates the badge. Live auto-refresh on `WS /ws/blocks`. Long chains stay responsive via pagination or virtualization. An unreachable node shows an explicit error rather than silently displaying stale data.
- **Verify:** `npm --prefix web run test -- ChainVisualizationPage; npm --prefix web run build`
- **Done when:** ≥5 sequential blocks render correctly and a block corrupted in the backing store is flagged invalid while the rest still render (WI-TC-7.6 — the live tamper demo, and the PRD §4 acceptance criterion); a genesis-only chain renders through the normal path with no empty-state special case (WI-TC-7.5); switching nodes re-renders without a page reload and never merges two nodes' chains when they fork (WI-TC-8.1/8.3); an unreachable node/selection shows a scoped explicit error (WI-TC-7.4/8.2); a 100+ block chain remains responsive (WI-TC-7.7). **Epic 4 is done when this slice is green.**
- **Pre-review:** none.

---

### Slice 24: Attacker component/image scaffold + attack-run results recorder

- **Epic:** 5. **Depends on:** Slice 19 (network) — can be started before or alongside Epic 4. **Est.:** ~1 week.
- **Use cases:** E5-UC-1-A (separate attacker image), E5-UC-6 (+E1, EC1).
- **Test cases:** AT-TC-1.3, AT-TC-6.1, 6.2, 6.3.
- **Files:** `attacks/__init__.py` `[new]`, `attacks/attacker_node/__init__.py` `[new]`, `attacks/attacker_node/overrides.py` `[new]`, `attacks/harness/__init__.py` `[new]`, `attacks/harness/recorder.py` `[new]`, `docker/attacker.Dockerfile` `[new]`, `docker-compose.yml` (extend — an `attacker` service profile), `results/attack_runs.csv` `[new]`, `tests/attacks/test_recorder.py` `[new]`, `tests/attacks/test_attacker_separation.py` `[new]`
- **Changes:** A **separate** attacker image with its own Dockerfile and compose service that **imports** `src/node`'s consensus engine as a library and subclasses/patches the message-handling and mining hooks from the outside. The honest-node image must contain **zero** attacker-mode flags, env conditionals, or hooks. `recorder.py`: append-only rows with `attack_type`, `consensus_mode`, `attacker_hash_power_share` (PoW) **and** `attacker_validator_seat_fraction` (PBFT) as **separate columns** — never one generic "fraction" — plus `failure_class` (byzantine|crash|n/a), `hash_rate_sample` (PoW), `outcome` (detected|blocked|succeeded|inconclusive), `time_to_detection`. A failed write raises a clear error and never silently drops a run.
- **Verify:** `python -m pytest tests/attacks/test_recorder.py tests/attacks/test_attacker_separation.py -v; docker build -f docker/attacker.Dockerfile .`
- **Done when:** a repository scan finds no attacker-mode conditional, flag, or hook anywhere under `src/node/` and the attacker behavior exists only under `attacks/` + `docker/attacker.Dockerfile` (AT-TC-1.3 — the M-13 closure); the attacker image builds and joins the compose network as its own service; a completed run appends exactly one row with the two metric columns kept separate (AT-TC-6.1); re-running the same parameters appends a second row rather than overwriting (AT-TC-6.3); a write failure surfaces an explicit error (AT-TC-6.2).
- **Pre-review:** **architect** — the honest-node/attacker separation boundary is an explicit PRD acceptance criterion (M-13) and is easy to violate accidentally.

---

### Slice 25: Sybil attack against PoW — hash-power-share measurement and sweep

- **Epic:** 5. **Depends on:** Slice 24. **Est.:** ~1–1.5 weeks.
- **Use cases:** E5-UC-1 (+B, E1, E2, EC1, EC2).
- **Test cases:** AT-TC-1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8.
- **Files:** `attacks/scenarios/sybil_pow.py` `[new]`, `attacks/attacker_node/overrides.py` (extend — mining-bias and proposal-flooding behavior), `tests/attacks/test_sybil_pow.py` `[new]`, `docs/results/` `[new dir]`
- **Changes:** Spin up N attacker containers at a configurable per-container mining effort against the honest network's **shared** `expected_difficulty`. Measure the attacker's **hash-power share** from per-container `hash_rate` samples via `GET /metrics/consensus` — never node count. Record fork / stall / attacker-block-finalized outcomes. Include a negative sub-scenario in which the attacker mines at a self-chosen lower declared difficulty. Sweep the share (linear or binary search) to bracket the disruption threshold. Infrastructure failures (attackers cannot join; honest network dies of resource exhaustion) are recorded as **inconclusive**, never as "attack failed".
- **Verify:** `python -m pytest tests/attacks/test_sybil_pow.py -v` then a real run: `python -m attacks.scenarios.sybil_pow --sweep --mode pow`
- **Done when:** an attacker block declaring an artificially low difficulty is rejected with `failure_type = "difficulty"` and never counts as a win (AT-TC-1.2 — the FR-24 cross-check); every recorded PoW row carries a measured hash-power share and a `hash_rate_sample`, and no row records a raw node-count fraction (AT-TC-1.1, PRD §5 acceptance criterion); the 0-share control run records "no disruption" (AT-TC-1.7); a run at/above hash-power majority records disruption (AT-TC-1.8); infra failures are recorded as inconclusive (AT-TC-1.5/1.6); the sweep produces at least one successful and one unsuccessful run for PoW (PRD §5 acceptance criterion).
- **Pre-review:** **security** — this scenario deliberately exercises the Sybil surface; confirm it runs against a disposable network only.

---

### Slice 26: Sybil attack against PBFT — seat fraction, Byzantine vs. crash variants, PeerInfo negative control

- **Epic:** 5. **Depends on:** Slice 25. **Est.:** ~1.5 weeks.
- **Use cases:** E5-UC-2 (+A, B, C, E1, EC1, EC2).
- **Test cases:** AT-TC-2.1…2.8.
- **Files:** `attacks/scenarios/sybil_pbft.py` `[new]`, `attacks/attacker_node/overrides.py` (extend — equivocating and silent variants), `tests/attacks/test_sybil_pbft.py` `[new]`
- **Changes:** Controlled-experiment redeployment placing N attacker containers into N of the n boot-time `ValidatorSet` seats. Two clearly separated variants: **UC-2-B Byzantine equivocation** (conflicting `prepare`/`commit` to different honest peers — a safety test) and **UC-2-C crash/silent** (stop responding — a liveness test). Outcome classification is read from `GET /node/info`'s `quorum_status`, not inferred. Include the boundary point `f = floor((n-1)/3)` and an explicitly labelled over-limit point (e.g., 2 attacker seats on n=4) recorded as an intentional boundary test, not a vulnerability. Include the **negative control**: mass `POST /peers/register` with zero `ValidatorSet` seats.
- **Verify:** `python -m pytest tests/attacks/test_sybil_pbft.py -v` then `python -m attacks.scenarios.sybil_pbft --sweep`
- **Done when:** mass `PeerInfo`-only registration leaves the quorum threshold and every consensus outcome unchanged (AT-TC-2.8 — the central C-4 negative control); at/below the theoretical boundary the Byzantine variant finalizes **no** wrong block (AT-TC-2.4/2.7); the crash variant at/below f keeps finalizing and above f stalls with a **crash/liveness** label never conflated with a Byzantine finding (AT-TC-2.5); every recorded PBFT row carries a `ValidatorSet` seat fraction and a `failure_class` (AT-TC-2.2); the over-limit run is labelled a boundary test point (AT-TC-2.6); the sweep produces at least one successful and one unsuccessful run for PBFT (PRD §5 acceptance criterion).
- **Pre-review:** **security** — directly targets the quorum/equivocation logic from Slices 17–18.

---

### Slice 27: Backdating/tampering — direct chain-store mutation with out-of-band trust anchor

- **Epic:** 5. **Depends on:** Slice 24 (recorder), Slice 9 (validation guarantees). **Est.:** ~1–1.5 weeks.
- **Use cases:** E5-UC-4 (+A, B, E1, E2, EC1, EC2).
- **Test cases:** AT-TC-4.1…4.11.
- **Files:** `attacks/harness/trust_anchor.py` `[new]`, `attacks/harness/resolver.py` `[new]`, `attacks/scenarios/tamper_store.py` `[new]`, `config/trust_anchor.example.json` `[new]`, `tests/attacks/test_tamper_store.py` `[new]`
- **Changes:** `trust_anchor.py` reads a **separately stored, read-only** trusted `IssuerKeyPair`/`NodeKeyPair` public-key file kept **outside** the attacked node's key-store directory. `resolver.py` builds a key resolver from that anchor and injects it into Epic 2's `validate_chain` — this is the exact seam that makes the test resistant to an attacker who swaps both the data and the node's local keys. The harness must never fall back to the attacked node's local key-store. Scenarios: metadata-only mutation; block-preimage mutation; mutation with the block's own `block_hash` recomputed at any position; content re-signed with an attacker key; multiple simultaneous tamper points. Re-validation is triggered by a node restart or by an append/sync event — **there is no periodic validation cycle to wait for**. Every scenario also confirms end-to-end through `GET /documents/{hash}` and `GET /node/info`, with no dependency on the Epic 4 UI.
- **Verify:** `python -m pytest tests/attacks/test_tamper_store.py -v` then `python -m attacks.scenarios.tamper_store --target <disposable-node>`
- **Done when:** validation using the out-of-band resolver reports invalid at the correct index with the expected `failure_type` for every scenario (AT-TC-4.3); a preimage-field tamper with recomputed `block_hash` at **any** position is caught via `proposer_signature` (AT-TC-4.7 — the M-1 closure, and a critical finding if it is not); content re-signed with an attacker key is rejected against the out-of-band issuer key (AT-TC-4.8); a code-level assertion proves the harness never reads the attacked node's local key-store (AT-TC-4.9 — the M-2 regression guard); detection is identical for a near-genesis block and the tip (AT-TC-4.10); with multiple tamper points, the earliest failing index is reported and a follow-up scan reveals the rest (AT-TC-4.11); `GET /node/info` reports `chain_valid = false` with the right `first_invalid_index` after a restart or sync event (AT-TC-4.2/4.4).
- **Pre-review:** **security** — the out-of-band trust-anchor requirement (M-2) is precisely the kind of thing that silently degrades into "read the local key file"; review before implementing.

---

### Slice 28: Backdating/tampering — mid-chain block injection (offline and online paths)

- **Epic:** 5. **Depends on:** Slice 27. **Est.:** ~1 week.
- **Use cases:** E5-UC-5 (+A, B, E1, EC1).
- **Test cases:** AT-TC-5.1…5.7.
- **Files:** `attacks/scenarios/inject_block.py` `[new]`, `tests/attacks/test_inject_block.py` `[new]`
- **Changes:** Construct a forged block carrying a falsified, chronologically earlier timestamp positioned to appear mid-chain. **Offline path:** write it directly into the store file and restart/reload the node. **Online path:** broadcast it / propose it via PBFT against a live honest node. Also attempt the full renumber-and-shift variant to demonstrate the cascading re-sign requirement, and confirm honest peers holding the pre-injection chain reject the rewritten fork through **full from-genesis revalidation** (Slice 16's divergence path).
- **Verify:** `python -m pytest tests/attacks/test_inject_block.py -v` then `python -m attacks.scenarios.inject_block --mode offline` and `--mode online`
- **Done when:** the offline injection is rejected at reload with `failure_type` of `"structural"` or `"link"` (AT-TC-5.2/5.4); the online injection is rejected immediately on `proposer_signature` verification and is **not re-broadcast** (AT-TC-5.3/5.5); a fully hash-consistent injection with a chronologically earlier timestamp is rejected by the monotonicity check with `"structural"` (AT-TC-5.7 — a critical finding if it is not); the renumber-and-shift variant is shown to require re-signing every downstream block, and honest peers reject the rewritten chain via full revalidation (AT-TC-5.6); every run appends a recorder row.
- **Pre-review:** **security** — exercises the chain-sync fork-adoption path from the security-priority list.

---

### Slice 29: Threshold aggregation and comparison charts

- **Epic:** 5. **Depends on:** Slices 25–28 (need recorded runs). **Est.:** ~1 week.
- **Use cases:** E5-UC-3 (+E1, EC1), E5-UC-7 (+A, E1, EC1).
- **Test cases:** AT-TC-3.1, 3.2, 3.3, AT-TC-7.1…7.6.
- **Files:** `attacks/analysis/__init__.py` `[new]`, `attacks/analysis/thresholds.py` `[new]`, `attacks/analysis/charts.py` `[new]`, `results/charts/` `[new dir]`, `tests/attacks/test_thresholds.py` `[new]`, `tests/attacks/test_charts.py` `[new]`
- **Changes:** `thresholds.py`: aggregate recorded runs per consensus mode and compute the minimum disruptive attacker fraction on the **algorithm-appropriate axis** — PoW hash-power share, PBFT `ValidatorSet` seat fraction — computed and reported independently, never merged; emit an explicit "no threshold found within the tested range" marker when applicable. `charts.py`: (a) a PoW-vs-PBFT block-finalization-latency chart across difficulties/network sizes sourced from `GET /metrics/consensus`; (b) a Sybil-resistance chart rendered as **two separate panels** with different x-axes. Export static images sized for the thesis document. Regeneration from stored data must be deterministic; a dataset missing rows for a chart must produce an explicit "cannot generate chart X because Y" message, never a misleading empty plot.
- **Verify:** `python -m pytest tests/attacks/test_thresholds.py tests/attacks/test_charts.py -v; python -m attacks.analysis.charts --out results/charts`
- **Done when:** the Sybil chart is emitted as two panels with distinct x-axis labels ("attacker hash-power share" and "attacker ValidatorSet seat fraction") and **no** shared node-count axis exists anywhere in the output (AT-TC-7.2 — the M-8 closure); ≥2 chart image files exist under `results/charts/` (PRD §5 acceptance criterion); running the script twice on unchanged data produces identical output (AT-TC-7.6/7.4); a dataset with no PBFT rows produces a named, explicit error instead of an empty chart (AT-TC-7.5); each mode's threshold (or its explicit "not found" marker) is reported on its own axis (AT-TC-3.1/3.2).
- **Pre-review:** none.

---

### D2 (Deliverable, not a TDD slice): Epic 5 written findings summary

- **Epic:** 5. **Depends on:** Slice 29. **Est.:** ~1 week of writing.
- **Use cases:** E5-UC-8 (+E1, EC1). **Test cases:** AT-TC-8.1…8.5.
- **Files:** `docs/results/findings.md` `[new]`, `README.md` (extend — link the results and how to reproduce them)
- **Changes:** A thesis-ready results chapter mapping attack type → outcome → consensus mode for every completed scenario; an explicit cross-reference of D1's theoretical expectations against the measured results, including any contradiction discussed rather than smoothed over; an explicit statement that PoW's hash-power-share metric and PBFT's seat-fraction metric are measured on **different axes and are not comparable node-for-node**; crash-fault (liveness) and Byzantine-fault (safety) findings reported as **distinct classes**; an explicit statement of any under-tested mode rather than overstated confidence. Embed the Slice 29 charts.
- **Verify:** `grep -E "hash-power share|ValidatorSet seat fraction|not directly comparable|crash|Byzantine" docs/results/findings.md`
- **Done when:** the file exists, contains the attack-type → outcome → mode mapping for every scenario run, contains the verbatim non-comparability statement, reports crash and Byzantine findings under separate headings, and references both generated charts (AT-TC-8.1…8.5). **Epic 5 — and the project — is done when this exists and every PRD acceptance box in §§1–5 is ticked.**
- **Pre-review:** none.

---

## 4. Acceptance criteria (project-level "done")

- [ ] `docs/research/epic1_blockchain_comparison.md` contains a ≥2-system × 5-dimension comparison table and ≥3 design decisions traced to research findings (PRD §1).
- [ ] Two independently started nodes compute an identical genesis `block_hash` from shared constants alone (PRD §2, C-1).
- [ ] N document hashes in one block produce one Merkle root and N independently verifiable inclusion proofs (PRD §2).
- [ ] Tampering any block field, at any position including the tip, is detected with the correct `failure_type` and the correct first-failing index; tip-block tampering with a recomputed `block_hash` is caught by `proposer_signature` (PRD §2, M-1).
- [ ] Chain state, `IssuerKeyPair`, and `NodeKeyPair` survive a restart and reload to an identical, verifiable state (PRD §2).
- [ ] A PoW block whose declared difficulty ≠ the network's `expected_difficulty` is rejected with `"difficulty"`; a PBFT block below 2f+1 distinct commit signatures is rejected with `"quorum"` — on the proposal path, the sync path, and the `GET /node/info` cache path identically (PRD §2/§3, FR-24/FR-25).
- [ ] A ≥4-node docker compose network starts, logs `ValidatorSet`/`IssuerRegistry` per node, and propagates a document submitted to one node to all others, in **both** PoW and PBFT modes (PRD §3).
- [ ] Under PBFT n=4: stopping 1 node keeps finalizing; stopping 2 reports **crash-fault** quorum loss; an equivocating validator is reported as a **Byzantine** event — the two are never conflated (PRD §3, M-9).
- [ ] Registering arbitrarily many `PeerInfo` peers never changes the PBFT quorum threshold (PRD §3, C-4).
- [ ] A divergent incoming chain triggers full from-genesis revalidation, not incremental (PRD §3, M-14).
- [ ] Every REST error uses the `{"error": {code, message, details}}` envelope; hash fields are validated against `^[0-9a-f]{64}$`; oversized metadata is rejected; `GET /chain` is always bounded (PRD §3, M-11/FR-18).
- [ ] `GET /node/info` returns all nine fields and its latency does not scale with chain length (PRD §3, FR-26).
- [ ] The UI can issue a document (unsigned submission, node-side signing) and show it confirmed with a block index on both networks; can verify an unmodified document as valid; shows an altered document as **invalid** (not "not found"); renders ≥5 blocks and flags a corrupted block; switches nodes without a page reload (PRD §4).
- [ ] The browser never generates, holds, or transmits issuer private-key material or a signature (PRD §4, hard constraint).
- [ ] ≥1 successful and ≥1 unsuccessful Sybil run recorded per consensus mode, on the correct per-algorithm metric axis (PRD §5).
- [ ] The attacker component is a separate build artifact with zero attacker-mode conditionals in the honest-node image (PRD §5, M-13).
- [ ] Tamper detection is verified against a separately stored, out-of-band trusted public key, never the attacked node's key-store (PRD §5, M-2).
- [ ] ≥2 comparison charts exist, with PoW and PBFT Sybil thresholds on **separate panels** (PRD §5, M-8).
- [ ] `docs/results/findings.md` exists with the non-comparability statement and distinct crash/Byzantine reporting (PRD §5).

---

## 5. Dependency order and optional interleaving

| # | Slice | Hard dependencies |
|---|---|---|
| D1 | Epic 1 research | — |
| 1 | Scaffold + canonical serialization | — (informed by D1) |
| 2 | Keys, signatures, DocumentRecord | 1 |
| 3 | Merkle tree + proofs | 1, 2 |
| 4 | Block structure + batch build | 3 |
| 5 | Genesis + chain append | 4 |
| 6 | Chain validation — core checklist | 5 |
| 7 | Chain validation — PoW/PBFT checks | 6 |
| 8 | Persistence | 7 |
| 9 | Tamper-detection suite (**Epic 2 gate**) | 8 |
| 10 | Node skeleton, config, registries, envelope | 9 |
| 11 | Key resolver, validity cache, `/node/info` | 10 |
| 12 | Peers REST + paginated `/chain` | 11 |
| 13 | `/documents` submit + lookup | 12 |
| 14 | PoW engine + metrics | 13 |
| 15 | WebSocket layer + inbound authentication | 14 |
| 16 | Chain sync + fork resolution | 15 |
| 17 | PBFT three-phase protocol | 16 |
| 18 | PBFT view-change + fault classification | 17 |
| 19 | docker compose network (**Epic 3 gate**) | 18 |
| 20 | React scaffold + badge | 19 |
| 21 | Issue page | 20 |
| 22 | Verify page | 21 |
| 23 | Chain visualization (**Epic 4 gate**) | 22 |
| 24 | Attacker image + results recorder | 19 |
| 25 | Sybil vs. PoW | 24 |
| 26 | Sybil vs. PBFT | 25 |
| 27 | Tampering — store mutation | 24 (+9) |
| 28 | Tampering — block injection | 27 |
| 29 | Thresholds + charts | 25, 26, 27, 28 |
| D2 | Findings summary | 29 |

**Optional interleaving (solo, for variety or to unblock writing):**

- D1 can be written at any time before the thesis text is finalized; only its *design justifications* need to precede Slices 1–7 conceptually.
- Slices 24–28 (Epic 5) depend on Slice 19, **not** on Epic 4. If you want attack results early for the thesis, run Epic 5 before Epic 4.
- Slice 27 (store tampering) only needs Slices 9 + 24; it can be done immediately after the network exists, well before the Sybil work.
- Slice 20 (React scaffold) can be started as soon as Slice 11 exists if you want the badge and node selector working against a single node before the full network.

---

## 6. Files created or changed

**Existing files extended:** `README.md`, `.gitignore`, `docker-compose.yml` (created in Slice 19, extended in Slice 24), `docs/research/epic1_blockchain_comparison.md` (created in D1, extended in Slice 9).

**All other paths listed in section 2 are new**, created by the slice that first names them. There is currently no source code in this repository, so no existing implementation path is referenced anywhere in this plan.

---

## 7. Risk assessment

| Risk | Impact | Where it bites | Mitigation in this plan |
|---|---|---|---|
| **Canonical serialization drift** | Two nodes compute different hashes for the same data; the whole network silently fails to converge. | Slices 1, 4, 6; every Epic 3 node. | One encoder module, frozen test vectors, and BC-TC-CS.3 asserting no duplicate encoding logic exists. Never edit the vectors after Slice 1. |
| **Cryptographic key handling** | Private keys leaked into logs, into the browser, or regenerated silently, destroying issuer identity continuity. | Slices 2, 8, 13, 21. | Separate stores per key type; fail-fast on missing key files; server-side-only issuer signing; a hard "no key material in the browser" check in Slice 21. **Security pre-review on all four.** |
| **PBFT quorum/equivocation logic error** | Safety violation — a wrong block finalizes; and the thesis's central PoW-vs-PBFT comparison becomes invalid. | Slices 17, 18; measured in 26. | Quorum counted only over the static `ValidatorSet`; one vote per `node_id` per `(view, seq)`; distinct-signer requirement enforced twice (engine + validation). **Security pre-review on both.** |
| **Sybil surface via peer registration** | An attacker inflates influence by registering peers. | Slice 12; measured in 26. | Structural separation of `PeerInfo` from `ValidatorSet`, asserted by CN-TC-1.11 and AT-TC-2.8 as a negative control. |
| **Fork-adoption bug** | A node adopts a tampered chain, silently defeating every guarantee proven in Slice 9. | Slice 16. | Full from-genesis revalidation on divergence (asserted with a call counter); PoW-only tie-break; PBFT same-height fork treated as a Byzantine event. **Security pre-review.** |
| **Trust-anchor shortcut in Epic 5** | Tamper tests read the attacked node's own key-store and produce false "valid"/"detected" results, invalidating the thesis evidence. | Slice 27. | Out-of-band anchor file + injected resolver, with AT-TC-4.9 as an explicit regression guard. **Security pre-review.** |
| **Attacker logic leaking into the honest node** | Violates PRD §5 acceptance (M-13) and contaminates every measurement. | Slice 24. | Separate image/Dockerfile/compose service; repo scan test (AT-TC-1.3). **Architect pre-review.** |
| **Difficulty change against an old chain** | Looks like a bug; actually by-design. | Slices 7, 8, 14, 25. | Documented in BC-TC-8.10; changing difficulty requires a fresh chain on every node. |
| **Scope creep from IPFS** | Time lost on an explicitly optional item. | Any. | IPFS is out of scope by PRD decision; `ipfs_cid` stays an optional, defaulted-absent field (BC-TC-1.3) and must never block an acceptance criterion. |
| **Data sensitivity** | Low. `DocumentRecord.metadata` should carry non-PII identifiers where possible and is size-capped server-side. No user authentication exists — a deliberate, documented prototype scope reduction (PRD §4 NFR). |
| **Persistence/schema changes** | Chain store format changes after data exists force a chain reset. | Slice 8. | Freeze the store contract in Slice 8 behind an interface; the demo network is disposable, so a reset is always acceptable. |
| **External calls** | None. No third-party services, no message broker (RabbitMQ explicitly rejected), no network access from `blockchain_core`. |

---

## 8. Dependencies

**Python (backend, Slices 1–19, 24–29):** `cryptography`, `fastapi`, `uvicorn[standard]`, `pydantic` v2, `websockets`, `httpx` (client + test client), `pytest`, `pytest-asyncio`, `ruff`, `mypy`; `matplotlib`, `plotly`, `pandas` (Slice 29 only).

**Frontend (Slices 20–23):** `react`, `react-dom`, `react-router-dom`, `typescript`, `vite`, `vitest`, `@testing-library/react`, `@testing-library/user-event`. Hashing uses the browser-native **Web Crypto API** — no third-party hashing library.

**Infrastructure:** Docker Engine + `docker compose` v2 (≥4 node containers plus the attacker service).

**Explicitly NOT dependencies:** RabbitMQ or any message broker (rejected by architecture review — a broker would invalidate the Sybil demonstration); IPFS (optional/deferred, must never block an acceptance criterion); Hyperledger/Ethereum or any existing blockchain framework (building from scratch is the thesis's premise).

---

## 9. Wave assignment

**Not performed — intentionally.** Wave assignment exists to let parallel agents own disjoint file sets within a wave. This plan is executed by one person sequentially, so slices carry no `Wave:` field; execution falls back to the dependency order in section 5. If this plan is ever handed to a parallel executor, waves must be assigned first, and note that Slices 6/7 (both edit `src/blockchain_core/validation.py`), 17/18 (both edit `src/node/consensus/pbft/engine.py`), and 24/25/26 (all edit `attacks/attacker_node/overrides.py`) share files and could never occupy the same wave.
