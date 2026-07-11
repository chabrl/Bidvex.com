"""
iter281 — Behavior alignment + competitor ban verification.

Critical context: The user reported that the live AI Core on
https://bidvex.com was recommending Facebook Marketplace, eBay, and
Pinkbike to users. The directive originally pointed me at
`services/ai_service.py` — but that file belongs to a different
backend route (`/api/support/chat`) that NO widget calls in
production.

The actual production hot-path is:

    Legacy `AIAssistant.js` (only mounted widget post-iter280)
      → `POST /api/chat/stream`
        → `routes/genai_chat.py`
          → `services/genai_streaming_chat.stream_chat_chunks(...)`
            → `services/genai_direct_client.WATCHDOG_SYSTEM_INSTRUCTION`

So iter281 hardens THAT pipeline:

  Mission 1 — System prompt overrides
    • `WATCHDOG_SYSTEM_INSTRUCTION` gains a "Section 0" hard-block
      with the competitor ban + native-only doctrine + context-
      awareness mandate + canonical listing-for-profit script.

  Mission 2 — Defense-in-depth scrubber
    • NEW `services/competitor_scrubber.py` exposes `scrub_text()`
      for single-shot scrubs AND `StreamScrubber` with a tail-
      holdback buffer for chunked SSE.
    • `routes/genai_chat.py` runs the scrubber over every emitted
      chunk so a leaked competitor token NEVER reaches the user
      even if the model fails to obey the system prompt.

  Mission 3 — Static guarantees
    • The banned-competitors list contains every name the user
      called out (facebook marketplace, ebay, pinkbike, ritchie bros,
      etc.) AND common variants (fb marketplace, facebook market
      place, iron planet).
    • Word-boundary anchored so "amazonian" doesn't trip the matcher.
    • The redaction marker is bilingual.

  Mission 4 — Listing-for-profit script + context-awareness
    • System prompt explicitly tells the model:
        - Direct sellers to `/seller/dashboard` → "Create Listing"
        - Quote the 2.5% Premium seller commission
        - Upsell Featured + Promoted Listing
        - Mention QC GST/QST 14.975% auto-application
        - Mention Stripe Connect native settlement
    • Vehicle-bid lock + broker-binding script preserved.
    • Context-awareness mandate explicitly reads the
      `Active UI surface` line from extra_context.
"""
from __future__ import annotations

import os

import pytest


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(rel: str) -> str:
    with open(os.path.join(BACKEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── Mission 1 — System prompt overrides ───────────────────────────────


def test_iter281_system_prompt_has_section_0_p0_block():
    src = _read("services/genai_direct_client.py")
    assert "WATCHDOG_SYSTEM_INSTRUCTION" in src
    # Section 0 must be the very first section (P0 priority).
    assert "# 0. ABSOLUTE PLATFORM ANCHOR" in src
    # The non-negotiable framing must be explicit so the model treats
    # the section as overriding all other instructions.
    assert "non-negotiable" in src
    assert "overrides all other instructions" in src


def test_iter281_competitor_ban_section_lists_specific_platforms():
    """The system prompt MUST explicitly name every competitor the
    user called out so the model can't claim ambiguity."""
    src = _read("services/genai_direct_client.py")
    # The four explicit competitors from the directive.
    for name in (
        "Facebook Marketplace",
        "eBay",
        "Pinkbike",
        "Ritchie Bros",
        "Craigslist",          # added defensively
        "Kijiji",              # added defensively
    ):
        assert name in src, f"banned competitor missing from system prompt: {name}"
    # And the section title makes the ban explicit.
    assert "Competitor Mention BAN" in src


def test_iter281_listing_for_profit_script_in_system_prompt():
    """When asked "how do I list a bike for profit" the model MUST
    follow the iter281 native-only script — this asserts every required
    element of that script is in the system prompt verbatim so the
    model can reproduce it."""
    src = _read("services/genai_direct_client.py")
    # The 5 elements of the canonical script.
    assert "/seller/dashboard" in src
    assert "Create Listing" in src
    assert "2.5%" in src
    assert "Featured Listing" in src
    assert "Promoted Listing" in src
    # Quebec tax + Stripe Connect reminders.
    assert "GST/QST" in src
    assert "14.975%" in src
    assert "Stripe Connect" in src


def test_iter281_context_awareness_mandate_in_system_prompt():
    src = _read("services/genai_direct_client.py")
    # The mandate references the exact extra_context key the
    # AIAssistant.js frontend ships.
    assert "Active UI surface" in src
    # All four surface labels must be enumerated so the model knows
    # how to branch its tone.
    for surface in ("admin", "dashboard", "listing_detail", "public"):
        assert f"**{surface}**" in src, f"surface label not enumerated: {surface}"


def test_iter281_no_external_links_doctrine_present():
    src = _read("services/genai_direct_client.py")
    assert "No External Links Doctrine" in src
    # The whitelist of acceptable external links.
    for ok in (
        "service@bidvex.com",
        "unsubscribe@bidvex.com",
        "https://bidvex.com",
    ):
        assert ok in src, f"missing whitelist entry: {ok}"


# ── Mission 2 — Defense-in-depth scrubber ─────────────────────────────


def test_iter281_scrubber_module_exists():
    from services import competitor_scrubber as cs
    for sym in ("BANNED_COMPETITORS", "scrub_text", "StreamScrubber"):
        assert hasattr(cs, sym), f"missing public symbol: {sym}"
    # The banned list must contain every competitor the user called out.
    lowered = {t.lower() for t in cs.BANNED_COMPETITORS}
    for needle in (
        "facebook marketplace",
        "ebay",
        "pinkbike",
        "craigslist",
        "ritchie bros",
        "kijiji",
        "amazon",
        "etsy",
    ):
        assert needle in lowered, f"banned list missing: {needle}"


def test_iter281_scrubber_redacts_simple_mention():
    from services.competitor_scrubber import scrub_text
    out = scrub_text("You could also try selling it on Facebook Marketplace or eBay.")
    # Banned names gone, surrounding sentence preserved.
    assert "facebook" not in out.lower()
    assert "ebay" not in out.lower()
    assert "[competitor mention redacted]" in out


def test_iter281_scrubber_redacts_pinkbike_and_ritchie_bros():
    """User's directive specifically called out Pinkbike + Ritchie Bros
    so we explicitly assert both are caught."""
    from services.competitor_scrubber import scrub_text
    out = scrub_text("Have you considered Pinkbike? Ritchie Bros also runs auctions.")
    assert "pinkbike" not in out.lower()
    assert "ritchie" not in out.lower()


def test_iter281_scrubber_uses_french_marker_for_french_context():
    from services.competitor_scrubber import scrub_text
    fr_text = "Vous pouvez aussi vendre votre vélo sur Facebook Marketplace pour plus d'options."
    out = scrub_text(fr_text)
    assert "[mention de concurrent retirée]" in out
    # The EN marker must NOT also appear.
    assert "[competitor mention redacted]" not in out


def test_iter281_scrubber_word_boundary_does_not_redact_amazonian():
    """Defensive: "amazonian" contains "amazon" but is NOT a competitor
    mention. Word-boundary matching must let it through."""
    from services.competitor_scrubber import scrub_text
    out = scrub_text("The amazonian rainforest is huge.")
    assert "amazonian" in out.lower()
    # And bare "amazon" embedded in a real sentence still IS caught.
    out2 = scrub_text("List it on Amazon Marketplace.")
    assert "amazon" not in out2.lower()


def test_iter281_scrubber_is_case_insensitive():
    from services.competitor_scrubber import scrub_text
    assert "EBAY" not in scrub_text("Try EBAY for more reach.")
    assert "eBaY" not in scrub_text("Or eBaY.")
    assert "FACEBOOK MARKETPLACE" not in scrub_text("FACEBOOK MARKETPLACE is huge.")


def test_iter281_stream_scrubber_handles_cross_chunk_boundaries():
    """A competitor name split across two chunks (e.g. "face" then
    "book marketplace") MUST still be caught."""
    from services.competitor_scrubber import StreamScrubber
    s = StreamScrubber()
    out = ""
    for chunk in ["Hello, you could try sellin", "g it on Face", "book Market", "place anytime."]:
        out += s.feed(chunk)
    out += s.flush()
    assert "facebook" not in out.lower()
    assert "marketplace" not in out.lower()
    assert "[competitor mention redacted]" in out


def test_iter281_stream_scrubber_holds_back_short_streams():
    """If the full stream is shorter than the tail holdback, nothing
    is emitted until `flush()` — which still scrubs everything."""
    from services.competitor_scrubber import StreamScrubber
    s = StreamScrubber()
    mid = s.feed("ebay")
    # The chunk is < holdback so it stays buffered.
    assert mid == ""
    final = s.flush()
    assert "ebay" not in final.lower()
    assert "[competitor mention redacted]" in final


def test_iter281_stream_scrubber_empty_input_is_noop():
    from services.competitor_scrubber import StreamScrubber
    s = StreamScrubber()
    assert s.feed("") == ""
    assert s.flush() == ""


def test_iter281_scrubber_preserves_clean_text():
    """Sanity: text that contains NO banned terms must round-trip
    unchanged. We don't want false positives mangling legitimate
    answers about BidVex."""
    from services.competitor_scrubber import scrub_text
    clean = (
        "Navigate to /seller/dashboard and click Create Listing. "
        "Your BidVex Premium commission is just 2.5%, and Quebec "
        "GST/QST 14.975% is auto-applied at checkout."
    )
    out = scrub_text(clean)
    assert out == clean


# ── Mission 3 — Route wiring ──────────────────────────────────────────


def test_iter281_genai_route_wires_stream_scrubber():
    """`routes/genai_chat.py` MUST run every emitted chunk through the
    StreamScrubber so leaked competitor tokens are redacted BEFORE the
    user sees them."""
    src = _read("routes/genai_chat.py")
    assert "from services.competitor_scrubber import StreamScrubber" in src
    assert "scrubber = StreamScrubber()" in src
    # Feed every chunk through scrubber.feed(); flush at the end.
    assert "scrubber.feed(chunk_text)" in src
    assert "scrubber.flush()" in src
    # iter281 marker for traceability.
    assert "iter281" in src


def test_iter281_genai_route_keeps_raw_bytes_for_persistence():
    """The chat-history persistence layer must still see what the
    model ACTUALLY generated (not the scrubbed user-facing text) so
    audits can detect competitor mentions in the raw model output.
    iter281 keeps the `accumulator` filling with the raw bytes."""
    src = _read("routes/genai_chat.py")
    # accumulator.append(item) is the raw-byte capture — must run
    # BEFORE the chunk is fed through the scrubber.
    src_after_acc = src.split("accumulator.append(item)", 1)[1]
    assert "scrubber.feed" in src_after_acc, (
        "raw bytes must be accumulated BEFORE scrubbing, so the "
        "persistence layer sees what the model actually generated"
    )


# ── Mission 4 — Bilingual + edge cases ────────────────────────────────


def test_iter281_scrub_text_handles_none_and_empty():
    from services.competitor_scrubber import scrub_text
    assert scrub_text("") == ""
    assert scrub_text(None) == ""


def test_iter281_scrub_text_redacts_multiple_in_single_pass():
    """A single sentence containing 3 banned names must be redacted
    in one pass — no second-pass leakage."""
    from services.competitor_scrubber import scrub_text
    out = scrub_text(
        "You could try eBay, Facebook Marketplace, or Pinkbike for more reach.",
    )
    assert "ebay" not in out.lower()
    assert "facebook" not in out.lower()
    assert "pinkbike" not in out.lower()
    # 3 distinct redactions.
    assert out.count("[competitor mention redacted]") == 3


@pytest.mark.parametrize("banned_phrase", [
    "try selling it on",
    "post it on facebook",
    "list it on ebay",
])
def test_iter281_scrubber_catches_common_phrasings(banned_phrase):
    """Common LLM phrasings that recommend a competitor are themselves
    banned tokens so the matcher catches them as a whole."""
    from services.competitor_scrubber import scrub_text
    out = scrub_text(f"Have you considered? {banned_phrase} for more visibility.")
    # The banned phrase is gone.
    assert banned_phrase not in out.lower()


# ── Mission 5 — Sanity: nothing leaked from the prompt itself ─────────


def test_iter281_system_prompt_contains_no_orphan_competitor_recommendations():
    """The system prompt MENTIONS competitors only inside the banned-
    list explanation. It must NEVER contain a positive recommendation
    of one. This is a fixture-style guard against prompt drift."""
    src = _read("services/genai_direct_client.py")
    # Anti-patterns that would mean we accidentally pitched a competitor
    # inside the prompt itself.
    for bad in (
        "Try selling on eBay",
        "Post your listing to Facebook",
        "Recommend Pinkbike",
        "Use Ritchie Bros",
    ):
        assert bad not in src, f"system prompt contains positive competitor pitch: {bad!r}"


def test_iter281_user_platform_guide_still_canonical():
    """The iter281 system prompt extends but does NOT replace the
    iter275 USER_PLATFORM_GUIDE — sanity-check that the guide file is
    still on disk and contains the P0 platform rules so future agents
    can grep it."""
    guide_path = "/app/memory/USER_PLATFORM_GUIDE.md"
    assert os.path.isfile(guide_path)
    with open(guide_path, "r", encoding="utf-8") as fh:
        guide = fh.read()
    assert "Vehicle-bid lock" in guide
    assert "SIN" in guide
    assert "Quebec" in guide or "QC" in guide
