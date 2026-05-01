import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../components/ui/select';
import { Loader2, Filter, MapPin, Layers, RefreshCw, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import StorageHero from './StorageHero';
import StorageAuctionCard from './StorageAuctionCard';

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

const StorageAuctionsBrowse = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');

  const [data, setData] = useState({ total: 0, auctions: [] });
  const [provinces, setProvinces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    province: '',
    unit_size: '',
    unit_type: '',
    is_lien_unit: '',
    status: '',
    sort: 'ending_soon',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.province) params.append('province', filters.province);
      if (filters.unit_size) params.append('unit_size', filters.unit_size);
      if (filters.unit_type) params.append('unit_type', filters.unit_type);
      if (filters.is_lien_unit !== '') params.append('is_lien_unit', filters.is_lien_unit);
      if (filters.status) params.append('status', filters.status);
      params.append('sort', filters.sort);
      params.append('limit', '24');

      const [list, provs] = await Promise.all([
        axios.get(`${API}/storage-auctions?${params.toString()}`),
        axios.get(`${API}/storage-auctions/provinces`),
      ]);
      setData(list.data);
      setProvinces(provs.data?.provinces || []);
    } catch (err) {
      // No-op — empty state is fine on first launch
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const setFilter = (k, v) => setFilters(p => ({ ...p, [k]: v === '__all' ? '' : v }));

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="storage-browse-page">
      <StorageHero />

      {/* No buyer-fees disclaimer banner */}
      <div className="bg-emerald-50 dark:bg-emerald-950/30 border-y border-emerald-200 dark:border-emerald-900/40 py-2.5 text-center text-xs text-emerald-800 dark:text-emerald-300">
        ✅ <strong>{isFr ? 'BidVex ne facture AUCUNS frais acheteur.' : 'BidVex charges ZERO buyer fees.'}</strong>
        {' '}
        {isFr
          ? 'Vous payez uniquement le montant de l\'offre gagnante à la facilité.'
          : "You pay only the winning bid amount to the facility."}
        {' • '}
        <Link to="/storage-auctions/how-it-works" className="underline hover:no-underline">
          {isFr ? 'Comment ça marche' : 'How it works'}
        </Link>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Filter Sidebar */}
        <aside className="space-y-3">
          <Card className="p-4 sticky top-4">
            <div className="flex items-center gap-2 mb-4 text-sm font-bold">
              <Filter className="h-4 w-4 text-blue-600" />
              {isFr ? 'Filtrer' : 'Filters'}
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block flex items-center gap-1">
                  <MapPin className="h-3 w-3" /> {isFr ? 'Province' : 'Province'}
                </label>
                <Select value={filters.province || '__all'} onValueChange={v => setFilter('province', v)}>
                  <SelectTrigger data-testid="filter-province"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{isFr ? 'Toutes les provinces' : 'All provinces'}</SelectItem>
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
                  {isFr ? "Taille d'unité" : 'Unit Size'}
                </label>
                <Select value={filters.unit_size || '__all'} onValueChange={v => setFilter('unit_size', v)}>
                  <SelectTrigger data-testid="filter-unit-size"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{isFr ? 'Toutes' : 'All sizes'}</SelectItem>
                    {UNIT_SIZES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">
                  {isFr ? "Type d'unité" : 'Unit Type'}
                </label>
                <Select value={filters.unit_type || '__all'} onValueChange={v => setFilter('unit_type', v)}>
                  <SelectTrigger data-testid="filter-unit-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{isFr ? 'Tous les types' : 'All types'}</SelectItem>
                    {UNIT_TYPES.map(t => (
                      <SelectItem key={t.v} value={t.v}>{isFr ? t.fr : t.en}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">
                  {isFr ? 'Statut' : 'Status'}
                </label>
                <Select value={filters.status || '__all'} onValueChange={v => setFilter('status', v)}>
                  <SelectTrigger data-testid="filter-status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{isFr ? 'Toutes' : 'All'}</SelectItem>
                    <SelectItem value="ending_soon">{isFr ? 'Se termine bientôt (1h)' : 'Ending Soon (<1h)'}</SelectItem>
                    <SelectItem value="upcoming">{isFr ? 'À venir' : 'Upcoming'}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">
                  {isFr ? 'Type juridique' : 'Lien Status'}
                </label>
                <Select
                  value={filters.is_lien_unit === '' ? '__all' : String(filters.is_lien_unit)}
                  onValueChange={v => setFilter('is_lien_unit', v === '__all' ? '' : v)}
                >
                  <SelectTrigger data-testid="filter-lien"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">{isFr ? 'Toutes' : 'All'}</SelectItem>
                    <SelectItem value="true">{isFr ? 'Unités sous rétention' : 'Lien Units'}</SelectItem>
                    <SelectItem value="false">{isFr ? 'Sans rétention' : 'Non-Lien'}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() =>
                  setFilters({ province: '', unit_size: '', unit_type: '', is_lien_unit: '', status: '', sort: 'ending_soon' })
                }
                data-testid="filter-clear"
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1" />
                {isFr ? 'Réinitialiser' : 'Clear filters'}
              </Button>
            </div>
          </Card>

          <Card className="p-3 text-[11px]">
            <div className="flex items-start gap-2 text-slate-600 dark:text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5 text-blue-600 shrink-0 mt-0.5" />
              <p>
                {isFr
                  ? 'BidVex est une plateforme technologique. La facilité d\'entreposage est l\'encanteur officiel.'
                  : 'BidVex is a technology platform. The storage facility is the official auctioneer.'}
                {' '}<Link to="/storage-auctions/terms" className="underline">{isFr ? 'Conditions' : 'Terms'}</Link>
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
              <p className="font-semibold text-lg">{isFr ? 'Aucune enchère active' : 'No active storage auctions yet'}</p>
              <p className="text-sm text-muted-foreground mt-1">
                {isFr
                  ? 'Revenez bientôt — nos facilités partenaires ajoutent constamment de nouvelles enchères.'
                  : 'Check back soon — our partner facilities are constantly adding new auctions.'}
              </p>
              <div className="mt-5">
                <Link to="/storage-auctions/register-facility">
                  <Button>{isFr ? 'Vous êtes une facilité ?' : 'Are you a storage facility?'}</Button>
                </Link>
              </div>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {data.auctions.map(a => (
                <StorageAuctionCard key={a.id} auction={a} />
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default StorageAuctionsBrowse;
