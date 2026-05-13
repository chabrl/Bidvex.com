/**
 * iter211 P4 — Demo Mode dashboard banner (amber).
 *
 * Renders only when `user.is_demo_account === true`. Shows on top of every
 * dashboard surface so the demo user always sees their isolation state.
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkles } from 'lucide-react';

const DemoModeBanner = ({ user }) => {
  const { i18n } = useTranslation();
  if (!user?.is_demo_account) return null;
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  return (
    <div
      data-testid="demo-mode-banner"
      className="rounded-xl border-2 border-amber-300 bg-gradient-to-r from-amber-50 to-yellow-50 p-3 mb-4 flex items-start gap-3"
    >
      <Sparkles className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-sm font-semibold text-amber-900">
          {isFr ? '🎭 Mode démonstration' : '🎭 Demo Mode'}
        </p>
        <p className="text-xs text-amber-800 mt-0.5 leading-relaxed">
          {isFr
            ? "Vos annonces ne sont pas visibles par les vrais utilisateurs. Les paiements sont simulés. Vous ne pouvez pas enchérir sur de vraies annonces."
            : 'Your listings are not visible to real users. Payments are simulated. You cannot bid on real listings.'}
        </p>
      </div>
    </div>
  );
};

export default DemoModeBanner;
export { DemoModeBanner };
