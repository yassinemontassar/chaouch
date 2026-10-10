# 0006: Data quality: source selection

- **Status:** accepted (owner's decision)
- **Date:** 2026-10-11

## Context
The first `uv run tasks.py ingest` on the owner's 9 sources fetched and cleaned everything, but the Arabic
output had three problems:
- The two fill-in PDF forms (`doc_passport_02`, `doc_tax_02`) extracted as scrambled Arabic: lam-alef split
  ("اإلدارة" for "الإدارة", 39 times), words in the wrong letter order, and 12 U+FFFD characters in the
  passport form. `doc_tax_02` alone was 101 of 125 chunks (81%), mostly empty form fields, and would fill
  the 2,500-token oracle budget for any question pointing at it.
- `doc_birth_01` lost its opening (conditions and required documents) to trafilatura's default extraction.
- `doc_birth_01` contained 273 Arabic presentation-form characters (U+FB50 to U+FEFF), pasted from a PDF into
  the page. They look normal but tokenize differently from the base letters.

A check on `doc_birth_02` confirmed the HTML Arabic is stored in logical order ("بوابة", not "ةباوب"); only
the PDFs were scrambled.

## Options
1. Keep the PDFs and repair the extraction (OCR or a different PDF library).
2. Drop the PDF forms; normalize the text; let a source opt into recall-first extraction.

## Experiment
Compared trafilatura's modes on the 7 HTML pages: `favor_recall` keeps `doc_birth_01`'s opening;
`favor_precision` returns nothing for `doc_tax_01`, so "precision" stays trafilatura's balanced default.
Re-ran ingest after each change.

## Results
| doc_id | Language | Before | After |
|---|---|---|---|
| doc_passport_01 | fr | 3 | 3 |
| doc_passport_02 | ar (PDF form) | 5 | removed |
| doc_birth_01 | ar | 2 | 3 |
| doc_birth_02 | ar | 1 | 1 |
| doc_cin_01 | fr | 2 | 2 |
| doc_cin_02 | fr | 3 | 3 |
| doc_cnss_01 | fr | 5 | 5 |
| doc_tax_01 | fr | 3 | removed |
| doc_tax_02 | ar (PDF form) | 101 | removed |
| doc_b3_01 | fr | | 2 |
| doc_b3_02 | fr | | 2 |
| **Total** | | **125** (39,929 tokens) | **21** (6,567 tokens) |

`doc_birth_01` went from 503 to 864 tokens once its conditions and required documents were kept, and has
no presentation-form characters left.

## Decision
Option 2:
- Removed `doc_passport_02` and `doc_tax_02` from `sources.yaml`.
- The cleaner applies Unicode NFKC to all text, which folds presentation forms into the base letters.
- New optional `extract_mode` per source (`precision` by default, `recall` allowed); `doc_birth_01` uses
  `recall`.
- Replaced `tax_declaration` with `criminal_record` (bulletin n°3, `doc_b3_01` and `doc_b3_02`): without
  the PDF, its only source was `doc_tax_01`, an index page of forms with no procedure content.

## Consequences
- `passport_renewal` now has a single French source and no Arabic one.
- Arabic coverage is the two birth certificate pages only; add Arabic HTML sources rather than PDF forms.
- `recall` adds some page clutter (a stray table marker at the start of `doc_birth_01`); use it only per source.
- NFKC also folds other compatibility characters (e.g. ligatures, non-breaking spaces), which is fine for
  retrieval and prompts.
