"""Cross-platform task runner, replaces `make` (spec 3.1.1).

Usage: uv run tasks.py <target> [extra args passed to the target's last command]
"""

from __future__ import annotations

import argparse
import subprocess
import sys

PY = sys.executable

TASKS: dict[str, list[list[str]]] = {
    "lint": [[PY, "-m", "ruff", "check", "."], [PY, "-m", "ruff", "format", "--check", "."]],
    "format": [[PY, "-m", "ruff", "format", "."], [PY, "-m", "ruff", "check", "--fix", "."]],
    "typecheck": [[PY, "-m", "mypy"]],
    "test": [[PY, "-m", "pytest"]],
    "test-live": [[PY, "-m", "pytest", "-m", "live"]],
    # needs Docker (`db-up`, `index`) and downloads the retrieval models on first run
    "test-integration": [[PY, "-m", "pytest", "-m", "integration"]],
    "validate-evals": [[PY, "-m", "evals.gold"]],
    "fetch": [[PY, "-m", "chaouch.ingestion", "fetch"]],
    "clean": [[PY, "-m", "chaouch.ingestion", "clean"]],
    "chunk": [[PY, "-m", "chaouch.ingestion", "chunk"]],
    "ingest": [[PY, "-m", "chaouch.ingestion", "all"]],
    "db-up": [["docker", "compose", "--profile", "core", "up", "-d", "--wait", "db"]],
    "index": [[PY, "-m", "chaouch.retrieval.index"]],
    "eval-retrieval": [[PY, "-m", "evals.runners.retrieval"]],
    "eval-smoke": [[PY, "-m", "evals.runners.baseline", "--suite", "smoke"]],
    "eval-full": [[PY, "-m", "evals.runners.baseline", "--suite", "full"]],
    "calibrate-report": [[PY, "-m", "scripts.calibration_report"]],
    "calibrate": [[PY, "-m", "scripts.calibration_report", "--rejudge"]],
}
TASKS["check"] = TASKS["lint"] + TASKS["typecheck"] + TASKS["test"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=sorted(TASKS))
    args, extra = parser.parse_known_args()
    commands = TASKS[args.target]
    for i, cmd in enumerate(commands):
        if i == len(commands) - 1:
            cmd = cmd + extra
        code = subprocess.call(cmd)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
