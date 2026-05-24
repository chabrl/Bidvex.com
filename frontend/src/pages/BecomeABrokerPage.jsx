/**
 * iter217 Phase 5 Hotfix v6.5 — Broker application form.
 *
 * Public route: /become-a-broker (EN) | /devenir-courtier (FR)
 *
 * 4-step wizard:
 *   1. Business information (legal name, province, registration, license)
 *   2. Document upload — Broker License, Corporate Registration, Government ID
 *      (PDF/JPG/PNG, max 10 MB each, OPTIONAL — can be added later from dashboard)
 *   3. Fee structure (fixed | percentage + min/max clamps)
 *   4. Pricing + Legal confirmation + submit
 *      Displays the BidVex Broker Annual Plan: $200 CAD/yr regular,
 *      $100 CAD/yr current (Launch Offer — 50% OFF).
 *
 * Submitting POSTs to /api/brokers/apply. Documents (if attached) are
 * uploaded via /api/brokers/upload-documents BEFORE the apply call so
 * the document URLs are persisted onto the broker doc.
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
import BrokerLiabilityAgreementModal from '../components/broker/BrokerLiabilityAgreementModal';
import {
  CheckCircle2, ChevronRight, ChevronLeft, AlertTriangle,
  Upload, FileText, FileImage, X, Loader2, Sparkles, Scale, ShieldCheck,
} from 'lucide-react';

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

const MAX_FILE_BYTES = 10 * 1024 * 1024;          // 10 MB
const ACCEPTED_MIME = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
const ACCEPT_ATTR = '.pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp';

const _fmt = (n) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n || 0));

// ── Reusable single-file upload zone (mirrors partner-registration UX) ──
function BrokerDocUploadZone({ id, file, onPick, onClear, label, hint, lang, testId }) {
  const isImage = file && file.type?.startsWith('image/');
  const previewUrl = isImage ? URL.createObjectURL(file) : null;
  return (
    <div className="space-y-1.5">
      <Label className="text-slate-700 dark:text-slate-300 text-xs font-medium">
        {label} <span className="text-slate-400">{hint}</span>
      </Label>
      <input
        type="file"
        id={id}
        accept={ACCEPT_ATTR}
        onChange={(e) => onPick(e.target.files?.[0] || null)}
        className="hidden"
        data-testid={testId}
      />
      {!file ? (
        <label
          htmlFor={id}
          className="flex items-center gap-2 px-4 py-3 rounded-lg border border-dashed border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800/40 text-slate-500 hover:border-blue-400 hover:text-blue-600 cursor-pointer transition-colors text-sm"
        >
          <Upload className="w-4 h-4 flex-shrink-0" />
          {lang === 'fr' ? 'Choisir un fichier (PDF, JPG, PNG · max 10 Mo)' : 'Choose a file (PDF, JPG, PNG · max 10MB)'}
        </label>
      ) : (
        <div
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-emerald-200 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-950/30"
          data-testid={`${testId}-preview`}
        >
          {previewUrl ? (
            <img
              src={previewUrl}
              alt={file.name}
              className="w-12 h-12 rounded object-cover flex-shrink-0"
              onLoad={() => URL.revokeObjectURL(previewUrl)}
            />
          ) : (
            <div className="w-12 h-12 rounded bg-rose-100 dark:bg-rose-900/40 flex items-center justify-center flex-shrink-0">
              <FileText className="w-6 h-6 text-rose-600 dark:text-rose-300" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{file.name}</p>
            <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB · {file.type || 'unknown'}</p>
          </div>
          <button
            type="button"
            onClick={onClear}
            className="p-1.5 rounded-md hover:bg-rose-100 dark:hover:bg-rose-900/30 text-rose-500"
            data-testid={`${testId}-remove`}
            aria-label="Remove file"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}

export default function BecomeABrokerPage() {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';

  const [step, setStep]         = useState(1);
  const [submitting, setSubmit] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError]       = useState(null);
  const [success, setSuccess]   = useState(false);

  const [form, setForm] = useState({
    legal_business_name: '',
    operating_province:  'ON',
    corporate_registration_number: '',
    broker_license_number: '',
    permit_type:         'broker',

    // iter225 Task 2 — Dynamic Provincial Registration fields
    qc_anq_number:       '',
    qc_opc_number:       '',
    on_omvic_number:     '',
    bc_vsa_number:       '',
    ab_amvic_number:     '',

    fee_type:            'fixed',     // fixed | percentage
    fixed_amount_cad:    500,
    percentage_rate:     0.03,        // 3%
    min_fee_cad:         '',
    max_fee_cad:         '',
    default_deposit_amount_cad: 500,

    legal_confirmed:     false,
  });

  // iter225 Task 3 — Liability agreement gating
  const [liabilityModalOpen, setLiabilityModalOpen] = useState(false);
  const [liabilitySigned, setLiabilitySigned]       = useState(false);

  // Step 2 — document upload state
  const [licenseFile,      setLicenseFile]      = useState(null);
  const [registrationFile, setRegistrationFile] = useState(null);
  const [idFile,           setIdFile]           = useState(null);

  const province = PROVINCES.find(p => p.code === form.operating_province) || PROVINCES[0];

  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  const validateFile = (f) => {
    if (!f) return null;
    if (f.size > MAX_FILE_BYTES) {
      return lang === 'fr'
        ? `Le fichier "${f.name}" dépasse 10 Mo.`
        : `File "${f.name}" exceeds 10MB.`;
    }
    if (!ACCEPTED_MIME.includes(f.type)) {
      return lang === 'fr'
        ? `Type de fichier non supporté pour "${f.name}". Utilisez PDF, JPG, PNG ou WebP.`
        : `Unsupported file type for "${f.name}". Use PDF, JPG, PNG or WebP.`;
    }
    return null;
  };

  const pickFile = (setter) => (f) => {
    const e = validateFile(f);
    if (e) { setError(e); return; }
    setError(null);
    setter(f);
  };

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
    if (step === 1) {
      if (!(form.legal_business_name && form.corporate_registration_number && form.broker_license_number)) return false;
      // iter225 Task 2 — Province-specific license fields are required (bilingual gate)
      if (form.operating_province === 'QC' && !(form.qc_anq_number.trim() || form.qc_opc_number.trim())) return false;
      if (form.operating_province === 'ON' && !form.on_omvic_number.trim()) return false;
      if (form.operating_province === 'BC' && !form.bc_vsa_number.trim()) return false;
      if (form.operating_province === 'AB' && !form.ab_amvic_number.trim()) return false;
      return true;
    }
    if (step === 2) return true;  // Docs always optional
    if (step === 3) {
      if (form.fee_type === 'fixed') return Number(form.fixed_amount_cad) > 0;
      return Number(form.percentage_rate) > 0;
    }
    if (step === 4) return form.legal_confirmed && liabilitySigned;
    return true;
  };

  const uploadDocsIfAny = async (token) => {
    if (!licenseFile && !registrationFile && !idFile) return {};
    setUploading(true);
    try {
      const fd = new FormData();
      if (licenseFile)      fd.append('license_document', licenseFile);
      if (registrationFile) fd.append('registration_document', registrationFile);
      if (idFile)           fd.append('additional_documents', idFile);
      const r = await axios.post(`${API_BASE}/brokers/upload-documents`, fd, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
      });
      return r.data || {};
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    setSubmit(true); setError(null);
    try {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');

      // 1) Upload documents first (if any) so they get attached on apply
      let docUrls = {};
      try {
        docUrls = await uploadDocsIfAny(token);
      } catch (e) {
        // Surface but don't block — user can re-upload later
        const msg = e?.response?.data?.detail?.message || e?.response?.data?.detail || e?.message || 'Document upload failed.';
        setError(lang === 'fr'
          ? `Téléversement des documents échoué (vous pourrez les ajouter plus tard) : ${msg}`
          : `Document upload failed (you can add them later from your dashboard): ${msg}`);
      }

      const payload = {
        legal_business_name:           form.legal_business_name.trim(),
        operating_province:            form.operating_province,
        corporate_registration_number: form.corporate_registration_number.trim(),
        broker_license_number:         form.broker_license_number.trim(),
        regulatory_body:               province.regulator,
        permit_type:                   form.permit_type,
        license_document_url:          docUrls.license_document_url || null,
        registration_document_url:     docUrls.registration_document_url || null,
        additional_documents:          docUrls.additional_documents || [],
        // iter225 Task 2 — Dynamic Provincial Registration
        qc_anq_number:   form.qc_anq_number.trim()  || null,
        qc_opc_number:   form.qc_opc_number.trim()  || null,
        on_omvic_number: form.on_omvic_number.trim() || null,
        bc_vsa_number:   form.bc_vsa_number.trim()  || null,
        ab_amvic_number: form.ab_amvic_number.trim() || null,
        fee_structure: {
          type:              form.fee_type,
          fixed_amount_cad:  Number(form.fixed_amount_cad) || 0,
          percentage_rate:   Number(form.percentage_rate) || 0,
          min_fee_cad:       form.min_fee_cad !== '' ? Number(form.min_fee_cad) : null,
          max_fee_cad:       form.max_fee_cad !== '' ? Number(form.max_fee_cad) : null,
        },
        default_deposit_amount_cad: Number(form.default_deposit_amount_cad) || 500,
      };
      const r = await axios.post(`${API_BASE}/brokers/apply`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.data?.success) {
        setSuccess(true);
        setTimeout(() => navigate('/broker/dashboard'), 1800);
      }
    } catch (e) {
      setError(
        e?.response?.data?.detail?.[lang === 'fr' ? 'message_fr' : 'message_en']
        || e?.response?.data?.detail?.error
        || (typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : null)
        || (lang === 'fr' ? 'Échec de la soumission.' : 'Submission failed.')
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

              {/* iter225 Task 2 — Dynamic Provincial Registration Fields */}
              <ProvincialLicenseFields province={form.operating_province} form={form} set={set} lang={lang} />

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

          {/* Step 2 — Document Upload (functional, partner-style) */}
          {step === 2 && (
            <div className="space-y-4" data-testid="broker-step-2">
              <h2 className="text-xl font-semibold">{lang === 'fr' ? '2. Téléversement des documents' : '2. Document Upload'}</h2>
              <Alert>
                <FileImage className="h-4 w-4" />
                <AlertDescription>
                  {lang === 'fr'
                    ? 'Vous pouvez également téléverser ces documents après l\'inscription depuis votre tableau de bord de courtier. Chaque fichier : PDF, JPG ou PNG, maximum 10 Mo.'
                    : 'You may also upload these documents after registration from your Broker Dashboard. Each file: PDF, JPG or PNG, max 10MB.'}
                </AlertDescription>
              </Alert>

              <BrokerDocUploadZone
                id="broker-license-upload"
                file={licenseFile}
                onPick={pickFile(setLicenseFile)}
                onClear={() => setLicenseFile(null)}
                label={lang === 'fr' ? 'Permis de courtier / concessionnaire' : 'Broker / Dealer License'}
                hint={lang === 'fr' ? '(optionnel)' : '(optional)'}
                lang={lang}
                testId="broker-doc-license"
              />
              <BrokerDocUploadZone
                id="broker-reg-upload"
                file={registrationFile}
                onPick={pickFile(setRegistrationFile)}
                onClear={() => setRegistrationFile(null)}
                label={lang === 'fr' ? 'Certificat d\'immatriculation' : 'Corporate Registration Certificate'}
                hint={lang === 'fr' ? '(optionnel)' : '(optional)'}
                lang={lang}
                testId="broker-doc-registration"
              />
              <BrokerDocUploadZone
                id="broker-id-upload"
                file={idFile}
                onPick={pickFile(setIdFile)}
                onClear={() => setIdFile(null)}
                label={lang === 'fr' ? 'Pièce d\'identité du contact principal' : 'Government-Issued ID of Primary Contact'}
                hint={lang === 'fr' ? '(optionnel)' : '(optional)'}
                lang={lang}
                testId="broker-doc-id"
              />
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

          {/* Step 4 — Subscription pricing + Legal */}
          {step === 4 && (
            <div className="space-y-4" data-testid="broker-step-4">
              <h2 className="text-xl font-semibold">{lang === 'fr' ? '4. Tarification & Confirmation légale' : '4. Pricing & Legal Confirmation'}</h2>

              {/* BidVex Broker Annual Plan — pricing card */}
              <div
                className="relative overflow-hidden rounded-xl border-2 border-blue-300 dark:border-blue-700 bg-gradient-to-br from-blue-50 via-white to-cyan-50 dark:from-blue-950/50 dark:via-slate-900 dark:to-cyan-950/50 p-5 shadow-sm"
                data-testid="broker-pricing-card"
              >
                <div className="absolute top-3 right-3">
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500 text-white text-[11px] font-bold tracking-wide shadow">
                    <Sparkles className="w-3 h-3" />
                    {lang === 'fr' ? 'Offre de lancement — 50 % DE RABAIS' : 'Launch Offer — 50% OFF'}
                  </span>
                </div>
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-300 mb-1">
                  {lang === 'fr' ? 'Forfait annuel BidVex Broker' : 'BidVex Broker Annual Plan'}
                </p>
                <div className="flex items-end gap-3 mt-2 flex-wrap">
                  <span className="text-3xl font-bold text-slate-900 dark:text-white" data-testid="broker-price-current">
                    $100.00 CAD
                  </span>
                  <span className="text-sm text-slate-500 line-through" data-testid="broker-price-original">
                    $200.00 CAD
                  </span>
                  <span className="text-xs text-slate-500">{lang === 'fr' ? '/ an' : '/ year'}</span>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-3 leading-relaxed">
                  {lang === 'fr'
                    ? 'Tarification de lancement à durée limitée. Le tarif régulier s\'applique au renouvellement, sauf indication contraire de BidVex. Renouvellement automatique avec avis par courriel 30 jours avant la date de renouvellement.'
                    : 'Limited-time launch pricing. Regular price applies upon renewal unless otherwise updated by BidVex. Auto-renews yearly with an email notification 30 days before renewal.'}
                </p>
                <p className="text-[11px] text-slate-500 mt-2">
                  {lang === 'fr'
                    ? 'Aucun paiement requis aujourd\'hui — la facturation commence après l\'approbation par l\'équipe BidVex.'
                    : 'No payment required today — billing begins after BidVex approves your application.'}
                </p>
              </div>

              <Alert>
                <AlertDescription>
                  {lang === 'fr'
                    ? `Je confirme que je détiens un permis de courtier / concessionnaire valide en ${province.name_fr} et que je suis légalement autorisé à agir comme courtier pour les transactions de véhicules conformément aux règlements de ${province.regulator}.`
                    : `I confirm I hold a valid commercial broker / dealer permit in ${province.name_en} and am legally authorized to act as a broker for vehicle transactions under ${province.regulator} regulations.`}
                </AlertDescription>
              </Alert>

              {/* iter225 Task 3 — 3-Tier Liability Agreement with forced scroll */}
              <div
                className={`rounded-lg border-2 p-4 ${liabilitySigned
                  ? 'border-emerald-300 bg-emerald-50 dark:bg-emerald-950/30'
                  : 'border-rose-300 bg-rose-50 dark:bg-rose-950/30'}`}
                data-testid="broker-liability-block"
              >
                <div className="flex items-start gap-3 mb-3">
                  <Scale className={`w-5 h-5 mt-0.5 flex-shrink-0 ${liabilitySigned ? 'text-emerald-600' : 'text-rose-600'}`} />
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm">
                      {lang === 'fr' ? 'Accord de responsabilité du courtier (obligatoire)' : 'Broker Liability Agreement (required)'}
                    </p>
                    <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
                      {lang === 'fr'
                        ? '3 sections juridiques. Doit être défilé à 100 % et signé numériquement avant de soumettre la demande.'
                        : 'Three legal sections. Must be scrolled 100% and digitally signed before you can submit your application.'}
                    </p>
                  </div>
                </div>
                {liabilitySigned ? (
                  <div className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-300 font-medium" data-testid="liability-signed-badge">
                    <ShieldCheck className="w-4 h-4" />
                    {lang === 'fr' ? 'Accord signé numériquement' : 'Agreement digitally signed'}
                  </div>
                ) : (
                  <Button
                    onClick={() => setLiabilityModalOpen(true)}
                    type="button"
                    className="w-full bg-gradient-to-r from-rose-600 to-amber-600 text-white hover:opacity-90"
                    data-testid="open-liability-modal"
                  >
                    <Scale className="w-4 h-4 mr-2" />
                    {lang === 'fr' ? 'Lire et signer l\'accord' : 'Read & Sign Agreement'}
                  </Button>
                )}
              </div>

              <label className="flex items-start gap-3 cursor-pointer">
                <input type="checkbox" checked={form.legal_confirmed}
                       onChange={(e) => set('legal_confirmed', e.target.checked)}
                       data-testid="legal-confirm" className="mt-1 h-5 w-5" />
                <span className="text-sm">
                  {lang === 'fr'
                    ? 'J\'accepte les Conditions d\'utilisation, la Politique de confidentialité et la tarification de lancement ci-dessus.'
                    : 'I agree to the Terms of Service, Privacy Policy, and the launch pricing above.'}
                </span>
              </label>
            </div>
          )}

          {/* Nav */}
          <div className="flex justify-between pt-4 border-t">
            <Button variant="outline" onClick={goBack} disabled={step === 1 || submitting || uploading} data-testid="broker-back">
              <ChevronLeft className="h-4 w-4 mr-1" />{lang === 'fr' ? 'Retour' : 'Back'}
            </Button>
            {step < 4 ? (
              <Button onClick={goNext} disabled={!canAdvance() || submitting || uploading} data-testid="broker-next">
                {lang === 'fr' ? 'Continuer' : 'Continue'}
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            ) : (
              <Button onClick={handleSubmit} disabled={!canAdvance() || submitting || uploading}
                className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white"
                data-testid="broker-submit">
                {(submitting || uploading) ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                {uploading
                  ? (lang === 'fr' ? 'Téléversement…' : 'Uploading…')
                  : submitting
                    ? (lang === 'fr' ? 'Envoi…' : 'Submitting…')
                    : (lang === 'fr' ? 'Soumettre la demande' : 'Submit Application')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* iter225 Task 3 — Liability Agreement Modal */}
      <BrokerLiabilityAgreementModal
        open={liabilityModalOpen}
        lang={lang}
        onClose={() => setLiabilityModalOpen(false)}
        onSigned={() => { setLiabilitySigned(true); }}
      />
    </div>
  );
}

// iter225 Task 2 — Dynamic Provincial Registration Fields component
function ProvincialLicenseFields({ province, form, set, lang }) {
  if (province === 'QC') {
    return (
      <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4 space-y-3" data-testid="provincial-fields-qc">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-300">
          {lang === 'fr' ? 'Inscriptions requises au Québec' : 'Required Quebec Registrations'}
        </p>
        <div>
          <Label>{lang === 'fr' ? 'Numéro d\'inscription ANQ (Autorité des marchés publics — véhicules)' : 'ANQ Registration # (Autorité des marchés publics — vehicles)'} *</Label>
          <Input
            value={form.qc_anq_number}
            onChange={(e) => set('qc_anq_number', e.target.value)}
            placeholder="ANQ-XXXX-XXXX"
            data-testid="qc-anq-number"
          />
        </div>
        <div>
          <Label>{lang === 'fr' ? 'Numéro de permis OPC (Office de la protection du consommateur)' : 'OPC Permit # (Office de la protection du consommateur)'} *</Label>
          <Input
            value={form.qc_opc_number}
            onChange={(e) => set('qc_opc_number', e.target.value)}
            placeholder="OPC-XXXXXX"
            data-testid="qc-opc-number"
          />
        </div>
        <p className="text-[11px] text-slate-500">
          {lang === 'fr'
            ? 'Au moins un des deux numéros est obligatoire pour exploiter au Québec.'
            : 'At least one of the two numbers is required to operate in Quebec.'}
        </p>
      </div>
    );
  }
  if (province === 'ON') {
    return (
      <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4 space-y-3" data-testid="provincial-fields-on">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-300">
          {lang === 'fr' ? 'Inscription requise en Ontario' : 'Required Ontario Registration'}
        </p>
        <div>
          <Label>{lang === 'fr' ? 'Numéro de registraire OMVIC' : 'OMVIC Registrant #'} *</Label>
          <Input
            value={form.on_omvic_number}
            onChange={(e) => set('on_omvic_number', e.target.value)}
            placeholder="OMVIC-1234567"
            data-testid="on-omvic-number"
          />
        </div>
        <p className="text-[11px] text-slate-500">
          {lang === 'fr'
            ? 'Tous les courtiers automobiles doivent être inscrits auprès de l\'OMVIC en Ontario.'
            : 'All vehicle brokers must be registered with OMVIC in Ontario.'}
        </p>
      </div>
    );
  }
  if (province === 'BC') {
    return (
      <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4 space-y-3" data-testid="provincial-fields-bc">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-300">
          {lang === 'fr' ? 'Inscription requise en C.-B.' : 'Required British Columbia Registration'}
        </p>
        <div>
          <Label>{lang === 'fr' ? 'Numéro d\'inscription VSA (Vehicle Sales Authority)' : 'VSA Registration # (Vehicle Sales Authority)'} *</Label>
          <Input
            value={form.bc_vsa_number}
            onChange={(e) => set('bc_vsa_number', e.target.value)}
            placeholder="VSA-XXXXX"
            data-testid="bc-vsa-number"
          />
        </div>
        <p className="text-[11px] text-slate-500">
          {lang === 'fr'
            ? 'Les courtiers doivent être inscrits auprès de la VSA en Colombie-Britannique.'
            : 'Brokers must be registered with the VSA in British Columbia.'}
        </p>
      </div>
    );
  }
  if (province === 'AB') {
    return (
      <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4 space-y-3" data-testid="provincial-fields-ab">
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-300">
          {lang === 'fr' ? 'Inscription requise en Alberta' : 'Required Alberta Registration'}
        </p>
        <div>
          <Label>{lang === 'fr' ? 'Numéro d\'industrie AMVIC' : 'AMVIC Business #'} *</Label>
          <Input
            value={form.ab_amvic_number}
            onChange={(e) => set('ab_amvic_number', e.target.value)}
            placeholder="AMVIC-XXXX"
            data-testid="ab-amvic-number"
          />
        </div>
      </div>
    );
  }
  // Other provinces — no additional fields, the standard broker_license_number above is enough
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 p-3 text-xs text-slate-500" data-testid="provincial-fields-generic">
      {lang === 'fr'
        ? 'Aucune inscription provinciale supplémentaire requise au-delà du numéro de permis ci-dessus.'
        : 'No additional provincial registration required beyond the broker / dealer license above.'}
    </div>
  );
}
