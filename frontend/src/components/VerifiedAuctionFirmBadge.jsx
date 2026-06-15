/**
 * VerifiedAuctionFirmBadge — iter304
 *
 * Distinct tier from "Licensed Dealer" / "Premium Seller". Admin-granted only.
 * Displays a brand-blue (#2B8FD0) shield-iconed badge that's bilingual EN/FR
 * with a tooltip explaining provincial auctioneer compliance.
 *
 * Usage:
 *   <VerifiedAuctionFirmBadge isVerified={user.verified_auction_firm} />
 *   <VerifiedAuctionFirmBadge isVerified userId={user.id} size="sm" />
 *
 * Props:
 *   - isVerified  (bool, required) — pass the user's `verified_auction_firm` flag.
 *                                    Component renders null when false.
 *   - size        ('xs'|'sm'|'md', default 'sm')
 *   - className   (optional extra Tailwind)
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldCheck } from 'lucide-react';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from './ui/tooltip';

const SIZE_MAP = {
  xs: { wrap: 'text-[10px] px-1.5 py-0.5', icon: 'h-3 w-3' },
  sm: { wrap: 'text-xs px-2 py-0.5',        icon: 'h-3.5 w-3.5' },
  md: { wrap: 'text-sm px-2.5 py-1',        icon: 'h-4 w-4' },
};

const VerifiedAuctionFirmBadge = ({ isVerified, size = 'sm', className = '', dataTestid }) => {
  const { i18n } = useTranslation();
  if (!isVerified) return null;
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const label = fr ? "Société d'enchères vérifiée" : 'Verified Auction Firm';
  const tooltip = fr
    ? "Ce vendeur est une société d'enchères vérifiée opérant selon les réglementations provinciales des commissaires-priseurs."
    : 'This seller is a verified auction firm operating under provincial auctioneer regulations.';
  const s = SIZE_MAP[size] || SIZE_MAP.sm;
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            data-testid={dataTestid || 'verified-auction-firm-badge'}
            className={`inline-flex items-center gap-1 rounded-full font-semibold whitespace-nowrap text-white ${s.wrap} ${className}`}
            style={{ backgroundColor: '#2B8FD0' }}
          >
            <ShieldCheck className={s.icon} aria-hidden="true" />
            <span>✓ {label}</span>
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs">
          {tooltip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default VerifiedAuctionFirmBadge;
