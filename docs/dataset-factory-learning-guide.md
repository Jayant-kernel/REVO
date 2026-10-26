# What to learn to build trustworthy datasets

This guide is for someone starting with little background. It covers dataset creation in general, then applies those ideas to Revo's Verified SQL Data Factory. You do **not** need to master every topic before helping. Learn the first three sections, build a small example, and return to the later sections as the work demands.

The central question is simple: **If someone uses a row from our dataset, why should they trust its meaning, answer, origin, and usefulness?** A successful SQL execution answers only a small part of that question.

## 1. First, understand what a dataset is

A dataset is a collection of records made for a purpose. A record might be a sales transaction, an image and its label, or a question paired with an SQL answer. The same records can be useful for one purpose and unsuitable for another.

Learn these ideas first:

| Idea | Plain meaning | Question to ask |
| --- | --- | --- |
| Unit of observation | What one row represents | Is this one customer, one order, one SQL task, or one model attempt? |
| Field and type | A named value and its allowed form | Is `amount` money, a count, or a string? Can it be NULL? |
| Population | The full group you want to describe | Are we measuring all generated attempts or only accepted rows? |
| Sample | The records actually examined | Was the sample selected fairly, or chosen because it looked good? |
| Label or target | The answer the dataset claims is correct | Who or what established that answer? |
| Split | A separate role for records | Could information from training appear in evaluation? |
| Version | A stable identity for data and rules | Can we reconstruct what a past result meant? |

For any dataset, write a one-paragraph **data specification** before collecting rows: intended users, intended use, record structure, inclusion and exclusion rules, label definition, source, quality gates, known limits, and who may access it.

Practice: take a small spreadsheet and describe what one row means, which values are missing, which rows are duplicates, and what conclusion the sheet *cannot* support.

## 2. Learn to ask precise business questions

Data quality begins before SQL. A vague question produces a vague answer even when the code runs perfectly.

For each task, identify:

- **Entity:** customer, invoice, shipment, playback, visit, or another real-world thing.
- **Grain:** one output row per what? For example, per customer and month.
- **Measure:** what is counted, summed, averaged, or compared, including units.
- **Population:** which source rows qualify? Define status and eligibility filters.
- **Time rule:** timezone, inclusive/exclusive endpoints, event date, and reporting period.
- **Relationship rule:** what happens when a related row is missing or repeated?
- **Tie rule:** if two events have the same timestamp, which wins?
- **Output rule:** columns, types, ordering if relevant, and empty-result behavior.

Example: “Show paid invoices by account” leaves open whether cancelled invoices count, whether duplicate account rows multiply results, and whether accounts with no paid invoices appear. A useful specification answers those questions. Never invent the answer just to make a verifier pass; ask for the business rule or keep the task unresolved.

Practice: write three different questions about the same `accounts` and `invoices` tables. Make their business meanings genuinely different, rather than changing table names or wording.

## 3. Learn SQL and relational data deeply

Start with tables, rows, columns, keys, types, filtering, sorting, `GROUP BY`, aggregates, and joins. Then learn CTEs, subqueries, `EXISTS`, window functions, deduplication, and date/time logic. For Revo, learn the behavior of **DuckDB**, because SQL dialects differ.

These are the traps that matter most for correctness:

| Trap | Why it matters |
| --- | --- |
| Bag semantics | SQL normally keeps duplicate rows. A join may multiply rows and totals. |
| NULL and three-valued logic | `NULL = NULL` is not true; filters and aggregates can behave unexpectedly. |
| Join fanout | Joining one account to many invoices and many payments can count each combination. |
| Ties | `ROW_NUMBER()` without a complete ordering may select an arbitrary winner. |
| Time boundaries | Midnight, timezones, week starts, and inclusive endpoints change answers. |
| Empty groups and missing links | A correct query may need zero-valued groups or may omit them; the contract decides. |
| Numeric types | Currency precision, rounding, negative values, and integer overflow matter. |
| Ordering | Rows are not guaranteed to appear in a particular order without `ORDER BY`. |

Practice: create tiny tables where a plausible wrong query returns the same answer as the correct query on ordinary data, then add one duplicate, NULL, missing relation, or boundary timestamp that exposes the difference. This is more valuable than memorizing syntax alone.

Read in this repo: [task semantics](task-semantics.md), [golden record](golden-record.md), and the relevant YAML task under `templates/sql/`. Treat the public task contract as the source of business meaning.

## 4. Learn how a dataset is produced

The general pipeline is **define → collect or generate → validate → label → select → split → package → monitor**. For Revo, a task specification and fixtures go to a candidate generator; candidate SQL runs in a sandbox; independent checks decide whether it is eligible; quality and provenance gates decide whether it enters a dataset.

Know the difference between these objects:

- **Task:** the question, schema, constraints, and expected behavior.
- **Fixture:** a small synthetic database used to exercise behavior.
- **Candidate:** SQL produced for a task. One task may have several candidates.
- **Oracle:** an independently designed way to determine the expected result.
- **Verification receipt:** evidence that particular checks ran against particular versions.
- **Golden:** a selected candidate that passed the applicable automated gates.
- **Dataset:** a versioned collection of eligible, appropriately diverse records.
- **Review package:** a presentation of selected records and evidence for a reviewer.

A row can pass an execution check and still be wrong. A qualification fixture is evidence about a task; it is not automatically a model-generated dataset row. A partial Golden in a smoke run is not an accepted complete product.

Read in this repo: [architecture](architecture.md) for the intended layers, then the current [production continuation prompt](production/company-sample-continuation-prompt-20261010.md) for the present acceptance target. The architecture file contains historical planning language, so verify status against current source and receipts.

## 5. Learn verification, not just testing

Testing asks whether a program behaves as expected on selected inputs. Verification in this factory combines several ways to catch wrong business answers:

| Method | Simple explanation | Limitation |
| --- | --- | --- |
| Execution | Does the SQL parse and run safely? | A wrong query can run. |
| Result comparison | Does the result match an expected result? | A weak fixture may hide a mistake. |
| Independent oracle | Is there a separately designed reference answer? | Shared assumptions can make both sides wrong. |
| Hidden tests | Does the query work on cases unseen during generation? | Hidden cases may still be too narrow. |
| Property tests | Does a required invariant hold? | The property must reflect the business rule. |
| Metamorphic tests | If data changes in a controlled way, does the result change as required? | A relation that never distinguishes wrong SQL adds little value. |
| Mutation tests | Can the tests catch plausible incorrect SQL changes? | Invalid SQL and infrastructure failures are not semantic kills. |
| Differential tests | Do alternative formulations agree on many inputs? | Agreement does not prove that their shared interpretation is right. |

Learn the words **false acceptance** (a wrong answer is approved), **false rejection** (a correct answer is rejected), **abstention** (the checker cannot establish enough), and **execution failure** (the infrastructure failed). Keep these counts separate. A checker that rejects everything has zero false acceptances but is useless.

For each difficult task, try to produce both a correct alternative SQL query and a *plausible* wrong one. Find a small counterexample where they differ, and explain the business reason. That is the heart of Revo's quality claim.

Read in this repo: [verification principles](verification-principles.md), [quality metrics](quality-metrics.md), and [engineering rubric](production/engineering-rubric.md).

## 6. Learn measurement and statistics

Always state the **denominator**. “223 wrong queries rejected” means something different from “223 of 223 curated wrong queries rejected,” and neither measures performance on every future SQL query.

Useful measurements include:

- **Generation yield:** accepted novel records ÷ physical model attempts, with retries included.
- **Verification outcomes:** correct accepted, correct rejected, wrong accepted, wrong rejected, abstentions, and infrastructure failures.
- **Coverage:** family, construct, schema, domain, difficulty, and edge-case counts.
- **Redundancy:** exact and meaningful semantic duplicates among selected records.
- **Replay success:** exported records reproduced successfully ÷ exported records attempted.
- **Cost:** compute time or money per *novel accepted* record, not just per generated candidate.

Study sampling bias, confidence intervals, held-out evaluation, data leakage, and the difference between a curated challenge set and real-world error frequency. Freeze an evaluation set before looking at its outcomes; if you use those cases to repair the checker, they become development cases and a new held-out set is needed.

An engineering score, a dataset quality assessment, model accuracy, completion percentage, and sales readiness are **different measures**. Write down each rubric *before* scoring. The historical 52/100 assessment in this project measured a particular commercial-readiness product; it is not a current SQL accuracy score. The frozen engineering rubric requires its own executed inputs.

Practice: report a small experiment as raw counts, denominators, selection method, and limitations before converting anything to a percentage.

## 7. Learn diversity and dataset design

More rows do not necessarily add more information. Changing a seed, table name, or sentence wording can produce another row with the same underlying business problem.

Build a coverage matrix across business question, SQL family, schema shape, domain, edge case, and error type. Seek *material* differences: for example, invoice eligibility, shipment final-leg selection, event ordering, and grade revision identity are different business rules. A balanced dataset needs distinct problems within each category, not only one template repeated many times.

Learn exact deduplication, semantic deduplication, train/evaluation leakage, public benchmark overlap, and role isolation. A high duplicate flag among sibling candidates does not automatically mean contamination from an external benchmark. Check the population and match source before making that claim.

Revo's current internal target is 80 accepted records, eight in each of ten SQL families, with additional instruction, schema, domain, construct, edge, novelty, and verification gates. The exact current authority lives in the [continuation prompt](production/company-sample-continuation-prompt-20261010.md) and frozen configuration; do not substitute the row count for quality.

## 8. Learn reproducibility and data engineering

Someone else should be able to answer: Which task, model, prompt, code, dependencies, fixtures, and checks produced this row? Can they replay it without your laptop or original checkout?

Learn stable identifiers, content hashes, manifests, immutable run identities, append-only journals, versioned schemas, JSONL and Parquet, typed round trips, and atomic publication. A hash detects changes to recorded bytes; it does not prove that the original meaning was correct. Binding request and response hashes **when the physical model call happens** is stronger than adding them later.

Also learn failure recovery: interrupted jobs, retries, duplicate spending, partial exports, stale source code, and missing receipts. Keep failed attempts. A later passing run does not erase an earlier unexplained failure.

Practice: export one synthetic SQL example, copy it to another folder, replay it there, and then change its SQL. Your validation should accept the original and reject the changed copy.

Read in this repo: [provenance model](provenance-model.md), [reproducibility](reproducibility.md), and [artifact retention](production/artifact-retention.md).

## 9. Learn secure execution and operational basics

Model-generated SQL is untrusted input. Learn why the factory limits filesystem and network access, CPU, memory, time, processes, and allowed SQL operations. Learn the difference between a SQL failure, a sandbox failure, a model-provider failure, and a policy rejection. A timeout or backend crash is not evidence that SQL is semantically wrong.

The practical software skills are Python, Git, command-line work, reading logs, writing focused tests, type checking, linting, container basics, and debugging from a minimal reproducer. You do not need to become a security specialist immediately, but you must know which boundaries protect the host and which checks merely measure answer quality.

Read in this repo: [security](security.md), [technical stack](technical-stack.md), and [production start](production/START_PRODUCTION.md).

## 10. Learn model use, rights, and privacy

If a model generates dataset content, record its exact identity, configuration, prompts, responses, call count, errors, and permitted use. Distinguish a locally installed model from a model whose license and output rights are cleared for a particular use. Internal experimentation, sending outputs to a company, and redistributing weights are different actions.

Learn data minimization, synthetic data limits, personal information, copyright and license provenance, attribution, and contamination checks. Synthetic rows can still resemble sensitive or copyrighted material if their sources are not controlled. Keep hidden tests and reference answers out of model prompts and public samples.

Read in this repo: [licensing](licensing.md), project governance records, and the intended dataset card. Legal decisions need a qualified human owner; a pipeline PASS cannot supply them.

## 11. Learn packaging and actual usefulness

A useful dataset must be understandable and testable by someone outside the project. Learn to write a dataset card: what it contains, how it was made, supported SQL dialect, intended uses, exclusions, provenance, known failure modes, rights status, and evaluation limits.

For a technical reviewer, prepare a small, representative sample with question, schema meanings, SQL, typed expected result, one important edge case, and a replay command. Include whole-dataset statistics alongside the showcase so readers can see whether the attractive examples represent the population.

To establish value, ask a prospective user what errors their SQL agent makes, whether this dataset detects those errors, and whether it integrates into their workflow. If you later claim training improvement, run a controlled baseline-versus-treatment study on separate evaluation data. A strong internal checker result alone does not prove customer value.

Read in this repo: [business validation](business-validation.md) and the [current company package prompt](production/company-sample-continuation-prompt-20261010.md).

## A practical learning order

1. **Week 1: data and SQL basics.** Define row grain, types, keys, joins, aggregates, NULLs, and bags. Build five tiny DuckDB databases and predict each query's output by hand.
2. **Week 2: business semantics.** Specify five analytical questions completely: eligible population, measure, time, ties, relationships, output. Write a correct query and a plausible wrong query for each.
3. **Week 3: checking answers.** Add normal, boundary, and adversarial fixtures. Find a counterexample for every wrong query. Compare correct alternatives and record failures honestly.
4. **Week 4: dataset quality.** Create a 10-record pilot with distinct business problems. Measure duplicates, coverage, accepted yield, and replay success with explicit denominators.
5. **Then: production discipline.** Add source-bound provenance, independent review of ambiguous semantics, held-out checker evaluation, safe execution, release packaging, and rights decisions.

These are study blocks, not a promise that the full Revo project will finish in five weeks. You can work on real repo tasks while learning each block.

## A small capstone project

Create a five-task synthetic SQL mini-dataset across at least two domains. For every task, provide a plain-language question, schema and column meanings, a correct SQL answer, expected typed result, three fixtures, one plausible wrong SQL query, and a minimal fixture that exposes it. Keep generation attempts and selected records separate. Export the selected tasks, replay them from a different folder, and write a one-page dataset card explaining what has and has not been established.

If another person can understand the business rule, reproduce the output, and see *why* the wrong answer is wrong, you have learned the core of this field.

## Quick glossary

- **Contract:** the exact behavior a task requires, including edge cases.
- **Fixture:** a controlled set of input tables and rows.
- **Oracle:** a reference method for deriving the expected result.
- **Counterexample:** a small input on which plausible correct and wrong solutions disagree.
- **Semantic mutant:** a valid SQL change that alters the business answer.
- **Mutation score:** the share of applicable valid wrong variants the tests detect under a stated rule.
- **Golden:** a selected record that passes the project's required automated gates.
- **Provenance:** the trace of where a record and its evidence came from.
- **Replay:** reproducing a recorded result from the recorded assets and versions.
- **Quarantine:** keeping a task out of eligible use until a real issue is resolved.
- **Held-out set:** evaluation material kept separate from development and tuning.
- **Dataset card:** a concise description of a dataset's construction, uses, limits, and rights.
