# Enterprise SQL Dataset Quality Research — Verified SQL Data Factory

Research date: 2026-09-26. Status labels used throughout: **FACT**
(verified in repo artifacts/code), **MEASURED** (counted from run
artifacts), **PROVISIONAL** (targeted-qualification-004, re-verification
still running), **HYPOTHESIS**, **UNKNOWN**.

Provisional-evidence rule: every number from
`runs/targeted-qualification-004/` is labeled PROVISIONAL until the
final CTE re-verification and quality refresh complete.

---

## 1. Executive summary (for a nontechnical founder)

**What we have:** a working factory that generates SQL tasks, gets a
local open-weight model to answer them, runs each answer in an
isolated sandbox, checks it with an independent answer key plus hidden
tests and mutation testing, and keeps only records that survive every
gate. Production-001 produced **232 Golden records** (MEASURED,
`runs/production-001/quality/export/golden.jsonl`); targeted
qualification runs repaired the three failing task families and added
up to ~217 more (80 + 69 + 68 PROVISIONAL).

**Why it matters:** the industry's standard SQL benchmarks are
measurably broken. A 2026 peer-reviewed audit found **52.8% annotation
errors in BIRD Mini-Dev and 66.1% in Spider 2.0-Snow** — wrong answers
in the answer key, shifting model rankings by up to 3 places (Jin et
al., CIDR 2026). A dataset where *every* answer carries executable
proof is exactly the gap in the market. Nobody sells that today.

**What blocks money:** (1) the newest repair results are provisional;
(2) no human has audited a single record yet (60 sampled, all
PENDING); (3) the model that generated the data is a third-party
safety-stripped ("abliterated") fine-tune with unclear license
lineage — a lawyer must clear it before any sale; (4) nobody has shown
the data improves a model (business hypothesis: INSUFFICIENT_EVIDENCE).

**Recommendation: READY FOR ANOTHER CONTROLLED QUALIFICATION** — not
for production, pilots, or sale. Finish the v5 re-verification, run
the pending human audit, clear the model license, then gate a limited
production batch. Details in §13–§15.

---

## 2. Technical summary (for a senior data/ML engineer)

**Pipeline (all verified in code, not just docs):** versioned YAML task
templates → deterministic seeded fixtures → Devstral-class local model
(3 candidates/task, raw responses preserved) → Docker sandbox
(`--network none`, read-only root, non-root, caps, kill+rm) →
independent pure-Python oracles (no SQL, no shared bug class) →
comparator (tolerance-aware, NULL==NULL) → hidden fixtures (3, seeded,
never stored) → property + metamorphic checks → mutation campaign
(threshold 0.90, never lowered) → PASS/FAIL/INCONCLUSIVE → dedup
(exact/structural/semantic) → contamination flags → risk-based audit
sampling → Golden → content-addressed provenance graph → snapshot →
Phase 7 release (manifest + SHA256SUMS + card).

**Measured state:**

| Run | Tasks | Cands | PASS | FAIL | INCONC | Golden | Yield |
|---|---:|---:|---:|---:|---:|---:|---:|
| Pilot-001 | 100 | 300 | 101 | 199 | — | 49 | 16.3% |
| Pilot-002 | 160 | 480 | 216 | 251 | 13 | 54 | 11.3% |
| Production-001 | 500 | 1,500 | 820 | 503 | 177 | 232 | 15.5% |
| TQ-002 (v3) | 82 | 246 | 189 | 48 | 9 | 80 | 32.5% |
| TQ-003 (v4) | 82 | 246 | 203 | 34 | 9 | 69 | 28.0% |
| TQ-004 (v5 PROVISIONAL) | 82 | 246 | 232 | 8 | 6 | 68 | 27.6% |

Production-001 Golden covers 7/10 families (zero CTE/temporal/window);
TQ runs repair exactly those three (TQ-004 PROVISIONAL: CTE 28,
temporal 30, window 10).

**Strongest findings from artifact inspection (MEASURED):**

1. Only **7 unique instructions across 232 production Golden records**
   and **78 unique SQL strings** — the dataset is template-heavy.
   Semantic duplicate rate in health: **0.862**. Dedup gates work (that's
   why Golden ≪ PASS), but instruction diversity is a real ceiling on
   training value.
2. Golden records are **13–26 KB each** (full verification evidence
   inline). Correct for auditability; wrong shape for a training
   product — public/training/private field separation (Part 6) is
   required before sale.
3. TQ-004 CTE instructions are hyper-prescriptive (they dictate CTE
   shape, function argument order, and join strategy). This likely
   inflates PASS rates and weakens the "genuinely difficult" claim —
   flagged for the difficulty-authenticity review (§12, roadmap P1).
4. `dataset_health.json` reports `contaminated_rate: 1.0` with
   `flagged_count: 0` — a reporting quirk (rate computed over an empty
   or degenerate denominator), not contamination, but it must be fixed
   before any customer sees it.
5. Strengths confirmed in code: mutation threshold enforced in two
   layers (Phase 4 gates PASS, Phase 5 re-checks from stored evidence);
   weak suites yield INCONCLUSIVE, never PASS; secrets structurally
   scrubbed from provenance; snapshot/release ids content-defined.

---

## 3. Market and buyer analysis

### 3.1 Buyer types, needs, risks, evidence, and rejection triggers

| Buyer | Needs | Key risks | Evidence requested | Rejects on |
|---|---|---|---|---|
| Foundation-model companies (post-training) | Large, diverse, verifiable SFT/RL data; preference pairs | Contamination of eval sets; license encumbrance; PII | Scale (100k+), license chain, dedup/contamination reports, Croissant/datasheet | Unknown license; eval overlap; no versioning |
| AI coding assistants | Eval benchmarks + failure taxonomies | Benchmark leakage; stale answers | Frozen versioned benchmarks, re-verification across releases, audit agreement | Annotation errors (cf. BIRD 52.8%); single-engine quirks |
| Text-to-SQL vendors | Domain-specific NL↔SQL pairs, robustness sets | Schema overfitting; dialect mismatch | Multi-schema coverage, paraphrase robustness (cf. SPENCE probe), dialect matrix | Template-only NL; one-dialect data |
| Enterprise data-agent teams | Private eval on own schema; custom datasets | Data leaving premises; wrong answers in production | On-prem/private-benchmark service, SOC2-type posture, provenance per record | Public-only product; no custom path |
| Model-evaluation companies | Independent, uncontaminated benchmarks | Memorization; ambiguous items | Freshness proof, ambiguity review (≥3 annotators, cf. Spider 2.0), inter-rater stats | Public items; no ambiguity handling |
| RL/post-training teams | Verifiable reward signals, difficulty gradients | Reward hacking on weak checks | Mutation-tested verifiers, empirical difficulty, failure datasets | Weak-suite PASS; declared-only difficulty |
| Data marketplaces (AWS/Snowflake/HF) | Legal eligibility, docs, support, updates | Ineligible/illegal data; no support org | License clarity, update policy, support process (AWS requires all three) | PII/HIPAA data; no update mechanism |
| System integrators | Packaged, supported, licensed bundles | Integration cost; liability | Datasheet, SLA/support terms, indemnity posture | Missing docs; unclear liability |

Data-format expectations: JSONL/Parquet with schema (universal);
Croissant JSON-LD for HF discoverability; SLSA/in-toto-style signed
provenance for supply-chain buyers; Snowflake-native sharing or S3
delivery for marketplace buyers. License expectations: Apache-2.0 /
CC-BY-4.0 / CDLA for open data; custom commercial terms with
field-of-use and redistribution clauses for paid tiers.

Training vs evaluation vs preference vs failure vs interactive needs
differ by buyer (table above); no single artifact serves all — Part 10
designs the product split.

### 3.2 Established standard vs practice vs recommendation

- **Standard (established):** Croissant/NeurIPS dataset-track
  requirements; W3C PROV concepts; SLSA provenance for artifacts;
  Landis & Koch kappa bands for audit agreement; AWS/Snowflake
  provider legal eligibility.
- **Common practice:** execution accuracy as primary metric (BIRD,
  Spider 2.0); hidden test splits; datasheets/data cards on HF
  (frequently left as "More Information Needed" — the WikiSQL card
  itself shows this failure mode).
- **Research recommendation:** multi-round execution verification
  (Spider 2.0-AIFunc), paraphrase-robustness probes (SPENCE),
  infeasible-question sets (TrustSQL), ambiguity review by ≥3
  annotators (Spider 2.0).
- **Our reasoned recommendation:** adopt all four research
  recommendations above plus mutation-tested verifiers (unique to us).
- **Cannot confirm publicly:** actual enterprise willingness-to-pay
  figures; marketplace revenue shares for SQL data specifically.

---

## 4. Existing benchmark comparison

| Dataset | Size | Dialect | DBs / variety | Verification | Exec-checked | Known problems | License/commercial |
|---|---|---|---|---|---|---|---|
| Spider 1.0 (Yu et al., EMNLP 2018) | 10,181 Q / 5,693 SQL | SQLite | 200 DBs, 138 domains | human review (~1,000 hrs) | No (exact-match) | Paraphrase memorization; oldest → most contaminated (SPENCE probe: 10–15pp paraphrase drops) | Research use; test set hidden |
| BIRD (NeurIPS 2023 D&B) | 12,751 pairs | SQLite (+PG/MySQL planned) | 95 DBs, 33.4GB, 37 domains | human + EX + VES efficiency metric | Yes (EX) | 52.8% Mini-Dev annotation errors (CIDR 2026); noise in Q+gold SQL (Wretblad, ACL 2024) | Research; DBs not redistributable |
| WikiSQL (Zhong et al. 2017) | 80,654 pairs | SQLite (2 types only) | 24,241 single tables | crowdsourced | Partial | Single-table only; 140 tables missing column names (LLMSQL 2025); HF card license "unknown" | Unclear (card: unknown) |
| SParC (Yu et al. 2019) | 4,298 sequences / 12.7k Q | SQLite | 200 DBs | expert-constructed | Partial | Same expert writes Q+SQL (bias); context-only | Research |
| CoSQL (Yu et al. 2019) | 3,007 dialogues / 10k SQL | SQLite | 200 DBs | Wizard-of-Oz + experts | Partial | Dialogue-act noise; ambiguous/clarify turns unevaluated as SQL | Research |
| KaggleDBQA (Lee et al., ACL 2021) | 272 examples | SQLite | 8 real Kaggle DBs | few-shot realistic | Yes | Tiny; 8 DBs only | Research |
| Spider 2.0 (ICLR 2025) | 632 workflows | BigQuery/Snowflake/SQLite/DuckDB/PG | 1,000+ cols, industrial | 3-annotator review + SQL rewrite anti-leakage | Yes (agentic EX) | o1-preview solves 21.3% (headroom, not error); annotation expensive, not scalable | Research |
| Spider 2.0-lite/snow | 547 each | Snowflake/SQLite/BigQuery | 152–158 DBs, ~800 cols | same pipeline | Yes | Snow subset 66.1% errors per CIDR 2026 audit scope note | Research |
| Dr.Spider (ICLR 2023) | 15k pre/post perturbation pairs | SQLite | Spider-dev derived | perturbation protocol | Yes | Derived-only; no new DBs | Research |
| TrustSQL (2024) | ATIS/Advising/EHRSQL/Spider splits | mixed | domain-specific | penalty scoring + infeasible Qs | Yes | Small; domain narrow | Research |
| **Ours (prod-001 + TQ)** | 232 + ~217 Golden | DuckDB only | synthetic, 3–8 tables | oracle+hidden+property+meta+mutation | **Yes, per-record proof** | Template-heavy NL (7 unique instructions/232); single dialect; no human audit yet | TBD (license chain incomplete) |

**What we do better:** per-record executable proof with mutation-tested
suites; content-addressed provenance; deterministic regeneration;
contamination machinery; no LLM-judge anywhere. No listed benchmark
does all five.

**What we do worse:** scale (hundreds vs tens of thousands);
real-database grounding (all synthetic); dialect coverage (one vs
five); NL diversity (7 unique instructions vs thousands of humans);
no completed human audit (Spider: 1,000 hrs; Spider 2.0: 3 reviewers).

---

## 5. Gold-standard quality checks (A/B/C hierarchy)

### Level A — minimum usable (all must PASS or the release is blocked)

Parseable records · valid schema · SQL executes · required columns
present · checksums match manifest · license field present and
non-"unknown" · versioned release id · train/eval split recorded.
**Current:** all implemented except license field (GAP — Part 6 adds
it) — release validator covers the rest (FACT, `release-format.md`).

### Level B — verified professional (our current tier, mostly done)

Independent oracle (HAVE) · hidden tests (HAVE, 3 seeded) ·
property tests (HAVE, family-justified) · metamorphic tests (HAVE) ·
mutation score ≥ threshold (HAVE, 0.90, dual-enforced) ·
deterministic reproduction (HAVE, byte-identical exports) · model +
prompt provenance (HAVE) · duplicate detection 3-level (HAVE) ·
contamination analysis (HAVE, reporting quirk to fix) · human-audit
sampling (MECHANISM HAVE, zero audits completed — GAP).

### Level C — premium enterprise (gap analysis)

| Check | Failure detected | Buyer motive | Difficulty | Have it? | Proof needed | Golden-block? | Status on fail |
|---|---|---|---|---|---|---|---|
| Cross-engine equivalence (DuckDB+SQLite+PG) | dialect-specific accidents | portability claims | Medium (dockerized runners exist) | NO | per-record 2-engine match log | YES (premium tier) | FAIL |
| Second independent oracle | oracle bug class | correctness trust | High (2× oracle cost) | NO | oracle-agreement rate | Sample-gate | AUDIT_REQUIRED |
| Differential fuzz across engines | engine divergence | robustness | Medium (SQLLogicTest harness exists as pattern) | NO | divergence log, zero unexplained | WARN | WARNING |
| Query-plan stability | pathological plans | perf-sensitive buyers | Medium | NO | EXPLAIN-cost bounds | NO | WARNING |
| Adversarial schemas (name collisions, type traps) | lexical-overfit models | robustness buyers | Medium | PARTIAL (edge fixtures) | trap pass rate | NO | WARNING |
| Ambiguous-language detection + rejection | unanswerable Qs (cf. TrustSQL/CoSQL) | eval validity | Medium | NO | ambiguity classifier + reviewer agreement | YES | INCONCLUSIVE |
| Semantic-equivalence (non-fingerprint) | paraphrase leakage | contamination | Medium (embeddings) | NO (fingerprint only) | paraphrase-probe delta (cf. SPENCE) | Sample-gate | AUDIT_REQUIRED |
| Counterfactual fixtures | fixture overfitting | generalization | Medium (mutation-only fixtures are the seed) | PARTIAL | counterfactual kill rate | NO | WARNING |
| NULL/3VL, tz/DST, precision, collation, unicode, skew, empty-table suites | edge-case blindness | enterprise correctness | Low–Medium (extend fixtures) | PARTIAL (12/14 edges; missing empty_result, negative_values) | edge coverage ≥ target | Tier-dependent | FAIL/WARNING |
| Memorization detection (paraphrase probe) | contaminated models scoring well | benchmark buyers | Low (protocol exists) | NO | probe delta report | Benchmark-gate | WARNING |
| Auditor agreement (κ) | unreliable human labels | everyone | Low | NO | κ ≥ 0.67 (see §7) | Blocks *audit claims*, not Golden | AUDIT_REQUIRED |
| Re-verification across versions | bit-rot | long-lived benchmarks | Low (deterministic replay exists) | PARTIAL (no scheduled policy) | re-verify log per release | NO | WARNING |
| Signed manifests (Sigstore/cosign) | tampering | supply-chain buyers | Low | NO (SHA256SUMS unsigned) | signature + transparency log | Release-gate | BLOCK |
| Dataset versioning + deprecation policy | stale citations | all | Low | PARTIAL (ids exist, no policy doc) | policy doc + tombstones | NO | WARNING |
| Croissant + datasheet artifacts | undiscoverability | HF/marketplace | Low | PARTIAL (card exists, no Croissant JSON-LD) | valid Croissant file | Release-gate (public) | BLOCK |

---

## 6. Golden Record definition (proposed strict spec)

Every field classified: **PUB-T** public training · **PUB-M** public
metadata · **PRIV-V** private verification evidence · **PRIV-B**
private benchmark · **INT** internal-only.

| Field | Class | Notes |
|---|---|---|
| task_id, template_id + version, seed | PUB-M | identity; seed enables regeneration |
| instruction (NL) | PUB-T | after ambiguity review |
| schema DDL | PUB-T | |
| fixture identity (hash, NOT rows) | PUB-M | rows stay private to prevent overfit |
| SQL dialect + version | PUB-M | `duckdb==1.5.5` pinned |
| candidate_sql | PUB-T | |
| model id + exact revision (digest) | PUB-M | digest, not tag |
| prompt version + generation settings | PUB-M | temperature/top-p/tokens/seed |
| parser result | PUB-M | |
| sandbox result summary (status, duration) | PUB-M | full stdout INT |
| independent expected result | PRIV-V | never in training product |
| comparison detail (≤3 diffs) | PRIV-V | |
| hidden-test results (seeds, NOT fixtures) | PRIV-V | fixtures never stored (already policy) |
| property/metamorphic/mutation results | PRIV-V summary / PUB-M score | scores public, details private |
| performance bounds | PUB-M | |
| duplicate groups | PUB-M | ids only |
| contamination flags | PUB-M | |
| audit status + auditor ids + κ batch | PUB-M | auditor identities INT |
| provenance refs (snapshot/release ids) | PUB-M | |
| license metadata (record + model + source) | PUB-M | **currently missing — ADD** |
| dataset split | PUB-M | |
| release identity + checksums | PUB-M | signature when added |

Current Golden JSONL (~13–26 KB/record) mixes PUB and PRIV-V freely —
this is the concrete reason Part 10 requires separate products before
any sale. No private benchmark answers were found in the release
surface (checked); benchmark `expected_sql` lives only in benchmark
items files (FACT, sampled).

---

## 7. Acceptance thresholds

"No public standard found" marks house recommendations. Sources where
they exist: Landis & Koch 1977 (κ bands) via NCBI Bookshelf;
Artstein & Poesio 2008 (κ > 0.8 sufficient); Di Eugenio & Glass
(κ ≥ 0.67 cutoff); Spider 2.0 (3-annotator review); BIRD (EX primary).

| Metric | Minimum | Strong | Premium | Source/justification |
|---|---|---|---|---|
| Execution-success rate | ≥ 0.80 | ≥ 0.90 | ≥ 0.95 | House; below 0.80 the generator is broken |
| Verification PASS rate | ≥ 0.25 | ≥ 0.40 | ≥ 0.55 | House; prod-001 MEASURED 0.55 blended, 0.34 pilot-001 |
| INCONCLUSIVE rate | ≤ 0.15 | ≤ 0.08 | ≤ 0.05 | House; prod-001 0.118 — near minimum |
| Mutation score | ≥ 0.90 (have) | ≥ 0.95 | 1.00 on sampled audit | House; observed 1.00 — keep 0.90 gate |
| Golden yield | report only | report only | report only | No standard; yield is diagnostic, never a target (anti-Goodhart) |
| Exact dup rate | ≤ 0.30 | ≤ 0.15 | ≤ 0.10 | House; prod-001 0.28 — at minimum |
| Semantic dup rate | ≤ 0.90 | ≤ 0.70 | ≤ 0.50 | House; prod-001 0.862 — near minimum; TQ better |
| Family coverage | 8/10 | 10/10 | 10/10 + adversarial | House; prod-001 7/10 — BELOW minimum alone |
| Construct coverage | ≥ 0.85 | ≥ 0.95 | 1.00 | House; prod-001 0.9375 |
| Edge coverage | ≥ 0.80 | ≥ 0.90 | 1.00 + tz/DST/unicode | House; prod-001 12/14 = 0.857 |
| Unique instructions/record | ≥ 0.25 | ≥ 0.60 | ≥ 0.90 | House (new); prod-001 7/232 = 0.03 — FAILS minimum |
| Human-audit failure rate | ≤ 0.10 | ≤ 0.05 | ≤ 0.02 + κ ≥ 0.67 | κ cutoffs sourced above; zero audits done |
| Contamination (hard flags) | 0 | 0 | 0 + paraphrase probe | House; flags currently 0 |
| Reproducibility (byte-identical) | 1.00 | 1.00 | 1.00 + cross-version | Have 1.00 (tested) |
| Provenance completeness | 1.00 Golden chains | 1.00 | 1.00 + signatures | Have chains; signatures missing |
| Security-test pass | 1.00 | 1.00 | 1.00 + red-team | Sandbox probe-asserted (docs) |

---

## 8. Hard-to-achieve differentiators (ranked by defensibility)

1. **Independent executable proof per answer** — HAVE. Competitors
   ship human labels (Spider: exact-match, no execution) or noisy EX
   (BIRD 52.8% key errors). Cost: already paid (oracle per template).
   Evidence to claim: this report + artifact paths. Commercial value:
   highest — the core thesis.
2. **Mutation-tested verification strength** — HAVE (0.90 dual-gated,
   observed 1.00). Nobody in the comparison table does this. Cost:
   ~14 cand/min verification compute. Keep.
3. **Content-addressed provenance per record** — HAVE (SLSA-shaped,
   unsigned). Cost: paid. Add signatures for premium tier (cheap).
4. **Contamination-resistant private benchmarks** — PARTIAL (machinery
   + frozen fingerprints; no production benchmark yet). Value: this is
   what eval companies buy. Work: build 500+ item benchmark post-v5.
5. **Counterexample-generating fixtures** — PARTIAL (mutation-only
   fixtures are the seed; generalize to counterfactual suites).
6. **Cross-engine validation** — ABSENT. Highest-cost differentiator
   (2nd engine + 2nd oracle sampling); unlocks portability claims
   Spider 2.0 owns today.
7. **Human-audit agreement at κ ≥ 0.8** — ABSENT (mechanism exists,
   zero audits). Cheap (~60 records × 2 auditors); required before any
   paid pilot.
8. **Rare-pattern coverage (adversarial/ambiguous rejection)** —
   ABSENT. TrustSQL-style infeasible sets + ambiguity gate.
9. **Demonstrated downstream lift** — ABSENT (hypothesis
   INSUFFICIENT_EVIDENCE). Requires the Phase 8 experiment with a real
   fine-tune; the single highest-value evidence in the company.
10. **Ambiguity-free NL at scale** — AT RISK (7 unique instructions;
    hyper-prescriptive TQ-004 prompts). Instruction-diversity program
    + paraphrase-robustness probe before scaling.

---

## 9. Legal, licensing, privacy, security (research, NOT legal advice)

- **Model-output licensing (URGENT):** production runs use
  `alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated` — a
  third-party fine-tune with safety mechanisms removed. Official
  Devstral Small is Apache 2.0 (Mistral docs), which permits use
  without constraints — but that license covers Mistral's weights, not
  automatically an abliterated derivative's lineage, and ablation
  raises safety/acceptable-use questions. **Requires qualified counsel
  before any distribution; record the full license chain per
  `docs/licensing.md` (currently incomplete).**
- **Synthetic-data privacy:** fully synthetic records with no personal
  data fall outside GDPR as anonymous information (Recital 26), but
  residual re-identification risk is debated (Beduschi 2024; Stadler
  et al. 2022) and the EDPB assesses AI-model anonymity case-by-case
  (Opinion 28/2024). Our fixtures are generated (no real persons) —
  strong position, but document the generation process and run the
  EDPS-style privacy-assurance assessment before enterprise sale.
- **Marketplace eligibility:** AWS requires legal eligibility, support
  org, update mechanism, seller qualification (AWS Data Exchange
  provider docs); Snowflake requires Provider/Consumer terms +
  acceptable-use compliance. None are satisfiable today (no support
  org, no update policy, no terms).
- **Security posture:** sandbox threat model T1–T12 documented with
  probe-asserted controls; secrets structurally scrubbed (verified in
  code); no private answers in release surface (verified by sampling).
  Missing for premium: signed manifests, red-team review, kernel/Docker
  zero-day acknowledgment already documented (good).
- **Questions for counsel:** abliterated-model output ownership;
  Apache-2.0 attribution/notices in distributions; benchmark-item
  copyright (instructions as derivative works); enterprise indemnity
  posture; export-control classification of dataset tooling.

---

## 10. Business and product design (no invented pricing)

| Product | Buyer | Fields | Visibility | Quality bar | Min size | Format | Versioning | License | Evidence | Risk | Build order |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Training set | post-training teams | PUB-T+M (§6) | public/internal | §7 Strong | 10k+ | JSONL+Parquet+Croissant | dated versions, tombstones | Apache-2.0/CC-BY | proof summaries | scale gap (have ~450) | 3rd |
| Public eval sample | community/eval cos | PUB-T (no answers) + metrics | public | Strong | 500 | JSONL + harness | frozen | CC-BY | benchmark report | contamination | 2nd |
| Private benchmark | eval cos/enterprise | items + harness, answers sealed | private | Premium | 500+ | sealed service/dump | fingerprinted, re-verified | commercial terms | freshness proof | leakage | 1st (build now) |
| Preference pairs | RL teams | chosen/rejected + verifier scores | internal | Strong | 5k+ | JSONL | dated | Apache-2.0 | score distributions | weak negatives | 4th |
| Failure dataset | robustness buyers | failing SQL + codes + oracle diff | public/internal | Strong | 1k+ | JSONL | dated | Apache-2.0 | taxonomy (have: 199 FAIL analyzed) | embarrassment risk (manage by framing) | 2nd |
| Adversarial set | eval cos | traps + expected behavior | private | Premium | 500+ | sealed | fingerprinted | commercial | trap pass rates | — | 5th |
| Verification API | vendors/enterprise | verdict + evidence | service | Premium | n/a | API + SLA | versioned | commercial | uptime, agreement | serving cost | 6th |
| Custom enterprise | enterprise | customer schema tasks | private | Premium | per-deal | mixed | per-deal | custom | pilot report | scoping | on demand |

Pricing: UNKNOWN/ASSUMED only. No sourced SQL-data price points were
found in public marketplace listings surveyed; mark all pricing
unknown until pilots.

---

## 11. Pipeline audit matrix (code/artifact-grounded)

| Requirement | Implementation | Evidence path | Strength | Missing | Risk | Priority | Effort | Blocks release? |
|---|---|---|---|---|---|---|---|---|
| Deterministic tasks | seeded fixtures, same id twice | `task_engine/`, tests | Strong | — | — | — | — | — |
| Contract versioning | template+oracle versions, unknown raises | `task_semantics.md`, registry | Strong | — | — | — | — | — |
| DuckDB semantics | pinned 1.5.5, probed | sandbox docs | Strong | cross-engine | portability claims | P2 | M | No (note it) |
| Docker isolation | T1–T12, probes | `sandbox/`, docker tests | Strong | red-team, sigs | escape zero-day (documented) | P2 | S–M | No |
| Independent oracle | pure-Python, static-tested independence | `verification/oracles/` | Strong | 2nd oracle | oracle bug class | P1 | L | Sample-gate |
| Hidden fixtures | 3 seeded, never stored | `verification/hidden.py` | Strong | — | — | — | — | — |
| Property/metamorphic | family registries, unknown raises | `verification/` | Strong | wider families | thin coverage | P2 | M | No |
| Mutation 0.90 | dual-enforced, never lowered | `verification/mutations.py`, golden gates | Strong | — | — | — | — | — |
| PASS/FAIL/INCONCLUSIVE | weak→INCONCLUSIVE by construction | phase-4 doc §10 | Strong | — | — | — | — | — |
| Dedup 3-level | hash-indexed, reps kept | `quality/duplicate_detection.py` | Strong | embedding-level | paraphrase leak | P1 | M | No (gate sample) |
| Contamination | role/template/registry flags | `quality/contamination.py` | Medium | reporting quirk fix; internet-scale | false confidence | P1 | S | Fix quirk: YES |
| Audit sampling | deterministic risk-based | `quality/audit.py` | Mechanism only | completed audits + κ | unverified labels | P0 | S | YES (paid pilot) |
| Golden selection | hard gates + quotas, deterministic | `quality/golden.py` | Strong | — | — | — | — | — |
| Provenance graph | content ids, scrubbed secrets | `provenance/` | Strong | signatures | tampering | P1 | S | Public: YES |
| Snapshots/releases | content ids, SHA256SUMS | `products/` | Strong | license field, Croissant | sale-blockers | P1 | S | YES |
| Benchmark isolation | frozen fingerprints, profiles | `products/`, `business/` | Mechanism only | production benchmark | leakage | P0 | M | YES (eval claims) |
| Honesty rules | status-gated claims, fixture quarantine | `business/claims.py` | Strong | — | — | — | — | — |

---

## 12. Roadmap (prioritized)

**P0 — before another production batch:**
- Finalize TQ-004 (complete CTE re-verification + quality refresh) —
  deliverable: final v5 report; test: 0 provisional flags.
- Fix contamination-rate reporting quirk — test: health shows
  rate consistent with flagged_count.
- Add record/model/source license metadata to Golden schema (Part 6) —
  test: every Golden record carries license fields; counsel clears
  abliterated-model lineage.
- Complete human audit of 60-sample + second auditor on subset,
  report κ — test: κ reported, failure rate ≤ 0.10.

**P1 — before any public sample:**
- Instruction-diversity program (unique-instruction ratio ≥ 0.25) +
  prescriptiveness review of TQ-004-style prompts — test: metric in
  health; audit sample of prompts passes naturalness review.
- Public/training/private field separation in products — test:
  training artifact contains zero PRIV-V fields (scanner test).
- Croissant JSON-LD + full datasheet per release — test: valid
  Croissant file in release.
- Signed manifests (Sigstore/cosign) — test: signature verifies offline.

**P2 — before a paid pilot:**
- Production private benchmark ≥ 500 items, frozen, paraphrase-probed —
  test: probe delta reported; contamination clean.
- Ambiguity/infeasible-question handling — test: TrustSQL-style split
  reported.
- Real fine-tune lift experiment (Phase 8) — test: verdict from
  measured delta, not fixtures.

**P3 — before enterprise sale:**
- Cross-engine validation (SQLite + Postgres runners) — test:
  2-engine agreement rate reported.
- Second-oracle sampling on audit subset — test: agreement rate.
- Support org, update policy, terms, deprecation policy docs.

**Later:** preference/failure/adversarial products; verification API;
multi-dialect; preference-learning formats; scheduled re-verification.

---

## 13. Scorecard (100 points, every deduction explained)

Weights: correctness proof 25 · integrity 15 · coverage/diversity 15 ·
docs/provenance 15 · audit 10 · reproducibility 10 · legal/commercial 10.

**Production-001: 62/100.** Deductions: single dialect/engine (−3);
no second oracle (−2); semantic dup 0.862 (−2); contamination-report
quirk (−2); 7/10 families (−5); 7 unique instructions (−4);
12–19 KB records unseparated (−2); no Croissant (−1); unsigned
manifests (−1); zero completed audits (−7); declared-only difficulty
(−1); no license metadata (−3); no measured lift (−2). (62 = 100−38;
arithmetic in `scorecard.md`.)

**Latest completed qualification (TQ-003 v4 final; TQ-004 excluded as
provisional): 67/100** — correctness 20, integrity 13 (targeted run,
lower duplication), coverage 9 (3 families by design + explicit
contracts), docs 12, audit 3, reproducibility 9, legal 1.

**Proposed future commercial release (after P0–P2): 90+/100** path:
audits+κ (+7), license chain (+3), field separation (+2),
Croissant+signatures (+2), benchmark (+2), diversity program (+4).

## 14. Go/no-go

**READY FOR ANOTHER CONTROLLED QUALIFICATION.** Production-001 alone
fails family coverage minimums (7/10) and instruction-diversity floors;
TQ-004 is provisional; zero audits are complete; the model license is
uncleared; the hypothesis is INSUFFICIENT_EVIDENCE. None of this is
fatal — the machinery is genuinely strong — but a paid pilot or public
sample now would sell claims the evidence cannot yet carry. The next
controlled qualification (finalized v5 + audit + license clearance) is
the correct gate, then a limited production batch.

## 15. Bibliography (direct links)

- Yu et al., Spider, EMNLP 2018 — https://aclanthology.org/D18-1425/
- Li et al., BIRD, NeurIPS 2023 D&B — https://arxiv.org/pdf/2305.03111
- Jin et al., Text-to-SQL Benchmarks are Broken, CIDR 2026 —
  https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf
- Jin et al., Pervasive Annotation Errors, PVLDB — https://www.vldb.org/pvldb/vol19/p931-jin.pdf
- Ranaldi et al., Termite contamination, ACL Findings 2024 —
  https://aclanthology.org/2024.findings-acl.827.pdf
- SPENCE paraphrase probe — https://arxiv.org/pdf/2604.17771
- Dr.Spider, ICLR 2023 — https://arxiv.org/pdf/2301.08881
- TrustSQL — https://arxiv.org/html/2403.15879v6
- Lei et al., Spider 2.0, ICLR 2025 — https://arxiv.org/abs/2411.07763
- Spider 2.0-AIFunc — https://arxiv.org/abs/2607.06229
- WikiSQL card (license unknown) —
  https://huggingface.co/datasets/Salesforce/wikisql
- LLMSQL/WikiSQL cleaning — https://arxiv.org/pdf/2510.02350
- SParC/CoSQL stats (CoSQL paper) — https://arxiv.org/pdf/1909.05378
- KaggleDBQA (Lee et al., ACL 2021) —
  https://www.microsoft.com/en-us/research/wp-content/uploads/2021/06/ACL2021_KaggleDBQA.pdf
- Gebru et al., Datasheets for Datasets, CACM 2021 (cited in Croissant
  paper below)
- Croissant, NeurIPS 2024 D&B —
  https://proceedings.neurips.cc/paper_files/paper/2024/file/9547b09b722f2948ff3ddb5d86002bc0-Paper-Datasets_and_Benchmarks_Track.pdf
- SQLLogicTest docs — https://sqlite.org/sqllogictest/doc/trunk/about.wiki
  and https://duckdb.org/docs/current/dev/sqllogictest/intro
- NIST AI RMF 1.0 — https://doi.org/10.6028/NIST.AI.100-1 ;
  GenAI Profile 600-1 — https://doi.org/10.6028/NIST.AI.600-1
- ISO/IEC 5259-2:2024 — https://www.iso.org/standard/81860.html
- Mistral model licenses — https://platform-docs-public.pages.dev/getting-started/models/weights
  ; Devstral Apache-2.0 — https://mistral.ai/news/devstral/
- Landis & Koch κ bands — https://www.ncbi.nlm.nih.gov/books/NBK92287/table/executivesummary.t2
- Artstein & Poesio agreement survey (κ>0.8; 80% rule) —
  https://aclanthology.org/W17-7401.pdf
- AWS Data Exchange provider requirements —
  https://docs.aws.amazon.com/data-exchange/latest/userguide/provider-getting-started.md
  ; publishing guidelines —
  https://docs.aws.amazon.com/data-exchange/latest/userguide/publishing-guidelines.html
- Snowflake Marketplace listings/legal —
  https://docs.snowflake.com/en/user-guide/data-marketplace and
  https://docs.snowflake.com/en/en/collaboration/collaboration-listings-legal
- EDPB Opinion 28/2024 — https://www.edpb.europa.eu/news/edpb-opinion-on-ai-models-gdpr-principles-support-responsible-ai_en
- EDPS synthetic-data TechSonar —
  https://www.edps.europa.eu/press-publications/publications/techsonar/synthetic-data
- Beduschi 2024, synthetic data & GDPR —
  https://journals.sagepub.com/doi/10.1177/20539517241231277
- Ganev, When Synthetic Data Met Regulation — https://arxiv.org/pdf/2307.00359
- SLSA provenance — https://slsa.dev/spec/v1.0/provenance ;
  C2PA spec — https://spec.c2pa.org/specifications/specifications/1.0/specs/C2PA_Specification.html
- SWE-bench Verified (500 human-filtered) — https://www.swebench.com/verified.html

## 16. Claims that remain unverified

No measured model lift; no customer willingness-to-pay; no market
size; cross-engine portability; second-oracle agreement; auditor κ;
production-002 yield; TQ-004 final numbers; abliterated-model license
safety; marketplace acceptance.

## 17. Questions requiring legal or customer validation

Legal counsel: abliterated-derivative output ownership and
attribution; Apache-2.0 notice compliance in distributions;
instruction copyright; indemnity posture; export classification.
Customer validation: which product (benchmark vs training) buyers
want first; acceptable audit-failure rate; price; update cadence;
on-prem vs hosted benchmark delivery.
