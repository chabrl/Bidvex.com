import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import axios from 'axios';
import {
  Building2, Shield, TrendingUp, FileText, Upload,
  CheckCircle, Clock, XCircle, ArrowRight,
  DollarSign, Users, Award, ChevronRight, Loader2, Zap
} from 'lucide-react';

const API = `${API_BASE}/api`;

const BecomePartnerPage = () => {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [partnerStatus, setPartnerStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [companyName, setCompanyName] = useState('');
  const [neqNumber, setNeqNumber] = useState('');
  const [neqFile, setNeqFile] = useState(null);
  const [certFiles, setCertFiles] = useState([]);

  useEffect(() => {
    if (user && token) fetchStatus();
    else setLoading(false);
  }, [user, token]);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/partner/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPartnerStatus(res.data);
    } catch { /* not logged in */ }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!neqFile) { toast.error(t('partnerPage.neqRequired')); return; }
    if (certFiles.length === 0) { toast.error(t('partnerPage.certRequired')); return; }
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('company_name', companyName);
      formData.append('neq_number', neqNumber);
      formData.append('neq_document', neqFile);
      certFiles.forEach(f => formData.append('certification_documents', f));
      const res = await axios.post(`${API}/partner/apply`, formData, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
      });
      toast.success(res.data.message);
      fetchStatus();
    } catch (err) {
      const detail = err.response?.data?.detail;
      let message = t('partnerPage.submitFailed');
      if (typeof detail === 'string') message = detail;
      else if (Array.isArray(detail)) message = detail.map(e => e?.msg || '').filter(Boolean).join(', ') || message;
      toast.error(message);
    } finally { setSubmitting(false); }
  };

  const benefits = [
    {
      icon: DollarSign,
      titleKey: 'partnerPage.benefit1Title',
      descKey: 'partnerPage.benefit1Desc',
      accent: 'border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-gradient-to-br dark:from-emerald-500/20 dark:to-emerald-600/5',
      iconBg: 'bg-emerald-100 dark:bg-white/[0.06]',
      iconColor: 'text-emerald-600 dark:text-emerald-400',
    },
    {
      icon: TrendingUp,
      titleKey: 'partnerPage.benefit2Title',
      descKey: 'partnerPage.benefit2Desc',
      accent: 'border-blue-200 dark:border-blue-500/20 bg-blue-50 dark:bg-gradient-to-br dark:from-blue-500/20 dark:to-blue-600/5',
      iconBg: 'bg-blue-100 dark:bg-white/[0.06]',
      iconColor: 'text-blue-600 dark:text-blue-400',
    },
    {
      icon: Shield,
      titleKey: 'partnerPage.benefit3Title',
      descKey: 'partnerPage.benefit3Desc',
      accent: 'border-violet-200 dark:border-violet-500/20 bg-violet-50 dark:bg-gradient-to-br dark:from-violet-500/20 dark:to-violet-600/5',
      iconBg: 'bg-violet-100 dark:bg-white/[0.06]',
      iconColor: 'text-violet-600 dark:text-violet-400',
    },
    {
      icon: Zap,
      titleKey: 'partnerPage.benefit4Title',
      descKey: 'partnerPage.benefit4Desc',
      accent: 'border-amber-200 dark:border-amber-500/20 bg-amber-50 dark:bg-gradient-to-br dark:from-amber-500/20 dark:to-amber-600/5',
      iconBg: 'bg-amber-100 dark:bg-white/[0.06]',
      iconColor: 'text-amber-600 dark:text-amber-400',
    },
  ];

  const StatusBanner = () => {
    if (!partnerStatus || partnerStatus.verification_status === 'unverified') return null;
    const config = {
      pending: { icon: Clock, bg: 'bg-amber-50 dark:bg-amber-950/50 border-amber-200 dark:border-amber-700/40', text: 'text-amber-700 dark:text-amber-300', sub: 'text-amber-600 dark:text-slate-400', label: t('partnerPage.statusPendingLabel'), desc: t('partnerPage.statusPendingDesc') },
      verified: { icon: Award, bg: 'bg-emerald-50 dark:bg-emerald-950/50 border-emerald-200 dark:border-emerald-700/40', text: 'text-emerald-700 dark:text-emerald-300', sub: 'text-emerald-600 dark:text-slate-400', label: t('partnerPage.statusVerifiedLabel'), desc: t('partnerPage.statusVerifiedDesc') },
      rejected: { icon: XCircle, bg: 'bg-red-50 dark:bg-red-950/50 border-red-200 dark:border-red-700/40', text: 'text-red-700 dark:text-red-300', sub: 'text-red-600 dark:text-slate-400', label: t('partnerPage.statusRejectedLabel'), desc: partnerStatus.rejection_reason || 'Please contact partners@bidvex.ca for details.' },
    }[partnerStatus.verification_status];
    if (!config) return null;
    const Icon = config.icon;
    return (
      <div className={`flex items-start gap-3 p-4 rounded-xl border ${config.bg}`} data-testid="partner-status-banner">
        <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${config.text}`} />
        <div>
          <p className={`font-semibold text-sm ${config.text}`}>{config.label}</p>
          <p className={`text-xs mt-0.5 ${config.sub}`}>{config.desc}</p>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950 text-slate-900 dark:text-white transition-colors" data-testid="become-partner-page">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(59,130,246,0.08),transparent_60%)] dark:bg-[radial-gradient(ellipse_at_top_left,rgba(59,130,246,0.12),transparent_60%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(16,185,129,0.06),transparent_60%)] dark:bg-[radial-gradient(ellipse_at_bottom_right,rgba(16,185,129,0.08),transparent_60%)]" />
        </div>
        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 pt-20 sm:pt-28 pb-12 sm:pb-16">
          <div className="space-y-5">
            <Badge className="bg-slate-100 dark:bg-white/[0.08] text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-white/10 px-3 py-1 text-xs font-medium tracking-wide backdrop-blur-sm" data-testid="partner-hero-badge">
              <Building2 className="w-3.5 h-3.5 mr-1.5 inline" /> {t('partnerPage.heroBadge')}
            </Badge>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight leading-[1.1]" data-testid="partner-hero-title">
              {t('partnerPage.heroTitle1')}
              <br />
              <span className="bg-gradient-to-r from-blue-600 via-emerald-500 to-blue-600 dark:from-blue-400 dark:via-emerald-400 dark:to-blue-400 bg-clip-text text-transparent">
                {t('partnerPage.heroTitle2')}
              </span>
            </h1>
            <p
              className="text-base sm:text-lg text-slate-600 dark:text-slate-400 max-w-xl leading-relaxed [&_strong]:text-slate-900 dark:[&_strong]:text-white [&_strong]:font-medium"
              dangerouslySetInnerHTML={{ __html: t('partnerPage.heroDesc') }}
            />
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              {!user ? (
                <Button onClick={() => navigate('/auth')} size="lg" className="bg-blue-600 hover:bg-blue-700 text-white h-11 px-6 text-sm font-medium" data-testid="partner-cta-signin">
                  {t('partnerPage.ctaSignIn')} <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button onClick={() => document.getElementById('apply-section')?.scrollIntoView({ behavior: 'smooth' })} size="lg" className="bg-blue-600 hover:bg-blue-700 text-white h-11 px-6 text-sm font-medium" data-testid="partner-cta-apply">
                  {t('partnerPage.ctaApply')} <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              )}
              <Button variant="outline" size="lg" className="border-slate-300 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 h-11 px-6 text-sm" onClick={() => window.location.href = 'mailto:partners@bidvex.ca'} data-testid="partner-cta-contact">
                {t('partnerPage.ctaContact')}
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Benefits — 2x2 on desktop, 1-col on mobile, equal-height cards */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
          {benefits.map((b, i) => (
            <div
              key={i}
              className={`group relative rounded-xl border p-5 transition-all duration-300 hover:scale-[1.01] hover:shadow-lg flex flex-col ${b.accent}`}
              data-testid={`partner-benefit-${i}`}
            >
              <div className={`w-9 h-9 rounded-lg ${b.iconBg} flex items-center justify-center mb-3`}>
                <b.icon className={`w-4.5 h-4.5 ${b.iconColor}`} />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white text-sm mb-1">{t(b.titleKey)}</h3>
              <p className="text-slate-600 dark:text-slate-400 text-xs leading-relaxed flex-1">{t(b.descKey)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ROI Highlight — side-by-side on desktop, stacked on mobile */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20">
        <div className="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/[0.03] p-6 sm:p-8 backdrop-blur-sm">
          <div className="flex flex-col sm:flex-row gap-6 sm:gap-10 items-start">
            <div className="flex-1 space-y-2">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{t('partnerPage.mathTitle')}</h2>
              <p
                className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed [&_strong]:text-slate-900 dark:[&_strong]:text-white [&_strong]:font-medium"
                dangerouslySetInnerHTML={{ __html: t('partnerPage.mathDesc') }}
              />
              <p className="text-xs text-slate-500 dark:text-slate-500 pt-1">
                {t('partnerPage.mathSub')}
              </p>
            </div>
            <div className="flex-shrink-0 text-center px-4 py-3 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 min-w-[140px] self-center sm:self-start">
              <div className="text-2xl sm:text-3xl font-bold text-emerald-600 dark:text-emerald-400" data-testid="partner-savings-highlight">3%</div>
              <div className="text-xs text-emerald-600/80 dark:text-emerald-400/70 font-medium">{t('partnerPage.mathPlatformFee')}</div>
              <div className="text-[10px] text-slate-500 mt-1">{t('partnerPage.mathIndustryAvg')}</div>
            </div>
          </div>
        </div>
      </section>

      {/* Application Form — max-w-[640px] centered on desktop, full-width on mobile */}
      <section id="apply-section" className="max-w-[640px] mx-auto px-4 sm:px-6 pb-20 sm:pb-28">
        <div className="rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-white/[0.02] overflow-hidden shadow-sm dark:shadow-none">
          <div className="px-4 sm:px-6 pt-6 pb-3 border-b border-slate-100 dark:border-white/5">
            <h2 className="font-semibold text-slate-900 dark:text-white text-base flex items-center gap-2">
              <FileText className="w-4 h-4 text-blue-500" /> {t('partnerPage.formTitle')}
            </h2>
            <p className="text-xs text-slate-500 mt-1">{t('partnerPage.formSubtitle')}</p>
          </div>
          <div className="p-4 sm:p-6 space-y-5">
            <StatusBanner />

            {!user ? (
              <div className="text-center py-10 space-y-4">
                <Users className="w-10 h-10 text-slate-400 dark:text-slate-600 mx-auto" />
                <p className="text-slate-600 dark:text-slate-400 text-sm">{t('partnerPage.signInPrompt')}</p>
                <Button onClick={() => navigate('/auth')} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="partner-login-cta">
                  {t('partnerPage.signInBtn')} <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            ) : partnerStatus?.verification_status === 'verified' ? (
              <div className="text-center py-10 space-y-3">
                <Award className="w-12 h-12 text-emerald-500 dark:text-emerald-400 mx-auto" />
                <p className="text-emerald-700 dark:text-emerald-400 font-semibold">{t('partnerPage.verifiedTitle')}</p>
                <p className="text-slate-500 text-sm">{t('partnerPage.verifiedDesc')}</p>
              </div>
            ) : partnerStatus?.verification_status === 'pending' ? null : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-slate-700 dark:text-slate-400 text-xs">{t('partnerPage.formCompanyLabel')}</Label>
                    <Input
                      value={companyName} onChange={e => setCompanyName(e.target.value)}
                      placeholder={t('partnerPage.formCompanyPlaceholder')} required
                      className="bg-slate-50 dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 h-9 text-sm"
                      data-testid="partner-company-name"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-slate-700 dark:text-slate-400 text-xs">{t('partnerPage.formNeqLabel')}</Label>
                    <Input
                      value={neqNumber} onChange={e => setNeqNumber(e.target.value)}
                      placeholder={t('partnerPage.formNeqPlaceholder')} required
                      className="bg-slate-50 dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-600 h-9 text-sm"
                      data-testid="partner-neq-number"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-700 dark:text-slate-400 text-xs">
                    {t('partnerPage.formNeqFileLabel')} <span className="text-slate-400 dark:text-slate-600">{t('partnerPage.formNeqFileHint')}</span>
                  </Label>
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={e => setNeqFile(e.target.files[0])} required className="hidden" id="neq-upload" data-testid="partner-neq-upload" />
                  <label htmlFor="neq-upload" className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-slate-300 dark:border-white/15 bg-slate-50 dark:bg-white/[0.03] text-slate-500 hover:border-blue-400 dark:hover:border-blue-500/40 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer transition-colors text-sm">
                    <Upload className="w-4 h-4 flex-shrink-0" />
                    {neqFile ? <span className="text-slate-900 dark:text-white truncate">{neqFile.name}</span> : t('partnerPage.formNeqFileBtn')}
                  </label>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-700 dark:text-slate-400 text-xs">
                    {t('partnerPage.formCertLabel')} <span className="text-slate-400 dark:text-slate-600">{t('partnerPage.formCertHint')}</span>
                  </Label>
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" multiple onChange={e => setCertFiles(Array.from(e.target.files))} required className="hidden" id="cert-upload" data-testid="partner-cert-upload" />
                  <label htmlFor="cert-upload" className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-slate-300 dark:border-white/15 bg-slate-50 dark:bg-white/[0.03] text-slate-500 hover:border-blue-400 dark:hover:border-blue-500/40 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer transition-colors text-sm">
                    <Upload className="w-4 h-4 flex-shrink-0" />
                    {certFiles.length > 0 ? <span className="text-slate-900 dark:text-white">{t('partnerPage.filesSelected', { count: certFiles.length })}</span> : t('partnerPage.formCertBtn')}
                  </label>
                </div>

                <div className="rounded-lg bg-slate-50 dark:bg-white/[0.03] border border-slate-100 dark:border-white/5 p-3 text-[11px] text-slate-500 leading-relaxed space-y-1">
                  <p>{t('partnerPage.formDisclaimer1')}</p>
                  <p>{t('partnerPage.formDisclaimer2')} <span className="text-slate-700 dark:text-slate-300">partners@bidvex.ca</span>.</p>
                </div>

                {/* Partner Fee Disclosure — full width, proper padding */}
                <div className="rounded-lg border-2 border-blue-200 dark:border-blue-500/30 bg-blue-50/50 dark:bg-blue-500/5 p-4 space-y-2" data-testid="partner-fee-disclosure">
                  <p className="text-xs font-semibold text-blue-700 dark:text-blue-300 uppercase tracking-wide">{t('partnerPage.feeSummaryTitle')}</p>
                  <ul className="text-xs text-slate-700 dark:text-slate-300 space-y-1.5 list-none pl-0">
                    <li className="flex items-start gap-2">
                      <span className="text-blue-500 font-bold mt-px">1.</span>
                      <span dangerouslySetInnerHTML={{ __html: t('partnerPage.feeLine1') }} />
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-500 font-bold mt-px">2.</span>
                      <span dangerouslySetInnerHTML={{ __html: t('partnerPage.feeLine2') }} />
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-500 font-bold mt-px">3.</span>
                      <span dangerouslySetInnerHTML={{ __html: t('partnerPage.feeLine3') }} />
                    </li>
                  </ul>
                  <p className="text-[10px] text-slate-500 dark:text-slate-500 pt-1">{t('partnerPage.feeFootnote')}</p>
                </div>

                {/* NEQ Verification Note — full width */}
                <div
                  className="rounded-lg bg-amber-50 dark:bg-amber-500/5 border border-amber-200 dark:border-amber-500/20 p-3 text-[11px] text-amber-700 dark:text-amber-300 leading-relaxed"
                  data-testid="partner-neq-verification-note"
                  dangerouslySetInnerHTML={{ __html: t('partnerPage.verificationNote') }}
                />

                <Button
                  type="submit"
                  disabled={submitting || !companyName || !neqNumber || !neqFile || certFiles.length === 0}
                  className="w-full sm:w-auto sm:mx-auto sm:flex bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-40 h-10 text-sm font-medium px-8"
                  data-testid="partner-submit-btn"
                >
                  {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ChevronRight className="w-4 h-4 mr-2" />}
                  {submitting ? t('partnerPage.formSubmitting') : t('partnerPage.formSubmitBtn')}
                </Button>
              </form>
            )}
          </div>
        </div>
      </section>
    </div>
  );
};

export default BecomePartnerPage;
