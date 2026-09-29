# Phase 8 — Commercial, GTM & Customer Validation (as-built)

Status: **implemented** (`verified_data_factory.business`).

## What Phase 8 is

A validation and commercialization **evidence layer** over frozen
Phases 1–7. It consumes Golden records, snapshots, releases, and
provenance — it redefines none of them. Its job is the business chain:

```text
Technical capability → Dataset value → Model/agent improvement →
Customer usefulness → Commercial willingness → Repeatable proposition
```

## What Phase 8 is not

No payments, no CRM, no customer portal, no marketing automation, no
GPU training platform, no proprietary model API requirement, no web
scraper, no competitor-intelligence system, no frontend.

## Evidence discipline

Every record carries a load-bearing status:

- `OBSERVED` — seen in practice.
- `MEASURED` — measured with a stated method and population.
- `USER_REPORTED` — a customer said so (their words, not our inference).
- `ASSUMED` — hypothesis, explicitly labeled.
- `UNKNOWN` — not yet known.
- `TEST_FIXTURE` — synthetic test data, quarantined from production
  evidence by construction.

Assumptions never masquerade as measurements: `MEASURED` claim status
requires `MEASURED` evidence, customer validation requires
`USER_REPORTED` evidence, and fixture data cannot support production
claims (enforced in `business.claims`).

## Honest outcomes

`INSUFFICIENT_EVIDENCE` is a valid result — for experiments, for the
core hypothesis, and for the business report. The phase discovers the
truth; it does not manufacture validation.

## Current core-hypothesis status: INSUFFICIENT_EVIDENCE

FACT: the experiment framework, private-benchmark lifecycle,
comparison math, economics, and claim validation are implemented and
tested against deterministic fixtures.

UNKNOWN: whether verified synthetic SQL data improves any real model
on any unseen benchmark (no real model experiment has run), what any
customer will pay, and every market-size figure.

See `docs/experiments.md`, `docs/model-value.md`,
`docs/customer-validation.md`, `docs/economics.md`, and `docs/gtm/`.

## CLI

- `factory business benchmark create|validate|contamination`
- `factory business experiment create|run`
- `factory business compare`
- `factory business economics`
- `factory business customer record`
- `factory business pilot create|transition|evaluate`
- `factory business claims validate`
- `factory business report`
- `factory business export`
