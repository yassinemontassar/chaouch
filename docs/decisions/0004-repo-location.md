# 0004: Repo stays in OneDrive; venv and eval cache live outside it

- **Status:** accepted (owner's decision)
- **Date:** 2026-10-10

## Context
The repo is at `C:\Users\yassi\OneDrive\Bureau\chaouch`. OneDrive syncs every write and can lock files
while a process writes them, which breaks virtualenv installs and SQLite. Spec 3.1.1 suggested a short path
such as `C:\dev\chaouch`.

## Options
1. Move the repo to `C:\dev\chaouch`.
2. Keep the repo in OneDrive and move heavy, frequently written files out.
3. Do nothing.

## Experiment
None. This is a working-environment choice, not a quality change.

## Results
| Item | Location | Set by |
|---|---|---|
| Virtualenv (~400 MB) | `C:\dev\venvs\chaouch` | user env var `UV_PROJECT_ENVIRONMENT` |
| Eval cache (SQLite) | `C:\dev\cache\chaouch\eval_cache.sqlite` | `cache_path` in `configs/eval.yaml` |
| Tokenizer and model weights | Hugging Face / Ollama user caches | their defaults |
| Raw downloads | `data/documents/raw/` (git-ignored) | still synced by OneDrive |

## Decision
Option 2. Never create `.venv` inside the repo. Any new cache or artifact folder defaults to a path under
`C:\dev\` and is configurable.

## Consequences
- `data/documents/raw/` still syncs; it is small for 5 procedures.
- `cache_path` is a Windows path; CI (Linux, Phase 5) must override it.
- Revisit before Phase 4, which brings large downloads and training checkpoints.
