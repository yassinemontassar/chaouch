# Chaouch

A Tunisian Derja assistant for administrative procedures, built and measured as an AI engineering project.

> Work in progress. Phase 0 (setup and baseline) is done: see [Baseline](#baseline). Phase 1
> (retrieval) is measured: see [Retrieval](#retrieval).

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

Gold set v1: 51 questions, drafted with AI from the official sources, then reviewed and edited by a native
speaker; 43 of them are in scope and scored here.
B0 and B1 run once per local model (Q4 GGUF via Ollama):

| ID | System |
|---|---|
| B0 | Local model, question only |
| B1 | Local model + the official documents pasted into the prompt |
| B2 | Gemini 3.5 Flash-Lite (free API) + the same documents |
| B3 | ALLaM 2 7B on Groq (Arabic specialist) + the same documents |

Results of 2026-10-11 ([full table](reports/2026-10-11_baseline.md), per-question JSON in `reports/`):

| System | Model | Correctness | Faithfulness | Dialect (1–5) | Trustworthy | p50 latency |
|---|---|---|---|---|---|---|
| B0 | Qwen3.5 2B | 0.07 (0.01–0.14) | – | 1.12 (1.02–1.23) | – | 3.3 s |
| B0 | Falcon-H1 3B | 0.09 (0.04–0.16) | – | 1.33 (1.14–1.56) | – | 2.7 s |
| B1 | Qwen3.5 2B | 0.46 (0.35–0.58) | 0.72 | 1.02 (1.00–1.07) | 0.19 (0.07–0.30) | 4.3 s |
| B1 | Falcon-H1 3B | 0.67 (0.54–0.79) | 0.83 | 1.16 (1.02–1.37) | 0.35 (0.21–0.49) | 9.2 s |
| B2 | Gemini 3.5 Flash-Lite | **0.84** (0.77–0.91) | **0.99** | **3.77** (3.30–4.19) | **0.63** (0.49–0.77) | 0.8 s |
| B3 | ALLaM 2 7B | 0.31 (0.19–0.42) | 0.71 | 1.14 (1.02–1.30) | 0.07 (0.00–0.16) | 0.6 s |

In brackets: 95% bootstrap confidence intervals over the 43 questions. **Trustworthy** = the share of
answers that could be shown as is: every required fact present (correctness 1.0) and faithfulness ≥ 0.9.

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
Its intervals overlap Qwen's on every metric; a paired comparison on the same questions shows Falcon
ahead on correctness (+0.21, 95% CI +0.07 to +0.35), borderline on the trustworthy rate (+0.16, 0.00 to
+0.33), and no different on dialect.

Caveats:

- Scores come from an LLM judge, Gemma 4 31B on Google AI Studio, with prompts `correctness_v2` and
  `dialect_v2`. It was calibrated against a second grader on 40 answers and 116 graded facts (fact
  agreement 100%, dialect within ±1 on 40/40). That second grader is also an AI (Claude), reviewed by
  the owner. The owner, a native speaker, then checked dialect on 20 more answers: within ±1 on 20/20,
  mean gap 0.30. Only 5 of those were graded by the owner alone; the other 15 were pre-filled by Claude
  and reviewed and adjusted by the owner
  ([ADR 0009](docs/decisions/0009-judge-calibration-v1.md), [ADR 0010](docs/decisions/0010-judge-gemma-4-31b.md)).
- The judge and B2 are both Google models. On the calibration answers it scored B2's dialect ~0.3 points
  higher than the second grader; on the owner's check it was ~0.2 points generous on every system alike.
  Read dialect gaps under ~0.3 as ties.
- Gold set v1 has 43 scored questions and each system ran once: differences of a few points are noise.
- 3 B1 Falcon faithfulness scores are missing (the judge API kept failing on them); its 0.83 is over 40.
- Answers that only repeat the question are scored 0 without the judge (3 for B0 Falcon, 1 for B3).

Hardware for all local numbers: RTX 3050 Laptop GPU (6 GB VRAM), 16 GB RAM, Windows 11.

## Retrieval

The system has to find the right official page on its own. Measured on the 43 gold questions against
27 documents: the 8 procedure pages plus 19 official pages on other procedures from the same portal,
added as distractors so the test isn't trivial ([ADR 0013](docs/decisions/0013-retrieval-comparison.md),
[full report](reports/2026-10-12_retrieval.md)).

| Retrieval | R@1 | R@5 | MRR | Latency per question (CPU) |
|---|---|---|---|---|
| BM25 (keywords) | 0.30 | 0.49 | 0.40 | < 1 ms |
| **bge-m3 embeddings** | **0.58** | **0.91** | **0.74** | 0.4 s |
| bge-m3 + BM25 (RRF fusion) | 0.42 | 0.77 | 0.60 | 0.4 s |
| bge-m3 + BM25 + reranker (bge-reranker-v2-m3) | 0.51 | 0.87 | 0.67 | 80 s |
| Qwen3-Embedding-0.6B | 0.42 | 0.73 | 0.60 | 0.8 s |

R@k: share of the gold documents in the top k chunks given to the model. MRR: mean of 1 / rank of the
first right chunk.

What it shows:

1. **Keywords can't bridge Derja and French.** BM25 finds 12% of the right pages first for Arabic-script
   questions, so fusing it with the embeddings makes them worse (MRR −0.14, paired 95% CI −0.24 to
   −0.04). The usual "hybrid search" recipe doesn't hold here.
2. **The reranker doesn't pay for itself.** It doesn't beat bge-m3 alone and takes ~80 s per question on
   a laptop CPU.
3. **Qwen3-Embedding matches the script, not the meaning.** For "قدّاش يكلّف الباسبور؟" it ranks
   Arabic-script pages on fishing cards and seamen's books above the French passport page: R@1 0.00 on Arabic-script
   questions.

Phase 2 uses bge-m3 alone.

Gold v2 light ([ADR 0014](docs/decisions/0014-gold-v2-arabic-twins.md)) adds the Arabic versions of the
French procedure pages: bge-m3 stays first (R@1 0.62, R@5 0.93, MRR 0.77 on 33 documents), and
BM25 fusion no longer hurts once Arabic-script questions have Arabic pages to match.

## Roadmap

Each phase targets a weakness the baseline found.

| Phase | Work | Weakness it targets |
|---|---|---|
| 1 | Retrieval: Arabic normalization, BM25, bge-m3 embeddings, fusion, reranker | The documents do most of the work, but B1 had them pasted in; the real system must find them |
| 2 | API, generation, observability | Falcon's 9.2 s latency and ~340-token answers; wrong terms and added wrong facts ([ADR 0012](docs/decisions/0012-answer-prompt-phase-2.md)) |
| 3 | Agent and tools | Out-of-scope and adversarial questions (not scored yet) |
| 4 | Arabizi normalizer; Derja style with QLoRA (optional) | Arabizi is ~30 points behind Arabic script; local models answer in formal Arabic (dialect ~1.2) |


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
| `db-up` | Postgres + pgvector in Docker (start Docker Desktop first) |
| `index` | embed the chunks into pgvector |
| `eval-retrieval` | Recall@k and MRR on the gold set, no LLM |
| `test-integration` | tests that need Docker and the retrieval models |
| `eval-smoke` | B2 on 20 gold questions |
| `eval-full` | all six systems on the whole gold set |
| `calibrate-report` / `calibrate` | judge calibration: stored results / re-judge the 40 calibration answers |

How to add documents and gold questions, and run evals on free tiers: [docs/workflows.md](docs/workflows.md).

## Data and licenses

PDF conversion uses PyMuPDF / pymupdf4llm (AGPL-3.0).
