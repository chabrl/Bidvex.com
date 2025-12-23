/**
 * BidVex Trust Badge Component
 * Displays verification status with visual indicators
 */

import React from 'react';
import { CheckCircle2, Phone, CreditCard, Shield, AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const TrustBadge = ({ 
  phoneVerified = false, 
  hasPaymentMethod = false, 
  showDetails = true,
  size = 'default' // 'small', 'default', 'large'
}) => {
  const { i18n } = useTranslation();
  const isFrench = i18n.language === 'fr';

  const isFullyVerified = phoneVerified && hasPaymentMethod;

  const sizeClasses = {
    small: 'text-xs gap-1',
    default: 'text-sm gap-2',
    large: 'text-base gap-3'
  };

  const iconSizes = {
    small: 'h-3 w-3',
    default: 'h-4 w-4',
    large: 'h-5 w-5'
  };

  const badgeSizes = {
    small: 'px-2 py-0.5',
    default: 'px-3 py-1.5',
    large: 'px-4 py-2'
  };

  if (isFullyVerified) {
    return (
      <div className={`inline-flex items-center ${sizeClasses[size]} ${badgeSizes[size]} rounded-full bg-[#06B6D4]/10 border border-[#06B6D4]/30`}>
        <Shield className={`${iconSizes[size]} text-[#06B6D4]`} />
        <span className="font-medium text-[#06B6D4]">
          {isFrench ? 'Vérifié' : 'Verified'}
        </span>
        <CheckCircle2 className={`${iconSizes[size]} text-[#06B6D4] fill-[#06B6D4]/20`} />
      </div>
    );
  }

  if (showDetails) {
    return (
      <div className="space-y-2">
        <div className={`inline-flex items-center ${sizeClasses[size]} ${badgeSizes[size]} rounded-full bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800`}>
          <AlertCircle className={`${iconSizes[size]} text-amber-500`} />
          <span className="font-medium text-amber-700 dark:text-amber-400">
            {isFrench ? 'Vérification incomplète' : 'Verification Incomplete'}
          </span>
        </div>
        
        <div className="flex flex-wrap gap-2">
          <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs ${
            phoneVerified 
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
          }`}>
            <Phone className="h-3 w-3" />
            <span>{isFrench ? 'Téléphone' : 'Phone'}</span>
            {phoneVerified && <CheckCircle2 className="h-3 w-3" />}
          </div>

          <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs ${
            hasPaymentMethod 
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
          }`}>
            <CreditCard className="h-3 w-3" />
            <span>{isFrench ? 'Paiement' : 'Payment'}</span>
            {hasPaymentMethod && <CheckCircle2 className="h-3 w-3" />}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center ${sizeClasses[size]} ${badgeSizes[size]} rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700`}>
      <span className="font-medium text-slate-500 dark:text-slate-400">
        {isFrench ? 'Non vérifié' : 'Not Verified'}
      </span>
    </div>
  );
};

export default TrustBadge;
