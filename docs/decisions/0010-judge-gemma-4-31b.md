# ADR 0010: Judge switch to Gemma 4 31B

- Status: accepted
- Date: 2026-10-11
- Related: ADR 0002 (first judge), ADR 0009 (calibration v1, v2 prompts)

## Context

The judge was `openai/gpt-oss-120b` on Groq (ADR 0002). Its free tier caps it at 200K tokens per
day, and one `eval-full` needs ~690 judge calls (~1.4M tokens): about a week of daily re-runs.
The v2 validation of ADR 0009 also stopped on the cap with 11 sample-B answers unjudged.
NVIDIA and Cerebras free tiers aren't available to the owner.

## Options

1. Keep gpt-oss-120b on Groq and run over ~7 days.
2. Gemma 4 31B (`gemma-4-31b-it`) on Google AI Studio, same `GEMINI_API_KEY`: 14.4K requests/day
   and 16K tokens/min on the free tier (owner's console, 2026-10-11).
3. Gemini Flash as judge: it would grade its own answers in B2.

## Experiment

- Model id from the API's model list: `models/gemma-4-31b-it` (also `gemma-4-26b-a4b-it`).
- JSON mode works, but Gemma 4 always prints a `<thought>…</thought>` block before the JSON, and
  thinking can't be turned off (`reasoning_effort` none/low → 400 "not supported for this model").
  The judge parser now strips a leading thought block.
- Gemma sometimes returns the bare list (`[{"claim": ...}]`) instead of `{"claims": [...]}`; the
  parser accepts it for outputs with a single list field (seen twice in the first `eval-full`).
- ~30 s per call; the API sometimes answers 503 "high demand", which the SDK retries.
- `uv run tasks.py calibrate`: the v2 prompts (ADR 0009) and the code echo rule, fresh Gemma calls on
  all 38 calibration answers (40 sample rows), against the second grader (core-claim rule, ADR 0009).

## Results

| Check | Sample A | Sample B | Target |
|---|---|---|---|
| Fact agreement | 54/54 = 100% | 62/62 = 100% | ≥ 80% |
| Judge stricter / looser | 0 / 0 | 0 / 0 | |
| Dialect within ±1 | 20/20 | 20/20 | ≥ 80% |
| Dialect mean absolute gap | 0.30 (Spearman 0.95) | 0.40 (Spearman 0.70) | ≤ 1.0 |

Both samples pass with no fact disagreement. (Under the strict reading the owner tried and
reverted, Gemma disagreed on exactly those 4 rows: 50/54 and 59/62.) The dialect problems of v1
(Moroccan and Egyptian answers scored 4–5) are gone. Perfect fact agreement against a second grader
that is itself an AI and was not fully blind is weaker evidence than it looks; ADR 0009 says so.

For comparison, gpt-oss-120b with the same prompts: sample A 49/54 facts (stricter on 5), 19/20
dialect; sample B incomplete at the daily cap (26/29 facts, 8/9 dialect).

### Same-family check (B2 = Gemini, judged by Gemma, both Google)

| Check | Sample A, B2 answers | Sample B, B2 answers |
|---|---|---|
| Fact agreement | 25/25 | 13/13 |
| Dialect within ±1 | 10/10 | 4/4 |
| Mean dialect gap, judge − grader | +0.2 | +0.5 |
| Same, all other answers | 0.0 | −0.25 |

No fact bias. On dialect, Gemma scores B2 slightly higher than the grader while it does not for
other systems: a possible mild leniency of ~0.3 points, on 14 answers only.

## Decision

- Default judge: `gemma_judge` (`gemma-4-31b-it`, provider `gemini_gemma` in `configs/models.yaml`):
  3 requests/min, 14,000/day, concurrency 4, timeout 120 s. The binding limit is 16K *input*
  tokens/min (`GenerateContentInputTokensPerModelPerMinute-FreeTier`): at 6/min the ~3-4K-token
  faithfulness prompts hit it at 6 and 4/min. Measured throughput is ~3 calls/min anyway (~30 s per call).
- Keep `groq_judge` (gpt-oss-120b) configured for re-runs; it is no longer the default.
- The self-judging check compares model families (`gemma` vs `gemini`) and doesn't flag B2. The
  caveat is recorded here instead: B2's dialect score may be ~0.3 points generous. Read B2 vs B3
  dialect gaps smaller than that as a tie.

## Consequences

- `eval-full` fits in a day: ~690 judge calls took ~3 hours.
- Gemma's API returns transient 500/503 errors (~45 of ~690 calls in the first run, after the SDK's
  retries). They are not cached, so re-running `eval-full` resumes and retries only those. The
  2026-10-11 baseline took five runs; 3 B1_falcon faithfulness calls (pass-007, pass-008, cin-007)
  failed on four runs in a row and are left unscored (their correctness and dialect are scored).
- Earlier gpt-oss judgments stay in the cache; reports name the judge and prompt versions.
- Judge and B2 share one Google key but not their limits (limits are per model).
- Judge latency is high (~30 s, thinking); runs are slow but unattended.
