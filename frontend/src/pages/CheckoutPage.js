import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
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
  Building2,
  User
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CheckoutPage = () => {
  const { listingId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t, i18n } = useTranslation();
  
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [listing, setListing] = useState(null);
  const [checkoutType, setCheckoutType] = useState(null);
  const [sellerIsTaxRegistered, setSellerIsTaxRegistered] = useState(false);
  
  // Check for success/cancelled status from Stripe redirect
  const status = searchParams.get('status');
  const sessionId = searchParams.get('session_id');
  
  useEffect(() => {
    if (status === 'success') {
      // Payment successful - show confirmation
      setLoading(false);
      return;
    }
    
    fetchCheckoutPreview();
  }, [listingId]);
  
  const fetchCheckoutPreview = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const token = localStorage.getItem('token');
      if (!token) {
        navigate('/auth?redirect=' + encodeURIComponent(window.location.pathname));
        return;
      }
      
      // Get listing details
      const listingRes = await axios.get(`${API}/listings/${listingId}`);
      setListing(listingRes.data);
      
      // Get checkout preview
      const previewRes = await axios.get(`${API}/payments/checkout/preview/${listingId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setBreakdown(previewRes.data.breakdown);
      setCheckoutType(previewRes.data.checkout_type);
      setSellerIsTaxRegistered(previewRes.data.seller_is_tax_registered);
      
    } catch (err) {
      console.error('Failed to load checkout:', err);
      setError(err.response?.data?.detail || 'Failed to load checkout details');
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
      
      const response = await axios.post(`${API}/payments/checkout/auction`, {
        listing_id: listingId,
        return_url: returnUrl
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Redirect to Stripe Checkout
      window.location.href = response.data.checkout_url;
      
    } catch (err) {
      console.error('Failed to create checkout session:', err);
      setError(err.response?.data?.detail || 'Failed to initiate payment');
      setProcessing(false);
    }
  };
  
  const formatCurrency = (amount) => {
    if (!amount && amount !== 0) return '$0.00';
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount);
  };
  
  const isVehicle = checkoutType === 'vehicle';
  const isFrench = i18n.language === 'fr';
  
  // Success state
  if (status === 'success') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-950 py-12">
        <div className="container max-w-2xl mx-auto px-4">
          <Card className="border-green-200 dark:border-green-800">
            <CardContent className="p-8 text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
              </div>
              <h1 className="text-2xl font-bold text-green-700 dark:text-green-400 mb-2">
                {isFrench ? 'Paiement réussi!' : 'Payment Successful!'}
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mb-6">
                {isFrench 
                  ? 'Votre paiement a été traité avec succès. Vous recevrez un email de confirmation sous peu.'
                  : 'Your payment has been processed successfully. You will receive a confirmation email shortly.'}
              </p>
              
              {isVehicle && (
                <Alert className="bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 mb-6 text-left">
                  <Info className="h-4 w-4 text-blue-600" />
                  <AlertDescription className="text-blue-700 dark:text-blue-300">
                    <strong>{isFrench ? 'Prochaines étapes:' : 'Next Steps:'}</strong>
                    <p className="mt-1">
                      {isFrench 
                        ? 'Veuillez envoyer le prix au marteau au vendeur par traite bancaire dans les 14 jours.'
                        : 'Please send the hammer price to the seller via Bank Draft within 14 days.'}
                    </p>
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
  
  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }
  
  // Error state
  if (error && !breakdown) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-950 py-12">
        <div className="container max-w-2xl mx-auto px-4">
          <Card className="border-red-200 dark:border-red-800">
            <CardContent className="p-8 text-center">
              <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-red-700 dark:text-red-400 mb-2">
                {isFrench ? 'Erreur de chargement' : 'Loading Error'}
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-4">{error}</p>
              <Button onClick={() => navigate(-1)} variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                {isFrench ? 'Retour' : 'Go Back'}
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
            <ArrowLeft className="mr-2 h-4 w-4" />
            {isFrench ? 'Retour' : 'Back'}
          </Button>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <ShoppingCart className="h-8 w-8 text-primary" />
            {isFrench ? 'Finaliser l\'achat' : 'Complete Purchase'}
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            {isFrench ? 'Vérifiez les détails avant de payer' : 'Review details before payment'}
          </p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-6">
          {/* Main checkout card */}
          <div className="md:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CreditCard className="h-5 w-5" />
                  {isFrench ? 'Détail des coûts' : 'Cost Breakdown'}
                </CardTitle>
                <CardDescription>
                  {isVehicle 
                    ? (isFrench ? 'Paiement hybride - Frais BidVex seulement' : 'Hybrid Payment - BidVex Fees Only')
                    : (isFrench ? 'Paiement complet via Stripe' : 'Full Payment via Stripe')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Item Section */}
                <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
                  <h3 className="font-semibold text-sm text-slate-500 dark:text-slate-400 mb-3">
                    {isFrench ? 'ARTICLE' : 'ITEM SALE'}
                  </h3>
                  
                  <div className="flex justify-between items-center">
                    <span>{isFrench ? 'Prix au marteau (Enchère gagnante)' : 'Hammer Price (Winning Bid)'}</span>
                    <span className="font-bold text-lg">{formatCurrency(breakdown?.hammer_price)}</span>
                  </div>
                  
                  {/* Tax on item */}
                  {!isVehicle && (
                    <div className="mt-2 flex justify-between items-center text-sm">
                      <span className="text-slate-600 dark:text-slate-400">
                        {isFrench ? 'Taxes sur l\'article (TPS/TVQ)' : 'Tax on Item (GST/QST)'}
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
                  <h3 className="font-semibold text-sm text-blue-600 dark:text-blue-400 mb-3">
                    {isFrench ? 'FRAIS DE SERVICE BIDVEX' : 'BIDVEX SERVICE FEES'}
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
                    
                    {isVehicle && breakdown?.platform_fee > 0 && (
                      <div className="flex justify-between">
                        <span>
                          {isFrench ? 'Frais plateforme' : 'Platform Fee'}
                          <span className="text-slate-400 ml-1">(2.5%)</span>
                        </span>
                        <span>{formatCurrency(breakdown?.platform_fee)}</span>
                      </div>
                    )}
                    
                    <Separator className="my-2" />
                    
                    <div className="flex justify-between">
                      <span>{isFrench ? 'TPS sur les frais' : 'GST on Fees'} (5%)</span>
                      <span>{formatCurrency(breakdown?.gst_on_fees)}</span>
                    </div>
                    
                    <div className="flex justify-between">
                      <span>{isFrench ? 'TVQ sur les frais' : 'QST on Fees'} (9.975%)</span>
                      <span>{formatCurrency(breakdown?.qst_on_fees)}</span>
                    </div>
                  </div>
                </div>
                
                {/* Processing Fee Section */}
                <div className="bg-amber-50 dark:bg-amber-950/30 rounded-lg p-4">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <CreditCard className="h-4 w-4 text-amber-600" />
                      <span className="font-medium">
                        {isFrench ? 'Frais de traitement' : 'Processing Fee'}
                      </span>
                      <span className="text-xs text-amber-600">(2.9% + $0.30)</span>
                    </div>
                    <span className="font-medium">{formatCurrency(breakdown?.processing_fee)}</span>
                  </div>
                  <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
                    {isFrench 
                      ? 'Frais de traitement de carte de crédit'
                      : 'Credit card processing fee'}
                  </p>
                </div>
                
                <Separator />
                
                {/* Total */}
                <div className="flex justify-between items-center py-2">
                  <span className="text-lg font-bold">
                    {isVehicle 
                      ? (isFrench ? 'Total à payer maintenant' : 'Total Due Now')
                      : (isFrench ? 'Total à payer' : 'Total Due')}
                  </span>
                  <span className="text-2xl font-bold text-primary">
                    {formatCurrency(breakdown?.buyer_total)}
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
                
                {/* Error */}
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
                      {isFrench ? 'Redirection...' : 'Redirecting...'}
                    </>
                  ) : (
                    <>
                      <CreditCard className="mr-2 h-5 w-5" />
                      {isFrench ? 'Payer' : 'Pay'} {formatCurrency(breakdown?.buyer_total)}
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
            <Card className="sticky top-4">
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
                    <Badge variant="outline">{listing.category}</Badge>
                  </>
                )}
                
                <Separator />
                
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-600 dark:text-slate-400">
                      {isFrench ? 'Prix au marteau' : 'Hammer Price'}
                    </span>
                    <span>{formatCurrency(breakdown?.hammer_price)}</span>
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
                </div>
                
                <Separator />
                
                <div className="flex justify-between font-bold">
                  <span>{isFrench ? 'Total' : 'Total'}</span>
                  <span className="text-primary">{formatCurrency(breakdown?.buyer_total)}</span>
                </div>
                
                {/* Tax Registration Info */}
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

export default CheckoutPage;
