import API_BASE from '../../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate, useSearchParams } from 'react-router-dom';
import SaveAsDraftButton from '../../components/SaveAsDraftButton';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { Loader2, Upload, ImagePlus, FileSpreadsheet } from 'lucide-react';
import AcceptedPaymentMethodsSelector from '../../components/AcceptedPaymentMethodsSelector';

const API = API_BASE;
const SIZES = ['5x5', '5x10', '10x10', '10x15', '10x20', '10x30+'];
const TYPES = [
  { v: 'indoor', en: 'Indoor', fr: 'Intérieur' },
  { v: 'outdoor', en: 'Outdoor', fr: 'Extérieur' },
  { v: 'climate_controlled', en: 'Climate Controlled', fr: 'Climatisé' },
  { v: 'drive_up', en: 'Drive-Up', fr: 'Accès véhicule' },
];

const StorageAuctionCreate = () => {
  const { t, i18n } = useTranslation();
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const isFr = (i18n.language || '').startsWith('fr');
  // iter299 P0 — Bill 96 applies to Quebec-based facilities.
  const isQuebecFacility = ['qc', 'quebec', 'québec'].includes(
    String(user?.province || '').trim().toLowerCase()
  );

  const [form, setForm] = useState({
    unit_number: '', unit_size: '10x10', unit_type: 'indoor',
    is_lien_unit: false, past_due_balance: '',
    description_en: '', description_fr: '',
    photos: [], video_url: '',
    starting_price: 1, reserve_price: '', bid_increment: 10,
    start_time: '', end_time: '',
    cleanup_deadline_hours: 72,
    // ── Payment method (single) — LEGACY ──
    payment_method: 'stripe',
    // iter482 P4B — Seller-Controlled Accepted Payment Methods (multi-select)
    accepted_payment_methods: ['stripe'],
    // ── iter445 — Storage buyer's premium is FIXED at 5 % (platform policy).
    // The field is no longer configurable by facilities; server ignores
    // any client-sent value.
    // ── iter216 P1 — Legal-notice confirmation (mandatory before publish) ──
    accepted_legal_notice: false,
    // ── Currency (Spec Global Rule 1) ──
    currency: 'CAD',
    // ── Optional participation deposit ──
    deposit_required: false,
    deposit_amount: '',
    deposit_type: 'fixed',  // "fixed" | "percentage" (Spec Feature 1)
    soft_close_enabled: true, soft_close_extension_minutes: 2,
  });
  const [submitting, setSubmitting] = useState(false);
  const [uploadingIdx, setUploadingIdx] = useState(false);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  // iter313 — Hydrate from /api/drafts/{id} when ?draft_id=X is on URL.
  const [searchParamsLocal] = useSearchParams();
  const hydratedDraftId = searchParamsLocal.get('draft_id');
  useEffect(() => {
    if (!hydratedDraftId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/drafts/${hydratedDraftId}`);
        const p = r.data?.payload || {};
        if (cancelled) return;
        setForm((prev) => ({ ...prev, ...p, draft_id: hydratedDraftId }));
      } catch { /* silent */ }
    })();
    return () => { cancelled = true; };
  }, [hydratedDraftId]);

  const uploadPhotos = async (files) => {
    setUploadingIdx(true);
    const urls = [];
    try {
      for (const f of files) {
        const fd = new FormData();
        fd.append('file', f);
        const res = await axios.post(`${API}/storage-facilities/upload-photo`, fd, {
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
        });
        if (res.data?.url) urls.push(res.data.url);
      }
      set('photos', [...form.photos, ...urls].slice(0, 10));
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploadingIdx(false);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.start_time || !form.end_time) { toast.error('Set start & end times'); return; }
    if (new Date(form.start_time) >= new Date(form.end_time)) {
      toast.error(t('storage.create.endTimeMustBeAfterStartTime'));
      return;
    }
    if (form.deposit_required && (!form.deposit_amount || parseFloat(form.deposit_amount) <= 0)) {
      toast.error(t('storage.create.setADepositAmount0'));
      return;
    }
    // iter216 P1 — Mandatory legal-notice + photo minimum
    if (!form.accepted_legal_notice) {
      toast.error(isFr
        ? 'Veuillez confirmer le processus de notification légale.'
        : 'Please confirm the legal-notification process.');
      return;
    }
    if (!form.photos || form.photos.length < 1) {
      toast.error(isFr
        ? 'Veuillez téléverser au moins 1 photo de l\'unité.'
        : 'Please upload at least 1 photo of the unit.');
      return;
    }
    // iter482 P4B — block publish if seller didn't choose ≥ 1 accepted method
    if (!form.accepted_payment_methods || form.accepted_payment_methods.length === 0) {
      toast.error(isFr
        ? 'Veuillez sélectionner au moins un mode de paiement.'
        : 'Please select at least one payment method.');
      return;
    }
    // iter299 P0 — Bill 96: QC facilities must provide a French description.
    if (isQuebecFacility && !String(form.description_fr || '').trim()) {
      toast.error(isFr
        ? 'Une description en français est obligatoire pour les annonces québécoises (Loi 96).'
        : 'A French description is required for Quebec listings under Bill 96.');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        starting_price: parseFloat(form.starting_price) || 1,
        reserve_price: form.reserve_price ? parseFloat(form.reserve_price) : null,
        past_due_balance: form.past_due_balance ? parseFloat(form.past_due_balance) : null,
        bid_increment: parseFloat(form.bid_increment) || 10,
        cleanup_deadline_hours: parseInt(form.cleanup_deadline_hours) || 72,
        deposit_amount: form.deposit_required && form.deposit_amount
          ? parseFloat(form.deposit_amount) : null,
        deposit_type: form.deposit_required ? form.deposit_type : null,
        currency: (form.currency || 'CAD').toUpperCase(),
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
        // iter445 — Buyer's premium is fixed platform policy (5 %); not
        // sent from the client. Server stamps the value regardless.
      };
      const res = await axios.post(`${API}/storage-facilities/auctions`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(t('storage.create.auctionCreated'));
      navigate(`/storage-auctions/${res.data.id}`);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object' && detail) ? (isFr ? detail.message_fr : detail.message_en) : detail;
      toast.error(msg || 'Failed to create');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-8" data-testid="storage-auction-create">
      <div className="max-w-3xl mx-auto px-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6 gap-3">
          <div>
            <h1 className="text-2xl font-bold mb-1">{t('storage.create.createNewAuction')}</h1>
            <p className="text-sm text-muted-foreground">{t('storage.create.listANewStorageUnitForAuction')}</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* iter446 — Storage Facility CSV Bulk Import shortcut */}
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/storage-auctions/bulk-import')}
              className="border-cyan-500 text-cyan-700 hover:bg-cyan-50"
              data-testid="storage-bulk-import-cta"
            >
              <FileSpreadsheet className="h-4 w-4 mr-2" />
              {isFr ? 'Importer plusieurs unités (CSV)' : 'Bulk import units (CSV)'}
            </Button>
            {/* iter313 — Universal Save-as-Draft, visible at every step */}
            <SaveAsDraftButton
              type="storage"
              formData={form}
              draftId={form.draft_id || null}
              onSaved={(id) => set('draft_id', id)}
            />
          </div>
        </div>
        <Card className="p-6">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>{t('storage.create.unitNumber')} *</Label>
                <Input required value={form.unit_number} onChange={e => set('unit_number', e.target.value)} placeholder="A-12" />
              </div>
              <div>
                <Label>{t('storage.create.size')} *</Label>
                <Select value={form.unit_size} onValueChange={v => set('unit_size', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{SIZES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>{t('storage.create.type')} *</Label>
                <Select value={form.unit_type} onValueChange={v => set('unit_type', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{TYPES.map(t => <SelectItem key={t.v} value={t.v}>{isFr ? t.fr : t.en}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-950/30 rounded-lg">
              <Checkbox checked={form.is_lien_unit} onCheckedChange={v => set('is_lien_unit', v === true)} className="mt-0.5" />
              <div className="flex-1">
                <Label className="cursor-pointer">{t('storage.create.lienUnit')}</Label>
                <p className="text-[11px] text-muted-foreground">{t('storage.create.tenantInDefaultOfPayment')}</p>
                {form.is_lien_unit && (
                  <Input className="mt-2" type="number" step="0.01" placeholder={t('storage.create.pastDueBalance')}
                    value={form.past_due_balance} onChange={e => set('past_due_balance', e.target.value)} />
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>{t('storage.create.descriptionEn')} *</Label>
                <Textarea required rows={3} value={form.description_en} onChange={e => set('description_en', e.target.value)} />
              </div>
              <div>
                <Label>
                  {t('storage.create.descriptionFr')}
                  {isQuebecFacility && <span className="text-red-600"> *</span>}
                </Label>
                <Textarea
                  rows={3}
                  value={form.description_fr}
                  onChange={e => set('description_fr', e.target.value)}
                  data-testid="storage-description-fr-input"
                />
                {isQuebecFacility && (
                  <p className="text-xs text-slate-500 mt-1" data-testid="storage-bill96-helper">
                    {isFr
                      ? 'Obligatoire pour les annonces québécoises (Loi 96)'
                      : 'Required for Quebec listings under Bill 96 / Obligatoire pour les annonces québécoises (Loi 96)'}
                  </p>
                )}
              </div>
            </div>

            {/* Photos */}
            <div>
              <Label>{t('storage.create.photosMax10')}</Label>
              <div className="flex gap-2 flex-wrap mt-2">
                {form.photos.map((url, i) => (
                  <div key={i} className="relative w-20 h-20 rounded-lg overflow-hidden border">
                    <img src={url} alt={`photo ${i}`} className="w-full h-full object-cover" />
                    <button type="button" onClick={() => set('photos', form.photos.filter((_, j) => j !== i))}
                      className="absolute top-0 right-0 bg-red-500 text-white text-xs w-5 h-5">×</button>
                  </div>
                ))}
                {form.photos.length < 10 && (
                  <label className="w-20 h-20 border-2 border-dashed rounded-lg flex items-center justify-center cursor-pointer hover:border-blue-500">
                    {uploadingIdx ? <Loader2 className="h-5 w-5 animate-spin" /> : <ImagePlus className="h-5 w-5" />}
                    <input type="file" accept="image/*" multiple className="hidden"
                      onChange={e => uploadPhotos(Array.from(e.target.files || []))} />
                  </label>
                )}
              </div>
            </div>

            <div>
              <Label>{t('storage.create.videoUrlOptional')}</Label>
              <Input type="url" value={form.video_url} onChange={e => set('video_url', e.target.value)} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>{t('storage.create.startingPrice')} *</Label>
                <Input type="number" step="0.01" required value={form.starting_price} onChange={e => set('starting_price', e.target.value)} />
              </div>
              <div>
                <Label>{t('storage.create.reservePrice')}</Label>
                <Input type="number" step="0.01" value={form.reserve_price} onChange={e => set('reserve_price', e.target.value)} />
              </div>
              <div>
                <Label>{t('storage.create.bidIncrement')}</Label>
                <Input type="number" step="1" value={form.bid_increment} onChange={e => set('bid_increment', e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>{t('storage.create.startTime')} *</Label>
                <Input type="datetime-local" required value={form.start_time} onChange={e => set('start_time', e.target.value)} />
              </div>
              <div>
                <Label>{t('storage.create.endTime')} *</Label>
                <Input type="datetime-local" required value={form.end_time} onChange={e => set('end_time', e.target.value)} />
              </div>
            </div>

            <div>
              <Label>{t('storage.create.cleanupDeadlineHoursAfterEnd')}</Label>
              <Input type="number" min="24" max="168" value={form.cleanup_deadline_hours} onChange={e => set('cleanup_deadline_hours', e.target.value)} />
            </div>

            {/* ── PAYMENT SETTINGS ── */}
            <div className="space-y-3 p-4 border rounded-lg bg-blue-50/40 dark:bg-blue-950/20">
              <div className="flex items-center justify-between">
                <Label className="text-base font-semibold">
                  {t('storage.create.paymentSettings')}
                </Label>
              </div>

              {/* Currency Selector (Spec Global Rule 1) */}
              <div className="space-y-2 pt-2" data-testid="storage-currency-section">
                <Label className="text-sm">{t('storage.create.currency')}</Label>
                <div className="flex gap-2" data-testid="storage-currency-selector">
                  {['CAD', 'USD'].map((cur) => (
                    <button
                      key={cur}
                      type="button"
                      onClick={() => set('currency', cur)}
                      className={`flex-1 py-2 px-3 rounded-lg border-2 text-sm font-semibold ${
                        form.currency === cur
                          ? 'border-blue-600 bg-blue-100/60 dark:bg-blue-900/30'
                          : 'border-slate-200 hover:border-blue-400'
                      }`}
                      data-testid={`storage-currency-${cur.toLowerCase()}`}
                    >
                      {cur === 'CAD' ? '🇨🇦 CAD' : '🇺🇸 USD'}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-500">
                  {t('storage.create.allTransactionsAreProcessedInCadByDefaul')}
                </p>
              </div>

              {/* iter482 P4 — Canonical Seller-Controlled Accepted Payment Methods (multi-select).
                  Replaces the legacy single-choice buttons. */}
              <div data-testid="payment-method-selector">
                <AcceptedPaymentMethodsSelector
                  value={form.accepted_payment_methods}
                  onChange={(list) => {
                    set('accepted_payment_methods', list);
                    // Keep the legacy single-choice field in sync with the first
                    // selected method so downstream fee-preview logic still works.
                    if (list && list.length > 0) set('payment_method', list[0]);
                  }}
                  isFrench={isFr}
                />
              </div>

              {/* Fee preview */}
              <div className="rounded-lg bg-white dark:bg-slate-900 p-3 text-xs border">
                {(form.accepted_payment_methods || []).includes('stripe') ? (
                  <p>
                    👤 <strong>
                      {t('storage.create.buyerPays')}
                    </strong>{' '}
                    {t('storage.create.hammerPrice5FeeStripeTaxesYouReceiveFull')}
                  </p>
                ) : (
                  <p>
                    👤 <strong>
                      {t('storage.create.buyerPaysYou')}
                    </strong>{' '}
                    {t('storage.create.hammerPriceDirectlyBidvexInvoicesYou5Str')}
                  </p>
                )}
              </div>

              {/* Deposit toggle */}
              <div className="flex items-start gap-2 pt-2">
                <Checkbox
                  checked={form.deposit_required}
                  onCheckedChange={v => set('deposit_required', v === true)}
                  className="mt-0.5"
                  data-testid="deposit-required-toggle"
                />
                <div className="flex-1">
                  <Label className="cursor-pointer text-sm">
                    {t('storage.create.requireADepositToParticipate')}
                  </Label>
                  <p className="text-[11px] text-muted-foreground">
                    {t('storage.create.biddersMustAuthorizeThisAmountBeforeThei')}
                  </p>
                  {form.deposit_required && (
                    <div className="mt-2 space-y-2" data-testid="storage-deposit-amount-block">
                      <div className="flex gap-2">
                        <button type="button" onClick={() => set('deposit_type', 'fixed')} className={`flex-1 px-2 py-1.5 rounded text-xs font-medium ${form.deposit_type === 'fixed' ? 'bg-blue-600 text-white' : 'bg-white border border-slate-300 text-slate-700'}`} data-testid="storage-deposit-type-fixed">
                          {t('storage.create.fixedAmount')}
                        </button>
                        <button type="button" onClick={() => set('deposit_type', 'percentage')} className={`flex-1 px-2 py-1.5 rounded text-xs font-medium ${form.deposit_type === 'percentage' ? 'bg-blue-600 text-white' : 'bg-white border border-slate-300 text-slate-700'}`} data-testid="storage-deposit-type-percentage">
                          {t('storage.create.ofStartingBid')}
                        </button>
                      </div>
                      <Label className="text-xs">
                        {form.deposit_type === 'fixed'
                          ? `${t('storage.create.depositAmount')} (${form.currency})`
                          : `${t('storage.create.depositPercentage')} (%)`}
                      </Label>
                      <Input
                        type="number"
                        min={form.deposit_type === 'percentage' ? '1' : '1'}
                        step={form.deposit_type === 'percentage' ? '1' : '0.01'}
                        value={form.deposit_amount}
                        onChange={e => set('deposit_amount', e.target.value)}
                        placeholder={form.deposit_type === 'fixed' ? (t('storage.create.eG100')) : (t('storage.create.eG10'))}
                        data-testid="deposit-amount-input"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* iter445 — Storage buyer's premium is FIXED PLATFORM POLICY.
                The facility no longer chooses or overrides this rate; the
                winning bidder always pays a flat 5 % on top of the hammer.
                Kept as a read-only informational badge so operators
                understand the fee model. */}
            <div className="rounded-lg border-2 border-blue-200 dark:border-blue-900 bg-blue-50/40 dark:bg-blue-950/20 p-4 space-y-2" data-testid="bp-section">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <Label className="text-sm font-semibold">
                  {isFr ? "Prime acheteur (fixe)" : "Buyer's Premium (fixed)"}
                </Label>
                <span
                  className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200 text-xs font-bold px-2 py-1"
                  data-testid="bp-fixed-badge"
                >
                  5%
                </span>
              </div>
              <p className="text-[11px] text-blue-800 dark:text-blue-300 leading-relaxed">
                ℹ️ {isFr
                  ? "BidVex facture 5 % à l'acheteur gagnant en plus du prix marteau. Votre facilité reçoit le prix marteau complet et n'est jamais facturée."
                  : "BidVex charges the winning buyer a flat 5% on top of the hammer price. Your facility receives the full hammer price and is never charged."}
              </p>
            </div>

            {/* iter216 P1 — Mandatory legal-notice confirmation */}
            <div className="rounded-lg border-2 border-amber-300 dark:border-amber-900 bg-amber-50/60 dark:bg-amber-950/30 p-4">
              <label className="flex items-start gap-2 cursor-pointer">
                <Checkbox
                  checked={form.accepted_legal_notice}
                  onCheckedChange={v => set('accepted_legal_notice', v === true)}
                  className="mt-0.5"
                  data-testid="legal-notice-checkbox"
                />
                <span className="text-xs leading-relaxed text-amber-900 dark:text-amber-200">
                  {t('storageCreate.legalNoticeConfirm', 'I confirm this unit has gone through the required legal-notification process and its contents may be auctioned under the relevant provincial law.')}
                </span>
              </label>
            </div>

            <Button type="submit" disabled={submitting} className="w-full bg-blue-600 hover:bg-blue-700 text-white" data-testid="create-auction-submit">
              {submitting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Upload className="h-4 w-4 mr-1" />}
              {t('storage.create.publishAuction')}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default StorageAuctionCreate;
