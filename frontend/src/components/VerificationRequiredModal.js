/**
 * BidVex Verification Required Modal
 * Displays when users try to bid/sell without completing verification
 * Requires: phone_verified === true AND payment_method_linked === true
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { 
  Phone, CreditCard, Shield, CheckCircle2, 
  AlertTriangle, ArrowRight, X, Sparkles 
} from 'lucide-react';

const VerificationRequiredModal = ({ isOpen, onClose, action = 'bid' }) => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();

  if (!isOpen) return null;

  const phoneVerified = user?.phone_verified === true;
  const hasPaymentMethod = user?.has_payment_method === true;

  const requirements = [
    {
      id: 'phone',
      label: 'Phone Verification',
      labelFr: 'Vérification du téléphone',
      description: 'Verify your phone number via SMS',
      descriptionFr: 'Vérifiez votre numéro par SMS',
      completed: phoneVerified,
      action: () => navigate('/verify-phone'),
      buttonText: 'Verify Phone',
      buttonTextFr: 'Vérifier le téléphone',
      icon: Phone
    },
    {
      id: 'payment',
      label: 'Payment Method',
      labelFr: 'Méthode de paiement',
      description: 'Link a valid payment card',
      descriptionFr: 'Ajoutez une carte de paiement',
      completed: hasPaymentMethod,
      action: () => navigate('/settings?tab=payment'),
      buttonText: 'Add Card',
      buttonTextFr: 'Ajouter une carte',
      icon: CreditCard
    }
  ];

  const allVerified = phoneVerified && hasPaymentMethod;
  const language = user?.preferred_language || 'en';
  const isFrench = language === 'fr';

  const actionText = {
    bid: isFrench ? 'placer une enchère' : 'place a bid',
    sell: isFrench ? 'créer une annonce' : 'create a listing',
    message: isFrench ? 'envoyer un message' : 'send a message'
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] p-6 text-white relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />
          
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>

          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center">
              <Shield className="h-7 w-7 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold">
                {isFrench ? 'Action requise' : 'Action Required'}
              </h2>
              <p className="text-white/80 text-sm">
                {isFrench ? 'Marché sécurisé' : 'Secure Marketplace'}
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Message */}
          <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
            <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800 dark:text-amber-200">
              {isFrench 
                ? `Pour maintenir un marché sécurisé, veuillez vérifier votre téléphone et ajouter une carte de paiement pour ${actionText[action]}.`
                : `To maintain a secure marketplace, please verify your phone and link a payment card to ${actionText[action]}.`}
            </p>
          </div>

          {/* Requirements Checklist */}
          <div className="space-y-3">
            {requirements.map((req) => {
              const Icon = req.icon;
              return (
                <div 
                  key={req.id}
                  className={`flex items-center justify-between p-4 rounded-xl border-2 transition-all ${
                    req.completed 
                      ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20'
                      : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      req.completed 
                        ? 'bg-green-500 text-white'
                        : 'bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
                    }`}>
                      {req.completed ? (
                        <CheckCircle2 className="h-5 w-5" />
                      ) : (
                        <Icon className="h-5 w-5" />
                      )}
                    </div>
                    <div>
                      <p className={`font-medium ${
                        req.completed 
                          ? 'text-green-700 dark:text-green-400'
                          : 'text-slate-900 dark:text-white'
                      }`}>
                        {isFrench ? req.labelFr : req.label}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {isFrench ? req.descriptionFr : req.description}
                      </p>
                    </div>
                  </div>

                  {!req.completed && (
                    <Button
                      size="sm"
                      onClick={() => {
                        onClose();
                        req.action();
                      }}
                      className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:opacity-90 text-white border-0"
                    >
                      {isFrench ? req.buttonTextFr : req.buttonText}
                      <ArrowRight className="h-4 w-4 ml-1" />
                    </Button>
                  )}

                  {req.completed && (
                    <span className="text-sm font-medium text-green-600 dark:text-green-400">
                      ✓ {isFrench ? 'Complété' : 'Complete'}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Trust Note */}
          <div className="flex items-start gap-3 p-4 rounded-xl bg-[#1E3A8A]/5 dark:bg-[#1E3A8A]/20">
            <Sparkles className="h-5 w-5 text-[#06B6D4] flex-shrink-0 mt-0.5" />
            <div className="text-xs text-slate-600 dark:text-slate-300">
              <p className="font-medium text-slate-800 dark:text-white mb-1">
                {isFrench ? 'Pourquoi ces vérifications ?' : 'Why these verifications?'}
              </p>
              {isFrench 
                ? 'Ces mesures protègent tous les utilisateurs contre la fraude et garantissent des transactions fiables sur BidVex.'
                : 'These measures protect all users from fraud and ensure trustworthy transactions on BidVex.'}
            </div>
          </div>

          {/* Close Button */}
          <Button
            variant="outline"
            className="w-full"
            onClick={onClose}
          >
            {isFrench ? 'Fermer' : 'Close'}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default VerificationRequiredModal;
