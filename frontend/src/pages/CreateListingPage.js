import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams, useParams } from 'react-router-dom';
import SaveAsDraftButton from '../components/SaveAsDraftButton';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { extractErrorMessage } from '../utils/errorHandler';
import { uploadListingImage } from '../utils/uploadListingImage';
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
import AcceptedPaymentMethodsSelector from '../components/AcceptedPaymentMethodsSelector';
import { CFIASoilBanner, CFIASoilCheckbox } from '../components/legal/LegalComplianceSections';
import useGeoLocation from '../hooks/useGeoLocation';
// iter299 P0 — Bill 96 French-title helpers + shared input field
import { isQuebecListing, validateFrenchTitle, humanizeQcError } from '../utils/bill96';
import FrenchTitleField from '../components/FrenchTitleField';
import ListingBlockDialog from '../components/ListingBlockDialog';
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
  // iter220 Task 3 — Single language detector shared across the Storage Locker
  // panel so every label/placeholder/help-text auto-switches when the global
  // i18n language flips. Use this instead of inline `i18n.language?.startsWith(...)`.
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const { user } = useAuth();

  // iter299 P0 — Bill 96: Quebec listings require a French title.
  const [frTitleError, setFrTitleError] = useState(null);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const geo = useGeoLocation();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [cfiaDeclaration, setCfiaDeclaration] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    title_fr: '',
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

  // iter312 D2 — Edit mode: when the route param `:listingId` is present,
  // hydrate formData from the existing listing so the seller can correct
  // a flagged listing without re-typing everything. URL: /edit-listing/:id
  const { listingId: editListingId } = useParams();
  const [searchParamsLocal] = useSearchParams();
  const hydratedDraftId = searchParamsLocal.get('draft_id');
  const [editMode, setEditMode] = useState(false);

  // iter313 — Hydrate from /api/drafts/{id} when ?draft_id=X is in URL.
  useEffect(() => {
    if (!hydratedDraftId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/drafts/${hydratedDraftId}`);
        const p = r.data?.payload || {};
        if (cancelled) return;
        setFormData((prev) => ({ ...prev, ...p, draft_id: hydratedDraftId }));
      } catch {
        toast.error('Failed to load draft');
      }
    })();
    return () => { cancelled = true; };
  }, [hydratedDraftId]);
  useEffect(() => {
    if (!editListingId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/listings/${editListingId}`);
        const l = r.data || {};
        if (cancelled) return;
        setEditMode(true);
        setFormData((prev) => ({
          ...prev,
          // Copy every overlapping field; leave others at their defaults.
          title:            l.title || '',
          title_fr:         l.title_fr || '',
          title_en:         l.title_en || '',
          description:      l.description || '',
          description_fr:   l.description_fr || '',
          description_en:   l.description_en || '',
          category:         l.category || '',
          condition:        l.condition || 'good',
          starting_price:   l.starting_price ?? '',
          buy_now_price:    l.buy_now_price ?? '',
          images:           Array.isArray(l.images) ? l.images : [],
          country:          l.country || 'CA',
          region:           l.region || '',
          city:             l.city || '',
          postal_code:      l.postal_code || '',
          location:         l.location || '',
          currency:         l.currency || 'CAD',
          id:               l.id,
        }));
        // iter441 — Prefill the storage-operator BP override when editing
        // a listing that already has a per-listing rate set.
        if (typeof l.custom_buyer_premium_rate === 'number' && l.custom_buyer_premium_rate > 0) {
          setBuyersPremiumPercent(String(Math.round(l.custom_buyer_premium_rate * 100 * 100) / 100));
        }
        // If the listing is a storage locker, flip the local flag so the
        // BP field renders (edit mode doesn't re-run the URL param toggle).
        if (l.category === 'storage_locker' || l.listing_type === 'storage_locker') {
          setIsStorageLocker(true);
        }
      } catch (err) {
        toast.error(extractErrorMessage(err) || 'Failed to load listing for editing');
      }
    })();
    return () => { cancelled = true; };
  }, [editListingId]);

  // Buyer's Premium — default to org setting
  const [buyersPremiumPercent, setBuyersPremiumPercent] = useState('');
  const isOpcCertified = user?.is_opc_certified === true;
  const isPartner = user?.is_partner === true || user?.role === 'partner' || user?.role === 'admin';
  // Phase 6.0 hotfix — Admin / super_admin bypass for storage validation
  const isAdminUser = user?.role === 'admin' || user?.role === 'super_admin' || user?.is_admin === true;
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

  // Seller Payment Method (legacy singleton, retained for backward compat)
  const [paymentMethod, setPaymentMethod] = useState('stripe');

  // iter482 P4B — Seller-Controlled Accepted Payment Methods (multi-select)
  const [acceptedPaymentMethods, setAcceptedPaymentMethods] = useState(['stripe']);

  // Deposit (Spec Feature 1) — single field, single flow
  const [requiresDeposit, setRequiresDeposit] = useState(false);
  const [depositType, setDepositType] = useState('fixed'); // 'fixed' | 'percentage'
  const [depositAmount, setDepositAmount] = useState('');

  // FEATURE PATCH v9 / Feature 4 — Quantity & per-unit hammer multiplier
  const [quantity, setQuantity] = useState(1);
  const [multiplyHammerByQuantity, setMultiplyHammerByQuantity] = useState(false);
  // iter233 — Display-only "Lot price × Quantity" toggle.
  const [priceMultipliedByQuantity, setPriceMultipliedByQuantity] = useState(false);

  // iter233 — When quantity drops to 1, automatically uncheck the display
  // multiplier so old state doesn't leak into the submitted payload.
  useEffect(() => {
    if (Math.max(1, parseInt(quantity, 10) || 1) <= 1 && priceMultipliedByQuantity) {
      setPriceMultipliedByQuantity(false);
    }
  }, [quantity, priceMultipliedByQuantity]);

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
  // iter342 — typed block reason from the backend (context-aware messages)
  const [blockReason, setBlockReason] = useState('vehicle_dealer_required');
  const [blockMessages, setBlockMessages] = useState(null);
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

  // iter298 BUG 2 — "Edit & Relist": pre-populate the form from an ended
  // listing (?relist=<listing_id>). The seller can adjust title / price /
  // duration / photos before republishing as a brand-new auction.
  useEffect(() => {
    const relistId = searchParams.get('relist');
    if (!relistId) return;
    let cancelled = false;
    axios.get(`${API}/listings/${relistId}`)
      .then((res) => {
        if (cancelled) return;
        const src = res.data || {};
        const nextWeek = new Date();
        nextWeek.setDate(nextWeek.getDate() + 7);
        setFormData((prev) => ({
          ...prev,
          title: src.title || prev.title,
          title_fr: src.title_fr || prev.title_fr,
          description: src.description || prev.description,
          description_fr: src.description_fr || prev.description_fr,
          category: src.category || prev.category,
          condition: src.condition || prev.condition,
          starting_price: src.starting_price != null ? String(src.starting_price) : prev.starting_price,
          buy_now_price: src.buy_now_price != null ? String(src.buy_now_price) : prev.buy_now_price,
          images: Array.isArray(src.images) ? src.images : prev.images,
          country: src.country || prev.country,
          region: src.region || prev.region,
          city: src.city || prev.city,
          postal_code: src.postal_code || prev.postal_code,
          location: src.location || prev.location,
          currency: src.currency || prev.currency,
          auction_end_date: nextWeek.toISOString().slice(0, 16),
        }));
        toast.info(isFr
          ? 'Formulaire pré-rempli depuis votre annonce terminée — modifiez puis republiez.'
          : 'Form pre-filled from your ended listing — adjust anything, then republish.');
      })
      .catch(() => {
        toast.error(isFr ? 'Annonce source introuvable.' : 'Source listing not found.');
      });
    return () => { cancelled = true; };
  }, [searchParams]);

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

  // iter440 — Upload each selected image to S3 via
  // /api/uploads/listing-image and store the returned public URL in
  // formData.images. Submitting base64 data URLs directly to
  // /api/listings was rejected by the API-level guardrail (see
  // routes/listings.py) and caused Mongo document bloat.
  const handleImageUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    for (const file of files) {
      if (file.size > 5000000) {
        toast.error('Image size should be less than 5MB');
        continue;
      }
      try {
        const url = await uploadListingImage(file);
        setFormData((prev) => ({
          ...prev,
          images: [...prev.images, url],
        }));
      } catch (err) {
        console.error('[CreateListing] image upload failed:', err);
        toast.error(extractErrorMessage(err) || 'Failed to upload image');
      }
    }
    // Reset the input so the same file can be re-picked if needed.
    e.target.value = '';
  };

  const removeImage = (index) => {
    setFormData({
      ...formData,
      images: formData.images.filter((_, i) => i !== index)
    });
  };

  const submitListingPayload = async (payload) => {
    try {
      // iter312 D2 — Edit mode submits PUT against the existing listing
      // (preserves seller data) and then resubmits the listing for AI re-scan.
      // Normal (non-edit) flow remains POST to /listings.
      let response;
      if (editMode && editListingId) {
        response = await axios.put(`${API}/listings/${editListingId}`, payload);
        // After saving the edits, kick the re-scan + status flip.
        try {
          await axios.post(`${API}/listings/${editListingId}/resubmit-for-review`);
        } catch {
          // Non-fatal — the edit itself succeeded. The seller can use the
          // "Resubmit" button on the dashboard if the re-scan didn't run.
        }
        toast.success((i18n.language || 'en').startsWith('fr')
          ? 'Annonce mise à jour et resoumise.'
          : 'Listing updated and resubmitted for review.');
        navigate('/seller/dashboard');
        return response.data;
      }
      response = await axios.post(`${API}/listings`, payload);
      toast.success('Listing created successfully!');
      navigate(`/listing/${response.data.id}`);
      return response.data;
    } catch (error) {
      console.error('Failed to create listing:', error);
      const detail = error?.response?.data?.detail;
      if (detail && typeof detail === 'object' && (detail.block_reason || detail.error === 'vehicle_listing_dealer_required')) {
        setBlockReason(detail.block_reason || 'vehicle_dealer_required');
        setBlockMessages(detail.message_en || detail.message_fr
          ? { en: detail.message_en, fr: detail.message_fr }
          : null);
        setVehicleComplianceSignals(Array.isArray(detail.signals) ? detail.signals : []);
        setVehicleComplianceReviewRequested(false);
        setVehicleComplianceReviewSubmitting(false);
        setVehicleComplianceOpen(true);
        return null;
      }
      // iter299 P0 — Bill 96 errors become readable inline form errors,
      // never a raw JSON popup.
      const qcMessage = humanizeQcError(error, isFr);
      if (qcMessage) {
        setFrTitleError(qcMessage);
        toast.error(qcMessage);
        document.getElementById('title-fr')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return null;
      }
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Failed to create listing');
      return null;
    }
  };

  // iter299 P0 — Bill 96 applies when the seller's registered province OR
  // the listing location is Quebec.
  const isQuebec = isQuebecListing(user?.province, formData.region, formData.city);

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Iter187: enforce CRA Tax Onboarding at submit time, not at form-mount time
    if (taxOnboardingPending) {
      toast.error('Please complete your tax declaration before publishing your listing.');
      return;
    }

    // iter482 P4B — block publish if seller didn't choose ≥ 1 accepted method
    if (!acceptedPaymentMethods || acceptedPaymentMethods.length === 0) {
      toast.error(
        i18n.language === 'fr'
          ? "Veuillez sélectionner au moins un mode de paiement."
          : "Please select at least one payment method."
      );
      return;
    }

    // iter310 — Bill 96 compliance is now zero-friction: when the listing
    // is in Quebec and the French copy is missing, the backend auto-
    // translates it via Gemini 2.5 Flash before persisting. The UI shows a
    // soft "Translating…" loading toast (NEVER a hard-block popup) while
    // the request is in flight. The 422 hard-gate is the absolute floor —
    // it only fires for truly empty submissions or when both EN + FR are
    // missing.
    const needsBill96Translation = isQuebec && (
      (String(formData.title || '').trim() && !String(formData.title_fr || '').trim()) ||
      (String(formData.description || '').trim() && !String(formData.description_fr || '').trim())
    );
    let bill96ToastId = null;
    if (needsBill96Translation) {
      bill96ToastId = toast.loading(
        isFr
          ? 'Traduction et mise en conformité avec la Loi 96…'
          : 'Translating and formatting listing for Bill 96 compliance…',
        { duration: 30000, id: 'bill96-translating' }
      );
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
        // iter233 — Display-only "Lot price × Quantity" toggle.
        price_multiplied_by_quantity: !isStorageLocker
          && (Math.max(1, parseInt(quantity) || 1) > 1)
          && !!priceMultipliedByQuantity,
        // iter445 — Storage listings ignore any client-sent BP rate;
        // server-side enforcement guarantees the fixed 5 % platform BP
        // regardless of this field. For non-storage flows the field is
        // still honored (partner override, iter441).
        buyers_premium_rate: isStorageLocker
          ? null
          : (buyersPremiumPercent !== '' ? parseFloat(buyersPremiumPercent) / 100 : null),
        payment_method: (acceptedPaymentMethods && acceptedPaymentMethods[0]) || paymentMethod,
        // iter482 P4 — Seller-Controlled Accepted Payment Methods (canonical).
        accepted_payment_methods: acceptedPaymentMethods,
        // Deposit (spec Feature 1) — disabled for storage_locker (native pre-auth holds replace this)
        requires_deposit: !isStorageLocker && requiresDeposit,
        deposit_amount: !isStorageLocker && requiresDeposit && depositAmount ? parseFloat(depositAmount) : null,
        deposit_type: !isStorageLocker && requiresDeposit ? depositType : null,
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
      // iter310 — Dismiss the Bill 96 "Translating…" loading toast.
      // Sonner uses string ids; passing the id dismisses the in-flight toast
      // regardless of whether the submit succeeded or failed.
      if (bill96ToastId) {
        toast.dismiss('bill96-translating');
      }
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
  //
  // iter312 D1 ROOT-CAUSE FIX:
  //   Previously this payload only sent {title, description, category,
  //   detected_signals, images, starting_price, listing_id}. The backend
  //   then created a stub listing with HARDCODED empty strings for
  //   location/city/region/country (because they weren't on the payload).
  //   That data was lost permanently when admin approved.
  //
  //   We now send EVERY form field the wizard has captured at the moment
  //   the AI block fires so the locked- stub mirrors the seller's draft
  //   exactly, and admin approve = pure status flip with no data loss.
  const handleRequestManualVehicleReview = async () => {
    if (vehicleComplianceReviewRequested || vehicleComplianceReviewSubmitting) return;
    setVehicleComplianceReviewSubmitting(true);
    try {
      await axios.post(`${API}/listings/request-manual-vehicle-review`, {
        title:            formData.title || '',
        title_en:         formData.title_en || '',
        title_fr:         formData.title_fr || '',
        description:      formData.description || '',
        description_en:   formData.description_en || '',
        description_fr:   formData.description_fr || '',
        category:         formData.category || '',
        condition:        formData.condition || 'good',
        currency:         formData.currency || 'CAD',
        starting_price:   parseFloat(formData.starting_price) || 0,
        buy_now_price:    formData.buy_now_price ? parseFloat(formData.buy_now_price) : null,
        // iter312 D1 — Send the seller's actual location so it's preserved.
        location:         formData.location || '',
        city:             formData.city || '',
        region:           formData.region || '',
        country:          formData.country || '',
        postal_code:      formData.postal_code || '',
        province:         formData.province || '',
        auction_end_date: formData.auction_end_date || null,
        detected_signals: vehicleComplianceSignals,
        images:           Array.isArray(formData.images) ? formData.images : [],
        images_count:     Array.isArray(formData.images) ? formData.images.length : 0,
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
  // iter223 — Demo accounts bypass the partner-fee lockdown entirely
  // so leads can experience the full create-listing flow. Their listings
  // are server-side stamped `is_demo_sandbox=true` and stay invisible
  // to the public marketplace.
  if (user?.is_partner && !user?.platform_fee_paid && !user?.is_demo_account) {
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
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <CardTitle className="text-2xl font-bold">{t('createListing.createNewListing', 'Create New Listing')}</CardTitle>
              {/* iter313 — Universal Save-as-Draft, always visible at every step */}
              <SaveAsDraftButton
                type="marketplace"
                formData={formData}
                draftId={formData.draft_id || null}
                onSaved={(id) => setFormData((p) => ({ ...p, draft_id: id }))}
              />
            </div>
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

              {/* iter299 P0 — Bill 96 French title (required for Quebec listings). */}
              <FrenchTitleField
                value={formData.title_fr}
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, title_fr: e.target.value }));
                  if (frTitleError) setFrTitleError(null);
                }}
                isQuebec={isQuebec}
                error={frTitleError}
                isFr={isFr}
              />

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
                        placeholder={isFr ? '3 m × 3 m, 1,5 m × 3 m, etc.' : '10x10, 5x10, etc.'}
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
                      <option value={24}>{isFr ? '24 heures' : '24 hours'}</option>
                      <option value={48}>{isFr ? '48 heures' : '48 hours'}</option>
                      <option value={72}>{isFr ? '72 heures (recommandé)' : '72 hours (recommended)'}</option>
                      <option value={168}>{isFr ? '1 semaine' : '1 week'}</option>
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
                        placeholder={isFr ? 'Montant personnalisé (50–5 000 CAD)' : 'Custom amount (50–5000 CAD)'}
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
                              {/* iter220 Task 3 — Show single-language tag
                                  label based on global i18n state. The side-
                                  by-side EN/FR was useful for facility-onboarding
                                  but feels redundant once the user has picked
                                  a language. */}
                              {isFr ? tag.fr : tag.en}
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
                {/* iter233 — Display-only "Lot price × Quantity" toggle. Renders only when qty > 1. */}
                {parseInt(quantity) > 1 && (
                  <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${priceMultipliedByQuantity ? 'border-amber-500 bg-amber-50' : 'border-slate-200 hover:border-slate-300'}`}>
                    <input
                      type="checkbox"
                      checked={priceMultipliedByQuantity}
                      onChange={(e) => setPriceMultipliedByQuantity(e.target.checked)}
                      className="mt-0.5 w-4 h-4 accent-amber-600 cursor-pointer"
                      data-testid="price-multiplied-by-quantity-toggle"
                    />
                    <div>
                      <span className="font-medium text-sm">
                        {t('createListing.priceMultipliedLabel', 'Multiply listed price by quantity')}
                      </span>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {t('createListing.priceMultipliedHelp', 'Check this if the price shown to buyers should reflect the total value of all units in this lot.')}
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
                {/* iter441 — Storage facility operators previously could set
                    a per-listing BP rate (0–25%). iter445 REMOVED this
                    override — storage BP is now a fixed platform policy
                    of 5 %. Partners keep the override; storage lockers
                    now show a read-only fixed-5% notice instead. */}
                {isStorageLocker ? (
                  <p
                    className="text-sm bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-900 text-emerald-800 dark:text-emerald-200 px-3 py-2 rounded flex items-center gap-2"
                    data-testid="bp-storage-fixed-notice"
                  >
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 text-white text-[10px] font-bold px-2 py-0.5">5%</span>
                    {t(
                      'createListing.buyersPremiumStorageFixed',
                      "Fixed 5% buyer's premium — charged to the winning bidder on top of the hammer. Your facility receives the full hammer and is never charged."
                    )}
                  </p>
                ) : isPartner ? (
                  <>
                    <Input
                      id="buyers_premium_percent"
                      type="number"
                      step="0.5"
                      min="0"
                      max="25"
                      placeholder={t('createListing.buyersPremiumPartnerPh', 'Leave blank for platform default (5%)')}
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

              {/* Payment Method Selection (LEGACY singleton — retained for
                  the fee-preview label). iter482 P4B adds a mandatory
                  multi-select accepted-methods block BELOW that becomes
                  the seller's actual acceptance policy. */}
              {/* iter482 P4 — Canonical Seller-Controlled Accepted Payment Methods
                  (multi-select). Replaces the legacy single-choice radio group.
                  Buyer will only see methods selected here. */}
              <div className="space-y-3" data-testid="payment-method-section">
                <AcceptedPaymentMethodsSelector
                  value={acceptedPaymentMethods}
                  onChange={setAcceptedPaymentMethods}
                  isFrench={i18n.language === 'fr'}
                />
                {(acceptedPaymentMethods || []).some((m) => ['cash', 'etransfer', 'cheque'].includes(m)) && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-md" data-testid="payment-legal-notice">
                    <p className="text-sm text-amber-800 font-medium">{t('createListing.legalDisclosureTitle')}</p>
                    <p className="text-xs text-amber-700 mt-1">
                      {t('createListing.legalDisclosureCash', { currency: formData.currency })}
                    </p>
                  </div>
                )}
                {(acceptedPaymentMethods || []).includes('stripe') && (
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

      {/* iter342 — Context-aware listing block dialog (typed block_reason) */}
      <ListingBlockDialog
        open={vehicleComplianceOpen}
        onOpenChange={setVehicleComplianceOpen}
        reason={blockReason}
        signals={vehicleComplianceSignals}
        messages={blockMessages}
        reviewRequested={vehicleComplianceReviewRequested}
        reviewSubmitting={vehicleComplianceReviewSubmitting}
        onRequestReview={handleRequestManualVehicleReview}
      />

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
