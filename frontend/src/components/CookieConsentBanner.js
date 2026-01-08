import React, { useState, useEffect } from 'react';
import { X, Cookie, Settings, Shield, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from './ui/button';
import { Switch } from './ui/switch';

const CookieConsentBanner = () => {
  const [showBanner, setShowBanner] = useState(false);
  const [showPreferences, setShowPreferences] = useState(false);
  const [preferences, setPreferences] = useState({
    essential: true, // Always required
    analytics: false,
    personalization: false,
    marketing: false
  });

  useEffect(() => {
    // Check if user has already made a choice
    const consent = localStorage.getItem('bidvex_cookie_consent');
    if (!consent) {
      // Show banner after a short delay for better UX
      setTimeout(() => setShowBanner(true), 1000);
    }
  }, []);

  const handleAcceptAll = () => {
    const allConsent = {
      essential: true,
      analytics: true,
      personalization: true,
      marketing: true,
      timestamp: new Date().toISOString()
    };
    localStorage.setItem('bidvex_cookie_consent', JSON.stringify(allConsent));
    setShowBanner(false);
  };

  const handleSavePreferences = () => {
    const consent = {
      ...preferences,
      timestamp: new Date().toISOString()
    };
    localStorage.setItem('bidvex_cookie_consent', JSON.stringify(consent));
    setShowBanner(false);
  };

  const handleRejectAll = () => {
    const minimalConsent = {
      essential: true,
      analytics: false,
      personalization: false,
      marketing: false,
      timestamp: new Date().toISOString()
    };
    localStorage.setItem('bidvex_cookie_consent', JSON.stringify(minimalConsent));
    setShowBanner(false);
  };

  if (!showBanner) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 p-4 animate-slide-up">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border-2 border-slate-200 dark:border-slate-700 overflow-hidden">
          {/* Header */}
          <div className="p-6 bg-gradient-to-r from-blue-50 to-slate-50 dark:from-blue-900/30 dark:to-slate-800/30 border-b border-slate-200 dark:border-slate-700">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 dark:bg-blue-800 rounded-lg">
                  <Cookie className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                    🍪 We Value Your Privacy
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    BidVex uses cookies to enhance your auction experience
                  </p>
                </div>
              </div>
              <button 
                onClick={handleRejectAll}
                className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              >
                <X className="h-5 w-5 text-slate-500" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="p-6">
            <p className="text-sm text-slate-700 dark:text-slate-300 mb-4">
              We use cookies and similar technologies to provide our services, personalize your 
              auction recommendations, and analyze site traffic. By clicking &quot;Accept All&quot;, you 
              consent to our use of cookies. You can manage your preferences below.
            </p>

            {/* Manage Preferences Toggle */}
            <button
              onClick={() => setShowPreferences(!showPreferences)}
              className="flex items-center gap-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline mb-4"
            >
              <Settings className="h-4 w-4" />
              Manage Cookie Preferences
              {showPreferences ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>

            {/* Preferences Panel */}
            {showPreferences && (
              <div className="space-y-4 mb-6 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700">
                {/* Essential Cookies */}
                <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 rounded-lg">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Shield className="h-4 w-4 text-green-600" />
                      <span className="font-semibold text-slate-900 dark:text-white">Essential Cookies</span>
                      <span className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded">Required</span>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      Required for basic site functionality, security, and fraud prevention.
                    </p>
                  </div>
                  <Switch checked={true} disabled className="opacity-50" />
                </div>

                {/* Analytics Cookies */}
                <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 rounded-lg">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-900 dark:text-white">Analytics Cookies</span>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      Help us understand how visitors interact with our auction platform.
                    </p>
                  </div>
                  <Switch 
                    checked={preferences.analytics}
                    onCheckedChange={(checked) => setPreferences(prev => ({ ...prev, analytics: checked }))}
                  />
                </div>

                {/* Personalization Cookies */}
                <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 rounded-lg">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-900 dark:text-white">Personalization Cookies</span>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      Enable personalized auction recommendations based on your bidding patterns.
                    </p>
                  </div>
                  <Switch 
                    checked={preferences.personalization}
                    onCheckedChange={(checked) => setPreferences(prev => ({ ...prev, personalization: checked }))}
                  />
                </div>

                {/* Marketing Cookies */}
                <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 rounded-lg">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-900 dark:text-white">Marketing Cookies</span>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      Used to show you relevant promoted listings and advertisements.
                    </p>
                  </div>
                  <Switch 
                    checked={preferences.marketing}
                    onCheckedChange={(checked) => setPreferences(prev => ({ ...prev, marketing: checked }))}
                  />
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3">
              <Button
                onClick={handleAcceptAll}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3"
              >
                Accept All Cookies
              </Button>
              {showPreferences && (
                <Button
                  onClick={handleSavePreferences}
                  variant="outline"
                  className="flex-1 border-2 border-slate-300 dark:border-slate-600 font-semibold py-3"
                >
                  Save Preferences
                </Button>
              )}
              <Button
                onClick={handleRejectAll}
                variant="ghost"
                className="flex-1 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 font-semibold py-3"
              >
                Reject Non-Essential
              </Button>
            </div>

            {/* Privacy Link */}
            <p className="text-xs text-center text-slate-500 dark:text-slate-400 mt-4">
              Learn more in our{' '}
              <a href="/privacy" className="text-blue-600 dark:text-blue-400 hover:underline">
                Privacy Policy
              </a>
              {' '}and{' '}
              <a href="/terms" className="text-blue-600 dark:text-blue-400 hover:underline">
                Terms of Service
              </a>
            </p>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes slide-up {
          from {
            transform: translateY(100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        .animate-slide-up {
          animation: slide-up 0.4s ease-out;
        }
      `}</style>
    </div>
  );
};

export default CookieConsentBanner;
