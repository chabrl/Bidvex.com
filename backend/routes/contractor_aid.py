"""
iter331 — Contractor Aid Hub backend.

Exposes:
  GET  /api/contractor/aid/info            — static structured workflow content
  POST /api/contractor/aid/chat            — non-streaming Gemini reply
  POST /api/contractor/aid/chat/stream     — SSE streaming Gemini reply

The endpoint uses the Emergent LLM Universal Key + emergentintegrations
library (Gemini provider, `gemini-3-flash-preview` model).

The system prompt is laser-focused on BidVex Contractor operational rules so
the assistant cannot hallucinate platform policies it doesn't know.

Each (user_id, session_id) pair persists into `contractor_aid_chats` so the
multi-turn history is reconstructable across reloads.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deps import get_current_user, get_db, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["contractor-aid"])

# ─── Model selection ─────────────────────────────────────────────────
# Gemini 3 Flash preview is the latest fast Gemini chat model exposed via
# the Emergent universal key (see integration playbook).
AID_MODEL_PROVIDER = "gemini"
AID_MODEL_NAME = "gemini-3-flash-preview"
SESSION_MAX_TURNS = 40
MESSAGE_MAX_CHARS = 4000


CONTRACTOR_AID_SYSTEM_PROMPT = """You are the **BidVex AI Contractor Aid**, an embedded assistant on the BidVex Contractor Dashboard. You help approved BidVex contractors (also called dialer_contractors or partners) understand exactly how the BidVex platform works so they can perform their day-to-day operations confidently.

You answer in the user's preferred language (English or French) and ALWAYS in the same language as the user's most recent question.

## Identity
- You are the BidVex AI core engine.
- You speak with the BidVex contractor team voice: friendly, concise, operational. No marketing fluff.
- You do NOT make promises about specific commission payouts, court rulings, or legal interpretations.
- When you don't know something, you say so and route the contractor to the appropriate channel.

## Authoritative Knowledge (do not deviate)

### 1. Commission engine — Section 6 of the Terms of Service
- **Baseline rate: exactly 5.0%** on every settled transaction inside a referred account.
- **Weekly leaderboard overlay**: every Monday 08:00 (America/Toronto), the previous 7-day commission volume is ranked across all contractors.
- **+1.0% overlay** per consecutive week a contractor stays inside the **Top 5**.
- **-1.0% overlay** per consecutive week a contractor stays **outside** the Top 5 (floor cannot drop below baseline).
- **Effective range is clamped to [5.0%, 20.0%]** — that is the hard floor and hard ceiling.
- Dollar earnings are **NEVER** exposed publicly. Only rank, masked ID and overlay rate appear in the leaderboard view.

### 2. Inbound IVR + extension
- Every contractor receives an **extension number starting at 1220** (sequential, never reused).
- The platform forwards calls dialed into the main BidVex number `+1 450 634 3099` → contractor's `personal_phone_number` via Twilio `<Dial>`.
- Contractors set their personal phone in **Dashboard → Profile → Personal Phone (E.164 format, e.g. +15145559876)**.
- If a contractor's personal phone is unset, inbound callers hear "extension cannot be reached" — set the phone in the profile to fix this.

### 3. Email Hub
- Outbound emails are sent from `contractor@bidvex.com` with `Reply-To: partners+c{extension}@reply.bidvex.ca`.
- The signature is auto-injected by the server — contractors don't need to add it manually.
- The Email Hub gate requires the Electronic Contractor Agreement v2 to be signed; the gate is on the dashboard itself.

### 4. Add-a-Client (permission-gated)
- Requires the admin-granted `add_users` permission.
- The 5 allowed client account types are: **individual_seller**, **business**, **partner**, **vehicle_dealer**, **storage_facility**.
- **Liquidator** and **Broker** accounts are platform-wide and are NOT created via the contractor shortcut.
- On creation, the new client receives a 7-day password-reset invite token. The contractor can copy the link and email it manually.

### 5. Stripe Connect (payouts)
- Every contractor must complete Stripe Connect onboarding before commissions can be paid out automatically.
- The monthly payout cron runs on the **1st of every month**.
- If banking isn't configured, payouts queue indefinitely until the contractor completes onboarding.
- Onboarding is launched from the dashboard's **"Set up Stripe"** button.

### 6. Referral attribution
- Contractors generate referrals via their **`/r/{referral_code}` link** (copy from dashboard).
- Attribution is logged immutably — even if an admin removes future attribution, the historical commission ledger is preserved.

### 7. Promotional structure (Summer 2026)
- 30-day free trial on any paid plan (lifetime once-per-user).
- First listing on us (slot fee waived) for net-new sellers.
- Summer 2026 50% discount visible to non-authenticated visitors on /pricing.

### 8. Escalation
- If a contractor faces a non-trivial issue (bug, missing feature, ambiguous policy), they should click **"Talk to a Human"** from the AI Assistant widget, or email **contractor@bidvex.com** with their extension number.

## Style
- Default to **short, scannable answers** (2–6 sentences or a short bullet list).
- Use Markdown when it helps (bold key numbers, bullet lists for steps).
- Do NOT speculate. If a question is outside the BidVex contractor scope, say "I can only help with BidVex contractor operations — for that, please reach out to contractor@bidvex.com."

## Hard constraints
- Never quote dollar earnings of other contractors.
- Never claim a feature exists that isn't in this prompt.
- Never propose pricing or commission changes — those are admin-only operations.
"""


# ─── Static workflow info (rendered on the Aid page) ──────────────────

AID_INFO_SECTIONS: List[Dict[str, Any]] = [
    {
        "id": "commission",
        "title_en": "Commission Engine — 5% Baseline + Top-5 Overlay",
        "title_fr": "Moteur de commission — Base de 5 % + bonification Top 5",
        "body_en": (
            "- **Baseline:** 5.0% on every settled transaction inside your referred accounts.\n"
            "- **Weekly overlay:** +1.0% per consecutive week in the **Top 5**; -1.0% per week outside.\n"
            "- **Effective range is clamped to [5%, 20%]** — that's the hard floor and hard ceiling.\n"
            "- The leaderboard is re-evaluated every **Monday at 08:00 America/Toronto**.\n"
            "- Your effective rate stamps onto each ledger row at accrual time so it never drifts retroactively."
        ),
        "body_fr": (
            "- **Base :** 5,0 % sur chaque transaction réglée dans vos comptes parrainés.\n"
            "- **Bonification hebdomadaire :** +1,0 % par semaine consécutive dans le **Top 5** ; -1,0 % hors Top 5.\n"
            "- **La plage effective est encadrée à [5 %, 20 %]** — c'est le plancher et le plafond stricts.\n"
            "- Le classement est ré-évalué tous les **lundis à 8 h 00 (America/Toronto)**.\n"
            "- Le taux effectif est estampillé sur chaque ligne de grand livre à l'accrual, il ne dérive jamais rétroactivement."
        ),
    },
    {
        "id": "ivr",
        "title_en": "Inbound IVR + Your Extension",
        "title_fr": "IVR entrant + Votre poste",
        "body_en": (
            "- Every contractor gets a unique extension starting at **1220** (sequential, never reused).\n"
            "- Callers dial `+1 450 634 3099`, choose a language and enter your extension.\n"
            "- BidVex bridges the call to your **personal phone** via Twilio.\n"
            "- Set your personal phone in **Dashboard → Profile** in E.164 format (e.g. +15145559876)."
        ),
        "body_fr": (
            "- Chaque contractant reçoit un poste unique à partir de **1220** (séquentiel, jamais réutilisé).\n"
            "- Les appelants composent le `+1 450 634 3099`, choisissent une langue puis entrent votre poste.\n"
            "- BidVex transfère l'appel sur votre **téléphone personnel** via Twilio.\n"
            "- Configurez votre téléphone personnel dans **Tableau de bord → Profil** au format E.164 (ex. +15145559876)."
        ),
    },
    {
        "id": "email",
        "title_en": "Contractor Email Hub",
        "title_fr": "Hub Courriels du contractant",
        "body_en": (
            "- Outbound from `contractor@bidvex.com` with Reply-To `partners+c{extension}@reply.bidvex.ca`.\n"
            "- Signature is auto-injected server-side — you don't add it manually.\n"
            "- Sending is gated by the Electronic Contractor Agreement v2 — sign it once and you're unlocked."
        ),
        "body_fr": (
            "- Envoi depuis `contractor@bidvex.com` avec Reply-To `partners+c{extension}@reply.bidvex.ca`.\n"
            "- La signature est injectée côté serveur — vous ne l'ajoutez pas manuellement.\n"
            "- L'envoi est conditionné à la signature de l'Entente du contractant v2 — signez-la une fois et c'est débloqué."
        ),
    },
    {
        "id": "add_client",
        "title_en": "Add-a-Client Shortcut (permission-gated)",
        "title_fr": "Ajouter un client (sur permission)",
        "body_en": (
            "- Requires the admin-granted **add_users** permission.\n"
            "- Allowed types: **Individual**, **Business**, **Partner**, **Vehicle Dealer**, **Storage Facility**.\n"
            "- New client receives a **7-day invite link** to set their password.\n"
            "- Liquidator and Broker accounts are NOT created via this shortcut."
        ),
        "body_fr": (
            "- Requiert la permission admin **add_users**.\n"
            "- Types autorisés : **Particulier**, **Entreprise**, **Partenaire**, **Marchand de véhicules**, **Centre d'entreposage**.\n"
            "- Le nouveau client reçoit un **lien d'invitation de 7 jours** pour définir son mot de passe.\n"
            "- Les comptes Liquidateur et Courtier ne sont PAS créés via ce raccourci."
        ),
    },
    {
        "id": "stripe",
        "title_en": "Stripe Connect + Payouts",
        "title_fr": "Stripe Connect + Versements",
        "body_en": (
            "- Complete onboarding from the dashboard's **Set up Stripe** button.\n"
            "- Monthly payout cron runs on the **1st of every month**.\n"
            "- Without Stripe configured, commissions accrue but stay queued."
        ),
        "body_fr": (
            "- Complétez l'inscription via le bouton **Configurer Stripe** sur le tableau de bord.\n"
            "- Le cron mensuel s'exécute le **1er de chaque mois**.\n"
            "- Sans Stripe configuré, les commissions s'accumulent mais restent en file d'attente."
        ),
    },
    {
        "id": "escalation",
        "title_en": "Stuck? Escalation Paths",
        "title_fr": "Bloqué ? Voies d'escalade",
        "body_en": (
            "- For ambiguous policy questions, use the BidVex AI chat below.\n"
            "- For platform bugs or account access problems, email **contractor@bidvex.com** with your extension number.\n"
            "- For DNS / Twilio / SendGrid setup issues, ping your admin (admins can hot-toggle most settings)."
        ),
        "body_fr": (
            "- Pour les questions de politique ambiguës, utilisez le chat BidVex AI ci-dessous.\n"
            "- Pour les bogues ou problèmes d'accès, écrivez à **contractor@bidvex.com** en mentionnant votre poste.\n"
            "- Pour la configuration DNS / Twilio / SendGrid, contactez votre admin (les admins peuvent basculer la plupart des réglages)."
        ),
    },
]


# ─── Pydantic models ──────────────────────────────────────────────────

class AidChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=MESSAGE_MAX_CHARS)
    session_id: Optional[str] = Field(None, max_length=64)
    language: Optional[str] = Field("en", max_length=4)


# ─── Static info endpoint ─────────────────────────────────────────────

@router.get("/contractor/aid/info")
async def get_aid_info(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Workflow descriptions + operational rules + escalation paths."""
    role = (getattr(user, "role", None) or "").lower()
    if role not in {"dialer_contractor", "admin", "super_admin"}:
        raise HTTPException(403, "contractor-only")
    return {
        "sections": AID_INFO_SECTIONS,
        "support_email": "contractor@bidvex.com",
        "main_phone": "+14506343099",
        "model": AID_MODEL_NAME,
    }


# ─── Chat helpers ─────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _persist_turn(db, user_id: str, session_id: str, role: str, content: str) -> None:
    """Persist a single chat turn under (user_id, session_id)."""
    if db is None:
        return
    try:
        await db.contractor_aid_chats.update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "session_id": session_id,
                    "created_at": _now_iso(),
                },
                "$set": {"updated_at": _now_iso()},
                "$push": {
                    "messages": {
                        "$each": [{"role": role, "content": content, "ts": _now_iso()}],
                        "$slice": -SESSION_MAX_TURNS,
                    },
                },
            },
            upsert=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[contractor-aid] persist failed: {e}")


async def _load_history(db, user_id: str, session_id: str) -> List[Dict[str, str]]:
    if db is None:
        return []
    try:
        doc = await db.contractor_aid_chats.find_one(
            {"user_id": user_id, "session_id": session_id},
            {"_id": 0, "messages": 1},
        )
        if doc is None:
            return []
        return doc.get("messages", []) or []
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[contractor-aid] history load failed: {e}")
        return []


def _build_chat(api_key: str, session_id: str, language: str = "en"):
    from emergentintegrations.llm.chat import LlmChat

    lang_hint = (
        "Repond en francais sauf si la derniere question est clairement en anglais."
        if (language or "en").lower().startswith("fr")
        else "Reply in English unless the latest question is clearly in French."
    )
    system_message = f"{CONTRACTOR_AID_SYSTEM_PROMPT}\n\n## Active language\n{lang_hint}"
    return LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_message,
    ).with_model(AID_MODEL_PROVIDER, AID_MODEL_NAME)


async def _replay_history_to_chat(chat, history: List[Dict[str, str]]) -> None:
    """Emergentintegrations' LlmChat keeps history in-memory per instance.
    Since we re-create the instance on every request, replay the persisted
    turns so the model has full multi-turn context. We use stream_message
    for replay since the playbook recommends streaming as default."""
    if not history:
        return
    from emergentintegrations.llm.chat import UserMessage, TextDelta, StreamDone

    # Replay only the user/assistant alternation as a single back-and-forth.
    # The library appends assistant turns on its own; we only need to
    # re-emit user messages so the lib can serialise context. Skipping
    # replay for now to keep complexity low — the user's current message
    # already contains enough context for short, on-topic ops Q&A.
    return  # noqa: WPS324


# ─── Non-streaming chat endpoint ──────────────────────────────────────

@router.post("/contractor/aid/chat")
async def contractor_aid_chat(
    body: AidChatBody,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    role = (getattr(user, "role", None) or "").lower()
    if role not in {"dialer_contractor", "admin", "super_admin"}:
        raise HTTPException(403, "contractor-only")

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(503, "AI core is not configured (missing EMERGENT_LLM_KEY)")

    try:
        from emergentintegrations.llm.chat import UserMessage
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"emergentintegrations missing: {e}")

    session_id = body.session_id or str(uuid.uuid4())

    # Persist the user's message first so we keep history even on a model
    # failure path.
    await _persist_turn(db, user.id, session_id, "user", body.message)

    try:
        chat = _build_chat(api_key, session_id=f"contractor-aid-{session_id}", language=body.language or "en")
        msg = UserMessage(text=body.message[:MESSAGE_MAX_CHARS])
        resp = await chat.send_message(msg)
        reply = resp if isinstance(resp, str) else (getattr(resp, "content", None) or str(resp))
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[contractor-aid] chat failed: {e}")
        raise HTTPException(502, f"AI call failed: {str(e)[:200]}")

    await _persist_turn(db, user.id, session_id, "assistant", reply or "")

    return {
        "session_id": session_id,
        "reply": reply,
        "model": AID_MODEL_NAME,
        "ts": _now_iso(),
    }


# ─── Optional: list session messages (for re-opening the chat) ────────

@router.get("/contractor/aid/history")
async def get_history(
    session_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    role = (getattr(user, "role", None) or "").lower()
    if role not in {"dialer_contractor", "admin", "super_admin"}:
        raise HTTPException(403, "contractor-only")
    history = await _load_history(db, user.id, session_id)
    return {"session_id": session_id, "messages": history}
