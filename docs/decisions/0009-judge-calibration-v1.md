# ADR 0009: Judge calibration v1

- Status: accepted, pending the owner's review of the disagreements
- Date: 2026-10-11
- Related: PROJECT_SPEC §8.2, ADR 0002 (judge choice), ADR 0007 (open items)

## Context

All Phase 0 scores come from an LLM judge: `openai/gpt-oss-120b` on Groq, with prompts
`correctness_v1` and `dialect_v1`. Before spending ~3 more days of the judge's
free daily quota, we checked whether its grades can be trusted.

## Method

Two samples, 40 answers, 116 required facts, all already graded by the judge (no new
judge calls). Second grader: Claude (Anthropic), a different model family from the
judge. The owner reviews every disagreement and has the final say.

| Sample | File | Content | Blind? |
|---|---|---|---|
| A | `judge_calibration_v1.xlsx` (built by `tasks.py`) | 20 answers, 54 facts: B2 ×8 (incl. 2 smoke), B3 ×5, B0 ×5 | **No**: the judge file was in Claude's context while grading |
| B | `judge_calibration_v1b.xlsx` | 20 answers, 62 facts: B2 ×4, B3 ×2, B0 ×14 | Mostly: Claude had seen each answer's overall score, not the per-fact verdicts |

Sample A is heavy on good (oracle) answers, so it tests fact strictness. Sample B is
heavy on bad (B0) answers, so it tests dialect on Moroccan, Egyptian and formal-Arabic text.

Fact rule used by the second grader: a fact counts as present if its core claim is
stated correctly. Missing a minor detail is fine; a wrong value (number, place, delay)
is absent.

**Owner's rubric (2026-10-11): the core-claim rule** above, the same rule as `correctness_v2`.
The owner first tried a strict reading (every part written in a fact must be stated) on four rows:
B3 pass-001 facts 1, 2 and 5 (both samples) and B2 pass-005 fact 4. It was reverted the same
day: those rows are graded Y again, and the sheets are back to the second grader's grades.

## Results

| Check | Sample A | Sample B | Target |
|---|---|---|---|
| Fact agreement | 47/54 = 87% | 56/62 = 90% (κ 0.77) | ≥ 80% |
| Fact disagreements | **judge stricter 7, looser 0** | judge stricter 4, looser 2 | balanced |
| Dialect within ±1 | 19/20 | **10/20** | ≥ 80% |
| Dialect mean absolute gap | 0.45 | **1.75** | ≤ 1.0 |

The targets are rules of thumb chosen for this project, not an external standard.
The table is the v1 judge against the second grader, core-claim rule.

## Findings

1. **The judge is too strict on correct, short answers.** All 7 disagreements in
   sample A go the same way. Clearest case: B2_smoke b3-005 answered
   "إي، تنجم تطلبها على الخط... بالبريد السريع (Rapid-Poste)" and both facts were marked
   absent. birth-003 ("من بلدية تونس") and birth-005 (sibling not allowed, after
   "لا، ما تنجمش") were also marked absent. This underrates exactly the systems that
   use documents (B1/B2/B3), which is where the comparison matters.
2. **The dialect judge can't tell Tunisian from other Arabic dialects.** It's fine on
   Tunisian vs formal Arabic (sample A: 19/20 within ±1), but it gave 4–5 to Moroccan
   (ديال، ديالو، كايناش، واش), Egyptian (عشان، بيجي، حاجة، بعدين) and echo answers
   (sample B). Left as is, the dialect metric would reward the exact failure Chaouch
   is meant to fix.
3. **Negative facts are misgraded.** For "does not confirm 3 months", the judge said
   present when the answer said "نعم، هذا صحيح".
4. **Echoes get credit.** An answer that only repeated the question (B3 pass-010) had
   one fact marked present and dialect 5; B0_falcon pass-004 (echo) got dialect 3.
5. **Minor-detail strictness** (B3 pass-001: "filled and signed", "show the original")
   is a rubric choice. The owner decided on the core-claim rule (see Method), so these are
   judge errors.

## Decision

- **Keep** the judge model (`gpt-oss-120b`): the problems are in the prompts, not the model.
- **Replace `correctness_v1` with `correctness_v2`**:
  - core-claim rule: present if the core claim is stated in any wording or language;
    missing a minor detail does not make it absent; a wrong value does
  - a wrong value is marked "contradicted": it scores the same as absent (only "present"
    counts) but is reported separately, so wrong answers can be told apart from missing ones
  - negative facts ("does not X", "X is not listed") are present if the answer clearly
    says no / leaves X out, and absent if the answer does X
  - echoes or non-answers: every fact absent
  - one short reason per fact (one line), so future disagreements can be read
- **Replace `dialect_v1` with `dialect_v2`**:
  - Tunisian markers (شنوّة، نجّم، باش، توّا، فمّا، برشا، يلزمك، متاع، بلاصة، غادي / mta3, 9adech, chnowa)
  - non-Tunisian red flags: Moroccan (ديال، كاين، واش، هادشي، دابا, bzaf), Egyptian
    (عشان، بيجي، حاجة، دلوقتي، إزاي، كده), Gulf/Levantine, and formal Arabic
  - French words inside Derja sentences are normal Tunisian usage (the owner's own mixed_fr
    gold answers do this)
  - hard caps: clear non-Tunisian dialect markers → max 2; mostly formal Arabic → max 2;
    mostly or entirely French → max 2; echo or non-answer → 1
  - grade only the answer's own wording; words copied from the question don't count
  - three anchor examples, one sentence at three levels: 5 is gold answer `pass-011`
    verbatim; 3 and 1 are formal-Arabic rewrites of the same sentence (3 keeps the Derja
    opening, 1 is fully formal). Never taken from evaluated model outputs. `pass-011` is in
    neither calibration sample.
- **Echoes are detected in code, before the judge** (`is_echo` in `evals/judge/judge.py`,
  used by `eval-full` and `calibrate`). An answer is an echo when it covers ≥ 70% of the
  question's character 3-grams, ≥ 38% of its own 3-grams come from the question, it adds
  < 50 new 3-grams, and it adds no yes/no word (لا، ليست، نعم، إيه، ey, le, non...). The last
  rule keeps "شهادة فصيلة الدم ليست ضرورية" (a correct answer to a yes/no question) from
  being flagged. An echo gets every fact absent with the reason "echo of the question",
  dialect 1 (label "echo"), no faithfulness, and no judge calls; reports count them
  (`n_echoes`). On the 2026-10-11 runs it flags 4 of 271 answers (B3 pass-010, B0_falcon
  pass-004, b3-005 and birth-002) and none of the 51 gold expected answers (tested).
- Re-validate `v2` on both samples (40 answers) before the remaining full runs:
  dialect within ±1 ≥ 80% and fact agreement ≥ 80% on each sample.
- **v2 validation result:** done with the Gemma 4 31B judge after Groq's daily cap stopped the
  gpt-oss run; both samples pass (facts 54/54 and 62/62, dialect within ±1 20/20 on each). See
  ADR 0010. gpt-oss with v2 and the echo rule: sample A 49/54 facts (still stricter on 5) and 19/20
  dialect; sample B incomplete at the cap (26/29 facts, 8/9 dialect).
- Earlier `v1` judgments stay in the cache but are not reported. Reports must list
  the prompt versions (they already do).

## Consequences

- Up to one extra day of judge quota: the 40 validation answers are small, and dialect
  calls don't include documents.
- B0 dialect numbers in the final Phase 0 table will drop: B0 does not speak Tunisian.
  B1/B2/B3 correctness will likely rise. Both changes make the numbers more accurate.
- A second grader that is also an AI is weaker evidence than a human. The owner's review
  of the disagreement rows is what makes this calibration count.
- Still open (ADR 0007): Arabizi script mirroring and a script-match metric.

## Known limitations

- **Negative facts.** On B2 birth-005 fact 2 ("a sibling is not allowed"), gpt-oss with
  `correctness_v2` says absent ("does not mention that a sibling is not listed") although the
  answer starts with "لا، ما تنجمش" and lists only the allowed people. Gemma 4 31B grades it
  present (ADR 0010), but a judge can still miss a negative fact stated by leaving it out.
- **Compound facts.** Facts such as "application form filled and signed" or "copy of CIN +
  show the original" pack several checks into one. Gold set v2 should split them into one
  check per fact, so each part is graded on its own instead of by the core-claim rule.
- **Echo rule thresholds** were chosen on the 2026-10-11 answers. A model that echoes the
  question and adds a long unrelated text is not flagged (it adds ≥ 50 new 3-grams); the judge
  grades it.
