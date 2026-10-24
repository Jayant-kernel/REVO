# Bounded final integration corrections

- First finalization stopped before artifact creation because START-HERE received
  a fresh-copy instruction/navigation clarification after Worker C pinned it.
  The fail-closed hash assertion identified that document-only drift. Updated
  only the index's START-HERE digest to the current reviewed-intent bytes; no
  SQL, expected output, authoritative source or replay executable changed.
- The outer native invocation's launch/terminal audit filenames collided with
  copied native child launch/terminal filenames. The retained files describe the
  actual bounded child, including PID, exact command, start and terminal. The
  outer 10800s bound and command are reconstructible from `integrate.py`; the
  observed outer terminal (exit0/no timeout/1293.578s) is retained in the tool
  output. No new native run is justified solely for duplicate supervision
  metadata. Do not describe the child metadata as a distinct outer observation.
- Separate review snapshots remain immutable. Their exact manifest digests apply
  to their review times, not the final artifact after these bounded document
  updates. The coordinator's final source-reference/link/inventory checks cover
  the final bytes.
