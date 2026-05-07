import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { extractErrorMessage } from '../utils/errorHandler';
import TaxInterviewModal from '../components/TaxInterviewModal';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Loader2, Upload, AlertTriangle } from 'lucide-react';
import LocationSelector from '../components/LocationSelector';
import CategorySelector from '../components/CategorySelector';
import InfoTip from '../components/InfoTip';
import { CFIASoilBanner, CFIASoilCheckbox } from '../components/legal/LegalComplianceSections';
import useGeoLocation from '../hooks/useGeoLocation';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';

const API = API_BASE;

const CFIA_TRIGGER_CATEGORIES = [
  "farm equipment", "tractors", "excavators", "heavy_construction", "bulldozers",
  "skid_steers", "combines", "industrial_machinery", "construction & excavation",
  "material handling (forklifts)", "tillage & seeding", "harvesting (combines)",
  "livestock & dairy",
  // French equivalents
  "équipement agricole", "tracteurs", "excavatrices", "construction lourde",
  "bouteurs", "chargeurs compacts", "moissonneuses", "machinerie industrielle",
  "construction et excavation", "manutention", "travail du sol et semis",
  "récolte (moissonneuses-batteuses)", "élevage et produits laitiers",
];

const CreateListingPage = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const geo = useGeoLocation();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [cfiaDeclaration, setCfiaDeclaration] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    condition: 'good',
    starting_price: '',
    buy_now_price: '',
    images: [],
    country: 'CA',
    region: '',
    city: '',
    postal_code: '',
    location: '',
    auction_end_date: '',
    currency: 'CAD',
  });

  // Buyer's Premium — default to org setting
  const [buyersPremiumPercent, setBuyersPremiumPercent] = useState('');
  const isOpcCertified = user?.is_opc_certified === true;
  const isPartner = user?.is_partner === true || user?.role === 'partner' || user?.role === 'admin';

  // Seller Payment Method
  const [paymentMethod, setPaymentMethod] = useState('stripe');

  // Deposit (Spec Feature 1) — single field, single flow
  const [requiresDeposit, setRequiresDeposit] = useState(false);
  const [depositType, setDepositType] = useState('fixed'); // 'fixed' | 'percentage'
  const [depositAmount, setDepositAmount] = useState('');

  // Shipping & Visit Options
  const [shippingInfo, setShippingInfo] = useState({
    available: false,
    methods: [],
    rates: {},
    delivery_time: ''
  });

  const [visitAvailability, setVisitAvailability] = useState({
    offered: false,
    dates: '',
    instructions: ''
  });
  
  // Final Seller Agreement (Binding Contract)
  const [finalAgreementAccepted, setFinalAgreementAccepted] = useState(false);

  useEffect(() => {
    fetchCategories();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setFormData(prev => ({
      ...prev,
      auction_end_date: tomorrow.toISOString().slice(0, 16)
    }));
    // Pre-fill buyer's premium from org/partner setting
    if (user?.custom_premium_rate != null) {
      setBuyersPremiumPercent(String(Math.round(user.custom_premium_rate * 100 * 100) / 100));
    }
  }, [user]);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleImageUpload = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => {
      if (file.size > 5000000) {
        toast.error('Image size should be less than 5MB');
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        setFormData(prev => ({
          ...prev,
          images: [...prev.images, reader.result]
        }));
      };
      reader.readAsDataURL(file);
    });
  };

  const removeImage = (index) => {
    setFormData({
      ...formData,
      images: formData.images.filter((_, i) => i !== index)
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Iter187: enforce CRA Tax Onboarding at submit time, not at form-mount time
    if (taxOnboardingPending) {
      toast.error('Please complete your tax declaration before publishing your listing.');
      return;
    }
    setLoading(true);

    try {
      const payload = {
        ...formData,
        starting_price: parseFloat(formData.starting_price),
        buy_now_price: formData.buy_now_price ? parseFloat(formData.buy_now_price) : null,
        auction_end_date: new Date(formData.auction_end_date).toISOString(),
        shipping_info: shippingInfo.available ? shippingInfo : null,
        visit_availability: visitAvailability.offered ? visitAvailability : null,
        // Convert percent → rate (e.g. 15 → 0.15), null if blank (org default applies server-side)
        buyers_premium_rate: buyersPremiumPercent !== '' ? parseFloat(buyersPremiumPercent) / 100 : null,
        payment_method: paymentMethod,
        // Deposit (spec Feature 1)
        requires_deposit: requiresDeposit,
        deposit_amount: requiresDeposit && depositAmount ? parseFloat(depositAmount) : null,
        deposit_type: requiresDeposit ? depositType : null,
        // Mandatory Binding Agreement
        agreement_accepted: finalAgreementAccepted,
      };

      const response = await axios.post(`${API}/listings`, payload);
      toast.success('Listing created successfully!');
      navigate(`/listing/${response.data.id}`);
    } catch (error) {
      console.error('Failed to create listing:', error);
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Failed to create listing');
    } finally {
      setLoading(false);
    }
  };

  // Tax Onboarding Gatekeeper — CRA Part XX Compliance
  // Iter187: render form first, mount modal as overlay so testids are reachable
  // and the modal does not interrupt mid-form. User cannot submit until tax_onboarding_completed.
  const taxOnboardingPending = !!(user && !user.tax_onboarding_completed);

  // Partner Fee Lockdown
  if (user?.is_partner && !user?.platform_fee_paid) {
    return (
      <div className="min-h-screen py-8 px-4" data-testid="partner-fee-lockdown-page">
        <div className="max-w-lg mx-auto">
          <Card className="border-amber-200 bg-amber-50">
            <CardHeader>
              <CardTitle className="text-xl font-bold text-amber-900 flex items-center gap-2">
                <Loader2 className="h-5 w-5 text-amber-600" /> Annual Partner Fee Required
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-amber-700">
                Your annual partner fee of <strong>$100 CAD/year + taxes</strong> has not been paid.
                Please complete your payment to activate listing capabilities.
              </p>
              <p className="text-sm text-amber-600">
                Check your email for the payment link, or go to your <strong>{t("profile.accountSettingsLink")}</strong> to initiate payment.
              </p>
              <div className="flex gap-2">
                <Button onClick={() => navigate('/settings')} className="bg-amber-600 hover:bg-amber-700 text-white" size="sm">
                  Go to Settings
                </Button>
                <Button onClick={() => navigate('/')} variant="outline" size="sm">
                  Back to Home
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4" data-testid="create-listing-page">
      <div className="max-w-3xl mx-auto">
        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle className="text-2xl font-bold">{t('createListing.createNewListing', 'Create New Listing')}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="title">{t('createListing.auctionTitle', 'Title')} *
                  <InfoTip en="A clear, descriptive title helps buyers find your item faster." fr="Un titre clair et descriptif aide les acheteurs à trouver votre article plus rapidement." />
                </Label>
                <Input
                  id="title"
                  name="title"
                  value={formData.title}
                  onChange={handleChange}
                  required
                  data-testid="title-input"
                  placeholder={t('createListing.auctionTitlePlaceholder', 'Enter a descriptive title')}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">{t('createListing.description', 'Description')} *
                  <InfoTip en="Include condition details, dimensions, and any flaws. Honest descriptions build trust." fr="Incluez l'état, les dimensions et tout défaut. Les descriptions honnêtes inspirent confiance." />
                </Label>
                <Textarea
                  id="description"
                  name="description"
                  value={formData.description}
                  onChange={handleChange}
                  required
                  rows={4}
                  data-testid="description-input"
                  placeholder={t('createListing.descriptionPlaceholder', 'Describe your item in detail')}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <CategorySelector
                    value={formData.category}
                    onChange={(val) => setFormData(prev => ({ ...prev, category: val }))}
                    required
                    filterVehicles
                    userRole={user?.role}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="condition">{t('createListing.condition', 'Condition')} *</Label>
                  <select
                    id="condition"
                    name="condition"
                    value={formData.condition}
                    onChange={handleChange}
                    required
                    className="w-full px-3 py-2 border border-input rounded-md bg-background"
                    data-testid="condition-select"
                  >
                    <option value="new">{t('createListing.conditionNew', 'New')}</option>
                    <option value="like_new">{t('createListing.conditionLikeNew', 'Like New')}</option>
                    <option value="good">{t('createListing.conditionGood', 'Good')}</option>
                    <option value="fair">{t('createListing.conditionFair', 'Fair')}</option>
                    <option value="poor">{t('createListing.conditionPoor', 'Poor')}</option>
                  </select>
                </div>
              </div>

              {/* CFIA Soil Rule Banner — Section 4 */}
              {formData.category && CFIA_TRIGGER_CATEGORIES.some(c => formData.category.toLowerCase().includes(c.toLowerCase())) && (
                <div className="space-y-3">
                  <CFIASoilBanner />
                  <CFIASoilCheckbox checked={cfiaDeclaration} onChange={(e) => setCfiaDeclaration(e.target.checked)} />
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="starting_price">{t('createListing.startingPrice', 'Starting Price')} ({formData.currency}) *
                    <InfoTip en="Lower starting prices attract more bidders and often result in higher final prices." fr="Des prix de départ plus bas attirent plus d'enchérisseurs et mènent souvent à des prix finaux plus élevés." />
                  </Label>
                  <Input
                    id="starting_price"
                    name="starting_price"
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    min="0.01"
                    value={formData.starting_price}
                    onChange={handleChange}
                    required
                    className="min-h-[48px]"
                    data-testid="starting-price-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="buy_now_price">{t('createListing.buyNowPrice', 'Buy Now Price')} ({formData.currency})
                    <InfoTip en="Optional. Allows buyers to skip bidding and purchase instantly at this price." fr="Optionnel. Permet aux acheteurs de sauter l'enchère et d'acheter instantanément à ce prix." />
                  </Label>
                  <Input
                    id="buy_now_price"
                    name="buy_now_price"
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    min="0.01"
                    value={formData.buy_now_price}
                    onChange={handleChange}
                    className="min-h-[48px]"
                    data-testid="buy-now-price-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="buyers_premium_percent">{t('createListing.buyersPremium', "Buyer's Premium (%)")}
                  <InfoTip en="A fee added to the winning bid, paid by the buyer. Standard: 5%. This covers platform services." fr="Des frais ajoutés à l'enchère gagnante, payés par l'acheteur. Standard: 5%. Cela couvre les services de la plateforme." />
                </Label>
                {isPartner ? (
                  <>
                    <Input
                      id="buyers_premium_percent"
                      type="number"
                      step="0.5"
                      min="0"
                      max="25"
                      placeholder="0"
                      value={buyersPremiumPercent}
                      onChange={(e) => setBuyersPremiumPercent(e.target.value)}
                      data-testid="buyers-premium-input"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('createListing.buyersPremiumPartnerHelp')}
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground bg-slate-50 px-3 py-2 rounded" data-testid="bp-locked-notice">
                    {t('createListing.buyersPremiumLockedNotice')}
                  </p>
                )}
              </div>

              {/* Payment Method Selection */}
              <div className="space-y-3" data-testid="payment-method-section">
                <Label>{t('createListing.paymentMethodLabel')}
                  <InfoTip en={t('createListing.paymentMethodInfo', { lng: 'en' })} fr={t('createListing.paymentMethodInfo', { lng: 'fr' })} />
                </Label>
                <div className="grid grid-cols-1 gap-2">
                  <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${paymentMethod === 'stripe' ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}>
                    <input type="radio" name="payment_method" value="stripe" checked={paymentMethod === 'stripe'} onChange={(e) => setPaymentMethod(e.target.value)} className="text-blue-600" data-testid="payment-stripe" />
                    <div>
                      <span className="font-medium text-sm">{t('createListing.paymentMethodStripe')}</span>
                      <span className="ml-2 text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">{t('createListing.paymentMethodStripeBadge')}</span>
                      <p className="text-xs text-muted-foreground mt-0.5">{t('createListing.paymentMethodStripeHelp')}</p>
                    </div>
                  </label>
                  <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${paymentMethod === 'cash' ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}>
                    <input type="radio" name="payment_method" value="cash" checked={paymentMethod === 'cash'} onChange={(e) => setPaymentMethod(e.target.value)} data-testid="payment-cash" />
                    <span className="font-medium text-sm">{t('createListing.paymentMethodCash')}</span>
                  </label>
                  <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${paymentMethod === 'e-transfer' ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}>
                    <input type="radio" name="payment_method" value="e-transfer" checked={paymentMethod === 'e-transfer'} onChange={(e) => setPaymentMethod(e.target.value)} data-testid="payment-etransfer" />
                    <span className="font-medium text-sm">{t('createListing.paymentMethodETransfer')}</span>
                  </label>
                </div>
                {(paymentMethod === 'cash' || paymentMethod === 'e-transfer') && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-md" data-testid="payment-legal-notice">
                    <p className="text-sm text-amber-800 font-medium">{t('createListing.legalDisclosureTitle')}</p>
                    <p className="text-xs text-amber-700 mt-1">
                      {t('createListing.legalDisclosureCash', { currency: formData.currency })}
                    </p>
                  </div>
                )}
                {paymentMethod === 'stripe' && (
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-md" data-testid="payment-stripe-notice">
                    <p className="text-sm text-blue-800 font-medium">{t('createListing.stripeDisclosureTitle')}</p>
                    <p className="text-xs text-blue-700 mt-1">
                      {t('createListing.stripeDisclosureBody', { currency: formData.currency })}
                    </p>
                  </div>
                )}
              </div>

              {/* Deposit (Spec Feature 1) — single field, single flow */}
              <div className="space-y-3" data-testid="deposit-section">
                <Label>
                  {t('createListing.bidderDepositLabel')}
                  <InfoTip
                    en={t('createListing.bidderDepositInfo', { lng: 'en' })}
                    fr={t('createListing.bidderDepositInfo', { lng: 'fr' })}
                  />
                </Label>
                <div className="grid grid-cols-1 gap-2">
                  <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${!requiresDeposit ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}>
                    <input type="radio" name="deposit_required" checked={!requiresDeposit} onChange={() => setRequiresDeposit(false)} data-testid="deposit-none" />
                    <div>
                      <span className="font-medium text-sm">{t('createListing.bidderNoDeposit')}</span>
                      <p className="text-xs text-muted-foreground mt-0.5">{t('createListing.bidderNoDepositHelp')}</p>
                    </div>
                  </label>
                  <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${requiresDeposit ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}>
                    <input type="radio" name="deposit_required" checked={requiresDeposit} onChange={() => setRequiresDeposit(true)} data-testid="deposit-required" />
                    <div>
                      <span className="font-medium text-sm">{t('createListing.bidderRequireDeposit')}</span>
                      <p className="text-xs text-muted-foreground mt-0.5">{t('createListing.bidderRequireDepositHelp')}</p>
                    </div>
                  </label>
                </div>
                {requiresDeposit && (
                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-md space-y-3" data-testid="deposit-amount-block">
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setDepositType('fixed')} className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${depositType === 'fixed' ? 'bg-blue-600 text-white' : 'bg-white border border-slate-300 text-slate-700'}`} data-testid="deposit-type-fixed">{t('createListing.depositTypeFixed')}</button>
                      <button type="button" onClick={() => setDepositType('percentage')} className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${depositType === 'percentage' ? 'bg-blue-600 text-white' : 'bg-white border border-slate-300 text-slate-700'}`} data-testid="deposit-type-percentage">{t('createListing.depositTypePercent')}</button>
                    </div>
                    <div>
                      <Label htmlFor="deposit_amount">
                        {depositType === 'fixed'
                          ? t('createListing.depositLabelFixed', { currency: formData.currency })
                          : t('createListing.depositLabelPercent')}
                      </Label>
                      <Input id="deposit_amount" type="number" min="0" step={depositType === 'percentage' ? '1' : '0.01'} value={depositAmount} onChange={(e) => setDepositAmount(e.target.value)} placeholder={depositType === 'fixed' ? t('createListing.depositPlaceholderFixed') : t('createListing.depositPlaceholderPercent')} data-testid="deposit-amount-input" />
                      <p className="text-xs text-muted-foreground mt-1">
                        {depositType === 'fixed'
                          ? t('createListing.depositHelpFixed', { amount: depositAmount || 'X', currency: formData.currency })
                          : t('createListing.depositHelpPercent', { amount: depositAmount || 'X', currency: formData.currency })}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Final Listing Disclosure (Spec Feature 6) */}
              <div className="p-4 bg-slate-100 border border-slate-300 rounded-md text-xs leading-relaxed" data-testid="seller-final-disclosure">
                <p className="font-semibold text-slate-900 mb-1">{t('createListing.sellerDisclosureTitle')}</p>
                <p className="text-slate-700">
                  {t('createListing.sellerDisclosureBody', { currency: formData.currency })}
                </p>
              </div>

              <LocationSelector
                value={{
                  country: formData.country,
                  region: formData.region,
                  city: formData.city,
                  postalCode: formData.postal_code,
                }}
                geoSuggestion={geo}
                onChange={({ country, region, city, postalCode }) => {
                  const detectedCurrency = country === 'US' ? 'USD' : 'CAD';
                  setFormData(prev => ({
                    ...prev,
                    country,
                    region,
                    city,
                    postal_code: postalCode,
                    location: [city, region, postalCode].filter(Boolean).join(', '),
                    currency: detectedCurrency,
                  }));
                }}
              />

              {/* Currency Selector */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label>{t('currency.selector', 'Listing Currency')}</Label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <AlertTriangle className="h-4 w-4 text-amber-500 cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-xs text-sm">
                        <p className="font-semibold mb-1">{t('currency.warningTitle', 'Currency Notice')}</p>
                        <p>{t('currency.warningBody', 'Changing the currency will require all bidders to pay in this currency. This cannot be changed once the auction starts.')}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex gap-2" data-testid="currency-selector">
                  {['CAD', 'USD'].map((cur) => (
                    <button
                      key={cur}
                      type="button"
                      onClick={() => setFormData(prev => ({ ...prev, currency: cur }))}
                      className={`flex-1 py-2.5 px-4 rounded-lg border-2 text-sm font-semibold transition-all ${
                        formData.currency === cur
                          ? 'border-[#06B6D4] bg-[#06B6D4]/10 text-[#06B6D4]'
                          : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300'
                      }`}
                      data-testid={`currency-${cur.toLowerCase()}`}
                    >
                      {cur === 'CAD' ? '🇨🇦 CAD' : '🇺🇸 USD'}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-500">
                  {t('createListing.currencyImmutableWarn')}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="auction_end_date">{t('createListing.auctionEndDate', 'Auction End Date')} *
                  <InfoTip en="Auctions typically run 3-7 days. Shorter durations create urgency; longer ones reach more bidders." fr="Les enchères durent habituellement 3-7 jours. Des durées plus courtes créent l'urgence ; des plus longues atteignent plus d'enchérisseurs." />
                </Label>
                <Input
                  id="auction_end_date"
                  name="auction_end_date"
                  type="datetime-local"
                  value={formData.auction_end_date}
                  onChange={handleChange}
                  required
                  data-testid="end-date-input"
                />
              </div>

              <div className="space-y-2">
                <Label>{t('createListing.images', 'Images')}
                  <InfoTip en="Upload clear photos from multiple angles. First photo is the thumbnail. Max 10 images." fr="Téléversez des photos claires sous plusieurs angles. La première photo est la miniature. Max 10 images." />
                </Label>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageUpload}
                  className="hidden"
                  id="image-upload"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => document.getElementById('image-upload').click()}
                  className="w-full"
                  data-testid="add-image-btn"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  {t('createListing.uploadImages', 'Upload Images')}
                </Button>
                {formData.images.length > 0 && (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
                    {formData.images.map((img, index) => (
                      <div key={index} className="relative aspect-square rounded-lg overflow-hidden bg-gray-100">
                        <img src={img} alt={`Preview ${index + 1}`} className="w-full h-full object-cover" />
                        <button
                          type="button"
                          onClick={() => removeImage(index)}
                          className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Shipping Options Section */}
              <Card className="border-2">
                <CardHeader>
                  <CardTitle className="text-lg">{t('createListing.shipping', 'Shipping Options')}
                    <InfoTip en="Offering shipping options increases bids from distant buyers. Set clear rates for each method." fr="Offrir des options d'expédition augmente les enchères des acheteurs éloignés. Définissez des tarifs clairs pour chaque méthode." />
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="shipping-available"
                      checked={shippingInfo.available}
                      onChange={(e) => setShippingInfo(prev => ({ ...prev, available: e.target.checked }))}
                      className="w-4 h-4"
                    />
                    <Label htmlFor="shipping-available">{t('createListing.offerShipping', 'Offer Shipping?')}</Label>
                  </div>

                  {shippingInfo.available && (
                    <div className="space-y-4 ml-6 p-4 border rounded-lg bg-muted/20">
                      <div>
                        <Label>{t('createListing.shippingMethods', 'Shipping Methods')}</Label>
                        <div className="space-y-2 mt-2">
                          {['local_pickup', 'standard', 'express'].map(method => (
                            <div key={method} className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                id={`shipping-${method}`}
                                checked={shippingInfo.methods.includes(method)}
                                onChange={(e) => {
                                  setShippingInfo(prev => ({
                                    ...prev,
                                    methods: e.target.checked
                                      ? [...prev.methods, method]
                                      : prev.methods.filter(m => m !== method)
                                  }));
                                }}
                                className="w-4 h-4"
                              />
                              <Label htmlFor={`shipping-${method}`} className="capitalize">
                                {method.replace('_', ' ')}
                              </Label>
                              {shippingInfo.methods.includes(method) && (
                                <Input
                                  type="number"
                                  placeholder="Rate ($)"
                                  value={shippingInfo.rates[method] || ''}
                                  onChange={(e) => setShippingInfo(prev => ({
                                    ...prev,
                                    rates: { ...prev.rates, [method]: e.target.value }
                                  }))}
                                  className="w-24"
                                />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <Label>{t('createListing.deliveryTime', 'Estimated Delivery Time')}</Label>
                        <Input
                          placeholder={t('createListing.deliveryTimePlaceholder', 'e.g., 3-5 business days')}
                          value={shippingInfo.delivery_time}
                          onChange={(e) => setShippingInfo(prev => ({ ...prev, delivery_time: e.target.value }))}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Visit Availability Section */}
              <Card className="border-2">
                <CardHeader>
                  <CardTitle className="text-lg">{t('createListing.visitBeforePurchase', 'Visit Before Purchase')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="visit-offered"
                      checked={visitAvailability.offered}
                      onChange={(e) => setVisitAvailability(prev => ({ ...prev, offered: e.target.checked }))}
                      className="w-4 h-4"
                    />
                    <Label htmlFor="visit-offered">{t('createListing.allowVisit', 'Allow buyers to schedule a visit?')}</Label>
                  </div>

                  {visitAvailability.offered && (
                    <div className="space-y-4 ml-6 p-4 border rounded-lg bg-green-50 dark:bg-green-900/10">
                      <div>
                        <Label>{t('createListing.availableDates', 'Available Dates')}</Label>
                        <Input
                          placeholder="e.g., Nov 15-20, 2025"
                          value={visitAvailability.dates}
                          onChange={(e) => setVisitAvailability(prev => ({ ...prev, dates: e.target.value }))}
                        />
                      </div>

                      <div>
                        <Label>{t('createListing.visitInstructions', 'Instructions')}</Label>
                        <Textarea
                          placeholder={t('createListing.visitInstructionsPlaceholder', 'Provide instructions for scheduling (e.g., contact info, time slots)')}
                          value={visitAvailability.instructions}
                          onChange={(e) => setVisitAvailability(prev => ({ ...prev, instructions: e.target.value }))}
                          rows={3}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Final Seller Agreement - Mandatory Legal Checkbox */}
              <div className="p-6 border-2 border-blue-600 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    id="finalAgreement"
                    checked={finalAgreementAccepted}
                    onChange={(e) => setFinalAgreementAccepted(e.target.checked)}
                    className="mt-1 w-5 h-5 accent-blue-600 cursor-pointer"
                  />
                  <label htmlFor="finalAgreement" className="text-sm leading-relaxed cursor-pointer text-slate-900 dark:text-slate-100">
                    <strong className="text-blue-900 dark:text-blue-300">{t('createListing.bindingAgreement', 'Binding Agreement to Sell')}:</strong>
                    <p className="mt-2">
                      {t('createListing.agreementText', 'I hereby certify that I am the legal owner or authorized agent of these items. I agree to sell the items to the highest bidder at the conclusion of the auction, regardless of the final price. I acknowledge that failing to honor a winning bid may result in account suspension and legal liability.')}
                    </p>
                  </label>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full gradient-button text-white border-0 min-h-[48px] text-base"
                disabled={loading || !finalAgreementAccepted}
                data-testid="submit-listing-btn"
              >
                {loading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> {t('createListing.creating', 'Creating...')}</>
                ) : (
                  t('createListing.submitListing', 'Create Listing')
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* Iter187: CRA Tax Declaration mounted as overlay AFTER form mount.
          Form testids remain reachable; user is blocked from submitting until completed. */}
      {taxOnboardingPending && (
        <TaxInterviewModal
          user={user}
          onComplete={() => window.location.reload()}
          onCancel={() => navigate('/seller/dashboard')}
        />
      )}
    </div>
  );
};

export default CreateListingPage;
