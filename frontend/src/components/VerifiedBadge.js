import React from 'react';
import { ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/**
 * Verified Auction Firm badge — shown on listing cards and partner profiles.
 * Accepts size='sm' (listing cards) or size='md' (profiles).
 */
export const VerifiedBadge = ({ size = 'sm', className = '' }) => {
  const { t } = useTranslation();
  const label = t('verifiedFirm', 'Verified Firm');

  if (size === 'md') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${className}`}
        style={{ backgroundColor: '#ecfdf5', color: '#047857', border: '1px solid #6ee7b7' }}
        data-testid="verified-badge"
      >
        <ShieldCheck className="h-4 w-4" style={{ color: '#059669' }} />
        {label}
      </span>
    );
  }

  // sm — compact for listing cards
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold shadow-sm ${className}`}
      style={{ backgroundColor: '#059669', color: '#ffffff' }}
      data-testid="verified-badge"
    >
      <ShieldCheck className="h-3 w-3" />
      {label}
    </span>
  );
};

export default VerifiedBadge;
