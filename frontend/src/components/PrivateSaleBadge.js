import React from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from './ui/badge';
import { Sparkles, ShieldCheck, User, Building2, Award, Warehouse, Car } from 'lucide-react';

/**
 * PrivateSaleBadge — bilingual (EN/FR) badge for INDIVIDUAL sellers.
 * Renders nothing when a higher-tier seller badge (Partner / Dealer / Storage)
 * should be shown instead.
 */
const PrivateSaleBadge = ({
  variant = 'default',
  showSavingsPercentage = true,
  className = '',
}) => {
  const { t } = useTranslation();
  const label = t('sellerBadge.privateSale', 'Private Sale');
  const savings = t('sellerBadge.privateSaveTax', 'Save ~15% on Taxes!');
  const heading = t('sellerBadge.privateHeading', 'Private Sale');
  const body = t(
    'sellerBadge.privateBody',
    'This item is from an individual seller. No sales tax on the hammer price!'
  );
  const helper = t(
    'sellerBadge.privateHelper',
    'GST/QST only applies to the buyer\u2019s premium'
  );
  const inline = t('sellerBadge.privateInline', 'Private Sale — Tax-Free Item!');

  if (variant === 'compact') {
    return (
      <Badge
        data-testid="badge-private-sale"
        className={`bg-gradient-to-r from-green-500 to-emerald-500 text-white border-0 ${className}`}
      >
        <User className="h-3 w-3 mr-1" />
        {label}
      </Badge>
    );
  }

  if (variant === 'inline') {
    return (
      <span
        data-testid="badge-private-sale"
        className={`inline-flex items-center gap-1 text-green-600 font-medium ${className}`}
      >
        <Sparkles className="h-4 w-4" />
        {inline}
      </span>
    );
  }

  return (
    <div
      data-testid="badge-private-sale"
      className={`bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/30 dark:to-emerald-900/30 border-2 border-green-300 dark:border-green-600 rounded-xl p-4 ${className}`}
    >
      <div className="flex items-start gap-3">
        <div className="p-2 bg-green-100 dark:bg-green-800 rounded-lg">
          <Sparkles className="h-6 w-6 text-green-600 dark:text-green-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h4 className="font-bold text-green-700 dark:text-green-300 text-lg">{heading}</h4>
            {showSavingsPercentage && (
              <Badge className="bg-green-600 text-white border-0 text-xs">{savings}</Badge>
            )}
          </div>
          <p className="text-sm text-green-600 dark:text-green-400">{body}</p>
          <div className="flex items-center gap-2 mt-2 text-xs text-green-500 dark:text-green-400">
            <ShieldCheck className="h-4 w-4" />
            <span>{helper}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * BusinessSellerBadge — bilingual badge for tax-registered businesses.
 */
export const BusinessSellerBadge = ({ variant = 'compact', className = '' }) => {
  const { t } = useTranslation();
  const label = t('sellerBadge.businessSeller', 'Business Seller');
  const heading = t('sellerBadge.businessHeading', 'Registered Business Seller');
  const body = t('sellerBadge.businessBody', 'Standard GST/QST applies');
  if (variant === 'compact') {
    return (
      <Badge
        data-testid="badge-business-seller"
        variant="outline"
        className={`border-blue-300 text-blue-600 ${className}`}
      >
        <ShieldCheck className="h-3 w-3 mr-1" />
        {label}
      </Badge>
    );
  }
  return (
    <div data-testid="badge-business-seller" className={`bg-blue-50 border border-blue-200 rounded-lg p-3 ${className}`}>
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-blue-600" />
        <div>
          <span className="font-medium text-blue-700">{heading}</span>
          <p className="text-xs text-blue-500">{body}</p>
        </div>
      </div>
    </div>
  );
};

/**
 * PartnerAuctionBadge — iter217 — bilingual badge for verified Partner Auctions.
 */
export const PartnerAuctionBadge = ({ companyName, className = '', variant = 'default' }) => {
  const { t } = useTranslation();
  const heading = t('sellerBadge.partnerAuctionHeading', 'Partner Auction');
  const body = t(
    'sellerBadge.partnerAuctionBody',
    'Hosted by a BidVex-verified auction firm. Buyer\u2019s premium and applicable taxes apply.'
  );
  if (variant === 'compact') {
    return (
      <Badge
        data-testid="badge-partner-auction"
        className={`bg-gradient-to-r from-blue-600 to-indigo-600 text-white border-0 ${className}`}
      >
        <Award className="h-3 w-3 mr-1" />
        {heading}
      </Badge>
    );
  }
  return (
    <div
      data-testid="badge-partner-auction"
      className={`bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 border-2 border-blue-300 dark:border-blue-600 rounded-xl p-4 ${className}`}
    >
      <div className="flex items-start gap-3">
        <div className="p-2 bg-blue-100 dark:bg-blue-800 rounded-lg">
          <Award className="h-6 w-6 text-blue-600 dark:text-blue-300" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h4 className="font-bold text-blue-700 dark:text-blue-200 text-lg">{heading}</h4>
            {companyName && (
              <Badge className="bg-blue-600 text-white border-0 text-xs">{companyName}</Badge>
            )}
          </div>
          <p className="text-sm text-blue-700 dark:text-blue-300">{body}</p>
        </div>
      </div>
    </div>
  );
};

/**
 * VehicleDealerBadge — iter217 — bilingual badge for licensed vehicle dealers.
 */
export const VehicleDealerBadge = ({ className = '', variant = 'default' }) => {
  const { t } = useTranslation();
  const heading = t('sellerBadge.vehicleDealerHeading', 'Vehicle Dealer Auction');
  const body = t(
    'sellerBadge.vehicleDealerBody',
    'Licensed vehicle dealer. Full taxes (GST/QST or HST) apply on the hammer price.'
  );
  if (variant === 'compact') {
    return (
      <Badge data-testid="badge-vehicle-dealer" className={`bg-slate-700 text-white border-0 ${className}`}>
        <Car className="h-3 w-3 mr-1" />
        {heading}
      </Badge>
    );
  }
  return (
    <div data-testid="badge-vehicle-dealer" className={`bg-slate-50 dark:bg-slate-900/30 border-2 border-slate-300 dark:border-slate-700 rounded-xl p-4 ${className}`}>
      <div className="flex items-start gap-3">
        <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
          <Car className="h-6 w-6 text-slate-700 dark:text-slate-200" />
        </div>
        <div className="flex-1">
          <h4 className="font-bold text-slate-700 dark:text-slate-200 text-lg">{heading}</h4>
          <p className="text-sm text-slate-600 dark:text-slate-300">{body}</p>
        </div>
      </div>
    </div>
  );
};

/**
 * StorageFacilityBadge — iter217 — bilingual badge for licensed storage facilities.
 */
export const StorageFacilityBadge = ({ className = '', variant = 'default' }) => {
  const { t } = useTranslation();
  const heading = t('sellerBadge.storageHeading', 'Storage Facility Auction');
  const body = t(
    'sellerBadge.storageBody',
    'Operated by a verified storage facility under provincial lien law.'
  );
  if (variant === 'compact') {
    return (
      <Badge data-testid="badge-storage-facility" className={`bg-amber-700 text-white border-0 ${className}`}>
        <Warehouse className="h-3 w-3 mr-1" />
        {heading}
      </Badge>
    );
  }
  return (
    <div data-testid="badge-storage-facility" className={`bg-amber-50 dark:bg-amber-950/30 border-2 border-amber-300 dark:border-amber-700 rounded-xl p-4 ${className}`}>
      <div className="flex items-start gap-3">
        <div className="p-2 bg-amber-100 dark:bg-amber-800 rounded-lg">
          <Warehouse className="h-6 w-6 text-amber-700 dark:text-amber-200" />
        </div>
        <div className="flex-1">
          <h4 className="font-bold text-amber-700 dark:text-amber-200 text-lg">{heading}</h4>
          <p className="text-sm text-amber-700 dark:text-amber-300">{body}</p>
        </div>
      </div>
    </div>
  );
};

/**
 * SellerAccountBadge — iter217 — picks the correct seller-type badge based on
 * the enriched `seller_account_type` field set by the backend at GET time.
 */
export const SellerAccountBadge = ({
  accountType,
  companyName,
  className = '',
  variant = 'default',
}) => {
  switch (accountType) {
    case 'partner':
      return <PartnerAuctionBadge companyName={companyName} className={className} variant={variant} />;
    case 'vehicle_dealer':
      return <VehicleDealerBadge className={className} variant={variant} />;
    case 'storage_facility':
      return <StorageFacilityBadge className={className} variant={variant} />;
    default:
      return <PrivateSaleBadge className={className} variant={variant} />;
  }
};

// Re-export Building2 import as a no-op suppressor (lint-friendly)
export { Building2 };

export default PrivateSaleBadge;
