# Legacy SaaS Provenance Search

## Scope

Read-only search on 2026-10-04 for an authentic historical SaaS contract or SQL
mapping in reachable Git history, reflog-reachable commits, and stashes.

## Results

- `git log --all -- templates/sql/funnel/saas_activation_payment.yaml` returned no
  commits.
- `git ls-tree -r` for the reachable historical reflog commit
  `641eed5c9ebac9a1dbfd9385dcc774b28629c649` contains only the pre-existing
  generic `completion` funnel templates, not a SaaS activation-payment template.
- `git stash list` returned no entries.
- The surviving generic SQL was recovered from the current untracked
  `tests/test_business_tasks.py`; it is not historical SaaS assignment evidence.

## Conclusion

No authentic historical SaaS SQL mapping or v1 contract was recovered. The artifact
`legacy_saas.sql` is a reconstructed legacy-generic formulation based on the
surviving generic mapping; historical SaaS assignment was not independently
recovered. Historical recovery status: UNPROVEN.
