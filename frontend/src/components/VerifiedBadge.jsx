/**
 * iter355 — VerifiedBadge
 *
 * Displays a "✓ ID Verified" badge for users whose Stripe Identity
 * KYC passed. Silent no-op when `isVerified` is false — the caller
 * decides where to place it (profile page, bid dialog header, etc.).
 */
import React from 'react';
import { ShieldCheck } from 'lucide-react';

/**
 * @param {{ isVerified: boolean; size?: 'sm'|'md'|'lg'; label?: string; className?: string; }} props
 */
export default function VerifiedBadge({
  isVerified,
  size = 'sm',
  label,
  className = '',
}) {
  if (!isVerified) return null;
  const dims = {
    sm: { pill: 'text-[10px] px-2 py-0.5 gap-1', icon: 'h-3 w-3' },
    md: { pill: 'text-xs px-2.5 py-1 gap-1.5', icon: 'h-3.5 w-3.5' },
    lg: { pill: 'text-sm px-3 py-1.5 gap-2', icon: 'h-4 w-4' },
  }[size] || { pill: 'text-xs px-2.5 py-1 gap-1.5', icon: 'h-3.5 w-3.5' };

  return (
    <span
      data-testid="verified-badge"
      title="Identity verified via Stripe · Identité vérifiée via Stripe"
      className={
        'inline-flex items-center rounded-full font-semibold bg-emerald-100 ' +
        'text-emerald-700 border border-emerald-200 ' +
        dims.pill +
        ' ' +
        className
      }
    >
      <ShieldCheck className={dims.icon} />
      {label || 'ID Verified'}
    </span>
  );
}
