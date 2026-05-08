#!/usr/bin/env python3
"""
iter201 — Phase 3 / 3E — CEO verification-checklist runner.

Wraps the pytest checklist suite into a script the compliance team can run
on demand.

Usage:
    cd /app/backend && python scripts/verify_phase3_checklist.py
"""
import os
import subprocess
import sys


def main() -> int:
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_path = os.path.join(backend_dir, "tests", "test_iter201_phase3_checklist.py")
    if not os.path.exists(test_path):
        print(f"ERROR: checklist tests not found at {test_path}")
        return 2
    print("=" * 70)
    print(" iter201 — Phase 3 — CEO Verification Checklist")
    print("=" * 70)
    return subprocess.call(["python", "-m", "pytest", test_path, "-v", "--tb=short"], cwd=backend_dir)


if __name__ == "__main__":
    sys.exit(main())
