"""
iter319 — BidVex Careers AI auto-screening (Claude via Emergent LLM key).

For every new applicant whose CV was successfully uploaded, we extract
text from the file, send it to Claude with a tightly-scoped JSON-only
system prompt, and persist:
  • screening.summary         (1-line semantic summary)
  • screening.recommendation  ("Yes" | "Maybe" | "No")
  • screening.raw_response    (full LLM payload, debugging only)
  • screening.completed_at    (ISO timestamp)

Admins can edit the summary after the fact — the route returns the
admin-edited value when present. The original LLM output is preserved
in `screening.llm_summary` for audit.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


SCREENING_MODEL_PROVIDER = "anthropic"
SCREENING_MODEL_NAME = "claude-sonnet-4-6"

# Hard cap on resume text we send to Claude — keeps cost predictable
# and trims noisy PDF artefacts beyond a typical 4-page CV.
RESUME_TEXT_MAX_CHARS = 12_000

SYSTEM_PROMPT = """\
You are an HR screening assistant for BidVex, an auction marketplace
that hires INDEPENDENT CONTRACTORS for outbound CALL-CENTER /
TELEMARKETING roles. Your job is to read a resume and tell the
recruiter (in ONE sentence) whether this candidate looks suitable for
an outbound-calling, client-facing sales role.

CALL CENTER / TELEMARKETING REQUIREMENT SIGNALS:
  • Prior outbound sales, inside-sales, BDR, SDR, tele-sales,
    appointment-setting, customer-success, or call-center work.
  • Bilingual French/English (BidVex operates in Quebec).
  • CRM / dialer / Salesforce / HubSpot experience.
  • Track record of quota attainment or commission income.
  • Strong written + spoken communication.

DISQUALIFIER SIGNALS:
  • Pure technical / engineering only with zero sales exposure.
  • No phone work, no client-facing experience whatsoever.

YOU MUST RESPOND WITH VALID JSON ONLY — no markdown, no prose, no
backticks around the JSON. Exact shape:

{
  "summary":         "<one neutral sentence, <= 180 chars>",
  "recommendation":  "Yes" | "Maybe" | "No",
  "key_signals":     ["<short signal>", "<short signal>"]
}

Recommendation rubric:
  Yes   — Multiple call-center/sales signals + bilingual OR strong
          communications background. Move forward.
  Maybe — Transferable skills (customer service, retail sales, account
          management) but no direct outbound-calling history.
  No    — Zero customer-facing or sales signals; clear mismatch.
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Resume → plain text ────────────────────────────────────────────────

def extract_text_from_file(file_path: Path) -> str:
    """Best-effort plain-text extraction for PDF or DOCX.
    Returns the empty string when extraction fails — we never raise to
    the caller because screening is a background nice-to-have."""
    try:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return _extract_pdf(file_path)
        if ext == ".docx":
            return _extract_docx(file_path)
        if ext == ".txt":
            return file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[screening] text extraction failed for {file_path}: {e}")
    return ""


def _extract_pdf(file_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        logger.warning(f"[screening] pypdf missing: {e}")
        return ""
    try:
        reader = PdfReader(str(file_path))
        chunks = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
                if t:
                    chunks.append(t)
            except Exception:  # noqa: BLE001
                continue
            if sum(len(c) for c in chunks) > RESUME_TEXT_MAX_CHARS * 2:
                break
        return "\n".join(chunks)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[screening] PDF extract failed: {e}")
        return ""


def _extract_docx(file_path: Path) -> str:
    try:
        import docx  # python-docx
    except ImportError as e:
        logger.warning(f"[screening] python-docx missing: {e}")
        return ""
    try:
        d = docx.Document(str(file_path))
        return "\n".join(p.text for p in d.paragraphs if p.text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[screening] DOCX extract failed: {e}")
        return ""


def _clean_text(text: str) -> str:
    # Collapse repeated whitespace (PDF artefacts), trim, cap length.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > RESUME_TEXT_MAX_CHARS:
        text = text[:RESUME_TEXT_MAX_CHARS] + "\n…[truncated]"
    return text


# ─── Claude call ────────────────────────────────────────────────────────

async def _call_claude(resume_text: str, job_title: str, job_description: str) -> Dict[str, Any]:
    """Single-shot non-streaming call. Returns the parsed JSON or a
    structured failure envelope (NEVER raises)."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {"status": "failed", "error": "EMERGENT_LLM_KEY not configured"}

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "error": f"emergentintegrations missing: {e}"}

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"screening-{uuid.uuid4().hex[:12]}",
            system_message=SYSTEM_PROMPT,
        ).with_model(SCREENING_MODEL_PROVIDER, SCREENING_MODEL_NAME)

        user_text = (
            f"JOB TITLE: {job_title}\n\n"
            f"JOB DESCRIPTION:\n{(job_description or '')[:2000]}\n\n"
            f"RESUME TEXT:\n{resume_text}\n\n"
            f"Return ONLY the JSON object."
        )
        msg = UserMessage(text=user_text)
        # Non-streaming — we just need the final string. send_message()
        # returns the assistant's text content.
        resp = await chat.send_message(msg)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[screening] Claude call failed: {e}")
        return {"status": "failed", "error": str(e)[:240]}

    return _parse_screening_json(resp)


def _parse_screening_json(raw: Any) -> Dict[str, Any]:
    """Be generous when parsing — Claude usually returns clean JSON
    but might wrap it in ```json fences. We strip those and try
    json.loads. On total failure, return a structured failure."""
    text = raw if isinstance(raw, str) else getattr(raw, "content", None) or str(raw)
    text = (text or "").strip()
    # Strip markdown fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Extract the first JSON object substring if there's wrapping prose.
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    try:
        obj = json.loads(text)
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "error": f"json parse: {e}", "raw": text[:400]}

    rec = (obj.get("recommendation") or "").strip().capitalize()
    if rec not in {"Yes", "Maybe", "No"}:
        rec = "Maybe"
    return {
        "status":         "ok",
        "summary":        (obj.get("summary") or "")[:220],
        "recommendation": rec,
        "key_signals":    list(obj.get("key_signals") or [])[:6],
        "raw":            text[:1000],
    }


# ─── Public API used by the careers route ───────────────────────────────

async def screen_applicant(
    db,
    *,
    applicant_id: str,
    job_id: str,
    cv_absolute_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the screening pipeline. Persists into `job_applicants`
    `screening` subdoc. Idempotent — re-running overwrites the
    `llm_*` keys but PRESERVES admin-edited `summary` field if set."""
    if cv_absolute_path is None or not cv_absolute_path.exists():
        result = {
            "status": "skipped", "reason": "no_cv",
            "completed_at": _now_iso(),
        }
        await db.job_applicants.update_one(
            {"id": applicant_id},
            {"$set": {"screening": result}},
        )
        return result

    resume_text = _clean_text(extract_text_from_file(cv_absolute_path))
    if not resume_text.strip():
        result = {
            "status": "skipped", "reason": "empty_text",
            "completed_at": _now_iso(),
        }
        await db.job_applicants.update_one(
            {"id": applicant_id},
            {"$set": {"screening": result}},
        )
        return result

    # Pull job context so the prompt has the title + description.
    job = await db.job_offers.find_one(
        {"id": job_id},
        {"_id": 0, "title": 1, "description_en": 1},
    )
    job_title = (job or {}).get("title") or "BidVex contractor"
    job_desc = (job or {}).get("description_en") or ""

    out = await _call_claude(resume_text, job_title, job_desc)

    # Read existing screening to preserve admin-edited summary if any.
    existing = await db.job_applicants.find_one(
        {"id": applicant_id},
        {"_id": 0, "screening": 1},
    )
    prior = (existing or {}).get("screening") or {}

    summary_value = out.get("summary", "")
    # Admins can pin a hand-edited summary by setting summary_edited=True.
    if prior.get("summary_edited"):
        summary_value = prior.get("summary") or summary_value

    payload = {
        "status":         out.get("status", "failed"),
        "summary":        summary_value,
        "llm_summary":    out.get("summary", ""),
        "recommendation": out.get("recommendation", "Maybe"),
        "key_signals":    out.get("key_signals", []),
        "error":          out.get("error"),
        "model":          f"{SCREENING_MODEL_PROVIDER}/{SCREENING_MODEL_NAME}",
        "completed_at":   _now_iso(),
        "summary_edited": prior.get("summary_edited", False),
    }
    await db.job_applicants.update_one(
        {"id": applicant_id},
        {"$set": {"screening": payload}},
    )
    return payload


__all__ = [
    "SCREENING_MODEL_PROVIDER",
    "SCREENING_MODEL_NAME",
    "extract_text_from_file",
    "screen_applicant",
]
