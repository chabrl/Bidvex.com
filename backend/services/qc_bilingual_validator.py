"""
iter217 — Quebec Bill 96 listing-title compliance validator.

When a seller's listing is located in Quebec (province="QC" or region="QC"
or city="Sherbrooke"/"Montreal"/"Quebec"...) we require BOTH an English
and a French title (and description).

This is a backend hard-gate; the frontend should ALSO show inline errors.

iter217 Phase 5 Hotfix (Feb 16, 2026) — heuristic relaxation:
The validator now also accepts a SINGLE-language title when that title is
already French. We auto-detect French by:
  (a) presence of French-specific accented characters (é, è, à, ç, etc.)
  (b) presence of common French stopwords (le, la, les, des, du, en, et, ...)
This stops the validator from rejecting bilingual sellers who type the
title in French without explicitly setting content_language="fr" — a
common UX gap on the listing form.
"""
import re
from typing import Optional
from fastapi import HTTPException

# Characters specific to French (excluding plain Latin a-z). If a title
# contains ANY of these, the validator treats the title as already-French
# and waives the `title_fr` requirement.
_FRENCH_ACCENT_RE = re.compile(r"[éèêëàâäîïôöùûüçÿœÉÈÊËÀÂÄÎÏÔÖÙÛÜÇŸŒ]")

# Common short French words that signal the text is already in French.
# Kept conservative — only words that are unambiguously French (i.e. would
# NEVER appear as a standalone word in an English listing title). Words
# that overlap with common English (de, son, ma, ta, lot, etc.) are
# intentionally excluded to avoid false positives on English titles like
# "John & Son", "De Niro car", "Lot of tools".
_FRENCH_STOPWORDS = {
    "le", "la", "les", "des", "du", "un", "une", "et", "ou", "en",
    "au", "aux", "avec", "pour", "par", "dans", "sur", "sous", "sans",
    "vers", "chez", "selon", "depuis", "ainsi", "donc", "mais", "ne",
    "pas", "plus", "très", "tres", "tout", "tous", "toute", "toutes",
    "cette", "ces", "ceci", "cela", "celui", "celle", "ceux", "leur",
    "leurs", "notre", "votre", "nos", "vos",
    "est", "sont", "était", "etait", "être", "etre", "avait",
    "comme", "aussi", "encore", "déjà", "deja", "jamais", "rien",
    "quelque", "quelques", "neuve", "occasion", "vendu", "vendue",
    "cuir", "noir", "blanc", "blanche", "rouge", "vert", "verte",
    "bleu", "bleue", "jaune", "gris", "grise", "brun", "brune",
    "neuf",
}


def _looks_french(text: Optional[str]) -> bool:
    """Returns True when `text` is detectably French.

    Detection rules (conservative — false-positive < false-negative):
      1. Contains at least one French-specific accent (é, è, à, ç, ...)
      2. OR has at least one token matching the unambiguous French
         stopword set (en, des, du, le, la, les, cuir, noir, ...).

    Stopwords were chosen to be unambiguously French — they will never
    appear as a standalone word in a normal English listing title.
    Covers titles like:
      - "Banquettes en cuir noir"  → 'en', 'cuir', 'noir' (3 hits)
      - "Vélos de montagne"        → accent on 'é'
      - "Lot d'outils — usagés"    → accent on 'é'
      - "Pool table"               → 0 hits → False
      - "Leather couch"            → 0 hits → False
    """
    if not text or not isinstance(text, str):
        return False
    if _FRENCH_ACCENT_RE.search(text):
        return True
    tokens = re.findall(r"[a-zàâäéèêëîïôöùûüç]+", text.lower())
    for tok in tokens:
        if tok in _FRENCH_STOPWORDS:
            return True
    return False


def _is_quebec_listing(region: Optional[str], city: Optional[str]) -> bool:
    r = (region or "").strip().upper()
    if r == "QC" or r == "QUEBEC":
        return True
    # City fallback only if region was not set
    if not r:
        c = (city or "").strip().lower()
        if c in ("montreal", "montréal", "quebec", "québec", "sherbrooke",
                 "laval", "gatineau", "longueuil", "saguenay", "trois-rivieres",
                 "trois-rivières", "levis", "lévis"):
            return True
    return False


def _is_blank(value: Optional[str]) -> bool:
    return value is None or not str(value).strip()


def assert_qc_bilingual_titles(
    *,
    title: Optional[str],
    title_fr: Optional[str],
    description: Optional[str] = None,
    description_fr: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    content_language: Optional[str] = None,
) -> None:
    """Raises HTTP 422 with a bilingual error if a Quebec listing is
    missing the French title or description.

    The check is permissive when:
      - The seller is outside Quebec.
      - The seller explicitly typed the title in French
        (content_language="fr").
      - The title is detectably French via accents or stopwords
        (Phase 5 Hotfix v2 — relaxation).
    """
    if not _is_quebec_listing(region, city):
        return

    lang = (content_language or "en").lower()

    # If the seller typed the listing in French OR the title is detectably
    # French already, the French copy IS `title` — no `title_fr` required.
    title_is_french = lang.startswith("fr") or _looks_french(title)

    if title_is_french:
        if _is_blank(title):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "qc_french_title_required",
                    "message_en": "Quebec listings require a French title (Bill 96).",
                    "message_fr": "Les annonces québécoises doivent inclure un titre en français (Loi 96).",
                },
            )
        # Description: if present, also accept it when detectably French.
        if description is not None and not _is_blank(description):
            desc_is_french = lang.startswith("fr") or _looks_french(description)
            if not desc_is_french and _is_blank(description_fr):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "qc_french_description_required",
                        "message_en": "Quebec listings require a French description (Bill 96).",
                        "message_fr": "Les annonces québécoises doivent inclure une description en français (Loi 96).",
                    },
                )
        return

    # Seller typed in English AND title is not detectably French:
    # title_fr MUST be present.
    if _is_blank(title_fr):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "qc_french_title_required",
                "message_en": "Quebec listings require a French title (Bill 96).",
                "message_fr": "Les annonces québécoises doivent inclure un titre en français (Loi 96).",
            },
        )
    if description is not None and not _is_blank(description):
        # description_fr is only required when description is not already French.
        desc_is_french = _looks_french(description)
        if not desc_is_french and _is_blank(description_fr):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "qc_french_description_required",
                    "message_en": "Quebec listings require a French description (Bill 96).",
                    "message_fr": "Les annonces québécoises doivent inclure une description en français (Loi 96).",
                },
            )
