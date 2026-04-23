/**
 * BidVex — Deposit Hold Copy (bilingual EN + FR)
 *
 * Source of truth for every UI surface that displays the $500 vehicle bid
 * deposit status. These strings are rendered side-by-side (both languages at
 * once) to match the OPC legal-notice convention used elsewhere on BidVex
 * (About page, vehicle payment email, etc.).
 *
 * Backend reference: services/vehicle_payment.py (Stripe manual-capture hold),
 * services/vehicle_auction_handler.py (release on auction close),
 * services/vehicle_payment.py::capture_deposit (only captured on missed
 * payment deadline).
 */
export const DEPOSIT_HOLD_AMOUNT = 500;

export const depositHoldCopy = {
  required: {
    en: "Security Hold Required — $500 will be held on your card",
    fr: "Retenue de sécurité requise — 500 $ seront retenus sur votre carte",
  },
  authorized: {
    en: "Hold Authorized — $500 reserved on your card",
    fr: "Retenue autorisée — 500 $ réservés sur votre carte",
  },
  released: {
    en: "Hold Released — $500 returned to your card",
    fr: "Retenue libérée — 500 $ retournés sur votre carte",
  },
  captured: {
    en: "Hold Captured — $500 charged due to missed payment deadline",
    fr: "Retenue capturée — 500 $ débités en raison du délai de paiement manqué",
  },
};

/**
 * Headline-only status label (no "$500" or long sentence), when a compact
 * badge is needed.
 */
export const depositHoldShortLabel = {
  required:   { en: "Security Hold Required",  fr: "Retenue de sécurité requise" },
  authorized: { en: "Hold Authorized",          fr: "Retenue autorisée" },
  released:   { en: "Hold Released",            fr: "Retenue libérée" },
  captured:   { en: "Hold Captured",            fr: "Retenue capturée" },
};
