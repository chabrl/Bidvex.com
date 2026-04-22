#!/usr/bin/env python3
"""
Add clicktracking=off to every <a> tag in every email template.
SendGrid honors this attribute and will NOT rewrite the URL even when
global click tracking is enabled in the account settings.

Idempotent: running it multiple times has no extra effect.
"""
import re
import sys
from pathlib import Path

ROOTS = [
    Path("/app/backend/sendgrid_templates"),
    Path("/app/email_templates"),
]

# Match any <a ...> opening tag (case-insensitive, across newlines).
# We intentionally do NOT touch </a> closing tags.
ANCHOR_RE = re.compile(r"<a\b([^>]*)>", re.IGNORECASE | re.DOTALL)

def inject(attrs: str) -> str:
    """Inject clicktracking=off into a tag's attribute string if missing."""
    # Already present (case-insensitive)? → no-op
    if re.search(r"\bclicktracking\s*=", attrs, re.IGNORECASE):
        return attrs
    # Append with a single leading space, collapsing trailing whitespace
    return attrs.rstrip() + " clicktracking=off"

def process(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    replaced = 0

    def _sub(m: re.Match) -> str:
        nonlocal replaced
        new_attrs = inject(m.group(1))
        if new_attrs != m.group(1):
            replaced += 1
        return f"<a{new_attrs}>"

    new_text = ANCHOR_RE.sub(_sub, original)
    if new_text != original:
        path.write_text(new_text, encoding="utf-8")
    return replaced

def main() -> int:
    total_files = 0
    total_tags = 0
    files_changed = 0
    for root in ROOTS:
        if not root.exists():
            print(f"[warn] missing root: {root}")
            continue
        for p in root.rglob("*.html"):
            total_files += 1
            before = p.read_text(encoding="utf-8")
            changed = process(p)
            after = p.read_text(encoding="utf-8")
            total_tags += changed
            if before != after:
                files_changed += 1
                print(f"  [+{changed:>3} tags]  {p.relative_to(Path('/app'))}")
    print()
    print(f"Files scanned : {total_files}")
    print(f"Files changed : {files_changed}")
    print(f"<a> tags updated : {total_tags}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
