import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from './ui/button';
import { ShieldCheck } from 'lucide-react';

const STORAGE_KEY = 'bidvex_cookie_consent';

const CookieConsent = () => {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem(STORAGE_KEY);
    if (!consent) setVisible(true);
  }, []);

  const accept = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ accepted: true, ts: Date.now() }));
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-[9999]"
      style={{ backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}
      data-testid="cookie-banner"
    >
      <div
        className="max-w-5xl mx-auto px-6 py-4 flex flex-col sm:flex-row items-center gap-4"
        style={{ backgroundColor: 'rgba(15, 23, 42, 0.92)', borderTop: '1px solid rgba(100, 116, 139, 0.25)' }}
      >
        <ShieldCheck className="h-6 w-6 shrink-0 hidden sm:block" style={{ color: '#38bdf8' }} />

        <p className="text-sm leading-relaxed flex-1" style={{ color: '#cbd5e1' }}>
          {t('cookie.message',
            'We use cookies and similar technologies to improve your experience, analyze traffic, and personalize content. By continuing to use this site you consent to our use of cookies in accordance with our Privacy Policy and Quebec\'s Law 25.'
          )}{' '}
          <a
            href="/privacy-policy"
            className="underline underline-offset-2 hover:text-white transition-colors"
            style={{ color: '#38bdf8' }}
          >
            {t('cookie.learnMore', 'Learn more')}
          </a>
        </p>

        <div className="flex gap-3 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={accept}
            className="border-slate-500 hover:border-white"
            style={{ color: '#e2e8f0', backgroundColor: 'transparent' }}
            data-testid="cookie-decline-btn"
          >
            {t('cookie.decline', 'Decline')}
          </Button>
          <Button
            size="sm"
            onClick={accept}
            style={{ backgroundColor: '#0ea5e9', color: '#ffffff' }}
            className="hover:opacity-90"
            data-testid="cookie-accept-btn"
          >
            {t('cookie.accept', 'Accept')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default CookieConsent;
