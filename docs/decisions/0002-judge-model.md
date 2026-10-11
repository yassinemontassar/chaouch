# 0002: Judge model is openai/gpt-oss-120b on Groq

- **Status:** superseded by ADR 0010 (Gemma 4 31B, 2026-10-11): Groq's 200K tokens/day cap
  is too small for `eval-full`. `groq_judge` stays configured for re-runs.
- **Date:** 2026-10-10

## Context
The baselines are scored by an LLM judge (correctness, faithfulness, dialect). A judge tends to favour
answers from its own model family, so it should not share a provider or family with any system it grades
(spec 8.2). The systems are a local Qwen model, a local Falcon model, Gemini Flash (B2) and ALLaM on Groq (B3).

## Options
1. Gemini Flash: strong, but it would grade its own answers in B2.
2. A Qwen model on Groq (`qwen/qwen3.8-27b`): same family as the local Qwen model.
3. `openai/gpt-oss-120b` on Groq: a different family from every evaluated system.

The model planned earlier, `llama-3.3-70b-versatile`, is no longer served by Groq (404 on 2026-10-10).

## Experiment
Listed Groq's models with our key on 2026-10-10, then ran the three judge prompts on made-up text.

## Results
| Check | Result |
|---|---|
| JSON mode | valid JSON on every call |
| Dialect, Derja sentence | 5 (`derja`) |
| Dialect, MSA sentence | 1 (`msa`) |
| Correctness, 1 of 2 facts present | 0.5 |
| Faithfulness, 1 of 2 claims supported | 0.5 |

## Decision
Use `openai/gpt-oss-120b` (`groq_judge` in `configs/models.yaml`). The runner still flags self-judging
(same model family), and a test checks that the default judge grades no configured system with its own family.

## Consequences
- Judge calls and B3 (ALLaM, also on Groq) share the Groq free-tier quota. The eval cache makes re-runs free.
- These are sanity checks, not calibration. Calibration was done in ADR 0009 (v1 prompts) and ADR 0010.
