/**
 * AcceptedPaymentMethodsSelector
 * -------------------------------------------------------------------
 * iter482 P4B — Seller Multi-select payment-method component used
 * across every Create Auction / Create Listing page.
 *
 * Highly visible checkboxes (NOT a dropdown) with clear bilingual
 * copy and explicit "at least one" client-side validation.
 *
 * Props:
 *   value:     string[]                  // controlled list of canonical slugs
 *   onChange:  (list: string[]) => void  // called on any checkbox toggle
 *   disabled?: boolean                   // e.g. when auction has bids
 *   lockedReason?: string                // shown when disabled=true
 *   isFrench?: boolean                   // i18n copy
 *
 * Canonical slugs (mirror `backend/services/payment_methods_registry.py`):
 *   'stripe' | 'etransfer' | 'cash' | 'cheque'
 */

import React from "react";
import { CreditCard, Send, Banknote, FileText } from "lucide-react";

export const PAYMENT_METHOD_OPTIONS = [
  {
    slug: "stripe",
    en: "Credit / Debit Card (Stripe)",
    fr: "Carte de crédit / débit (Stripe)",
    hint_en: "Buyer pays online. Funds captured after seller settles.",
    hint_fr: "L'acheteur paie en ligne. Fonds capturés après règlement.",
    Icon: CreditCard,
  },
  {
    slug: "etransfer",
    en: "E-Transfer",
    fr: "Virement Interac",
    hint_en: "Buyer sends an Interac e-Transfer to the seller directly.",
    hint_fr: "L'acheteur envoie un virement Interac directement au vendeur.",
    Icon: Send,
  },
  {
    slug: "cash",
    en: "Cash",
    fr: "Espèces",
    hint_en: "Buyer pays in person on pickup.",
    hint_fr: "L'acheteur paie en personne à la collecte.",
    Icon: Banknote,
  },
  {
    slug: "cheque",
    en: "Cheque",
    fr: "Chèque",
    hint_en: "Buyer mails or delivers a bank cheque.",
    hint_fr: "L'acheteur envoie ou remet un chèque bancaire.",
    Icon: FileText,
  },
];

export function AcceptedPaymentMethodsSelector({
  value = [],
  onChange,
  disabled = false,
  lockedReason,
  isFrench = false,
  className = "",
}) {
  const toggle = (slug) => {
    if (disabled) return;
    const set = new Set(value || []);
    if (set.has(slug)) set.delete(slug);
    else set.add(slug);
    onChange?.(Array.from(set));
  };

  return (
    <div
      className={`space-y-3 ${className}`}
      data-testid="accepted-payment-methods-selector"
    >
      <div>
        <h3
          className="text-base font-semibold text-slate-900 dark:text-slate-100"
          data-testid="accepted-payment-methods-title"
        >
          {isFrench
            ? "Modes de paiement acceptés"
            : "Payment Methods Accepted"}
          <span className="text-red-600 ml-1">*</span>
        </h3>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          {isFrench
            ? "Sélectionnez tous les modes de paiement que vous acceptez de l'acheteur gagnant."
            : "Select all payment methods you are willing to accept from the winning buyer."}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {PAYMENT_METHOD_OPTIONS.map(({ slug, en, fr, hint_en, hint_fr, Icon }) => {
          const checked = (value || []).includes(slug);
          return (
            <label
              key={slug}
              data-testid={`accepted-payment-methods-checkbox-${slug}-label`}
              className={`flex items-start gap-3 p-3 rounded-lg border transition
                ${checked
                  ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/30"
                  : "border-slate-200 dark:border-slate-700 hover:border-slate-400"}
                ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(slug)}
                disabled={disabled}
                className="mt-0.5 h-4 w-4 accent-emerald-600"
                data-testid={`accepted-payment-methods-checkbox-${slug}`}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-slate-500" />
                  <span className="font-medium text-slate-900 dark:text-slate-100">
                    {isFrench ? fr : en}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {isFrench ? hint_fr : hint_en}
                </p>
              </div>
            </label>
          );
        })}
      </div>

      {disabled && lockedReason ? (
        <p
          className="text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 rounded-md px-3 py-2"
          data-testid="accepted-payment-methods-locked-notice"
        >
          {lockedReason}
        </p>
      ) : null}

      {(value?.length ?? 0) === 0 ? (
        <p
          className="text-sm text-red-600"
          data-testid="accepted-payment-methods-error"
        >
          {isFrench
            ? "Veuillez sélectionner au moins un mode de paiement."
            : "Please select at least one payment method."}
        </p>
      ) : null}
    </div>
  );
}

export default AcceptedPaymentMethodsSelector;
