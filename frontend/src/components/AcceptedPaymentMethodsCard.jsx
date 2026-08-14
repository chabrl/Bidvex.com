/**
 * iter484.2 — Accepted Payment Methods Card
 * ==========================================
 *
 * Buyer-facing card that renders the seller's accepted payment methods
 * with canonical bilingual labels + icons.  Driven entirely by the
 * data on `listing.accepted_payment_methods` (or the immutable
 * `accepted_payment_methods_snapshot` if the auction has received its
 * first bid).  No hardcoded Stripe copy, no hardcoded ordering.
 *
 * Canonical slugs (source of truth: /app/backend/services/payment_methods_registry.py):
 *   - "stripe"     — Card via BidVex Stripe checkout
 *   - "etransfer"  — Interac E-Transfer
 *   - "cash"       — Cash on pickup
 *   - "cheque"     — Certified cheque
 *
 * Read precedence — mirrors backend `effective_methods()`:
 *   1. `accepted_payment_methods_snapshot` (locked, wins if present)
 *   2. `accepted_payment_methods`         (live seller list)
 *   3. `payment_method` (legacy singleton, wrapped as 1-element list)
 *   4. Empty state
 *
 * Test IDs:
 *   - `accepted-payment-methods-card`         (root)
 *   - `apm-method-{stripe|etransfer|cash|cheque}`
 *   - `accepted-payment-methods-empty`
 *   - `accepted-payment-methods-locked-badge` (when snapshot in effect)
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import {
  CreditCard, Send, Banknote, Landmark, Info, Lock,
} from 'lucide-react';

const CANONICAL = ['stripe', 'etransfer', 'cash', 'cheque'];

const META = {
  stripe: {
    en: 'Stripe Checkout',
    fr: 'Paiement Stripe',
    description_en: 'Secure card payment via BidVex Stripe. Visa, Mastercard, Amex accepted.',
    description_fr: 'Paiement sécurisé par carte via BidVex Stripe. Visa, Mastercard, Amex acceptés.',
    Icon: CreditCard,
    tint: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800',
  },
  etransfer: {
    en: 'Interac E-Transfer',
    fr: 'Virement Interac',
    description_en: 'Instructions will be sent by email after the auction closes.',
    description_fr: 'Les instructions seront envoyées par courriel à la fin de l\u2019enchère.',
    Icon: Send,
    tint: 'text-purple-700 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40 border-purple-200 dark:border-purple-800',
  },
  cash: {
    en: 'Cash on Pickup',
    fr: 'Comptant à la collecte',
    description_en: 'Pay the seller in cash when you pick up the item.',
    description_fr: 'Payer le vendeur en espèces lors du ramassage.',
    Icon: Banknote,
    tint: 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800',
  },
  cheque: {
    en: 'Certified Cheque',
    fr: 'Chèque certifié',
    description_en: 'A certified cheque payable to the seller, delivered at pickup.',
    description_fr: 'Un chèque certifié à l\u2019ordre du vendeur, remis lors du ramassage.',
    Icon: Landmark,
    tint: 'text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800',
  },
};

/**
 * Resolve the effective methods list from a listing / lot / auction object.
 * Mirrors backend `services/seller_payment_methods_service::effective_methods()`.
 */
export function resolveAcceptedMethods(listing) {
  if (!listing || typeof listing !== 'object') return [];
  const snap = listing.accepted_payment_methods_snapshot;
  if (Array.isArray(snap) && snap.length > 0) {
    return snap.filter((m) => CANONICAL.includes(m));
  }
  const live = listing.accepted_payment_methods;
  if (Array.isArray(live) && live.length > 0) {
    return live.filter((m) => CANONICAL.includes(m));
  }
  const legacy = listing.payment_method;
  if (typeof legacy === 'string' && legacy.trim()) {
    const norm = legacy.replace('-', '').toLowerCase();
    if (CANONICAL.includes(norm)) return [norm];
    // Legacy variants: e-transfer → etransfer
    if (norm === 'etransfer' || legacy === 'e-transfer') return ['etransfer'];
  }
  return [];
}

export function isPaymentMethodsLocked(listing) {
  if (!listing || typeof listing !== 'object') return false;
  return Array.isArray(listing.accepted_payment_methods_snapshot)
    && listing.accepted_payment_methods_snapshot.length > 0;
}

/**
 * @param {object} props
 * @param {object} props.listing  auction / lot / listing document (data-driven)
 * @param {string} [props.variant] "card" (default) | "inline"
 * @param {string} [props.className] extra classes for the root
 */
export default function AcceptedPaymentMethodsCard({ listing, variant = 'card', className = '' }) {
  const { i18n } = useTranslation();
  const isFR = (i18n.language || '').startsWith('fr');
  const methods = resolveAcceptedMethods(listing);
  const locked = isPaymentMethodsLocked(listing);

  const title = isFR ? 'Modes de paiement acceptés' : 'Accepted Payment Methods';
  const empty = isFR
    ? 'Aucun mode de paiement n\u2019est configuré pour cette enchère. Contactez le vendeur.'
    : 'No payment methods configured by the seller. Contact the seller before bidding.';
  const lockedLabelEN = 'Locked at first bid';
  const lockedLabelFR = 'Verrouillés au premier enchérisseur';

  const rows = methods.map((slug) => {
    const meta = META[slug];
    if (!meta) return null;
    const { Icon, tint } = meta;
    const label = isFR ? meta.fr : meta.en;
    const description = isFR ? meta.description_fr : meta.description_en;
    return (
      <div
        key={slug}
        className={`flex items-start gap-3 rounded-lg border p-3 ${tint}`}
        data-testid={`apm-method-${slug}`}
      >
        <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold leading-tight">{label}</div>
          <div className="text-xs opacity-80 mt-0.5">{description}</div>
        </div>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-4 w-4 mt-0.5 flex-shrink-0 opacity-80"
          aria-hidden="true"
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
    );
  });

  const body = (
    <div className="space-y-2" data-testid="accepted-payment-methods-card">
      {methods.length === 0 ? (
        <div
          className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800 p-3 text-xs"
          data-testid="accepted-payment-methods-empty"
        >
          <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <span>{empty}</span>
        </div>
      ) : (
        rows
      )}
    </div>
  );

  if (variant === 'inline') {
    return <div className={className}>{body}</div>;
  }

  return (
    <Card className={className} data-testid="accepted-payment-methods-card-root">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <CreditCard className="h-4 w-4 text-slate-500" aria-hidden="true" />
          <span>{title}</span>
          {locked && (
            <Badge
              variant="outline"
              className="ml-auto text-[10px] font-medium border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 flex items-center gap-1"
              data-testid="accepted-payment-methods-locked-badge"
              title={isFR ? lockedLabelFR : lockedLabelEN}
            >
              <Lock className="h-3 w-3" aria-hidden="true" />
              <span>{isFR ? lockedLabelFR : lockedLabelEN}</span>
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
}
