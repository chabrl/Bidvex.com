"""
iter334 — Audio format bridge between Twilio Media Streams and Gemini Live.

Twilio Media Streams:  µ-law encoded, 8 kHz mono, base64 in JSON frames.
Gemini Live input:     PCM 16-bit signed little-endian, 16 kHz mono.
Gemini Live output:    PCM 16-bit signed little-endian, 24 kHz mono.

We use Python's stdlib `audioop` module (compiled C, sub-millisecond
per chunk) for both operations. No numpy/scipy required.

Note: `audioop` was removed from Python's stdlib in 3.13. This module
defensively imports the drop-in `audioop-lts` replacement if the
stdlib version is missing so we do not have to touch requirements.txt
if the runtime is later upgraded.
"""
from __future__ import annotations

try:
    import audioop  # Python 3.11 / 3.12 stdlib
except ImportError:  # pragma: no cover — only on Python ≥3.13
    import audioop_lts as audioop  # type: ignore[import-not-found]


# ─── Twilio → Gemini ──────────────────────────────────────────────────

def twilio_mulaw_to_gemini_pcm16(mulaw_8k_bytes: bytes) -> bytes:
    """Decode 8 kHz µ-law from Twilio and up-sample to 16 kHz PCM16 for Gemini.

    Args:
        mulaw_8k_bytes: raw µ-law bytes as decoded from Twilio's base64
            `media.payload` (1 byte per sample at 8 kHz).

    Returns:
        16 kHz PCM 16-bit signed little-endian bytes ready to feed into
        Gemini's `audio/pcm;rate=16000` blob.
    """
    if not mulaw_8k_bytes:
        return b""
    pcm16_8k = audioop.ulaw2lin(mulaw_8k_bytes, 2)
    pcm16_16k, _state = audioop.ratecv(pcm16_8k, 2, 1, 8000, 16000, None)
    return pcm16_16k


# ─── Gemini → Twilio ──────────────────────────────────────────────────

def gemini_pcm16_to_twilio_mulaw(pcm16_24k_bytes: bytes) -> bytes:
    """Down-sample 24 kHz PCM16 from Gemini and encode to 8 kHz µ-law for Twilio.

    Args:
        pcm16_24k_bytes: 24 kHz PCM 16-bit signed little-endian bytes as
            emitted by Gemini's Live API `inline_data.data`.

    Returns:
        Raw µ-law bytes (1 byte per sample at 8 kHz) ready to be
        base64-encoded and shipped inside Twilio's `media.payload`.
    """
    if not pcm16_24k_bytes:
        return b""
    pcm16_8k, _state = audioop.ratecv(pcm16_24k_bytes, 2, 1, 24000, 8000, None)
    mulaw_8k = audioop.lin2ulaw(pcm16_8k, 2)
    return mulaw_8k


# ─── Round-trip sanity helper (used only in tests) ───────────────────

def mulaw_roundtrip_length(mulaw_bytes: bytes) -> int:
    """Return the length of a mulaw→PCM(16k)→PCM(8k)→mulaw round trip.

    This exists purely for regression tests — it validates that the
    resampler chain preserves the sample count within the expected
    down-sampling ratio (approximately 1:1 for a full round trip).
    """
    pcm16 = twilio_mulaw_to_gemini_pcm16(mulaw_bytes)
    pcm16_8k, _ = audioop.ratecv(pcm16, 2, 1, 16000, 8000, None)
    mulaw = audioop.lin2ulaw(pcm16_8k, 2)
    return len(mulaw)
