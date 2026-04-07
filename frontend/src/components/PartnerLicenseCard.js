import React from 'react';
import { Store, Check, Shield, Headphones, BarChart3, FileSpreadsheet, Megaphone, Sparkles, Crown } from 'lucide-react';
import { Button } from './ui/button';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

const PartnerLicenseCard = ({ user }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const features = [
    { icon: Check, key: 'subCards.features.discount25' },
    { icon: Store, key: 'subCards.features.storefront' },
    { icon: FileSpreadsheet, key: 'subCards.features.csvImport' },
    { icon: Sparkles, key: 'subCards.features.earlyAccess2h' },
    { icon: Megaphone, key: 'subCards.features.featured10' },
    { icon: BarChart3, key: 'subCards.features.analyticsExport' },
    { icon: Headphones, key: 'subCards.features.prioritySupport' },
  ];

  const isActive = user?.is_partner && user?.subscription_status === 'active';
  const renewDate = user?.subscription_end_date ? new Date(user.subscription_end_date).toLocaleDateString() : null;

  return (
    <div className="w-full" data-testid="partner-license-card">
      <div className="rounded-2xl border-2 border-cyan-400/50 bg-gradient-to-br from-cyan-50 via-white to-teal-50 dark:from-cyan-950/30 dark:via-slate-800/80 dark:to-teal-950/30 p-6 lg:p-8 shadow-lg shadow-cyan-100/50 dark:shadow-cyan-900/20">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center shadow-lg">
            <Store className="h-7 w-7 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xl font-bold text-slate-900 dark:text-white" data-testid="partner-license-title">
                {t('subCards.plans.partner_pro.name')}
              </h3>
              {isActive && (
                <span className="px-2.5 py-0.5 bg-green-500 text-white text-xs font-bold rounded-full" data-testid="partner-active-badge">
                  ACTIVE
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t('subCards.plans.partner_pro.description')}
            </p>
          </div>
        </div>

        {/* Renewal info */}
        {renewDate && (
          <div className="mb-5 px-4 py-2.5 rounded-lg bg-cyan-100/60 dark:bg-cyan-900/20 border border-cyan-200 dark:border-cyan-800">
            <p className="text-sm text-cyan-800 dark:text-cyan-300">
              <Shield className="inline h-4 w-4 mr-1.5 -mt-0.5" />
              {isActive ? `Renews ${renewDate}` : `Expired ${renewDate}`}
            </p>
          </div>
        )}

        {/* Features grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-6">
          {features.map((f, i) => {
            const Icon = f.icon;
            return (
              <div key={i} className="flex items-center gap-2.5 py-1.5">
                <div className="w-5 h-5 rounded-full bg-cyan-100 dark:bg-cyan-900/40 flex items-center justify-center shrink-0">
                  <Icon className="h-3 w-3 text-cyan-600 dark:text-cyan-400" />
                </div>
                <span className="text-sm text-slate-700 dark:text-slate-300">{t(f.key)}</span>
              </div>
            );
          })}
        </div>

        {/* CTA */}
        <Button
          onClick={() => navigate('/partner/dashboard')}
          className="w-full h-11 rounded-xl bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-700 hover:to-teal-700 text-white font-semibold shadow-lg shadow-cyan-500/25"
          data-testid="partner-dashboard-btn"
        >
          <Crown className="h-4 w-4 mr-2" />
          Partner Dashboard
        </Button>
      </div>
    </div>
  );
};

export default PartnerLicenseCard;
