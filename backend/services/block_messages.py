"""
iter342 — Typed block-reason enum + bilingual seller-facing messages.

Every automated listing block MUST return a `block_reason` from this enum so
the frontend shows ONLY the message matching the specific gate that fired.
Non-vehicle sellers must never see the dealer-licensing wall of text.
"""
from __future__ import annotations

BLOCK_REASONS = (
    "vehicle_dealer_required",
    "prohibited_item",
    "ai_review_required",
    "false_positive_suspected",
)

BLOCK_MESSAGES: dict[str, dict[str, str]] = {
    "vehicle_dealer_required": {
        "en": "Vehicle listings on BidVex require a verified provincial dealer licence "
              "(OMVIC in ON, AMVIC in AB, VSA in BC, SAAQ in QC). If you are a licensed "
              "dealer, contact vehicles@bidvex.com to verify your account. If you are "
              "selling a personal vehicle, please use the Marketplace section instead.",
        "fr": "Les annonces de véhicules sur BidVex nécessitent une licence de "
              "concessionnaire provincial vérifiée (OMVIC en ON, AMVIC en AB, VSA en "
              "C.-B., SAAQ au QC). Si vous êtes un concessionnaire licencié, contactez "
              "vehicles@bidvex.com pour vérifier votre compte. Si vous vendez un véhicule "
              "personnel, utilisez plutôt la section Marché.",
    },
    "prohibited_item": {
        "en": "This listing contains content that is not permitted on BidVex. Please review "
              "our Prohibited Items policy at bidvex.com/legal/prohibited. If you believe "
              "this is an error, contact service@bidvex.com.",
        "fr": "Cette annonce contient du contenu non autorisé sur BidVex. Veuillez consulter "
              "notre politique d'articles interdits à bidvex.com/legal/prohibited. Si vous "
              "pensez qu'il s'agit d'une erreur, contactez service@bidvex.com.",
    },
    "ai_review_required": {
        "en": "Your listing has been flagged for manual review by our team. It will appear "
              "in your Drafts while under review. We typically respond within 24 hours. "
              "You will be notified by email when it is approved or if changes are needed.",
        "fr": "Votre annonce a été signalée pour examen manuel par notre équipe. Elle "
              "apparaîtra dans vos brouillons pendant l'examen. Nous répondons généralement "
              "dans les 24 heures. Vous serez informé par courriel lorsqu'elle sera approuvée "
              "ou si des modifications sont nécessaires.",
    },
    "false_positive_suspected": {
        "en": "Your listing was flagged automatically. If you believe this is a mistake, "
              "click 'Request Manual Review' and our team will review it within 24 hours. "
              "Your listing will be saved as a draft in the meantime.",
        "fr": "Votre annonce a été signalée automatiquement. Si vous pensez qu'il s'agit "
              "d'une erreur, cliquez sur 'Demander un examen manuel' et notre équipe "
              "l'examinera dans les 24 heures. Votre annonce sera sauvegardée comme "
              "brouillon entre-temps.",
    },
}


def get_block_message(reason: str, lang: str = "en") -> str:
    msgs = BLOCK_MESSAGES.get(reason) or BLOCK_MESSAGES["false_positive_suspected"]
    return msgs["fr"] if (lang or "en").lower().startswith("fr") else msgs["en"]
