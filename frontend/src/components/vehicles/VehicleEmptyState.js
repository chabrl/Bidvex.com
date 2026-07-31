/**
 * iter202 Phase A — Vehicle Auctions Empty States
 * ================================================
 * Three mandatory variants per sprint constraint #10:
 *   • variant="zero-listings"      → flag is ON but no active listings yet (dealer CTA)
 *   • variant="filtered-no-results"→ filters applied, no matches (clear-filters CTA)
 *   • variant="error"              → generic API failure fallback
 *
 * Coming Soon (flag OFF) is handled by VehicleComingSoonPage upstream — not here.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Car, Filter, RotateCcw, PlusCircle, AlertTriangle, Mail, Sparkles } from 'lucide-react';
// iter442 — Choice modal (Single Listing vs Multi-Lot Auction)
import VehicleListingChoiceModal from './VehicleListingChoiceModal';

const ZeroListingsSVG = () => (
  <svg viewBox="0 0 240 160" className="w-48 h-32 mx-auto" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#0B2545" />
        <stop offset="100%" stopColor="#22D3EE" />
      </linearGradient>
    </defs>
    <rect x="6" y="120" width="228" height="6" rx="3" fill="#E2E8F0" />
    <g transform="translate(40 30)">
      <rect x="0" y="40" width="160" height="40" rx="14" fill="url(#g)" opacity="0.08" />
      <path d="M14,60 Q26,20 64,20 L96,20 Q134,20 146,60" stroke="url(#g)" strokeWidth="3" strokeLinecap="round" fill="none" />
      <rect x="14" y="60" width="132" height="22" rx="10" fill="#FFFFFF" stroke="url(#g)" strokeWidth="2" />
      <circle cx="40" cy="82" r="10" fill="#0B2545" />
      <circle cx="120" cy="82" r="10" fill="#0B2545" />
      <circle cx="40" cy="82" r="4" fill="#94A3B8" />
      <circle cx="120" cy="82" r="4" fill="#94A3B8" />
      <rect x="58" y="42" width="44" height="20" rx="6" fill="#22D3EE" opacity="0.2" />
    </g>
    <g transform="translate(190 18)">
      <circle cx="0" cy="0" r="14" fill="#22D3EE" opacity="0.18" />
      <path d="M-6,-1 L-2,3 L6,-5" stroke="#0B2545" strokeWidth="2.5" strokeLinecap="round" fill="none" />
    </g>
  </svg>
);

const FilteredSVG = () => (
  <svg viewBox="0 0 240 160" className="w-48 h-32 mx-auto" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
    <rect x="6" y="120" width="228" height="6" rx="3" fill="#E2E8F0" />
    <g transform="translate(70 26)" stroke="#0B2545" strokeWidth="2.5" strokeLinecap="round" fill="none">
      <circle cx="48" cy="48" r="36" fill="#FFFFFF" stroke="#0B2545" />
      <circle cx="48" cy="48" r="22" fill="#22D3EE" fillOpacity="0.18" stroke="#0B2545" />
      <line x1="76" y1="76" x2="100" y2="100" stroke="#0B2545" strokeWidth="5" />
      <path d="M36,40 L60,40 L52,52 L52,62 L44,58 L44,52 Z" fill="#0B2545" stroke="none" />
    </g>
  </svg>
);

const ErrorSVG = () => (
  <svg viewBox="0 0 240 160" className="w-48 h-32 mx-auto" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
    <rect x="6" y="120" width="228" height="6" rx="3" fill="#E2E8F0" />
    <g transform="translate(80 22)">
      <path d="M40,4 L80,72 L0,72 Z" fill="#FEF3C7" stroke="#D97706" strokeWidth="3" strokeLinejoin="round" />
      <line x1="40" y1="28" x2="40" y2="50" stroke="#D97706" strokeWidth="4" strokeLinecap="round" />
      <circle cx="40" cy="60" r="3" fill="#D97706" />
    </g>
  </svg>
);

const VehicleEmptyState = ({
  variant = 'zero-listings',
  onClearFilters,
  onRetry,
  className = '',
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  // iter442 — Choice modal state
  const [choiceOpen, setChoiceOpen] = React.useState(false);

  if (variant === 'filtered-no-results') {
    return (
      <div
        className={`text-center py-14 px-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 ${className}`}
        data-testid="vehicle-empty-filtered"
      >
        <FilteredSVG />
        <h3 className="mt-4 text-xl sm:text-2xl font-bold text-slate-900 dark:text-white">
          {t('vehicleEmpty.filteredTitle', 'No vehicles match those filters')}
        </h3>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 max-w-md mx-auto">
          {t('vehicleEmpty.filteredBody', 'Try widening your search — clear a filter or two and the available auctions will reappear.')}
        </p>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={onClearFilters}
            className="inline-flex items-center gap-2 rounded-lg bg-[#0B2545] hover:bg-[#0E2B52] text-white font-semibold text-sm px-4 py-2.5"
            data-testid="vehicle-empty-clear-filters-btn"
          >
            <RotateCcw className="h-4 w-4" />
            {t('vehicleEmpty.clearFilters', 'Clear filters')}
          </button>
          <button
            type="button"
            onClick={() => navigate('/vehicle-auctions')}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 font-semibold text-sm px-4 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800"
            data-testid="vehicle-empty-browse-all-btn"
          >
            <Filter className="h-4 w-4" />
            {t('vehicleEmpty.browseAll', 'Browse all auctions')}
          </button>
        </div>
      </div>
    );
  }

  if (variant === 'error') {
    return (
      <div
        className={`text-center py-14 px-4 rounded-2xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 ${className}`}
        data-testid="vehicle-empty-error"
      >
        <ErrorSVG />
        <h3 className="mt-4 text-xl sm:text-2xl font-bold text-amber-900 dark:text-amber-200">
          {t('vehicleEmpty.errorTitle', 'We couldn’t load the auctions')}
        </h3>
        <p className="mt-2 text-sm text-amber-800/80 dark:text-amber-200/80 max-w-md mx-auto">
          {t('vehicleEmpty.errorBody', 'Something went wrong while reaching the server. Please try again in a few seconds.')}
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex items-center gap-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold text-sm px-4 py-2.5"
          data-testid="vehicle-empty-retry-btn"
        >
          <RotateCcw className="h-4 w-4" />
          {t('vehicleEmpty.retry', 'Retry')}
        </button>
      </div>
    );
  }

  // zero-listings (default)
  return (
    <div
      className={`text-center py-14 px-4 rounded-2xl bg-gradient-to-br from-cyan-50 via-white to-emerald-50 dark:from-cyan-950/20 dark:via-slate-900 dark:to-emerald-950/20 border border-cyan-100 dark:border-cyan-900 ${className}`}
      data-testid="vehicle-empty-zero"
    >
      <ZeroListingsSVG />
      <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-cyan-100 dark:bg-cyan-900/40 text-cyan-800 dark:text-cyan-200 text-[11px] font-bold uppercase tracking-wider px-3 py-1">
        <Sparkles className="h-3 w-3" />
        {t('vehicleEmpty.zeroBadge', 'Be among the first listings')}
      </span>
      <h3 className="mt-3 text-xl sm:text-2xl font-bold text-[#0B2545] dark:text-white">
        {t('vehicleEmpty.zeroTitle', 'No live vehicle auctions yet')}
      </h3>
      <p className="mt-2 text-sm text-slate-700 dark:text-slate-300 max-w-lg mx-auto">
        {t(
          'vehicleEmpty.zeroBody',
          'BidVex Vehicle Auctions are now open to verified Canadian dealers. List your first vehicle and reach buyers from BC to Newfoundland — your auction can launch in minutes.'
        )}
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => navigate('/vehicle-auctions/seller/register')}
          className="inline-flex items-center gap-2 rounded-lg bg-[#0B2545] hover:bg-[#0E2B52] text-white font-semibold text-sm px-4 py-2.5"
          data-testid="vehicle-empty-register-btn"
        >
          <Car className="h-4 w-4" />
          {t('vehicleEmpty.registerCta', 'Register as a seller')}
        </button>
        <button
          type="button"
          onClick={() => setChoiceOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg border-2 border-cyan-500 text-cyan-700 dark:text-cyan-300 font-semibold text-sm px-4 py-2.5 hover:bg-cyan-50 dark:hover:bg-cyan-900/30"
          data-testid="vehicle-empty-list-btn"
        >
          <PlusCircle className="h-4 w-4" />
          {t('vehicleEmpty.listCta', 'List a vehicle')}
        </button>
        <button
          type="button"
          onClick={() => navigate('/vehicle-auctions/dealer-license')}
          className="inline-flex items-center gap-2 rounded-lg text-slate-700 dark:text-slate-200 font-semibold text-sm px-4 py-2.5 hover:bg-slate-100 dark:hover:bg-slate-800"
          data-testid="vehicle-empty-license-btn"
        >
          <Mail className="h-4 w-4" />
          {t('vehicleEmpty.verifyLicenseCta', 'Verify dealer licence')}
        </button>
      </div>

      {/* iter442 — Choice modal driven by the "List a vehicle" CTA */}
      <VehicleListingChoiceModal open={choiceOpen} onOpenChange={setChoiceOpen} />
    </div>
  );
};

export default VehicleEmptyState;
