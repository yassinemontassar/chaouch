# 0011: Main local model is Falcon-H1 3B Instruct

- **Status:** accepted
- **Date:** 2026-10-11

## Context
Chaouch runs a local model on a 6 GB laptop GPU. Phase 0 carried two candidates (ADR 0005): Qwen3.5 2B
and Falcon-H1 3B Instruct, both Q4 GGUF via Ollama. The rest of the project (generation in Phase 2, Derja
work and fine-tuning in Phase 4) builds on one of them.

## Options
1. Falcon-H1 3B Instruct (`hf.co/tiiuae/Falcon-H1-3B-Instruct-GGUF:Q4_K_M`)
2. Qwen3.5 2B (`qwen3.5:2b`, thinking off)

## Experiment
`uv run tasks.py eval-full` on gold set v1 (43 scored in-scope questions), 2026-10-11, commit 8234c6f,
judge Gemma 4 31B with `correctness_v2` / `dialect_v2` (ADR 0010). Order of criteria from
`docs/workflows.md` §4: B1 first (model + documents, closest to real use), then latency, then B0.

## Results
| | Falcon-H1 3B | Qwen3.5 2B |
|---|---|---|
| B1 correctness | **0.67** | 0.46 |
| B1 faithfulness | **0.83** (40 of 43 scored) | 0.72 |
| B1 dialect (1–5) | 1.16 | 1.02 |
| B1 correctness: arabic / arabizi / mixed_fr | **0.82** / 0.53 / 0.65 | 0.62 / 0.30 / 0.46 |
| B1 latency p50 / p95 | 9.2 s / 15.4 s | **4.3 s / 11.1 s** |
| B0 correctness | 0.09 | 0.07 |

RTX 3050 Laptop (6 GB), Ollama, 4096-token context, oracle documents up to 2500 tokens.

## Decision
Falcon-H1 3B is the main local model: with documents it gets 21 points more correctness and 11 more
faithfulness, and it is ahead on every script. Qwen3.5 2B stays configured as the fallback.

## Consequences
- **Latency** is twice Qwen's (p50 9.2 s vs 4.3 s). Look into it in Phase 2: answer length (Falcon writes
  long, list-style answers), context size, and streaming the answer.
- **Dialect** is ~1.2: Falcon answers in formal Arabic, like every system except Gemini (3.8). This is the
  target of the Phase 4 Derja work.
- **Arabizi** is its weak script (0.53 vs 0.82 on Arabic): the target of the Phase 4 normalizer.
- Still to check before Phase 4: QLoRA fine-tuning and GGUF export for Falcon-H1's hybrid
  (attention + Mamba) architecture (`docs/workflows.md` §4, criterion 3). If it isn't supported, revisit
  this choice with the fallback.
- Falcon echoed the question in 3 of 43 B0 answers (ADR 0009 echo rule); Qwen produced none.
