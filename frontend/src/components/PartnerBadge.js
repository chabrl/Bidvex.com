import React, { useState, useEffect, useRef } from 'react';
import { ShieldCheck, Award } from 'lucide-react';
import API_BASE from '../config';

/**
 * PartnerBadge — Fetches badge data from GET /api/partner/badge/{sellerId}
 * and renders a premium verified shield with hover tooltip.
 *
 * Badge types:
 *   - verified_vip:    Gold shield
 *   - verified_firm:   Blue shield
 *   - approved_partner: Subtle badge
 *   - null:            Renders nothing
 */
const PartnerBadge = ({ sellerId, size = 'sm' }) => {
  const [badge, setBadge] = useState(null);
  const [showTooltip, setShowTooltip] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!sellerId) return;
    let cancelled = false;
    fetch(`${API_BASE}/partner/badge/${sellerId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data?.badge_type) setBadge(data);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [sellerId]);

  if (!badge || !badge.badge_type) return null;

  const isVip = badge.badge_type === 'verified_vip';
  const isVerified = badge.badge_type === 'verified_firm';
  const isLarge = size === 'md';
  const Icon = isVip ? Award : ShieldCheck;

  const colorMap = {
    verified_vip: {
      bg: isLarge ? '#fffbeb' : '#f59e0b',
      text: isLarge ? '#b45309' : '#fff',
      border: '#fbbf24',
      icon: isLarge ? '#d97706' : '#fff',
      label: 'VIP Verified',
    },
    verified_firm: {
      bg: isLarge ? '#eff6ff' : '#2563eb',
      text: isLarge ? '#1d4ed8' : '#fff',
      border: '#93c5fd',
      icon: isLarge ? '#2563eb' : '#fff',
      label: 'Verified Firm',
    },
    approved_partner: {
      bg: isLarge ? '#ecfdf5' : '#059669',
      text: isLarge ? '#047857' : '#fff',
      border: '#6ee7b7',
      icon: isLarge ? '#059669' : '#fff',
      label: 'Partner',
    },
  };

  const c = colorMap[badge.badge_type] || colorMap.approved_partner;
  const tooltip = 'BidVex Verified: This firm has met our professional standards for auction transparency.';

  if (isLarge) {
    return (
      <div className="relative inline-block" ref={ref}>
        <span
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium cursor-default transition-shadow hover:shadow-md"
          style={{ backgroundColor: c.bg, color: c.text, border: `1px solid ${c.border}` }}
          data-testid={`partner-badge-${badge.badge_type}`}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <Icon className="h-4 w-4" style={{ color: c.icon }} />
          {c.label}
        </span>
        {showTooltip && (
          <div
            className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-lg text-xs font-medium shadow-lg whitespace-nowrap pointer-events-none"
            style={{ backgroundColor: '#1e293b', color: '#f1f5f9', maxWidth: '280px', whiteSpace: 'normal' }}
            data-testid="partner-badge-tooltip"
          >
            {tooltip}
            <div
              className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0"
              style={{ borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderTop: '5px solid #1e293b' }}
            />
          </div>
        )}
      </div>
    );
  }

  // Small variant — for listing cards and vehicle cards
  return (
    <div className="relative inline-block" ref={ref}>
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold shadow-sm cursor-default transition-shadow hover:shadow-md"
        style={{ backgroundColor: c.bg, color: c.text }}
        data-testid={`partner-badge-${badge.badge_type}`}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <Icon className="h-3 w-3" />
        {c.label}
      </span>
      {showTooltip && (
        <div
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-lg text-xs font-medium shadow-lg pointer-events-none"
          style={{ backgroundColor: '#1e293b', color: '#f1f5f9', maxWidth: '260px', whiteSpace: 'normal' }}
          data-testid="partner-badge-tooltip"
        >
          {tooltip}
          <div
            className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0"
            style={{ borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderTop: '5px solid #1e293b' }}
          />
        </div>
      )}
    </div>
  );
};

export default PartnerBadge;
