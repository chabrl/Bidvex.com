/**
 * iter341 P1 — Google Maps B2B Prospect Finder (Contractor Dashboard).
 * Feature-flagged on GOOGLE_MAPS_API_KEY (503 → disabled UI + prerequisite).
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { MapPin, Search, Loader2, Star, Globe, Phone, PhoneCall, UserPlus, Info } from 'lucide-react';
import API_BASE from '../../config';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';

const TYPES = [
  { value: 'vehicle_dealer', en: 'Vehicle Dealers', fr: 'Concessionnaires' },
  { value: 'liquidator', en: 'Liquidators', fr: 'Liquidateurs' },
  { value: 'auctioneer', en: 'Auctioneers', fr: 'Encanteurs' },
  { value: 'storage_facility', en: 'Storage Facilities', fr: 'Entreposage' },
  { value: 'industrial', en: 'Industrial/Commercial', fr: 'Industriel/Commercial' },
];

const toE164 = (phone) => {
  const digits = (phone || '').replace(/\D/g, '');
  if (!digits) return '';
  return digits.length === 10 ? `+1${digits}` : `+${digits}`;
};

export const ProspectFinder = ({ token, fr, isAdmin, onAddAsClient }) => {
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [city, setCity] = useState('');
  const [bizType, setBizType] = useState('vehicle_dealer');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [cached, setCached] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!token) return;
    axios.get(`${API_BASE}/contractor/prospect-finder/config`, { headers })
      .then((r) => setConfig(r.data))
      .catch(() => setConfig({ enabled: false }));
    // eslint-disable-next-line
  }, [token]);

  const search = async () => {
    if (city.trim().length < 2) {
      toast.error(fr ? 'Entrez une ville ou un code postal.' : 'Enter a city or postal code.');
      return;
    }
    setLoading(true);
    try {
      const r = await axios.get(
        `${API_BASE}/contractor/prospect-finder?city=${encodeURIComponent(city.trim())}&type=${bizType}&radius_km=25`,
        { headers },
      );
      setResults(r.data?.items || []);
      setCached(!!r.data?.cached);
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Recherche échouée' : 'Search failed'));
    } finally { setLoading(false); }
  };

  const enabled = !!config?.enabled;

  return (
    <Card data-testid="prospect-finder">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <MapPin className="h-5 w-5 text-emerald-600" />
          {fr ? 'Chercheur de prospects' : 'Prospect Finder'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!enabled && config && (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800" data-testid="prospect-finder-flag-note">
            {config.prerequisite || (fr
              ? 'Clé API Google Maps requise — ajoutez GOOGLE_MAPS_API_KEY à la configuration d\'environnement Emergent.'
              : 'Google Maps API key required — add GOOGLE_MAPS_API_KEY to the Emergent environment configuration.')}
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-2">
          <Input
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder={fr ? 'Ville ou code postal (ex. Montréal)' : 'City or postal code (e.g. Montreal)'}
            className="sm:max-w-xs"
            disabled={!enabled}
            data-testid="prospect-city-input"
            onKeyDown={(e) => e.key === 'Enter' && enabled && search()}
          />
          <Button onClick={search} disabled={!enabled || loading} size="sm" className="sm:h-10" data-testid="prospect-search-btn">
            {loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Search className="h-4 w-4 mr-1" />}
            {fr ? 'Rechercher' : 'Search'}
          </Button>
        </div>

        <div className="flex flex-wrap gap-1.5" data-testid="prospect-type-pills">
          {TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => setBizType(t.value)}
              disabled={!enabled}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                bizType === t.value
                  ? 'bg-emerald-600 text-white border-emerald-600'
                  : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-emerald-400'
              } disabled:opacity-50`}
              data-testid={`prospect-type-${t.value}`}
            >
              {fr ? t.fr : t.en}
            </button>
          ))}
        </div>

        {results && (
          <div className="space-y-2" data-testid="prospect-results">
            <p className="text-xs text-slate-500">
              {results.length} {fr ? 'résultats' : 'results'}
              {cached ? (fr ? ' (cache 24 h — aucun coût API)' : ' (24h cache — no API cost)') : ''}
            </p>
            {results.length === 0 && (
              <p className="text-sm text-slate-500" data-testid="prospect-empty">
                {fr ? 'Aucune entreprise trouvée pour cette recherche.' : 'No businesses found for this search.'}
              </p>
            )}
            {results.map((p, i) => (
              <div key={p.place_id || i} className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 space-y-1.5" data-testid={`prospect-row-${i}`}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm">{p.name}</span>
                  {p.rating != null && (
                    <span className="flex items-center gap-0.5 text-xs text-amber-600">
                      <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                      {p.rating} ({p.review_count})
                    </span>
                  )}
                  {p.already_in_bidvex && (
                    <Badge className="bg-blue-100 text-blue-800 border-blue-300 text-[10px]" data-testid={`prospect-existing-badge-${i}`}>
                      {fr ? 'Déjà sur BidVex' : 'Already on BidVex'}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-slate-500">{p.address}</p>
                <div className="flex items-center gap-3 text-xs text-slate-600 dark:text-slate-400 flex-wrap">
                  {p.phone && <span className="flex items-center gap-1"><Phone className="h-3 w-3" />{p.phone}</span>}
                  {p.website && (
                    <a href={p.website} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[#2B8FD0] hover:underline">
                      <Globe className="h-3 w-3" />{fr ? 'Site web' : 'Website'}
                    </a>
                  )}
                  {p.google_maps_url && (
                    <a href={p.google_maps_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[#2B8FD0] hover:underline">
                      <MapPin className="h-3 w-3" />Maps
                    </a>
                  )}
                </div>
                <div className="flex gap-1.5 pt-1">
                  <Button
                    size="sm" variant="outline" className="h-7 text-[11px]"
                    disabled={!p.phone}
                    title={!p.phone ? (fr ? 'Aucun téléphone disponible' : 'No phone available') : ''}
                    onClick={() => navigate(`/admin/dialer?phone=${encodeURIComponent(toE164(p.phone))}&name=${encodeURIComponent(p.name)}`)}
                    data-testid={`prospect-call-queue-btn-${i}`}
                  >
                    <PhoneCall className="h-3 w-3 mr-1" />
                    {fr ? 'Ajouter à la file d\'appels' : 'Add to Call Queue'}
                  </Button>
                  <Button
                    size="sm" variant="outline" className="h-7 text-[11px]"
                    onClick={() => onAddAsClient({ name: p.name, phone: toE164(p.phone) })}
                    data-testid={`prospect-add-client-btn-${i}`}
                  >
                    <UserPlus className="h-3 w-3 mr-1" />
                    {fr ? 'Ajouter comme client référé' : 'Add as Referred Client'}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {isAdmin && config?.billing_note && (
          <p className="flex items-start gap-1.5 text-[11px] text-slate-400 border-t border-slate-100 dark:border-slate-800 pt-2" data-testid="prospect-billing-note">
            <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            {config.billing_note}
          </p>
        )}
      </CardContent>
    </Card>
  );
};

export default ProspectFinder;
