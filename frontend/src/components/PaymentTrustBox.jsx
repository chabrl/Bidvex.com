import React from 'react';
import { useTranslation } from 'react-i18next';
import { Lock, ShieldCheck, CheckCircle2 } from 'lucide-react';

/**
 * iter217 — Payment Method Trust Box
 *
 * Bilingual EN/FR explainer rendered above the "Add Payment Method"
 * button on the Account → Payment tab. Reduces drop-off and fraud anxiety
 * by clearly stating that adding a card does NOT trigger a charge.
 */
const PaymentTrustBox = ({ className = '' }) => {
  const { t } = useTranslation();
  return (
    <div
      data-testid="payment-trust-box"
      className={`rounded-xl ${className}`}
      style={{
        background: '#f0f9ff',
        border: '1px solid rgba(37,99,235,0.2)',
        borderLeft: '3px solid #2563eb',
        padding: 20,
      }}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <Lock className="h-5 w-5" style={{ color: '#2563eb' }} />
        </div>
        <div className="flex-1 space-y-3">
          <h4 className="font-bold text-base" style={{ color: '#0f172a' }}>
            {t('paymentTrust.heading', 'Why we ask for a payment method')}
          </h4>
          <p style={{ color: '#334155', fontSize: 13.5, lineHeight: 1.6 }}>
            {t('paymentTrust.body', 'Adding a card does NOT mean we will charge you. Your card is used solely to:')}
          </p>
          <ul className="space-y-1.5" style={{ fontSize: 13.5, color: '#334155', lineHeight: 1.6 }}>
            {['reason1', 'reason2', 'reason3', 'reason4'].map(key => (
              <li key={key} className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 flex-shrink-0 mt-0.5" style={{ color: '#16a34a' }} />
                <span>{t(`paymentTrust.${key}`)}</span>
              </li>
            ))}
          </ul>
          <p style={{ color: '#334155', fontSize: 13.5, lineHeight: 1.6, fontStyle: 'italic' }}>
            {t('paymentTrust.footer', 'You will NEVER be charged without your explicit confirmation. You can remove your card at any time.')}
          </p>
          <div className="flex items-center gap-2 pt-2 border-t border-blue-200/60" style={{ marginTop: 12, paddingTop: 12 }}>
            <ShieldCheck className="h-4 w-4" style={{ color: '#64748b' }} />
            <div className="flex flex-col">
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>
                {t('paymentTrust.stripeBadge', 'Secured by Stripe — PCI DSS compliant')}
              </span>
              <span style={{ fontSize: 11, color: '#94a3b8' }}>
                {t('paymentTrust.stripeSubcopy', 'BidVex never stores your full card number.')}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PaymentTrustBox;
