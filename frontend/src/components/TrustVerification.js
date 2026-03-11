import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Shield, 
  CheckCircle2, 
  CreditCard, 
  AlertTriangle,
  Loader2,
  Lock,
  Info
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Initialize Stripe
const stripePromise = loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY);

// Bilingual error messages
const ERROR_MESSAGES = {
  en: {
    card_declined: "Your card was declined. Please try a different card.",
    insufficient_funds: "Your card has insufficient funds. Please try a different card.",
    expired_card: "Your card has expired. Please use a valid card.",
    invalid_card: "Invalid card details. Please check and try again.",
    processing_error: "Payment processing error. Please try again.",
    generic_error: "A valid payment method is required to place bids.",
    network_error: "Network error. Please check your connection and try again."
  },
  fr: {
    card_declined: "Votre carte a été refusée. Veuillez essayer une autre carte.",
    insufficient_funds: "Fonds insuffisants sur votre carte. Veuillez essayer une autre carte.",
    expired_card: "Votre carte a expiré. Veuillez utiliser une carte valide.",
    invalid_card: "Détails de carte invalides. Veuillez vérifier et réessayer.",
    processing_error: "Erreur de traitement du paiement. Veuillez réessayer.",
    generic_error: "Un mode de paiement valide est requis pour enchérir.",
    network_error: "Erreur réseau. Vérifiez votre connexion et réessayez."
  }
};

const getErrorMessage = (error, lang = 'en') => {
  const messages = ERROR_MESSAGES[lang] || ERROR_MESSAGES.en;
  
  if (error?.code) {
    switch (error.code) {
      case 'card_declined':
        return messages.card_declined;
      case 'insufficient_funds':
        return messages.insufficient_funds;
      case 'expired_card':
        return messages.expired_card;
      case 'invalid_card_number':
      case 'invalid_expiry':
      case 'invalid_cvc':
        return messages.invalid_card;
      case 'processing_error':
        return messages.processing_error;
      default:
        return error.message || messages.generic_error;
    }
  }
  
  return error?.message || messages.generic_error;
};

/**
 * TrustVerificationCard - Main component for displaying trust status and verification
 */
const TrustVerificationCard = ({ onVerified, refreshUser }) => {
  const { t, i18n } = useTranslation();
  const isFrench = i18n.language === 'fr';
  
  const [loading, setLoading] = useState(true);
  const [trustStatus, setTrustStatus] = useState(null);
  const [showVerification, setShowVerification] = useState(false);
  
  useEffect(() => {
    fetchTrustStatus();
  }, []);
  
  const fetchTrustStatus = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/payments/trust-status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTrustStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch trust status:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleVerificationSuccess = async () => {
    setShowVerification(false);
    await fetchTrustStatus();
    if (refreshUser) await refreshUser();
    if (onVerified) onVerified();
    toast.success(isFrench ? 'Vérification complétée!' : 'Verification complete!');
  };
  
  if (loading) {
    return (
      <Card className="glassmorphism">
        <CardContent className="p-6 flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  }
  
  const isVerified = trustStatus?.is_verified;
  
  return (
    <Card className={`glassmorphism ${isVerified ? 'border-green-500/30' : 'border-amber-500/30'}`} data-testid="trust-verification-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Shield className={`h-5 w-5 ${isVerified ? 'text-green-500' : 'text-amber-500'}`} />
            {isFrench ? 'Statut de confiance' : 'Trust Status'}
          </CardTitle>
          <Badge 
            variant={isVerified ? 'default' : 'secondary'}
            className={isVerified ? 'bg-green-500' : 'bg-amber-500'}
          >
            {isVerified 
              ? (isFrench ? 'Vérifié' : 'Verified')
              : (isFrench ? 'Non vérifié' : 'Unverified')}
          </Badge>
        </div>
        <CardDescription>
          {isVerified 
            ? (isFrench 
                ? 'Votre compte est vérifié. Vous pouvez enchérir sur les articles.'
                : 'Your account is verified. You can place bids on items.')
            : (isFrench
                ? 'Ajoutez un mode de paiement valide pour vérifier votre compte et enchérir.'
                : 'Add a valid payment method to verify your account and place bids.')}
        </CardDescription>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {isVerified ? (
          <>
            <div className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-950/30 rounded-lg border border-green-200 dark:border-green-800">
              <CheckCircle2 className="h-8 w-8 text-green-500" />
              <div>
                <p className="font-semibold text-green-700 dark:text-green-400">
                  {isFrench ? 'Vérification complète' : 'Verification Complete'}
                </p>
                <p className="text-sm text-green-600 dark:text-green-500">
                  {trustStatus?.trust_verified_at 
                    ? (isFrench ? 'Vérifié le ' : 'Verified on ') + 
                      new Date(trustStatus.trust_verified_at).toLocaleDateString(isFrench ? 'fr-CA' : 'en-CA')
                    : ''}
                </p>
              </div>
            </div>
            
            {trustStatus?.payment_method && (
              <div className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                <CreditCard className="h-5 w-5 text-slate-500" />
                <div>
                  <p className="font-medium capitalize">
                    {trustStatus.payment_method.brand} •••• {trustStatus.payment_method.last4}
                  </p>
                  <p className="text-xs text-slate-500">
                    {isFrench ? 'Expire' : 'Expires'} {trustStatus.payment_method.exp_month}/{trustStatus.payment_method.exp_year}
                  </p>
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            <Alert className="border-amber-200 bg-amber-50 dark:bg-amber-950/30">
              <Info className="h-4 w-4 text-amber-600" />
              <AlertDescription className="text-amber-700 dark:text-amber-400">
                {isFrench 
                  ? 'Un mode de paiement valide est requis pour enchérir. Votre carte ne sera pas débitée lors de la vérification.'
                  : 'A valid payment method is required to bid. Your card will not be charged during verification.'}
              </AlertDescription>
            </Alert>
            
            {!showVerification ? (
              <Button 
                onClick={() => setShowVerification(true)}
                className="w-full"
                data-testid="complete-verification-btn"
              >
                <Lock className="mr-2 h-4 w-4" />
                {isFrench ? 'Compléter la vérification' : 'Complete Verification'}
              </Button>
            ) : (
              <Elements stripe={stripePromise}>
                <SetupIntentForm 
                  onSuccess={handleVerificationSuccess}
                  onCancel={() => setShowVerification(false)}
                  language={i18n.language}
                />
              </Elements>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

/**
 * SetupIntentForm - Stripe Elements form for card verification
 */
const SetupIntentForm = ({ onSuccess, onCancel, language = 'en' }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [clientSecret, setClientSecret] = useState(null);
  
  const isFrench = language === 'fr';
  
  useEffect(() => {
    createSetupIntent();
  }, []);
  
  const createSetupIntent = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${API}/payments/setup-intent`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setClientSecret(response.data.client_secret);
    } catch (error) {
      console.error('Failed to create SetupIntent:', error);
      setError(getErrorMessage({ code: 'processing_error' }, language));
    }
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!stripe || !elements || !clientSecret) {
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const { error: submitError, setupIntent } = await stripe.confirmCardSetup(
        clientSecret,
        {
          payment_method: {
            card: elements.getElement(CardElement),
          },
        }
      );
      
      if (submitError) {
        setError(getErrorMessage(submitError, language));
        return;
      }
      
      if (setupIntent.status === 'succeeded') {
        // Confirm with backend (in case webhook is delayed)
        const token = localStorage.getItem('token');
        await axios.post(`${API}/payments/setup-intent/confirm`, {
          setup_intent_id: setupIntent.id
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        onSuccess();
      }
      
    } catch (error) {
      console.error('Verification error:', error);
      setError(getErrorMessage(error.response?.data || error, language));
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="p-4 border rounded-lg bg-white dark:bg-slate-900">
        <CardElement
          options={{
            style: {
              base: {
                fontSize: '16px',
                color: '#1e293b',
                '::placeholder': {
                  color: '#94a3b8',
                },
                iconColor: '#3b82f6',
              },
              invalid: {
                color: '#dc2626',
                iconColor: '#dc2626',
              },
            },
            hidePostalCode: true,
          }}
        />
      </div>
      
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <Lock className="h-3 w-3" />
        <span>
          {isFrench 
            ? 'Vos informations sont protégées par Stripe'
            : 'Your information is protected by Stripe'}
        </span>
      </div>
      
      <div className="flex gap-2">
        <Button 
          type="submit" 
          disabled={!stripe || loading || !clientSecret}
          className="flex-1"
          data-testid="verify-card-btn"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {isFrench ? 'Vérification...' : 'Verifying...'}
            </>
          ) : (
            <>
              <Shield className="mr-2 h-4 w-4" />
              {isFrench ? 'Vérifier la carte' : 'Verify Card'}
            </>
          )}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          {isFrench ? 'Annuler' : 'Cancel'}
        </Button>
      </div>
    </form>
  );
};

/**
 * BidBlocker - Component to show when user tries to bid without verification
 */
const BidBlocker = ({ onVerify }) => {
  const { i18n } = useTranslation();
  const isFrench = i18n.language === 'fr';
  
  return (
    <Alert className="border-red-200 bg-red-50 dark:bg-red-950/30">
      <AlertTriangle className="h-4 w-4 text-red-600" />
      <AlertDescription className="flex flex-col gap-3">
        <span className="text-red-700 dark:text-red-400">
          {isFrench 
            ? 'Vous devez vérifier votre compte avant de pouvoir enchérir.'
            : 'You must verify your account before you can bid.'}
        </span>
        <Button size="sm" onClick={onVerify} className="w-fit">
          <Shield className="mr-2 h-4 w-4" />
          {isFrench ? 'Vérifier maintenant' : 'Verify Now'}
        </Button>
      </AlertDescription>
    </Alert>
  );
};

/**
 * useTrustStatus - Hook for checking trust status
 */
export const useTrustStatus = () => {
  const [status, setStatus] = useState({
    isVerified: false,
    canBid: false,
    loading: true
  });
  
  const checkStatus = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setStatus({ isVerified: false, canBid: false, loading: false });
        return;
      }
      
      const response = await axios.get(`${API}/payments/trust-status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setStatus({
        isVerified: response.data.is_verified,
        canBid: response.data.can_bid,
        loading: false,
        ...response.data
      });
    } catch (error) {
      setStatus({ isVerified: false, canBid: false, loading: false });
    }
  };
  
  useEffect(() => {
    checkStatus();
  }, []);
  
  return { ...status, refresh: checkStatus };
};

export { TrustVerificationCard, SetupIntentForm, BidBlocker, getErrorMessage };
export default TrustVerificationCard;
