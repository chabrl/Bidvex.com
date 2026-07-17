#!/usr/bin/env python3
"""
iter359 — LangLink Bulk Sweep.

Migrates every `<Link>` in the frontend to `<LangLink>` so all internal
navigation respects the active language and never triggers the client-side
legacy → /en/* redirect.

Safe transformations:
  1. `import { Link, ... } from 'react-router-dom'`
       → `import { ... } from 'react-router-dom'` + insert
         `import { LangLink } from '<relative>/LangLink';`
     (If `Link` is the only named import, drop the whole line.)
  2. Every `<Link ...>` → `<LangLink ...>`
  3. Every `</Link>` → `</LangLink>`

Skipped:
  • Files inside __tests__ or with test_ in path
  • The LangLink component itself
  • Files that already import LangLink (idempotent re-run)

Emits a report to stdout: <file>: N changes / errors.
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path


FRONTEND_SRC = Path("/app/frontend/src")
LANGLINK_PATH = FRONTEND_SRC / "components" / "LangLink.jsx"


def relative_import_path(from_file: Path) -> str:
    """Compute the ES-module relative path to LangLink.jsx from `from_file`."""
    from_dir = from_file.parent.resolve()
    target = LANGLINK_PATH.resolve()
    rel = os.path.relpath(target.with_suffix(''), from_dir)
    # Ensure explicit ./ prefix
    if not rel.startswith('.'):
        rel = './' + rel
    return rel.replace(os.sep, '/')


LINK_IMPORT_RE = re.compile(
    r"^(import\s*\{\s*)([^}]+?)(\s*\}\s*from\s*['\"]react-router-dom['\"];?)\s*$",
    re.MULTILINE,
)


def _rewrite_import_line(match: re.Match) -> tuple[str, bool]:
    """
    Rewrite a `import { ... } from 'react-router-dom'` line to remove Link.
    Returns (new_line, had_link_import).
    """
    prefix, middle, suffix = match.group(1), match.group(2), match.group(3)
    parts = [p.strip() for p in middle.split(',') if p.strip()]
    had_link = 'Link' in parts
    if not had_link:
        return match.group(0), False
    parts = [p for p in parts if p != 'Link']
    if not parts:
        # No remaining named imports — drop the whole line.
        return '', True
    return f"{prefix}{', '.join(parts)}{suffix}", True


def migrate_file(path: Path) -> dict:
    """Migrate a single file. Returns stats dict."""
    src = path.read_text(encoding='utf-8')
    original = src
    stats = {"file": str(path), "link_open": 0, "link_close": 0,
             "import_dropped": False, "langlink_added": False,
             "already_had_langlink": False}

    if 'LangLink' in src and re.search(r'\bLangLink\b', src):
        # Idempotent: already migrated.
        stats["already_had_langlink"] = True

    # 1) Rewrite the import statement — remove Link, keep the rest.
    had_link_import = False

    def _sub(m):
        nonlocal had_link_import
        new_line, hl = _rewrite_import_line(m)
        if hl:
            had_link_import = True
        return new_line

    src = LINK_IMPORT_RE.sub(_sub, src)

    # 2) Replace <Link with <LangLink (JSX-open only — not the word "Link" elsewhere).
    #    Require a whitespace/end after "Link" to avoid touching LangLink or LinkedIn.
    def _open_sub(m):
        stats["link_open"] += 1
        return "<LangLink" + m.group(1)

    src = re.sub(r"<Link(\s|>|/)", _open_sub, src)

    # 3) Replace </Link> with </LangLink>
    def _close_sub(m):
        stats["link_close"] += 1
        return "</LangLink>"

    src = re.sub(r"</Link>", _close_sub, src)

    # 4) If we did any replacements or dropped an import, insert the LangLink import.
    needs_import = (stats["link_open"] > 0 or stats["link_close"] > 0)
    if needs_import and not re.search(r"import\s*\{[^}]*\bLangLink\b[^}]*\}\s*from", src):
        rel = relative_import_path(path)
        # Insert directly after the last existing import statement (or at top).
        import_lines = [i for i, line in enumerate(src.splitlines())
                        if line.startswith('import ') or line.startswith('const ') and 'require(' in line]
        insertion_line = f"import {{ LangLink }} from '{rel}';"
        # Find the position after the last import.
        lines = src.splitlines(keepends=True)
        last_import_idx = -1
        for i, line in enumerate(lines):
            if re.match(r"^\s*import\s", line):
                last_import_idx = i
        if last_import_idx >= 0:
            lines.insert(last_import_idx + 1, insertion_line + "\n")
            src = "".join(lines)
        else:
            src = insertion_line + "\n" + src
        stats["langlink_added"] = True

    stats["import_dropped"] = had_link_import

    if src != original:
        path.write_text(src, encoding='utf-8')
        stats["written"] = True
    else:
        stats["written"] = False
    return stats


def main():
    js_files = list(FRONTEND_SRC.rglob("*.js")) + list(FRONTEND_SRC.rglob("*.jsx"))
    total_files = 0
    total_open = 0
    total_close = 0
    skipped = []
    for path in js_files:
        s = str(path)
        if "__tests__" in s or "/test_" in s or "test." in path.name:
            continue
        if path.name == "LangLink.jsx" or path.name == "urlMap.js" or "LanguageContext" in path.name:
            skipped.append(str(path))
            continue
        # Skip if the file doesn't mention Link at all.
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if "react-router-dom" not in text:
            continue
        if not re.search(r"<Link\b|import\s*\{[^}]*\bLink\b[^}]*react-router-dom", text):
            continue
        stats = migrate_file(path)
        if stats["written"]:
            total_files += 1
            total_open += stats["link_open"]
            total_close += stats["link_close"]
            rel = str(path).replace("/app/frontend/src/", "")
            print(f"[migrate] {rel}: {stats['link_open']} open, {stats['link_close']} close"
                  + (" (+import)" if stats["langlink_added"] else "")
                  + (" (-Link import)" if stats["import_dropped"] else ""))
    print(f"\n[iter359] Sweep complete: {total_files} files, {total_open} <Link> + {total_close} </Link> replaced.")
    if skipped:
        print(f"[iter359] Skipped {len(skipped)} infra file(s): {[Path(s).name for s in skipped]}")


if __name__ == "__main__":
    main()
