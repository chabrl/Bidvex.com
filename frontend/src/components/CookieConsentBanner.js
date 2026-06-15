import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Shield, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { useCookieConsent, DEFAULT_CONSENT } from '../hooks/useCookieConsent';
import API_BASE from '../config';

const CookieConsentBanner = () => {
  const { i18n } = useTranslation();
  const { hasConsented, acceptAll, refuseAll, saveCustom } = useCookieConsent();
  const [visible, setVisible] = useState(false);
  const [showCustomize, setShowCustomize] = useState(false);
  const [strings, setStrings] = useState(null);
  const [prefs, setPrefs] = useState({ ...DEFAULT_CONSENT });

  // Show banner after short delay if user hasn't consented yet.
  // Phase 5.4 — E2E test bypass: if REACT_APP_E2E_AUTO_ACCEPT_COOKIES is set,
  // OR window.__BIDVEX_E2E__ is true, OR localStorage flag is set, auto-accept
  // on mount so Playwright suites can authenticate without clicking through
  // the Law-25 banner.
  useEffect(() => {
    const e2eEnv = (typeof process !== 'undefined' && process.env && process.env.REACT_APP_E2E_AUTO_ACCEPT_COOKIES === 'true');
    let e2eWindow = false;
    let e2eStorage = false;
    try { e2eWindow = !!(typeof window !== 'undefined' && window.__BIDVEX_E2E__); } catch { /* noop */ }
    try { e2eStorage = (localStorage.getItem('bidvex_e2e_auto_accept_cookies') === 'true'); } catch { /* noop */ }
    if ((e2eEnv || e2eWindow || e2eStorage) && !hasConsented) {
      try { acceptAll(); } catch { /* noop */ }
      return;
    }
    if (!hasConsented) {
      const timer = setTimeout(() => setVisible(true), 800);
      return () => clearTimeout(timer);
    }
  }, [hasConsented, acceptAll]);

  // iter304 — Re-fetch localized strings whenever the active i18n language changes,
  // so the banner re-renders in FR when the user toggles language WITHOUT
  // requiring a page reload.
  useEffect(() => {
    if (!visible) return;
    const lang = (i18n.language || 'en').toLowerCase().startsWith('fr') ? 'fr' : 'en';
    fetch(`${API_BASE}/legal/cookie-policy?lang=${lang}`)
      .then((r) => r.json())
      .then((d) => setStrings(d.consent))
      .catch(() => {});
  }, [visible, i18n.language]);

  if (!visible || hasConsented) return null;

  // Fallback if API hasn't responded yet
  const S = strings || {
    banner_title: 'Cookie Consent',
    banner_text: 'We use cookies to enhance your experience.',
    accept_all: 'Accept All',
    refuse_all: 'Refuse All',
    customize: 'Customize',
    privacy_policy_link: '/privacy-policy',
    privacy_policy_text: 'Privacy Policy',
    privacy_by_default: '',
    law25_notice: '',
    categories: {
      strictly_necessary: { name: 'Strictly Necessary', description: 'Required for core functionality.', required: true },
      functionality: { name: 'Functionality', description: 'Enhanced features.', required: false },
      analytics: { name: 'Analytics', description: 'Usage data.', required: false },
      marketing: { name: 'Marketing', description: 'Personalized ads.', required: false },
    },
  };

  const cats = S.categories || {};

  const _notifyPixel = () => {
    // Phase 5 — Boot Meta Pixel once analytics consent is granted (CASL-compliant)
    try {
      import('../utils/metaPixel').then(({ notifyConsentGranted }) => notifyConsentGranted());
    } catch (e) {
      // silent
    }
  };

  const _revokePixel = () => {
    // Phase 5 Hotfix — CASL-compliant withdrawal. Immediately revokes
    // Meta Pixel tracking and clears any queued events.
    try {
      import('../utils/metaPixel').then(({ revokeConsent }) => revokeConsent());
    } catch (e) {
      // silent
    }
  };

  const handleAcceptAll = () => {
    acceptAll();
    setVisible(false);
    _notifyPixel();
  };
  const handleRefuseAll = () => {
    refuseAll();
    setVisible(false);
    _revokePixel();
  };
  const handleSave = () => {
    saveCustom(prefs);
    setVisible(false);
    if (prefs?.analytics) _notifyPixel();
    else _revokePixel();
  };

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-[9999] p-3 sm:p-4"
      data-testid="cookie-consent-banner"
      style={{ animation: 'cookie-slide-up 0.35s ease-out' }}
    >
      <div className="max-w-2xl mx-auto">
        <div
          className="rounded-2xl overflow-hidden shadow-2xl border border-slate-700/60"
          style={{ backgroundColor: '#0f172a' }}
        >
          {/* Header */}
          <div className="px-5 pt-5 pb-3 flex items-start gap-3">
            <div
              className="p-2 rounded-lg shrink-0"
              style={{ backgroundColor: 'rgba(14,165,233,0.15)' }}
            >
              <Shield className="h-5 w-5" style={{ color: '#38bdf8' }} />
            </div>
            <div className="flex-1 min-w-0">
              <h3
                className="text-base font-semibold mb-1"
                style={{ color: '#f1f5f9' }}
                data-testid="cookie-banner-title"
              >
                {S.banner_title}
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: '#94a3b8' }}>
                {S.banner_text}
              </p>
            </div>
          </div>

          {/* Privacy-by-default notice */}
          {S.privacy_by_default && (
            <div className="px-5 pb-2">
              <p className="text-xs" style={{ color: '#64748b' }}>
                {S.privacy_by_default}
              </p>
            </div>
          )}

          {/* Customize toggle */}
          <div className="px-5">
            <button
              onClick={() => setShowCustomize(!showCustomize)}
              className="flex items-center gap-1.5 text-xs font-medium py-1.5 transition-colors"
              style={{ color: '#38bdf8' }}
              data-testid="cookie-customize-btn"
            >
              <Settings className="h-3.5 w-3.5" />
              {S.customize}
              {showCustomize ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>
          </div>

          {/* Category toggles */}
          {showCustomize && (
            <div
              className="mx-5 mt-2 mb-1 p-3 rounded-lg space-y-2"
              style={{ backgroundColor: 'rgba(30,41,59,0.7)', border: '1px solid rgba(71,85,105,0.4)' }}
              data-testid="cookie-preferences-panel"
            >
              {Object.entries(cats).map(([key, cat]) => (
                <div
                  key={key}
                  className="flex items-center justify-between gap-3 p-2.5 rounded-lg"
                  style={{ backgroundColor: 'rgba(15,23,42,0.6)' }}
                  data-testid={`cookie-category-${key}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium" style={{ color: '#e2e8f0' }}>
                        {cat.name}
                      </span>
                      {cat.required && (
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                          style={{ backgroundColor: 'rgba(34,197,94,0.15)', color: '#4ade80' }}
                        >
                          {strings ? (S.banner_title === 'Consentement aux temoins' ? 'Requis' : 'Required') : 'Required'}
                        </span>
                      )}
                    </div>
                    <p className="text-xs mt-0.5" style={{ color: '#64748b' }}>
                      {cat.description}
                    </p>
                  </div>
                  <Switch
                    checked={cat.required ? true : !!prefs[key]}
                    disabled={cat.required}
                    onCheckedChange={(v) =>
                      !cat.required && setPrefs((p) => ({ ...p, [key]: v }))
                    }
                    className={cat.required ? 'opacity-50' : ''}
                    data-testid={`cookie-toggle-${key}`}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Action buttons */}
          <div className="px-5 pt-3 pb-4 flex flex-col sm:flex-row gap-2">
            <Button
              onClick={handleAcceptAll}
              className="flex-1 font-semibold text-sm py-2.5"
              style={{ backgroundColor: '#0ea5e9', color: '#fff' }}
              data-testid="cookie-accept-all-btn"
            >
              {S.accept_all}
            </Button>
            {showCustomize && (
              <Button
                onClick={handleSave}
                variant="outline"
                className="flex-1 font-semibold text-sm py-2.5 border-slate-600"
                style={{ color: '#e2e8f0', backgroundColor: 'transparent' }}
                data-testid="cookie-save-prefs-btn"
              >
                {strings
                  ? S.banner_title === 'Consentement aux temoins'
                    ? 'Enregistrer'
                    : 'Save Preferences'
                  : 'Save Preferences'}
              </Button>
            )}
            <Button
              onClick={handleRefuseAll}
              variant="ghost"
              className="flex-1 font-semibold text-sm py-2.5"
              style={{ color: '#94a3b8' }}
              data-testid="cookie-refuse-all-btn"
            >
              {S.refuse_all}
            </Button>
          </div>

          {/* Law 25 notice + privacy link */}
          <div
            className="px-5 py-3 text-center"
            style={{ borderTop: '1px solid rgba(71,85,105,0.3)', backgroundColor: 'rgba(15,23,42,0.5)' }}
          >
            {S.law25_notice && (
              <p className="text-[11px] mb-1" style={{ color: '#475569' }}>
                {S.law25_notice}
              </p>
            )}
            <a
              href={S.privacy_policy_link || '/privacy-policy'}
              className="text-xs hover:underline"
              style={{ color: '#38bdf8' }}
              data-testid="cookie-privacy-link"
            >
              {S.privacy_policy_text || 'Privacy Policy'}
            </a>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes cookie-slide-up {
          from { transform: translateY(100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default CookieConsentBanner;
