# 0005: Falcon-H1-3B-Instruct stands in for Falcon-H1 Arabic 3B

- **Status:** accepted (owner's decision)
- **Date:** 2026-10-10

## Context
Spec 3.1.2 picks Falcon-H1 Arabic 3B Instruct (Q4_K_M) as the local Arabic specialist. TII announced the
Falcon-H1 Arabic family (3B, 7B, 34B) in January 2026, but has not published the weights: the Hugging Face
blog post links only to a chat demo, no `tiiuae/*Arabic*` repo exists, and no community GGUF was found
(checked 2026-10-10).

## Options
1. `tiiuae/Falcon-H1-3B-Instruct-GGUF`: TII's general Falcon-H1 3B, same hybrid architecture; Arabic is one
   of its 18 languages.
2. Run only Qwen3.5 2B locally until the Arabic weights appear.
3. Another Arabic-capable model of 3B or less.

## Experiment
Checked the repo, license and file size with the Hugging Face API, and Ollama's engine version. After the
owner pulled both local models (2026-10-11), ran `uv run tasks.py test-live` and called each model directly
through Ollama's OpenAI-compatible endpoint (temperature 0, `OLLAMA_CONTEXT_LENGTH=4096`,
`OLLAMA_MAX_LOADED_MODELS=1`).

## Results
| Item | Value |
|---|---|
| Repo | `tiiuae/Falcon-H1-3B-Instruct-GGUF` (official TII) |
| File | `Falcon-H1-3B-Instruct-Q4_K_M.gguf`, 1.89 GB |
| License | Falcon LLM License (`falcon-llm-license`) |
| Ollama tag | `hf.co/tiiuae/Falcon-H1-3B-Instruct-GGUF:Q4_K_M` |
| Ollama support | Ollama 0.40.2 runs llama.cpp b11351; Falcon-H1 support was merged in llama.cpp PR #14534 (2025-07-09) |
| Loads | yes: Ollama reports architecture `falcon-h1`, 3.15B parameters |
| Chat template | the one embedded in the GGUF works: clean replies, no leaked template tokens ("Reply with the single word: ok" gave `ok`; a French question got a correct one-sentence French answer) |
| VRAM, 4096 context | Falcon-H1 3B 2.13 GB, Qwen3.5 2B 2.36 GB, both fully on the GPU (6 GB card, one model loaded at a time) |
| Latency once loaded | about 4–9 s per short answer for either model |

Qwen3.5 2B thinking-off (spec 3.1.2), checked with the same prompt:

| Request | Reasoning output | Completion tokens |
|---|---|---|
| with `reasoning_effort: none` (our config) | none | 2 |
| without it | 346 characters | 93 |

## Decision
Option 1, configured as `falcon_h1_3b` (not called "Arabic") in `configs/models.yaml`, used by B0_falcon and
B1_falcon.

## Consequences
- B0/B1 measure a general multilingual Falcon, not the Arabic specialist. Say so wherever the numbers appear.
- Switch to Falcon-H1 Arabic if TII publishes it, and re-run B0/B1.
