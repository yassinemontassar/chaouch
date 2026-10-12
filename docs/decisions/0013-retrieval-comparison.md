# 0013: Retrieval: dense bge-m3 alone, no BM25 fusion, no reranker

- **Status:** accepted (owner, 2026-10-12)
- **Date:** 2026-10-12
- **Related:** ADR 0003 (oracle documents), ADR 0006 (sources), ADR 0011 (main local model)

## Context
Phase 1 must find the official documents that B1 was given by hand (Falcon-H1 3B went from 0.09 to
0.67 correctness once the documents were in the prompt). Spec 9.2 plans BM25 + dense (bge-m3) fused
with RRF, then a cross-encoder reranker (bge-reranker-v2-m3). The owner also asked to compare a
second embedder, Qwen3-Embedding-0.6B, and to pick one from our numbers.

Questions are Derja (Arabic script, Arabizi, or mixed with French); 6 of the 8 procedure documents
are French. With 8 documents, Recall@5 is nearly trivial (5 chunks can cover most of the corpus), so
19 official pages on other procedures from the same portal were added as **distractors**
(owner-approved; checked against every required fact, none answers a gold question).

## Options
1. BM25 only (normalized Arabic and Latin text, Lucene idf)
2. Dense only: bge-m3 or Qwen3-Embedding-0.6B (its built-in query prompt), pgvector cosine
3. Hybrid: BM25 + dense, Reciprocal Rank Fusion (k = 60)
4. Hybrid + rerank: bge-reranker-v2-m3 on the top 20 fused chunks

## Experiment
`uv run tasks.py eval-retrieval`, gold set v1 (43 in-scope questions, questions.jsonl sha256
35830b865fa8), chunks sha256 2081d39596d8 (target 400 bge-m3 tokens, overlap 50). Two corpora in one
run: `core` (8 documents, 21 chunks) and `full` (core + 19 distractors: 27 documents, 51 chunks;
BM25 is built per corpus and the dense search filters by role, so `core` equals a core-only index).
Reports: `reports/2026-10-12_retrieval.md` (no reranker) and `reports/2026-10-12_retrieval_rerank.md`.

R@k = share of the gold documents in the top k **chunks** (what the LLM sees with top_k = 5).
MRR = mean of 1 / rank of the first chunk from a gold document. Intervals: 95% bootstrap over
questions; differences: paired bootstrap on the same questions. All models in float32 on CPU
(i5-12450HX, 8 cores), Postgres 16 + pgvector 0.8.7 in Docker.

## Results
**Full corpus** (27 documents), the one the decision rests on:

| Config | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| BM25 | 0.30 (0.17–0.44) | 0.47 | 0.49 | 0.40 (0.28–0.54) |
| **dense bge-m3** | **0.58** (0.44–0.73) | **0.85** | **0.91** | **0.74** (0.64–0.84) |
| hybrid bge-m3 | 0.42 (0.28–0.56) | 0.73 | 0.77 | 0.60 (0.49–0.71) |
| dense Qwen3-Embedding-0.6B | 0.42 (0.28–0.57) | 0.70 | 0.73 | 0.60 (0.48–0.72) |
| hybrid Qwen3 | 0.44 (0.30–0.59) | 0.65 | 0.71 | 0.59 (0.47–0.71) |
| hybrid bge-m3 + rerank | 0.51 (0.37–0.65) | 0.73 | 0.87 | 0.67 (0.56–0.78) |

Paired differences on the full corpus (MRR / R@1, 95% CI):

| A − B | MRR | R@1 |
|---|---|---|
| dense bge-m3 − BM25 | +0.34 (+0.18 to +0.49) | +0.28 (+0.09 to +0.45) |
| hybrid bge-m3 − dense bge-m3 | **−0.14 (−0.24 to −0.04)** | −0.16 (−0.31 to −0.02) |
| dense Qwen3 − dense bge-m3 | **−0.14 (−0.27 to −0.01)** | −0.16 (−0.34 to +0.01) |
| hybrid + rerank − hybrid (bge-m3) | +0.07 (−0.04 to +0.17) | +0.09 (−0.05 to +0.23) |
| hybrid + rerank − dense (bge-m3) | **−0.07 (−0.18 to +0.03)** | −0.07 (−0.22 to +0.07) |

By script of the question, full corpus (R@1 / MRR):

| Config | Arabic script (16) | Arabizi (15) | Mixed with French (12) |
|---|---|---|---|
| BM25 | 0.12 / 0.16 | 0.27 / 0.42 | 0.58 / 0.71 |
| dense bge-m3 | 0.53 / 0.72 | 0.57 / 0.72 | 0.67 / 0.79 |
| dense Qwen3 | **0.00** / 0.27 | 0.67 / 0.80 | 0.67 / 0.79 |
| hybrid bge-m3 + rerank | 0.38 / 0.52 | 0.53 / 0.74 | 0.67 / 0.78 |

By language of the gold document, full corpus (R@1 / MRR): dense bge-m3 0.43 / 0.52 on the 7
questions with Arabic gold documents, 0.61 / 0.78 on the 36 with French ones.

Effect of the distractors (dense bge-m3, core → full): R@1 0.77 → 0.58, R@5 0.98 → 0.91,
MRR 0.88 → 0.74. On the core corpus alone every dense config has R@5 ≥ 0.81.

**Qwen3 sanity check** (R@1 0.00 on Arabic-script questions looked like a bug). Ruled out:
padding / last-token pooling (a short chunk embedded alone or batched with a long one: cosine
1.0000), a stale or inconsistent index (freshly embedded chunks vs stored vectors: cosine 1.0), the
query instruction (present in the model config; with or without it, rankings stay wrong), and
float precision (bfloat16 was found and fixed before indexing). Example rankings show the cause:
for "قدّاش يكلّف الباسبور؟" Qwen's top 3 are Arabic-script distractors (fishing registration card,
seaman's book, birth-record correction) and the French passport page is 20th. Qwen matches the
**script** of Derja questions rather than their meaning: on the core corpus the only Arabic-script
pages are the birth pages (R@1 0.19); the 6 Arabic distractors take it to 0.00. It is the model.
Reproduce: `uv run python -m scripts.qwen_sanity_check`.

**Arabic diacritics** (all 16 Arabic-script questions carry shadda etc.). Stripping them from the
query only, full corpus: bge-m3 R@1 0.53 → 0.41, MRR 0.72 → 0.63 (worse); Qwen3 R@1 0.00 → 0.06,
MRR 0.27 → 0.32. A single spot check had suggested the shadda hurts bge-m3; over the 16 questions,
keeping the diacritics is better. Reproduce: `uv run python -m scripts.query_diacritics_check`
(query side only; the stored chunk vectors are unchanged).

Latency per question on CPU (p50 / p95): embed the question 426 / 653 ms (bge-m3),
807 / 1248 ms (Qwen3); pgvector search 3 / 4 ms; BM25 < 1 ms; **fusing + reranking 20 candidates
79.6 / 99.6 s** (bge-reranker-v2-m3, float32, max_length 512: ~4 s per pair).

## Decision
- **Embedder: bge-m3** (`default_embedder` stays `bge_m3`). Qwen3-Embedding-0.6B is worse on dense
  MRR (−0.14, interval excludes 0), fails on Arabic-script questions (R@1 0.00 on the full corpus)
  and is twice as slow per query; it is only slightly better on Arabizi.
- **Retrieval mode: dense only**, not hybrid. Adding BM25 through RRF lowers MRR by 0.14 (interval
  excludes 0): BM25 cannot bridge Derja questions to French documents (R@1 0.12 on Arabic-script
  questions), so fusion mostly mixes in wrong chunks. BM25 helps only on mixed-French questions,
  where dense is already as good.
- **No reranker.** Reranking the 20 fused chunks recovers part of what fusion lost (+0.07 MRR over
  hybrid, interval includes 0) but stays below dense bge-m3 alone (−0.07 MRR, −0.18 to +0.03), is
  weakest on Arabic-script questions (R@1 0.38 vs 0.53), and costs ~80 s per question on CPU.
  Latency is a hard constraint (owner): since reranking does not beat dense, the cheaper variants
  (fewer candidates, max_length 256, fp16 on the GPU) were **not** run.

## Consequences
- Phase 2 calls `retrieve(..., mode="dense")` with bge-m3. `hybrid` and `bm25` stay in the code and
  in `eval-retrieval`, to re-test once Arabizi is transliterated (Phase 4) or the corpus grows.
- **Derja vocabulary is the main retrieval weakness.** A spot check: bge-m3 scores
  "قدّاش يكلّف الباسبور؟" closer to an unrelated water-meter sentence than to the passport fee, but
  "قداش يكلف جواز السفر؟" (official noun) correctly. Follow-up to test: the Derja → official-term
  glossary proposed in ADR 0012, applied to the query. Stripping diacritics is **not** a fix (it
  lowers bge-m3 R@1 on Arabic-script questions from 0.53 to 0.41).
- **CNSS is the hardest procedure** (R@1 0.14 on the full corpus for every config without the
  reranker, 0.29 with it): the CNSS-contributions distractor outranks the registration page. A procedure router (Phase 3) that
  filters by procedure would remove this kind of error.
- **Revisit the reranker** only if a later change makes it beat dense (e.g. after the glossary or
  Arabizi transliteration), and then measure the cheap variants first (rerank_candidates 5–10,
  max_length 256, fp16 on the GPU next to Falcon with the CUDA torch build); adopt one only with the
  owner's approval. Not tested here: reranking the dense top 20 instead of the fused top 20 (the two
  pools overlap heavily on 51 chunks).
- Translating the query to French (spec 9.2) is not needed for now: French documents are not the
  weak spot (bge-m3 R@1 0.61 on questions with French gold documents vs 0.43 on Arabic ones).
- **Planned next, before Phase 2: gold set v2** (owner, 2026-10-12). Add the Arabic versions of the
  four French core pages, which the portal publishes under the same ids (`/Ar/..._D1618` passport,
  `D1309` CIN, `D1705` bulletin n°3, `D717` CNSS), relabel `gold_doc_ids` accordingly, and add new
  Derja questions ([HUMAN]). Then re-run `eval-retrieval`: these numbers compare only within gold v1.
- Spec §10 Phase 1 acceptance: `eval-retrieval` reports Recall@5 and MRR by script and document
  language, and this ADR compares BM25 / dense / hybrid / hybrid + rerank with numbers.
