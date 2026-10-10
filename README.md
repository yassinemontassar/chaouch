# Chaouch

A Tunisian Derja assistant for administrative procedures, built and measured as an AI engineering project.

> Work in progress (Phase 0: setup and baseline).

## The problem

Tunisians ask about paperwork (passport renewal, birth certificates, ID cards, CNSS, criminal record extracts) in Derja:
in Arabic script, in Latin letters with numbers (Arabizi: `3`, `7`, `9`), or mixed with French.
The official information is in French or Modern Standard Arabic, spread over many sites and PDFs.

General-purpose LLMs handle Tunisian dialect poorly. TounsiBench (EMNLP 2025) found that most LLMs
struggle to recognize and answer properly in Tunisian Arabic; see also
[How Well Do LLMs Understand Tunisian Arabic?](https://arxiv.org/abs/2511.16683).

Examples of failures seen in Phase 0: _to be added from the model notes in
`docs/decisions/0001-model-observations.md`._

## Baseline

Baselines on the gold set, written by a native speaker. B0 and B1 run once per local model
(Qwen3.5 2B and Falcon-H1 3B Instruct, both Q4 via Ollama):

| ID | System |
|---|---|
| B0 | Local model, question only |
| B1 | Local model + the official documents pasted into the prompt |
| B2 | Gemini Flash (free API) + the same documents |
| B3 | ALLaM 2 7B on Groq (Arabic specialist) + the same documents |

Answers are graded by an LLM judge from a different model family (correctness against the required facts,
faithfulness to the documents, dialect on a 1–5 scale). Results: _pending the gold set; the table will be in
`reports/<date>_baseline.md`._

Hardware for all local numbers: RTX 3050 Laptop GPU (6 GB VRAM), 16 GB RAM, Windows 11.

## Running it locally (Windows, native)

One-time setup in PowerShell:

```powershell
winget install astral-sh.uv Ollama.Ollama
uv python install 3.12
git config --global core.longpaths true
setx UV_PROJECT_ENVIRONMENT C:\dev\venvs\chaouch   # keep the virtualenv out of the repo
setx OLLAMA_MAX_LOADED_MODELS 1
setx OLLAMA_CONTEXT_LENGTH 4096
```

Open a new terminal, then:

```powershell
uv sync
copy .env.example .env   # then fill in the API keys
uv run tasks.py check
uv run pre-commit install
```

`uv run tasks.py <target>`:

| Target | What it does |
|---|---|
| `check` | lint + types + tests |
| `test-live` | one real call per configured model (needs keys / Ollama) |
| `validate-evals` | checks `data/evals/gold/questions.jsonl` |
| `ingest` | `fetch` + `clean` + `chunk` the sources in `data/documents/sources.yaml` |
| `eval-smoke` | B2 on 20 gold questions |
| `eval-full` | B0, B1, B2 on the whole gold set |

## Data and licenses

PDF conversion uses PyMuPDF / pymupdf4llm (AGPL-3.0).
