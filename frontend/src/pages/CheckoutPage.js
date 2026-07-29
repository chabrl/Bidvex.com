import API_BASE from '../config';
import ErrorBoundary from '../components/ErrorBoundary';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { formatCurrency } from '../utils/currencyFormatter';
import { extractErrorMessage } from '../utils/errorHandler';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  ShoppingCart, 
  CreditCard, 
  Shield, 
  CheckCircle2, 
  AlertTriangle,
  Loader2,
  ArrowLeft,
  FileText,
  Info,
  User,
  Clock,
  Banknote,
  Send,
} from 'lucide-react';

import InfoTip from '../components/InfoTip';

const API = API_BASE;

const CheckoutPage = () => {
  const { listingId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { i18n } = useTranslation();
  
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [listing, setListing] = useState(null);
  const [checkoutType, setCheckoutType] = useState(null);
  const [sellerIsTaxRegistered, setSellerIsTaxRegistered] = useState(false);
  const [isPartnerListing, setIsPartnerListing] = useState(false);
  const [partnerCompany, setPartnerCompany] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('stripe');

  // Auction winner flow state
  const [isWinnerFlow, setIsWinnerFlow] = useState(false);
  const [winnerPreview, setWinnerPreview] = useState(null);
  const [latePenalty, setLatePenalty] = useState(0);
  const [isOverdue, setIsOverdue] = useState(false);
  const [paymentDeadline, setPaymentDeadline] = useState(null);
  
  const status = searchParams.get('status');
  const isFrench = i18n.language === 'fr';
  
  useEffect(() => {
    if (status === 'success') {
      setLoading(false);
      return;
    }
    loadCheckout();
  }, [listingId]); // eslint-disable-line
  
  const loadCheckout = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const token = localStorage.getItem('token');
      if (!token) {
        navigate('/auth?redirect=' + encodeURIComponent(window.location.pathname));
        return;
      }
      
      const headers = { Authorization: `Bearer ${token}` };

      // Try auction winner preview first
      try {
        const winnerRes = await axios.get(
          `${API}/payments/auction-winner-preview/${listingId}`,
          { headers }
        );
        // Success = this is an auction winner checkout
        setIsWinnerFlow(true);
        setWinnerPreview(winnerRes.data);
        setBreakdown(winnerRes.data.breakdown);
        setCheckoutType(winnerRes.data.checkout_type);
        setSellerIsTaxRegistered(winnerRes.data.seller_is_business);
        setIsPartnerListing(winnerRes.data.is_partner_listing || false);
        setLatePenalty(winnerRes.data.late_penalty || 0);
        setIsOverdue(winnerRes.data.is_overdue || false);
        setPaymentDeadline(winnerRes.data.payment_deadline);
        setListing({
          title: winnerRes.data.title,
          images: winnerRes.data.images,
          category: winnerRes.data.category,
        });
        return;
      } catch (winnerErr) {
        // If it's a specific auth/payment error, show it directly
        const winnerStatus = winnerErr.response?.status;
        if (winnerStatus === 403 || winnerStatus === 400) {
          setError(extractErrorMessage(winnerErr) || 'Access denied');
          return;
        }
        // 404 = not a winner listing, fall through to general checkout
      }

      // Existing general checkout preview flow
      const listingRes = await axios.get(`${API}/listings/${listingId}`);
      setListing(listingRes.data);
      
      const previewRes = await axios.get(
        `${API}/payments/checkout/preview/${listingId}`,
        { headers }
      );
      
      setBreakdown(previewRes.data.breakdown);
      setCheckoutType(previewRes.data.checkout_type);
      setSellerIsTaxRegistered(previewRes.data.seller_is_tax_registered);
      setIsPartnerListing(previewRes.data.is_partner_listing || false);
      setPartnerCompany(previewRes.data.partner_company || null);

    } catch (err) {
      console.error('Failed to load checkout:', err);
      setError(extractErrorMessage(err) || 'Failed to load checkout details');
    } finally {
      setLoading(false);
    }
  };
  
  const handleProceedToPayment = async () => {
    try {
      setProcessing(true);
      setError(null);
      
      const token = localStorage.getItem('token');
      const returnUrl = `${window.location.origin}/checkout/${listingId}`;

      // Offline payment (Cash or E-Transfer)
      if (paymentMethod === 'cash' || paymentMethod === 'etransfer') {
        const response = await axios.post(
          `${API}/payments/offline-checkout/${listingId}`,
          { payment_method: paymentMethod, return_url: returnUrl },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (response.data.success) {
          navigate(`/checkout/${listingId}?status=success&method=${paymentMethod}&order=${response.data.order_id}`);
        }
        return;
      }

      // Stripe payment (default)
      let response;
      if (isWinnerFlow) {
        response = await axios.post(
          `${API}/payments/auction-winner-checkout/${listingId}`,
          { return_url: returnUrl },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else {
        response = await axios.post(
          `${API}/payments/checkout/auction`,
          { listing_id: listingId, return_url: returnUrl },
          { headers: { Authorization: `Bearer ${token}` } }
        );
      }
      
      window.location.href = response.data.checkout_url;
    } catch (err) {
      console.error('Failed to create checkout session:', err);
      setError(extractErrorMessage(err) || 'Failed to initiate payment');
      setProcessing(false);
    }
  };
  
  const isVehicle = checkoutType === 'vehicle';

  // Derive buyer total (accounts for late penalty in winner flow)
  const buyerTotal = isWinnerFlow
    ? (winnerPreview?.buyer_total || 0)
    : breakdown?.buyer_total;
  
  // Success state
  if (status === 'success') {
    const method = searchParams.get('method');
    const isOffline = method === 'cash' || method === 'etransfer';
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-950 py-12">
        <div className="container max-w-2xl mx-auto px-4">
          <Card className="border-green-200 dark:border-green-800" data-testid="checkout-success">
            <CardContent className="p-8 text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
              </div>
              <h1 className="text-2xl font-bold text-green-700 dark:text-green-400 mb-2">
                {isOffline
                  ? (isFrench ? 'Commande confirmée!' : 'Order Confirmed!')
                  : (isFrench ? 'Paiement réussi!' : 'Payment Successful!')}
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mb-6">
                {isOffline
                  ? method === 'etransfer'
                    ? (isFrench
                        ? 'Votre commande est confirmée. Les instructions de virement Interac ont été envoyées à votre courriel.'
                        : 'Your order is confirmed. Interac E-Transfer instructions have been sent to your email.')
                    : (isFrench
                        ? 'Votre commande est confirmée. Veuillez contacter le vendeur pour organiser la cueillette et le paiement comptant.'
                        : 'Your order is confirmed. Please contact the seller to arrange local pickup and cash payment.')
                  : (isFrench 
                    ? 'Votre paiement a été traité avec succès.'
                    : 'Your payment has been processed successfully. You will receive a confirmation email shortly.')}
              </p>
              {isOffline && method === 'etransfer' && (
                <Alert className="mb-6 bg-blue-50 dark:bg-blue-950 border-blue-200 text-left">
                  <Send className="h-4 w-4 text-blue-600" />
                  <AlertDescription>
                    <strong>{isFrench ? 'Rappel:' : 'Reminder:'}</strong>{' '}
                    {isFrench
                      ? "Veuillez vérifier votre courriel pour l'adresse de virement Interac et inclure le numéro de référence."
                      : 'Please check your email for the Interac E-Transfer address and include the reference number.'}
                  </AlertDescription>
                </Alert>
              )}
              <div className="flex gap-4 justify-center">
                <Button onClick={() => navigate('/profile/purchases')} variant="outline">
                  <FileText className="mr-2 h-4 w-4" />
                  {isFrench ? 'Voir mes achats' : 'View My Purchases'}
                </Button>
                <Button onClick={() => navigate('/marketplace')}>
                  {isFrench ? 'Continuer les enchères' : 'Continue Bidding'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }
  
  if (error && !breakdown) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-950 py-12">
        <div className="container max-w-2xl mx-auto px-4">
          <Card className="border-red-200 dark:border-red-800" data-testid="checkout-error">
            <CardContent className="p-8 text-center">
              <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-red-700 dark:text-red-400 mb-2">
                {isFrench ? 'Erreur de chargement' : 'Loading Error'}
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-4">{error}</p>
              <Button onClick={() => navigate(-1)} variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" /> {isFrench ? 'Retour' : 'Go Back'}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-950 py-8">
      <div className="container max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="mb-6">
          <Button variant="ghost" onClick={() => navigate(-1)} className="mb-4">
            <ArrowLeft className="mr-2 h-4 w-4" /> {isFrench ? 'Retour' : 'Back'}
          </Button>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <ShoppingCart className="h-8 w-8 text-primary" />
            {isWinnerFlow
              ? (isFrench ? 'Paiement - Enchère gagnée' : 'Auction Winner Payment')
              : (isFrench ? "Finaliser l'achat" : 'Complete Purchase')}
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            {isFrench ? 'Vérifiez les détails avant de payer' : 'Review details before payment'}
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-6">
          {/* Main checkout card */}
          <div className="md:col-span-2">
            <Card data-testid="checkout-breakdown-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CreditCard className="h-5 w-5" />
                  {isFrench ? 'Détail des coûts' : 'Cost Breakdown'}
                </CardTitle>
                <CardDescription>
                  {isPartnerListing
                    ? (isFrench ? 'Encans professionnels' : 'Professional Partner Auction')
                    : isVehicle 
                      ? (isFrench ? 'Paiement hybride - Frais BidVex seulement' : 'Hybrid Payment - BidVex Fees Only')
                      : (isFrench ? 'Paiement complet via Stripe' : 'Full Payment via Stripe')}
                  {partnerCompany && (
                    <span className="ml-2 inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                      <Shield className="h-3 w-3" /> {partnerCompany}
                    </span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Overdue Warning */}
                {isOverdue && (
                  <Alert className="bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800" data-testid="overdue-alert">
                    <AlertTriangle className="h-4 w-4 text-red-600" />
                    <AlertDescription className="text-red-700 dark:text-red-300">
                      <strong>{isFrench ? 'Paiement en retard!' : 'Payment Overdue!'}</strong>
                      <p className="mt-1">
                        {isFrench
                          ? `Une pénalité de retard de ${formatCurrency(latePenalty)} a été appliquée.`
                          : `A late penalty of ${formatCurrency(latePenalty)} has been applied.`}
                      </p>
                    </AlertDescription>
                  </Alert>
                )}

                {/* Payment Deadline */}
                {paymentDeadline && !isOverdue && (
                  <Alert className="bg-amber-50 dark:bg-amber-950 border-amber-200 dark:border-amber-800" data-testid="deadline-alert">
                    <Clock className="h-4 w-4 text-amber-600" />
                    <AlertDescription className="text-amber-700 dark:text-amber-300">
                      {isFrench ? 'Date limite de paiement: ' : 'Payment deadline: '}
                      <strong>{new Date(paymentDeadline).toLocaleDateString()}</strong>
                    </AlertDescription>
                  </Alert>
                )}

                {/* Item Section */}
                <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
                  <h3 className="font-semibold text-sm text-slate-500 dark:text-slate-400 mb-3">
                    {isFrench ? 'ARTICLE' : 'ITEM SALE'}
                  </h3>
                  <div className="flex justify-between items-center">
                    <span>{isFrench ? 'Prix au marteau (Enchère gagnante)' : 'Hammer Price (Winning Bid)'}</span>
                    <span className="font-bold text-lg" data-testid="hammer-price">
                      {formatCurrency(isWinnerFlow ? winnerPreview?.hammer_price : breakdown?.hammer_price)}
                    </span>
                  </div>
                  
                  {!isVehicle && (
                    <div className="mt-2 flex justify-between items-center text-sm">
                      <span className="text-slate-600 dark:text-slate-400">
                        {isFrench ? "Taxes sur l'article (TPS/TVQ)" : 'Tax on Item (GST/QST)'}
                      </span>
                      {sellerIsTaxRegistered ? (
                        <span>{formatCurrency(breakdown?.hammer_tax_total)}</span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                            <User className="h-3 w-3 mr-1" />
                            {isFrench ? 'Vendeur particulier' : 'Private Seller'}
                          </Badge>
                          <span className="text-green-600">$0.00</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                
                {/* BidVex Fees Section */}
                <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-4">
                  <h3 className="font-semibold text-sm text-blue-600 dark:text-blue-400 mb-3 flex items-center justify-between">
                    <span>{isFrench ? 'FRAIS DE SERVICE BIDVEX' : 'BIDVEX SERVICE FEES'}</span>
                    {breakdown?.flow_type && (
                      <Badge variant="outline" className={`text-[10px] ${
                        breakdown.flow_type === 'PARTNER_FLOW'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-slate-50 text-slate-600 border-slate-200'
                      }`} data-testid="flow-type-badge">
                        {breakdown.flow_type === 'PARTNER_FLOW'
                          ? (isFrench ? 'Vendeur Partenaire' : 'Partner Seller')
                          : (isFrench ? 'Vendeur Standard' : 'Standard Seller')}
                      </Badge>
                    )}
                  </h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>
                        {isFrench ? 'Prime acheteur' : "Buyer's Premium"} 
                        <span className="text-slate-400 ml-1">
                          ({(breakdown?.buyer_premium_rate * 100)?.toFixed(1)}%)
                        </span>
                      </span>
                      <span>{formatCurrency(breakdown?.buyer_premium)}</span>
                    </div>
                    
                    {breakdown?.flow_type === 'PARTNER_FLOW' && (
                      <p className="text-xs text-emerald-600 -mt-1">
                        {isFrench ? '100% transféré au vendeur partenaire' : '100% transferred to Partner seller'}
                      </p>
                    )}
                    
                    {(isVehicle || isPartnerListing) && breakdown?.platform_fee > 0 && (
                      <div className="flex justify-between">
                        <span>
                          {isFrench ? 'Frais plateforme' : 'Platform Fee'}
                          <span className="text-slate-400 ml-1">
                            ({(breakdown?.platform_fee_rate * 100)?.toFixed(1)}%)
                          </span>
                        </span>
                        <span>{formatCurrency(breakdown?.platform_fee)}</span>
                      </div>
                    )}
                    
                    <Separator className="my-2" />
                    
                    <div className="flex justify-between">
                      <span>{isFrench ? 'TPS' : 'GST'} (5%)</span>
                      <span>{formatCurrency(breakdown?.gst)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>{isFrench ? 'TVQ' : 'QST'} (9.975%)</span>
                      <span>{formatCurrency(breakdown?.qst)}</span>
                    </div>
                    <p className="text-xs text-slate-400">
                      {isFrench
                        ? `Taxe calculée sur ${formatCurrency(breakdown?.taxable_amount || (breakdown?.hammer_price + breakdown?.buyer_premium))}`
                        : `Tax calculated on ${formatCurrency(breakdown?.taxable_amount || (breakdown?.hammer_price + breakdown?.buyer_premium))}`}
                    </p>
                  </div>
                </div>
                
                {/* ── Payment Method Selector ── */}
                <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden" data-testid="payment-method-selector">
                  <div className="bg-slate-100 dark:bg-slate-800 px-4 py-2.5">
                    <h3 className="font-semibold text-sm flex items-center gap-2">
                      <CreditCard className="h-4 w-4" />
                      {isFrench ? 'Méthode de paiement' : 'Payment Method'}
                    </h3>
                  </div>
                  <div className="p-3 space-y-2">
                    {/* Stripe */}
                    <label data-testid="payment-method-stripe"
                      className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                        paymentMethod === 'stripe' ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/20' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                      }`}>
                      <input type="radio" name="paymentMethod" value="stripe" checked={paymentMethod === 'stripe'}
                        onChange={() => setPaymentMethod('stripe')} className="mt-1 accent-blue-600" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <CreditCard className="h-4 w-4 text-blue-600" />
                          <span className="font-medium">{isFrench ? 'Carte de crédit' : 'Credit Card'}</span>
                          <span className="text-[10px] bg-blue-600 text-white px-1.5 py-0.5 rounded-full font-medium">{isFrench ? 'Recommandé' : 'Recommended'}</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">{isFrench ? 'Paiement sécurisé par Stripe. Visa, Mastercard, Amex.' : 'Secure payment via Stripe. Visa, Mastercard, Amex.'}</p>
                      </div>
                    </label>
                    {/* Cash */}
                    <label data-testid="payment-method-cash"
                      className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                        paymentMethod === 'cash' ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                      }`}>
                      <input type="radio" name="paymentMethod" value="cash" checked={paymentMethod === 'cash'}
                        onChange={() => setPaymentMethod('cash')} className="mt-1 accent-emerald-600" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <Banknote className="h-4 w-4 text-emerald-600" />
                          <span className="font-medium">{isFrench ? 'Comptant' : 'Cash'}</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">{isFrench ? 'Paiement en personne lors de la cueillette.' : 'Pay in person at local pickup.'}</p>
                      </div>
                    </label>
                    {/* E-Transfer */}
                    <label data-testid="payment-method-etransfer"
                      className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                        paymentMethod === 'etransfer' ? 'border-purple-500 bg-purple-50/50 dark:bg-purple-950/20' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                      }`}>
                      <input type="radio" name="paymentMethod" value="etransfer" checked={paymentMethod === 'etransfer'}
                        onChange={() => setPaymentMethod('etransfer')} className="mt-1 accent-purple-600" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <Send className="h-4 w-4 text-purple-600" />
                          <span className="font-medium">{isFrench ? 'Virement Interac' : 'Interac E-Transfer'}</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">{isFrench ? 'Les instructions seront envoyées par courriel.' : 'Instructions will be sent via email.'}</p>
                      </div>
                    </label>
                  </div>
                </div>

                {/* Processing Fee Section (Standard flow only — Partners absorb this) */}
                {paymentMethod === 'stripe' && breakdown?.flow_type !== 'PARTNER_FLOW' && (
                <div className="bg-amber-50 dark:bg-amber-950/30 rounded-lg p-4">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <CreditCard className="h-4 w-4 text-amber-600" />
                      <span className="font-medium">
                        {isFrench ? 'Frais de traitement sécurisé' : 'Secure Processing Fee'}
                      </span>
                      <span className="text-xs text-amber-600">(2.9% + $0.30)</span>
                    </div>
                    <span className="font-medium">{formatCurrency(breakdown?.stripe_processing_fee || breakdown?.processing_fee)}</span>
                  </div>
                </div>
                )}

                {/* Late Penalty Section */}
                {latePenalty > 0 && (
                  <div className="bg-red-50 dark:bg-red-950/30 rounded-lg p-4" data-testid="late-penalty-section">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-red-600" />
                        <span className="font-medium text-red-700 dark:text-red-400">
                          {isFrench ? 'Pénalité de retard (2%/mois)' : 'Late Penalty (2%/month)'}
                        </span>
                      </div>
                      <span className="font-bold text-red-600" data-testid="late-penalty-amount">
                        +{formatCurrency(latePenalty)}
                      </span>
                    </div>
                  </div>
                )}
                
                <Separator />
                
                {/* Total */}
                <div className="flex justify-between items-center py-2">
                  <span className="text-lg font-bold">
                    {isVehicle 
                      ? (isFrench ? 'Total à payer maintenant' : 'Total Due Now')
                      : (isFrench ? 'Total à payer' : 'Total Due')}
                    <InfoTip en="This is the total amount you'll be charged, including all fees, premiums, and applicable taxes." fr="C'est le montant total qui vous sera facturé, incluant tous les frais, primes et taxes applicables." />
                  </span>
                  <span className="text-2xl font-bold text-primary" data-testid="checkout-total">
                    {formatCurrency(buyerTotal)}
                  </span>
                </div>
                
                {/* Vehicle Note */}
                {isVehicle && (
                  <Alert className="bg-blue-50 dark:bg-blue-950 border-blue-200">
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      <strong>{isFrench ? 'Paiement véhicule:' : 'Vehicle Payment:'}</strong>
                      <p className="mt-1">
                        {isFrench
                          ? `Seuls les frais BidVex sont payés maintenant. Le prix au marteau (${formatCurrency(breakdown?.hammer_price)}) doit être payé directement au vendeur par traite bancaire.`
                          : `Only BidVex fees are paid now. Hammer price (${formatCurrency(breakdown?.hammer_price)}) must be paid directly to seller via Bank Draft.`}
                      </p>
                    </AlertDescription>
                  </Alert>
                )}
                
                {error && (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                )}
              </CardContent>
              
              <CardFooter className="flex flex-col gap-4">
                <Button 
                  className="w-full h-12 text-lg"
                  onClick={handleProceedToPayment}
                  disabled={processing}
                  data-testid="proceed-to-payment-btn"
                >
                  {processing ? (
                    <>
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      {paymentMethod === 'stripe'
                        ? (isFrench ? 'Redirection...' : 'Redirecting...')
                        : (isFrench ? 'Confirmation...' : 'Confirming...')}
                    </>
                  ) : paymentMethod === 'stripe' ? (
                    <>
                      <CreditCard className="mr-2 h-5 w-5" />
                      {isFrench ? 'Payer' : 'Pay'} {formatCurrency(buyerTotal)}
                    </>
                  ) : paymentMethod === 'cash' ? (
                    <>
                      <Banknote className="mr-2 h-5 w-5" />
                      {isFrench ? 'Confirmer la commande' : 'Confirm Order'} — {formatCurrency(buyerTotal)}
                    </>
                  ) : (
                    <>
                      <Send className="mr-2 h-5 w-5" />
                      {isFrench ? 'Confirmer le virement' : 'Confirm E-Transfer'} — {formatCurrency(buyerTotal)}
                    </>
                  )}
                </Button>
                
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Shield className="h-4 w-4" />
                  <span>
                    {isFrench 
                      ? 'Paiement sécurisé par Stripe'
                      : 'Secure payment powered by Stripe'}
                  </span>
                </div>
              </CardFooter>
            </Card>
          </div>
          
          {/* Order Summary Sidebar */}
          <div>
            <Card className="sticky top-4" data-testid="order-summary">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">
                  {isFrench ? 'Résumé' : 'Order Summary'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {listing && (
                  <>
                    {listing.images?.[0] && (
                      <img 
                        src={listing.images[0]} 
                        alt={listing.title}
                        className="w-full h-32 object-cover rounded-lg"
                      />
                    )}
                    <h3 className="font-semibold line-clamp-2">{listing.title}</h3>
                    {listing.category && <Badge variant="outline">{listing.category}</Badge>}
                  </>
                )}
                
                <Separator />
                
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-600 dark:text-slate-400">
                      {isFrench ? 'Prix au marteau' : 'Hammer Price'}
                    </span>
                    <span>
                      {formatCurrency(isWinnerFlow ? winnerPreview?.hammer_price : breakdown?.hammer_price)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600 dark:text-slate-400">
                      {isFrench ? 'Frais + Taxes' : 'Fees + Taxes'}
                    </span>
                    <span>
                      {formatCurrency(
                        (breakdown?.buyer_premium || 0) + 
                        (breakdown?.platform_fee || 0) + 
                        (breakdown?.fees_tax_total || 0) +
                        (breakdown?.hammer_tax_total || 0)
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600 dark:text-slate-400">
                      {isFrench ? 'Traitement' : 'Processing'}
                    </span>
                    <span>{formatCurrency(breakdown?.processing_fee)}</span>
                  </div>
                  {latePenalty > 0 && (
                    <div className="flex justify-between text-red-600">
                      <span>{isFrench ? 'Pénalité' : 'Late Penalty'}</span>
                      <span>+{formatCurrency(latePenalty)}</span>
                    </div>
                  )}
                </div>
                
                <Separator />
                
                <div className="flex justify-between font-bold">
                  <span>Total</span>
                  <span className="text-primary">{formatCurrency(buyerTotal)}</span>
                </div>
                
                <div className="text-xs text-slate-500 pt-2 border-t">
                  <p className="font-medium mb-1">BidVex Inc.</p>
                  <p>TPS/GST: 123456789RT0001</p>
                  <p>TVQ/QST: 1234567890TQ0001</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function CheckoutPageWithErrorBoundary(props) {
  return (
    <ErrorBoundary scope="checkout">
      <CheckoutPage {...props} />
    </ErrorBoundary>
  );
}
