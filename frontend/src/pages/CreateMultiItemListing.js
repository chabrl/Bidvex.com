import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { 
  Plus, Trash2, Upload, Loader2, ChevronLeft, ChevronRight, 
  FileText, Image as ImageIcon, CheckCircle, AlertCircle, Edit2,
  Calendar as CalendarIcon, Truck, Clock, MapPin as MapPinIcon, RefreshCcw, 
  Building2, DollarSign, Shield, AlertTriangle
} from 'lucide-react';
import Papa from 'papaparse';
import { useDropzone } from 'react-dropzone';
import RichTextEditor from '../components/RichTextEditor';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CreateMultiItemListing = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { canCreateMultiLot } = useFeatureFlags();
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  
  // Step 1: Basic Info
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    location: '',
    city: '',
    region: '',
    auction_end_date: '',
    currency: user?.preferred_currency || 'CAD',
    increment_option: 'tiered', // tiered or simplified
  });

  // Step 2: Lots
  const [numLots, setNumLots] = useState(1); // Number of lots to generate
  const [currentPage, setCurrentPage] = useState(1); // Pagination for lots
  const lotsPerPage = 10;
  
  const [lots, setLots] = useState([{
    lot_number: 1,
    title: '',
    description: '',
    quantity: 1,
    starting_price: '',
    current_price: '',
    condition: 'good',
    images: [],
    pricing_mode: 'multiplied', // fixed or multiplied
    buy_now_enabled: false,
    buy_now_price: ''
  }]);

  // Step 5: Promotion Selection
  const [promotionTier, setPromotionTier] = useState('standard'); // 'standard', 'premium', 'elite'
  const [promotionPaymentComplete, setPromotionPaymentComplete] = useState(false);

  const [uploadMethod, setUploadMethod] = useState('manual'); // 'manual', 'csv', 'images'
  const [csvData, setCsvData] = useState(null);
  const [bulkImages, setBulkImages] = useState([]);
  const [validationErrors, setValidationErrors] = useState({});

  // Step 4: Documents, Shipping, Visit, Auction Terms
  const [documents, setDocuments] = useState({
    terms_conditions: null, // {filename, content_type, base64_content}
    important_info: null,
    catalogue: null
  });
  const [auctionTerms, setAuctionTerms] = useState({
    en: '',
    fr: ''
  });
  const [activeTermsLang, setActiveTermsLang] = useState('en'); // 'en' or 'fr'
  
  const [shippingInfo, setShippingInfo] = useState({
    available: false,
    methods: [], // ['local_pickup', 'standard', 'express']
    rates: {}, // {local_pickup: 0, standard: 25, express: 50}
    delivery_time: '' // e.g., "3-5 business days"
  });
  
  const [visitAvailability, setVisitAvailability] = useState({
    offered: false,
    dates: '', // e.g., "Nov 15-20, 2025"
    instructions: '' // Additional instructions for scheduling
  });

  // NEW: Seller Obligations State
  const [sellerObligations, setSellerObligations] = useState({
    // Dynamic Currency Exchange
    customExchangeRate: '', // Seller enters manually (e.g., "1.42")
    // Logistics
    providesShipping: 'no', // 'yes' or 'no'
    shippingDetails: '',
    // Removal Deadline
    removalDeadline: '',
    removalDeadlineDays: '7',
    // Site Capabilities - Basic
    facilityAddress: '',
    hasTailgateAccess: false,
    hasForkliftAvailable: false,
    // Site Capabilities - Professional
    hasLoadingDock: false,
    loadingDockType: '', // 'high' or 'standard'
    hasOverheadCrane: false,
    craneCapacity: '', // in tons
    groundLevelLoadingOnly: false,
    hasScaleOnSite: false,
    authorizedPersonnelOnly: false,
    safetyRequirements: '', // e.g., "Hard hat, safety vest required"
    additionalSiteNotes: '', // e.g., "Enter through Gate 4"
    // Refund Policy
    refundPolicy: 'non_refundable', // 'non_refundable' or 'refundable'
    refundTerms: '',
    // Agreement Confirmation
    sellerAgreementConfirmed: false
  });

  // Visit date validation error
  const [visitDateError, setVisitDateError] = useState('');

  useEffect(() => {
    // Check if user can create multi-lot auctions based on feature flag
    if (user && !canCreateMultiLot(user)) {
      toast.error(t('createListing.restrictedToBusinessAccounts', 'Multi-lot auctions are restricted to business accounts. Please upgrade your account or contact support.'));
      navigate('/seller/dashboard');
    }
    fetchCategories();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setFormData(prev => ({ ...prev, auction_end_date: tomorrow.toISOString().slice(0, 16) }));
  }, [user, canCreateMultiLot, navigate]);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  // Step 1 Handlers
  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  // Step 2 - Manual Lot Entry
  const handleLotChange = (index, field, value) => {
    const updatedLots = [...lots];
    updatedLots[index][field] = value;
    setLots(updatedLots);
    validateLot(index, updatedLots[index]);
  };

  const addLot = () => {
    if (lots.length >= 500) {
      toast.error(t('createListing.maxLotsReached', 'Maximum 500 lots allowed per listing'));
      return;
    }
    setLots([...lots, {
      lot_number: lots.length + 1,
      title: '',
      description: '',
      quantity: 1,
      starting_price: '',
      current_price: '',
      condition: 'good',
      images: [],
      buy_now_enabled: false,
      buy_now_price: ''
    }]);
  };

  const removeLot = (index) => {
    const updatedLots = lots.filter((_, i) => i !== index);
    updatedLots.forEach((lot, i) => { lot.lot_number = i + 1; });
    setLots(updatedLots);
  };

  // Generate specified number of lots
  const generateLots = (count) => {
    if (count < 1 || count > 500) {
      toast.error(t('createListing.invalidLotCount', 'Please enter a number between 1 and 500'));
      return;
    }
    
    const newLots = Array.from({ length: count }, (_, i) => ({
      lot_number: i + 1,
      title: '',
      description: '',
      quantity: 1,
      starting_price: '',
      current_price: '',
      condition: 'good',
      images: [],
      pricing_mode: 'multiplied',
      buy_now_enabled: false,
      buy_now_price: ''
    }));
    
    setLots(newLots);
    setCurrentPage(1); // Reset to first page
    toast.success(`Generated ${count} lot${count > 1 ? 's' : ''}`);
  };

  const handleLotImageUpload = (index, e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => {
      if (file.size > 5000000) {
        toast.error('Image size should be less than 5MB');
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const updatedLots = [...lots];
        updatedLots[index].images = [...updatedLots[index].images, reader.result];
        setLots(updatedLots);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeLotImage = (lotIndex, imageIndex) => {
    const updatedLots = [...lots];
    updatedLots[lotIndex].images = updatedLots[lotIndex].images.filter((_, i) => i !== imageIndex);
    setLots(updatedLots);
  };

  // CSV Upload Handler
  const handleCSVUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const parsedLots = results.data.map((row, index) => {
          const imageUrls = row.image_urls ? row.image_urls.split(',').map(url => url.trim()) : [];
          return {
            lot_number: index + 1,
            title: row.title || '',
            description: row.description || '',
            quantity: parseInt(row.quantity) || 1,
            starting_price: parseFloat(row.starting_bid) || '',
            current_price: parseFloat(row.starting_bid) || '',
            condition: 'good',
            images: imageUrls
          };
        });

        if (parsedLots.length > 500) {
          toast.error(`CSV contains ${parsedLots.length} lots. Maximum 500 allowed.`);
          setLots(parsedLots.slice(0, 500));
        } else {
          setLots(parsedLots);
          toast.success(`Loaded ${parsedLots.length} lots from CSV`);
        }
        setCsvData(results.data);
      },
      error: (error) => {
        toast.error('Failed to parse CSV: ' + error.message);
      }
    });
  };

  // Bulk Image Upload with Drag and Drop
  const onDrop = (acceptedFiles) => {
    const imageFiles = acceptedFiles.filter(file => 
      file.type.startsWith('image/') && 
      ['.jpg', '.jpeg', '.png', '.webp'].some(ext => file.name.toLowerCase().endsWith(ext))
    );

    if (imageFiles.length !== acceptedFiles.length) {
      toast.error('Some files were rejected. Only .jpg, .png, .webp allowed');
    }

    imageFiles.forEach(file => {
      if (file.size > 5000000) {
        toast.error(`${file.name} is too large. Max 5MB per image.`);
        return;
      }

      const reader = new FileReader();
      reader.onload = () => {
        setBulkImages(prev => [...prev, { 
          name: file.name, 
          data: reader.result,
          matched: false,
          lotIndex: null
        }]);
      };
      reader.readAsDataURL(file);
    });
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp']
    },
    multiple: true
  });

  // Auto-match images to lots
  const autoMatchImages = () => {
    const updatedLots = [...lots];
    let matchCount = 0;

    bulkImages.forEach((img, imgIndex) => {
      const fileName = img.name.toLowerCase().replace(/\.(jpg|jpeg|png|webp)$/i, '');
      
      // Try to find matching lot
      const lotIndex = updatedLots.findIndex(lot => {
        const lotTitle = lot.title.toLowerCase().trim();
        // Match by exact title or by keyword extraction
        return lotTitle === fileName || 
               fileName.includes(lotTitle) || 
               lotTitle.includes(fileName) ||
               // Match patterns like "item1" to "Item 1"
               fileName.replace(/[^a-z0-9]/g, '') === lotTitle.replace(/[^a-z0-9]/g, '');
      });

      if (lotIndex !== -1 && !updatedLots[lotIndex].images.includes(img.data)) {
        updatedLots[lotIndex].images = [...updatedLots[lotIndex].images, img.data];
        bulkImages[imgIndex].matched = true;
        bulkImages[imgIndex].lotIndex = lotIndex;
        matchCount++;
      }
    });

    setLots(updatedLots);
    setBulkImages([...bulkImages]);
    toast.success(`Auto-matched ${matchCount} images to lots`);
  };

  // Manual image assignment
  const assignImageToLot = (imageIndex, lotIndex) => {
    const updatedLots = [...lots];
    const image = bulkImages[imageIndex];
    
    if (!updatedLots[lotIndex].images.includes(image.data)) {
      updatedLots[lotIndex].images = [...updatedLots[lotIndex].images, image.data];
      bulkImages[imageIndex].matched = true;
      bulkImages[imageIndex].lotIndex = lotIndex;
      setLots(updatedLots);
      setBulkImages([...bulkImages]);
      toast.success('Image assigned');
    }
  };

  // Validation
  const validateLot = (index, lot) => {
    const errors = {};
    
    if (lot.starting_price && (parseFloat(lot.starting_price) < 1 || parseFloat(lot.starting_price) > 10000)) {
      errors.starting_price = t('createListing.startingPriceRange', 'Starting bid must be between 1 and 10,000 CAD');
    }
    
    if (lot.description && (lot.description.length < 20 || lot.description.length > 500)) {
      errors.description = t('createListing.descriptionLength', 'Description must be 20-500 characters');
    }
    
    if (lot.quantity && (!Number.isInteger(parseFloat(lot.quantity)) || parseFloat(lot.quantity) < 1)) {
      errors.quantity = t('createListing.quantityPositive', 'Quantity must be a positive integer');
    }

    // Buy Now price validation: must be at least 20% higher than starting price
    if (lot.buy_now_enabled && lot.buy_now_price && lot.starting_price) {
      const startingPrice = parseFloat(lot.starting_price);
      const buyNowPrice = parseFloat(lot.buy_now_price);
      const minBuyNowPrice = startingPrice * 1.2; // 20% higher
      
      if (buyNowPrice < minBuyNowPrice) {
        errors.buy_now_price = t('createListing.buyNowMinPrice', `Buy Now price must be at least $${minBuyNowPrice.toFixed(2)} (20% above starting price)`, { price: minBuyNowPrice.toFixed(2) });
      }
    }

    setValidationErrors(prev => ({ ...prev, [index]: errors }));
    return Object.keys(errors).length === 0;
  };

  const validateStep = (step) => {
    if (step === 1) {
      if (!formData.title || !formData.description || !formData.category || 
          !formData.city || !formData.region || !formData.location || !formData.auction_end_date) {
        toast.error(t('createListing.fillRequired', 'Please fill all required fields'));
        return false;
      }
      return true;
    }
    
    if (step === 2) {
      if (lots.length === 0) {
        toast.error(t('createListing.addOneLot', 'Please add at least one lot'));
        return false;
      }

      // Validate all lots
      let allValid = true;
      lots.forEach((lot, index) => {
        if (!validateLot(index, lot)) {
          allValid = false;
        }
      });

      if (!allValid) {
        toast.error(t('createListing.fixValidationErrors', 'Please fix validation errors in lots'));
        return false;
      }

      return true;
    }

    if (step === 3) {
      // Step 3 is the review step - no additional validation needed
      // Just ensure optional fields have default values
      return true;
    }

    // Step 4 validation: Visit date and Seller Agreement
    if (step === 4) {
      // Validate visit date if offered
      if (visitAvailability.offered) {
        if (!visitAvailability.dates) {
          toast.error('Please select an inspection date');
          return false;
        }
        
        const visitDate = new Date(visitAvailability.dates);
        const auctionEndDate = new Date(formData.auction_end_date);
        
        if (visitDate >= auctionEndDate) {
          toast.error('Inspection dates must occur while the auction is active');
          return false;
        }
      }
      
      // Validate Seller Obligations
      if (!sellerObligations.customExchangeRate || parseFloat(sellerObligations.customExchangeRate) <= 0) {
        toast.error('Please enter a valid custom exchange rate');
        return false;
      }
      
      if (!sellerObligations.providesShipping) {
        toast.error('Please select a shipping/logistics option');
        return false;
      }
      
      if (sellerObligations.providesShipping === 'yes' && !sellerObligations.shippingDetails.trim()) {
        toast.error('Please provide shipping details');
        return false;
      }
      
      if (!sellerObligations.facilityAddress.trim()) {
        toast.error('Please enter a facility address');
        return false;
      }
      
      if (sellerObligations.refundPolicy === 'refundable' && !sellerObligations.refundTerms.trim()) {
        toast.error('Please specify refund terms');
        return false;
      }
      
      if (!sellerObligations.sellerAgreementConfirmed) {
        toast.error('Please confirm the Seller Commitment to proceed');
        return false;
      }
      
      return true;
    }

    return true;
  };

  // Navigation
  const goToNextStep = () => {
    if (validateStep(currentStep)) {
      if (currentStep === 2 && lots.length > 500) {
        toast.error('Maximum 500 lots allowed');
        return;
      }
      setCurrentStep(prev => Math.min(prev + 1, 5));
    }
  };

  const goToPrevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  // Submit
  const handleSubmit = async () => {
    if (!validateStep(2)) return;

    setLoading(true);
    const lotsData = lots.map(lot => ({
      ...lot,
      starting_price: parseFloat(lot.starting_price),
      current_price: parseFloat(lot.starting_price),
      quantity: parseInt(lot.quantity),
      buy_now_enabled: lot.buy_now_enabled || false,
      buy_now_price: lot.buy_now_enabled && lot.buy_now_price ? parseFloat(lot.buy_now_price) : null,
      available_quantity: parseInt(lot.quantity),
      sold_quantity: 0,
      lot_status: 'active'
    }));

    try {
      const payload = {
        ...formData,
        auction_end_date: new Date(formData.auction_end_date).toISOString(),
        lots: lotsData,
        documents: {
          terms_conditions: documents.terms_conditions,
          important_info: documents.important_info,
          catalogue: documents.catalogue
        },
        shipping_info: shippingInfo.available ? shippingInfo : null,
        visit_availability: visitAvailability.offered ? {
          ...visitAvailability,
          dates: visitAvailability.dates // Now in YYYY-MM-DD format
        } : null,
        // Seller Obligations - Complete
        seller_obligations: {
          // Dynamic Currency Exchange
          custom_exchange_rate: parseFloat(sellerObligations.customExchangeRate) || null,
          // Logistics
          provides_shipping: sellerObligations.providesShipping,
          shipping_details: sellerObligations.shippingDetails,
          // Removal Deadline
          removal_deadline_days: parseInt(sellerObligations.removalDeadlineDays),
          removal_deadline_custom: sellerObligations.removalDeadline,
          // Basic Facility
          facility_address: sellerObligations.facilityAddress,
          has_tailgate_access: sellerObligations.hasTailgateAccess,
          has_forklift_available: sellerObligations.hasForkliftAvailable,
          // Professional Facility
          has_loading_dock: sellerObligations.hasLoadingDock,
          loading_dock_type: sellerObligations.loadingDockType,
          has_overhead_crane: sellerObligations.hasOverheadCrane,
          crane_capacity: sellerObligations.craneCapacity ? parseFloat(sellerObligations.craneCapacity) : null,
          ground_level_loading_only: sellerObligations.groundLevelLoadingOnly,
          has_scale_on_site: sellerObligations.hasScaleOnSite,
          authorized_personnel_only: sellerObligations.authorizedPersonnelOnly,
          safety_requirements: sellerObligations.safetyRequirements,
          additional_site_notes: sellerObligations.additionalSiteNotes,
          // Refund Policy
          refund_policy: sellerObligations.refundPolicy,
          refund_terms: sellerObligations.refundTerms,
          // Agreement
          agreement_confirmed: sellerObligations.sellerAgreementConfirmed,
          agreement_timestamp: new Date().toISOString()
        },
        auction_terms_en: auctionTerms.en || null,
        auction_terms_fr: auctionTerms.fr || null,
        // Promotion tier
        promotion_tier: promotionTier !== 'standard' ? promotionTier : null,
        is_promoted: promotionTier !== 'standard'
      };
      const response = await axios.post(`${API}/multi-item-listings`, payload);
      toast.success(t('createListing.listingCreated'));
      navigate(`/multi-item-listing/${response.data.id}`);
    } catch (error) {
      console.error('Failed:', error);
      toast.error(error.response?.data?.detail || t('createListing.createFailed', 'Failed to create listing'));
    } finally {
      setLoading(false);
    }
  };

  // Render Step Indicator
  const StepIndicator = () => (
    <div className="flex items-center justify-center mb-8">
      {[1, 2, 3, 4, 5].map(step => (
        <React.Fragment key={step}>
          <div className={`flex items-center justify-center w-10 h-10 rounded-full font-semibold transition-all ${
            step === currentStep 
              ? 'bg-gradient-to-r from-[#009BFF] to-[#0056A6] text-white scale-110' 
              : step < currentStep 
                ? 'bg-green-500 text-white' 
                : 'bg-gray-200 dark:bg-gray-700 text-gray-500'
          }`}>
            {step < currentStep ? <CheckCircle className="h-5 w-5" /> : step}
          </div>
          {step < 5 && (
            <div className={`w-16 h-1 mx-2 ${
              step < currentStep ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'
            }`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );

  // Render steps
  const renderStep1 = () => (
    <div className="space-y-4">
      <h3 className="text-xl font-semibold mb-4">{t('createListing.stepLabels.basic')}</h3>
      <div className="space-y-2">
        <Label htmlFor="title">{t('createListing.auctionTitle')} *</Label>
        <Input 
          id="title" 
          name="title" 
          value={formData.title} 
          onChange={handleChange} 
          placeholder="e.g., Estate Sale - Furniture Collection"
          required 
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="description">{t('createListing.description')} *</Label>
        <Textarea 
          id="description" 
          name="description" 
          value={formData.description} 
          onChange={handleChange} 
          rows={4} 
          placeholder={t('createListing.descriptionPlaceholder')}
          required 
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="category">{t('createListing.category')} *</Label>
          <select 
            id="category" 
            name="category" 
            value={formData.category} 
            onChange={handleChange} 
            required 
            className="w-full px-3 py-2 border border-input rounded-md bg-background"
          >
            <option value="">{t('createListing.selectCategory')}</option>
            {categories.map(cat => (
              <option key={cat.id} value={cat.name_en}>{cat.name_en}</option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="auction_end_date">{t('createListing.auctionEndDate')} *</Label>
          <Input 
            id="auction_end_date" 
            name="auction_end_date" 
            type="datetime-local" 
            value={formData.auction_end_date} 
            onChange={handleChange} 
            required 
          />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="space-y-2">
          <Label htmlFor="city">{t('createListing.city')} *</Label>
          <Input 
            id="city" 
            name="city" 
            value={formData.city} 
            onChange={handleChange} 
            placeholder={t('createListing.cityPlaceholder', 'e.g., Montreal')}
            required 
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="region">{t('createListing.region')} *</Label>
          <Input 
            id="region" 
            name="region" 
            value={formData.region} 
            onChange={handleChange} 
            placeholder={t('createListing.regionPlaceholder', 'e.g., Quebec')}
            required 
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="location">{t('createListing.location')} *</Label>
          <Input 
            id="location" 
            name="location" 
            value={formData.location} 
            onChange={handleChange} 
            placeholder={t('createListing.locationPlaceholder', 'e.g., 123 Main St')}
            required 
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="currency" className="flex items-center gap-2">
          💱 {t('createListing.currency')}
          {user?.currency_locked && (
            <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
              🔒 {t('currency.locked')}
            </span>
          )}
        </Label>
        <select
          id="currency"
          name="currency"
          value={formData.currency}
          onChange={handleChange}
          className="w-full px-3 py-2 border border-input rounded-md bg-background"
          disabled={user?.currency_locked}
        >
          <option value="CAD">🇨🇦 CAD (Canadian Dollar)</option>
          <option value="USD">🇺🇸 USD (US Dollar)</option>
        </select>
        <p className="text-sm text-muted-foreground">
          All prices in this auction will be in {formData.currency}. {formData.currency === 'CAD' ? 'GST and QST taxes will apply.' : 'No GST/QST for USD auctions.'}
          {user?.currency_locked && (
            <span className="block mt-2 text-blue-600">
              💡 Currency is set based on your location for tax compliance.
            </span>
          )}
        </p>
      </div>
      
      {/* Bid Increment Option */}
      <div className="space-y-2">
        <Label htmlFor="increment_option" className="flex items-center gap-2">
          📊 {t('createListing.incrementSchedule')}
        </Label>
        <select
          id="increment_option"
          name="increment_option"
          value={formData.increment_option}
          onChange={handleChange}
          className="w-full px-3 py-2 border border-input rounded-md bg-background"
        >
          <option value="tiered">{t('createListing.tiered')}</option>
          <option value="simplified">{t('createListing.simplified')}</option>
        </select>
        <div className="p-4 bg-gray-50 rounded-md border border-gray-200 text-sm">
          {formData.increment_option === 'tiered' ? (
            <div>
              <p className="font-semibold mb-2">Tiered Schedule:</p>
              <ul className="space-y-1 text-muted-foreground">
                <li>• $0-$99.99 → $5 increment</li>
                <li>• $100-$499.99 → $10 increment</li>
                <li>• $500-$999.99 → $25 increment</li>
                <li>• $1,000-$4,999.99 → $50 increment</li>
                <li>• $5,000-$9,999.99 → $100 increment</li>
                <li>• $10,000+ → Larger increments</li>
              </ul>
            </div>
          ) : (
            <div>
              <p className="font-semibold mb-2">Simplified Schedule:</p>
              <ul className="space-y-1 text-muted-foreground">
                <li>• $0-$100 → $1 increment</li>
                <li>• $100-$1,000 → $5 increment</li>
                <li>• $1,000-$10,000 → $25 increment</li>
                <li>• $10,000+ → $100 increment</li>
              </ul>
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          This determines the minimum bid increment buyers must follow. You can change this for each auction.
        </p>
      </div>
      
      {/* Number of Lots */}
      <div className="space-y-2 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <Label htmlFor="numLots" className="flex items-center gap-2 text-lg font-semibold">
          🧩 {t('createListing.numberOfLots')}
        </Label>
        <p className="text-sm text-muted-foreground mb-2">
          Specify how many lots you want in this auction. Lot rows will be auto-generated as you type.
        </p>
        <div className="flex gap-2 items-center">
          <Input 
            id="numLots" 
            type="number"
            min="1"
            max="500"
            value={numLots} 
            onChange={(e) => {
              const value = parseInt(e.target.value) || 1;
              setNumLots(value);
              // Auto-generate lots when valid number is entered
              if (value > 0 && value <= 500) {
                generateLots(value);
              }
            }} 
            placeholder="e.g., 280"
            className="w-32"
          />
          <span className="text-sm text-muted-foreground">
            {lots.length > 0 ? `✓ ${lots.length} lot${lots.length > 1 ? 's' : ''} ready` : 'Enter number to generate'}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          💡 Max 500 lots per auction. Lots will be displayed 10 per page in Step 2 for easy editing.
        </p>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-semibold">{t('createListing.stepLabels.lots')} ({lots.length}/500)</h3>
        {lots.length >= 450 && lots.length < 500 && (
          <div className="flex items-center text-amber-500">
            <AlertCircle className="h-4 w-4 mr-1" />
            <span className="text-sm">Approaching 500-lot limit</span>
          </div>
        )}
        {lots.length >= 500 && (
          <div className="flex items-center text-red-500">
            <AlertCircle className="h-4 w-4 mr-1" />
            <span className="text-sm font-semibold">500-lot limit reached</span>
          </div>
        )}
      </div>

      {/* Upload Method Selection */}
      <Card className="border-2 border-dashed">
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4 mb-4">
            <Button
              type="button"
              variant={uploadMethod === 'manual' ? 'default' : 'outline'}
              onClick={() => setUploadMethod('manual')}
              className={uploadMethod === 'manual' ? 'gradient-button text-white' : ''}
            >
              <Edit2 className="mr-2 h-4 w-4" />
              {t('createListing.manual')}
            </Button>
            <Button
              type="button"
              variant={uploadMethod === 'csv' ? 'default' : 'outline'}
              onClick={() => setUploadMethod('csv')}
              className={uploadMethod === 'csv' ? 'gradient-button text-white' : ''}
            >
              <FileText className="mr-2 h-4 w-4" />
              {t('createListing.csvUpload')}
            </Button>
            <Button
              type="button"
              variant={uploadMethod === 'images' ? 'default' : 'outline'}
              onClick={() => setUploadMethod('images')}
              className={uploadMethod === 'images' ? 'gradient-button text-white' : ''}
            >
              <ImageIcon className="mr-2 h-4 w-4" />
              {t('createListing.imagesBulk')}
            </Button>
          </div>

          {uploadMethod === 'csv' && (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Upload a CSV file with columns: <code>title, description, quantity, starting_bid, image_urls</code>
              </p>
              <input
                type="file"
                accept=".csv"
                onChange={handleCSVUpload}
                className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>
          )}

          {uploadMethod === 'images' && (
            <div className="space-y-4">
              <div {...getRootProps()} className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isDragActive ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/10' : 'border-gray-300'
              }`}>
                <input {...getInputProps()} />
                <Upload className="mx-auto h-12 w-12 text-gray-400 mb-2" />
                <p className="text-sm text-muted-foreground">
                  {isDragActive ? 'Drop images here...' : 'Drag & drop images, or click to select'}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Supports .jpg, .png, .webp (max 5MB each)
                </p>
              </div>

              {bulkImages.length > 0 && (
                <>
                  <Button type="button" onClick={autoMatchImages} variant="outline" className="w-full">
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Auto-Match Images to Lots
                  </Button>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 max-h-64 overflow-y-auto">
                    {bulkImages.map((img, idx) => (
                      <div key={idx} className="relative group">
                        <img src={img.data} alt={img.name} className="w-full h-24 object-cover rounded" />
                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded p-1 flex flex-col justify-between">
                          <p className="text-white text-xs truncate">{img.name}</p>
                          {img.matched ? (
                            <span className="text-green-400 text-xs">✓ Lot {img.lotIndex + 1}</span>
                          ) : (
                            <select
                              onChange={(e) => assignImageToLot(idx, parseInt(e.target.value))}
                              className="text-xs bg-white/90 rounded px-1"
                            >
                              <option value="">Assign...</option>
                              {lots.map((lot, lotIdx) => (
                                <option key={lotIdx} value={lotIdx}>Lot {lot.lot_number}</option>
                              ))}
                            </select>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Lots List */}
      <div className="space-y-4">
        <Button 
          type="button" 
          onClick={addLot} 
          variant="outline" 
          className="w-full"
          disabled={lots.length >= 500}
        >
          <Plus className="mr-2 h-4 w-4" /> Add Another Lot
        </Button>

        {/* Pagination Controls */}
        {lots.length > lotsPerPage && (
          <div className="flex items-center justify-between bg-gray-50 p-3 rounded-lg border">
            <div className="text-sm text-muted-foreground">
              Showing lots {((currentPage - 1) * lotsPerPage) + 1} to {Math.min(currentPage * lotsPerPage, lots.length)} of {lots.length}
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}
              >
                ← Previous
              </Button>
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.ceil(lots.length / lotsPerPage) }, (_, i) => i + 1)
                  .filter(page => {
                    // Show first 2, last 2, and current +/- 1
                    return page <= 2 || page > Math.ceil(lots.length / lotsPerPage) - 2 || 
                           Math.abs(page - currentPage) <= 1;
                  })
                  .map((page, idx, arr) => (
                    <React.Fragment key={page}>
                      {idx > 0 && arr[idx - 1] !== page - 1 && <span className="px-1">...</span>}
                      <Button
                        type="button"
                        variant={page === currentPage ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setCurrentPage(page)}
                        className={page === currentPage ? 'gradient-button text-white' : ''}
                      >
                        {page}
                      </Button>
                    </React.Fragment>
                  ))}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(Math.min(Math.ceil(lots.length / lotsPerPage), currentPage + 1))}
                disabled={currentPage >= Math.ceil(lots.length / lotsPerPage)}
              >
                Next →
              </Button>
            </div>
          </div>
        )}

        <div className="space-y-4 pr-2">
          {lots.slice((currentPage - 1) * lotsPerPage, currentPage * lotsPerPage).map((lot, displayIndex) => {
            const actualIndex = (currentPage - 1) * lotsPerPage + displayIndex;
            return (
            <Card key={actualIndex} className="border-2" data-lot-index={actualIndex}>
              <CardContent className="pt-6 space-y-4">
                <div className="flex justify-between items-start">
                  <h4 className="font-semibold text-lg">Lot {lot.lot_number}</h4>
                  {lots.length > 1 && (
                    <Button 
                      type="button" 
                      variant="ghost" 
                      size="sm" 
                      onClick={() => removeLot(actualIndex)}
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{t('createListing.lotTitle')} *</Label>
                    <Input 
                      value={lot.title} 
                      onChange={(e) => handleLotChange(actualIndex, 'title', e.target.value)} 
                      placeholder={t('createListing.lotTitlePlaceholder')}
                      required 
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('createListing.quantity')} *</Label>
                    <Input 
                      type="number" 
                      min="1" 
                      step="1"
                      value={lot.quantity} 
                      onChange={(e) => handleLotChange(actualIndex, 'quantity', e.target.value)} 
                      required 
                    />
                    {validationErrors[actualIndex]?.quantity && (
                      <p className="text-red-500 text-xs">{validationErrors[actualIndex].quantity}</p>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>{t('createListing.lotDescription')} * (20-500 {t('createListing.characters', 'characters')})</Label>
                  <Textarea 
                    value={lot.description} 
                    onChange={(e) => handleLotChange(actualIndex, 'description', e.target.value)} 
                    rows={2}
                    placeholder={t('createListing.lotDescPlaceholder')}
                    required 
                  />
                  <div className="flex justify-between text-xs">
                    <span className={
                      lot.description.length < 20 || lot.description.length > 500 
                        ? 'text-red-500' 
                        : 'text-green-500'
                    }>
                      {lot.description.length} characters
                    </span>
                    {validationErrors[actualIndex]?.description && (
                      <p className="text-red-500">{validationErrors[actualIndex].description}</p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{t('createListing.startingPrice')} ({formData.currency}) * (1-10,000)</Label>
                    <Input 
                      type="number" 
                      step="0.01" 
                      min="1"
                      max="10000"
                      value={lot.starting_price} 
                      onChange={(e) => handleLotChange(actualIndex, 'starting_price', e.target.value)} 
                      required 
                    />
                    {validationErrors[actualIndex]?.starting_price && (
                      <p className="text-red-500 text-xs">{validationErrors[actualIndex].starting_price}</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label>{t('createListing.condition')}</Label>
                    <select 
                      value={lot.condition} 
                      onChange={(e) => handleLotChange(actualIndex, 'condition', e.target.value)} 
                      className="w-full px-3 py-2 border border-input rounded-md bg-background"
                    >
                      <option value="new">{t('createListing.conditionNew')}</option>
                      <option value="like_new">{t('createListing.conditionLikeNew')}</option>
                      <option value="good">{t('createListing.conditionGood')}</option>
                      <option value="fair">{t('createListing.conditionFair')}</option>
                      <option value="poor">{t('createListing.conditionPoor')}</option>
                    </select>
                  </div>
                </div>

                {/* Buy Now Price Section */}
                <div className="p-4 border-2 border-dashed border-cyan-300 dark:border-cyan-700 rounded-lg bg-cyan-50 dark:bg-cyan-900/20">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">⚡</span>
                      <Label className="text-base font-semibold text-cyan-800 dark:text-cyan-200">{t('createListing.buyNowOption')}</Label>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={lot.buy_now_enabled || false}
                        onChange={(e) => handleLotChange(actualIndex, 'buy_now_enabled', e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-cyan-300 dark:peer-focus:ring-cyan-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-[#06B6D4]"></div>
                    </label>
                  </div>
                  
                  {lot.buy_now_enabled && (
                    <div className="space-y-2">
                      <Label className="text-sm">{t('createListing.buyNowPrice')} ($) *</Label>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">$</span>
                        <Input 
                          type="number" 
                          step="0.01" 
                          min={lot.starting_price ? (parseFloat(lot.starting_price) * 1.2).toFixed(2) : '1'}
                          value={lot.buy_now_price || ''} 
                          onChange={(e) => handleLotChange(actualIndex, 'buy_now_price', e.target.value)} 
                          placeholder={lot.starting_price ? `Min: $${(parseFloat(lot.starting_price) * 1.2).toFixed(2)}` : 'Enter starting price first'}
                          className="flex-1"
                        />
                      </div>
                      {validationErrors[actualIndex]?.buy_now_price && (
                        <p className="text-red-500 text-xs">{validationErrors[actualIndex].buy_now_price}</p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        ℹ️ Buy Now price must be at least 20% higher than starting bid to protect auction integrity.
                      </p>
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Images</Label>
                  <input 
                    type="file" 
                    accept="image/*" 
                    multiple 
                    onChange={(e) => handleLotImageUpload(actualIndex, e)} 
                    className="hidden" 
                    id={`lot-image-${actualIndex}`} 
                  />
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={() => document.getElementById(`lot-image-${actualIndex}`).click()} 
                    className="w-full"
                  >
                    <Upload className="mr-2 h-4 w-4" /> Upload Images
                  </Button>
                  {lot.images.length > 0 && (
                    <div className="grid grid-cols-3 gap-2 mt-2">
                      {lot.images.map((img, imgIdx) => (
                        <div key={imgIdx} className="relative aspect-square rounded-lg overflow-hidden bg-gray-100">
                          <img src={img} alt="" className="w-full h-full object-cover" />
                          <button 
                            type="button" 
                            onClick={() => removeLotImage(actualIndex, imgIdx)} 
                            className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 text-xs hover:bg-red-600"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
            );
          })}
        </div>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div className="space-y-6">
      <h3 className="text-xl font-semibold">{t('createListing.reviewSubmit')}</h3>
      
      {/* Summary */}
      <Card className="bg-gradient-to-r from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 border-blue-200">
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-blue-600">{lots.length}</p>
              <p className="text-sm text-muted-foreground">{t('createListing.totalLots')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-600">
                {lots.reduce((sum, lot) => sum + parseInt(lot.quantity || 0), 0)}
              </p>
              <p className="text-sm text-muted-foreground">{t('createListing.totalItems')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-600">
                ${lots.reduce((sum, lot) => sum + parseFloat(lot.starting_price || 0), 0).toFixed(2)}
              </p>
              <p className="text-sm text-muted-foreground">{t('createListing.totalValue')}</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-600">
                {lots.reduce((sum, lot) => sum + (lot.images?.length || 0), 0)}
              </p>
              <p className="text-sm text-muted-foreground">{t('createListing.totalImages')}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Auction Details Review */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Auction Details
            <Button type="button" variant="ghost" size="sm" onClick={() => setCurrentStep(1)}>
              <Edit2 className="h-4 w-4 mr-1" /> Edit
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div><strong>Title:</strong> {formData.title}</div>
          <div><strong>Category:</strong> {formData.category}</div>
          <div><strong>Location:</strong> {formData.city}, {formData.region}</div>
          <div><strong>End Date:</strong> {new Date(formData.auction_end_date).toLocaleString()}</div>
        </CardContent>
      </Card>

      {/* Lots Preview Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Lots Preview
            <Button type="button" variant="ghost" size="sm" onClick={() => setCurrentStep(2)}>
              <Edit2 className="h-4 w-4 mr-1" /> Edit
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted sticky top-0">
                <tr>
                  <th className="p-2 text-left">#</th>
                  <th className="p-2 text-left">Title</th>
                  <th className="p-2 text-left">Qty</th>
                  <th className="p-2 text-left">Starting Bid</th>
                  <th className="p-2 text-left">Condition</th>
                  <th className="p-2 text-left">Images</th>
                </tr>
              </thead>
              <tbody>
                {lots.map((lot, index) => (
                  <tr key={index} className="border-t">
                    <td className="p-2">{lot.lot_number}</td>
                    <td className="p-2 font-medium">{lot.title}</td>
                    <td className="p-2">{lot.quantity}</td>
                    <td className="p-2">${parseFloat(lot.starting_price).toFixed(2)}</td>
                    <td className="p-2 capitalize">{lot.condition.replace('_', ' ')}</td>
                    <td className="p-2">{lot.images?.length || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  // Step 4: Documents, Shipping, Visit, & Seller Obligations
  const renderStep4 = () => {
    // Validate visit date against auction end date
    const validateVisitDate = (dateValue) => {
      if (!dateValue || !formData.auction_end_date) {
        setVisitDateError('');
        return true;
      }
      
      const visitDate = new Date(dateValue);
      const auctionEndDate = new Date(formData.auction_end_date);
      
      if (visitDate >= auctionEndDate) {
        setVisitDateError('Inspection dates must occur while the auction is active.');
        return false;
      }
      
      setVisitDateError('');
      return true;
    };

    // Get maximum allowed date for visit (day before auction ends)
    const getMaxVisitDate = () => {
      if (!formData.auction_end_date) return '';
      const endDate = new Date(formData.auction_end_date);
      endDate.setDate(endDate.getDate() - 1);
      return endDate.toISOString().split('T')[0];
    };

    // Get minimum date (today)
    const getMinVisitDate = () => {
      return new Date().toISOString().split('T')[0];
    };

    const handleFileUpload = async (docType, event) => {
      const file = event.target.files[0];
      if (!file) return;

      // Validate file size (10MB)
      if (file.size > 10 * 1024 * 1024) {
        toast.error('File too large. Maximum size is 10MB');
        return;
      }

      // Validate file type
      const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg'];
      if (!allowedTypes.includes(file.type)) {
        toast.error('Invalid file type. Please upload PDF, PNG, or JPG');
        return;
      }

      // Convert to base64
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64 = reader.result.split(',')[1];
        setDocuments(prev => ({
          ...prev,
          [docType]: {
            filename: file.name,
            content_type: file.type,
            base64_content: base64
          }
        }));
        toast.success(`${file.name} uploaded successfully`);
      };
      reader.readAsDataURL(file);
    };

    return (
      <div className="space-y-8">
        <h3 className="text-2xl font-semibold">Documents, Shipping & Visit Options</h3>

        {/* Documents Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Upload Documents (Optional)
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Upload PDFs or images (max 10MB each). These will be available to buyers.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Terms & Conditions */}
            <div>
              <Label>{t('createListing.termsConditions')}</Label>
              <div className="flex items-center gap-2 mt-2">
                <Input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => handleFileUpload('terms_conditions', e)}
                  className="flex-1"
                />
                {documents.terms_conditions && (
                  <span className="text-sm text-green-600 flex items-center gap-1">
                    <CheckCircle className="h-4 w-4" />
                    {documents.terms_conditions.filename}
                  </span>
                )}
              </div>
            </div>

            {/* Important Information */}
            <div>
              <Label>{t('createListing.importantInfo')}</Label>
              <div className="flex items-center gap-2 mt-2">
                <Input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => handleFileUpload('important_info', e)}
                  className="flex-1"
                />
                {documents.important_info && (
                  <span className="text-sm text-green-600 flex items-center gap-1">
                    <CheckCircle className="h-4 w-4" />
                    {documents.important_info.filename}
                  </span>
                )}
              </div>
            </div>

            {/* Catalogue */}
            <div>
              <Label>Catalogue</Label>
              <div className="flex items-center gap-2 mt-2">
                <Input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => handleFileUpload('catalogue', e)}
                  className="flex-1"
                />
                {documents.catalogue && (
                  <span className="text-sm text-green-600 flex items-center gap-1">
                    <CheckCircle className="h-4 w-4" />
                    {documents.catalogue.filename}
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Shipping Section */}
        <Card>
          <CardHeader>
            <CardTitle>{t('createListing.shipping')}</CardTitle>
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
              <Label htmlFor="shipping-available">{t("createListing.offerShipping")}</Label>
            </div>

            {shippingInfo.available && (
              <div className="space-y-4 ml-6 p-4 border rounded-lg">
                <div>
                  <Label>{t('createListing.shippingMethods')}</Label>
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
                  <Label>{t('createListing.deliveryTime')}</Label>
                  <Input
                    placeholder="e.g., 3-5 business days"
                    value={shippingInfo.delivery_time}
                    onChange={(e) => setShippingInfo(prev => ({ ...prev, delivery_time: e.target.value }))}
                  />
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Visit Before Auction Section - REDESIGNED */}
        <Card className="border-2 border-amber-200 dark:border-amber-700">
          <CardHeader className="bg-amber-50 dark:bg-amber-900/20">
            <CardTitle className="flex items-center gap-2 text-amber-800 dark:text-amber-300">
              <CalendarIcon className="h-5 w-5" />
              Visit Before Auction (Pre-Inspection)
            </CardTitle>
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Allow buyers to inspect items before bidding. Dates must be scheduled during the active auction period.
            </p>
          </CardHeader>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="visit-offered"
                checked={visitAvailability.offered}
                onChange={(e) => setVisitAvailability(prev => ({ ...prev, offered: e.target.checked }))}
                className="w-5 h-5 accent-amber-500"
              />
              <Label htmlFor="visit-offered" className="text-base font-medium cursor-pointer">
                Allow buyers to schedule a visit?
              </Label>
            </div>

            {visitAvailability.offered && (
              <div className="space-y-4 ml-6 p-4 border-2 border-amber-100 dark:border-amber-800 rounded-lg bg-white dark:bg-slate-800">
                {/* Date Picker - Date Only (No Time) */}
                <div className="space-y-2">
                  <Label className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                    <CalendarIcon className="h-4 w-4 text-amber-600" />
                    Inspection Date *
                  </Label>
                  <Input
                    type="date"
                    value={visitAvailability.dates}
                    onChange={(e) => {
                      setVisitAvailability(prev => ({ ...prev, dates: e.target.value }));
                      validateVisitDate(e.target.value);
                    }}
                    min={getMinVisitDate()}
                    max={getMaxVisitDate()}
                    className={`w-full text-lg font-medium ${
                      visitDateError 
                        ? 'border-red-500 focus:ring-red-500 focus:border-red-500' 
                        : 'border-amber-300 focus:ring-amber-500 focus:border-amber-500'
                    }`}
                    required={visitAvailability.offered}
                  />
                  
                  {/* Date Validation Error */}
                  {visitDateError && (
                    <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-lg">
                      <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0" />
                      <p className="text-sm font-medium text-red-700 dark:text-red-300">
                        {visitDateError}
                      </p>
                    </div>
                  )}

                  {/* Helper Text */}
                  {!visitDateError && formData.auction_end_date && (
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      ℹ️ Auction ends: {new Date(formData.auction_end_date).toLocaleDateString()}. 
                      Inspection must be scheduled before this date.
                    </p>
                  )}
                </div>

                {/* Instructions */}
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-900 dark:text-white">
                    Visit Instructions
                  </Label>
                  <Textarea
                    placeholder="Provide instructions for scheduling (e.g., contact info, time slots, what to expect)..."
                    value={visitAvailability.instructions}
                    onChange={(e) => setVisitAvailability(prev => ({ ...prev, instructions: e.target.value }))}
                    rows={3}
                    className="border-amber-200 focus:ring-amber-500 focus:border-amber-500"
                  />
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* =========================================== */}
        {/* CONSOLIDATED SELLER AGREEMENT BLOCK */}
        {/* =========================================== */}
        <Card className="border-2 border-blue-300 dark:border-blue-700 shadow-lg">
          <CardHeader className="bg-gradient-to-r from-blue-50 to-slate-50 dark:from-blue-900/30 dark:to-slate-900/30">
            <CardTitle className="flex items-center gap-2 text-blue-800 dark:text-blue-300 text-xl">
              <Shield className="h-6 w-6" />
              Seller Obligations & Agreement
            </CardTitle>
            <p className="text-sm text-blue-700 dark:text-blue-400">
              Complete the following mandatory information to list your auction.
            </p>
          </CardHeader>
          <CardContent className="space-y-6 pt-6">
            
            {/* Dynamic Currency Exchange - Manual Input */}
            <div className="space-y-3">
              <Label className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                <DollarSign className="h-4 w-4 text-green-600" />
                Custom Exchange Rate (Cross-Border Sales) *
              </Label>
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border-2 border-green-200 dark:border-green-700">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-medium text-slate-700 dark:text-slate-300">1 USD =</span>
                  <Input
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="e.g., 1.42"
                    value={sellerObligations.customExchangeRate}
                    onChange={(e) => setSellerObligations(prev => ({ ...prev, customExchangeRate: e.target.value }))}
                    className="w-32 text-lg font-bold text-center border-2 border-green-400 focus:ring-green-500 focus:border-green-500"
                    required
                  />
                  <span className="font-medium text-slate-700 dark:text-slate-300">CAD</span>
                </div>
                <p className="text-xs text-green-700 dark:text-green-400 mt-3">
                  ⚠️ Enter the rate you will use for this transaction. <strong>This rate will be locked once the auction goes live.</strong>
                </p>
              </div>
            </div>

            {/* Logistics - Shipping/Rigging */}
            <div className="space-y-3">
              <Label className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                <Truck className="h-4 w-4 text-blue-600" />
                Logistics (Shipping/Rigging) *
              </Label>
              <select
                value={sellerObligations.providesShipping}
                onChange={(e) => setSellerObligations(prev => ({ ...prev, providesShipping: e.target.value }))}
                className="w-full px-4 py-3 border-2 border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-medium focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
              >
                <option value="">-- Select Option --</option>
                <option value="yes">Yes - Seller Provides Shipping/Rigging</option>
                <option value="no">No - Buyer Responsible for Pickup</option>
              </select>
              
              {sellerObligations.providesShipping === 'yes' && (
                <Textarea
                  placeholder="Provide shipping details, costs, carriers used, rigging capabilities..."
                  value={sellerObligations.shippingDetails}
                  onChange={(e) => setSellerObligations(prev => ({ ...prev, shippingDetails: e.target.value }))}
                  rows={3}
                  className="border-blue-200 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              )}
            </div>

            {/* Removal Deadline */}
            <div className="space-y-3">
              <Label className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                <Clock className="h-4 w-4 text-orange-600" />
                Deadline for Item Removal *
              </Label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-600 dark:text-slate-400">Items must be picked up within</span>
                  <select
                    value={sellerObligations.removalDeadlineDays}
                    onChange={(e) => setSellerObligations(prev => ({ ...prev, removalDeadlineDays: e.target.value }))}
                    className="px-3 py-2 border-2 border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 font-medium focus:ring-2 focus:ring-blue-500"
                    required
                  >
                    <option value="3">3 days</option>
                    <option value="5">5 days</option>
                    <option value="7">7 days</option>
                    <option value="10">10 days</option>
                    <option value="14">14 days</option>
                    <option value="30">30 days</option>
                  </select>
                  <span className="text-sm text-slate-600 dark:text-slate-400">of auction close</span>
                </div>
                <Input
                  type="text"
                  placeholder="Or specify custom deadline..."
                  value={sellerObligations.removalDeadline}
                  onChange={(e) => setSellerObligations(prev => ({ ...prev, removalDeadline: e.target.value }))}
                  className="border-slate-300 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* =========================================== */}
            {/* EXPANDED FACILITY DETAILS - Professional */}
            {/* =========================================== */}
            <div className="space-y-4">
              <Label className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white text-lg">
                <Building2 className="h-5 w-5 text-purple-600" />
                Professional Facility Details
              </Label>
              
              <div className="space-y-4 p-5 bg-purple-50 dark:bg-purple-900/20 rounded-xl border-2 border-purple-200 dark:border-purple-700">
                {/* Facility Address */}
                <div className="space-y-2">
                  <Label className="text-sm font-medium text-slate-700 dark:text-slate-300">{t('createListing.facilityAddress')} *</Label>
                  <Input
                    placeholder={t('createListing.facilityAddressPlaceholder', 'Enter pickup/facility address...')}
                    value={sellerObligations.facilityAddress}
                    onChange={(e) => setSellerObligations(prev => ({ ...prev, facilityAddress: e.target.value }))}
                    className="border-purple-300 focus:ring-purple-500 focus:border-purple-500"
                    required
                  />
                </div>

                {/* Professional Facility Options - Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3">
                  
                  {/* Loading Dock */}
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-purple-200 dark:border-purple-700">
                    <label className="flex items-center gap-2 cursor-pointer mb-2">
                      <input
                        type="checkbox"
                        checked={sellerObligations.hasLoadingDock}
                        onChange={(e) => setSellerObligations(prev => ({ ...prev, hasLoadingDock: e.target.checked }))}
                        className="w-5 h-5 accent-purple-600"
                      />
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        🚚 {t('createListing.loadingDock')}
                      </span>
                    </label>
                    {sellerObligations.hasLoadingDock && (
                      <select
                        value={sellerObligations.loadingDockType}
                        onChange={(e) => setSellerObligations(prev => ({ ...prev, loadingDockType: e.target.value }))}
                        className="w-full mt-2 px-3 py-2 text-sm border rounded-lg bg-purple-50 dark:bg-slate-700"
                      >
                        <option value="">{t('createListing.selectDockType')}</option>
                        <option value="high">{t('createListing.highDock')}</option>
                        <option value="standard">{t('createListing.standardDock')}</option>
                        <option value="adjustable">{t('createListing.adjustableDock')}</option>
                      </select>
                    )}
                  </div>

                  {/* Overhead Crane */}
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-purple-200 dark:border-purple-700">
                    <label className="flex items-center gap-2 cursor-pointer mb-2">
                      <input
                        type="checkbox"
                        checked={sellerObligations.hasOverheadCrane}
                        onChange={(e) => setSellerObligations(prev => ({ ...prev, hasOverheadCrane: e.target.checked }))}
                        className="w-5 h-5 accent-purple-600"
                      />
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        🏗️ {t('createListing.overheadCrane')}
                      </span>
                    </label>
                    {sellerObligations.hasOverheadCrane && (
                      <Input
                        type="number"
                        placeholder={t('createListing.craneCapacity')}
                        value={sellerObligations.craneCapacity}
                        onChange={(e) => setSellerObligations(prev => ({ ...prev, craneCapacity: e.target.value }))}
                        className="mt-2 text-sm"
                      />
                    )}
                  </div>

                  {/* Ground Level Loading */}
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-purple-200 dark:border-purple-700">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={sellerObligations.groundLevelLoadingOnly}
                        onChange={(e) => setSellerObligations(prev => ({ ...prev, groundLevelLoadingOnly: e.target.checked }))}
                        className="w-5 h-5 accent-purple-600"
                      />
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        📦 {t('createListing.groundLevel')}
                      </span>
                    </label>
                  </div>

                  {/* Scale on Site */}
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-purple-200 dark:border-purple-700">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={sellerObligations.hasScaleOnSite}
                        onChange={(e) => setSellerObligations(prev => ({ ...prev, hasScaleOnSite: e.target.checked }))}
                        className="w-5 h-5 accent-purple-600"
                      />
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        ⚖️ {t('createListing.scaleOnSite')}
                      </span>
                    </label>
                  </div>

                  {/* Tailgate Access */}
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-purple-200 dark:border-purple-700">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={sellerObligations.hasTailgateAccess}
                        onChange={(e) => setSellerObligations(prev => ({ ...prev, hasTailgateAccess: e.target.checked }))}
                        className="w-5 h-5 accent-purple-600"
                      />
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        🚛 {t("createListing.tailgate")}
                      </span>
                    </label>
                  </div>

                  {/* Forklift Available */}
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-purple-200 dark:border-purple-700">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={sellerObligations.hasForkliftAvailable}
                        onChange={(e) => setSellerObligations(prev => ({ ...prev, hasForkliftAvailable: e.target.checked }))}
                        className="w-5 h-5 accent-purple-600"
                      />
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        🏗️ {t('createListing.forklift')}
                      </span>
                    </label>
                  </div>
                </div>

                {/* Authorized Personnel & Safety */}
                <div className="p-4 mt-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-300 dark:border-amber-700">
                  <label className="flex items-center gap-2 cursor-pointer mb-3">
                    <input
                      type="checkbox"
                      checked={sellerObligations.authorizedPersonnelOnly}
                      onChange={(e) => setSellerObligations(prev => ({ ...prev, authorizedPersonnelOnly: e.target.checked }))}
                      className="w-5 h-5 accent-amber-600"
                    />
                    <span className="font-semibold text-amber-800 dark:text-amber-300">
                      🔒 {t('createListing.authorizedOnly')}
                    </span>
                  </label>
                  {sellerObligations.authorizedPersonnelOnly && (
                    <Input
                      placeholder="Specify requirements (e.g., Hard hat, safety vest, steel-toe boots)"
                      value={sellerObligations.safetyRequirements}
                      onChange={(e) => setSellerObligations(prev => ({ ...prev, safetyRequirements: e.target.value }))}
                      className="border-amber-300 focus:ring-amber-500"
                    />
                  )}
                </div>

                {/* Additional Site Notes */}
                <div className="space-y-2 mt-4">
                  <Label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    📝 Additional Site Notes
                  </Label>
                  <Textarea
                    placeholder="e.g., Enter through Gate 4; Appointment required 24h in advance; Limited parking available"
                    value={sellerObligations.additionalSiteNotes}
                    onChange={(e) => setSellerObligations(prev => ({ ...prev, additionalSiteNotes: e.target.value }))}
                    rows={3}
                    className="border-purple-200 focus:ring-purple-500 focus:border-purple-500"
                  />
                </div>
              </div>
            </div>

            {/* Refund Policy */}
            <div className="space-y-3">
              <Label className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                <RefreshCcw className="h-4 w-4 text-red-600" />
                Refund Policy *
              </Label>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <label 
                  className={`flex items-center gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    sellerObligations.refundPolicy === 'non_refundable'
                      ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:border-slate-400'
                  }`}
                >
                  <input
                    type="radio"
                    name="refundPolicy"
                    value="non_refundable"
                    checked={sellerObligations.refundPolicy === 'non_refundable'}
                    onChange={(e) => setSellerObligations(prev => ({ ...prev, refundPolicy: e.target.value }))}
                    className="w-5 h-5 accent-red-600"
                  />
                  <div>
                    <span className="font-bold text-red-700 dark:text-red-400">Non-Refundable</span>
                    <p className="text-xs text-slate-600 dark:text-slate-400">All sales are final</p>
                  </div>
                </label>
                
                <label 
                  className={`flex items-center gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    sellerObligations.refundPolicy === 'refundable'
                      ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:border-slate-400'
                  }`}
                >
                  <input
                    type="radio"
                    name="refundPolicy"
                    value="refundable"
                    checked={sellerObligations.refundPolicy === 'refundable'}
                    onChange={(e) => setSellerObligations(prev => ({ ...prev, refundPolicy: e.target.value }))}
                    className="w-5 h-5 accent-green-600"
                  />
                  <div>
                    <span className="font-bold text-green-700 dark:text-green-400">Refundable</span>
                    <p className="text-xs text-slate-600 dark:text-slate-400">Terms apply</p>
                  </div>
                </label>
              </div>
              
              {sellerObligations.refundPolicy === 'refundable' && (
                <Textarea
                  placeholder="Specify refund terms and conditions..."
                  value={sellerObligations.refundTerms}
                  onChange={(e) => setSellerObligations(prev => ({ ...prev, refundTerms: e.target.value }))}
                  rows={2}
                  className="border-green-200 focus:ring-green-500"
                  required
                />
              )}
            </div>

            {/* =========================================== */}
            {/* SELLER COMMITMENT BLOCK - "The Legal Shield" */}
            {/* =========================================== */}
            <div className="mt-8 space-y-4">
              {/* Why This Matters - Info Box */}
              <div className="p-5 bg-gradient-to-r from-indigo-50 to-blue-50 dark:from-indigo-900/30 dark:to-blue-900/30 rounded-xl border-2 border-indigo-200 dark:border-indigo-700">
                <div className="flex items-start gap-3 mb-4">
                  <div className="p-2 bg-indigo-100 dark:bg-indigo-800 rounded-lg flex-shrink-0">
                    <Shield className="h-5 w-5 text-indigo-700 dark:text-indigo-300" />
                  </div>
                  <div>
                    <h4 className="font-bold text-indigo-900 dark:text-indigo-200 text-lg mb-1">
                      🛡️ Why This Agreement Matters
                    </h4>
                    <p className="text-sm text-indigo-700 dark:text-indigo-300">
                      <strong>Important:</strong> This agreement serves as your legal contract with the buyer. 
                      Providing accurate details protects you from disputes and ensures a smooth payout.
                    </p>
                  </div>
                </div>

                {/* Examples */}
                <div className="space-y-3 pl-12">
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border-l-4 border-blue-500">
                    <p className="text-sm text-slate-700 dark:text-slate-300">
                      <strong className="text-blue-700 dark:text-blue-400">📦 Logistics Example:</strong> If you state 
                      &quot;Forklift Available&quot; and cannot provide one at pickup, you may be liable for the 
                      buyer&apos;s specialized transport costs.
                    </p>
                  </div>
                  
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border-l-4 border-red-500">
                    <p className="text-sm text-slate-700 dark:text-slate-300">
                      <strong className="text-red-700 dark:text-red-400">💰 Refunds Example:</strong> Explicitly marking 
                      an item &quot;Non-Refundable&quot; protects your sale if a buyer has &quot;buyer&apos;s remorse&quot; 
                      after winning.
                    </p>
                  </div>
                  
                  <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border-l-4 border-orange-500">
                    <p className="text-sm text-slate-700 dark:text-slate-300">
                      <strong className="text-orange-700 dark:text-orange-400">📅 Removal Example:</strong> Setting a 
                      7-day removal deadline allows you to legally charge storage fees or relist the item if the 
                      buyer fails to pick it up on time.
                    </p>
                  </div>
                </div>
              </div>

              {/* Seller Commitment Checkbox */}
              <div className="p-6 bg-gradient-to-r from-blue-100 to-slate-100 dark:from-blue-900/40 dark:to-slate-800/40 rounded-xl border-2 border-blue-300 dark:border-blue-700">
                <label className="flex items-start gap-4 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={sellerObligations.sellerAgreementConfirmed}
                    onChange={(e) => setSellerObligations(prev => ({ ...prev, sellerAgreementConfirmed: e.target.checked }))}
                    className="w-6 h-6 mt-1 accent-blue-600 flex-shrink-0"
                    required
                  />
                  <div>
                    <p className="font-bold text-lg text-blue-900 dark:text-blue-200 mb-2">
                      ✅ Seller Commitment *
                    </p>
                    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                      By listing this item, I certify that all location, logistics, and refund information 
                      provided is <strong>accurate and binding</strong>. I understand that providing false or 
                      misleading information may result in penalties, dispute liability, and removal from the platform.
                    </p>
                  </div>
                </label>
                
                {!sellerObligations.sellerAgreementConfirmed && (
                  <p className="mt-3 text-sm text-amber-700 dark:text-amber-400 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    You must confirm the seller commitment to proceed
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Auction Terms & Conditions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              📝 Auction Terms & Conditions (Optional)
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Write your auction terms directly on the platform. Buyers can view and download them as PDF.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Language Toggle */}
            <div className="flex gap-2 mb-4">
              <Button
                type="button"
                variant={activeTermsLang === 'en' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveTermsLang('en')}
              >
                English
              </Button>
              <Button
                type="button"
                variant={activeTermsLang === 'fr' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveTermsLang('fr')}
              >
                Français
              </Button>
            </div>

            {/* English Editor */}
            {activeTermsLang === 'en' && (
              <div>
                <Label>English Terms & Conditions</Label>
                <div className="mt-2">
                  <RichTextEditor
                    content={auctionTerms.en}
                    onChange={(value) => setAuctionTerms(prev => ({ ...prev, en: value }))}
                    placeholder="Enter your auction terms and conditions in English..."
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Use the toolbar to format your terms. Supports headings, bold, italic, underline, lists, and links.
                </p>
              </div>
            )}

            {/* French Editor */}
            {activeTermsLang === 'fr' && (
              <div>
                <Label>Termes et Conditions (Français)</Label>
                <div className="mt-2">
                  <RichTextEditor
                    content={auctionTerms.fr}
                    onChange={(value) => setAuctionTerms(prev => ({ ...prev, fr: value }))}
                    placeholder="Entrez les termes et conditions de votre enchère en français..."
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Utilisez la barre d&apos;outils pour formater vos termes.
                </p>
              </div>
            )}

            <div className="bg-blue-50 dark:bg-blue-950 p-4 rounded-lg">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                💡 <strong>Tip:</strong> If you leave this blank, buyers will see &quot;No terms provided by seller&quot; on the auction page.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  // Step 5: Promotion Selection
  const renderStep5 = () => {
    const promotionTiers = [
      {
        id: 'standard',
        name: 'Standard',
        price: 0,
        priceText: 'Free',
        description: 'Basic placement in search results',
        features: [
          'Visible in category searches',
          'Appears in main marketplace',
          'Standard listing appearance'
        ],
        badge: null,
        borderColor: 'border-gray-200 dark:border-gray-700',
        bgColor: 'bg-gray-50 dark:bg-gray-800/50'
      },
      {
        id: 'premium',
        name: 'Premium',
        price: 25,
        priceText: '$25',
        description: 'Highlighted border and "Featured" badge',
        features: [
          'Highlighted gold border',
          '"Featured" badge on listing',
          'Appears at top of category searches',
          'Priority in search results',
          '7-day promotion duration'
        ],
        badge: '⭐ Popular',
        recommended: true,
        borderColor: 'border-[#06B6D4]',
        bgColor: 'bg-cyan-50 dark:bg-cyan-900/20'
      },
      {
        id: 'elite',
        name: 'Elite',
        price: 50,
        priceText: '$50',
        description: 'Maximum visibility across the platform',
        features: [
          'Everything in Premium',
          'Guaranteed homepage "Hot Items" carousel',
          'Priority in "Featured Auctions" section',
          'Premium gold badge with animation',
          'Email newsletter spotlight',
          '14-day promotion duration'
        ],
        badge: '👑 Best Value',
        borderColor: 'border-amber-400',
        bgColor: 'bg-amber-50 dark:bg-amber-900/20'
      }
    ];

    return (
      <div className="space-y-6">
        <div className="text-center mb-8">
          <h3 className="text-2xl font-bold mb-2">🚀 Promote Your Listing</h3>
          <p className="text-muted-foreground">
            Choose a promotion tier to increase visibility and drive more bids
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {promotionTiers.map((tier) => (
            <Card
              key={tier.id}
              className={`relative cursor-pointer transition-all duration-300 hover:shadow-lg ${
                promotionTier === tier.id 
                  ? `ring-2 ring-[#06B6D4] ${tier.bgColor}` 
                  : `${tier.borderColor} hover:border-[#06B6D4]/50`
              } ${tier.recommended ? 'scale-105 shadow-lg' : ''}`}
              onClick={() => setPromotionTier(tier.id)}
            >
              {/* Badge */}
              {tier.badge && (
                <div className={`absolute -top-3 left-1/2 transform -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold ${
                  tier.recommended 
                    ? 'bg-[#06B6D4] text-white' 
                    : 'bg-amber-400 text-amber-900'
                }`}>
                  {tier.badge}
                </div>
              )}

              <CardHeader className="text-center pt-8">
                <CardTitle className="text-xl">{tier.name}</CardTitle>
                <div className="mt-2">
                  <span className={`text-3xl font-bold ${
                    tier.price === 0 ? 'text-green-600' : 'text-[#1E3A8A]'
                  }`}>
                    {tier.priceText}
                  </span>
                  {tier.price > 0 && <span className="text-muted-foreground text-sm"> one-time</span>}
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  {tier.description}
                </p>
              </CardHeader>

              <CardContent>
                <ul className="space-y-2">
                  {tier.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm">
                      <CheckCircle className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                        promotionTier === tier.id ? 'text-[#06B6D4]' : 'text-green-500'
                      }`} />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                {/* Selection Indicator */}
                <div className={`mt-4 py-2 rounded-lg text-center text-sm font-medium transition-colors ${
                  promotionTier === tier.id
                    ? 'bg-[#06B6D4] text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-muted-foreground'
                }`}>
                  {promotionTier === tier.id ? '✓ Selected' : 'Select'}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Promotion Summary */}
        {promotionTier !== 'standard' && (
          <Card className="border-2 border-[#06B6D4] bg-[#06B6D4]/5">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-lg">
                    {promotionTier === 'premium' ? '⭐ Premium' : '👑 Elite'} Promotion Selected
                  </p>
                  <p className="text-muted-foreground text-sm">
                    Your listing will be promoted immediately after creation
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-[#1E3A8A]">
                    ${promotionTier === 'premium' ? '25' : '50'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Added to your total
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Info Box */}
        <div className="bg-blue-50 dark:bg-blue-950 p-4 rounded-lg">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            💡 <strong>Tip:</strong> Promoted listings receive on average 3x more views and 2x more bids. 
            The promotion fee is charged when you create the listing.
          </p>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle className="text-3xl font-bold text-center">
              {t('createListing.title')}
            </CardTitle>
            <p className="text-center text-muted-foreground">
              {t('createListing.subtitle', 'Create a grouped auction with multiple lots')}
            </p>
          </CardHeader>
          <CardContent>
            <StepIndicator />

            <div className="mb-8">
              {currentStep === 1 && renderStep1()}
              {currentStep === 2 && renderStep2()}
              {currentStep === 3 && renderStep3()}
              {currentStep === 4 && renderStep4()}
              {currentStep === 5 && renderStep5()}
            </div>

            {/* Navigation Buttons */}
            <div className="flex justify-between pt-6 border-t">
              <Button
                type="button"
                variant="outline"
                onClick={goToPrevStep}
                disabled={currentStep === 1 || loading}
              >
                <ChevronLeft className="mr-2 h-4 w-4" />
                {t('common.back')}
              </Button>

              {currentStep < 5 ? (
                <Button
                  type="button"
                  onClick={goToNextStep}
                  className="gradient-button text-white border-0"
                >
                  {t('common.next')}
                  <ChevronRight className="ml-2 h-4 w-4" />
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={handleSubmit}
                  className="gradient-button text-white border-0"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('createListing.creating', 'Creating...')}
                    </>
                  ) : (
                    <>
                      <CheckCircle className="mr-2 h-4 w-4" />
                      {t('createListing.submitListing')}
                    </>
                  )}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default CreateMultiItemListing;
