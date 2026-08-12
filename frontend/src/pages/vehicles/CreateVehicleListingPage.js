import API_BASE from '../../config';
import { extractErrorMessage } from '../../utils/errorHandler';
/**
 * Create Vehicle Listing Page
 * Multi-step form with VIN auto-fill and photo upload
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import confetti from 'canvas-confetti';
import VehicleCategoryGrid from '../../components/vehicles/VehicleCategoryGrid';
import SaveAsDraftButton from '../../components/SaveAsDraftButton';
import ProvinceSellerNotice from '../../components/vehicles/ProvinceSellerNotice';
import VehicleLegalFooter from '../../components/vehicles/VehicleLegalFooter';
import VehicleProvinceEligibility from '../../components/vehicles/VehicleProvinceEligibility';
import DealerVerificationGate from '../../components/vehicles/DealerVerificationGate';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { Checkbox } from '../../components/ui/checkbox';
import {
  Car, Search, CheckCircle, XCircle, Upload, Camera, DollarSign,
  Calendar, MapPin, FileText, AlertTriangle, ChevronRight, ChevronLeft,
  Loader2, Shield, Zap, Info, Settings2, Fuel, Gauge, Palette

} from 'lucide-react';
import LocationSelector from '../../components/LocationSelector';
import AcceptedPaymentMethodsSelector from '../../components/AcceptedPaymentMethodsSelector';
import useGeoLocation from '../../hooks/useGeoLocation';

const API = API_BASE;

const BODY_TYPES = [
  { value: 'sedan', label: 'Sedan' },
  { value: 'suv', label: 'SUV' },
  { value: 'truck', label: 'Truck' },
  { value: 'coupe', label: 'Coupe' },
  { value: 'hatchback', label: 'Hatchback' },
  { value: 'van', label: 'Van' },
  { value: 'convertible', label: 'Convertible' },
  { value: 'wagon', label: 'Wagon' },
  { value: 'other', label: 'Other' },
];

const FUEL_TYPES = [
  { value: 'gasoline', label: 'Gasoline' },
  { value: 'diesel', label: 'Diesel' },
  { value: 'electric', label: 'Electric' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'plugin_hybrid', label: 'Plug-in Hybrid' },
  { value: 'other', label: 'Other' },
];

const TRANSMISSIONS = [
  { value: 'automatic', label: 'Automatic' },
  { value: 'manual', label: 'Manual' },
  { value: 'cvt', label: 'CVT' },
  { value: 'dct', label: 'Dual-Clutch' },
];

const DRIVETRAINS = [
  { value: 'fwd', label: 'FWD (Front-Wheel Drive)' },
  { value: 'rwd', label: 'RWD (Rear-Wheel Drive)' },
  { value: 'awd', label: 'AWD (All-Wheel Drive)' },
  { value: '4wd', label: '4WD (Four-Wheel Drive)' },
];

const PHOTO_CATEGORIES = [
  { id: 'front', label: 'Front View', required: true },
  { id: 'rear', label: 'Rear View', required: true },
  { id: 'driver_side', label: 'Driver Side', required: false },
  { id: 'passenger_side', label: 'Passenger Side', required: false },
  { id: 'interior_front', label: 'Interior (Front)', required: false },
  { id: 'interior_rear', label: 'Interior (Rear)', required: false },
  { id: 'dashboard', label: 'Dashboard', required: false },
  { id: 'engine', label: 'Engine Bay', required: false },
  { id: 'trunk', label: 'Trunk', required: false },
  { id: 'vin_plate', label: 'VIN Plate', required: true },
  { id: 'damage', label: 'Damage (if any)', required: false },
  { id: 'other', label: 'Other', required: false },
];

const CONDITIONS = ['excellent', 'good', 'fair', 'poor', 'unknown'];

// Create Vehicle Listing Page Component
const CreateVehicleListingPage = () => {
  const navigate = useNavigate();
  // iter198 — Capture pilot attribution (URL param wins over stored value)
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const utm = params.get('utm_source');
      if (utm) localStorage.setItem('bidvex.utm_source', utm.slice(0, 100));
    } catch (_e) {}
  }, []);
  const { t, i18n } = useTranslation();
  const { token, user } = useAuth();
  const geo = useGeoLocation();
  const [currentStep, setCurrentStep] = useState(0);
  // iter482 P4B — Seller-Controlled Accepted Payment Methods (multi-select)
  const [acceptedPaymentMethods, setAcceptedPaymentMethods] = useState(['stripe']);

  const STEPS = [
    { id: 'vin', title: t('vehicleListing.steps.vin', 'VIN & Basic Info'), icon: Car },
    { id: 'specs', title: t('vehicleListing.steps.specs', 'Specifications'), icon: Settings2 },
    { id: 'condition', title: t('vehicleListing.steps.condition', 'Condition Report'), icon: FileText },
    { id: 'photos', title: t('vehicleListing.steps.photos', 'Photos & Media'), icon: Camera },
    { id: 'auction', title: t('vehicleListing.steps.auction', 'Auction Settings'), icon: DollarSign },
    { id: 'review', title: t('vehicleListing.steps.review', 'Review & Submit'), icon: CheckCircle },
  ];
  const [loading, setLoading] = useState(false);
  const [vinLoading, setVinLoading] = useState(false);
  const [sellerProfile, setSellerProfile] = useState(null);
  // iter427 — Track the seller-status probe so we can render an inline
  // DealerVerificationGate instead of silently redirecting unverified
  // dealers. Distinguishes "no seller row" (never registered) from
  // "seller row present but not approved yet".
  const [sellerProbe, setSellerProbe] = useState({ loaded: false, noProfile: false });
  const [photos, setPhotos] = useState({});
  
  // Form data
  const [formData, setFormData] = useState({
    // iter201 — Vehicle category (CEO 15-category taxonomy)
    category_id: '',
    subcategory_id: '',

    // VIN & Basic
    vin: '',
    year: '',
    make: '',
    model: '',
    trim: '',
    body_type: 'sedan',
    
    // Specs
    mileage: '',
    transmission: 'automatic',
    fuel_type: 'gasoline',
    drivetrain: 'fwd',
    engine_size: '',
    cylinders: '',
    horsepower: '',
    exterior_color: '',
    interior_color: '',
    
    // Documentation
    ownership_status: 'owned',
    title_status: 'clean',
    lien_status: 'clear',
    
    // Condition
    is_running: true,
    starts_normally: true,
    engine_condition: 'good',
    transmission_condition: 'good',
    brakes_condition: 'good',
    suspension_condition: 'good',
    body_condition: 'good',
    paint_condition: 'good',
    interior_condition: 'good',
    tires_condition: 'good',
    has_accident_history: false,
    has_flood_damage: false,
    has_fire_damage: false,
    has_frame_damage: false,
    mechanical_notes: '',
    cosmetic_notes: '',
    
    // Location
    location_country: 'CA',
    location_city: '',
    location_province: '',
    location_postal_code: '',
    
    // Auction
    auction_type: 'timed',
    visibility: 'public',
    auction_access: 'public_individual',  // iter194 — Public | Licensed Only
    run_status: 'run_and_drive',          // iter194 — Run & Drive | Starts Only | Non-Operational
    start_time: '',
    end_time: '',
    starting_price: '',
    reserve_price: '',
    buy_now_price: '',
    bid_increment: '100',
    requires_deposit: true,
    deposit_amount: '500',
    deposit_type: 'fixed',
    currency: 'CAD',
    // payment_method removed — iter194: dealer transactions are off-platform; BidVex only collects unlock fee from buyer at win
    
    // Description
    title: '',
    title_fr: '',          // iter285 — QC Bill 96 French title (auto-mirrors `title` when blank)
    description: '',
    description_fr: '',    // iter285 — QC Bill 96 French description
    features: [],

    // iter285 — Provincial registration eligibility (Bug 4).
    // `eligible_provinces` is either `["ALL"]` or an explicit list of 2-letter
    // codes (QC, ON, BC, …). `inspection_status` indicates safety/e-test/MVI
    // status. Both default to empty so existing listings without these fields
    // continue to render the "TBD / contact seller" notice.
    eligible_provinces: ['ALL'],
    inspection_status: 'as_is',

    // iter286 — Bug 5 — Carfax / inspection report fields.
    carfax_url: '',
    carfax_file: '',
    inspection_file: '',
  });

  // Check seller profile
  useEffect(() => {
    const checkSeller = async () => {
      if (!token) {
        navigate('/auth');
        return;
      }

      try {
        const response = await axios.get(`${API}/vehicle-sellers/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSellerProfile(response.data);
        setSellerProbe({ loaded: true, noProfile: false });
        // iter427 — Do NOT redirect on unverified. The parent render
        // now surfaces an inline <DealerVerificationGate> with a
        // "Verify Dealer" CTA. Redirect only kept for the auth/token
        // path above.
      } catch (error) {
        if (error.response?.status === 404) {
          // Never registered. Render the gate (not_registered branch).
          setSellerProbe({ loaded: true, noProfile: true });
          return;
        }
        setSellerProbe({ loaded: true, noProfile: false });
      }
    };

    checkSeller();
  }, [token, navigate]);

  // iter313 — Hydrate from /api/drafts/{id} when ?draft_id=X on URL.
  const [searchParamsLocal] = useSearchParams();
  const hydratedDraftId = searchParamsLocal.get('draft_id');
  useEffect(() => {
    if (!hydratedDraftId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/drafts/${hydratedDraftId}`);
        const p = r.data?.payload || {};
        if (cancelled) return;
        setFormData((prev) => ({ ...prev, ...p, draft_id: hydratedDraftId }));
      } catch { /* silent */ }
    })();
    return () => { cancelled = true; };
  }, [hydratedDraftId]);

  // Update form field
  const updateField = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  // Decode VIN
  const decodeVIN = async () => {
    if (!formData.vin || formData.vin.length !== 17) {
      toast.error('Please enter a valid 17-character VIN');
      return;
    }
    
    setVinLoading(true);
    try {
      const response = await axios.get(`${API}/vehicles/decode-vin/${formData.vin}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const data = response.data;
      setFormData(prev => ({
        ...prev,
        year: data.year?.toString() || prev.year,
        make: data.make || prev.make,
        model: data.model || prev.model,
        trim: data.trim || prev.trim,
        body_type: data.body_type || prev.body_type,
        transmission: data.transmission || prev.transmission,
        fuel_type: data.fuel_type || prev.fuel_type,
        drivetrain: data.drivetrain || prev.drivetrain,
        engine_size: data.engine_size || prev.engine_size,
        cylinders: data.cylinders?.toString() || prev.cylinders,
        horsepower: data.horsepower?.toString() || prev.horsepower,
      }));
      
      toast.success('VIN decoded successfully!');
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to decode VIN');
    } finally {
      setVinLoading(false);
    }
  };

  // Handle photo upload
  const handlePhotoUpload = (category, files) => {
    const newPhotos = { ...photos };
    if (!newPhotos[category]) {
      newPhotos[category] = [];
    }
    
    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        newPhotos[category].push({
          file,
          preview: e.target.result,
          category,
        });
        setPhotos({ ...newPhotos });
      };
      reader.readAsDataURL(file);
    });
  };

  // Remove photo
  const removePhoto = (category, index) => {
    const newPhotos = { ...photos };
    newPhotos[category].splice(index, 1);
    setPhotos(newPhotos);
  };

  // Get total photo count
  const getTotalPhotos = () => {
    return Object.values(photos).reduce((sum, arr) => sum + arr.length, 0);
  };

  // Submit listing — iter292 Directive 3: dealer-controlled lifecycle.
  // `intent` carries the dealer's lifecycle choice from the submit-row
  // buttons (Save as Draft / Schedule / Go Live Now). Falls back to
  // "live" so older call sites that pass no arg keep the existing
  // behaviour.
  const handleSubmit = async (intent = 'live') => {
    if (getTotalPhotos() < 10) {
      toast.error('Please upload at least 10 photos');
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
    // Guard: Schedule intent must have a future start_time.
    if (intent === 'schedule') {
      const startMs = new Date(formData.start_time).getTime();
      if (!startMs || startMs <= Date.now() + 60_000) {
        toast.error(t(
          'vehicleListing.scheduleStartFutureRequired',
          'Schedule (Upcoming) requires a Start Time at least 1 minute in the future.'
        ));
        return;
      }
    }
    
    setLoading(true);
    try {
      // Prepare listing data
      const listingData = {
        vin: formData.vin,
        year: parseInt(formData.year),
        make: formData.make,
        model: formData.model,
        trim: formData.trim || null,
        body_type: formData.body_type,
        mileage: parseInt(formData.mileage),
        transmission: formData.transmission,
        fuel_type: formData.fuel_type,
        drivetrain: formData.drivetrain,
        engine_size: formData.engine_size || null,
        cylinders: formData.cylinders ? parseInt(formData.cylinders) : null,
        horsepower: formData.horsepower ? parseInt(formData.horsepower) : null,
        exterior_color: formData.exterior_color,
        interior_color: formData.interior_color,
        ownership_status: formData.ownership_status,
        title_status: formData.title_status,
        lien_status: formData.lien_status,
        condition_report: {
          is_running: formData.is_running,
          starts_normally: formData.starts_normally,
          engine_condition: formData.engine_condition,
          transmission_condition: formData.transmission_condition,
          brakes_condition: formData.brakes_condition,
          suspension_condition: formData.suspension_condition,
          body_condition: formData.body_condition,
          paint_condition: formData.paint_condition,
          interior_condition: formData.interior_condition,
          tires_condition: formData.tires_condition,
          has_accident_history: formData.has_accident_history,
          has_flood_damage: formData.has_flood_damage,
          has_fire_damage: formData.has_fire_damage,
          has_frame_damage: formData.has_frame_damage,
          mechanical_notes: formData.mechanical_notes || null,
          cosmetic_notes: formData.cosmetic_notes || null,
        },
        location_city: formData.location_city,
        location_province: formData.location_province,
        location_postal_code: formData.location_postal_code,
        auction_type: formData.auction_type,
        visibility: formData.visibility,
        start_time: new Date(formData.start_time).toISOString(),
        end_time: new Date(formData.end_time).toISOString(),
        starting_price: parseFloat(formData.starting_price),
        reserve_price: formData.reserve_price ? parseFloat(formData.reserve_price) : null,
        buy_now_price: formData.buy_now_price ? parseFloat(formData.buy_now_price) : null,
        bid_increment: parseFloat(formData.bid_increment),
        requires_deposit: formData.requires_deposit,
        deposit_amount: formData.requires_deposit && formData.deposit_amount ? parseFloat(formData.deposit_amount) : null,
        deposit_type: formData.requires_deposit ? formData.deposit_type : null,
        currency: formData.currency,
        // payment_method removed (iter194)
        // iter482 P4B — Seller-Controlled Accepted Payment Methods multi-select.
        accepted_payment_methods: acceptedPaymentMethods,
        auction_access: formData.auction_access,
        run_status: formData.run_status,
        title: formData.title,
        // iter285 — Quebec Bill 96 compliance. Auto-mirror the English title
        // when the seller left the FR field blank (the form pre-fills it
        // anyway, but this is a belt-and-suspenders guard).
        title_fr: (formData.title_fr && formData.title_fr.trim())
          ? formData.title_fr.trim()
          : formData.title,
        description: formData.description,
        description_fr: (formData.description_fr && formData.description_fr.trim())
          ? formData.description_fr.trim()
          : formData.description,
        features: formData.features,
        // iter285 — Bug 4 — Provincial registration eligibility.
        eligible_provinces: Array.isArray(formData.eligible_provinces) && formData.eligible_provinces.length > 0
          ? formData.eligible_provinces
          : ['ALL'],
        inspection_status: formData.inspection_status || 'as_is',

        // iter286 — Bug 5 — Carfax / inspection references.
        carfax_url:       (formData.carfax_url || '').trim() || null,
        carfax_file:      (formData.carfax_file || '').trim() || null,
        inspection_file:  (formData.inspection_file || '').trim() || null,
        // iter201 — Phase 2 — Vehicle category (CEO 15-category taxonomy)
        category_id: formData.category_id || null,
        subcategory_id: formData.subcategory_id || null,
        // iter198 — Pilot attribution
        utm_source: (() => {
          try { return localStorage.getItem('bidvex.utm_source') || null; } catch (_e) { return null; }
        })(),
        // iter292 — Directive 3: Dealer lifecycle intent.
        submission_intent: intent,
      };

      // iter201 — Phase 2 — Validate category required (CEO constraint #3)
      if (!listingData.category_id) {
        toast.error(i18n.language?.startsWith('fr')
          ? 'Veuillez sélectionner une catégorie de véhicule'
          : 'Please select a vehicle category');
        setLoading(false);
        return;
      }
      // iter201 — Phase 2 — Quebec French-language enforcement (CEO constraint #2)
      // iter285 — Actionable error messages now point the seller to the EXACT
      // step + field that needs filling (no more dead-end popup).
      if ((listingData.location_province || '').toUpperCase() === 'QC') {
        const fr = (s) => typeof s === 'string' && s.trim().length > 0;
        if (!fr(listingData.title_fr) && !fr(listingData.title)) {
          toast.error(i18n.language?.startsWith('fr')
            ? "Étape 5 (Paramètres d'enchère) — veuillez remplir le champ « Titre du véhicule (Français) »."
            : "Step 5 (Auction Settings) — please fill in the 'Titre du véhicule (Français)' field.");
          setCurrentStep(STEPS.findIndex(s => s.id === 'auction'));
          setLoading(false);
          return;
        }
        if (!fr(listingData.description_fr) && !fr(listingData.description)) {
          toast.error(i18n.language?.startsWith('fr')
            ? "Étape 5 — veuillez remplir le champ « Description (Français) »."
            : "Step 5 — please fill in the 'Description (Français)' field.");
          setCurrentStep(STEPS.findIndex(s => s.id === 'auction'));
          setLoading(false);
          return;
        }
      }

      // Create listing
      let vehicleId;
      try {
        const createResponse = await axios.post(`${API}/vehicles`, listingData, {
          headers: { Authorization: `Bearer ${token}` }
        });
        vehicleId = createResponse.data?.id;
        if (!vehicleId) {
          // Backend OK but no id back — surface gracefully, do NOT navigate.
          toast.error(i18n.language?.startsWith('fr')
            ? "Annonce créée mais identifiant manquant. Réessayez."
            : "Listing created but no id returned. Please retry.");
          setLoading(false);
          return;
        }
      } catch (createErr) {
        // iter283 — Structured backend errors (400/403/422) ship a dict
        // body like { detail: { error, message_en, message_fr } }. Coerce
        // to a string toast so React/sonner doesn't try to render an
        // object and blow up the page.
        const _resp = createErr?.response;
        const _detail = _resp?.data?.detail;
        let _msg;
        if (typeof _detail === 'string') {
          _msg = _detail;
        } else if (_detail && typeof _detail === 'object') {
          const _isFr = (i18n.language || '').toLowerCase().startsWith('fr');
          _msg = (_isFr ? _detail.message_fr : _detail.message_en)
            || _detail.message_en
            || _detail.message_fr
            || _detail.error
            || JSON.stringify(_detail);
        } else {
          _msg = createErr?.message || 'Failed to create listing';
        }
        // 403 = broker partnership required.
        if (_resp?.status === 403) {
          toast.error(_msg || (i18n.language?.startsWith('fr')
            ? "Les annonces de véhicules nécessitent un partenariat courtier vérifié."
            : "Vehicle listings require verified broker partnership."));
        } else {
          toast.error(_msg);
        }
        setLoading(false);
        return; // ← Never navigate on error.
      }
      toast.success('Listing created! Uploading photos...');

      // Upload photos (in production, would use cloud storage)
      // For now, we'll simulate the upload.
      // iter283 — Wrap each upload in try/catch so ONE bad image doesn't
      // bring down the whole submit and leave the user on a blank page.
      let _photo_fail = 0;
      for (const [category, categoryPhotos] of Object.entries(photos)) {
        for (const photo of categoryPhotos) {
          try {
            const uploadFormData = new FormData();
            uploadFormData.append('file', photo.file);
            await axios.post(
              `${API}/vehicles/${vehicleId}/media?category=${category}`,
              uploadFormData,
              {
                headers: {
                  Authorization: `Bearer ${token}`,
                  'Content-Type': 'multipart/form-data'
                }
              }
            );
          } catch (uploadErr) {
            _photo_fail += 1;
            console.error('[CreateVehicle] photo upload failed:', uploadErr);
          }
        }
      }
      if (_photo_fail > 0) {
        toast.warning(`${_photo_fail} photo(s) failed to upload. You can add more from the listing detail page.`);
      }

      // iter198 — Pilot success celebration: confetti + warm toast on a pilot dealer's FIRST listing
      const isPilot = listingData.utm_source === 'pilot-welcome-banner';
      const isFirstListing = (sellerProfile?.total_listings || 0) === 0;
      if (isPilot && isFirstListing) {
        try {
          // Center burst
          confetti({
            particleCount: 120,
            spread: 75,
            origin: { y: 0.6 },
            colors: ['#06B6D4', '#2563EB', '#6366F1', '#FFFFFF'],
          });
          // Side bursts for extra polish
          setTimeout(() => confetti({ particleCount: 60, angle: 60, spread: 55, origin: { x: 0 } }), 250);
          setTimeout(() => confetti({ particleCount: 60, angle: 120, spread: 55, origin: { x: 1 } }), 400);
        } catch (_e) {}
        const isFr = (i18n?.language || 'en').toLowerCase().startsWith('fr');
        toast.success(
          isFr
            ? "🎉 Bravo ! Votre tout premier véhicule est en ligne. Bienvenue dans la famille BidVex Pilote."
            : "🎉 Congrats! Your very first vehicle is live. Welcome to the BidVex Pilot family.",
          { duration: 8000 }
        );
        // Clear the attribution flag so the celebration only fires once
        try { localStorage.removeItem('bidvex.utm_source'); } catch (_e) {}
      } else {
        toast.success('Vehicle listing created successfully!');
      }
      navigate(`/vehicle-dashboard`);
      
    } catch (error) {
      // iter283 — Same defense as the inner catch: coerce dict details
      // to a string toast so we never crash the page on submit.
      const _detail = error?.response?.data?.detail;
      let _msg;
      if (typeof _detail === 'string') {
        _msg = _detail;
      } else if (_detail && typeof _detail === 'object') {
        const _isFr = (i18n.language || '').toLowerCase().startsWith('fr');
        _msg = (_isFr ? _detail.message_fr : _detail.message_en)
          || _detail.message_en || _detail.message_fr || _detail.error
          || JSON.stringify(_detail);
      } else {
        _msg = error?.message || 'Failed to create listing';
      }
      toast.error(_msg);
    } finally {
      setLoading(false);
    }
  };

  // Navigation
  const nextStep = () => setCurrentStep(s => Math.min(s + 1, STEPS.length - 1));
  const prevStep = () => setCurrentStep(s => Math.max(s - 1, 0));

  // Progress
  const progress = ((currentStep + 1) / STEPS.length) * 100;

  // Render step content
  const renderStepContent = () => {
    switch (STEPS[currentStep].id) {
      case 'vin':
        return (
          <div className="space-y-6">
            {/* iter201 — Vehicle Category Grid (CEO 15-category taxonomy) */}
            <div className="space-y-2">
              <Label className="text-base font-semibold">
                {t('vehicleListing.category', 'Vehicle Category')} *
              </Label>
              <p className="text-sm text-slate-500">
                {t('vehicleListing.categoryHint', 'Pick the category that best matches your vehicle. "Vehicle Parts & Accessories" is open to all sellers — every other category requires a verified provincial dealer licence.')}
              </p>
              <VehicleCategoryGrid
                selectedCategoryId={formData.category_id}
                selectedSubcategoryId={formData.subcategory_id}
                onChange={(catId, subId) => {
                  setFormData((p) => ({ ...p, category_id: catId || '', subcategory_id: subId || '' }));
                }}
              />
            </div>

            {/* iter201 — Province-aware seller notice based on the listing's province */}
            {formData.location_province && (
              <ProvinceSellerNotice provinceCode={formData.location_province} />
            )}

            {/* VIN Input */}
            <div className="space-y-4">
              <div>
                <Label className="text-base font-semibold">{t('vehicleListing.vinNumber', 'Vehicle Identification Number (VIN)')}</Label>
                <p className="text-sm text-slate-500 mb-2">
                  {t('vehicleListing.vinPlaceholder', 'Enter the 17-character VIN to auto-fill vehicle information')}
                </p>
                <div className="flex gap-2">
                  <Input
                    value={formData.vin}
                    onChange={(e) => updateField('vin', e.target.value.toUpperCase())}
                    placeholder="e.g., 1HGBH41JXMN109186"
                    maxLength={17}
                    className="font-mono text-lg"
                    data-testid="vin-input"
                  />
                  <Button 
                    onClick={decodeVIN} 
                    disabled={vinLoading || formData.vin.length !== 17}
                    className="gap-2"
                  >
                    {vinLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Search className="h-4 w-4" />
                    )}
                    {t('vehicleListing.lookupVin', 'Decode')}
                  </Button>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  {formData.vin.length}/17 characters
                </p>
              </div>
            </div>
            
            {/* Basic Info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label>{t('vehicleListing.year', 'Year')} *</Label>
                <Input
                  type="number"
                  value={formData.year}
                  onChange={(e) => updateField('year', e.target.value)}
                  placeholder="2024"
                  min="1900"
                  max={new Date().getFullYear() + 1}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('vehicleListing.make', 'Make')} *</Label>
                <Input
                  value={formData.make}
                  onChange={(e) => updateField('make', e.target.value)}
                  placeholder={t('vehicleListing.makePlaceholder', 'Toyota')}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('vehicleListing.model', 'Model')} *</Label>
                <Input
                  value={formData.model}
                  onChange={(e) => updateField('model', e.target.value)}
                  placeholder={t('vehicleListing.modelPlaceholder', 'Camry')}
                />
              </div>
              <div className="space-y-2">
                <Label>Trim</Label>
                <Input
                  value={formData.trim}
                  onChange={(e) => updateField('trim', e.target.value)}
                  placeholder="XSE"
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label>{t('vehicleListing.bodyType', 'Body Type')} *</Label>
              <Select value={formData.body_type} onValueChange={(v) => updateField('body_type', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {BODY_TYPES.map(type => (
                    <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        );
        
      case 'specs':
        return (
          <div className="space-y-6">
            {/* Mileage */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Gauge className="h-4 w-4" /> {t('vehicleListing.mileage', 'Mileage (km)')} *
              </Label>
              <Input
                type="number"
                value={formData.mileage}
                onChange={(e) => updateField('mileage', e.target.value)}
                placeholder="50000"
              />
            </div>
            
            {/* Drivetrain */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Settings2 className="h-4 w-4" /> {t('vehicleListing.transmission', 'Transmission')} *
                </Label>
                <Select value={formData.transmission} onValueChange={(v) => updateField('transmission', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {TRANSMISSIONS.map(t => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Fuel className="h-4 w-4" /> {t('vehicleListing.fuelType', 'Fuel Type')} *
                </Label>
                <Select value={formData.fuel_type} onValueChange={(v) => updateField('fuel_type', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {FUEL_TYPES.map(f => (
                      <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label>{t('vehicleListing.driveType', 'Drivetrain')} *</Label>
                <Select value={formData.drivetrain} onValueChange={(v) => updateField('drivetrain', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {DRIVETRAINS.map(d => (
                      <SelectItem key={d.value} value={d.value}>{d.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            {/* Engine */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>{t('vehicleListing.engineSize', 'Engine Size (L)')}</Label>
                <Input
                  value={formData.engine_size}
                  onChange={(e) => updateField('engine_size', e.target.value)}
                  placeholder="2.5"
                />
              </div>
              <div className="space-y-2">
                <Label>{t('vehicleListing.cylinders', 'Cylinders')}</Label>
                <Input
                  type="number"
                  inputMode="numeric"
                  value={formData.cylinders}
                  onChange={(e) => updateField('cylinders', e.target.value)}
                  placeholder="4"
                />
              </div>
              <div className="space-y-2">
                <Label>{t('vehicleListing.horsepower', 'Horsepower')}</Label>
                <Input
                  type="number"
                  inputMode="numeric"
                  value={formData.horsepower}
                  onChange={(e) => updateField('horsepower', e.target.value)}
                  placeholder="200"
                />
              </div>
            </div>
            
            {/* Colors */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Palette className="h-4 w-4" /> {t('vehicleListing.exteriorColor', 'Exterior Color')} *
                </Label>
                <Input
                  value={formData.exterior_color}
                  onChange={(e) => updateField('exterior_color', e.target.value)}
                  placeholder="Pearl White"
                />
              </div>
              <div className="space-y-2">
                <Label>{t('vehicleListing.interiorColor', 'Interior Color')} *</Label>
                <Input
                  value={formData.interior_color}
                  onChange={(e) => updateField('interior_color', e.target.value)}
                  placeholder="Black Leather"
                />
              </div>
            </div>
            
            {/* Documentation */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Ownership Status *</Label>
                <Select value={formData.ownership_status} onValueChange={(v) => updateField('ownership_status', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="owned">Owned</SelectItem>
                    <SelectItem value="financed">{t("vehicleListing.financed")}</SelectItem>
                    <SelectItem value="leased">Leased</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Title Status *</Label>
                <Select value={formData.title_status} onValueChange={(v) => updateField('title_status', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="clean">Clean</SelectItem>
                    <SelectItem value="salvage">Salvage</SelectItem>
                    <SelectItem value="rebuilt">Rebuilt</SelectItem>
                    <SelectItem value="flood">Flood</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Lien Status *</Label>
                <Select value={formData.lien_status} onValueChange={(v) => updateField('lien_status', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="clear">Clear</SelectItem>
                    <SelectItem value="lien_exists">{t("vehicleListing.lienExists")}</SelectItem>
                    <SelectItem value="pending_release">{t("vehicleListing.pendingRelease")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* iter285 — Bug 4 — Provincial registration eligibility picker.
                Compliance requirement, not optional. Card pills + detail
                page surface these flags so buyers know whether they can
                register the vehicle in their home province. */}
            <VehicleProvinceEligibility
              value={formData.eligible_provinces}
              inspectionStatus={formData.inspection_status}
              onChange={({ eligible_provinces, inspection_status }) =>
                setFormData(prev => ({
                  ...prev,
                  eligible_provinces,
                  inspection_status,
                }))
              }
            />
          </div>
        );
        
      case 'condition':
        return (
          <div className="space-y-6">
            {/* Running Status */}
            <Card className="border-2">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <h3 className="font-semibold">Is the vehicle running?</h3>
                    <p className="text-sm text-slate-500">Does it start and drive?</p>
                  </div>
                  <div className="flex gap-4">
                    <Button
                      variant={formData.is_running ? 'default' : 'outline'}
                      onClick={() => updateField('is_running', true)}
                      className="gap-2"
                    >
                      <CheckCircle className="h-4 w-4" /> Yes
                    </Button>
                    <Button
                      variant={!formData.is_running ? 'destructive' : 'outline'}
                      onClick={() => updateField('is_running', false)}
                      className="gap-2"
                    >
                      <XCircle className="h-4 w-4" /> No
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Condition Ratings */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { key: 'engine_condition', label: 'Engine' },
                { key: 'transmission_condition', label: 'Transmission' },
                { key: 'brakes_condition', label: 'Brakes' },
                { key: 'suspension_condition', label: 'Suspension' },
                { key: 'body_condition', label: 'Body' },
                { key: 'paint_condition', label: 'Paint' },
                { key: 'interior_condition', label: 'Interior' },
                { key: 'tires_condition', label: 'Tires' },
              ].map(item => (
                <div key={item.key} className="space-y-2">
                  <Label>{item.label}</Label>
                  <Select value={formData[item.key]} onValueChange={(v) => updateField(item.key, v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {CONDITIONS.map(c => (
                        <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>
            
            {/* Damage History */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { key: 'has_accident_history', label: 'Accident History' },
                { key: 'has_flood_damage', label: 'Flood Damage' },
                { key: 'has_fire_damage', label: 'Fire Damage' },
                { key: 'has_frame_damage', label: 'Frame Damage' },
              ].map(item => (
                <div key={item.key} className="flex items-center space-x-2 p-4 bg-slate-50 rounded-lg">
                  <Checkbox
                    checked={formData[item.key]}
                    onCheckedChange={(checked) => updateField(item.key, checked)}
                  />
                  <Label className="cursor-pointer">{item.label}</Label>
                </div>
              ))}
            </div>
            
            {/* Notes */}
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t("vehicleListing.mechanicalNotes")}</Label>
                <Textarea
                  value={formData.mechanical_notes}
                  onChange={(e) => updateField('mechanical_notes', e.target.value)}
                  placeholder="Describe any mechanical issues or recent repairs..."
                  rows={4}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("vehicleListing.cosmeticNotes")}</Label>
                <Textarea
                  value={formData.cosmetic_notes}
                  onChange={(e) => updateField('cosmetic_notes', e.target.value)}
                  placeholder="Describe any scratches, dents, or cosmetic imperfections..."
                  rows={4}
                />
              </div>
            </div>
          </div>
        );
        
      case 'photos':
        return (
          <div className="space-y-6">
            {/* Photo Count */}
            <div className={`p-4 rounded-lg ${getTotalPhotos() >= 10 ? 'bg-green-50 border border-green-200' : 'bg-yellow-50 border border-yellow-200'}`}>
              <div className="flex items-center gap-2">
                {getTotalPhotos() >= 10 ? (
                  <CheckCircle className="h-5 w-5 text-green-600" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-yellow-600" />
                )}
                <span className="font-medium">
                  {getTotalPhotos()} / 10 {t('vehicleListing.photosUploaded', 'photos uploaded')} ({t('vehicleListing.minPhotos', 'minimum required')})
                </span>
              </div>
            </div>
            
            {/* Photo Categories */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {PHOTO_CATEGORIES.map(category => (
                <Card key={category.id} className={category.required ? 'border-blue-200' : ''}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <Label className="flex items-center gap-2">
                        {category.label}
                        {category.required && <Badge variant="outline" className="text-xs">Required</Badge>}
                      </Label>
                      <Badge>{photos[category.id]?.length || 0}</Badge>
                    </div>
                    
                    {/* Preview */}
                    {photos[category.id]?.length > 0 && (
                      <div className="flex gap-2 mb-3 flex-wrap">
                        {photos[category.id].map((photo, idx) => (
                          <div key={idx} className="relative w-16 h-16">
                            <img 
                              src={photo.preview} 
                              alt="" 
                              className="w-full h-full object-cover rounded"
                            />
                            <button
                              onClick={() => removePhoto(category.id, idx)}
                              className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-xs"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* Upload */}
                    <label className="block cursor-pointer">
                      <div className="border-2 border-dashed rounded-lg p-4 text-center hover:border-blue-400 transition-colors">
                        <Camera className="h-6 w-6 mx-auto text-slate-400 mb-1" />
                        <span className="text-sm text-slate-500">Click to upload</span>
                      </div>
                      <input
                        type="file"
                        accept="image/*"
                        multiple
                        className="hidden"
                        onChange={(e) => handlePhotoUpload(category.id, e.target.files)}
                      />
                    </label>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* iter286 — Bug 5 — Carfax / Inspection report inputs.
                Optional fields. Sellers paste a Carfax CA share URL OR
                an S3 URL to a previously-uploaded PDF. The documents are
                broker-gated on the buyer side via the dedicated endpoint
                /api/vehicle-auctions/{id}/carfax. */}
            <div
              data-testid="vehicle-carfax-step"
              className="space-y-3 p-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900/30"
            >
              <div>
                <Label className="text-sm font-semibold">Vehicle Documents (optional)</Label>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Documents are only visible to verified broker partners.
                  Individual buyers see a locked preview.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="carfax-url-input">Carfax / Vehicle History Report URL</Label>
                <Input
                  id="carfax-url-input"
                  data-testid="vehicle-carfax-url-input"
                  type="url"
                  value={formData.carfax_url}
                  onChange={(e) => updateField('carfax_url', e.target.value)}
                  placeholder="https://www.carfax.ca/VehicleHistory/..."
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="carfax-file-input">Carfax PDF (S3 / public URL)</Label>
                <Input
                  id="carfax-file-input"
                  data-testid="vehicle-carfax-file-input"
                  type="url"
                  value={formData.carfax_file}
                  onChange={(e) => updateField('carfax_file', e.target.value)}
                  placeholder="https://your-bucket.s3.amazonaws.com/.../carfax.pdf"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="inspection-file-input">Inspection / Safety Report PDF</Label>
                <Input
                  id="inspection-file-input"
                  data-testid="vehicle-inspection-file-input"
                  type="url"
                  value={formData.inspection_file}
                  onChange={(e) => updateField('inspection_file', e.target.value)}
                  placeholder="https://your-bucket.s3.amazonaws.com/.../inspection.pdf"
                />
              </div>
            </div>
          </div>
        );
        
      case 'auction':
        return (
          <div className="space-y-6">
            {/* Title & Description */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Listing Title (English) *</Label>
                <Input
                  data-testid="vehicle-title-en-input"
                  value={formData.title}
                  onChange={(e) => {
                    const v = e.target.value;
                    setFormData(prev => ({
                      ...prev,
                      title: v,
                      // iter285 — Auto-mirror to title_fr when it's empty OR
                      // when the seller hasn't customized it yet (still equals
                      // the previous English title). Sellers can edit FR
                      // independently after touching that field.
                      title_fr: (!prev.title_fr || prev.title_fr === prev.title) ? v : prev.title_fr,
                    }));
                  }}
                  placeholder="e.g., 2020 Toyota Camry XSE - Low Mileage, One Owner"
                />
              </div>

              {/* iter285 — French title field (Quebec Bill 96 compliance).
                  Required only when location_province === 'QC'. Auto-populated
                  with the English title so sellers can edit rather than retype. */}
              <div className="space-y-2">
                <Label>
                  Titre du véhicule (Français)
                  {(formData.location_province || '').toUpperCase() === 'QC' ? ' *' : ' (optional)'}
                </Label>
                <Input
                  data-testid="vehicle-title-fr-input"
                  value={formData.title_fr}
                  onChange={(e) => updateField('title_fr', e.target.value)}
                  placeholder="ex. 2020 Toyota Camry XSE - Faible kilométrage, un propriétaire"
                />
                {(formData.location_province || '').toUpperCase() === 'QC' && (
                  <p className="text-[11px] text-muted-foreground">
                    Requis pour les annonces québécoises (Charte de la langue française).
                    Peut être identique au titre anglais.
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label>Description (English) *</Label>
                <Textarea
                  data-testid="vehicle-description-en-input"
                  value={formData.description}
                  onChange={(e) => {
                    const v = e.target.value;
                    setFormData(prev => ({
                      ...prev,
                      description: v,
                      description_fr: (!prev.description_fr || prev.description_fr === prev.description) ? v : prev.description_fr,
                    }));
                  }}
                  placeholder="Describe your vehicle in detail..."
                  rows={5}
                />
              </div>

              {/* iter285 — French description (Quebec Bill 96 compliance). */}
              <div className="space-y-2">
                <Label>
                  Description (Français)
                  {(formData.location_province || '').toUpperCase() === 'QC' ? ' *' : ' (optional)'}
                </Label>
                <Textarea
                  data-testid="vehicle-description-fr-input"
                  value={formData.description_fr}
                  onChange={(e) => updateField('description_fr', e.target.value)}
                  placeholder="Décrivez votre véhicule en détail…"
                  rows={5}
                />
              </div>
            </div>
            
            {/* Location */}
            <LocationSelector
              value={{
                country: formData.location_country,
                region: formData.location_province,
                city: formData.location_city,
                postalCode: formData.location_postal_code,
              }}
              geoSuggestion={geo}
              onChange={({ country, region, city, postalCode }) => {
                setFormData(prev => ({
                  ...prev,
                  location_country: country,
                  location_province: region,
                  location_city: city,
                  location_postal_code: postalCode,
                }));
              }}
            />
            
            {/* Auction Type */}
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Auction Type *</Label>
                <Select value={formData.auction_type} onValueChange={(v) => updateField('auction_type', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="timed">{t("vehicleListing.timedAuction")}</SelectItem>
                    <SelectItem value="live">{t("vehicleListing.liveAuction")}</SelectItem>
                    <SelectItem value="buy_now">{t("vehicleListing.buyNowOnly")}</SelectItem>
                    <SelectItem value="timed_with_buy_now">Timed + Buy Now</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Visibility *</Label>
                <Select value={formData.visibility} onValueChange={(v) => updateField('visibility', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="public">Public (Everyone)</SelectItem>
                    <SelectItem value="dealer_only">{t("vehicleListing.dealersOnly")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            {/* Timing */}
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Calendar className="h-4 w-4" /> Start Time *
                </Label>
                <Input
                  type="datetime-local"
                  value={formData.start_time}
                  onChange={(e) => updateField('start_time', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>End Time *</Label>
                <Input
                  type="datetime-local"
                  value={formData.end_time}
                  onChange={(e) => updateField('end_time', e.target.value)}
                />
              </div>
            </div>
            
            {/* Pricing */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <DollarSign className="h-4 w-4" /> {t('vehicleListing.startingPrice', 'Starting Price')} *
                </Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  value={formData.starting_price}
                  onChange={(e) => updateField('starting_price', e.target.value)}
                  placeholder="25000"
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label>{t('vehicleListing.reservePrice', 'Reserve Price')}</Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  value={formData.reserve_price}
                  onChange={(e) => updateField('reserve_price', e.target.value)}
                  placeholder="Optional"
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label>{t('vehicleListing.buyNowPrice', 'Buy Now Price')}</Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  value={formData.buy_now_price}
                  onChange={(e) => updateField('buy_now_price', e.target.value)}
                  placeholder="Optional"
                  className="min-h-[48px]"
                />
              </div>
              <div className="space-y-2">
                <Label>{t('vehicleListing.bidIncrement', 'Bid Increment')}</Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  value={formData.bid_increment}
                  onChange={(e) => updateField('bid_increment', e.target.value)}
                  placeholder="100"
                  className="min-h-[48px]"
                />
              </div>
            </div>
            
            {/* Currency Selector (Spec Global Rule 1) */}
            <div className="space-y-2 p-4 bg-slate-50 rounded-lg" data-testid="vehicle-currency-section">
              <Label>{t('createListing.currencyLabel')}</Label>
              <div className="flex gap-2" data-testid="vehicle-currency-selector">
                {['CAD', 'USD'].map((cur) => (
                  <button
                    key={cur}
                    type="button"
                    onClick={() => updateField('currency', cur)}
                    className={`flex-1 py-2.5 px-4 rounded-lg border-2 text-sm font-semibold transition-all ${
                      formData.currency === cur
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-slate-200 text-slate-500 hover:border-slate-300'
                    }`}
                    data-testid={`vehicle-currency-${cur.toLowerCase()}`}
                  >
                    {cur === 'CAD' ? '🇨🇦 CAD' : '🇺🇸 USD'}
                  </button>
                ))}
              </div>
              <p className="text-xs text-slate-500">
                {t('createListing.currencyImmutableWarn')}
              </p>
            </div>

            {/* iter194 — Auction Access Type (Public vs Licensed Only) */}
            <div className="space-y-2 p-4 bg-slate-50 rounded-lg" data-testid="vehicle-auction-access-section">
              <Label className="text-sm font-semibold">{t('vehicleDealer.auctionAccessTitle')}</Label>
              <p className="text-xs text-slate-500">{t('vehicleDealer.auctionAccessDesc')}</p>
              <div className="grid grid-cols-1 gap-2 mt-2">
                {[
                  { v: 'public_individual', label: t('vehicleDealer.accessPublic'), desc: t('vehicleDealer.accessPublicDesc') },
                  { v: 'licensed_only',     label: t('vehicleDealer.accessLicensed'), desc: t('vehicleDealer.accessLicensedDesc') },
                ].map((opt) => (
                  <label
                    key={opt.v}
                    className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${formData.auction_access === opt.v ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}
                  >
                    <input
                      type="radio"
                      name="vehicle_auction_access"
                      value={opt.v}
                      checked={formData.auction_access === opt.v}
                      onChange={(e) => updateField('auction_access', e.target.value)}
                      data-testid={`vehicle-access-${opt.v.replace('_', '-')}`}
                      className="mt-0.5"
                    />
                    <div>
                      <span className="font-medium text-sm">{opt.label}</span>
                      <p className="text-xs text-slate-500 mt-0.5">{opt.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* iter194 — Vehicle Start/Run Status */}
            <div className="space-y-2 p-4 bg-slate-50 rounded-lg" data-testid="vehicle-run-status-section">
              <Label className="text-sm font-semibold">{t('vehicleDealer.runStatusTitle')}</Label>
              <p className="text-xs text-slate-500">{t('vehicleDealer.runStatusDesc')}</p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-2">
                {[
                  { v: 'run_and_drive',   label: t('vehicleDealer.runDrive'),       desc: t('vehicleDealer.runDriveDesc'),       icon: '🟢' },
                  { v: 'starts_only',     label: t('vehicleDealer.startsOnly'),     desc: t('vehicleDealer.startsOnlyDesc'),     icon: '🟡' },
                  { v: 'non_operational', label: t('vehicleDealer.nonOperational'), desc: t('vehicleDealer.nonOperationalDesc'), icon: '🔴' },
                ].map((opt) => (
                  <label
                    key={opt.v}
                    className={`flex flex-col gap-1 p-3 rounded-lg border cursor-pointer transition-colors ${formData.run_status === opt.v ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="vehicle_run_status"
                        value={opt.v}
                        checked={formData.run_status === opt.v}
                        onChange={(e) => updateField('run_status', e.target.value)}
                        data-testid={`vehicle-run-${opt.v.replace(/_/g, '-')}`}
                      />
                      <span className="text-xl">{opt.icon}</span>
                      <span className="font-medium text-sm">{opt.label}</span>
                    </div>
                    <p className="text-xs text-slate-500 ml-6">{opt.desc}</p>
                  </label>
                ))}
              </div>
            </div>

            {/* iter194 — Direct Transaction Policy notice (replaces payment method picker) */}
            <div className="p-4 rounded-lg border-2 border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800" data-testid="vehicle-direct-transaction-notice">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-sm text-amber-900 dark:text-amber-200 mb-1">
                    {t('vehicleDealer.directTransactionTitle')}
                  </p>
                  <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
                    {t('vehicleDealer.directTransactionBody')}
                  </p>
                </div>
              </div>
            </div>

            {/* iter482 P4B — Seller-Controlled Accepted Payment Methods multi-select */}
            <div className="space-y-3 p-4 bg-slate-50 rounded-lg">
              <AcceptedPaymentMethodsSelector
                value={acceptedPaymentMethods}
                onChange={setAcceptedPaymentMethods}
                isFrench={i18n.language === 'fr'}
              />
            </div>

            {/* Deposit (Spec Feature 1) */}
            <div className="space-y-3 p-4 bg-slate-50 rounded-lg" data-testid="vehicle-deposit-section">
              <Label>{t('createListing.bidderDepositLabel')}</Label>
              <div className="grid grid-cols-1 gap-2">
                <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer ${!formData.requires_deposit ? 'border-blue-500 bg-blue-50' : 'border-slate-200'}`}>
                  <input type="radio" name="vehicle_deposit_required" checked={!formData.requires_deposit} onChange={() => updateField('requires_deposit', false)} data-testid="vehicle-deposit-none" />
                  <div>
                    <span className="font-medium text-sm">{t('createListing.bidderNoDeposit')}</span>
                  </div>
                </label>
                <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer ${formData.requires_deposit ? 'border-blue-500 bg-blue-50' : 'border-slate-200'}`}>
                  <input type="radio" name="vehicle_deposit_required" checked={formData.requires_deposit} onChange={() => updateField('requires_deposit', true)} data-testid="vehicle-deposit-required" />
                  <div>
                    <span className="font-medium text-sm">{t('createListing.bidderRequireDeposit')}</span>
                    <p className="text-xs text-slate-500">{t('createListing.bidderRequireDepositHelpVehicle')}</p>
                  </div>
                </label>
              </div>
              {formData.requires_deposit && (
                <div className="space-y-3" data-testid="vehicle-deposit-amount-block">
                  <div className="flex gap-2">
                    <button type="button" onClick={() => updateField('deposit_type', 'fixed')} className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${formData.deposit_type === 'fixed' ? 'bg-blue-600 text-white' : 'bg-white border border-slate-300 text-slate-700'}`} data-testid="vehicle-deposit-type-fixed">{t('createListing.depositTypeFixed')}</button>
                    <button type="button" onClick={() => updateField('deposit_type', 'percentage')} className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${formData.deposit_type === 'percentage' ? 'bg-blue-600 text-white' : 'bg-white border border-slate-300 text-slate-700'}`} data-testid="vehicle-deposit-type-percentage">{t('createListing.depositTypePercent')}</button>
                  </div>
                  <Input
                    type="number"
                    inputMode="decimal"
                    value={formData.deposit_amount}
                    onChange={(e) => updateField('deposit_amount', e.target.value)}
                    placeholder={formData.deposit_type === 'fixed' ? `${t('createListing.depositPlaceholderFixed')} ${formData.currency}` : t('createListing.depositPlaceholderPercent')}
                    data-testid="vehicle-deposit-amount-input"
                  />
                </div>
              )}
            </div>
          </div>
        );
        
      case 'review':
        return (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Car className="h-5 w-5" /> Vehicle Info
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p><strong>VIN:</strong> {formData.vin}</p>
                  <p><strong>Year:</strong> {formData.year}</p>
                  <p><strong>Make/Model:</strong> {formData.make} {formData.model} {formData.trim}</p>
                  <p><strong>Mileage:</strong> {formData.mileage} km</p>
                  <p><strong>Title:</strong> {formData.title_status}</p>
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <DollarSign className="h-5 w-5" /> Auction Settings
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p><strong>Starting Price:</strong> ${formData.starting_price}</p>
                  {formData.reserve_price && <p><strong>Reserve:</strong> ${formData.reserve_price}</p>}
                  {formData.buy_now_price && <p><strong>Buy Now:</strong> ${formData.buy_now_price}</p>}
                  <p><strong>Location:</strong> {formData.location_city}, {formData.location_province} {formData.location_postal_code}</p>
                  <p><strong>Photos:</strong> {getTotalPhotos()}</p>
                </CardContent>
              </Card>
            </div>
            
            {/* Warnings */}
            {getTotalPhotos() < 10 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-red-500 mt-0.5" />
                <div>
                  <p className="font-medium text-red-700">Missing Required Photos</p>
                  <p className="text-sm text-red-600">You need at least 10 photos. Current: {getTotalPhotos()}</p>
                </div>
              </div>
            )}
            
            {/* Legal Notice */}
            <Card className="bg-yellow-50 border-yellow-200">
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <Shield className="h-5 w-5 text-yellow-600 mt-0.5" />
                  <div className="text-sm text-yellow-700">
                    <p className="font-medium mb-2">Seller Acknowledgment</p>
                    <p>By submitting this listing, you confirm that:</p>
                    <ul className="list-disc list-inside mt-2 space-y-1">
                      <li>{t("vehicleListing.infoAccurate")}</li>
                      <li>{t("vehicleListing.legalAuthority")}</li>
                      <li>{t("vehicleListing.respondPromptly")}</li>
                      <li>You agree to BidVex's seller terms and conditions</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        );
        
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="create-vehicle-listing-page">
      {/* iter427 — Dealer verification gate. Renders inline with a
         clear "Verify Dealer" CTA when the seller is not approved
         or is suspended, replacing the previous silent redirect. */}
      {sellerProbe.loaded && (
        sellerProbe.noProfile
        || user?.vehicle_dealer_suspended
        || (sellerProfile && sellerProfile.verification_status !== 'approved')
      ) && (
        <DealerVerificationGate
          sellerProfile={sellerProfile}
          noProfile={sellerProbe.noProfile}
          suspended={!!user?.vehicle_dealer_suspended}
          surfaceLabel="vehicle listing"
        />
      )}

      {/* The form body only renders once the seller is verified. */}
      {sellerProbe.loaded
       && !sellerProbe.noProfile
       && !user?.vehicle_dealer_suspended
       && sellerProfile
       && sellerProfile.verification_status === 'approved' && (
      <>
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                {t('vehicleListing.title', 'List Your Vehicle')}
              </h1>
              <p className="text-slate-500 mt-1">
                {t('vehicleListing.subtitle', 'Create a professional vehicle auction listing')}
              </p>
            </div>
            {/* iter313 — Universal Save-as-Draft visible at every step */}
            <SaveAsDraftButton
              type="vehicle"
              formData={formData}
              draftId={formData.draft_id || null}
              onSaved={(id) => setFormData((p) => ({ ...p, draft_id: id }))}
            />
          </div>
          
          {/* Progress */}
          <div className="mt-6">
            <div className="flex justify-between mb-2 overflow-x-auto gap-1 pb-1">
              {STEPS.map((step, index) => {
                const Icon = step.icon;
                return (
                  <div 
                    key={step.id}
                    className={`flex items-center gap-1 md:gap-2 text-sm shrink-0 ${
                      index <= currentStep ? 'text-blue-600' : 'text-slate-400'
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                      index < currentStep ? 'bg-blue-600 text-white' :
                      index === currentStep ? 'bg-blue-100 text-blue-600 border-2 border-blue-600' :
                      'bg-slate-100'
                    }`}>
                      {index < currentStep ? (
                        <CheckCircle className="h-5 w-5" />
                      ) : (
                        <Icon className="h-4 w-4" />
                      )}
                    </div>
                    <span className="hidden lg:inline text-xs">{step.title}</span>
                  </div>
                );
              })}
            </div>
            <Progress value={progress} className="h-2" />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {React.createElement(STEPS[currentStep].icon, { className: "h-5 w-5" })}
              {STEPS[currentStep].title}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <AnimatePresence mode="wait">
              <motion.div
                key={currentStep}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                {renderStepContent()}
              </motion.div>
            </AnimatePresence>
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex flex-col-reverse sm:flex-row justify-between gap-3 mt-6">
          <Button
            variant="outline"
            onClick={prevStep}
            disabled={currentStep === 0}
            className="w-full sm:w-auto gap-2 min-h-[48px]"
          >
            <ChevronLeft className="h-4 w-4" /> {t('vehicleListing.previous', 'Previous')}
          </Button>
          
          {currentStep < STEPS.length - 1 ? (
            <Button onClick={nextStep} className="w-full sm:w-auto gap-2 min-h-[48px]">
              {t('vehicleListing.next', 'Next')} <ChevronRight className="h-4 w-4" />
            </Button>
          ) : (
            /* iter292 — Directive 3: Three explicit lifecycle buttons so
               dealers control whether a freshly-created vehicle listing
               is hidden (Draft), publicly visible with a countdown
               (Schedule / Upcoming), or open for bidding immediately
               (Go Live Now). */
            <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
              <Button
                variant="outline"
                onClick={() => handleSubmit('draft')}
                disabled={loading || getTotalPhotos() < 10}
                className="w-full sm:w-auto gap-2 min-h-[48px]"
                data-testid="submit-listing-draft-btn"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {t('vehicleListing.saveAsDraft', 'Save as Draft')}
              </Button>
              <Button
                variant="outline"
                onClick={() => handleSubmit('schedule')}
                disabled={loading || getTotalPhotos() < 10}
                className="w-full sm:w-auto gap-2 min-h-[48px] border-blue-600 text-blue-700 hover:bg-blue-50"
                data-testid="submit-listing-schedule-btn"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calendar className="h-4 w-4" />}
                {t('vehicleListing.scheduleUpcoming', 'Schedule (Upcoming)')}
              </Button>
              <Button
                onClick={() => handleSubmit('live')}
                disabled={loading || getTotalPhotos() < 10}
                className="w-full sm:w-auto gap-2 bg-green-600 hover:bg-green-700 min-h-[48px]"
                data-testid="submit-listing-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> {t('vehicleListing.submitting', 'Creating...')}
                  </>
                ) : (
                  <>
                    <CheckCircle className="h-4 w-4" /> {t('vehicleListing.goLiveNow', 'Go Live Now')}
                  </>
                )}
              </Button>
            </div>
          )}
        </div>
      </div>
      {/* iter201 — Phase 2 — Bilingual legal footer (CEO Part 4) */}
      <VehicleLegalFooter />
      </>
      )}
    </div>
  );
};

export default CreateVehicleListingPage;
