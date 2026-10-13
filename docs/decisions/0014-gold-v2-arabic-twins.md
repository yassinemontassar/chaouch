# 0014: Gold v2 light: Arabic twins of the core pages

- **Status:** accepted (owner, 2026-10-13)
- **Date:** 2026-10-13
- **Related:** ADR 0006 (sources), ADR 0013 (retrieval comparison)

## Context
ADR 0013 measured retrieval on gold v1, where 6 of the 8 core pages are French and the only Arabic
ones are the two birth certificate pages. The portal publishes every procedure page in Arabic under the
same id, so a real user's Arabic-script question can be answered by an Arabic page that v1 didn't index.
ADR 0013 planned gold v2 before Phase 2: add the Arabic versions of the passport, CIN, bulletin n°3 and
CNSS pages, relabel the gold documents, then add new Derja questions ([HUMAN]). This ADR is the "light"
step: the new pages and the relabeling only. The questions are unchanged.

## Options
How to make "the French page or its Arabic twin" count as the gold document:
1. `translation_of: <original>` on the Arabic source in `sources.yaml`. Scoring maps each document to its
   original, so the twins fill **one** gold slot. `gold_doc_ids` and the owner's spreadsheet stay untouched.
2. Alternatives written per question in `gold_doc_ids` (e.g. `doc_cin_01|doc_cin_04`) in
   `questions.jsonl` and in the spreadsheet: 35 rows, with the same mapping repeated on each.

Which pages:
1. The four ADR 0013 names: passport D1618, CIN first time D1309, bulletin n°3 residents D1705, CNSS D717.
2. Those four, plus the two other French core pages that also have twins: CIN renewal D1310 and
   bulletin n°3 abroad D1702.

The owner chose option 1 for the mapping and option 2 for the pages (2026-10-13).

## Experiment
Six new core sources, all `language: ar`, `extract_mode: recall`. The default extraction drops the
conditions and required documents of these pages, as for `doc_birth_01` (ADR 0006).

| New doc_id | Arabic page | translation_of | Chunks (tokens) | Original's chunks (tokens) |
|---|---|---|---|---|
| doc_passport_03 | D1618 | doc_passport_01 | 3 (934) | 3 (918) |
| doc_cin_03 | D1309 | doc_cin_02 | 3 (931) | 3 (838) |
| doc_cin_04 | D1310 | doc_cin_01 | 3 (894) | 2 (736) |
| doc_cnss_02 | D717 | doc_cnss_01 | 6 (2013) | 5 (1837) |
| doc_b3_03 | D1705 | doc_b3_01 | 2 (672) | 2 (614) |
| doc_b3_04 | D1702 | doc_b3_02 | 2 (691) | 2 (601) |

Before adding them, Claude checked the facts against the French pages: passport 25 / 80 TND,
4 photos, 15 days; CIN 3 TND, 3 photos, age 18; bulletin n°3 3 TND (3.300 TND abroad); the same CNSS
documents. After NFKC there are no presentation-form characters and no U+FFFD. The 51 v1 chunks are
unchanged: same text, title and section as the v1 index.

The validator enforces the mapping. `translation_of` must name a known core source of the same
procedure in the other language that is not itself a translation. `gold_doc_ids` must name the
original, not the translation.

`uv run tasks.py eval-retrieval --configs bm25,dense:bge_m3,hybrid:bge_m3,dense:qwen3_emb_0_6b,hybrid:qwen3_emb_0_6b --label gold_v2`.
The run used the same 43 in-scope questions as v1 (questions.jsonl sha256 35830b865fa8) and chunks
sha256 9471cc490cc4. Corpora: `core` has 14 documents (40 chunks), `full` has 33 (70 chunks), with the
same 19 distractors. The reranker was not run: ADR 0013 rejected it at ~80 s per question. Report:
`reports/2026-10-13_retrieval_gold_v2.md`. The v1 vs v2 comparison is paired on the same questions
(95% bootstrap). No judge runs: the Phase 0 baselines (B0 to B3, oracle documents) stay on v1.

## Results
**Full corpus** (the one ADR 0013's decision rests on). v2 next to the ADR 0013 (v1) numbers:

| Config | R@1 v1 → v2 | R@5 v1 → v2 | MRR v1 → v2 | MRR v2 − v1 (95% CI) |
|---|---|---|---|---|
| BM25 | 0.30 → 0.49 | 0.49 → 0.70 | 0.40 → 0.61 | +0.21 (+0.10 to +0.33) |
| **dense bge-m3** | **0.58 → 0.62** | **0.91 → 0.93** | **0.74 → 0.77** | +0.03 (−0.04 to +0.10) |
| hybrid bge-m3 | 0.42 → 0.60 | 0.77 → 0.88 | 0.60 → 0.77 | +0.17 (+0.08 to +0.27) |
| dense Qwen3-Embedding-0.6B | 0.42 → 0.51 | 0.73 → 0.86 | 0.60 → 0.69 | +0.10 (+0.00 to +0.20) |
| hybrid Qwen3 | 0.44 → 0.60 | 0.71 → 0.79 | 0.59 → 0.74 | +0.15 (+0.06 to +0.26) |

**Core corpus:**

| Config | R@1 v1 → v2 | R@5 v1 → v2 | MRR v1 → v2 | MRR v2 − v1 (95% CI) |
|---|---|---|---|---|
| BM25 | 0.35 → 0.53 | 0.51 → 0.72 | 0.44 → 0.65 | +0.21 (+0.10 to +0.32) |
| **dense bge-m3** | **0.77 → 0.72** | **0.98 → 0.93** | **0.88 → 0.84** | −0.03 (−0.10 to +0.04) |
| hybrid bge-m3 | 0.63 → 0.72 | 0.91 → 0.88 | 0.78 → 0.84 | +0.06 (+0.00 to +0.13) |
| dense Qwen3 | 0.53 → 0.56 | 0.88 → 0.88 | 0.72 → 0.74 | +0.01 (−0.06 to +0.10) |

Paired differences on v2, full corpus (MRR / R@1, 95% CI):

| A − B | MRR | R@1 |
|---|---|---|
| dense bge-m3 − BM25 | +0.16 (−0.00 to +0.32) | +0.13 (−0.07 to +0.33) |
| hybrid bge-m3 − dense bge-m3 | **+0.00 (−0.09 to +0.10)** (v1: −0.14) | −0.01 (−0.16 to +0.14) |
| dense Qwen3 − dense bge-m3 | −0.08 (−0.21 to +0.06) (v1: −0.14) | −0.10 (−0.29 to +0.08) |

By script of the question, full corpus, R@1 / MRR (v1 in brackets):

| Config | Arabic script (16) | Arabizi (15) | Mixed with French (12) |
|---|---|---|---|
| BM25 | 0.56 / 0.66 (0.12 / 0.16) | 0.33 / 0.49 (0.27 / 0.42) | 0.58 / 0.71 (0.58 / 0.71) |
| dense bge-m3 | 0.69 / 0.86 (0.53 / 0.72) | 0.57 / 0.71 (0.57 / 0.72) | 0.58 / 0.73 (0.67 / 0.79) |
| dense Qwen3 | 0.31 / 0.55 (0.00 / 0.27) | 0.67 / 0.81 (0.67 / 0.80) | 0.58 / 0.75 (0.67 / 0.79) |

Which version is found first (dense bge-m3, full corpus, the 31 questions on twinned procedures, first
gold chunk in the top 5): Arabic-script questions hit the **Arabic twin** 11 times out of 13 and the
original twice. Arabizi questions hit the **French original** 12 times out of 13. Mixed-French
questions hit the original 9 times out of 10. With French-only scoring on the v2 corpus, dense bge-m3
R@1 would be 0.43 (v1: 0.58): the twins take the first rank from the French pages.

By procedure, dense bge-m3, full, R@1 / MRR (v1 in brackets): CNSS 0.43 / 0.64 (0.14 / 0.48),
CIN 0.81 / 0.94 (0.69 / 0.88), passport 0.83 / 0.90 (0.92 / 0.92), bulletin n°3 0.44 / 0.76
(0.50 / 0.76), birth (no twin) 0.43 / 0.50 (0.43 / 0.52).

Effect of the distractors, dense bge-m3 MRR core → full: 0.84 → 0.77 (v1: 0.88 → 0.74).

Duplicates in what the model would see: for dense bge-m3, the top 5 chunks hold **both versions of the
same page** in 18 of 43 questions on the full corpus, and 23 of 43 on core.

Query latency (CPU, p50): bge-m3 102 ms and Qwen3 186 ms in this run (ADR 0013: 426 and 807 ms, which
included first-call warm-up on a busier machine). Treat latency as unchanged; the corpus is still tiny.

## Decision
- **Adopt gold v2 light** for retrieval evals: the six Arabic twins as core sources, scored through
  `translation_of`. From now on, `eval-retrieval` numbers compare only within v2 (chunks sha256
  9471cc490cc4).
- **Retrieval stays dense bge-m3 (ADR 0013).** It is still the best or tied on every metric. Its
  overall change from v1 is small and not significant (MRR +0.03, −0.04 to +0.10): its gain on
  Arabic-script questions (R@1 0.53 → 0.69) is offset by small losses elsewhere.
- **ADR 0013's reason against hybrid no longer holds, but its decision does.** BM25 now matches
  Arabic-script questions to the Arabic twins (R@1 0.12 → 0.56), so fusion no longer hurts:
  hybrid − dense is +0.00 MRR (−0.09 to +0.10) instead of −0.14. Hybrid doesn't beat dense either,
  so the simpler dense path stays.

## Consequences
- **Phase 2 should deduplicate twins in the context.** In 18 of 43 questions, two of the 5 chunks are
  the same page in two languages. Proposal to test in Phase 2: keep one version per original (the
  higher-ranked one) and fill the freed slots. It costs no extra model calls; measure it with
  `eval-retrieval` (distinct gold documents in the top 5) before adopting.
- Script decides the language of the page found: Arabic-script → Arabic page, Arabizi / French →
  French page. Citations will mix languages; the answer prompt (ADR 0012) must not assume French
  sources.
- The **reranker** was not re-run. With hybrid now level with dense, the reranker's +0.07 over hybrid
  (ADR 0013, not significant) might now beat dense. Under ADR 0013's rule, re-test only the cheap
  variants (rerank 5–10 candidates, max_length 256, GPU) and only with the owner's approval.
  Owner (2026-10-13): no re-test now. It stays an open option for later, **not a Phase 2 blocker**.
- CNSS is still the weakest procedure on the full corpus, though better (R@1 0.14 → 0.43); the procedure
  router (Phase 3) remains the planned fix. Passport loses a little (R@1 0.92 → 0.83): Arabic pages of
  other procedures now compete with it.
- The Phase 0 baselines and the judge runs stay on v1: B1's oracle documents come from
  `gold_doc_ids`, which did not change.
- **Still to do for full gold v2** ([HUMAN]): new Derja questions, then re-run `eval-retrieval`. These v2
  light numbers rest on the same 43 questions as v1.
