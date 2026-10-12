# Retrieval eval, 2026-10-12

Gold set: 43 in-scope questions (questions.jsonl sha256 35830b865fa8). Chunks: sha256 2081d39596d8.
R@k = share of the gold documents found in the top k **chunks** (what the LLM sees); MRR = mean of 1 / rank of the first chunk from a gold document. In brackets: 95% bootstrap intervals over questions.

## Corpus `core`: 8 documents, 21 chunks

| Config | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| bm25 | 0.35 (0.22–0.49) | 0.49 (0.35–0.63) | 0.51 (0.37–0.65) | 0.44 (0.31–0.58) |
| dense:bge_m3 | 0.77 (0.65–0.87) | 0.92 (0.83–0.99) | 0.98 (0.93–1.00) | 0.88 (0.79–0.95) |
| hybrid:bge_m3 | 0.63 (0.49–0.76) | 0.88 (0.79–0.98) | 0.91 (0.81–0.98) | 0.78 (0.67–0.87) |
| dense:qwen3_emb_0_6b | 0.53 (0.40–0.69) | 0.81 (0.70–0.93) | 0.88 (0.77–0.98) | 0.72 (0.62–0.82) |
| hybrid:qwen3_emb_0_6b | 0.56 (0.42–0.71) | 0.79 (0.67–0.91) | 0.81 (0.70–0.93) | 0.71 (0.60–0.82) |

By script (R@1 / MRR):

| Config | arabic (n=16) | arabizi (n=15) | mixed_fr (n=12) |
|---|---|---|---|
| bm25 | 0.12 / 0.19 | 0.27 / 0.43 | 0.75 / 0.79 |
| dense:bge_m3 | 0.75 / 0.88 | 0.73 / 0.85 | 0.83 / 0.90 |
| hybrid:bge_m3 | 0.56 / 0.75 | 0.60 / 0.78 | 0.75 / 0.80 |
| dense:qwen3_emb_0_6b | 0.19 / 0.52 | 0.67 / 0.80 | 0.83 / 0.89 |
| hybrid:qwen3_emb_0_6b | 0.31 / 0.55 | 0.60 / 0.77 | 0.83 / 0.84 |

By doc language (R@1 / MRR):

| Config | ar (n=7) | fr (n=36) |
|---|---|---|
| bm25 | 0.29 / 0.36 | 0.36 / 0.46 |
| dense:bge_m3 | 0.57 / 0.68 | 0.81 / 0.91 |
| hybrid:bge_m3 | 0.43 / 0.48 | 0.67 / 0.83 |
| dense:qwen3_emb_0_6b | 0.29 / 0.55 | 0.58 / 0.75 |
| hybrid:qwen3_emb_0_6b | 0.43 / 0.53 | 0.58 / 0.74 |

By procedure (R@1 / MRR):

| Config | birth_certificate (n=7) | cin (n=8) | cnss_registration (n=7) | criminal_record (n=9) | passport_renewal (n=12) |
|---|---|---|---|---|---|
| bm25 | 0.29 / 0.36 | 0.44 / 0.54 | 0.43 / 0.43 | 0.28 / 0.56 | 0.33 / 0.35 |
| dense:bge_m3 | 0.57 / 0.68 | 0.88 / 1.00 | 0.86 / 0.90 | 0.56 / 0.81 | 0.92 / 0.94 |
| hybrid:bge_m3 | 0.43 / 0.48 | 0.75 / 0.94 | 0.57 / 0.71 | 0.44 / 0.78 | 0.83 / 0.87 |
| dense:qwen3_emb_0_6b | 0.29 / 0.55 | 0.75 / 0.94 | 0.57 / 0.69 | 0.44 / 0.76 | 0.58 / 0.67 |
| hybrid:qwen3_emb_0_6b | 0.43 / 0.53 | 0.75 / 0.94 | 0.57 / 0.66 | 0.44 / 0.76 | 0.58 / 0.66 |

Paired differences (A − B on the same questions, 95% paired bootstrap):

| A | B | Metric | A − B | 95% CI |
|---|---|---|---|---|
| dense:bge_m3 | bm25 | MRR | +0.43 | +0.29 to +0.57 |
| dense:bge_m3 | bm25 | R@1 | +0.42 | +0.26 to +0.58 |
| hybrid:bge_m3 | bm25 | MRR | +0.33 | +0.21 to +0.46 |
| hybrid:bge_m3 | bm25 | R@1 | +0.28 | +0.13 to +0.43 |
| dense:qwen3_emb_0_6b | bm25 | MRR | +0.28 | +0.16 to +0.40 |
| dense:qwen3_emb_0_6b | bm25 | R@1 | +0.19 | +0.05 to +0.34 |
| hybrid:qwen3_emb_0_6b | bm25 | MRR | +0.27 | +0.16 to +0.38 |
| hybrid:qwen3_emb_0_6b | bm25 | R@1 | +0.21 | +0.10 to +0.33 |
| hybrid:bge_m3 | dense:bge_m3 | MRR | -0.10 | -0.17 to -0.03 |
| hybrid:bge_m3 | dense:bge_m3 | R@1 | -0.14 | -0.26 to -0.05 |
| hybrid:qwen3_emb_0_6b | dense:qwen3_emb_0_6b | MRR | -0.01 | -0.08 to +0.05 |
| hybrid:qwen3_emb_0_6b | dense:qwen3_emb_0_6b | R@1 | +0.02 | -0.07 to +0.12 |
| dense:qwen3_emb_0_6b | dense:bge_m3 | MRR | -0.15 | -0.28 to -0.03 |
| dense:qwen3_emb_0_6b | dense:bge_m3 | R@1 | -0.23 | -0.42 to -0.05 |
| hybrid:qwen3_emb_0_6b | hybrid:bge_m3 | MRR | -0.07 | -0.17 to +0.04 |
| hybrid:qwen3_emb_0_6b | hybrid:bge_m3 | R@1 | -0.07 | -0.23 to +0.07 |

## Corpus `full`: 27 documents, 51 chunks

| Config | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| bm25 | 0.30 (0.17–0.44) | 0.47 (0.33–0.63) | 0.49 (0.35–0.63) | 0.40 (0.28–0.54) |
| dense:bge_m3 | 0.58 (0.44–0.73) | 0.85 (0.73–0.94) | 0.91 (0.81–0.98) | 0.74 (0.64–0.84) |
| hybrid:bge_m3 | 0.42 (0.28–0.56) | 0.73 (0.60–0.86) | 0.77 (0.65–0.88) | 0.60 (0.49–0.71) |
| dense:qwen3_emb_0_6b | 0.42 (0.28–0.57) | 0.70 (0.56–0.83) | 0.73 (0.60–0.86) | 0.60 (0.48–0.72) |
| hybrid:qwen3_emb_0_6b | 0.44 (0.30–0.59) | 0.65 (0.51–0.79) | 0.71 (0.57–0.84) | 0.59 (0.47–0.71) |

By script (R@1 / MRR):

| Config | arabic (n=16) | arabizi (n=15) | mixed_fr (n=12) |
|---|---|---|---|
| bm25 | 0.12 / 0.16 | 0.27 / 0.42 | 0.58 / 0.71 |
| dense:bge_m3 | 0.53 / 0.72 | 0.57 / 0.72 | 0.67 / 0.79 |
| hybrid:bge_m3 | 0.25 / 0.45 | 0.47 / 0.66 | 0.58 / 0.72 |
| dense:qwen3_emb_0_6b | 0.00 / 0.27 | 0.67 / 0.80 | 0.67 / 0.79 |
| hybrid:qwen3_emb_0_6b | 0.12 / 0.28 | 0.60 / 0.77 | 0.67 / 0.76 |

By doc language (R@1 / MRR):

| Config | ar (n=7) | fr (n=36) |
|---|---|---|
| bm25 | 0.29 / 0.33 | 0.31 / 0.42 |
| dense:bge_m3 | 0.43 / 0.52 | 0.61 / 0.78 |
| hybrid:bge_m3 | 0.29 / 0.39 | 0.44 / 0.64 |
| dense:qwen3_emb_0_6b | 0.29 / 0.51 | 0.44 / 0.61 |
| hybrid:qwen3_emb_0_6b | 0.43 / 0.51 | 0.44 / 0.60 |

By procedure (R@1 / MRR):

| Config | birth_certificate (n=7) | cin (n=8) | cnss_registration (n=7) | criminal_record (n=9) | passport_renewal (n=12) |
|---|---|---|---|---|---|
| bm25 | 0.29 / 0.33 | 0.44 / 0.53 | 0.14 / 0.29 | 0.28 / 0.53 | 0.33 / 0.34 |
| dense:bge_m3 | 0.43 / 0.52 | 0.69 / 0.88 | 0.14 / 0.48 | 0.50 / 0.76 | 0.92 / 0.92 |
| hybrid:bge_m3 | 0.29 / 0.39 | 0.44 / 0.67 | 0.14 / 0.37 | 0.28 / 0.63 | 0.75 / 0.79 |
| dense:qwen3_emb_0_6b | 0.29 / 0.51 | 0.56 / 0.73 | 0.14 / 0.32 | 0.39 / 0.70 | 0.58 / 0.64 |
| hybrid:qwen3_emb_0_6b | 0.43 / 0.51 | 0.56 / 0.70 | 0.14 / 0.34 | 0.39 / 0.68 | 0.58 / 0.63 |

Paired differences (A − B on the same questions, 95% paired bootstrap):

| A | B | Metric | A − B | 95% CI |
|---|---|---|---|---|
| dense:bge_m3 | bm25 | MRR | +0.34 | +0.18 to +0.49 |
| dense:bge_m3 | bm25 | R@1 | +0.28 | +0.09 to +0.45 |
| hybrid:bge_m3 | bm25 | MRR | +0.20 | +0.10 to +0.30 |
| hybrid:bge_m3 | bm25 | R@1 | +0.12 | +0.00 to +0.23 |
| dense:qwen3_emb_0_6b | bm25 | MRR | +0.19 | +0.09 to +0.31 |
| dense:qwen3_emb_0_6b | bm25 | R@1 | +0.12 | +0.00 to +0.26 |
| hybrid:qwen3_emb_0_6b | bm25 | MRR | +0.18 | +0.10 to +0.28 |
| hybrid:qwen3_emb_0_6b | bm25 | R@1 | +0.14 | +0.05 to +0.26 |
| hybrid:bge_m3 | dense:bge_m3 | MRR | -0.14 | -0.24 to -0.04 |
| hybrid:bge_m3 | dense:bge_m3 | R@1 | -0.16 | -0.31 to -0.02 |
| hybrid:qwen3_emb_0_6b | dense:qwen3_emb_0_6b | MRR | -0.01 | -0.09 to +0.05 |
| hybrid:qwen3_emb_0_6b | dense:qwen3_emb_0_6b | R@1 | +0.02 | -0.07 to +0.12 |
| dense:qwen3_emb_0_6b | dense:bge_m3 | MRR | -0.14 | -0.27 to -0.01 |
| dense:qwen3_emb_0_6b | dense:bge_m3 | R@1 | -0.16 | -0.34 to +0.01 |
| hybrid:qwen3_emb_0_6b | hybrid:bge_m3 | MRR | -0.02 | -0.11 to +0.08 |
| hybrid:qwen3_emb_0_6b | hybrid:bge_m3 | R@1 | +0.02 | -0.09 to +0.14 |

## Latency per stage (CPU)

| Stage | p50 ms | p95 ms |
|---|---|---|
| embed query (bge_m3) | 352 | 527 |
| dense search (pgvector) | 3 | 4 |
| embed query (qwen3_emb_0_6b) | 809 | 1254 |
| bm25 | 0 | 0 |

Settings: candidates 20 per retriever, RRF k 60, rerank 20 with BAAI/bge-reranker-v2-m3 (max_length 512), top_k 5, device cpu.
