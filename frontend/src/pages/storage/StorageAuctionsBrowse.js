import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../components/ui/select';
import { Loader2, Filter, MapPin, Layers, RefreshCw, ShieldCheck, Search, X } from 'lucide-react';

import StorageHero from './StorageHero';
import StorageAuctionCard from './StorageAuctionCard';
import StorageFooterBanner from './StorageFooterBanner';
import SEO from '../../components/SEO';
// iter364 — Google AdSense inline ad zones.
import AdUnit from '../../components/AdUnit';
import { useAuth } from '../../contexts/AuthContext';
import { LangLink } from '../../components/LangLink';

const API = API_BASE;

const UNIT_SIZES = ['5x5', '5x10', '10x10', '10x15', '10x20', '10x30+'];
const UNIT_TYPES = [
  { v: 'indoor', en: 'Indoor', fr: 'Intérieur' },
  { v: 'outdoor', en: 'Outdoor', fr: 'Extérieur' },
  { v: 'climate_controlled', en: 'Climate Controlled', fr: 'Climatisé' },
  { v: 'drive_up', en: 'Drive-Up', fr: 'Accès véhicule' },
];
const SORT_OPTIONS = [
  { v: 'ending_soon', en: 'Ending Soonest', fr: 'Fin la plus proche' },
  { v: 'newest', en: 'Newest Listed', fr: 'Plus récent' },
  { v: 'price_low', en: 'Lowest Price', fr: 'Prix bas' },
  { v: 'most_bids', en: 'Most Bids', fr: "Plus d'offres" },
];

// iter219 — Visible Content Tags (mirror of backend
// services/visible_content_tags.py::ALLOWED_CONTENT_TAGS).
const CONTENT_TAGS = [
  { slug: 'boxes',          en: 'Boxes',          fr: 'Boîtes' },
  { slug: 'tools',          en: 'Tools',          fr: 'Outils' },
  { slug: 'furniture',      en: 'Furniture',      fr: 'Meubles' },
  { slug: 'electronics',    en: 'Electronics',    fr: 'Électronique' },
  { slug: 'sporting_goods', en: 'Sporting Goods', fr: 'Articles de sport' },
  { slug: 'appliances',     en: 'Appliances',     fr: 'Électroménagers' },
  { slug: 'miscellaneous',  en: 'Miscellaneous',  fr: 'Divers' },
];

// Phase 6.2 hotfix — Single source of truth for "this user has the facility
// portal unlocked". Hides every "Are you a facility?" CTA + surfaces direct
// links into the facility dashboard / create-unit flow.
const _isFacilityOrAdmin = (user) => !!user && (
  user.storage_facility_approved === true
  || user.account_type === 'storage_facility'
  || user.is_storage_facility === true
  || user.role === 'admin'
  || user.role === 'super_admin'
  || user.is_admin === true
);

const StorageAuctionsBrowse = () => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  const { user } = useAuth();
  const isFacilityOrAdmin = _isFacilityOrAdmin(user);

  const [data, setData] = useState({ total: 0, auctions: [] });
  const [provinces, setProvinces] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    province: '',
    unit_size: '',
    unit_type: '',
    is_lien_unit: '',
    status: '',
    sort: 'ending_soon',
    // iter219 — Visible-content tag filter (array of canonical slugs) + free-text search.
    tags: [],
    search: '',
  });
  // iter219 — Debounced search input. Local state mirrors the input value;
  // we push it into `filters.search` after 400 ms of inactivity so each
  // keystroke doesn't fire a network call.
  const [searchInput, setSearchInput] = useState('');
  useEffect(() => {
    const t = setTimeout(() => {
      setFilters((p) => (p.search === searchInput ? p : { ...p, search: searchInput }));
    }, 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.province) params.append('province', filters.province);
      if (filters.unit_size) params.append('unit_size', filters.unit_size);
      if (filters.unit_type) params.append('unit_type', filters.unit_type);
      if (filters.is_lien_unit !== '') params.append('is_lien_unit', filters.is_lien_unit);
      if (filters.status) params.append('status', filters.status);
      // iter219 — Tags (comma-separated) + search (free text) pushed to API
      if (filters.tags && filters.tags.length > 0) params.append('tags', filters.tags.join(','));
      if (filters.search && filters.search.trim()) params.append('search', filters.search.trim());
      params.append('sort', filters.sort);
      params.append('limit', '24');

      const [list, provs, pub] = await Promise.all([
        axios.get(`${API}/storage-auctions?${params.toString()}`),
        axios.get(`${API}/storage-auctions/provinces`),
        axios.get(`${API}/storage-auctions/stats/public`).catch(() => ({ data: null })),
      ]);
      setData(list.data);
      setProvinces(provs.data?.provinces || []);
      setStats(pub.data || null);
    } catch (err) {
      // No-op — empty state is fine on first launch
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const setFilter = (k, v) => setFilters(p => ({ ...p, [k]: v === '__all' ? '' : v }));
  // iter219 — Toggle a canonical tag slug in/out of the active filter set.
  const toggleTag = (slug) => {
    setFilters((p) => ({
      ...p,
      tags: p.tags.includes(slug) ? p.tags.filter((s) => s !== slug) : [...p.tags, slug],
    }));
  };

  return (
    <div className="min-h-screen bg-sky-50 dark:bg-slate-900" data-testid="storage-browse-page">
      <SEO
        title="Storage Unit Auctions"
        description="Browse live storage unit auctions across Canada. Bid on abandoned storage lockers from verified facilities — no buyer fees on BidVex."
        path="/storage-auctions"
      />
      <StorageHero />

      {/* ── PUBLIC STATS BAR (iter171, iter193 single-language) ── */}
      {stats && (stats.total_sold > 0 || stats.active_facilities > 0 || stats.active_auctions > 0) && (
        <div className="bg-[#0B2545] border-b border-[#1a3a5c] py-4" data-testid="storage-public-stats">
          <div className="container mx-auto px-4">
            <div className="flex flex-wrap justify-center items-start gap-6 md:gap-12 text-white">
              {stats.total_sold > 0 && (
                <div className="text-center" data-testid="stat-total-sold">
                  <p className="text-2xl md:text-3xl font-black text-[#3FB4CB]">{stats.total_sold}</p>
                  <p className="text-xs text-gray-300">{t('storage.browse.unitsSold')}</p>
                </div>
              )}
              {stats.active_facilities > 0 && (
                <div className="text-center" data-testid="stat-active-facilities">
                  <p className="text-2xl md:text-3xl font-black text-[#3FB4CB]">{stats.active_facilities}</p>
                  <p className="text-xs text-gray-300">{t('storage.browse.verifiedFacilities')}</p>
                </div>
              )}
              {stats.active_auctions > 0 && (
                <div className="text-center" data-testid="stat-active-auctions">
                  <p className="text-2xl md:text-3xl font-black text-[#3FB4CB]">{stats.active_auctions}</p>
                  <p className="text-xs text-gray-300">{t('storage.browse.liveNowStat')}</p>
                </div>
              )}
              {stats.total_bids_placed > 0 && (
                <div className="text-center" data-testid="stat-total-bids">
                  <p className="text-2xl md:text-3xl font-black text-[#3FB4CB]">{stats.total_bids_placed.toLocaleString()}</p>
                  <p className="text-xs text-gray-300">{t('storage.browse.bidsPlaced')}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Pricing transparency banner — single language (iter193) */}
      <div className="bg-emerald-50 dark:bg-emerald-950/30 border-y border-emerald-200 dark:border-emerald-900/40 py-3 text-center text-xs text-emerald-800 dark:text-emerald-300">
        💰 <strong>{t('storage.browse.transparentFees')}</strong>{' '}
        {t('storage.browse.transparentFeesBody')}
        {' • '}
        <LangLink to="/storage-auctions/how-it-works" className="underline hover:no-underline">{t('storage.browse.howItWorksLink')}</LangLink>
      </div>

      {/* iter283 — Cross-link to Marketplace per dual-visibility spec. */}
      <div className="bg-slate-50 dark:bg-slate-900/30 border-b border-slate-200 dark:border-slate-800 py-2 text-center text-[12px] text-slate-500 dark:text-slate-400"
           data-testid="storage-marketplace-crosslink">
        🛒 {t('storage.browse.alsoInMarketplace',
            'All these listings are also available in the')}{' '}
        <LangLink to="/marketplace" className="underline hover:no-underline font-medium text-slate-700 dark:text-slate-200">
          {t('storage.browse.marketplaceLink', 'Marketplace →')}
        </LangLink>
      </div>

      {/* iter219 — Buyer keyword search + visible-content tag pills.
          Tags filter by `visible_content_tags` server-side; the search box
          additionally scans description / facility / unit# / tag labels. */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 space-y-3">
          <div className="relative max-w-2xl mx-auto" data-testid="storage-search-row">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            <Input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={
                isFr
                  ? 'Rechercher : meubles, outils, électronique…'
                  : 'Search: furniture, tools, electronics…'
              }
              className="pl-9 pr-9 h-10 text-sm"
              data-testid="storage-search-input"
            />
            {searchInput && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => setSearchInput('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                data-testid="storage-search-clear"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <div
            className="flex flex-wrap items-center justify-center gap-2"
            data-testid="storage-tag-pill-row"
          >
            <span className="text-[11px] uppercase tracking-wider text-slate-500 mr-1">
              {isFr ? 'Contenu visible :' : 'Visible Contents:'}
            </span>
            {CONTENT_TAGS.map((tag) => {
              const active = filters.tags.includes(tag.slug);
              return (
                <button
                  key={tag.slug}
                  type="button"
                  onClick={() => toggleTag(tag.slug)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    active
                      ? 'bg-amber-500 text-white border-amber-500 shadow-sm'
                      : 'bg-white text-slate-700 border-slate-300 hover:border-amber-400 hover:bg-amber-50'
                  }`}
                  data-testid={`storage-tag-pill-${tag.slug}`}
                  aria-pressed={active}
                >
                  {isFr ? tag.fr : tag.en}
                </button>
              );
            })}
            {(filters.tags.length > 0 || filters.search) && (
              <button
                type="button"
                onClick={() => {
                  setFilters((p) => ({ ...p, tags: [], search: '' }));
                  setSearchInput('');
                }}
                className="text-[11px] text-slate-500 underline hover:text-slate-700 ml-2"
                data-testid="storage-tag-pill-clear"
              >
                {isFr ? 'Effacer' : 'Clear'}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Filter Sidebar */}
        <aside className="space-y-3">
          <Card className="p-4 sticky top-4">
            <div className="flex items-center gap-2 mb-4 text-sm font-bold">
              <Filter className="h-4 w-4 text-blue-600" />
              {t('storage.browse.filters')}
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block flex items-center gap-1">
                  <MapPin className="h-3 w-3" /> {t('storage.browse.province')}
                </label>
                <Select value={filters.province || '__all'} onValueChange={v => setFilter('province', v)}>
                  <SelectTrigger data-testid="filter-province"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{t('storage.browse.allProvinces')}</SelectItem>
                    {provinces.map(p => (
                      <SelectItem key={p.province} value={p.province}>
                        {p.province} ({p.count})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">
                  {t('storage.browse.unitSize')}
                </label>
                <Select value={filters.unit_size || '__all'} onValueChange={v => setFilter('unit_size', v)}>
                  <SelectTrigger data-testid="filter-unit-size"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{t('storage.browse.allSizes')}</SelectItem>
                    {UNIT_SIZES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">
                  {t('storage.browse.unitType')}
                </label>
                <Select value={filters.unit_type || '__all'} onValueChange={v => setFilter('unit_type', v)}>
                  <SelectTrigger data-testid="filter-unit-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{t('storage.browse.allTypes')}</SelectItem>
                    {UNIT_TYPES.map(t => (
                      <SelectItem key={t.v} value={t.v}>{isFr ? t.fr : t.en}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">
                  {t('storage.browse.status')}
                </label>
                <Select value={filters.status || '__all'} onValueChange={v => setFilter('status', v)}>
                  <SelectTrigger data-testid="filter-status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{t('storage.browse.all')}</SelectItem>
                    <SelectItem value="ending_soon">{t('storage.browse.endingSoon1h')}</SelectItem>
                    <SelectItem value="upcoming">{t('storage.browse.upcoming')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">
                  {t('storage.browse.lienStatus')}
                </label>
                <Select
                  value={filters.is_lien_unit === '' ? '__all' : String(filters.is_lien_unit)}
                  onValueChange={v => setFilter('is_lien_unit', v === '__all' ? '' : v)}
                >
                  <SelectTrigger data-testid="filter-lien"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{t('storage.browse.all')}</SelectItem>
                    <SelectItem value="true">{t('storage.browse.lienUnits')}</SelectItem>
                    <SelectItem value="false">{t('storage.browse.nonLien')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => {
                  setFilters({
                    province: '', unit_size: '', unit_type: '',
                    is_lien_unit: '', status: '', sort: 'ending_soon',
                    tags: [], search: '',
                  });
                  setSearchInput('');
                }}
                data-testid="filter-clear"
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1" />
                {t('storage.browse.clearFilters')}
              </Button>
            </div>
          </Card>

          <Card className="p-3 text-[11px]">
            <div className="flex items-start gap-2 text-slate-600 dark:text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5 text-blue-600 shrink-0 mt-0.5" />
              <p>
                {t('storage.browse.bidvexIsATechnologyPlatformTheStorageFac')}
                {' '}<LangLink to="/storage-auctions/terms" className="underline">{t('storage.browse.terms')}</LangLink>
              </p>
            </div>
          </Card>
        </aside>

        {/* Auction Grid */}
        <main>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-muted-foreground" data-testid="storage-browse-count">
              {isFr ? `${data.total} enchères` : `${data.total} auctions`}
            </p>
            <Select value={filters.sort} onValueChange={v => setFilter('sort', v)}>
              <SelectTrigger className="w-44" data-testid="filter-sort"><SelectValue /></SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map(o => (
                  <SelectItem key={o.v} value={o.v}>{isFr ? o.fr : o.en}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {loading ? (
            <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>
          ) : data.auctions.length === 0 ? (
            <Card className="p-12 text-center" data-testid="storage-browse-empty">
              <Layers className="h-12 w-12 mx-auto mb-3 text-slate-400 opacity-50" />
              <p className="font-semibold text-lg">{t('storage.browse.noActiveStorageAuctionsYet')}</p>
              <p className="text-sm text-muted-foreground mt-1">
                {t('storage.browse.checkBackSoonOurPartnerFacilitiesAreCons')}
              </p>
              <div className="mt-5">
                {isFacilityOrAdmin ? (
                  <div className="flex gap-2 justify-center flex-wrap" data-testid="storage-facility-portal-cta">
                    <LangLink to="/facility/dashboard">
                      <Button data-testid="empty-state-facility-dashboard-btn">
                        📊 {isFr ? 'Tableau de bord' : 'Facility Dashboard'}
                      </Button>
                    </LangLink>
                    <LangLink to="/create-listing?type=storage_locker">
                      <Button variant="outline" data-testid="empty-state-create-unit-btn">
                        ➕ {isFr ? 'Créer une enchère' : 'Create Unit Auction'}
                      </Button>
                    </LangLink>
                  </div>
                ) : (
                  <LangLink to="/storage-auctions/register-facility">
                    <Button>{t('storage.browse.areYouAStorageFacility')}</Button>
                  </LangLink>
                )}
              </div>
            </Card>
          ) : (
            <>
            {/* iter364 — Ad zone above storage grid */}
            <AdUnit
              slot={process.env.REACT_APP_ADSENSE_SLOT_STORAGE_TOP || 'storage-top'}
              format="horizontal"
              style={{ width: '100%', minHeight: 90, marginBottom: 16 }}
              testId="ad-storage-top"
              label="Advertisement"
            />
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {data.auctions.map(a => (
                <StorageAuctionCard key={a.id} auction={a} />
              ))}
            </div>
            {/* iter364 — Ad zone below storage grid */}
            <AdUnit
              slot={process.env.REACT_APP_ADSENSE_SLOT_STORAGE_BOTTOM || 'storage-bottom'}
              format="horizontal"
              style={{ width: '100%', minHeight: 90, marginTop: 24 }}
              testId="ad-storage-bottom"
              label="Advertisement"
            />
            </>
          )}
        </main>
      </div>
      <StorageFooterBanner />
    </div>
  );
};

export default StorageAuctionsBrowse;
