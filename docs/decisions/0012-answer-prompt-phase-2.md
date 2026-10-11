# 0012: Answer prompt and answer checks for Phase 2

- **Status:** proposed (open item for Phase 2; nothing implemented yet)
- **Date:** 2026-10-11
- **Related:** ADR 0001 (model observations), ADR 0007 (open items), ADR 0011 (main local model)

## Context
The B1 Falcon-H1 3B answers of the 2026-10-11 baseline (ADR 0001) show three problems that the
answer prompt and a post-check could address. None of them is fixed by retrieval (Phase 1).

1. **Wrong document name.** In 10 of 12 passport answers Falcon calls the passport "بطاقة هوية" (ID card),
   because the source documents are French ("passeport") and the model maps them to the wrong Arabic
   term. The judge is inconsistent about it: it zeroed pass-001, pass-003 and pass-004 for it and gave
   full marks to pass-002, 005, 008, 010 and 011.
2. **Long, formal answers.** ~340 tokens per answer on average (Qwen ~160, Gemini ~90), in list-style
   formal Arabic. This is the main cause of the 9.2 s p50 latency, and of the low dialect score (~1.2).
3. **Contradictions and added wrong facts still score as correct.** `correctness_v2` checks that the
   required facts are present, not that nothing wrong was added:
   - pass-002 states "للمرة الأولى: 25 دينار / للحالة الثانية: 80 دينار" (wrong: 80 TND is the normal fee,
     25 TND is for pupils, students and children under 7), then the right rule further down: 1.0.
   - b3-003 says the bulletin n°3 is for "الجزائريين والمولودين في الجزائر" (Algerians, born in Algeria)
     instead of Tunisians: 1.0.
   - cin-005 reads "17 sna" as "30 سنة" and answers for an adult: 1.0.

## Options
1. Do nothing until Phase 2 measures it on the retrieval pipeline.
2. In Phase 2, change the answer prompt (`answer_oracle_v2`) and add a check on the answer.

## Proposal (to test in Phase 2, as an ADR experiment)
- **Glossary in the answer prompt**: the French and formal terms of the documents and their Derja
  equivalents, e.g. passeport → باسبور / جواز سفر, carte d'identité → بطاقة التعريف, bulletin n°3 →
  البطاقة عدد 3. Built from the gold answers and owner-reviewed, never invented.
- **"Answer briefly in Derja"**: a length limit (a few sentences, or a short list when the answer is a
  list of documents) and the instruction to answer in Tunisian Derja, with one short example.
- **Tunisian writing conventions**: Western digits only (3, 15, 80, never ٣، ١٥، ٨٠), and no full
  diacritics. Both mark an answer as non-Tunisian to a native reader (owner's notes, ADR 0001); B1_qwen
  wrote "٣ دينار".
- **A contradiction check**: a judge step (or a separate prompt) that lists facts in the answer that
  contradict the documents or the gold facts, so an answer with a wrong fee or the wrong country can't
  score 1.0. Report it as its own metric next to correctness, so the two stay comparable with Phase 0.

## Consequences
- Any change to the answer prompt or the judge makes new calls and new reports; compare against the
  Phase 0 baseline only with the prompt versions written next to the numbers.
- A new judge prompt needs re-calibration first (`uv run tasks.py calibrate`, ADR 0009).
