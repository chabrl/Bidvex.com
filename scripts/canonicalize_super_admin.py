#!/usr/bin/env python3
"""
Canonicalize 'superadmin' → 'super_admin' across backend code. Matches the
convention already used by routes/auth.py when writing role to the DB.
"""
import re
from pathlib import Path

ROOTS = ["/app/backend/routes", "/app/backend/services"]

# Replace only the bare-string occurrences, not variable names.
# Match "superadmin" or 'superadmin' (both quote styles), never inside another word.
PATTERNS = [
    (re.compile(r'"superadmin"'), '"super_admin"'),
    (re.compile(r"'superadmin'"), "'super_admin'"),
]

total = 0
files_touched = 0
for root in ROOTS:
    for p in Path(root).rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        original = text
        for pat, repl in PATTERNS:
            text = pat.sub(repl, text)
        if text != original:
            p.write_text(text, encoding="utf-8")
            diffs = sum(1 for _ in re.finditer(r'"super_admin"|\'super_admin\'', text)) \
                   - sum(1 for _ in re.finditer(r'"super_admin"|\'super_admin\'', original))
            files_touched += 1
            total += diffs
            print(f"  {p.relative_to('/app')}: +{diffs} replacements")

print(f"\nTouched {files_touched} files, {total} string replacements (superadmin → super_admin)")
