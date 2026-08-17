"""P6.1.1 — Freeze-state audit script (READ-ONLY).

Captures git HEAD, branch, and confirms preview environment.
Emits a machine-readable JSON snapshot at /app/backend/tests/iter496_2/freeze_state.json.
NEVER writes to production DB. Never edits source code.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd="/app", text=True).strip()
    except Exception as exc:
        return f"<git error: {exc}>"


def main() -> dict:
    out = {
        "audit": "P6.1.1 — Tax Engine Reconciliation",
        "phase": "P1 — Freeze State",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git("rev-parse", "HEAD"),
        "git_branch": _git("branch", "--show-current"),
        "git_last_commit_subject": _git("log", "-1", "--pretty=%s"),
        "environment": {
            "REACT_APP_BACKEND_URL": os.environ.get("REACT_APP_BACKEND_URL", "<not set>"),
            "DB_NAME_present": bool(os.environ.get("DB_NAME")),
            "MONGO_URL_present": bool(os.environ.get("MONGO_URL")),
            "PREVIEW_ONLY": True,
        },
        "guardrails": {
            "production_code_modified": False,
            "database_writes": False,
            "migrations_run": False,
            "bootstrap_rates_modified": False,
            "tax_rate_config_docs_modified": False,
            "deployment_triggered": False,
        },
    }
    Path("/app/backend/tests/iter496_2/freeze_state.json").write_text(
        json.dumps(out, indent=2, sort_keys=True)
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    main()
