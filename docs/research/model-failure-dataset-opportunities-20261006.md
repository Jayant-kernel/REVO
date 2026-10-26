# Dataset opportunities around model failures

Research date: 6 October 2026. Scope: public primary-source research, benchmark pages, and first-party product documentation. This is an opportunity assessment, not a buyer interview study or an independent model evaluation. REST is interpreted as REST APIs; the earlier term remains ambiguous.

## Recommendation

Test three wedges first: API recovery workflows, spreadsheet debugging, and precise editing of existing PowerPoint decks. Accounting reconciliation is especially attractive as an extension of Revo's SQL fixtures and provenance system, provided an accounting expert can review the contracts. Keep SQL as the current engineering foundation while testing a new market; this research does not justify abandoning it.

My ranking is a judgment about verifiability, attainable scope, buyer access, and fit with Revo. It is not a measured market-size ranking. Named product vendors below are examples of potential buyer categories or competitors, not confirmed prospects. No source establishes willingness to buy our dataset.

The product should combine tasks, valid starting environments/files, expert solutions, execution or artifact checks, failure examples, and private evaluation variants. A pile of prompt-answer pairs is easier to copy and gives buyers less evidence of value.

## Evidence that changes the decision

1. **API chains remain meaningfully difficult, but simple calls are comparatively strong.** Postman's APIFlow-Bench reports 19 models on generated REST workflows. On its 20-subtask slice, point estimates range from about 44% to 73%; short subtasks are mostly much easier. It also reports final-answer failures after successful state changes. The long-chain slice contains only 11 worlds, confidence intervals overlap, and axis samples are uneven. Do not turn this into a universal model ranking or treat every API operation as an unsolved problem. [APIFlow-Bench](https://blog.postman.com/apiflow-bench/)

2. **Business spreadsheet workflows are a better target than elementary formulas.** SpreadsheetBench 2 covers 321 tasks involving financial models, debugging, and visualization. Its correctness checks include required changes and preservation of other cells. The page's static summary and newer leaderboard snapshots differ, so no single number is treated as the latest best score here. [SpreadsheetBench](https://spreadsheetbench.github.io/)

3. **PowerPoint editing has direct evidence of difficulty.** PPT-Eval reports 120 tasks over 12 files; Claude 4.5 Opus achieved 45% task success in the published setup. This is historical evidence for a specific agent and environment, not the current ceiling for every presentation product. [PPT-Eval](https://proceedings.mlr.press/v306/gandhi26a.html)

4. **Accounting needs consistent evidence, not merely plausible totals.** FinBalance reports at most 46% exact final-balance-sheet accuracy for six evaluated models on 710 examples, with failures linking entries to documents and aggregating them. It is a new research benchmark; external production generalization is unproven. [FinBalance](https://arxiv.org/abs/2606.15949)

5. **A training-data diagnosis can be wrong.** FinRCA-Bench holds the reasoning model fixed and changes retrieval; reported exact accuracy changes from 2.05% to 72.44%. This is a synthetic accounts-payable reconciliation benchmark, but it illustrates why retrieval, tools, and evidence access must be tested before proposing fine-tuning. [FinRCA-Bench](https://arxiv.org/abs/2608.18534)

## Opportunity inventory

The proposed datasets and buyers are inferences from the evidence. Multiple rows share a research family; they are distinct task wedges, not independent estimates of market size.

| Wedge | Failure or research gap | Proposed dataset and verifier | Potential buyer; main obstacle |
|---|---|---|---|
| REST workflow recovery | Long dependencies, re-authentication, rejected requests, and final-state/report mismatches [APIFlow](https://blog.postman.com/apiflow-bench/) | Local API worlds, injected recoverable errors, successful traces; state, provenance, and final-answer checks | Agent/integration vendors; realistic simulation and existing public benchmarks |
| Business-policy tool use | Conversations require tool actions consistent with policy and user intent [tau-bench](https://sierra.ai/resources/research/tau-bench) | Policy-controlled returns, cancellations, account updates; database-state and policy checks | Support-agent vendors; rules and simulator can introduce ambiguity |
| Workbook debugging | Cross-sheet logical/reference errors and preservation constraints [SpreadsheetBench 2](https://spreadsheetbench.github.io/) | Broken workbook, brief, corrected workbook, dependency-aware hidden inputs | Spreadsheet-agent vendors; reliable recalculation and licensed source files |
| Financial-model completion | Multi-statement dependencies and business assumptions [SpreadsheetBench 2](https://spreadsheetbench.github.io/) | Incomplete models with expert-completed formulas; perturb assumptions and compare results | Finance copilots; expensive expert labels |
| Exact PowerPoint edits | Creation/editing tasks yield partial progress and unintended changes [PPT-Eval](https://proceedings.mlr.press/v306/gandhi26a.html) | Before/after PPTX, precise instruction, action trace; object structure, rendering, editability, unchanged-slide checks | Presentation/office-agent vendors; subjective grading and rendering differences |
| Source-grounded deck production | Layout reasoning and coherent placement remain difficult [PPTBench](https://arxiv.org/abs/2512.02624) | Owned source materials, brand template, editable deck; factual traceability, overflow checks, expert rubric | Presentation vendors; crowded market and high annotation cost |
| Document-to-ledger reconciliation | Source binding, consistent entries, and aggregation [FinBalance](https://arxiv.org/abs/2606.15949) | Invoices, credits, statements, ledger truth; accounting invariants and evidence references | Accounting automation; professional review and jurisdiction-specific rules |
| Financial root-cause evidence retrieval | Correct labels can lack complete supporting records [FinRCA](https://arxiv.org/abs/2608.18534) | Transaction graphs, known injected discrepancies, required evidence sets | Reconciliation vendors; retrieval engineering may beat training |
| Complex document extraction | Diverse documents, nested tables, reading order [OmniDocBench](https://arxiv.org/abs/2412.07626) | Owned/synthetic forms and scans paired with structured truth; field, row, and table checks | Document-AI vendors; generic OCR is competitive |
| Conflicting enterprise knowledge | Near-duplicates, outdated facts, missing evidence across sources [EnterpriseRAG-Bench](https://arxiv.org/abs/2605.05253) | Coherent synthetic company corpus, dated policies, answer/clarify/abstain targets | Enterprise-search vendors; access control and retrieval may be root cause |
| Accessible interactive interfaces | Visually good output can violate accessibility checks [A11yn](https://arxiv.org/abs/2510.13914) | Broken/corrected UIs; automated audits plus keyboard, focus, and screen-reader review | Coding/site-builder vendors; automated audits are incomplete |
| Whole-repository migrations | Passing old tests does not prove migration completion [SWE Refactor Bench](https://arxiv.org/abs/2608.23564) | Licensed repo snapshots, migration briefs, reviewed patches; migration audit and hidden behavioral tests | Coding-agent vendors; costly environments and ground truth |
| Infrastructure changes | IaC resource dependencies require domain reasoning [SWE-InfraBench](https://arxiv.org/abs/2606.05249) | Small CDK/Terraform change tasks; synth/plan, resource assertions, optional disposable deployment | DevOps agents; historical tested models and cloud costs |
| Vulnerability repair preserving behavior | Crash suppression and memorized patches can inflate success [PatchBench](https://arxiv.org/abs/2609.04075) | Authorized isolated repair tasks; security regression and preserved functional behavior | Security/coding-agent vendors; specialist validation required |
| Optimization constraint formulation | Solver use does not ensure correct global constraints [OPT-Engine](https://arxiv.org/abs/2601.19924) | Scheduling/routing briefs and executable models; feasibility and objective-quality checks | Logistics/planning software; expert specifications and costly solving |
| Parametric CAD generation/editing | Geometry alone misses parameters and engineering design intent [BenchCAD](https://arxiv.org/abs/2605.10865) | Part specs, programs, edit requests; kernel validity, dimensions, editability checks | CAD copilots; geometry expertise and substantial public corpora |
| Cross-module RTL | Practical hierarchy remains harder than small module tasks [ChipVerilog](https://arxiv.org/abs/2607.13079) | Reviewed specs, RTL, testbenches; compilation, simulation, equivalence checks | Chip-design assistants; specialist talent and IP rights |
| Dialect/code-mixed speech | Local dialect data can materially help transcription [Dialect Matters](https://arxiv.org/abs/2601.04373) | Consented noisy speech, entity labels, transcript and intended action | Voice-agent vendors; acquisition and annotation, not unlimited synthetic text |
| Multilingual voice actions | Task completion and interaction quality vary by language [tau-Multilingual](https://arxiv.org/abs/2609.35820) | Calls with tools, interruptions, entity corrections; action, interaction, and speech scoring | Voice-agent vendors; Hindi was near English in this study, so target a measured narrow gap |
| FHIR resource navigation | Interoperable records require complex retrieval and reasoning [FHIR-AgentBench](https://arxiv.org/abs/2509.19319) | Synthetic resource bundles and questions; resource validity and evidence-linked answers | Healthcare software; clinical review, standards expertise, long procurement |
| Scientific analysis validity | Open-ended exploration and robust scientific reasoning remain uneven [SciAgentArena](https://arxiv.org/abs/2606.12736) | Reproducible domain workflows with injected leakage/unit/statistical errors | Research-agent vendors; validity may require expert judgment |
| Layout-preserving translation | Translation also requires preserving reading order and document geometry [BabelDOC](https://aclanthology.org/2026.acl-demo.25.pdf) | Owned multilingual documents and corrected translations; layout/terminology/expert checks | Localization/document vendors; language experts and subjective quality |

## Three practical pilot designs

These are proposed experiments, not existing datasets or fixed budgets.

### API recovery

Start with order-to-refund workflows in a local service. Vary expired tokens, request-schema changes, timeouts after writes, duplicate retries, and legitimate business-policy refusal. Make requirements discoverable through specs or truthful error messages. Require both correct final state and truthful reporting. Keep different workflow graphs and API versions out of training.

Measure end-to-end completion, duplicate side effects, collateral changes, recovery, and cost. Compare better documentation/tools against a training-data intervention. Revo's fixtures, hidden tests, sandboxing, and provenance are relevant, but an API state machine is new engineering work.

### Workbook debugging

Create a small set of owned multi-sheet business workbooks, inject reviewed errors, and retain a trusted working version. Target broken references, incorrect aggregation, hardcoded values replacing formulas, and changing assumptions. Recalculate in the intended spreadsheet engine; writing a formula string is not proof it works. Test new input values and workbook structures, not only the visible original totals.

Measure complete-task correctness, untouched-cell preservation, formula robustness, reviewer time, and cost. Financial-model templates already have public and commercial competition; the wedge is reliable debugging of a particular customer's workbook class.

### Existing-deck editing

Build owned decks and paired edits: update a linked chart, change selected layouts, repair overlaps, apply a master, or translate selected content while preserving structure. The output must be editable PPTX. Check object structure and render in the target application, then have reviewers assess factual accuracy and design quality.

Split by source deck, theme, and task family. Do not count 100 variants of one deck as 100 independent environments. The person the user knows could provide access to recurring failures; no willingness to pay is yet established.

## Demand and competition

First-party products show that these workflows are being commercialized: Gamma documents enterprise presentation rollout and workspace templates; Shortcut documents spreadsheet modeling and editing; Extend exposes per-field extraction evaluations and published document benchmarks. These are investment/product signals, not proof that these companies buy third-party datasets. [Gamma](https://help.gamma.app/en/articles/16951482-what-is-gamma-enterprise), [Shortcut](https://mog.shortcut.ai/tutorial/by-feature/action-vs-ask), [Extend](https://docs.extend.ai/evaluation/running-evaluation-sets)

Mercor's September APEX-Agents revision reports real cross-application professional tasks and changes grading to prevent hedged multiple-answer responses from gaming rubrics. This is both a competitive signal and a warning: a verifier can reward superficially convincing outputs unless it measures the requested outcome precisely. [APEX-Agents 1.1](https://www.mercor.com/blog/introducing-apex-agents-1-1/)

Public datasets already exist in nearly every category above. A defensible commercial contribution would be rights-cleared fresh tasks, private hidden variants, customer-specific environments, expert corrections, reliable graders, and measured incremental value. Downloading and repackaging public benchmarks does not establish that contribution or permission to redistribute them.

## How to establish that data is the right intervention

1. Obtain an owned or authorized sample of actual customer failures; choose a narrowly defined deliverable.
2. Verify the task is solvable and the labels are correct. Audit the evaluator independently.
3. Run the target model with fixed tools, model version, task budget, and repeated trials.
4. Classify failures: missing knowledge, retrieval, tool interface, runtime, instruction ambiguity, planning, or grading error.
5. Compare prompt/documentation fixes, better retrieval, and deterministic helper tools before training.
6. Where the buyer can train, compare an appropriate training intervention with controls on genuinely held-out task/environment families. If they cannot train a hosted model, sell evaluations, retrieval examples, or workflow improvements rather than claiming fine-tuning uplift.
7. Track full-task success, severe error rate, cost, and human correction time. A model-judged preference improvement alone is insufficient for execution tasks.
8. Require a paid pilot or another concrete procurement commitment before scaling production.

No benchmark proves that our proposed data will improve a model. The evidence supports selecting experiments. The clearest next step is one narrow buyer-backed pilot, using Revo's verification-first approach and adding only the new domain machinery that pilot needs.
