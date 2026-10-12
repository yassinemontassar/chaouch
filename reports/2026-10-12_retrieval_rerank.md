# Retrieval eval, 2026-10-12

Gold set: 43 in-scope questions (questions.jsonl sha256 35830b865fa8). Chunks: sha256 2081d39596d8.
R@k = share of the gold documents found in the top k **chunks** (what the LLM sees); MRR = mean of 1 / rank of the first chunk from a gold document. In brackets: 95% bootstrap intervals over questions.

## Corpus `full`: 27 documents, 51 chunks

| Config | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| bm25 | 0.30 (0.17–0.44) | 0.47 (0.33–0.63) | 0.49 (0.35–0.63) | 0.40 (0.28–0.54) |
| dense:bge_m3 | 0.58 (0.44–0.73) | 0.85 (0.73–0.94) | 0.91 (0.81–0.98) | 0.74 (0.64–0.84) |
| hybrid:bge_m3 | 0.42 (0.28–0.56) | 0.73 (0.60–0.86) | 0.77 (0.65–0.88) | 0.60 (0.49–0.71) |
| hybrid_rerank:bge_m3 | 0.51 (0.37–0.65) | 0.73 (0.60–0.86) | 0.87 (0.77–0.95) | 0.67 (0.56–0.78) |

By script (R@1 / MRR):

| Config | arabic (n=16) | arabizi (n=15) | mixed_fr (n=12) |
|---|---|---|---|
| bm25 | 0.12 / 0.16 | 0.27 / 0.42 | 0.58 / 0.71 |
| dense:bge_m3 | 0.53 / 0.72 | 0.57 / 0.72 | 0.67 / 0.79 |
| hybrid:bge_m3 | 0.25 / 0.45 | 0.47 / 0.66 | 0.58 / 0.72 |
| hybrid_rerank:bge_m3 | 0.38 / 0.52 | 0.53 / 0.74 | 0.67 / 0.78 |

By doc language (R@1 / MRR):

| Config | ar (n=7) | fr (n=36) |
|---|---|---|
| bm25 | 0.29 / 0.33 | 0.31 / 0.42 |
| dense:bge_m3 | 0.43 / 0.52 | 0.61 / 0.78 |
| hybrid:bge_m3 | 0.29 / 0.39 | 0.44 / 0.64 |
| hybrid_rerank:bge_m3 | 0.43 / 0.56 | 0.53 / 0.69 |

By procedure (R@1 / MRR):

| Config | birth_certificate (n=7) | cin (n=8) | cnss_registration (n=7) | criminal_record (n=9) | passport_renewal (n=12) |
|---|---|---|---|---|---|
| bm25 | 0.29 / 0.33 | 0.44 / 0.53 | 0.14 / 0.29 | 0.28 / 0.53 | 0.33 / 0.34 |
| dense:bge_m3 | 0.43 / 0.52 | 0.69 / 0.88 | 0.14 / 0.48 | 0.50 / 0.76 | 0.92 / 0.92 |
| hybrid:bge_m3 | 0.29 / 0.39 | 0.44 / 0.67 | 0.14 / 0.37 | 0.28 / 0.63 | 0.75 / 0.79 |
| hybrid_rerank:bge_m3 | 0.43 / 0.56 | 0.56 / 0.71 | 0.29 / 0.54 | 0.50 / 0.76 | 0.67 / 0.72 |

Paired differences (A − B on the same questions, 95% paired bootstrap):

| A | B | Metric | A − B | 95% CI |
|---|---|---|---|---|
| dense:bge_m3 | bm25 | MRR | +0.34 | +0.18 to +0.49 |
| dense:bge_m3 | bm25 | R@1 | +0.28 | +0.09 to +0.45 |
| hybrid:bge_m3 | bm25 | MRR | +0.20 | +0.10 to +0.30 |
| hybrid:bge_m3 | bm25 | R@1 | +0.12 | +0.00 to +0.23 |
| hybrid_rerank:bge_m3 | bm25 | MRR | +0.27 | +0.15 to +0.38 |
| hybrid_rerank:bge_m3 | bm25 | R@1 | +0.21 | +0.07 to +0.35 |
| hybrid:bge_m3 | dense:bge_m3 | MRR | -0.14 | -0.24 to -0.04 |
| hybrid:bge_m3 | dense:bge_m3 | R@1 | -0.16 | -0.31 to -0.02 |
| hybrid_rerank:bge_m3 | hybrid:bge_m3 | MRR | +0.07 | -0.04 to +0.17 |
| hybrid_rerank:bge_m3 | hybrid:bge_m3 | R@1 | +0.09 | -0.05 to +0.23 |

## Latency per stage (CPU)

| Stage | p50 ms | p95 ms |
|---|---|---|
| embed query (bge_m3) | 355 | 547 |
| dense search (pgvector) | 3 | 5 |
| bm25 | 0 | 5 |
| fuse + rerank 20 | 79563 | 99575 |

Settings: candidates 20 per retriever, RRF k 60, rerank 20 with BAAI/bge-reranker-v2-m3 (max_length 512), top_k 5, device cpu.
