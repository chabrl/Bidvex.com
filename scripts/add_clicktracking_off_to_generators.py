#!/usr/bin/env python3
"""
Add clicktracking=off to every `<a ... href=...>` literal in Python
generator scripts so future template regeneration preserves the attribute.
"""
import re
from pathlib import Path

TARGETS = [
    Path("/app/backend/sendgrid_templates/generate_templates.py"),
    Path("/app/backend/sendgrid_templates/generate_bilingual_templates.py"),
    Path("/app/backend/sendgrid_templates/generate_all_bilingual_templates.py"),
    Path("/app/backend/sendgrid_templates/draft_invoice_template.py"),
]

# Match `<a ` opening tag inside a Python string (single or double quoted),
# only when clicktracking=off is not already present.
ANCHOR_RE = re.compile(r"<a\b([^>]*)>", re.IGNORECASE | re.DOTALL)

def inject(attrs: str) -> str:
    if re.search(r"\bclicktracking\s*=", attrs, re.IGNORECASE):
        return attrs
    return attrs.rstrip() + " clicktracking=off"

total = 0
for path in TARGETS:
    if not path.exists():
        print(f"[skip] {path}")
        continue
    text = path.read_text(encoding="utf-8")
    changed = 0

    def _sub(m: re.Match) -> str:
        global changed
        new_attrs = inject(m.group(1))
        if new_attrs != m.group(1):
            changed += 1
        return f"<a{new_attrs}>"

    new_text = ANCHOR_RE.sub(_sub, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        total += changed
        print(f"  [+{changed:>3}]  {path.relative_to(Path('/app'))}")
print(f"\nTotal <a> literals updated in generator scripts: {total}")
