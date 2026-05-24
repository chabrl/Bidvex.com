/**
 * iter217 Phase 5 Hotfix v5b — Public Broker Directory.
 *
 * Route: /brokers (EN) | /courtiers (FR)
 *
 * Shows every approved broker as a card with their fee structure preview
 * and a "Request Partnership →" CTA. Buyers can filter by province.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import API_BASE from '../config';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/select';
import { Handshake, MapPin, ShieldCheck, Banknote, Star, CheckCircle2 } from 'lucide-react';
import MyActiveBrokerPanel from '../components/broker/MyActiveBrokerPanel';

const PROVINCES = [
  { code: 'ALL', name_en: 'All Provinces',     name_fr: 'Toutes provinces' },
  { code: 'ON',  name_en: 'Ontario',           name_fr: 'Ontario' },
  { code: 'QC',  name_en: 'Quebec',            name_fr: 'Québec' },
  { code: 'BC',  name_en: 'British Columbia',  name_fr: 'Colombie-Britannique' },
  { code: 'AB',  name_en: 'Alberta',           name_fr: 'Alberta' },
  { code: 'MB',  name_en: 'Manitoba',          name_fr: 'Manitoba' },
  { code: 'SK',  name_en: 'Saskatchewan',      name_fr: 'Saskatchewan' },
];

const _fmtFee = (fs, lang) => {
  if (!fs) return '';
  if (fs.type === 'fixed') {
    return lang === 'fr' ? `${Number(fs.fixed_amount_cad).toFixed(0)} $ par véhicule` : `$${Number(fs.fixed_amount_cad).toFixed(0)} per vehicle`;
  }
  const pct = (Number(fs.percentage_rate || 0) * 100).toFixed(1);
  return lang === 'fr' ? `${pct} % du prix final` : `${pct}% of hammer price`;
};

export default function BrokerDirectoryPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const navigate = useNavigate();

  const [brokers, setBrokers] = useState([]);
  const [province, setProvince] = useState('ALL');
  const [loading, setLoading] = useState(true);
  // iter228 — if the buyer already has an active partnership, hide the
  // directory and show the management panel exclusively.
  const [hasActivePartnership, setHasActivePartnership] = useState(false);

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const tok = _token();
      if (!tok) { setHasActivePartnership(false); return; }
      try {
        const r = await axios.get(`${API_BASE}/broker-relationships/my-active-broker`, {
          headers: { Authorization: `Bearer ${tok}` },
        });
        if (!cancelled) {
          const rel = r.data?.data?.relationship;
          setHasActivePartnership(rel && ['active', 'approved'].includes(rel.status));
        }
      } catch { if (!cancelled) setHasActivePartnership(false); }
    })();
    return () => { cancelled = true; };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = (province && province !== 'ALL') ? `?province=${province}` : '';
      const r = await axios.get(`${API_BASE}/brokers${qs}`);
      setBrokers(r.data?.data || []);
    } catch {
      setBrokers([]);
    } finally {
      setLoading(false);
    }
  }, [province]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="container mx-auto max-w-6xl py-8 px-4">
      {/* iter228 — My Active Broker Partnership panel (rendered ONLY when bound) */}
      <MyActiveBrokerPanel lang={lang} />

      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold mb-1" data-testid="broker-directory-title">
            <Handshake className="inline-block h-7 w-7 mr-2 -mt-1" />
            {hasActivePartnership
              ? (lang === 'fr' ? 'Autres courtiers' : 'Other Brokers')
              : (lang === 'fr' ? 'Annuaire des courtiers' : 'Broker Directory')}
          </h1>
          <p className="text-slate-600 dark:text-slate-300">
            {hasActivePartnership
              ? (lang === 'fr'
                  ? 'Vous avez déjà un partenariat actif. Pour changer, vous devrez d\'abord mettre fin au courant.'
                  : 'You already have an active partnership. To switch, end your current one first.')
              : (lang === 'fr'
                  ? 'Partenariat avec un courtier agréé pour enchérir sur des véhicules dans les provinces réglementées.'
                  : 'Partner with a licensed broker to bid on vehicles in regulated provinces.')}
          </p>
        </div>
        <Select value={province} onValueChange={setProvince}>
          <SelectTrigger className="w-[220px]" data-testid="broker-directory-province">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROVINCES.map(p => <SelectItem key={p.code} value={p.code}>{lang === 'fr' ? p.name_fr : p.name_en}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {loading && <p className="text-center py-12 text-slate-500">{lang === 'fr' ? 'Chargement...' : 'Loading...'}</p>}

      {!loading && brokers.length === 0 && (
        <Card><CardContent className="p-8 text-center">
          <p className="text-slate-600 dark:text-slate-300 mb-4">
            {lang === 'fr' ? 'Aucun courtier disponible dans cette province pour le moment.' : 'No brokers available in this province yet.'}
          </p>
          <Button variant="outline" onClick={() => navigate('/become-a-broker')} data-testid="become-broker-cta">
            {lang === 'fr' ? 'Devenir courtier →' : 'Become a Broker →'}
          </Button>
        </CardContent></Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {brokers.map((b) => (
          <Card key={b.id} className="hover:shadow-lg transition" data-testid={`broker-card-${b.id}`}>
            <CardContent className="p-5 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-lg leading-snug">{b.legal_business_name}</h3>
                <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200">
                  <ShieldCheck className="h-3 w-3 mr-1" />
                  {lang === 'fr' ? 'Vérifié' : 'Verified'}
                </Badge>
              </div>
              <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <MapPin className="h-4 w-4" />
                <span>{b.operating_province} · {b.regulatory_body}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <Banknote className="h-4 w-4" />
                <span data-testid={`broker-fee-${b.id}`}>{_fmtFee(b.fee_structure, lang)}</span>
              </div>
              <div className="text-xs text-slate-500">
                {lang === 'fr' ? 'Licence' : 'License'}: {b.broker_license_number_masked}
              </div>
              {/* iter217 Phase 5 Hotfix v7 — Trust score */}
              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 border-t border-slate-200 dark:border-slate-700 pt-2.5">
                {Number(b.rating_count || 0) > 0 ? (
                  <span className="flex items-center gap-1" data-testid={`broker-rating-${b.id}`}>
                    <Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500" />
                    <strong className="text-slate-700 dark:text-slate-200">{Number(b.rating_avg || 0).toFixed(1)}</strong>
                    <span>({b.rating_count})</span>
                  </span>
                ) : (
                  <span className="text-slate-400">{lang === 'fr' ? 'Nouveau courtier' : 'New broker'}</span>
                )}
                {Number(b.completed_transactions || 0) > 0 && (
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    {b.completed_transactions} {lang === 'fr' ? 'transactions' : 'transactions'}
                  </span>
                )}
              </div>
              <Button
                className="w-full bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => navigate(`/brokers/${b.id}/request`)}
                disabled={hasActivePartnership}
                title={hasActivePartnership
                  ? (lang === 'fr' ? 'Mettez fin à votre partenariat actif d\'abord' : 'End your active partnership first')
                  : ''}
                data-testid={`broker-request-${b.id}`}
              >
                {hasActivePartnership
                  ? (lang === 'fr' ? 'Déjà lié à un courtier' : 'Already partnered with a broker')
                  : (lang === 'fr' ? 'Demander un partenariat →' : 'Request Partnership →')}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
