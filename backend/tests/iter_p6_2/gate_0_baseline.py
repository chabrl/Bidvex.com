"""P6.2 — Gate 0 baseline freeze (READ-ONLY snapshot).

Captures git HEAD, iter482/488/489/494/495/496/496.1 test count, and the
pre-existing failure list so any regression introduced by P6.2 is
attributable.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd="/app", text=True).strip()
    except Exception as exc:
        return f"<git error: {exc}>"


BASELINE = {
    "audit": "P6.2 — Gate 0 freeze",
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "git_head": _git("rev-parse", "HEAD"),
    "git_branch": _git("branch", "--show-current"),
    "regression_suites": [
        "iter482", "iter488", "iter489",
        "iter494", "iter495", "iter496", "iter496_1",
    ],
    "baseline_totals": {
        "collected": 262,
        "passed": 259,
        "failed": 3,
    },
    "preexisting_failures": [
        "tests/iter482/test_mcp_tool_descriptions.py::test_all_tools_have_bidvex_platform_prefix_en_via_jsonrpc",
        "tests/iter482/test_mcp_tool_descriptions.py::test_all_tools_have_bidvex_platform_prefix_en_via_legacy_rest",
        "tests/iter482/test_p61_real_stripe_reconciliation.py::TestRealStripeReconciliation::test_full_real_stripe_reconciliation",
    ],
    "preexisting_failures_relationship_to_tax": "NONE — all 3 unrelated (MCP tool description formatting and real-Stripe live network reconciliation).",
    "p6_1_1_evidence_intact": True,
    "guardrails": {
        "deployment_triggered": False,
        "stripe_credentials_touched": False,
        "database_writes": False,
    },
    "notes": (
        "P6.2 target: reduce RED findings without regressing the 259 "
        "green tests. Any of the 3 baseline failures must remain "
        "unchanged (not now-passing, not now-failing-for-a-new-reason)."
    ),
}

if __name__ == "__main__":
    Path("/app/backend/tests/iter_p6_2/gate_0_baseline.json").parent.mkdir(exist_ok=True)
    Path("/app/backend/tests/iter_p6_2/gate_0_baseline.json").write_text(
        json.dumps(BASELINE, indent=2, sort_keys=True)
    )
    print(json.dumps(BASELINE, indent=2, sort_keys=True))
