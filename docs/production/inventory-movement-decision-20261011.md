# Approved inventory input-row identity — 11 October 2026

The user explicitly selected **Input-row bag** for the forward inventory net-flow
contract. Each posted input row contributes once, even when movement IDs or whole
payloads repeat. No ID uniqueness, immutable-ID domain restriction or implicit
de-duplication is introduced. This is a public business-contract decision, not a
human SQL-quality review or an external-sharing approval.

`sql.cte.inventory_net_flow@2` makes that rule explicit while preserving signed
receipt addition/issue subtraction, year/status scope, all warehouses, one-sided
warehouses, zero totals, columns and ordering. Version1 remains unchanged and
quarantined. Its earlier authored reference negation overflow is retained; the
reference now widens INTEGER units before negation without changing business meaning.

Distinct question: reconcile two signed stock-movement input streams, rather than
threshold a one-table warehouse total. Domain: inventory. Schema role: receipt and
issue movement bags. Constructs: CTE, UNION ALL, grouped SUM, signed arithmetic;
correct alternatives include full outer aggregate reconciliation and correlated
sums. Boundaries: year ends, unposted movements, zero/negative corrections, one-sided
warehouses, repeated IDs/payloads and INTEGER extrema. This closes one CTE template
slot only after complete executed qualification; it is not an accepted product row.
