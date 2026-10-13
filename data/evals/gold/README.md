# Gold evaluation set [HUMAN]

Owned and reviewed by a native Derja speaker (see Provenance). **Never** used for training.

`questions.jsonl`: one JSON object per line, in the schema of PROJECT_SPEC.md section 7.2:

```json
{"id": "pass-001", "procedure": "passport_renewal", "question": "...", "script": "arabizi", "code_switching": false, "category": "in_scope", "difficulty": "easy", "expected_answer": "...", "required_facts": ["..."], "gold_doc_ids": ["doc_passport_01"], "notes": ""}
```

Rules checked by `uv run tasks.py validate-evals`:

- Errors (must fix): invalid JSON, unknown or missing fields, a wrong enum value, a duplicate `id`, a `gold_doc_ids` entry that isn't in `data/documents/sources.yaml`.
  An `in_scope` question needs a `procedure` that has a source, plus non-empty `required_facts` and `gold_doc_ids`.
- Warnings (targets from `configs/eval.yaml`): fewer than 50 questions, `script` not roughly a third each (`arabic`, `arabizi`, `mixed_fr`),
  out-of-scope + adversarial not about 15%.

`procedure` may be `null` for out-of-scope and adversarial questions.

## Provenance

The questions and expected answers were drafted with AI assistance (Claude) from the official source pages
in `data/documents/sources.yaml`, then reviewed by a native Derja speaker for natural Derja and for facts.
Claude is neither an evaluated system nor the judge (`configs/models.yaml`).

`questions.jsonl` is generated from the owner's spreadsheet, the source of truth:

```powershell
uv run scripts/gold_from_xlsx.py ../chaouch_gold_questions.xlsx
uv run tasks.py validate-evals
```

## Versions

- **v1** (2026-10-11): the 51 questions above. Phase 0 baselines (B0–B3) and ADR 0013 use it.
- **v2 light** (2026-10-13, ADR 0014): same questions and `gold_doc_ids`. The Arabic twins of the
  passport, CIN, bulletin n°3 and CNSS pages were added as core sources with `translation_of` in
  `sources.yaml`, so `eval-retrieval` counts either language version as the gold document
  (owner-approved mapping). New Derja questions come later ([HUMAN]).
