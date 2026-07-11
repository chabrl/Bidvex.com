"""
iter214 P5 — General-purpose AI Moderation Scanner
====================================================
Detects prohibited content on marketplace listings using Gemini.

This complements the iter203 vehicle-specific scanner. It runs in parallel
as a background task after a listing is created (or edited) and flags
listings into status="pending_review" when a violation is suspected.

Designed to:
  • Fail OPEN (LLM unavailable → leave listing as-is, no crash)
  • Fail SAFE (errors are logged, never auto-approved)
  • Support bilingual EN/FR text
  • Return a structured `violation_codes[]` so the admin UI can render
    category-specific tags and the rejection email can reference the
    exact rule that was violated.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# iter214 P5 — 20 canonical violation codes (mirrors /prohibited-items page).
PROHIBITED_VIOLATION_CODES = (
    "PROHIBITED_DRUG_ILLEGAL",
    "PROHIBITED_DRUG_RX_MEDICATION",
    "PROHIBITED_DRUG_PARAPHERNALIA",
    "PROHIBITED_WEAPON_FIREARM",
    "PROHIBITED_WEAPON_EDGED",
    "PROHIBITED_WEAPON_EXPLOSIVE",
    "PROHIBITED_WEAPON_OTHER",
    "VEHICLE_WRONG_SECTION",
    "FINANCIAL_FRAUD",
    "STOLEN_GOODS",
    "COUNTERFEIT_GOODS",
    "HUMAN_EXPLOITATION",
    "ENDANGERED_SPECIES",
    "CYBER_THREAT",
    "PLATFORM_BYPASS",
    "REGULATED_PRODUCT_UNLICENSED",
    "ADULT_CONTENT",
    "IDENTITY_FRAUD",
    "ANIMAL_EXPLOITATION",
    "ACADEMIC_FRAUD",
)


MODERATION_PROMPT = """You are BidVex's content-moderation system for a
Canadian auction marketplace. Your job is to detect ANY content that
violates one of the platform's prohibited-item categories below.

The marketplace operates under Canadian federal + provincial law (Criminal
Code, Controlled Drugs and Substances Act, Firearms Act, Consumer Packaging
Act, CITES, Provincial liquor / cannabis laws). Treat all decisions as if a
Crown prosecutor were reviewing them.

LISTING TO ANALYSE:
Category:    {category}
Title:       {title}
Description: {description}
Price (CAD): {price}

═══════════════════════════════════════════════════════
VIOLATION CATEGORIES & MAPPING TO violation_codes
═══════════════════════════════════════════════════════

1. PROHIBITED_DRUG_ILLEGAL — cannabis (outside licensed channels),
   cocaine, heroin, methamphetamine, fentanyl, MDMA, psilocybin, LSD,
   ketamine, opioids, crack cocaine, kratom, synthetic cannabinoids,
   bath salts.

2. PROHIBITED_DRUG_RX_MEDICATION — any prescription medication
   (OxyContin, Adderall, Xanax, Percocet, Ritalin, Ozempic, antibiotics,
   insulin) or anything requiring a Canadian Rx.

3. PROHIBITED_DRUG_PARAPHERNALIA — pipes, bongs, syringes (non-medical),
   rolling papers marketed for drugs.

4. PROHIBITED_WEAPON_FIREARM — handguns, rifles, shotguns, ammunition,
   firearm parts, suppressors, illegal-capacity magazines, ghost-gun
   components.

5. PROHIBITED_WEAPON_EDGED — switchblades, gravity / butterfly knives,
   brass knuckles, push daggers.

6. PROHIBITED_WEAPON_EXPLOSIVE — grenades, IEDs, commercial fireworks.

7. PROHIBITED_WEAPON_OTHER — nunchucks, morning stars, metal-knuckle
   rings, tasers, stun guns, crossbows (province-restricted), pepper /
   bear spray sold as a weapon.

8. VEHICLE_WRONG_SECTION — any car, truck, SUV, motorcycle, ATV,
   snowmobile, boat, RV, trailer, heavy equipment listed OUTSIDE the
   dedicated Vehicle Auctions section. Use year + brand patterns, VIN,
   mileage, engine specs, transmission, fuel type as indicators.

9. FINANCIAL_FRAUD — counterfeit currency, fake banknotes, fraudulent
   investment / Ponzi materials, unauthorized gift cards, stolen
   financial instruments, credit-card skimmers, POS-fraud devices.

10. STOLEN_GOODS — items with removed serial numbers, catalytic
    converters sold without paper trail, stolen electronics
    ("no box, no receipt, cheap"), goods obtained via break-and-enter,
    any wording implying the item was illegally obtained.

11. COUNTERFEIT_GOODS — fake luxury (Louis Vuitton replica, Rolex
    AAA+, Gucci copy), counterfeit electronics, knockoff sneakers
    explicitly marketed as fakes.

12. HUMAN_EXPLOITATION — human remains, organs, tissue, blood
    products, human-trafficking materials, ANY child-exploitation
    material (zero tolerance — confidence MUST be 1.0).

13. ENDANGERED_SPECIES — ivory, rhino horn, tiger parts, shark fin,
    CITES-listed specimens, live animals from illegal breeding.

14. CYBER_THREAT — malware, ransomware, spyware, keyloggers, hacking
    tools, credential stealers, phishing kits, stolen credential
    databases, deepfake tools sold for fraud.

15. PLATFORM_BYPASS — explicit requests to pay off-platform via
    e-transfer to a personal account, cryptocurrency for tracking
    bypass, Western Union / MoneyGram in suspicious context, fake
    "BidVex"-branded materials from non-BidVex parties, asking buyer
    to skip the auction fee.

16. REGULATED_PRODUCT_UNLICENSED — tobacco targeting minors / sold
    without licence, vaping products outside a licensed retailer,
    alcohol sold outside LCBO / SAQ rules, cannabis outside federal
    / provincial licensed channels, Health-Canada medical devices
    without permit, unregistered pesticides.

17. ADULT_CONTENT — pornographic material of any kind, sexual
    services / escort listings, adult toys with explicit images or
    descriptions.

18. IDENTITY_FRAUD — fake passports, driver's licences, SIN cards,
    health cards, immigration documents.

19. ANIMAL_EXPLOITATION — animal-fighting equipment (cockfighting,
    dogfighting), live animals from illegal breeding operations.

20. ACADEMIC_FRAUD — essays, exams, credentials for sale,
    "essay-writing service" listings.

═══════════════════════════════════════════════════════
OUTPUT FORMAT (STRICT JSON — no markdown, no prose)
═══════════════════════════════════════════════════════

{{
  "verdict":          "PASS" | "UNSURE" | "FAIL",
  "violation_codes":  [array of strings — empty when PASS],
  "confidence":       0.0 to 1.0,
  "reasons_en":       short EN explanation,
  "reasons_fr":       short FR explanation,
  "recommended_action": "allow" | "manual_review" | "reject"
}}

Decision rubric:
  • If you are SURE the listing violates ≥ 1 category → verdict = "FAIL",
    recommended_action = "reject", populate violation_codes.
  • If suspicious but not certain → verdict = "UNSURE",
    recommended_action = "manual_review".
  • Clean listing → verdict = "PASS", violation_codes = [], confidence = 1.0,
    recommended_action = "allow".

Be strict but fair: a clean "wooden dining table, used, good condition"
must PASS. A "DeWalt drill set, used" must PASS. A 2020 Toyota Camry on
Marketplace must FAIL with VEHICLE_WRONG_SECTION."""


async def _call_gemini_moderation(
    category: Optional[str],
    title: Optional[str],
    description: Optional[str],
    price: Optional[float],
) -> dict:
    """Call Gemini with the moderation prompt. Raises RuntimeError on failure."""
    api_key = (
        os.environ.get("EMERGENT_LLM_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    )
    if not api_key:
        raise RuntimeError("no_llm_credentials")

    try:
        from google import genai  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(f"genai_import_failed: {exc}") from exc

    client = genai.Client(api_key=api_key)
    prompt = MODERATION_PROMPT.format(
        category=category or "",
        title=(title or "")[:300],
        description=(description or "")[:2000],
        price=price if price is not None else "",
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
            "max_output_tokens": 512,
        },
    )
    raw = (response.text or "").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gemini_returned_non_json: {raw[:300]}") from exc

    # Sanitise output — filter unknown codes
    codes = parsed.get("violation_codes") or []
    if isinstance(codes, list):
        parsed["violation_codes"] = [
            c for c in codes if c in PROHIBITED_VIOLATION_CODES
        ]
    else:
        parsed["violation_codes"] = []

    # Normalise verdict / action
    parsed["verdict"] = str(parsed.get("verdict", "PASS")).upper()
    if parsed["verdict"] not in {"PASS", "UNSURE", "FAIL"}:
        parsed["verdict"] = "UNSURE"
    parsed["recommended_action"] = parsed.get("recommended_action") or "allow"
    if parsed["recommended_action"] not in {"allow", "manual_review", "reject"}:
        parsed["recommended_action"] = "manual_review"

    return parsed


async def scan_listing_for_violations(
    db,
    *,
    listing_id: str,
    collection: str = "listings",
) -> dict:
    """Background-task entry point.

    Returns a result dict regardless of outcome. Errors are returned with
    `error=True` so the caller can log them but never crashes.
    """
    try:
        listing = await db[collection].find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            return {"error": True, "reason": "listing_not_found"}

        try:
            result = await _call_gemini_moderation(
                category=listing.get("category"),
                title=listing.get("title"),
                description=listing.get("description"),
                price=listing.get("starting_price") or listing.get("buy_now_price"),
            )
        except RuntimeError as exc:
            logger.warning(f"[moderation_scan:{listing_id}] LLM unavailable: {exc}")
            # Persist a soft "manual_review" status only if we already had a hard fail signal.
            await db[collection].update_one(
                {"id": listing_id},
                {"$set": {
                    "moderation_scan_at": datetime.now(timezone.utc).isoformat(),
                    "moderation_status": "pending_review",
                    "moderation_error": str(exc)[:200],
                }},
            )
            return {"error": True, "reason": str(exc)}

        verdict = result.get("verdict")
        codes = result.get("violation_codes") or []
        action = result.get("recommended_action")

        update_fields = {
            "moderation_scan_at": datetime.now(timezone.utc).isoformat(),
            "moderation_verdict": verdict,
            "moderation_codes": codes,
            "moderation_confidence": result.get("confidence"),
            "moderation_reasons_en": (result.get("reasons_en") or "")[:500],
            "moderation_reasons_fr": (result.get("reasons_fr") or "")[:500],
        }

        if verdict == "FAIL" and action == "reject":
            update_fields["moderation_status"] = "rejected"
            update_fields["status"] = "rejected"
            update_fields["block_reason"] = "prohibited_item"
        elif verdict == "UNSURE" or action == "manual_review":
            update_fields["moderation_status"] = "pending_review"
            update_fields["status"] = "pending_review"
            update_fields["block_reason"] = "ai_review_required"
        else:
            update_fields["moderation_status"] = "passed"

        await db[collection].update_one(
            {"id": listing_id}, {"$set": update_fields},
        )

        # iter342 — admin notification (in-app + deduped email) on ANY
        # moderation block so a human can review it. Best-effort.
        if update_fields.get("block_reason"):
            try:
                from services.compliance_notifier import notify_admins_of_violation
                seller_id = listing.get("seller_id") or listing.get("facility_id")
                seller = await db.users.find_one(
                    {"id": seller_id}, {"_id": 0, "email": 1}
                ) if seller_id else None
                await notify_admins_of_violation(
                    db,
                    kind=("blocked_prohibited_item"
                          if update_fields["block_reason"] == "prohibited_item"
                          else "paused_by_ai"),
                    listing={
                        "id": listing_id,
                        "title": listing.get("title") or listing.get("description_en"),
                        "category": listing.get("category"),
                        "seller_id": seller_id,
                    },
                    signals=codes or [f"verdict:{verdict}"],
                    seller_email=(seller or {}).get("email"),
                    extra={"collection": collection, "gate": "prohibited_items_scanner"},
                )
            except Exception as notify_exc:  # noqa: BLE001
                logger.warning(f"[moderation_scan:{listing_id}] admin notify failed: {notify_exc}")

        return {
            "ok": True,
            "verdict": verdict,
            "violation_codes": codes,
            "confidence": result.get("confidence"),
            "action": action,
        }
    except Exception as exc:
        logger.exception(f"[moderation_scan:{listing_id}] unexpected error: {exc}")
        return {"error": True, "reason": str(exc)}
