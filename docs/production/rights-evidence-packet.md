# Checkpoint rights decision packet — pending

This packet records the decision still needed for a commercial SQL dataset.
It is not a legal opinion or a clearance record.

The smoke manifest identifies
`alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest`
with observed revision
`ollama-digest:a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4`.
Its governance status is `REVIEW_REQUIRED_NON_COMMERCIAL`. Production-001's
older artifact does not record that revision and must not be backfilled.

Source pages inspected on 2026-09-29:

- [Mistral's Devstral Small 2 announcement](https://mistral.ai/news/devstral-2-vibe-cli/)
  and [base model card](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512)
  identify the base as Apache 2.0.
- [Huihui's derivative card](https://huggingface.co/huihui-ai/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated)
  labels the derivative Apache 2.0 and recommends research, testing, or
  controlled use, avoiding direct public-facing commercial deployment.
- [AliBilge's quantization card](https://huggingface.co/AliBilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated/blob/main/README.md)
  labels its GGUF quantization Apache 2.0 and points to the Huihui derivative.

These are useful provenance leads. They do not establish that the exact local
Ollama digest corresponds to the reviewed GGUF file or that every obligation
for the intended output distribution is satisfied. The derivative's research
recommendation and its legal effect require the authorized owner's decision.

Evidence still needed from the authorized rights owner:

1. The exact checkpoint source, version, weights or manifest digest, and the
   origin of the Ollama package.
2. The derivative model's license and notices, linked to the exact artifact.
3. The upstream base model and any fine-tune/abliteration dependencies, their
   applicable terms, and whether obligations pass through to this use.
4. The permitted commercial generation and intended distribution of SQL,
   questions, schemas, fixtures, and packaged metadata.
5. Any restrictions on redistributing model outputs, synthetic data, or
   attribution; required notices and records.
6. A signed or otherwise recorded decision with reviewer identity, date,
   intended product scope, and cited evidence hashes.

No affirmative decision has been supplied. The release gate remains blocked.
If the checkpoint changes, record a new model snapshot, config identity, and
qualification run before using the new output in a review candidate.
