"""
iter281 — Competitor-mention scrubber.

Defense-in-depth scrubber for the AI Core's streaming responses. Even
with the iter281 system-prompt overrides telling the model NEVER to
mention competing platforms, we cannot fully trust LLM compliance at
the generation layer. This module applies a deterministic
post-generation scrub so a leaked competitor token NEVER reaches the
user.

The scrubber operates in TWO modes:

  • `scrub_text(text)` — non-streaming pass for the full reply.
  • `StreamScrubber()` — stateful streaming pass that buffers a tail
    overlap to catch competitor tokens split across chunk boundaries.

If a banned token is detected, the offending substring is replaced
with the canonical redaction marker "[competitor mention redacted]"
in EN or "[mention de concurrent retirée]" in FR (the FR variant is
selected when the surrounding sentence contains French accent markers
or the language hint is FR).

Banned list is intentionally explicit + redundant (e.g. both
"facebook marketplace" and "fb marketplace"). The list is case-
insensitive but word-boundary-aware so we don't accidentally redact
"amazonian" or "ebay-style".
"""
from __future__ import annotations

import re
from typing import List, Tuple


# ── Banned terms ──────────────────────────────────────────────────────
#
# Each entry is (canonical_form, optional_extra_variants). The matcher
# builds a single combined regex with word-boundary anchors.

BANNED_COMPETITORS: List[str] = [
    # Big general marketplaces
    "facebook marketplace", "facebook market place", "fb marketplace",
    "facebook groups", "facebook group",
    "ebay", "ebay motors",
    "craigslist",
    "kijiji", "kijiji autos",
    "lespac",
    "amazon", "amazon marketplace",
    "walmart marketplace",
    "etsy",
    "mercari",
    "offerup",
    "vinted",
    # Bicycle-specific
    "pinkbike",
    "bicyclebluebook", "bicycle blue book",
    "bike24",
    "bikeexchange", "bike exchange",
    # Industrial / heavy-equipment auction houses
    "ritchie bros", "ritchie brothers", "ritchiebros",
    "ironplanet", "iron planet",
    "copart",
    "manheim",
    "adesa",
    "auctionzip",
    "govdeals",
    "proxibid",
    "hibid",
    "bidsquare",
    # Auto classifieds
    "autotrader", "auto trader",
    "cargurus",
    # Aliased / generic phrasing the model sometimes hallucinates
    "try selling it on",
    "post it on facebook",
    "list it on ebay",
]


_REDACT_EN = "[competitor mention redacted]"
_REDACT_FR = "[mention de concurrent retirée]"


def _build_pattern() -> re.Pattern:
    """Build a single case-insensitive regex matching any banned term
    on word boundaries. Longest patterns first so multi-word terms are
    preferred over their substrings."""
    sorted_terms = sorted(BANNED_COMPETITORS, key=len, reverse=True)
    # Escape each term + use \b on alphanumeric edges. Some terms
    # contain spaces, which `\b` handles naturally as the alpha→space
    # boundary on both sides.
    alternatives = "|".join(re.escape(t) for t in sorted_terms)
    return re.compile(rf"\b(?:{alternatives})\b", flags=re.IGNORECASE)


_PATTERN = _build_pattern()


def _redaction_for_language(surrounding_text: str) -> str:
    """Pick EN or FR redaction marker based on the surrounding text."""
    if not surrounding_text:
        return _REDACT_EN
    # Heuristic — French accent characters mean we're in a FR context.
    if any(ch in surrounding_text for ch in "àâçéèêëîïôûùüÿœæ"):
        return _REDACT_FR
    # Common FR connective words also signal FR context.
    fr_tokens = re.findall(r"\b(?:vous|votre|nous|notre|aussi|peut|sur|une|des|les)\b",
                           surrounding_text, flags=re.IGNORECASE)
    if len(fr_tokens) >= 2:
        return _REDACT_FR
    return _REDACT_EN


def scrub_text(text: str) -> str:
    """Single-shot scrub for non-streaming responses.

    Returns the scrubbed text with every banned competitor mention
    swapped for the localized redaction marker. Safe to call on
    empty / None inputs."""
    if not text:
        return text or ""

    def _replace(match: re.Match) -> str:
        # Use a small window around the match to pick EN vs FR.
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        return _redaction_for_language(text[start:end])

    return _PATTERN.sub(_replace, text)


class StreamScrubber:
    """Stateful scrubber for chunked SSE/streaming responses.

    The bot may emit competitor terms split across chunk boundaries
    (e.g. "face" + "book marketplace"). We hold back the trailing N
    characters of every chunk in an internal buffer so the next chunk
    can be concatenated and re-scanned for cross-boundary matches.

    Usage:
        scrubber = StreamScrubber()
        for chunk in upstream_stream:
            yield scrubber.feed(chunk)
        # Always flush at the end.
        yield scrubber.flush()
    """

    # Longest banned term is ~ 24 chars ("bicyclebluebook" etc. with
    # spaces). 48 gives us 2x safety margin.
    _TAIL_HOLDBACK = 48

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, chunk: str) -> str:
        """Append `chunk` to the internal buffer, scrub everything
        SAFE to emit, and return the emittable substring. The tail
        holdback is retained for the next call."""
        if not chunk:
            return ""
        self._buf += chunk
        if len(self._buf) <= self._TAIL_HOLDBACK:
            # Not yet enough material to emit safely.
            return ""
        # Split: keep last N chars in the buffer, emit the rest scrubbed.
        emit, self._buf = self._buf[:-self._TAIL_HOLDBACK], self._buf[-self._TAIL_HOLDBACK:]
        return scrub_text(emit)

    def flush(self) -> str:
        """Final flush — scrub whatever's left in the buffer and emit
        it. Always called once at the end of the upstream stream."""
        remaining = self._buf
        self._buf = ""
        return scrub_text(remaining)


__all__ = [
    "BANNED_COMPETITORS",
    "scrub_text",
    "StreamScrubber",
]
