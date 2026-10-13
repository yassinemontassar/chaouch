# Retrieval eval, 2026-10-13

Gold set: 43 in-scope questions (questions.jsonl sha256 35830b865fa8). Chunks: sha256 9471cc490cc4.
R@k = share of the gold documents found in the top k **chunks** (what the LLM sees); MRR = mean of 1 / rank of the first chunk from a gold document. A document and its translation (`translation_of` in sources.yaml) count as one gold document. In brackets: 95% bootstrap intervals over questions.

## Corpus `core`: 14 documents, 40 chunks

| Config | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| bm25 | 0.53 (0.40–0.67) | 0.70 (0.56–0.84) | 0.72 (0.58–0.86) | 0.65 (0.52–0.78) |
| dense:bge_m3 | 0.72 (0.59–0.84) | 0.93 (0.84–1.00) | 0.93 (0.84–1.00) | 0.84 (0.75–0.93) |
| hybrid:bge_m3 | 0.72 (0.59–0.84) | 0.88 (0.79–0.98) | 0.88 (0.79–0.98) | 0.84 (0.74–0.92) |
| dense:qwen3_emb_0_6b | 0.56 (0.42–0.70) | 0.86 (0.74–0.95) | 0.88 (0.79–0.98) | 0.74 (0.63–0.83) |
| hybrid:qwen3_emb_0_6b | 0.65 (0.51–0.78) | 0.79 (0.67–0.91) | 0.84 (0.72–0.93) | 0.77 (0.66–0.88) |

By script (R@1 / MRR):

| Config | arabic (n=16) | arabizi (n=15) | mixed_fr (n=12) |
|---|---|---|---|
| bm25 | 0.56 / 0.68 | 0.33 / 0.50 | 0.75 / 0.79 |
| dense:bge_m3 | 0.81 / 0.94 | 0.60 / 0.77 | 0.75 / 0.82 |
| hybrid:bge_m3 | 0.81 / 0.92 | 0.60 / 0.78 | 0.75 / 0.81 |
| dense:qwen3_emb_0_6b | 0.31 / 0.59 | 0.67 / 0.81 | 0.75 / 0.84 |
| hybrid:qwen3_emb_0_6b | 0.56 / 0.71 | 0.60 / 0.78 | 0.83 / 0.85 |

By doc language (R@1 / MRR):

| Config | ar (n=7) | ar+fr (n=36) |
|---|---|---|
| bm25 | 0.29 / 0.36 | 0.58 / 0.71 |
| dense:bge_m3 | 0.57 / 0.61 | 0.75 / 0.89 |
| hybrid:bge_m3 | 0.43 / 0.48 | 0.78 / 0.91 |
| dense:qwen3_emb_0_6b | 0.29 / 0.53 | 0.61 / 0.78 |
| hybrid:qwen3_emb_0_6b | 0.43 / 0.53 | 0.69 / 0.82 |

By procedure (R@1 / MRR):

| Config | birth_certificate (n=7) | cin (n=8) | cnss_registration (n=7) | criminal_record (n=9) | passport_renewal (n=12) |
|---|---|---|---|---|---|
| bm25 | 0.29 / 0.36 | 0.62 / 0.82 | 1.00 / 1.00 | 0.56 / 0.83 | 0.33 / 0.36 |
| dense:bge_m3 | 0.57 / 0.61 | 0.88 / 1.00 | 0.71 / 0.83 | 0.44 / 0.76 | 0.92 / 0.94 |
| hybrid:bge_m3 | 0.43 / 0.48 | 0.75 / 0.94 | 1.00 / 1.00 | 0.56 / 0.83 | 0.83 / 0.89 |
| dense:qwen3_emb_0_6b | 0.29 / 0.53 | 0.75 / 0.92 | 1.00 / 1.00 | 0.44 / 0.74 | 0.42 / 0.58 |
| hybrid:qwen3_emb_0_6b | 0.43 / 0.53 | 0.75 / 0.90 | 1.00 / 1.00 | 0.67 / 0.89 | 0.50 / 0.61 |

Paired differences (A − B on the same questions, 95% paired bootstrap):

| A | B | Metric | A − B | 95% CI |
|---|---|---|---|---|
| dense:bge_m3 | bm25 | MRR | +0.20 | +0.04 to +0.35 |
| dense:bge_m3 | bm25 | R@1 | +0.19 | +0.00 to +0.40 |
| hybrid:bge_m3 | bm25 | MRR | +0.19 | +0.09 to +0.30 |
| hybrid:bge_m3 | bm25 | R@1 | +0.19 | +0.05 to +0.33 |
| dense:qwen3_emb_0_6b | bm25 | MRR | +0.09 | -0.02 to +0.21 |
| dense:qwen3_emb_0_6b | bm25 | R@1 | +0.02 | -0.14 to +0.19 |
| hybrid:qwen3_emb_0_6b | bm25 | MRR | +0.12 | +0.05 to +0.21 |
| hybrid:qwen3_emb_0_6b | bm25 | R@1 | +0.12 | +0.02 to +0.21 |
| hybrid:bge_m3 | dense:bge_m3 | MRR | -0.01 | -0.10 to +0.08 |
| hybrid:bge_m3 | dense:bge_m3 | R@1 | +0.00 | -0.14 to +0.14 |
| hybrid:qwen3_emb_0_6b | dense:qwen3_emb_0_6b | MRR | +0.04 | -0.04 to +0.11 |
| hybrid:qwen3_emb_0_6b | dense:qwen3_emb_0_6b | R@1 | +0.09 | -0.02 to +0.21 |
| dense:qwen3_emb_0_6b | dense:bge_m3 | MRR | -0.11 | -0.23 to +0.02 |
| dense:qwen3_emb_0_6b | dense:bge_m3 | R@1 | -0.16 | -0.35 to +0.02 |
| hybrid:qwen3_emb_0_6b | hybrid:bge_m3 | MRR | -0.06 | -0.16 to +0.04 |
| hybrid:qwen3_emb_0_6b | hybrid:bge_m3 | R@1 | -0.07 | -0.21 to +0.07 |

## Corpus `full`: 33 documents, 70 chunks

| Config | R@1 | R@3 | R@5 | MRR |
|---|---|---|---|---|
| bm25 | 0.49 (0.35–0.63) | 0.67 (0.54–0.81) | 0.70 (0.56–0.84) | 0.61 (0.48–0.74) |
| dense:bge_m3 | 0.62 (0.48–0.76) | 0.88 (0.77–0.98) | 0.93 (0.84–1.00) | 0.77 (0.67–0.87) |
| hybrid:bge_m3 | 0.60 (0.47–0.73) | 0.88 (0.79–0.98) | 0.88 (0.79–0.98) | 0.77 (0.68–0.86) |
| dense:qwen3_emb_0_6b | 0.51 (0.36–0.65) | 0.79 (0.67–0.91) | 0.86 (0.74–0.95) | 0.69 (0.58–0.80) |
| hybrid:qwen3_emb_0_6b | 0.60 (0.47–0.74) | 0.79 (0.67–0.91) | 0.79 (0.67–0.91) | 0.74 (0.62–0.85) |

By script (R@1 / MRR):

| Config | arabic (n=16) | arabizi (n=15) | mixed_fr (n=12) |
|---|---|---|---|
| bm25 | 0.56 / 0.66 | 0.33 / 0.49 | 0.58 / 0.71 |
| dense:bge_m3 | 0.69 / 0.86 | 0.57 / 0.71 | 0.58 / 0.73 |
| hybrid:bge_m3 | 0.69 / 0.85 | 0.53 / 0.73 | 0.58 / 0.72 |
| dense:qwen3_emb_0_6b | 0.31 / 0.55 | 0.67 / 0.81 | 0.58 / 0.75 |
| hybrid:qwen3_emb_0_6b | 0.56 / 0.68 | 0.60 / 0.78 | 0.67 / 0.76 |

By doc language (R@1 / MRR):

| Config | ar (n=7) | ar+fr (n=36) |
|---|---|---|
| bm25 | 0.29 / 0.33 | 0.53 / 0.67 |
| dense:bge_m3 | 0.43 / 0.50 | 0.65 / 0.82 |
| hybrid:bge_m3 | 0.29 / 0.40 | 0.67 / 0.85 |
| dense:qwen3_emb_0_6b | 0.29 / 0.49 | 0.56 / 0.73 |
| hybrid:qwen3_emb_0_6b | 0.43 / 0.51 | 0.64 / 0.78 |

By procedure (R@1 / MRR):

| Config | birth_certificate (n=7) | cin (n=8) | cnss_registration (n=7) | criminal_record (n=9) | passport_renewal (n=12) |
|---|---|---|---|---|---|
| bm25 | 0.29 / 0.33 | 0.62 / 0.80 | 0.71 / 0.86 | 0.56 / 0.83 | 0.33 / 0.35 |
| dense:bge_m3 | 0.43 / 0.50 | 0.81 / 0.94 | 0.43 / 0.64 | 0.44 / 0.76 | 0.83 / 0.90 |
| hybrid:bge_m3 | 0.29 / 0.40 | 0.75 / 0.94 | 0.57 / 0.79 | 0.56 / 0.81 | 0.75 / 0.85 |
| dense:qwen3_emb_0_6b | 0.29 / 0.49 | 0.75 / 0.91 | 0.71 / 0.83 | 0.44 / 0.74 | 0.42 / 0.56 |
| hybrid:qwen3_emb_0_6b | 0.43 / 0.51 | 0.75 / 0.89 | 0.71 / 0.86 | 0.67 / 0.89 | 0.50 / 0.59 |

Paired differences (A − B on the same questions, 95% paired bootstrap):

| A | B | Metric | A − B | 95% CI |
|---|---|---|---|---|
| dense:bge_m3 | bm25 | MRR | +0.16 | -0.00 to +0.32 |
| dense:bge_m3 | bm25 | R@1 | +0.13 | -0.07 to +0.33 |
| hybrid:bge_m3 | bm25 | MRR | +0.16 | +0.06 to +0.28 |
| hybrid:bge_m3 | bm25 | R@1 | +0.12 | +0.00 to +0.26 |
| dense:qwen3_emb_0_6b | bm25 | MRR | +0.08 | -0.03 to +0.20 |
| dense:qwen3_emb_0_6b | bm25 | R@1 | +0.02 | -0.14 to +0.19 |
| hybrid:qwen3_emb_0_6b | bm25 | MRR | +0.12 | +0.05 to +0.21 |
| hybrid:qwen3_emb_0_6b | bm25 | R@1 | +0.12 | +0.02 to +0.21 |
| hybrid:bge_m3 | dense:bge_m3 | MRR | +0.00 | -0.09 to +0.10 |
| hybrid:bge_m3 | dense:bge_m3 | R@1 | -0.01 | -0.16 to +0.14 |
| hybrid:qwen3_emb_0_6b | dense:qwen3_emb_0_6b | MRR | +0.04 | -0.04 to +0.12 |
| hybrid:qwen3_emb_0_6b | dense:qwen3_emb_0_6b | R@1 | +0.09 | -0.02 to +0.21 |
| dense:qwen3_emb_0_6b | dense:bge_m3 | MRR | -0.08 | -0.21 to +0.06 |
| dense:qwen3_emb_0_6b | dense:bge_m3 | R@1 | -0.10 | -0.29 to +0.08 |
| hybrid:qwen3_emb_0_6b | hybrid:bge_m3 | MRR | -0.04 | -0.13 to +0.07 |
| hybrid:qwen3_emb_0_6b | hybrid:bge_m3 | R@1 | +0.00 | -0.12 to +0.14 |

## Latency per stage (CPU)

| Stage | p50 ms | p95 ms |
|---|---|---|
| embed query (bge_m3) | 102 | 150 |
| dense search (pgvector) | 2 | 2 |
| embed query (qwen3_emb_0_6b) | 186 | 261 |
| bm25 | 0 | 0 |

Settings: candidates 20 per retriever, RRF k 60, rerank 20 with BAAI/bge-reranker-v2-m3 (max_length 512), top_k 5, device cpu.
