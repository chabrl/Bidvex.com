"""
iter338 — Word-boundary token matching (systemic substring-bug fix).

Every keyword-list check against user content MUST use these helpers instead
of raw `token in text` substring checks. Substring matching caused P0 false
positives (e.g. Kia "rio" matching inside "Ontario"/"interior" blocked a
legitimate multi-lot auction).

Boundary rule: a token matches only when it is NOT immediately preceded or
followed by an alphanumeric character. This works for hyphenated/dotted
tokens ("f-150", "id.4", "vin:") where `\\b` misbehaves. Inputs are expected
to be lowercase.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable, Optional


@lru_cache(maxsize=2048)
def _compile(token: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])")


def has_word(text: str, token: str) -> bool:
    """True when `token` appears in `text` as a whole word/phrase."""
    if not text or not token:
        return False
    return bool(_compile(token).search(text))


def first_word_match(text: str, tokens: Iterable[str]) -> Optional[str]:
    """Return the first token that appears as a whole word/phrase, else None."""
    if not text:
        return None
    for tok in tokens:
        if tok and _compile(tok).search(text):
            return tok
    return None


def has_any_word(text: str, tokens: Iterable[str]) -> bool:
    return first_word_match(text, tokens) is not None
