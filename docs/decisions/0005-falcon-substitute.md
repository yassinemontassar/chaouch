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
Checked the repo, license and file size with the Hugging Face API, and Ollama's engine version. Not
downloaded or run yet.

## Results
| Item | Value |
|---|---|
| Repo | `tiiuae/Falcon-H1-3B-Instruct-GGUF` (official TII) |
| File | `Falcon-H1-3B-Instruct-Q4_K_M.gguf`, 1.89 GB |
| License | Falcon LLM License (`falcon-llm-license`) |
| Ollama tag | `hf.co/tiiuae/Falcon-H1-3B-Instruct-GGUF:Q4_K_M` |
| Ollama support | Ollama 0.40.2 runs llama.cpp b11351; Falcon-H1 support was merged in llama.cpp PR #14534 (2025-07-09) |

## Decision
Option 1, configured as `falcon_h1_3b` (not called "Arabic") in `configs/models.yaml`, used by B0_falcon and
B1_falcon.

## Consequences
- B0/B1 measure a general multilingual Falcon, not the Arabic specialist. Say so wherever the numbers appear.
- Still to verify after the download: the model loads in Ollama, the chat template works, and it fits the
  VRAM budget with a 4096 context.
- Switch to Falcon-H1 Arabic if TII publishes it, and re-run B0/B1.
