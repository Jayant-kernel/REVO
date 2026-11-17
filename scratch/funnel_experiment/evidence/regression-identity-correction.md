# Regression Identity Correction

The `1003 passed` and `1018 passed` full-regression commands were launched without
a source-tree identity captured at launch. Later guard identities cannot certify
those earlier starts. Both results are therefore `INFORMATIONAL`; their launch
source identities are `UNPROVEN`.

This correction is append-only. A new full regression will be certified only after
recording source identities immediately before launch and immediately after its
terminal summary, with no source edits while it runs.
