import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { extractErrorMessage } from '../utils/errorHandler';
import TaxInterviewModal from '../components/TaxInterviewModal';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import { Loader2, Upload, AlertTriangle, ShieldAlert, ExternalLink, Search } from 'lucide-react';
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
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
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
  // Phase 6.0 hotfix — Admin / superadmin bypass for storage validation
  const isAdminUser = user?.role === 'admin' || user?.role === 'superadmin' || user?.is_admin === true;
  // Phase 6.2 hotfix — Approved storage facilities can list units; everyone
  // else is gated (backend returns 403 on submit). Used to (a) auto-toggle
  // the storage_locker card when the URL specifies `?type=storage_locker`
  // and (b) surface an upfront warning to non-facility users.
  const isFacilityOrAdmin = isAdminUser || !!(
    user && (
      user.storage_facility_approved === true
      || user.account_type === 'storage_facility'
      || user.is_storage_facility === true
    )
  );

  // Seller Payment Method
  const [paymentMethod, setPaymentMethod] = useState('stripe');

  // Deposit (Spec Feature 1) — single field, single flow
  const [requiresDeposit, setRequiresDeposit] = useState(false);
  const [depositType, setDepositType] = useState('fixed'); // 'fixed' | 'percentage'
  const [depositAmount, setDepositAmount] = useState('');

  // FEATURE PATCH v9 / Feature 4 — Quantity & per-unit hammer multiplier
  const [quantity, setQuantity] = useState(1);
  const [multiplyHammerByQuantity, setMultiplyHammerByQuantity] = useState(false);

  // Phase 6.0 / Task 4 — Storage Locker / Abandoned Unit
  const [isStorageLocker, setIsStorageLocker] = useState(false);
  const [storageMetadata, setStorageMetadata] = useState({
    facility_name: '',
    facility_address: '',
    locker_size: '',
    locker_number: '',
    cleanout_deadline_hours: 72,
    security_deposit_amount: 100,
    security_deposit_preset: '100',   // UI helper: '100' | '250' | 'custom'
    facility_manager_email: '',
    facility_manager_phone: '',
    notes: '',
  });
  // iter219 — Visible Content Tags (optional bilingual checkbox cluster).
  // Canonical EN slugs stored in DB; bilingual labels rendered in the UI.
  const [visibleContentTags, setVisibleContentTags] = useState([]);

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

  // iter207 — Vehicle compliance warning dialog (replaces narrow top-right toast)
  const [vehicleComplianceOpen, setVehicleComplianceOpen] = useState(false);
  const [vehicleComplianceSignals, setVehicleComplianceSignals] = useState([]);
  // Phase 6.0 hotfix — Manual Review request state inside the vehicle-block modal
  const [vehicleComplianceReviewRequested, setVehicleComplianceReviewRequested] = useState(false);
  const [vehicleComplianceReviewSubmitting, setVehicleComplianceReviewSubmitting] = useState(false);

  // FEATURE PATCH v9 / Feature 3 — AI category mismatch warning popup
  const [aiMismatchModal, setAiMismatchModal] = useState({ open: false, suggested: '', reasonEn: '', reasonFr: '', confidence: 0 });
  const [pendingPayload, setPendingPayload] = useState(null);

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

  // Phase 6.2 hotfix — Auto-toggle the storage_locker card when the URL
  // includes ?type=storage_locker (used by the new Navbar / Footer / Hero
  // facility CTAs). Only triggers for facility/admin users.
  useEffect(() => {
    if (searchParams.get('type') === 'storage_locker' && isFacilityOrAdmin) {
      setIsStorageLocker(true);
    }
  }, [searchParams, isFacilityOrAdmin]);

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

  const submitListingPayload = async (payload) => {
    try {
      const response = await axios.post(`${API}/listings`, payload);
      toast.success('Listing created successfully!');
      navigate(`/listing/${response.data.id}`);
      return response.data;
    } catch (error) {
      console.error('Failed to create listing:', error);
      const detail = error?.response?.data?.detail;
      if (detail && typeof detail === 'object' && detail.error === 'vehicle_listing_dealer_required') {
        setVehicleComplianceSignals(Array.isArray(detail.signals) ? detail.signals : []);
        setVehicleComplianceReviewRequested(false);
        setVehicleComplianceReviewSubmitting(false);
        setVehicleComplianceOpen(true);
        return null;
      }
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Failed to create listing');
      return null;
    }
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
        // iter219 — Storage Locker auctions don't support instant Buy Now
        // (abandoned-property auctions are open-ended bidding only).
        buy_now_price: isStorageLocker
          ? null
          : (formData.buy_now_price ? parseFloat(formData.buy_now_price) : null),
        auction_end_date: new Date(formData.auction_end_date).toISOString(),
        // Phase 6.3 Task 2 — Storage locker sanitization. Strip retail
        // marketplace fields that are hidden in the UI so the payload stays
        // clean and matches the backend's defensive normalization.
        shipping_info: !isStorageLocker && shippingInfo.available ? shippingInfo : null,
        visit_availability: !isStorageLocker && visitAvailability.offered ? visitAvailability : null,
        condition: isStorageLocker ? 'as_is' : formData.condition,
        quantity: isStorageLocker ? 1 : Math.max(1, parseInt(quantity) || 1),
        multiply_hammer_by_quantity: !isStorageLocker
          && (Math.max(1, parseInt(quantity) || 1) > 1)
          && !!multiplyHammerByQuantity,
        // Convert percent → rate (e.g. 15 → 0.15), null if blank (org default applies server-side)
        buyers_premium_rate: buyersPremiumPercent !== '' ? parseFloat(buyersPremiumPercent) / 100 : null,
        payment_method: paymentMethod,
        // Deposit (spec Feature 1) — disabled for storage_locker (native pre-auth holds replace this)
        requires_deposit: !isStorageLocker && requiresDeposit,
        deposit_amount: !isStorageLocker && requiresDeposit && depositAmount ? parseFloat(depositAmount) : null,
        deposit_type: !isStorageLocker && requiresDeposit ? depositType : null,
        // FEATURE PATCH v9 / Feature 4 — Quantity (forced to 1 for storage_locker)
        quantity: isStorageLocker ? 1 : Math.max(1, parseInt(quantity) || 1),
        multiply_hammer_by_quantity: !isStorageLocker
          && (Math.max(1, parseInt(quantity) || 1) > 1)
          && !!multiplyHammerByQuantity,
        // Phase 6.0 / Task 4 — Storage Locker
        listing_type: isStorageLocker ? 'storage_locker' : null,
        storage_metadata: isStorageLocker ? {
          facility_name:           storageMetadata.facility_name.trim(),
          facility_address:        storageMetadata.facility_address.trim(),
          locker_size:             storageMetadata.locker_size.trim(),
          locker_number:           storageMetadata.locker_number.trim(),
          cleanout_deadline_hours: parseInt(storageMetadata.cleanout_deadline_hours) || 72,
          security_deposit_amount: parseFloat(storageMetadata.security_deposit_amount) || 100,
          facility_manager_email:  storageMetadata.facility_manager_email.trim(),
          facility_manager_phone:  storageMetadata.facility_manager_phone.trim(),
          notes:                   storageMetadata.notes.trim(),
        } : null,
        // iter219 — Storage Locker forces category="storage_locker" (no
        // retail picker shown to facility operators). For non-storage flows
        // the user's selected category is preserved as-is.
        category: isStorageLocker ? 'storage_locker' : formData.category,
        // iter219 — Visible Content Tags (canonical EN slugs). Stays empty
        // when the facility couldn't see inside the unit. Always sent so
        // the backend can clear any legacy values on edit.
        visible_content_tags: isStorageLocker ? visibleContentTags : [],
        // Mandatory Binding Agreement
        agreement_accepted: finalAgreementAccepted,
      };

      // FEATURE PATCH v9 / Feature 3 — Pre-publish AI category mismatch check.
      // iter219 — Skip for storage_locker auctions (no retail category to
      // mismatch against; category is force-set to "storage_locker").
      if (!isStorageLocker) {
        try {
          const sg = await axios.post(`${API}/listings/suggest-category`, {
            title: payload.title || '',
            description: payload.description || '',
            seller_category: payload.category || '',
          });
          if (sg.data && sg.data.match === false && sg.data.suggested_category) {
            setPendingPayload(payload);
            setAiMismatchModal({
              open: true,
              suggested: sg.data.suggested_category,
              reasonEn: sg.data.reason_en || '',
              reasonFr: sg.data.reason_fr || '',
              confidence: sg.data.confidence || 0,
            });
            setLoading(false);
            return;
          }
        } catch (_) { /* fail-open */ }
      }

      await submitListingPayload(payload);
    } catch (error) {
      console.error('Failed to create listing:', error);
      toast.error('Failed to create listing');
    } finally {
      setLoading(false);
    }
  };

  // FEATURE PATCH v9 / Feature 3 — Seller chooses to keep their category despite warning
  const handleAiMismatchAcknowledge = async () => {
    if (!pendingPayload) {
      setAiMismatchModal({ open: false, suggested: '', reasonEn: '', reasonFr: '', confidence: 0 });
      return;
    }
    setLoading(true);
    try {
      const created = await submitListingPayload(pendingPayload);
      if (created?.id) {
        // Flag for AI review (will move listing to pending_ai_review)
        try {
          await axios.post(`${API}/listings/${created.id}/flag-for-ai-review`, {
            seller_category: pendingPayload.category,
            suggested_category: aiMismatchModal.suggested,
            ai_confidence: aiMismatchModal.confidence,
            ai_reason_en: aiMismatchModal.reasonEn,
            ai_reason_fr: aiMismatchModal.reasonFr,
            listing_type: 'single',
          });
          toast.warning('Listing submitted — pending AI category review by admin.');
        } catch (e) {
          console.error('Failed to flag for review:', e);
        }
      }
    } finally {
      setLoading(false);
      setAiMismatchModal({ open: false, suggested: '', reasonEn: '', reasonFr: '', confidence: 0 });
      setPendingPayload(null);
    }
  };

  const handleAiMismatchCorrect = () => {
    // User wants to fix the category — switch to suggested
    if (aiMismatchModal.suggested) {
      setFormData((prev) => ({ ...prev, category: aiMismatchModal.suggested }));
      toast.info(`Category updated to "${aiMismatchModal.suggested}". You can submit again.`);
    }
    setAiMismatchModal({ open: false, suggested: '', reasonEn: '', reasonFr: '', confidence: 0 });
    setPendingPayload(null);
  };

  // Phase 6.0 hotfix — POST /listings/request-manual-vehicle-review when the
  // user clicks the new "Request Manual Review" button inside the vehicle-block
  // modal. The listing has NOT been created yet at this point, so we send the
  // form snapshot + detected signals so an admin can override the block.
  const handleRequestManualVehicleReview = async () => {
    if (vehicleComplianceReviewRequested || vehicleComplianceReviewSubmitting) return;
    setVehicleComplianceReviewSubmitting(true);
    try {
      await axios.post(`${API}/listings/request-manual-vehicle-review`, {
        title:            formData.title || '',
        description:      formData.description || '',
        category:         formData.category || '',
        detected_signals: vehicleComplianceSignals,
        images:           Array.isArray(formData.images) ? formData.images : [],
        images_count:     Array.isArray(formData.images) ? formData.images.length : 0,
        starting_price:   parseFloat(formData.starting_price) || 0,
        listing_id:       formData.id || null,
      });
      setVehicleComplianceReviewRequested(true);
    } catch (e) {
      const errorMessage = extractErrorMessage(e);
      toast.error(errorMessage || 'Failed to submit manual review request');
    } finally {
      setVehicleComplianceReviewSubmitting(false);
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
                {/* iter219 — Storage Locker auctions don't use retail
                    categories. The category is forced to "storage_locker"
                    server-side; this dropdown is hidden so facility operators
                    are never prompted to pick a niche. */}
                {!isStorageLocker && (
                  <div className="space-y-2" data-testid="category-section">
                    <CategorySelector
                      value={formData.category}
                      onChange={(val) => setFormData(prev => ({ ...prev, category: val }))}
                      required
                      filterVehicles
                      userRole={user?.role}
                    />
                  </div>
                )}

                {/* Phase 6.3 Task 2 — Condition is irrelevant for storage
                    locker auctions (abandoned property lots are sold as-is). */}
                {!isStorageLocker && (
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
                )}
              </div>

              {/* Phase 6.0 / Task 4 — Storage Locker / Abandoned Unit category card */}
              <div
                className={`rounded-lg border p-4 cursor-pointer transition-all ${isStorageLocker ? 'border-amber-500 bg-amber-50' : 'border-slate-200 hover:border-slate-300 bg-white'}`}
                onClick={() => setIsStorageLocker((v) => !v)}
                data-testid="storage-locker-toggle-card"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setIsStorageLocker((v) => !v)}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={isStorageLocker}
                    readOnly
                    className="mt-1 w-4 h-4 accent-amber-600 pointer-events-none"
                    data-testid="storage-locker-checkbox"
                  />
                  <div className="flex-1">
                    <p className="font-semibold text-sm">
                      📦 {t('createListing.storageLockerLabel', 'Storage Locker / Abandoned Unit')}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {t('createListing.storageLockerHelp', 'For self-storage facility cleanout auctions — the entire unit sells as one lot. Buyer must clear all contents within the cleanout deadline.')}
                    </p>
                  </div>
                </div>
              </div>

              {isStorageLocker && (
                <div className="space-y-4 rounded-lg border border-amber-200 bg-amber-50/30 p-4" data-testid="storage-metadata-panel">
                  <div className="flex items-start gap-2 rounded-md bg-amber-100 border border-amber-300 p-3 text-xs text-amber-900">
                    <span className="text-base leading-none">⚠️</span>
                    <p data-testid="storage-locker-warning">
                      <strong>{t('createListing.storageWarningTitle', 'Important — Cleanout Obligation')}.</strong>{' '}
                      {t('createListing.storageWarningBody', 'Buyers are legally required to clear the entire contents of the unit within the specified deadline. The cleanout security deposit is held securely until facility manager verification.')}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="facility_name">{t('createListing.facilityName', 'Facility Name')} *</Label>
                      <Input
                        id="facility_name"
                        type="text"
                        value={storageMetadata.facility_name}
                        onChange={(e) => setStorageMetadata((m) => ({ ...m, facility_name: e.target.value }))}
                        required={isStorageLocker && !isAdminUser}
                        maxLength={200}
                        data-testid="facility-name-input"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="facility_address">{t('createListing.facilityAddress', 'Facility Address')}</Label>
                      <Input
                        id="facility_address"
                        type="text"
                        value={storageMetadata.facility_address}
                        onChange={(e) => setStorageMetadata((m) => ({ ...m, facility_address: e.target.value }))}
                        maxLength={300}
                        data-testid="facility-address-input"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="locker_size">{t('createListing.lockerSize', 'Locker Size')}</Label>
                      <Input
                        id="locker_size"
                        type="text"
                        placeholder="10x10, 5x10, etc."
                        value={storageMetadata.locker_size}
                        onChange={(e) => setStorageMetadata((m) => ({ ...m, locker_size: e.target.value }))}
                        maxLength={30}
                        data-testid="locker-size-input"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="locker_number">{t('createListing.lockerNumber', 'Locker Number')}</Label>
                      <Input
                        id="locker_number"
                        type="text"
                        value={storageMetadata.locker_number}
                        onChange={(e) => setStorageMetadata((m) => ({ ...m, locker_number: e.target.value }))}
                        maxLength={30}
                        data-testid="locker-number-input"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="cleanout_deadline_hours">{t('createListing.cleanoutDeadline', 'Cleanout Deadline')} *</Label>
                    <select
                      id="cleanout_deadline_hours"
                      value={storageMetadata.cleanout_deadline_hours}
                      onChange={(e) => setStorageMetadata((m) => ({ ...m, cleanout_deadline_hours: parseInt(e.target.value) }))}
                      className="w-full px-3 py-2 border border-input rounded-md bg-background"
                      data-testid="cleanout-deadline-select"
                    >
                      <option value={24}>24 hours / heures</option>
                      <option value={48}>48 hours / heures</option>
                      <option value={72}>72 hours / heures (recommended)</option>
                      <option value={168}>1 week / 1 semaine</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="security_deposit_preset">{t('createListing.securityDeposit', 'Security Deposit Hold (CAD)')} *</Label>
                    <div className="grid grid-cols-3 gap-2" data-testid="security-deposit-presets">
                      {[
                        { id: '100',     label: '$100',  amount: 100 },
                        { id: '250',     label: '$250',  amount: 250 },
                        { id: 'custom',  label: t('createListing.depositCustom', 'Custom'), amount: storageMetadata.security_deposit_amount },
                      ].map((preset) => (
                        <Button
                          key={preset.id}
                          type="button"
                          variant={storageMetadata.security_deposit_preset === preset.id ? 'default' : 'outline'}
                          className={storageMetadata.security_deposit_preset === preset.id ? 'bg-amber-600 hover:bg-amber-700 text-white border-0' : ''}
                          onClick={() => setStorageMetadata((m) => ({
                            ...m,
                            security_deposit_preset: preset.id,
                            security_deposit_amount: preset.id === 'custom' ? m.security_deposit_amount : preset.amount,
                          }))}
                          data-testid={`deposit-preset-${preset.id}`}
                        >
                          {preset.label}
                        </Button>
                      ))}
                    </div>
                    {storageMetadata.security_deposit_preset === 'custom' && (
                      <Input
                        type="number"
                        min={50}
                        max={5000}
                        step={5}
                        value={storageMetadata.security_deposit_amount}
                        onChange={(e) => setStorageMetadata((m) => ({ ...m, security_deposit_amount: parseFloat(e.target.value) || 100 }))}
                        className="mt-2"
                        data-testid="deposit-custom-input"
                        placeholder="Custom amount (50–5000 CAD)"
                      />
                    )}
                    <p className="text-[11px] text-muted-foreground mt-1">
                      {t('createListing.depositHelp', 'Held via Stripe authorization (capture_method=manual). Released or captured by facility manager after cleanout verification.')}
                    </p>
                  </div>

                  {/* iter219 — Visible Content Tags (optional bilingual cluster).
                      Facility manager can skip entirely if they only cut a lock
                      and see closed boxes. Tags drive buyer keyword search on
                      /storage-auctions. */}
                  <div className="space-y-2" data-testid="visible-content-tags-section">
                    <Label>
                      {t('createListing.visibleContentsTitle', 'Visible Contents / Contenu visible')}{' '}
                      <span className="text-xs font-normal text-muted-foreground">
                        ({t('createListing.optionalLabel', 'Optional / Optionnel')})
                      </span>
                    </Label>
                    <p className="text-[11px] text-muted-foreground">
                      {t(
                        'createListing.visibleContentsHelp',
                        "Tag what you can see inside the unit so buyers can search by keyword. Skip if you can only see closed boxes — listing publishes fine without any tag.",
                      )}
                    </p>
                    <div
                      className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2"
                      data-testid="visible-content-tags-grid"
                    >
                      {[
                        { slug: 'boxes',          en: 'Boxes',          fr: 'Boîtes' },
                        { slug: 'tools',          en: 'Tools',          fr: 'Outils' },
                        { slug: 'furniture',      en: 'Furniture',      fr: 'Meubles' },
                        { slug: 'electronics',    en: 'Electronics',    fr: 'Électronique' },
                        { slug: 'sporting_goods', en: 'Sporting Goods', fr: 'Articles de sport' },
                        { slug: 'appliances',     en: 'Appliances',     fr: 'Électroménagers' },
                        { slug: 'miscellaneous',  en: 'Miscellaneous',  fr: 'Divers' },
                      ].map((tag) => {
                        const checked = visibleContentTags.includes(tag.slug);
                        return (
                          <label
                            key={tag.slug}
                            className={`flex items-center gap-2 rounded-md border px-3 py-2 cursor-pointer transition-colors ${
                              checked
                                ? 'border-amber-500 bg-amber-100/60'
                                : 'border-slate-200 bg-white hover:border-amber-300'
                            }`}
                            data-testid={`tag-pill-${tag.slug}`}
                          >
                            <input
                              type="checkbox"
                              className="accent-amber-600"
                              checked={checked}
                              onChange={(e) => {
                                setVisibleContentTags((prev) =>
                                  e.target.checked
                                    ? [...prev, tag.slug]
                                    : prev.filter((s) => s !== tag.slug),
                                );
                              }}
                              data-testid={`tag-checkbox-${tag.slug}`}
                            />
                            <span className="text-xs font-medium">
                              {tag.en} / {tag.fr}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

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

                {/* iter219 — Buy Now Price hidden for storage_locker.
                    Storage auctions are open-ended bidding only (no instant
                    purchase), aligning with abandoned-property auction norms. */}
                {!isStorageLocker && (
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
                )}
              </div>

              {/* FEATURE PATCH v9 / Feature 4 — Quantity field with optional "multiply hammer by quantity" toggle.
                  Phase 6.3 Task 2 — Hidden for storage_locker (each unit IS the whole lot). */}
              {!isStorageLocker && (
              <div className="space-y-2" data-testid="quantity-section">
                <Label htmlFor="quantity">{t('createListing.quantity', 'Quantity')}
                  <InfoTip
                    en="Number of identical units in this listing. If you set this above 1 you can choose whether the winning hammer price applies per unit or to the whole lot."
                    fr="Nombre d'unités identiques dans cette annonce. Si vous indiquez plus de 1, vous pouvez choisir si le prix marteau gagnant s'applique par unité ou à l'ensemble du lot."
                  />
                </Label>
                <Input
                  id="quantity"
                  type="number"
                  min="1"
                  step="1"
                  inputMode="numeric"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="min-h-[48px]"
                  data-testid="quantity-input"
                />
                {parseInt(quantity) > 1 && (
                  <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${multiplyHammerByQuantity ? 'border-cyan-500 bg-cyan-50' : 'border-slate-200 hover:border-slate-300'}`}>
                    <input
                      type="checkbox"
                      checked={multiplyHammerByQuantity}
                      onChange={(e) => setMultiplyHammerByQuantity(e.target.checked)}
                      className="mt-0.5 w-4 h-4 accent-cyan-600 cursor-pointer"
                      data-testid="multiply-hammer-toggle"
                    />
                    <div>
                      <span className="font-medium text-sm">{t('createListing.multiplyHammerLabel', 'Multiply hammer price by quantity')}</span>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {t('createListing.multiplyHammerHelp', 'When enabled, the winning bid is treated as a per-unit price. All platform & broker fees calculate against the full base amount (hammer × quantity).')}
                      </p>
                    </div>
                  </label>
                )}
              </div>
              )}

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

              {/* Deposit (Spec Feature 1) — single field, single flow.
                  Phase 6.3 Task 2 — Hidden for storage_locker (replaced by the
                  centralized storage auction pre-auth hold system). */}
              {!isStorageLocker && (
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
              )}

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

              {/* Shipping Options Section.
                  Phase 6.3 Task 2 — Hidden for storage_locker (buyer must
                  collect from the facility's physical address). */}
              {!isStorageLocker && (
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
              )}

              {/* Visit Availability Section.
                  Phase 6.3 Task 2 — Hidden for storage_locker (cleanout windows
                  are governed by the facility-managed pickup schedule). */}
              {!isStorageLocker && (
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
              )}

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

      {/* iter207 — Vehicle compliance warning dialog (replaces collapsed top-right toast) */}
      <Dialog open={vehicleComplianceOpen} onOpenChange={setVehicleComplianceOpen}>
        <DialogContent
          data-testid="vehicle-compliance-dialog"
          className="sm:max-w-2xl border-rose-200"
        >
          <DialogHeader>
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 mb-2">
              <ShieldAlert className="h-6 w-6 text-rose-600" />
            </div>
            <DialogTitle
              data-testid="vehicle-compliance-dialog-title"
              className="text-center text-xl font-semibold text-slate-900"
            >
              {(i18n.language || 'en').toLowerCase().startsWith('fr')
                ? 'Annonce de véhicule refusée'
                : 'Vehicle listing not allowed'}
            </DialogTitle>
            <DialogDescription
              data-testid="vehicle-compliance-dialog-body"
              className="text-center text-sm leading-relaxed text-slate-600 pt-2"
            >
              {(i18n.language || 'en').toLowerCase().startsWith('fr') ? (
                <>
                  Les annonces de véhicules sont réservées aux concessionnaires licenciés.
                  Veuillez faire vérifier votre licence par votre organisme provincial
                  (OMVIC, AMVIC, VSA, SAAQ, FCAA, etc.) avant de publier des véhicules,
                  ou continuez dans la section <strong>Enchères de véhicules</strong>.
                </>
              ) : (
                <>
                  Vehicle listings are restricted to licensed dealers only.
                  Please get your provincial dealer licence verified
                  (OMVIC, AMVIC, VSA, SAAQ, FCAA, etc.) before posting vehicles,
                  or browse the <strong>Vehicle Auctions</strong> section instead.
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          {vehicleComplianceSignals.length > 0 && (
            <div
              data-testid="vehicle-compliance-signals"
              className="mt-2 rounded-md bg-slate-50 border border-slate-200 px-3 py-2"
            >
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">
                {(i18n.language || 'en').toLowerCase().startsWith('fr')
                  ? 'Signaux détectés'
                  : 'Detected signals'}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {vehicleComplianceSignals.map((sig, i) => (
                  <span
                    key={i}
                    className="font-mono text-[11px] bg-white border border-slate-200 rounded px-2 py-0.5 text-slate-700"
                  >
                    {sig}
                  </span>
                ))}
              </div>
            </div>
          )}

          <DialogFooter
            data-testid="vehicle-compliance-footer"
            className="mt-4 flex flex-col sm:flex-row sm:flex-wrap sm:items-stretch sm:justify-center gap-3 py-2"
          >
            {vehicleComplianceReviewRequested ? (
              <div
                data-testid="vehicle-compliance-review-submitted"
                className="w-full rounded-lg border border-slate-200 bg-slate-50 text-center"
                style={{ padding: '24px' }}
              >
                <p className="text-base font-semibold text-emerald-900 mb-2">
                  ✅ {(i18n.language || 'en').toLowerCase().startsWith('fr')
                      ? 'Demande de révision soumise'
                      : 'Review Request Submitted'}
                </p>
                <p className="text-sm text-slate-700 leading-relaxed max-w-md mx-auto">
                  {(i18n.language || 'en').toLowerCase().startsWith('fr') ? (
                    <>
                      Notre équipe vérifiera manuellement cette annonce dans 5 à 50 minutes.
                      Vous recevrez un courriel et une notification système instantanée dès l'approbation.
                    </>
                  ) : (
                    <>
                      Our team will manually verify this listing within 5 to 50 minutes.
                      You will receive an instant email and system notification once approved.
                    </>
                  )}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => setVehicleComplianceOpen(false)}
                  data-testid="vehicle-compliance-review-close-btn"
                >
                  {(i18n.language || 'en').toLowerCase().startsWith('fr') ? 'Fermer' : 'Close'}
                </Button>
              </div>
            ) : (
              <>
                <Button
                  variant="outline"
                  data-testid="vehicle-compliance-secondary-btn"
                  onClick={() => {
                    setVehicleComplianceOpen(false);
                    navigate('/vehicle-auctions');
                  }}
                  className="flex-1 sm:flex-none sm:min-w-[180px] whitespace-nowrap h-11"
                >
                  <ExternalLink className="mr-2 h-4 w-4 flex-shrink-0" />
                  <span className="truncate">
                    {(i18n.language || 'en').toLowerCase().startsWith('fr')
                      ? 'Enchères de véhicules'
                      : 'Go to Vehicle Auctions'}
                  </span>
                </Button>
                <Button
                  data-testid="vehicle-compliance-primary-btn"
                  onClick={() => {
                    setVehicleComplianceOpen(false);
                    navigate('/vehicle-auctions/dealer-license');
                  }}
                  className="flex-1 sm:flex-none sm:min-w-[180px] whitespace-nowrap h-11 bg-rose-600 hover:bg-rose-700 text-white"
                >
                  <span className="truncate">
                    {(i18n.language || 'en').toLowerCase().startsWith('fr')
                      ? 'Vérifier ma licence'
                      : 'Verify dealer licence'}
                  </span>
                </Button>
                <Button
                  variant="outline"
                  data-testid="vehicle-compliance-manual-review-btn"
                  onClick={handleRequestManualVehicleReview}
                  disabled={vehicleComplianceReviewSubmitting}
                  className="flex-1 sm:flex-none sm:min-w-[180px] whitespace-nowrap h-11 border-amber-400 bg-amber-50 text-amber-900 hover:bg-amber-100 hover:border-amber-500 disabled:opacity-60"
                  style={{ paddingLeft: 20, paddingRight: 20 }}
                >
                  <Search className="mr-2 h-4 w-4 flex-shrink-0" />
                  <span className="truncate">
                    {vehicleComplianceReviewSubmitting
                      ? ((i18n.language || 'en').toLowerCase().startsWith('fr') ? 'Envoi…' : 'Sending…')
                      : ((i18n.language || 'en').toLowerCase().startsWith('fr')
                          ? 'Révision manuelle'
                          : 'Request Manual Review')}
                  </span>
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* FEATURE PATCH v9 / Feature 3 — AI category mismatch popup */}
      <Dialog open={aiMismatchModal.open} onOpenChange={(v) => !v && handleAiMismatchCorrect()}>
        <DialogContent className="sm:max-w-lg border-amber-200" data-testid="ai-mismatch-dialog">
          <DialogHeader>
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 mb-2">
              <ShieldAlert className="h-6 w-6 text-amber-600" />
            </div>
            <DialogTitle className="text-center text-xl font-semibold text-slate-900" data-testid="ai-mismatch-title">
              {(i18n.language || 'en').toLowerCase().startsWith('fr')
                ? 'Catégorie possiblement incorrecte'
                : 'Possible category mismatch'}
            </DialogTitle>
            <DialogDescription className="text-center text-sm leading-relaxed text-slate-600 pt-2" data-testid="ai-mismatch-body">
              {(i18n.language || 'en').toLowerCase().startsWith('fr')
                ? (aiMismatchModal.reasonFr || aiMismatchModal.reasonEn || 'Notre système IA pense que votre annonce devrait se trouver dans une autre catégorie.')
                : (aiMismatchModal.reasonEn || aiMismatchModal.reasonFr || 'Our AI system thinks your listing belongs in a different category.')
              }
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2 rounded-md border border-amber-200 bg-amber-50/60 p-3">
            <div className="flex items-center justify-between text-sm gap-2 flex-wrap">
              <span>{(i18n.language || 'en').toLowerCase().startsWith('fr') ? 'Votre catégorie' : 'Your category'}</span>
              <span className="font-medium">{formData.category || '—'}</span>
            </div>
            <div className="flex items-center justify-between text-sm gap-2 mt-2 flex-wrap">
              <span>{(i18n.language || 'en').toLowerCase().startsWith('fr') ? 'Suggestion IA' : 'AI suggestion'}</span>
              <span className="font-semibold text-amber-900">{aiMismatchModal.suggested || '—'}</span>
            </div>
            {aiMismatchModal.confidence ? (
              <div className="text-[11px] text-amber-700 mt-1">
                {(i18n.language || 'en').toLowerCase().startsWith('fr') ? 'Confiance' : 'Confidence'}: {Math.round((aiMismatchModal.confidence || 0) * 100)}%
              </div>
            ) : null}
          </div>
          <DialogFooter className="flex-col sm:flex-row sm:justify-between gap-2 mt-4">
            <Button
              variant="outline"
              onClick={handleAiMismatchCorrect}
              className="w-full sm:w-auto"
              data-testid="ai-mismatch-correct-btn"
            >
              {(i18n.language || 'en').toLowerCase().startsWith('fr')
                ? `Utiliser « ${aiMismatchModal.suggested} »`
                : `Use "${aiMismatchModal.suggested}"`}
            </Button>
            <Button
              onClick={handleAiMismatchAcknowledge}
              className="w-full sm:w-auto bg-amber-600 hover:bg-amber-700 text-white"
              data-testid="ai-mismatch-keep-btn"
            >
              {(i18n.language || 'en').toLowerCase().startsWith('fr')
                ? 'OK — soumettre pour examen admin'
                : 'OK — submit for admin review'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CreateListingPage;
