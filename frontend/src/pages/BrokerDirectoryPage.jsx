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
import { Handshake, MapPin, ShieldCheck, Banknote } from 'lucide-react';

const PROVINCES = [
  { code: '',   name_en: 'All Provinces',     name_fr: 'Toutes provinces' },
  { code: 'ON', name_en: 'Ontario',           name_fr: 'Ontario' },
  { code: 'QC', name_en: 'Quebec',            name_fr: 'Québec' },
  { code: 'BC', name_en: 'British Columbia',  name_fr: 'Colombie-Britannique' },
  { code: 'AB', name_en: 'Alberta',           name_fr: 'Alberta' },
  { code: 'MB', name_en: 'Manitoba',          name_fr: 'Manitoba' },
  { code: 'SK', name_en: 'Saskatchewan',      name_fr: 'Saskatchewan' },
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
  const [province, setProvince] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/api/brokers${province ? `?province=${province}` : ''}`);
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
      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold mb-1" data-testid="broker-directory-title">
            <Handshake className="inline-block h-7 w-7 mr-2 -mt-1" />
            {lang === 'fr' ? 'Annuaire des courtiers' : 'Broker Directory'}
          </h1>
          <p className="text-slate-600 dark:text-slate-300">
            {lang === 'fr'
              ? 'Partenariat avec un courtier agréé pour enchérir sur des véhicules dans les provinces réglementées.'
              : 'Partner with a licensed broker to bid on vehicles in regulated provinces.'}
          </p>
        </div>
        <Select value={province} onValueChange={setProvince}>
          <SelectTrigger className="w-[220px]" data-testid="broker-directory-province">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROVINCES.map(p => <SelectItem key={p.code || 'all'} value={p.code}>{lang === 'fr' ? p.name_fr : p.name_en}</SelectItem>)}
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
              <Button
                className="w-full bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white"
                onClick={() => navigate(`/brokers/${b.id}/request`)}
                data-testid={`broker-request-${b.id}`}
              >
                {lang === 'fr' ? 'Demander un partenariat →' : 'Request Partnership →'}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
