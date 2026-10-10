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
