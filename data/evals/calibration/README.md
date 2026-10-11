# Judge calibration

Checks how far the LLM judge agrees with a second grader before trusting baseline numbers (spec 8.2).
Results and decisions: ADR 0009 (v1 prompts, v2 prompts, echo rule, owner's rubric) and ADR 0010 (judge
switched to Gemma 4 31B).

## Files

| File | What |
|---|---|
| `judge_calibration_v1.xlsx` | sample A: 20 answers, 54 facts, one row per fact (tab "Grade", rules in "Guide") |
| `judge_calibration_v1_judge.json` | the v1 judge's (gpt-oss-120b) verdicts for sample A |
| `judge_calibration_v1b.xlsx` | sample B: 20 answers, 62 facts; tabs "Facts" and "Dialect", Claude's and the v1 judge's grades side by side |
| `dialect_check_v1.xlsx` | sample C: 20 other answers, dialect only, graded by the native-speaker owner (5 alone, 15 pre-filled by Claude and reviewed by the owner; tab "Dialect") |
| `dialect_check_v1_judge.json` | the 2026-10-11 judge's (Gemma 4 31B, `dialect_v2`) dialect scores for sample C; don't open it before grading |

Second grader: Claude, reviewed by the owner (not fully blind, see ADR 0009). In sample B the `owner`
column overrides Claude: blank or `claude` keeps Claude's grade, `judge` takes the judge's, and `Y`/`N`
(Facts tab) or `owner score (optional)` (Dialect tab) is the owner's own grade.

Owner's rubric: the core-claim rule, the same as `correctness_v2`: a fact is present if its core claim
is stated; a missing minor detail is fine, a wrong value is not (ADR 0009). Compound facts should be
split in gold set v2.

## Samples

- A, built by `uv run python scripts/calibration_sample.py` from the 2026-10-11 reports: `b3-005` and
  `birth-003` from the first smoke run (`B2_smoke`, gemini-2.5-flash), 8 B2, 5 B3 and 5 B0 answers, spread
  over scripts and judge scores. Heavy on good answers: tests fact strictness.
- B, built by hand: 14 B0, 4 B2 and 2 B3 answers. Heavy on bad answers: tests dialect (Moroccan,
  Egyptian, formal Arabic) and echoes.

Two answers are in both samples (B3 pass-001, B0_qwen cnss-001): 38 distinct answers.

## Commands

- `uv run tasks.py calibrate-report`: the stored v1 judge results vs the grader, per sample, and sample C
  (owner vs the Gemma judge on dialect) once it is graded. Rebuild sample C with
  `uv run python -m scripts.dialect_sample` (overwrites the sheet).
- `uv run tasks.py calibrate`: re-judges the 38 answers with the current judge and prompts (answers come
  from the sheets, judge calls are cached), prints a report per sample and a same-family check on the B2
  (Gemini) answers. Exit code 0 = pass: on each sample, fact agreement ≥ 80% and dialect within ±1 ≥ 80%.
- `uv run tasks.py calibrate --cached`: the same from the cache only, no judge calls; unjudged answers
  are listed as "not judged".

Each report gives fact agreement and Cohen's kappa, the direction of disagreements (judge stricter or
looser), dialect mean absolute difference, % within ±1 and Spearman, and every disagreement with the
judge's one-line reason (v2 prompts) or verdict (v1).

## Redo after changing the judge or its prompts

1. `uv run tasks.py calibrate`. A changed prompt or model makes new calls.
2. Pass: record the numbers in an ADR. Fail: read the disagreements before changing anything.
3. New graded answers: add a sample sheet (and a loader in `scripts/calibration_report.py` if the layout
   differs).
