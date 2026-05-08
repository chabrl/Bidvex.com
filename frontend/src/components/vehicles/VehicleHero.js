/**
 * iter202 Phase A — Vehicle Auctions Hero Banner
 * ===============================================
 * Dark navy gradient hero per CEO spec:
 *   • Big bilingual headline + sub
 *   • Trust badge strip (Bilingual, Verified dealers, Soft-close, Provincial tax)
 *   • Live stats strip wired to GET /api/vehicles/stats
 *   • Search bar (search by make/model/VIN)
 *   • CLS = 0 — fixed-height grid for stats with skeleton placeholders
 */
import API_BASE from '../../config';
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import {
  Car, Search, ShieldCheck, Globe2, Gavel, Receipt, Activity,
  Flame, MapPin, Loader2,
} from 'lucide-react';

const API = API_BASE;

const StatTile = ({ icon: Icon, value, label, accent = 'sky', loading, testId }) => (
  <div
    className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm px-4 py-3 min-h-[68px]"
    data-testid={testId}
  >
    <div className={`w-10 h-10 rounded-lg flex items-center justify-center bg-${accent}-500/15 text-${accent}-300 flex-shrink-0`}>
      <Icon className="h-5 w-5" />
    </div>
    <div className="min-w-0">
      {loading ? (
        <div className="h-5 w-12 bg-white/10 rounded animate-pulse mb-1" />
      ) : (
        <div className="text-xl font-bold text-white leading-none truncate" data-testid={`${testId}-value`}>
          {value ?? '—'}
        </div>
      )}
      <div className="text-[11px] uppercase tracking-wide text-slate-300/80 mt-1 truncate">
        {label}
      </div>
    </div>
  </div>
);

const TrustChip = ({ icon: Icon, label, testId }) => (
  <span
    className="inline-flex items-center gap-1.5 rounded-full bg-white/10 border border-white/10 text-slate-100 text-xs px-3 py-1.5 backdrop-blur-sm"
    data-testid={testId}
  >
    <Icon className="h-3.5 w-3.5 text-emerald-300" />
    {label}
  </span>
);

const VehicleHero = ({ onSearch, searchQuery, setSearchQuery }) => {
  const { t } = useTranslation();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/vehicles/stats`);
        if (!cancelled) setStats(res.data || {});
      } catch (e) {
        if (!cancelled) setStats({});
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <section
      className="relative overflow-hidden bg-gradient-to-br from-[#040B1F] via-[#0B2545] to-[#0E2B52] text-white"
      data-testid="vehicle-hero"
    >
      {/* subtle grid pattern */}
      <div className="absolute inset-0 opacity-[0.07] pointer-events-none" aria-hidden>
        <div className="absolute inset-0" style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)",
          backgroundSize: '48px 48px',
        }} />
      </div>
      {/* glow blobs */}
      <div className="absolute -top-32 -right-24 w-96 h-96 rounded-full bg-cyan-500/15 blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -left-24 w-96 h-96 rounded-full bg-blue-500/15 blur-3xl pointer-events-none" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-10 lg:pt-16 lg:pb-12">
        {/* Top row — eyebrow */}
        <div className="flex items-center gap-2 mb-5">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-cyan-500/15 border border-cyan-400/30 text-cyan-200 text-[11px] font-semibold uppercase tracking-wider px-3 py-1">
            <Car className="h-3.5 w-3.5" />
            {t('vehicleHero.eyebrow', 'BidVex Vehicle Auctions')}
          </span>
          <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-400/30 text-emerald-200 text-[11px] font-semibold uppercase tracking-wider px-3 py-1">
            <Activity className="h-3.5 w-3.5 animate-pulse" />
            {t('vehicleHero.live', 'Live across Canada')}
          </span>
        </div>

        {/* Headline */}
        <h1
          className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight leading-[1.05] max-w-4xl text-white"
          data-testid="vehicle-hero-title"
        >
          {t('vehicleHero.title', 'Cars, trucks & equipment.')}
          <span className="block text-cyan-300 mt-1">
            {t('vehicleHero.titleAccent', 'Verified. Bilingual. Canadian.')}
          </span>
        </h1>
        <p
          className="mt-4 text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed"
          data-testid="vehicle-hero-subtitle"
        >
          {t(
            'vehicleHero.subtitle',
            'Provincial-compliant auctions for licensed dealers and qualified buyers. Soft-close protection, transparent fees, and tax-aware checkout from BC to Newfoundland.'
          )}
        </p>

        {/* Search bar */}
        <form
          onSubmit={(e) => { e.preventDefault(); onSearch?.(searchQuery); }}
          className="mt-6 flex flex-col sm:flex-row gap-3 max-w-2xl"
          data-testid="vehicle-hero-search-form"
        >
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery || ''}
              onChange={(e) => setSearchQuery?.(e.target.value)}
              placeholder={t(
                'vehicleHero.searchPlaceholder',
                'Search by make, model, VIN, or city…'
              )}
              className="w-full h-12 sm:h-14 rounded-xl bg-white/10 border border-white/15 text-white placeholder:text-slate-400 pl-12 pr-4 focus:outline-none focus:bg-white/15 focus:border-cyan-400/50 transition"
              data-testid="vehicle-hero-search-input"
            />
          </div>
          <button
            type="submit"
            className="h-12 sm:h-14 px-6 sm:px-8 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-[#0B2545] font-bold transition-colors whitespace-nowrap"
            data-testid="vehicle-hero-search-submit"
          >
            {t('vehicleHero.searchCta', 'Find vehicles')}
          </button>
        </form>

        {/* Trust chips */}
        <div className="mt-6 flex flex-wrap gap-2" data-testid="vehicle-hero-trust">
          <TrustChip icon={ShieldCheck} label={t('vehicleHero.trust.dealers', 'Verified dealers')} testId="vehicle-hero-trust-dealers" />
          <TrustChip icon={Gavel} label={t('vehicleHero.trust.softClose', 'Soft-close protection')} testId="vehicle-hero-trust-softclose" />
          <TrustChip icon={Receipt} label={t('vehicleHero.trust.taxAware', 'Provincial tax-aware')} testId="vehicle-hero-trust-tax" />
          <TrustChip icon={Globe2} label={t('vehicleHero.trust.bilingual', 'EN · FR bilingual')} testId="vehicle-hero-trust-bilingual" />
        </div>

        {/* Stats strip */}
        <div
          className="mt-8 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3"
          data-testid="vehicle-hero-stats"
        >
          <StatTile
            icon={Car}
            value={stats?.active_listings ?? 0}
            label={t('vehicleHero.stats.active', 'Active auctions')}
            accent="sky"
            loading={loading}
            testId="vehicle-hero-stat-active"
          />
          <StatTile
            icon={Flame}
            value={stats?.ending_soon ?? 0}
            label={t('vehicleHero.stats.ending', 'Ending in 24h')}
            accent="orange"
            loading={loading}
            testId="vehicle-hero-stat-ending"
          />
          <StatTile
            icon={ShieldCheck}
            value={stats?.verified_dealers ?? 0}
            label={t('vehicleHero.stats.dealers', 'Verified dealers')}
            accent="emerald"
            loading={loading}
            testId="vehicle-hero-stat-dealers"
          />
          <StatTile
            icon={MapPin}
            value={stats?.provinces_covered ?? 0}
            label={t('vehicleHero.stats.provinces', 'Provinces live')}
            accent="cyan"
            loading={loading}
            testId="vehicle-hero-stat-provinces"
          />
          <StatTile
            icon={Activity}
            value={stats?.total_bids_24h ?? 0}
            label={t('vehicleHero.stats.bids', 'Bids in 24h')}
            accent="violet"
            loading={loading}
            testId="vehicle-hero-stat-bids"
          />
        </div>
      </div>

      {/* Wave divider matching homepage style */}
      <div className="absolute bottom-0 left-0 right-0 pointer-events-none">
        <svg
          viewBox="0 0 1440 80"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-12 sm:h-16"
          preserveAspectRatio="none"
          aria-hidden
        >
          <path
            d="M0,80 C240,40 480,0 720,20 C960,40 1200,80 1440,40 L1440,80 Z"
            className="fill-slate-50 dark:fill-slate-950"
          />
        </svg>
      </div>
    </section>
  );
};

export default VehicleHero;
