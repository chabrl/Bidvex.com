import API_BASE from '../../config';
/**
 * Vehicle Seller Registration Page
 * Register as a vehicle seller (Private, Dealer, or Auctioneer)
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import {
  User, Building2, Gavel, CheckCircle, Upload, FileText, 
  Shield, Star, Loader2, AlertTriangle, Info, Car, ArrowRight
} from 'lucide-react';
import SellerDocumentManager from '../../components/vehicles/SellerDocumentManager';
import { ResubmitApplicationPanel } from '../../components/ResubmitApplicationPanel';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

const SELLER_TYPES = [
  {
    id: 'dealer',
    title: 'Licensed Dealer / Concessionnaire licencié',
    description: 'OPC-licensed road vehicle dealer / Concessionnaire de véhicules routiers licencié OPC',
    icon: Building2,
    limit: 'Unlimited / Illimitées',
    requirements: ['OPC Permit / Permis OPC', 'Business registration / Inscription d\'entreprise', 'Tax ID / Numéro de taxe'],
    color: 'green',
  },
  {
    id: 'auctioneer',
    title: 'Verified Auctioneer / Encanteur vérifié',
    description: 'Professional auction house / Maison d\'enchères professionnelle',
    icon: Gavel,
    limit: 'Unlimited / Illimitées',
    requirements: ['Auctioneer license / Licence d\'encanteur', 'Business registration / Inscription d\'entreprise', 'Insurance / Assurance'],
    color: 'purple',
  },
];

const SellerRegistrationPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const [step, setStep] = useState(1);
  const [selectedType, setSelectedType] = useState(null);
  const [loading, setLoading] = useState(false);
  const [existingSeller, setExistingSeller] = useState(null);
  
  const [formData, setFormData] = useState({
    business_name: '',
    business_address: '',
    business_phone: '',
    license_number: '',
    license_province: 'QC',
    tax_id: '',
    website: '',
    description: '',
  });

  // Check if already registered
  useEffect(() => {
    // iter198 — Pilot attribution: capture ?utm_source=… from the URL
    try {
      const params = new URLSearchParams(window.location.search);
      const utm = params.get('utm_source');
      if (utm) localStorage.setItem('bidvex.utm_source', utm.slice(0, 100));
    } catch (_e) {}

    const checkExisting = async () => {
      if (!token) {
        navigate('/auth');
        return;
      }
      
      try {
        const response = await axios.get(`${API}/vehicle-sellers/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setExistingSeller(response.data);
      } catch (error) {
        // Not registered yet
      }
    };
    
    // expose for ResubmitApplicationPanel callback
    window.__refetchVehicleSeller = checkExisting;
    checkExisting();
  }, [token, navigate]);

  const updateField = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    if (!selectedType) {
      toast.error('Please select a seller type');
      return;
    }
    
    // Validate required fields for business sellers
    if (selectedType !== 'private') {
      if (!formData.business_name) {
        toast.error('Business name is required');
        return;
      }
      if (!formData.license_number) {
        toast.error('License number is required');
        return;
      }
    }
    
    setLoading(true);
    try {
      const response = await axios.post(`${API}/vehicle-sellers/register`, {
        seller_type: selectedType,
        business_name: formData.business_name || null,
        business_address: formData.business_address || null,
        business_phone: formData.business_phone || null,
        license_number: formData.license_number || null,
        license_province: formData.license_province || null,
        tax_id: formData.tax_id || null,
        website: formData.website || null,
        description: formData.description || null,
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success('Registration submitted! Awaiting admin approval.');
      navigate('/vehicle-auctions');
      
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  // If already registered, show status
  if (existingSeller) {
    const typeInfo = SELLER_TYPES.find(t => t.id === existingSeller.seller_type);
    const Icon = typeInfo?.icon || User;
    
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12">
        <div className="max-w-2xl mx-auto px-4">
          <Card>
            <CardHeader className="text-center">
              <div className={`w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center ${
                existingSeller.verification_status === 'approved' 
                  ? 'bg-green-100' 
                  : existingSeller.verification_status === 'rejected'
                  ? 'bg-red-100'
                  : 'bg-yellow-100'
              }`}>
                <Icon className={`h-8 w-8 ${
                  existingSeller.verification_status === 'approved'
                    ? 'text-green-600'
                    : existingSeller.verification_status === 'rejected'
                    ? 'text-red-600'
                    : 'text-yellow-600'
                }`} />
              </div>
              <CardTitle>{t("seller.accountStatus")}</CardTitle>
              <CardDescription>
                {typeInfo?.title || 'Vehicle Seller'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="text-center">
                <Badge className={`text-lg px-4 py-2 ${
                  existingSeller.verification_status === 'approved'
                    ? 'bg-green-500'
                    : existingSeller.verification_status === 'rejected'
                    ? 'bg-red-500'
                    : 'bg-yellow-500'
                }`}>
                  {existingSeller.verification_status === 'approved' && (
                    <CheckCircle className="h-4 w-4 mr-2 inline" />
                  )}
                  {existingSeller.verification_status.toUpperCase()}
                </Badge>
              </div>
              
              {existingSeller.verification_status === 'approved' && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <p className="text-green-700">
                    Your account is approved! You can now list vehicles.
                  </p>
                  <div className="mt-4 flex gap-4">
                    <Button onClick={() => navigate('/vehicle-auctions/create')}>
                      <Car className="h-4 w-4 mr-2" /> List a Vehicle
                    </Button>
                    <Button variant="outline" onClick={() => navigate('/vehicle-auctions/my-listings')}>
                      My Listings
                    </Button>
                  </div>
                </div>
              )}
              
              {existingSeller.verification_status === 'pending' && (
                <div className="space-y-4">
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <p className="text-yellow-700 flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5" />
                      Your application is under review. Please upload required documents to speed up the process.
                    </p>
                  </div>
                  
                  {/* Document Upload Section */}
                  <SellerDocumentManager />
                </div>
              )}
              
              {existingSeller.verification_status === 'rejected' && (
                <div className="space-y-3">
                  <div
                    className="bg-red-50 border border-red-200 rounded-lg p-4"
                    data-testid="dealer-rejection-reason-block"
                  >
                    <p className="text-red-700 font-semibold flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4" />
                      {(i18n.language || 'en').toLowerCase().startsWith('fr')
                        ? 'Demande refusée'
                        : 'Application Declined'}
                    </p>
                    <p className="text-sm text-red-600 mt-2">
                      <strong>{(i18n.language || 'en').toLowerCase().startsWith('fr') ? 'Raison' : 'Reason'}:</strong>{' '}
                      {existingSeller.rejection_reason ||
                        ((i18n.language || 'en').toLowerCase().startsWith('fr') ? 'Non spécifiée' : 'Not specified')}
                    </p>
                  </div>
                  <ResubmitApplicationPanel
                    flavor="dealer"
                    token={token}
                    rejectionReason={existingSeller.rejection_reason}
                    resubmissionCount={existingSeller.resubmission_count || 0}
                    rejectionHistory={existingSeller.rejection_history || []}
                    prefillData={{
                      sellerType: existingSeller.seller_type,
                      businessName: existingSeller.business_name,
                      licenseNumber: existingSeller.license_number,
                      licenseProvince: existingSeller.license_province,
                    }}
                    onResubmitted={() => { if (typeof window.__refetchVehicleSeller === 'function') window.__refetchVehicleSeller(); }}
                  />
                </div>
              )}
              
              {/* Stats */}
              <div className="grid grid-cols-3 gap-4 pt-4 border-t">
                <div className="text-center">
                  <p className="text-2xl font-bold">{existingSeller.total_listings}</p>
                  <p className="text-sm text-slate-500">Total Listings</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">{existingSeller.total_sold}</p>
                  <p className="text-sm text-slate-500">Sold</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">
                    {existingSeller.monthly_listing_count}/{existingSeller.monthly_listing_limit}
                  </p>
                  <p className="text-sm text-slate-500">This Month</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12" data-testid="seller-registration-page">
      <div className="max-w-4xl mx-auto px-4">
        {/* Bilingual Header — EN */}
        <div className="text-center mb-6">
          <Badge className="mb-4">Vehicle Auctions</Badge>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white mb-2">
            List Your Vehicles on BidVex — Licensed Dealers Only
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 max-w-2xl mx-auto leading-relaxed">
            BidVex accepts vehicle listings exclusively from OPC-licensed road vehicle dealers (commerçants de véhicules routiers) holding a valid permit issued by the Office de la protection du consommateur du Québec. Individual private sellers are not eligible to list road vehicles on this platform.
          </p>
          <p className="text-sm text-green-700 dark:text-green-400 mt-2 font-medium">
            Unlimited vehicle listings included with your verified dealer account. No per-listing fees for dealers.
          </p>
        </div>
        <hr className="border-slate-200 dark:border-slate-700 mb-4" />
        {/* Bilingual Header — FR */}
        <div className="text-center mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white mb-2">
            Listez vos véhicules sur BidVex — Concessionnaires licenciés seulement
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 max-w-2xl mx-auto leading-relaxed">
            BidVex accepte les annonces de véhicules exclusivement des concessionnaires de véhicules routiers licenciés par l'OPC (commerçants de véhicules routiers) détenant un permis valide délivré par l'Office de la protection du consommateur du Québec. Les vendeurs privés individuels ne sont pas admissibles à lister des véhicules routiers sur cette plateforme.
          </p>
          <p className="text-sm text-green-700 dark:text-green-400 mt-2 font-medium">
            Annonces de véhicules illimitées incluses avec votre compte concessionnaire vérifié. Aucun frais par annonce pour les concessionnaires.
          </p>
        </div>

        {/* Non-Dismissible Disclaimer Box (Bilingual) */}
        <div className="border-2 border-red-300 bg-red-50 dark:bg-red-900/15 rounded-lg p-5 mb-8 space-y-3" data-testid="vehicle-platform-disclaimer">
          <p className="text-sm text-red-800 dark:text-red-200 leading-relaxed">
            <strong>EN:</strong> BidVex is a technology platform only. We do not buy, sell, or take possession of vehicles. All vehicle sales are contracts formed directly between the licensed dealer and the winning bidder. BidVex does not hold title to any vehicle at any time.
          </p>
          <hr className="border-red-200 dark:border-red-700" />
          <p className="text-sm text-red-800 dark:text-red-200 leading-relaxed">
            <strong>FR:</strong> BidVex est une plateforme technologique uniquement. Nous n'achetons pas, ne vendons pas et ne prenons pas possession de véhicules. Toutes les ventes de véhicules sont des contrats formés directement entre le concessionnaire licencié et l'enchérisseur gagnant. BidVex ne détient le titre d'aucun véhicule en aucun moment.
          </p>
        </div>

        {/* Step 1: Choose Type */}
        {step === 1 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="grid md:grid-cols-3 gap-6 mb-8">
              {SELLER_TYPES.map((type) => {
                const Icon = type.icon;
                const isSelected = selectedType === type.id;
                
                return (
                  <Card 
                    key={type.id}
                    className={`cursor-pointer transition-all hover:shadow-lg ${
                      isSelected 
                        ? `border-2 border-${type.color}-500 ring-4 ring-${type.color}-100` 
                        : 'hover:border-slate-300'
                    }`}
                    onClick={() => setSelectedType(type.id)}
                    data-testid={`seller-type-${type.id}`}
                  >
                    <CardContent className="pt-6">
                      <div className={`w-12 h-12 rounded-lg flex items-center justify-center mb-4 ${
                        isSelected ? `bg-${type.color}-100` : 'bg-slate-100'
                      }`}>
                        <Icon className={`h-6 w-6 ${
                          isSelected ? `text-${type.color}-600` : 'text-slate-500'
                        }`} />
                      </div>
                      
                      <h3 className="font-semibold text-lg mb-1">{type.title}</h3>
                      <p className="text-sm text-slate-500 mb-4">{type.description}</p>
                      
                      <div className="space-y-3">
                        <div className="flex items-center gap-2 text-sm">
                          <Star className="h-4 w-4 text-yellow-500" />
                          <span className="font-medium">{type.limit}</span>
                        </div>
                        
                        <div className="text-xs text-slate-400">
                          Required: {type.requirements.join(', ')}
                        </div>
                      </div>
                      
                      {isSelected && (
                        <div className="mt-4 pt-4 border-t">
                          <Badge className={`bg-${type.color}-500`}>Selected</Badge>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
            
            <div className="text-center">
              <Button 
                size="lg"
                disabled={!selectedType}
                onClick={() => setStep(2)}
                className="gap-2"
              >
                Continue <CheckCircle className="h-4 w-4" />
              </Button>
            </div>
          </motion.div>
        )}

        {/* Step 2: Details */}
        {step === 2 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {selectedType === 'private' ? 'Personal Information' : 'Business Information'}
                </CardTitle>
                <CardDescription>
                  {selectedType === 'private' 
                    ? 'Provide your details to register as a private seller'
                    : 'Provide your business details for verification'
                  }
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {selectedType !== 'private' && (
                  <>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Business Name *</Label>
                        <Input
                          value={formData.business_name}
                          onChange={(e) => updateField('business_name', e.target.value)}
                          placeholder="Your Company Name"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t("seller.businessPhone")}</Label>
                        <Input
                          value={formData.business_phone}
                          onChange={(e) => updateField('business_phone', e.target.value)}
                          placeholder="+1 (555) 000-0000"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>{t("seller.businessAddress")}</Label>
                      <Input
                        value={formData.business_address}
                        onChange={(e) => updateField('business_address', e.target.value)}
                        placeholder="123 Business St, City, Province"
                      />
                    </div>
                    
                    <div className="grid md:grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label>{selectedType === 'dealer' ? 'Dealer' : 'Auctioneer'} License # *</Label>
                        <Input
                          value={formData.license_number}
                          onChange={(e) => updateField('license_number', e.target.value)}
                          placeholder="LIC-12345"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t("seller.licenseProvince")}</Label>
                        <Input
                          value={formData.license_province}
                          onChange={(e) => updateField('license_province', e.target.value)}
                          placeholder="QC"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Tax ID / GST #</Label>
                        <Input
                          value={formData.tax_id}
                          onChange={(e) => updateField('tax_id', e.target.value)}
                          placeholder="Optional"
                        />
                      </div>
                    </div>
                  </>
                )}
                
                {/* OPC Permit Field (Bilingual) */}
                <div className="space-y-2 border-2 border-amber-200 rounded-lg p-4 bg-amber-50/50 dark:bg-amber-900/10">
                  <Label className="font-semibold">OPC Permit Number / Numéro de permis OPC *</Label>
                  <Input
                    value={formData.license_number}
                    onChange={(e) => updateField('license_number', e.target.value)}
                    placeholder="XXXXXXX"
                    data-testid="opc-permit-input"
                  />
                  <p className="text-xs text-slate-500">Your permit number as issued by the OPC. Example format: XXXXXXX. This will be verified before your account is activated.</p>
                  <hr className="border-slate-200 dark:border-slate-700" />
                  <p className="text-xs text-slate-500">Votre numéro de permis tel que délivré par l'OPC. Format exemple : XXXXXXX. Ce numéro sera vérifié avant l'activation de votre compte.</p>
                </div>
                
                <div className="space-y-2">
                  <Label>Website</Label>
                  <Input
                    value={formData.website}
                    onChange={(e) => updateField('website', e.target.value)}
                    placeholder="https://www.example.com"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>About {selectedType === 'private' ? 'You' : 'Your Business'}</Label>
                  <Textarea
                    value={formData.description}
                    onChange={(e) => updateField('description', e.target.value)}
                    placeholder="Tell buyers about yourself or your business..."
                    rows={4}
                  />
                </div>
                
                {/* Info Box */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-blue-500 mt-0.5" />
                    <div className="text-sm text-blue-700">
                      <p className="font-medium mb-1">What happens next?</p>
                      <ul className="list-disc list-inside space-y-1">
                        <li>{t("seller.applicationReview")}</li>
                        <li>We may contact you for additional documentation</li>
                        <li>Approval typically takes 1-2 business days</li>
                        <li>You&apos;ll be notified via email once approved</li>
                      </ul>
                    </div>
                  </div>
                </div>
                
                {/* Dealer Onboarding Agreement (Bilingual — Section 6.2) */}
                <div className="border-2 border-slate-300 dark:border-slate-600 rounded-lg p-4 space-y-3" data-testid="dealer-agreement-block">
                  <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed space-y-2">
                    <p>I represent and warrant that: (1) I hold a valid, current OPC permit (permis de commerçant de véhicules routiers) issued by the Office de la protection du consommateur du Québec; (2) I will comply with all obligations under the Consumer Protection Act including written contracts of sale, legal warranties (garantie légale de bon fonctionnement), and disclosure of my permit number to buyers; (3) I acknowledge that BidVex is a technology platform only and is not a co-vendor, guarantor, or party to any vehicle sale contract; (4) I will not list any vehicle for which I do not hold clear title free of undisclosed encumbrances.</p>
                    <hr className="border-slate-200 dark:border-slate-700" />
                    <p>Je déclare et garantis que : (1) je détiens un permis OPC valide et en vigueur (permis de commerçant de véhicules routiers) délivré par l'Office de la protection du consommateur du Québec ; (2) je me conformerai à toutes les obligations en vertu de la Loi sur la protection du consommateur, notamment les contrats de vente écrits, les garanties légales (garantie légale de bon fonctionnement) et la divulgation de mon numéro de permis aux acheteurs ; (3) je reconnais que BidVex est une plateforme technologique uniquement et n'est pas un co-vendeur, garant ou partie à tout contrat de vente de véhicule ; (4) je ne listerai aucun véhicule pour lequel je ne détiens pas un titre clair exempt de charges non divulguées.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <div className="flex justify-between mt-6">
              <Button variant="outline" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button 
                onClick={handleSubmit}
                disabled={loading}
                className="gap-2"
                data-testid="submit-registration-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Submitting...
                  </>
                ) : (
                  <>
                    <CheckCircle className="h-4 w-4" /> Submit Application
                  </>
                )}
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default SellerRegistrationPage;
