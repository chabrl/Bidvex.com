/**
 * iter217 Phase 5 Hotfix v5b — Broker application form.
 *
 * Public route: /become-a-broker (EN) | /devenir-courtier (FR)
 *
 * 4-step wizard:
 *   1. Business information (legal name, province, registration, license)
 *   2. Document upload (placeholder — Phase v6 wires S3 multipart)
 *   3. Fee structure (fixed | percentage + min/max clamps)
 *   4. Legal confirmation + submit
 *
 * Submitting POSTs to /api/brokers/apply. Successful response navigates
 * to the broker dashboard (which shows "Pending Review" state until an
 * admin approves the application).
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import API_BASE from '../config';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/select';
import { Alert, AlertDescription } from '../components/ui/alert';
import { CheckCircle2, ChevronRight, ChevronLeft, AlertTriangle } from 'lucide-react';

const PROVINCES = [
  { code: 'ON', name_en: 'Ontario',            name_fr: 'Ontario',            regulator: 'OMVIC' },
  { code: 'QC', name_en: 'Quebec',             name_fr: 'Québec',             regulator: 'SAAQ / OPC' },
  { code: 'BC', name_en: 'British Columbia',   name_fr: 'Colombie-Britannique', regulator: 'VSA' },
  { code: 'AB', name_en: 'Alberta',            name_fr: 'Alberta',            regulator: 'AMVIC' },
  { code: 'MB', name_en: 'Manitoba',           name_fr: 'Manitoba',           regulator: 'MPI' },
  { code: 'SK', name_en: 'Saskatchewan',       name_fr: 'Saskatchewan',       regulator: 'SGI' },
  { code: 'NS', name_en: 'Nova Scotia',        name_fr: 'Nouvelle-Écosse',    regulator: 'OMVB' },
  { code: 'NB', name_en: 'New Brunswick',      name_fr: 'Nouveau-Brunswick',  regulator: 'NBPSCMVD' },
  { code: 'NL', name_en: 'Newfoundland',       name_fr: 'Terre-Neuve',        regulator: 'NLDGS' },
  { code: 'PE', name_en: 'PEI',                name_fr: 'Î.-P.-É.',           regulator: 'PEI Highway Safety' },
];

const _fmt = (n) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n || 0));

export default function BecomeABrokerPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';

  const [step, setStep]         = useState(1);
  const [submitting, setSubmit] = useState(false);
  const [error, setError]       = useState(null);
  const [success, setSuccess]   = useState(false);

  const [form, setForm] = useState({
    legal_business_name: '',
    operating_province:  'ON',
    corporate_registration_number: '',
    broker_license_number: '',
    permit_type:         'broker',

    fee_type:            'fixed',     // fixed | percentage
    fixed_amount_cad:    500,
    percentage_rate:     0.03,        // 3%
    min_fee_cad:         '',
    max_fee_cad:         '',
    default_deposit_amount_cad: 500,

    legal_confirmed:     false,
  });

  const province = PROVINCES.find(p => p.code === form.operating_province) || PROVINCES[0];

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  // ── Live fee preview on a $15,000 sample ─────────────────────────
  const sampleFee = (() => {
    const sample = 15000;
    let raw = form.fee_type === 'fixed'
      ? Number(form.fixed_amount_cad) || 0
      : sample * (Number(form.percentage_rate) || 0);
    const mn = Number(form.min_fee_cad);
    const mx = Number(form.max_fee_cad);
    if (form.min_fee_cad !== '' && !Number.isNaN(mn)) raw = Math.max(raw, mn);
    if (form.max_fee_cad !== '' && !Number.isNaN(mx)) raw = Math.min(raw, mx);
    return raw;
  })();

  const goNext = () => setStep(s => Math.min(4, s + 1));
  const goBack = () => setStep(s => Math.max(1, s - 1));

  const canAdvance = () => {
    if (step === 1) return form.legal_business_name && form.corporate_registration_number && form.broker_license_number;
    if (step === 2) return true;  // Docs are optional in MVP; v6 wires S3
    if (step === 3) {
      if (form.fee_type === 'fixed') return Number(form.fixed_amount_cad) > 0;
      return Number(form.percentage_rate) > 0;
    }
    if (step === 4) return form.legal_confirmed;
    return true;
  };

  const handleSubmit = async () => {
    setSubmit(true); setError(null);
    try {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      const payload = {
        legal_business_name:           form.legal_business_name.trim(),
        operating_province:            form.operating_province,
        corporate_registration_number: form.corporate_registration_number.trim(),
        broker_license_number:         form.broker_license_number.trim(),
        regulatory_body:               province.regulator,
        permit_type:                   form.permit_type,
        fee_structure: {
          type:              form.fee_type,
          fixed_amount_cad:  Number(form.fixed_amount_cad) || 0,
          percentage_rate:   Number(form.percentage_rate) || 0,
          min_fee_cad:       form.min_fee_cad !== '' ? Number(form.min_fee_cad) : null,
          max_fee_cad:       form.max_fee_cad !== '' ? Number(form.max_fee_cad) : null,
        },
        default_deposit_amount_cad: Number(form.default_deposit_amount_cad) || 500,
      };
      const r = await axios.post(`${API_BASE}/api/brokers/apply`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.data?.success) {
        setSuccess(true);
        setTimeout(() => navigate('/broker/dashboard'), 1500);
      }
    } catch (e) {
      setError(
        e?.response?.data?.detail?.[lang === 'fr' ? 'message_fr' : 'message_en']
        || e?.response?.data?.detail?.error
        || e?.response?.data?.detail
        || 'Submission failed.'
      );
    } finally {
      setSubmit(false);
    }
  };

  if (success) {
    return (
      <div className="container mx-auto max-w-2xl py-12 px-4">
        <Card>
          <CardContent className="p-8 text-center" data-testid="broker-apply-success">
            <CheckCircle2 className="mx-auto h-16 w-16 text-emerald-500 mb-4" />
            <h1 className="text-2xl font-bold mb-2">
              {lang === 'fr' ? 'Demande reçue !' : 'Application received!'}
            </h1>
            <p className="text-slate-600 dark:text-slate-300 mb-6">
              {lang === 'fr'
                ? 'Notre équipe vérifiera vos documents sous 24-48 heures. Redirection vers le tableau de bord…'
                : 'Our team will review your documents within 24-48 hours. Redirecting to your dashboard…'}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-3xl py-8 px-4">
      <h1 className="text-3xl font-bold mb-2" data-testid="broker-apply-title">
        {lang === 'fr' ? 'Devenir courtier BidVex' : 'Become a BidVex Broker'}
      </h1>
      <p className="text-slate-600 dark:text-slate-300 mb-6">
        {lang === 'fr'
          ? 'Permettez aux acheteurs individuels d\'enchérir sur des véhicules sous votre permis commercial.'
          : 'Let individual buyers bid on vehicles under your commercial permit.'}
      </p>

      {/* Step indicator */}
      <div className="flex items-center justify-between mb-8" data-testid="broker-apply-stepper">
        {[1, 2, 3, 4].map((s) => (
          <div key={s} className="flex items-center flex-1">
            <div
              className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold ${
                s === step
                  ? 'bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white'
                  : s < step
                  ? 'bg-emerald-500 text-white'
                  : 'bg-slate-200 dark:bg-slate-700 text-slate-500'
              }`}
            >{s < step ? '✓' : s}</div>
            {s < 4 && <div className={`h-0.5 flex-1 mx-2 ${s < step ? 'bg-emerald-500' : 'bg-slate-200 dark:bg-slate-700'}`} />}
          </div>
        ))}
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          {error && (
            <Alert variant="destructive" data-testid="broker-apply-error">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{String(error)}</AlertDescription>
            </Alert>
          )}

          {/* Step 1 — Business info */}
          {step === 1 && (
            <div className="space-y-4" data-testid="broker-step-1">
              <h2 className="text-xl font-semibold">{lang === 'fr' ? '1. Informations sur l\'entreprise' : '1. Business Information'}</h2>
              <div>
                <Label>{lang === 'fr' ? 'Raison sociale' : 'Legal Business Name'} *</Label>
                <Input value={form.legal_business_name} onChange={(e) => set('legal_business_name', e.target.value)} data-testid="legal-business-name" />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label>{lang === 'fr' ? 'Province d\'exploitation' : 'Operating Province'} *</Label>
                  <Select value={form.operating_province} onValueChange={(v) => set('operating_province', v)}>
                    <SelectTrigger data-testid="broker-province"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PROVINCES.map(p => (
                        <SelectItem key={p.code} value={p.code}>{lang === 'fr' ? p.name_fr : p.name_en}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>{lang === 'fr' ? 'Organisme de réglementation' : 'Regulatory Body'}</Label>
                  <Input value={province.regulator} disabled data-testid="broker-regulator" />
                </div>
              </div>
              <div>
                <Label>{lang === 'fr' ? 'Numéro d\'immatriculation' : 'Corporate Registration #'} *</Label>
                <Input value={form.corporate_registration_number} onChange={(e) => set('corporate_registration_number', e.target.value)} data-testid="corp-reg-number" />
              </div>
              <div>
                <Label>{lang === 'fr' ? 'Numéro de permis' : 'Broker / Dealer License #'} *</Label>
                <Input value={form.broker_license_number} onChange={(e) => set('broker_license_number', e.target.value)} data-testid="broker-license-number" />
              </div>
              <div>
                <Label>{lang === 'fr' ? 'Type de permis' : 'Permit Type'} *</Label>
                <Select value={form.permit_type} onValueChange={(v) => set('permit_type', v)}>
                  <SelectTrigger data-testid="broker-permit-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dealer">{lang === 'fr' ? 'Concessionnaire' : 'Dealer'}</SelectItem>
                    <SelectItem value="broker">{lang === 'fr' ? 'Courtier' : 'Broker'}</SelectItem>
                    <SelectItem value="agent">Agent</SelectItem>
                    <SelectItem value="corporation">Corporation</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* Step 2 — Documents */}
          {step === 2 && (
            <div className="space-y-4" data-testid="broker-step-2">
              <h2 className="text-xl font-semibold">{lang === 'fr' ? '2. Téléversement des documents' : '2. Document Upload'}</h2>
              <Alert>
                <AlertDescription>
                  {lang === 'fr'
                    ? 'Téléversement des documents en cours d\'intégration. Vous pourrez les fournir après la soumission via votre tableau de bord de courtier.'
                    : 'Document upload coming soon. You can attach license + corporate registration + photo ID after submission from your broker dashboard.'}
                </AlertDescription>
              </Alert>
              <ul className="list-disc pl-5 text-sm text-slate-600 dark:text-slate-300 space-y-1">
                <li>{lang === 'fr' ? 'Permis de courtier / concessionnaire (PDF, JPG, PNG)' : 'Broker / Dealer License (PDF, JPG, PNG)'}</li>
                <li>{lang === 'fr' ? 'Certificat d\'immatriculation' : 'Corporate Registration Certificate'}</li>
                <li>{lang === 'fr' ? 'Pièce d\'identité du contact principal' : 'Government-Issued ID of Primary Contact'}</li>
              </ul>
            </div>
          )}

          {/* Step 3 — Fees */}
          {step === 3 && (
            <div className="space-y-4" data-testid="broker-step-3">
              <h2 className="text-xl font-semibold">{lang === 'fr' ? '3. Structure de frais' : '3. Fee Structure'}</h2>
              <div className="flex gap-2">
                <button
                  className={`flex-1 p-3 rounded-lg border-2 ${form.fee_type === 'fixed' ? 'border-[#1E3A8A] bg-blue-50 dark:bg-blue-950' : 'border-slate-200 dark:border-slate-700'}`}
                  onClick={() => set('fee_type', 'fixed')}
                  data-testid="fee-type-fixed"
                >
                  <div className="font-semibold">{lang === 'fr' ? 'Frais fixe' : 'Fixed Fee'}</div>
                  <div className="text-xs text-slate-500">{lang === 'fr' ? 'p. ex. 500 $ par véhicule' : 'e.g. $500 per car'}</div>
                </button>
                <button
                  className={`flex-1 p-3 rounded-lg border-2 ${form.fee_type === 'percentage' ? 'border-[#1E3A8A] bg-blue-50 dark:bg-blue-950' : 'border-slate-200 dark:border-slate-700'}`}
                  onClick={() => set('fee_type', 'percentage')}
                  data-testid="fee-type-percentage"
                >
                  <div className="font-semibold">{lang === 'fr' ? 'Pourcentage' : 'Percentage'}</div>
                  <div className="text-xs text-slate-500">{lang === 'fr' ? 'p. ex. 3 % du prix final' : 'e.g. 3% of hammer'}</div>
                </button>
              </div>
              {form.fee_type === 'fixed' ? (
                <div>
                  <Label>{lang === 'fr' ? 'Montant fixe ($ CAD)' : 'Fixed Amount (CAD $)'} *</Label>
                  <Input type="number" min="0" value={form.fixed_amount_cad} onChange={(e) => set('fixed_amount_cad', e.target.value)} data-testid="fixed-amount" />
                </div>
              ) : (
                <div>
                  <Label>{lang === 'fr' ? 'Pourcentage (%)' : 'Percentage Rate (%)'} *</Label>
                  <Input type="number" min="0" max="100" step="0.5" value={(Number(form.percentage_rate) * 100).toFixed(2)}
                         onChange={(e) => set('percentage_rate', (Number(e.target.value) || 0) / 100)}
                         data-testid="pct-rate" />
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>{lang === 'fr' ? 'Frais min. (optionnel)' : 'Min Fee (optional)'}</Label>
                  <Input type="number" min="0" value={form.min_fee_cad} onChange={(e) => set('min_fee_cad', e.target.value)} data-testid="min-fee" />
                </div>
                <div>
                  <Label>{lang === 'fr' ? 'Frais max. (optionnel)' : 'Max Fee (optional)'}</Label>
                  <Input type="number" min="0" value={form.max_fee_cad} onChange={(e) => set('max_fee_cad', e.target.value)} data-testid="max-fee" />
                </div>
              </div>
              <Alert className="bg-blue-50 dark:bg-blue-950 border-blue-200">
                <AlertDescription data-testid="fee-preview">
                  {lang === 'fr'
                    ? `Sur un véhicule de 15 000 $, vos frais seraient : ${_fmt(sampleFee)}`
                    : `On a $15,000 vehicle your fee would be: ${_fmt(sampleFee)}`}
                </AlertDescription>
              </Alert>
            </div>
          )}

          {/* Step 4 — Legal */}
          {step === 4 && (
            <div className="space-y-4" data-testid="broker-step-4">
              <h2 className="text-xl font-semibold">{lang === 'fr' ? '4. Confirmation légale' : '4. Legal Confirmation'}</h2>
              <Alert>
                <AlertDescription>
                  {lang === 'fr'
                    ? `Je confirme que je détiens un permis de courtier / concessionnaire valide en ${province.name_fr} et que je suis légalement autorisé à agir comme courtier pour les transactions de véhicules conformément aux règlements de ${province.regulator}.`
                    : `I confirm I hold a valid commercial broker / dealer permit in ${province.name_en} and am legally authorized to act as a broker for vehicle transactions under ${province.regulator} regulations.`}
                </AlertDescription>
              </Alert>
              <label className="flex items-start gap-3 cursor-pointer">
                <input type="checkbox" checked={form.legal_confirmed}
                       onChange={(e) => set('legal_confirmed', e.target.checked)}
                       data-testid="legal-confirm" className="mt-1 h-5 w-5" />
                <span className="text-sm">
                  {lang === 'fr' ? 'J\'accepte et je confirme.' : 'I agree and confirm.'}
                </span>
              </label>
            </div>
          )}

          {/* Nav */}
          <div className="flex justify-between pt-4 border-t">
            <Button variant="outline" onClick={goBack} disabled={step === 1 || submitting} data-testid="broker-back">
              <ChevronLeft className="h-4 w-4 mr-1" />{lang === 'fr' ? 'Retour' : 'Back'}
            </Button>
            {step < 4 ? (
              <Button onClick={goNext} disabled={!canAdvance() || submitting} data-testid="broker-next">
                {lang === 'fr' ? 'Continuer' : 'Continue'}
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            ) : (
              <Button onClick={handleSubmit} disabled={!canAdvance() || submitting}
                className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white"
                data-testid="broker-submit">
                {submitting ? (lang === 'fr' ? 'Envoi...' : 'Submitting...') : (lang === 'fr' ? 'Soumettre la demande' : 'Submit Application')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
