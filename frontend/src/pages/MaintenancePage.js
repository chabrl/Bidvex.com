/**
 * MaintenancePage - Coming Soon / Maintenance Mode Landing Page
 * Modern startup-style design for BidVex auction platform
 * Features: Email subscription, responsive design, animated elements, bilingual (EN/FR)
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { 
  Mail, Bell, ArrowRight, Gavel, TrendingUp, Shield, Users,
  Clock, CheckCircle, Sparkles, Twitter, Facebook, Instagram, Linkedin,
  Globe
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MaintenancePage = ({ mode = 'coming_soon', message, expectedBack }) => {
  const { t, i18n } = useTranslation();
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [countdown, setCountdown] = useState(null);

  const currentLang = i18n.language?.startsWith('fr') ? 'fr' : 'en';

  const toggleLanguage = () => {
    const newLang = currentLang === 'en' ? 'fr' : 'en';
    i18n.changeLanguage(newLang);
    try {
      localStorage.setItem('bidvex_language', newLang);
    } catch (e) {}
  };

  // Calculate countdown if expectedBack is provided
  useEffect(() => {
    if (expectedBack) {
      const targetDate = new Date(expectedBack);
      const updateCountdown = () => {
        const now = new Date();
        const diff = targetDate - now;
        
        if (diff <= 0) {
          setCountdown(null);
          return;
        }
        
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        
        setCountdown({ days, hours, minutes, seconds });
      };
      
      updateCountdown();
      const interval = setInterval(updateCountdown, 1000);
      return () => clearInterval(interval);
    }
  }, [expectedBack]);

  const handleSubscribe = async (e) => {
    e.preventDefault();
    if (!email || !email.includes('@')) {
      toast.error(t('maintenance.invalidEmail'));
      return;
    }

    setSubmitting(true);
    try {
      const response = await axios.post(`${API}/subscribe`, { email });
      if (response.data.success) {
        setSubscribed(true);
        toast.success(response.data.message);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || t('maintenance.subscriptionFailed');
      toast.error(errorMsg);
    } finally {
      setSubmitting(false);
    }
  };

  const isMaintenanceMode = mode === 'maintenance';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white overflow-hidden">
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {/* Gradient Orbs */}
        <div className="absolute top-1/4 -left-20 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-teal-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-purple-500/10 rounded-full blur-3xl" />
        
        {/* Floating Auction Icons */}
        <div className="absolute top-20 left-[10%] opacity-20 animate-bounce" style={{ animationDuration: '3s' }}>
          <Gavel className="h-12 w-12" />
        </div>
        <div className="absolute top-40 right-[15%] opacity-20 animate-bounce" style={{ animationDuration: '4s', animationDelay: '0.5s' }}>
          <TrendingUp className="h-10 w-10" />
        </div>
        <div className="absolute bottom-32 left-[20%] opacity-20 animate-bounce" style={{ animationDuration: '3.5s', animationDelay: '1s' }}>
          <Shield className="h-8 w-8" />
        </div>
        <div className="absolute bottom-48 right-[25%] opacity-20 animate-bounce" style={{ animationDuration: '4.5s', animationDelay: '1.5s' }}>
          <Users className="h-10 w-10" />
        </div>
        
        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiMyMDI4MzgiIGZpbGwtb3BhY2l0eT0iMC40Ij48cGF0aCBkPSJNMzYgMzRoLTJ2LTRoMnY0em0wLTZoLTJ2LTRoMnY0em0wLTZoLTJ2LTRoMnY0em0wLTZoLTJWMTJoMnY0em0wLTZoLTJWNmgydjR6bTAgMzBoLTJ2LTRoMnY0em0wIDZoLTJ2LTRoMnY0em0tNi0zNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6bTAgNmgtMnYtNGgydjR6Ii8+PC9nPjwvZz48L3N2Zz4=')] opacity-30" />
      </div>

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex flex-col">
        {/* Header with Logo */}
        <header className="py-8 px-6">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-teal-400 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30">
                <Gavel className="h-6 w-6 text-white" />
              </div>
              <span className="text-2xl font-bold bg-gradient-to-r from-white to-blue-200 bg-clip-text text-transparent">
                BidVex
              </span>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Language Toggle */}
              <button
                onClick={toggleLanguage}
                className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/10 rounded-full hover:bg-white/10 transition-colors"
                aria-label="Toggle language"
              >
                <Globe className="h-4 w-4" />
                <span className="text-sm font-medium">{currentLang.toUpperCase()}</span>
              </button>
              
              {/* Status Badge */}
              <div className={`px-4 py-2 rounded-full text-sm font-medium flex items-center gap-2 ${
                isMaintenanceMode 
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
              }`}>
                <div className={`w-2 h-2 rounded-full animate-pulse ${isMaintenanceMode ? 'bg-amber-400' : 'bg-blue-400'}`} />
                {isMaintenanceMode ? t('maintenance.statusBadgeMaintenance') : t('maintenance.statusBadgeComingSoon')}
              </div>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <main className="flex-1 flex items-center justify-center px-6 py-12">
          <div className="max-w-4xl mx-auto text-center">
            {/* Main Headline */}
            <div className="mb-8">
              <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 rounded-full border border-white/10 mb-6">
                <Sparkles className="h-4 w-4 text-yellow-400" />
                <span className="text-sm text-blue-200">
                  {isMaintenanceMode ? t('maintenance.maintenanceTagline') : t('maintenance.tagline')}
                </span>
              </div>
              
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 leading-tight">
                {isMaintenanceMode ? (
                  <>
                    {t('maintenance.headlineMaintenance')}
                    <span className="block bg-gradient-to-r from-blue-400 via-teal-400 to-blue-400 bg-clip-text text-transparent">
                      {t('maintenance.maintenanceHighlight')}
                    </span>
                  </>
                ) : (
                  <>
                    {t('maintenance.headlineComingSoon')}
                    <span className="block bg-gradient-to-r from-blue-400 via-teal-400 to-blue-400 bg-clip-text text-transparent">
                      {t('maintenance.headlineHighlight')}
                    </span>
                  </>
                )}
              </h1>
              
              <p className="text-lg sm:text-xl text-slate-300 max-w-2xl mx-auto leading-relaxed">
                {message || (isMaintenanceMode 
                  ? t('maintenance.defaultDescriptionMaintenance')
                  : t('maintenance.defaultDescriptionComingSoon')
                )}
              </p>
            </div>

            {/* Countdown Timer */}
            {countdown && (
              <div className="mb-10">
                <p className="text-sm text-slate-400 mb-4">
                  {isMaintenanceMode ? t('maintenance.expectedBackIn') : t('maintenance.launchingIn')}
                </p>
                <div className="flex justify-center gap-4">
                  {[
                    { value: countdown.days, label: t('maintenance.days') },
                    { value: countdown.hours, label: t('maintenance.hours') },
                    { value: countdown.minutes, label: t('maintenance.minutes') },
                    { value: countdown.seconds, label: t('maintenance.seconds') }
                  ].map((item) => (
                    <div key={item.label} className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl px-4 sm:px-6 py-4">
                      <div className="text-3xl sm:text-4xl font-bold text-white">{String(item.value).padStart(2, '0')}</div>
                      <div className="text-xs text-slate-400 uppercase tracking-wider">{item.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Email Subscription Form */}
            <div className="max-w-md mx-auto mb-12">
              {!subscribed ? (
                <form onSubmit={handleSubscribe} className="space-y-4">
                  <p className="text-slate-300 mb-4">
                    <Bell className="h-4 w-4 inline mr-2" />
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
                        className="pl-12 h-14 bg-white/5 border-white/10 text-white placeholder:text-slate-400 focus:border-blue-400 focus:ring-blue-400/20 rounded-xl"
                        disabled={submitting}
                        data-testid="subscribe-email-input"
                      />
                    </div>
                    <Button
                      type="submit"
                      disabled={submitting}
                      className="h-14 px-8 bg-gradient-to-r from-blue-500 to-teal-500 hover:from-blue-600 hover:to-teal-600 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/25 transition-all duration-300 hover:shadow-blue-500/40"
                      data-testid="subscribe-button"
                    >
                      {submitting ? (
                        <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
                      ) : (
                        <>
                          {t('maintenance.notifyMe')}
                          <ArrowRight className="ml-2 h-5 w-5" />
                        </>
                      )}
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="p-6 bg-green-500/10 border border-green-500/30 rounded-2xl" data-testid="subscription-success">
                  <CheckCircle className="h-12 w-12 text-green-400 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-green-300 mb-2">{t('maintenance.successTitle')}</h3>
                  <p className="text-slate-300">
                    {t('maintenance.successMessage')}
                  </p>
                </div>
              )}
            </div>

            {/* Feature Highlights */}
            {!isMaintenanceMode && (
              <div className="grid sm:grid-cols-3 gap-6 max-w-3xl mx-auto mb-12">
                {[
                  { icon: Gavel, title: t('maintenance.featureLiveAuctions'), desc: t('maintenance.featureLiveAuctionsDesc') },
                  { icon: Shield, title: t('maintenance.featureSecurePlatform'), desc: t('maintenance.featureSecurePlatformDesc') },
                  { icon: TrendingUp, title: t('maintenance.featureGreatDeals'), desc: t('maintenance.featureGreatDealsDesc') }
                ].map((feature) => (
                  <div key={feature.title} className="p-6 bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl hover:bg-white/10 transition-colors">
                    <feature.icon className="h-8 w-8 text-blue-400 mx-auto mb-4" />
                    <h3 className="font-semibold mb-2">{feature.title}</h3>
                    <p className="text-sm text-slate-400">{feature.desc}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </main>

        {/* Footer */}
        <footer className="py-8 px-6 border-t border-white/10">
          <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-sm text-slate-400">
              © {new Date().getFullYear()} BidVex. {currentLang === 'fr' ? 'Tous droits réservés.' : 'All rights reserved.'}
            </p>
            
            {/* Social Links */}
            <div className="flex items-center gap-4">
              {[
                { icon: Twitter, href: '#', label: 'Twitter' },
                { icon: Facebook, href: '#', label: 'Facebook' },
                { icon: Instagram, href: '#', label: 'Instagram' },
                { icon: Linkedin, href: '#', label: 'LinkedIn' }
              ].map((social) => (
                <a
                  key={social.label}
                  href={social.href}
                  aria-label={social.label}
                  className="w-10 h-10 flex items-center justify-center rounded-full bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <social.icon className="h-5 w-5" />
                </a>
              ))}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default MaintenancePage;
