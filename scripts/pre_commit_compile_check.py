#!/usr/bin/env python3
"""
iter310 — Pre-commit syntax / compile gate
==========================================
Ultra-fast Python compilation check: walks `/app/backend` (and any
other Python tree below the repo root) and runs `py_compile` on every
.py file. If ANY file fails to compile, the hook prints the file and
the error and exits non-zero — the commit is blocked.

Target latency: <0.5s on this repo (~300 backend .py files).

Catches:
  • IndentationError (the iter309 P0)
  • SyntaxError
  • Unterminated strings / mismatched brackets

Install:
  python /app/scripts/pre_commit_compile_check.py --install

Run manually:
  python /app/scripts/pre_commit_compile_check.py
"""
from __future__ import annotations

import argparse
import os
import py_compile
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


REPO_ROOT = Path("/app")
SCAN_DIRS = ("backend", "scripts")
EXCLUDE_PARTS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}


def _iter_py_files() -> list[Path]:
    files: list[Path] = []
    for top in SCAN_DIRS:
        root = REPO_ROOT / top
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if any(part in EXCLUDE_PARTS for part in p.parts):
                continue
            files.append(p)
    return files


def _check_one(path: Path) -> tuple[bool, str]:
    try:
        py_compile.compile(str(path), doraise=True)
        return True, ""
    except py_compile.PyCompileError as exc:  # syntax / indentation
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true",
                        help="Install as .git/hooks/pre-commit and exit.")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress per-file success output.")
    args = parser.parse_args()

    if args.install:
        return _install_hook()

    start = time.perf_counter()
    files = _iter_py_files()
    failures: list[tuple[Path, str]] = []
    # Parallel scan — py_compile is CPU-bound, hits <0.5s on a 4-core pod
    workers = min(8, (os.cpu_count() or 2))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_check_one, files, chunksize=16))
    for f, (ok, err) in zip(files, results):
        if not ok:
            failures.append((f, err))

    elapsed = time.perf_counter() - start

    if failures:
        print(f"\n  ✗ COMPILE CHECK FAILED ({len(failures)}/{len(files)} files)\n")
        for f, err in failures:
            print(f"    × {f.relative_to(REPO_ROOT)}")
            for line in err.splitlines()[:8]:
                print(f"        {line}")
            print()
        print(f"  scanned {len(files)} files in {elapsed*1000:.0f}ms — BLOCKED")
        return 1

    if not args.quiet:
        print(f"  ✓ {len(files)} files compile cleanly ({elapsed*1000:.0f}ms)")
    return 0


def _install_hook() -> int:
    hook_path = REPO_ROOT / ".git" / "hooks" / "pre-commit"
    if not (REPO_ROOT / ".git").is_dir():
        print(f"  ✗ {REPO_ROOT}/.git not found — cannot install hook")
        return 1
    body = (
        "#!/usr/bin/env bash\n"
        "# iter310 — block commits with syntax/indentation errors\n"
        "python /app/scripts/pre_commit_compile_check.py --quiet\n"
    )
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(body)
    os.chmod(hook_path, 0o755)
    print(f"  ✓ pre-commit hook installed at {hook_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
