# 0010: Judge switch to Gemma 4 31B

- **Status:** accepted
- **Date:** 2026-10-11
- **Related:** ADR 0002 (first judge), ADR 0009 (calibration v1, v2 prompts)

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

### Native-speaker check (sample C, dialect only)

`data/evals/calibration/dialect_check_v1.xlsx`: 20 answers from the 2026-10-11 reports that are in
neither calibration sample (6 B1_falcon, 6 B2, 4 B1_qwen, 2 B0_falcon, 2 B0_qwen; 7 Arabic, 7 Arabizi,
6 mixed), graded 1–5 against the judge's stored `dialect_v2` scores. No new judge calls.

**How it was graded.** The owner, a native Tunisian speaker, graded 5 answers alone. The other 15 were
pre-filled by Claude and then reviewed and adjusted by the owner. So only 5 grades are fully independent
of an AI; the sheet doesn't record which 5, so the numbers below can't be split by who graded.

| Check | Result | Target |
|---|---|---|
| Dialect within ±1 | 20/20 (exact on 14) | ≥ 80% |
| Mean absolute gap | 0.30 | ≤ 1.0 |
| Spearman | 0.76 | |
| Judge − owner, B2 answers | +0.17 (higher on 2, lower on 1, n = 6) | |
| Judge − owner, other answers | +0.21 (higher on 3, lower on 0, n = 14) | |

The judge agrees with the owner within one point everywhere and is slightly generous (~+0.2) on all
systems alike. The B2-specific leniency seen on the calibration answers (+0.2 to +0.5) does not show up
here. The six one-point gaps: the judge scored higher on cin-008 B2, pass-009 B2 (Arabizi mirroring with
copied and garbled words), cnss-001 B1_falcon (Moroccan ديالو), cnss-003 B1_qwen (Egyptian "دي") and
pass-009 B0_falcon, and lower on cnss-002 B2 (a short neutral phrase). The owner's notes on what makes an
answer Tunisian are in ADR 0001.

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
- Rules for a future `dialect_v3`, from the owner's check (not implemented; changing the prompt needs
  re-calibration):
  - Eastern Arabic digits (٣، ١٥، ٨٠) are a non-Tunisian marker: Tunisians write 3, 15, 80. Seen in 3
    answers (B1_qwen b3-002 "٣ دينار", B0_qwen pass-005 and b3-004).
  - Full diacritics ("تُفْرِغُ البطاقَة") mark formal or textbook Arabic.
  - A question translated into formal Arabic and asked back is an echo; the code echo rule misses it
    (B0_falcon b3-001 "الوظيفة الثالثة من النشرة 3 متى هي؟").
