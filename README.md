# Chaouch

A Tunisian Derja assistant for administrative procedures, built and measured as an AI engineering project.

> Work in progress (Phase 0: setup and baseline).

## Running it locally (Windows, native)

One-time setup in PowerShell:

```powershell
winget install astral-sh.uv Ollama.Ollama
uv python install 3.12
git config --global core.longpaths true
# Keep the virtualenv outside OneDrive / the repo:
setx UV_PROJECT_ENVIRONMENT C:\dev\venvs\chaouch
# Ollama: one model in memory, modest context (6 GB laptop GPU):
setx OLLAMA_MAX_LOADED_MODELS 1
setx OLLAMA_CONTEXT_LENGTH 4096
```

Open a new terminal, then:

```powershell
uv sync
copy .env.example .env   # then fill in the API keys
uv run tasks.py check    # lint + types + tests
uv run pre-commit install
```

Tasks (`uv run tasks.py <target>`): `lint`, `format`, `typecheck`, `test`, `test-live`, `check`.
