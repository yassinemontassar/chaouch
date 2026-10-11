# 0008: B2 uses Gemini 3.5 Flash-Lite

- **Status:** accepted (owner's decision)
- **Date:** 2026-10-11

## Context
B2 was `gemini-2.5-flash`. Its free tier allows only 20 requests per day (the 429 names
`GenerateRequestsPerDayPerProjectPerModel`, limit 20), so one smoke run used a whole day and B2 on the 43
in-scope questions would take 3 days. Every re-run after a prompt change would cost days again (ADR 0007).

## Options
1. Keep `gemini-2.5-flash` and run B2 over several days.
2. Another Gemini model with a larger free daily quota.
3. `qwen/qwen3.8-27b` on Groq: 1,000 requests/day and 8,000 tokens/min (response headers), 200K tokens/day
   (Groq docs), 131K context; same family as the local Qwen model.

## Experiment
Listed the models on the owner's Gemini key and sent one short Derja question to each candidate
(2026-10-11). The Gemini API does not report free-tier limits; the owner read them from the AI Studio
console (aistudio.google.com/rate-limit) on 2026-10-11.

## Results
| Model | RPM | RPD | TPM | One Derja question |
|---|---|---|---|---|
| gemini-2.5-flash | 5 | 20 | | answered |
| **gemini-3.5-flash-lite** | **15** | **500** | 250K | answered (in MSA) |
| gemini-3.5-flash | | | | answered (in MSA) |
| gemini-3.1-flash-lite | | | | 503, "high demand" |
| gemini-2.5-flash-lite | | | | 404, "no longer available to new users" |
| gemma-4-31b-it | | 14.4K | 16K | 500, internal error |
| qwen/qwen3.8-27b (Groq) | 30 | 1,000 | 8K | answered (in MSA) |

Blank cells were not checked. Gemini limits are from the owner's console; Groq limits from response
headers and Groq's docs.

## Decision
Option 2: `gemini-3.5-flash-lite` (`gemini_flash_lite` in `configs/models.yaml`, rpm 15, rpd 500). B2 on the
full gold set fits in one day, B2 stays Gemini Flash-class as the spec intended, and Gemini is a different
family from the judge and from every other system.

## Consequences
- The 14 B2 answers cached from `gemini-2.5-flash` are not reused; B2 starts fresh.
- A Flash-Lite model is weaker than Flash, so B2 is a lower bar for "big general model" than planned.
- Possible extra baseline later: Gemma 4 31B (14.4K requests/day, 16K tokens/min on the owner's project),
  once it stops returning 500 errors.
- Gemini limits are per model; the `gemini` provider entry holds Flash-Lite's limits, so re-check them before
  adding another Gemini model.
