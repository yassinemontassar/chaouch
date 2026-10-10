# 0003: Oracle context for B1/B2 uses cleaned gold documents, not chunks

- **Status:** accepted
- **Date:** 2026-10-10

## Context
B1/B2 paste the gold documents into the prompt. The local models run with a 4096-token context
(`OLLAMA_CONTEXT_LENGTH`), which has to hold the prompt, the documents, the question and the answer.

## Options
1. Join the gold document's chunks from `chunks.jsonl`.
2. Use the cleaned document (`processed/<doc_id>.md`), cut at a paragraph boundary to a token budget.
3. Use the full documents and raise the context window.

## Experiment
None needed with numbers yet. Chunks overlap by design (`overlap_tokens: 50` in `configs/retrieval.yaml`),
so joining N chunks repeats about 50 × (N − 1) tokens. Raising the context window grows the KV cache past
the ~3–3.5 GB VRAM budget (spec 3.1.2).

## Results
| Option | Repeated text | Fits 4096 context |
|---|---|---|
| Joined chunks | ~50 tokens per chunk boundary | yes, with less real content |
| Cleaned document + budget | none | yes |
| Full document | none | no, for long PDFs |

## Decision
Use the cleaned gold documents, cut at a paragraph boundary to `oracle_token_budget` (2500 bge-m3 tokens,
`configs/eval.yaml`). Each document starts with its title, source URL and retrieval date. The per-question
truncation flag and the truncation rate per system go in the report.

## Consequences
- The budget is counted with the bge-m3 tokenizer, which only approximates each LLM's own tokenizer. If
  Ollama reports prompt tokens close to 4096, lower the budget.
- A high truncation rate means B1/B2 never saw part of the answer; read their correctness with that in mind.
- B3 (ALLaM on Groq) also has a 4096-token context, so the same budget applies.
