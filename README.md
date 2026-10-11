# Chaouch

A Tunisian Derja assistant for administrative procedures, built and measured as an AI engineering project.

> Work in progress. Phase 0 (setup and baseline) is done: see [Baseline](#baseline).

## The problem

Tunisians ask about paperwork (passport renewal, birth certificates, ID cards, CNSS, criminal record extracts) in Derja:
in Arabic script, in Latin letters with numbers (Arabizi: `3`, `7`, `9`), or mixed with French.
The official information is in French or Modern Standard Arabic, spread over many sites and PDFs.

General-purpose LLMs handle Tunisian dialect poorly. TounsiBench (EMNLP 2025) found that most LLMs
struggle to recognize and answer properly in Tunisian Arabic; see also
[How Well Do LLMs Understand Tunisian Arabic?](https://arxiv.org/abs/2511.16683).

Failures seen in the Phase 0 baseline ([model observations](docs/decisions/0001-model-observations.md)):

- Without documents, small local models invent fees: the passport costs 80 TND, Qwen3.5 2B says
  "100 دينار", Falcon-H1 3B "10 دينار".
- The criminal-record extract (bulletin n°3, البطاقة عدد 3) becomes a "card number 3": "تكلّف البطاقة رقم 3
  في تونس حسب نوعها (شخصية، شركة، أو مؤسسة)".
- Answers meant to be Derja come out in formal Arabic, Moroccan ("الطريقة ديالو هي كايناش") or Egyptian
  ("عشان ... اللي بيجي").

## Baseline

Gold set v1: 51 questions written and reviewed by a native speaker, 43 of them in scope and scored here.
B0 and B1 run once per local model (Q4 GGUF via Ollama):

| ID | System |
|---|---|
| B0 | Local model, question only |
| B1 | Local model + the official documents pasted into the prompt |
| B2 | Gemini 3.5 Flash-Lite (free API) + the same documents |
| B3 | ALLaM 2 7B on Groq (Arabic specialist) + the same documents |

Results of 2026-10-11 ([full table](reports/2026-10-11_baseline.md), per-question JSON in `reports/`):

| System | Model | Correctness | Faithfulness | Dialect (1–5) | p50 latency |
|---|---|---|---|---|---|
| B0 | Qwen3.5 2B | 0.07 | – | 1.12 | 3.3 s |
| B0 | Falcon-H1 3B | 0.09 | – | 1.33 | 2.7 s |
| B1 | Qwen3.5 2B | 0.46 | 0.72 | 1.02 | 4.3 s |
| B1 | Falcon-H1 3B | 0.67 | 0.83 | 1.16 | 9.2 s |
| B2 | Gemini 3.5 Flash-Lite | **0.84** | **0.99** | **3.77** | 0.8 s |
| B3 | ALLaM 2 7B | 0.31 | 0.71 | 1.14 | 0.6 s |

Correctness on B1 by script of the question:

| Model | Arabic script | Arabizi | Mixed with French |
|---|---|---|---|
| Qwen3.5 2B | 0.62 | 0.30 | 0.46 |
| Falcon-H1 3B | 0.82 | 0.53 | 0.65 |

What it shows:

1. **The documents do most of the work.** Falcon-H1 3B goes from 0.09 to 0.67 correctness once the
   official text is in the prompt. Retrieval (Phase 1) has to find those documents on its own.
2. **Local models don't speak Derja.** With or without documents, the local models and ALLaM score ~1.2
   on dialect (formal Arabic or another dialect); only Gemini reaches 3.8.
3. **Arabizi is the weak spot.** Arabizi questions score about 30 points lower than Arabic-script ones for
   both local models (B1 Falcon 0.53 vs 0.82, B1 Qwen 0.30 vs 0.62).

Falcon-H1 3B is the main local model from here on ([ADR 0011](docs/decisions/0011-main-local-model.md)).

Caveats:

- Scores come from an LLM judge, Gemma 4 31B on Google AI Studio, with prompts `correctness_v2` and
  `dialect_v2`. It was calibrated against a second grader on 40 answers and 116 graded facts (fact
  agreement 100%, dialect within ±1 on 40/40); the second grader is also an AI, reviewed by the owner
  ([ADR 0009](docs/decisions/0009-judge-calibration-v1.md), [ADR 0010](docs/decisions/0010-judge-gemma-4-31b.md)).
- The judge and B2 are both Google models. On the calibration answers the judge scored B2's dialect ~0.3
  points higher than the second grader did, and not the others: B2's 3.77 may be a little generous.
- Gold set v1 has 43 scored questions and each system ran once: differences of a few points are noise.
- 3 B1 Falcon faithfulness scores are missing (the judge API kept failing on them); its 0.83 is over 40.
- Answers that only repeat the question are scored 0 without the judge (3 for B0 Falcon, 1 for B3).

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
| `eval-full` | all six systems on the whole gold set |
| `calibrate-report` / `calibrate` | judge calibration: stored results / re-judge the 40 calibration answers |

How to add documents and gold questions, and run evals on free tiers: [docs/workflows.md](docs/workflows.md).

## Data and licenses

PDF conversion uses PyMuPDF / pymupdf4llm (AGPL-3.0).
