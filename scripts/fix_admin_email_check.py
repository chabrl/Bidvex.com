#!/usr/bin/env python3
"""
Replace every standalone `endswith("@bidvex.com")` admin check with a proper
role-based check. Skips lines that already include an `or role` clause
(those compound checks were already accepting non-bidvex admins correctly).
"""
import re
from pathlib import Path

TARGETS = [
    "/app/backend/routes/site_mode.py",
    "/app/backend/routes/messages.py",
    "/app/backend/routes/trust_safety.py",
    "/app/backend/routes/misc.py",
    "/app/backend/routes/subscriptions.py",
    "/app/backend/routes/email_marketing_ext.py",
    "/app/backend/routes/site_config.py",
]

# AND-only form: `    if not current_user.email.endswith("@bidvex.com"):`
# (may have leading whitespace; may or may not have trailing colon/newline)
PATTERN_ALONE = re.compile(
    r'^(?P<indent>[ \t]*)if not current_user\.email\.endswith\("@bidvex\.com"\):',
    re.MULTILINE,
)

# Compound "role AND (not endswith)" form where endswith is an extra gate:
#   `if current_user.role != 'admin' and not current_user.email.endswith("@bidvex.com"):`
# Make these pure role checks (role check is the source of truth).
PATTERN_COMPOUND = re.compile(
    r'^(?P<indent>[ \t]*)if current_user\.role (?P<op>!=|not in) '
    r'(?P<expected>\'admin\'|"admin"|\["admin", ?"super_admin"\]|\["admin", ?"superadmin"\]) '
    r'and not current_user\.email\.endswith\("@bidvex\.com"\):',
    re.MULTILINE,
)

REPLACEMENT_ALONE = (
    r'\g<indent>if getattr(current_user, "role", None) not in ("admin", "superadmin"):'
)

def replace_compound(m):
    indent = m.group("indent")
    op = m.group("op")
    expected = m.group("expected")
    # Normalize: just use the role check without endswith
    return f'{indent}if current_user.role {op} {expected}:'

total_a = total_c = 0
for p in TARGETS:
    path = Path(p)
    if not path.exists():
        print(f"skip missing: {p}")
        continue
    text = path.read_text()
    new, a = PATTERN_ALONE.subn(REPLACEMENT_ALONE, text)
    new, c = PATTERN_COMPOUND.subn(replace_compound, new)
    if a or c:
        path.write_text(new)
        print(f"  {path.name}: alone={a}  compound={c}")
        total_a += a
        total_c += c

print(f"\nTotal: standalone fixes={total_a}, compound simplifications={total_c}")
