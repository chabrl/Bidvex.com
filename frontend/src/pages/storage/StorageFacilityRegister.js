import API_BASE from '../../config';
import React, { useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { ShieldCheck, Loader2, ArrowLeft, ArrowRight, ExternalLink } from 'lucide-react';
import StorageFooterBanner from './StorageFooterBanner';

const API = API_BASE;
const PROVINCES = ['AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'ON', 'PE', 'QC', 'SK', 'NT', 'NU', 'YT'];

const StorageFacilityRegister = () => {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const isFr = (i18n.language || '').startsWith('fr');

  const [step, setStep] = useState(1); // 1: Info, 2: Credentials, 3: Stripe
  const [form, setForm] = useState({
    company_name: '', company_name_fr: '', contact_name: '',
    email: '', phone: '', address: '', city: '', province: 'QC',
    postal_code: '', units_available: 0, referral_source: '',
    business_registration_number: '', opc_permit_number: '',
    accepted_terms: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const validateStep1 = () => {
    if (!form.company_name || form.company_name.length < 2) {
      toast.error(t('storage.facilityRegister.companyNameRequired'));
      return false;
    }
    if (!form.contact_name) {
      toast.error(t('storage.facilityRegister.contactNameRequired'));
      return false;
    }
    if (!form.email || !form.phone) {
      toast.error(t('storage.facilityRegister.emailAndPhoneRequired'));
      return false;
    }
    if (!form.address || !form.city || !form.postal_code) {
      toast.error(t('storage.facilityRegister.fullAddressRequired'));
      return false;
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!token) { toast.error(t('storage.facilityRegister.signInFirst')); return; }
    if (!form.accepted_terms) {
      toast.error(t('storage.facilityRegister.acceptTheTerms'));
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/storage-facilities/register`, form, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setResult(res.data);
      setStep(4);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object' && detail) ? (isFr ? detail.message_fr : detail.message_en) : detail;
      toast.error(msg || (t('storage.facilityRegister.registrationFailed')));
    } finally {
      setSubmitting(false);
    }
  };

  // ── SUCCESS / SUBMITTED VIEW ──
  if (step === 4 && result) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
        <div className="flex items-center justify-center px-4 py-16">
          <Card className="max-w-md p-8 text-center" data-testid="register-success">
            <ShieldCheck className="h-16 w-16 mx-auto text-emerald-500 mb-4" />
            <h2 className="text-2xl font-bold mb-2">
              {t('storage.facilityRegister.applicationReceived')}
            </h2>
            <p className="text-sm text-muted-foreground mb-4">
              {isFr ? result.message_fr : result.message_en}
            </p>
            {result.stripe_onboarding_url && (
              <Button
                className="w-full bg-[#635BFF] hover:bg-[#5048E5] text-white mb-3"
                onClick={() => { window.location.href = result.stripe_onboarding_url; }}
                data-testid="stripe-onboarding-link"
              >
                <ExternalLink className="h-4 w-4 mr-1" />
                {t('storage.facilityRegister.continueWithStripe')}
              </Button>
            )}
            <Button variant="outline" onClick={() => navigate('/storage-auctions')} className="w-full">
              {t('storage.facilityRegister.backToAuctions')}
            </Button>
          </Card>
        </div>
        <StorageFooterBanner />
      </div>
    );
  }

  const StepIndicator = () => (
    <div className="flex items-center gap-2 mb-6" data-testid="step-indicator">
      {[1, 2, 3].map(n => (
        <React.Fragment key={n}>
          <div
            className={`w-8 h-8 flex items-center justify-center rounded-full text-xs font-bold transition-all ${
              step === n
                ? 'bg-blue-600 text-white scale-110'
                : step > n
                ? 'bg-emerald-500 text-white'
                : 'bg-slate-200 dark:bg-slate-700 text-slate-500'
            }`}
            data-testid={`step-${n}-indicator`}
          >
            {step > n ? '✓' : n}
          </div>
          {n < 3 && (
            <div className={`flex-1 h-0.5 ${step > n ? 'bg-emerald-500' : 'bg-slate-200 dark:bg-slate-700'}`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="storage-register-page">
      <div className="max-w-2xl mx-auto px-4">
        <h1 className="text-3xl font-bold mb-2">
          {t('storage.facilityRegister.listYourFacility')}
        </h1>
        <p className="text-sm text-muted-foreground mb-2">
          {t('storage.facilityRegister.registrationForCanadianStorageFacilities')}
        </p>
        <p className="text-xs text-emerald-700 dark:text-emerald-400 mb-6">
          ✅ {t('storage.facilityRegister.k5CommissionOnlyNoMonthlySubscription')}
        </p>

        <Card className="p-6">
          <StepIndicator />

          {/* ── STEP 1: Facility Info ── */}
          {step === 1 && (
            <div className="space-y-4" data-testid="step-1-content">
              <h3 className="font-bold text-lg">
                {t('storage.facilityRegister.step1FacilityInfo')}
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>{t('storage.facilityRegister.companyNameEn')} *</Label>
                  <Input value={form.company_name} onChange={e => set('company_name', e.target.value)} data-testid="reg-company-name" />
                </div>
                <div>
                  <Label>{t('storage.facilityRegister.companyNameFr')}</Label>
                  <Input value={form.company_name_fr} onChange={e => set('company_name_fr', e.target.value)} />
                </div>
              </div>

              <div>
                <Label>{t('storage.facilityRegister.contactName')} *</Label>
                <Input value={form.contact_name} onChange={e => set('contact_name', e.target.value)} data-testid="reg-contact-name" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>{t('storage.facilityRegister.email')} *</Label>
                  <Input type="email" value={form.email} onChange={e => set('email', e.target.value)} />
                </div>
                <div>
                  <Label>{t('storage.facilityRegister.phone')} *</Label>
                  <Input value={form.phone} onChange={e => set('phone', e.target.value)} />
                </div>
              </div>

              <div>
                <Label>{t('storage.facilityRegister.address2')} *</Label>
                <Input value={form.address} onChange={e => set('address', e.target.value)} />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div>
                  <Label>{t('storage.facilityRegister.city')} *</Label>
                  <Input value={form.city} onChange={e => set('city', e.target.value)} />
                </div>
                <div>
                  <Label>{t('storage.facilityRegister.province')} *</Label>
                  <Select value={form.province} onValueChange={v => set('province', v)}>
                    <SelectTrigger data-testid="reg-province"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PROVINCES.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>{t('storage.facilityRegister.postalCode')} *</Label>
                  <Input value={form.postal_code} onChange={e => set('postal_code', e.target.value)} />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label>{t('storage.facilityRegister.unitsAvailable')}</Label>
                  <Input
                    type="number" min="0"
                    value={form.units_available}
                    onChange={e => set('units_available', parseInt(e.target.value || '0'))}
                  />
                </div>
                <div>
                  <Label>{t('storage.facilityRegister.howDidYouHearAboutUs')}</Label>
                  <Input value={form.referral_source} onChange={e => set('referral_source', e.target.value)} />
                </div>
              </div>

              <div className="flex justify-end pt-3">
                <Button
                  type="button"
                  onClick={() => { if (validateStep1()) setStep(2); }}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                  data-testid="step-1-next-btn"
                >
                  {t('storage.facilityRegister.next')} <ArrowRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}

          {/* ── STEP 2: Business Credentials ── */}
          {step === 2 && (
            <div className="space-y-4" data-testid="step-2-content">
              <h3 className="font-bold text-lg">
                {t('storage.facilityRegister.step2BusinessCredentials')}
              </h3>
              <p className="text-xs text-muted-foreground">
                {t('storage.facilityRegister.optionalButRecommendedHelpsSpeedUpVerifi')}
              </p>

              <div>
                <Label>
                  {t('storage.facilityRegister.businessRegistrationNumber')}
                  {form.province === 'QC' && (
                    <span className="ml-1 text-xs text-muted-foreground">({t('storage.facilityRegister.neqForQc')})</span>
                  )}
                </Label>
                <Input
                  value={form.business_registration_number}
                  onChange={e => set('business_registration_number', e.target.value)}
                  data-testid="reg-business-number"
                />
              </div>

              {form.province === 'QC' && (
                <div>
                  <Label>{t('storage.facilityRegister.opcPermitNumberQuebec')}</Label>
                  <Input
                    value={form.opc_permit_number}
                    onChange={e => set('opc_permit_number', e.target.value)}
                    placeholder={t('storage.facilityRegister.optional')}
                    data-testid="reg-opc-permit"
                  />
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {t('storage.facilityRegister.ifYouOperateInQuebecAndHaveAnOpcPermitPr')}
                  </p>
                </div>
              )}

              <div className="rounded-lg bg-amber-50 dark:bg-amber-950/30 p-3 text-xs text-amber-800 dark:text-amber-300">
                ⚠️ {t('storage.facilityRegister.youWillBeSolelyResponsibleForComplianceW')}
              </div>

              <div className="flex justify-between pt-3">
                <Button type="button" variant="outline" onClick={() => setStep(1)} data-testid="step-2-back-btn">
                  <ArrowLeft className="h-4 w-4 mr-1" /> {t('storage.facilityRegister.back')}
                </Button>
                <Button
                  type="button"
                  onClick={() => setStep(3)}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                  data-testid="step-2-next-btn"
                >
                  {t('storage.facilityRegister.next')} <ArrowRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}

          {/* ── STEP 3: Stripe Setup + Confirm ── */}
          {step === 3 && (
            <div className="space-y-4" data-testid="step-3-content">
              <h3 className="font-bold text-lg">
                {t('storage.facilityRegister.step3StripeSetup')}
              </h3>

              <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-4 text-sm border border-blue-200 dark:border-blue-900/40">
                <p className="font-semibold mb-2">
                  💳 {t('storage.facilityRegister.whyStripeConnect')}
                </p>
                <ul className="space-y-1.5 text-xs ml-4 list-disc">
                  <li>
                    {t('storage.facilityRegister.forStripePaymentAuctionsBidvexTransfersT')}
                  </li>
                  <li>
                    {t('storage.facilityRegister.forCashOrETransferAuctionsBidvexChargesY')}
                  </li>
                  <li>
                    {t('storage.facilityRegister.stripeVerifiesYourIdentityKycAStandard51')}
                  </li>
                </ul>
              </div>

              <div className="flex items-start gap-2 p-3 bg-slate-100 dark:bg-slate-800/50 rounded-lg">
                <Checkbox
                  checked={form.accepted_terms}
                  onCheckedChange={v => set('accepted_terms', v === true)}
                  className="mt-0.5"
                  data-testid="reg-accept-terms"
                />
                <label className="text-xs leading-snug">
                  {isFr ? (
                    <>J'accepte les <a href="/storage-auctions/terms" target="_blank" rel="noreferrer" className="underline text-blue-600">conditions générales</a> des enchères d'entreposage BidVex et reconnais que ma facilité est seule responsable du respect des lois provinciales sur les droits de rétention.</>
                  ) : (
                    <>I accept the BidVex Storage Auction <a href="/storage-auctions/terms" target="_blank" rel="noreferrer" className="underline text-blue-600">Terms & Conditions</a> and acknowledge that my facility is solely responsible for compliance with provincial lien laws.</>
                  )}
                </label>
              </div>

              <div className="flex justify-between pt-3">
                <Button type="button" variant="outline" onClick={() => setStep(2)} data-testid="step-3-back-btn">
                  <ArrowLeft className="h-4 w-4 mr-1" /> {t('storage.facilityRegister.back')}
                </Button>
                <Button
                  type="button"
                  onClick={handleSubmit}
                  disabled={submitting || !form.accepted_terms}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  data-testid="reg-submit-btn"
                >
                  {submitting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                  {t('storage.facilityRegister.submitApplication')}
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
      <StorageFooterBanner />
    </div>
  );
};

export default StorageFacilityRegister;
