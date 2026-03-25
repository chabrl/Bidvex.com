import API_BASE from '../config';
/**
 * MaintenancePage - Coming Soon / Maintenance Mode Landing Page
 * Professional design for BidVex auction platform
 * Features: Email subscription, responsive design, animated elements, bilingual (EN/FR)
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { 
  Mail, Bell, ArrowRight, Gavel, TrendingUp, Shield, Users,
  Clock, CheckCircle, Sparkles, Twitter, Facebook, Instagram, Linkedin,
  Globe, Lock
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const API = `${API_BASE}/api`;

const BIDVEX_LOGO = 'https://customer-assets.emergentagent.com/job_aa51ced5-053b-417a-a5ea-c63c2febfff9/artifacts/xkt9mtpw_logo%20app.png';

const MaintenancePage = ({ mode = 'coming_soon', message, expectedBack, socialLinks }) => {
  const { t, i18n } = useTranslation();
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [countdown, setCountdown] = useState(null);

  const currentLang = i18n.language?.startsWith('fr') ? 'fr' : 'en';

  const toggleLanguage = () => {
    const newLang = currentLang === 'en' ? 'fr' : 'en';
    i18n.changeLanguage(newLang);
    try { localStorage.setItem('bidvex_language', newLang); } catch {}
  };

  const socialMediaIcons = [
    { icon: Twitter, href: socialLinks?.twitter || '#', label: 'Twitter' },
    { icon: Facebook, href: socialLinks?.facebook || '#', label: 'Facebook' },
    { icon: Instagram, href: socialLinks?.instagram || '#', label: 'Instagram' },
    { icon: Linkedin, href: socialLinks?.linkedin || '#', label: 'LinkedIn' }
  ];

  useEffect(() => {
    if (!expectedBack) return;
    const targetDate = new Date(expectedBack);
    const update = () => {
      const diff = targetDate - new Date();
      if (diff <= 0) { setCountdown(null); return; }
      setCountdown({
        days: Math.floor(diff / 86400000),
        hours: Math.floor((diff % 86400000) / 3600000),
        minutes: Math.floor((diff % 3600000) / 60000),
        seconds: Math.floor((diff % 60000) / 1000)
      });
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [expectedBack]);

  const handleSubscribe = async (e) => {
    e.preventDefault();
    if (!email || !email.includes('@')) {
      toast.error(t('maintenance.invalidEmail'));
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/subscribe`, { email });
      if (res.data.success) {
        setSubscribed(true);
        toast.success(res.data.message);
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : t('maintenance.subscriptionFailed'));
    } finally { setSubmitting(false); }
  };

  const isMaint = mode === 'maintenance';

  const features = [
    { icon: Gavel, title: t('maintenance.featureLiveAuctions'), desc: t('maintenance.featureLiveAuctionsDesc') },
    { icon: Shield, title: t('maintenance.featureSecurePlatform'), desc: t('maintenance.featureSecurePlatformDesc') },
    { icon: TrendingUp, title: t('maintenance.featureGreatDeals'), desc: t('maintenance.featureGreatDealsDesc') }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white overflow-hidden" data-testid="maintenance-page">
      {/* Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-20 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-teal-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-purple-500/10 rounded-full blur-3xl" />
        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiMyMDI4MzgiIGZpbGwtb3BhY2l0eT0iMC40Ij48cGF0aCBkPSJNMzYgMzRoLTJ2LTRoMnY0em0wLTZoLTJ2LTRoMnY0em0wLTZoLTJ2LTRoMnY0em0wLTZoLTJWMTJoMnY0em0wLTZoLTJWNmgydjR6bTAgMzBoLTJ2LTRoMnY0em0wIDZoLTJ2LTRoMnY0em0tNi0zNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6Ii8+PC9nPjwvZz48L3N2Zz4=')] opacity-30" />
      </div>

      <div className="relative z-10 min-h-screen flex flex-col">
        {/* Header */}
        <header className="py-6 sm:py-8 px-4 sm:px-6">
          <div className="max-w-5xl mx-auto flex items-center justify-between">
            {/* Logo — clean spacing, no overlap */}
            <div className="flex items-center gap-3" data-testid="maintenance-logo">
              <img src={BIDVEX_LOGO} alt="BidVex" className="h-10 w-10 sm:h-12 sm:w-12 object-contain rounded-xl flex-shrink-0" />
              <span className="text-xl sm:text-2xl font-bold bg-gradient-to-r from-white to-blue-200 bg-clip-text text-transparent">
                BidVex
              </span>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              {/* Admin Access */}
              <a href="/admin" className="p-2 bg-white/5 border border-white/10 rounded-full hover:bg-white/10 transition-colors opacity-40 hover:opacity-100" title="Admin Access">
                <Lock className="h-4 w-4" />
              </a>
              {/* Language Toggle */}
              <button onClick={toggleLanguage} className="flex items-center gap-1.5 px-3 py-2 bg-white/5 border border-white/10 rounded-full hover:bg-white/10 transition-colors text-sm" aria-label="Toggle language" data-testid="lang-toggle">
                <Globe className="h-4 w-4" />
                <span className="font-medium">{currentLang.toUpperCase()}</span>
              </button>
              {/* Status Badge */}
              <div className={`hidden sm:flex px-3 py-1.5 rounded-full text-xs font-medium items-center gap-2 ${
                isMaint ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
              }`} data-testid="status-badge">
                <div className={`w-2 h-2 rounded-full animate-pulse ${isMaint ? 'bg-amber-400' : 'bg-blue-400'}`} />
                {isMaint ? t('maintenance.statusBadgeMaintenance') : t('maintenance.statusBadgeComingSoon')}
              </div>
            </div>
          </div>
        </header>

        {/* Hero */}
        <main className="flex-1 flex items-center justify-center px-4 sm:px-6 py-8 sm:py-12">
          <div className="max-w-3xl mx-auto text-center">
            {/* Shimmer Pill */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/15 mb-6 relative overflow-hidden" data-testid="tagline-pill">
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer" style={{ backgroundSize: '200% 100%' }} />
              <Sparkles className="h-4 w-4 text-yellow-400 relative z-10" />
              <span className="text-sm text-blue-200 relative z-10">
                {isMaint ? t('maintenance.maintenanceTagline') : t('maintenance.tagline')}
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 leading-tight" data-testid="headline">
              {isMaint ? t('maintenance.headlineMaintenance') : t('maintenance.headlineComingSoon')}
              <span className="block bg-gradient-to-r from-blue-400 via-teal-400 to-blue-400 bg-clip-text text-transparent">
                {isMaint ? t('maintenance.maintenanceHighlight') : t('maintenance.headlineHighlight')}
              </span>
            </h1>

            <p className="text-base sm:text-lg text-slate-300 max-w-xl mx-auto leading-relaxed mb-8" data-testid="description">
              {message || (isMaint ? t('maintenance.defaultDescriptionMaintenance') : t('maintenance.defaultDescriptionComingSoon'))}
            </p>

            {/* Countdown */}
            {countdown && (
              <div className="mb-10">
                <p className="text-sm text-slate-400 mb-4">
                  {isMaint ? t('maintenance.expectedBackIn') : t('maintenance.launchingIn')}
                </p>
                <div className="flex justify-center gap-3 sm:gap-4">
                  {[
                    { value: countdown.days, label: t('maintenance.days') },
                    { value: countdown.hours, label: t('maintenance.hours') },
                    { value: countdown.minutes, label: t('maintenance.minutes') },
                    { value: countdown.seconds, label: t('maintenance.seconds') }
                  ].map((item) => (
                    <div key={item.label} className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl px-3 sm:px-5 py-3">
                      <div className="text-2xl sm:text-3xl font-bold text-white tabular-nums">{String(item.value).padStart(2, '0')}</div>
                      <div className="text-[10px] sm:text-xs text-slate-400 uppercase tracking-wider mt-0.5">{item.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Email Subscription */}
            <div className="max-w-md mx-auto mb-12">
              {!subscribed ? (
                <form onSubmit={handleSubscribe} className="space-y-4">
                  <p className="text-slate-300 text-sm flex items-center justify-center gap-2 mb-3">
                    <Bell className="h-4 w-4" />
                    {t('maintenance.getNotified')}
                  </p>
                  <div className="flex flex-col sm:flex-row gap-3">
                    <div className="relative flex-1">
                      <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                      <Input
                        type="email"
                        placeholder={t('maintenance.emailPlaceholder')}
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="pl-12 h-12 bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus:border-blue-400 focus:ring-blue-400/20 rounded-xl"
                        disabled={submitting}
                        data-testid="subscribe-email-input"
                      />
                    </div>
                    <Button
                      type="submit"
                      disabled={submitting}
                      className="h-12 px-6 bg-gradient-to-r from-blue-500 to-teal-500 hover:from-blue-600 hover:to-teal-600 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 transition-all"
                      data-testid="subscribe-button"
                    >
                      {submitting ? (
                        <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
                      ) : (
                        <>{t('maintenance.notifyMe')} <ArrowRight className="ml-2 h-4 w-4" /></>
                      )}
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="p-6 bg-green-500/10 border border-green-500/30 rounded-2xl" data-testid="subscription-success">
                  <CheckCircle className="h-10 w-10 text-green-400 mx-auto mb-3" />
                  <h3 className="text-lg font-semibold text-green-300 mb-1">{t('maintenance.successTitle')}</h3>
                  <p className="text-sm text-slate-300">{t('maintenance.successMessage')}</p>
                </div>
              )}
            </div>

            {/* Feature Cards */}
            {!isMaint && (
              <div className="grid sm:grid-cols-3 gap-4 max-w-2xl mx-auto">
                {features.map((f, i) => (
                  <div
                    key={i}
                    className="flex flex-col items-center text-center p-5 bg-white/[0.04] backdrop-blur-lg border border-white/10 rounded-2xl hover:bg-white/[0.08] transition-all duration-300"
                    data-testid={`feature-card-${i}`}
                  >
                    <div className="w-11 h-11 rounded-xl bg-blue-500/15 flex items-center justify-center mb-3">
                      <f.icon className="h-5 w-5 text-blue-400" />
                    </div>
                    <h3 className="font-semibold text-sm text-white mb-1.5">{f.title}</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">{f.desc}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </main>

        {/* Footer */}
        <footer className="py-6 px-4 sm:px-6 border-t border-white/10">
          <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-slate-500">
              &copy; {new Date().getFullYear()} BidVex. {currentLang === 'fr' ? 'Tous droits réservés.' : 'All rights reserved.'}
            </p>
            <div className="flex items-center gap-3" data-testid="social-icons">
              {socialMediaIcons.map((s) => {
                const isActive = s.href && s.href !== '#';
                const Wrapper = isActive ? 'a' : 'div';
                const props = isActive ? { href: s.href, target: '_blank', rel: 'noopener noreferrer' } : {};
                return (
                  <Wrapper
                    key={s.label}
                    {...props}
                    aria-label={s.label}
                    className={`w-9 h-9 flex items-center justify-center rounded-full border transition-colors ${
                      isActive
                        ? 'bg-white/5 border-white/15 text-slate-400 hover:text-white hover:bg-white/10 cursor-pointer'
                        : 'bg-white/[0.02] border-white/5 text-slate-600'
                    }`}
                    data-testid={`social-${s.label.toLowerCase()}`}
                  >
                    <s.icon className="h-4 w-4" />
                  </Wrapper>
                );
              })}
            </div>
          </div>
        </footer>
      </div>

      {/* Shimmer animation CSS */}
      <style>{`
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .animate-shimmer {
          animation: shimmer 3s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
};

export default MaintenancePage;
