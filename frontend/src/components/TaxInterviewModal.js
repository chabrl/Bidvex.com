import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import { Building2, User, Shield, AlertTriangle, CheckCircle, X, ArrowLeft } from 'lucide-react';
import { TAX_DECLARATIONS, TAX_FIELD_REQUIREMENTS } from '../utils/taxCompliance';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TaxInterviewModal = ({ user, onComplete, onCancel }) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language || 'en';
  
  const [step, setStep] = useState(1); // 1: Type selection, 2: Data collection, 3: Confirmation
  const [sellerType, setSellerType] = useState(null);
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const [agreedToReport, setAgreedToReport] = useState(false);
  const [loading, setLoading] = useState(false);
  
  // ESC key to close modal
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') {
        handleExit();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [step]);
  
  const handleExit = () => {
    // If user has entered data in step 2, confirm before exiting
    if (step === 2 && (formData.legal_name || formData.legal_business_name)) {
      setShowExitConfirm(true);
    } else {
      confirmExit();
    }
  };
  
  const confirmExit = () => {
    if (onCancel) {
      onCancel();
    } else {
      navigate('/'); // Redirect to homepage
    }
  };
  
  const [formData, setFormData] = useState({
    // Individual fields
    legal_name: user?.name || '',
    date_of_birth: '',
    sin: '',
    principal_address: user?.address || '',
    
    // Business fields
    legal_business_name: '',
    business_number: '',
    business_province: '', // NEW: Province selection
    neq_number: '',
    gst_number: '',
    qst_number: '',
    registered_office_address: '',
  });

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const validateStep2 = () => {
    const declarations = TAX_DECLARATIONS[lang];
    
    if (sellerType === 'individual') {
      if (!formData.legal_name || !formData.date_of_birth || !formData.sin) {
        toast.error('Please fill all required fields');
        return false;
      }
      if (formData.sin.replace(/\D/g, '').length !== 9) {
        toast.error('SIN must be 9 digits');
        return false;
      }
    } else if (sellerType === 'business') {
      // Always required
      if (!formData.legal_business_name || !formData.business_number || !formData.business_province) {
        toast.error('Please fill all required fields: Business Name, Business Number, and Province');
        return false;
      }
      if (formData.business_number.replace(/\D/g, '').length !== 9) {
        toast.error('Business Number must be 9 digits');
        return false;
      }
      
      // Province-specific requirements
      const isQuebec = formData.business_province === 'QC' || formData.business_province === 'Quebec';
      
      if (isQuebec) {
        // Quebec businesses MUST have NEQ and QST
        if (!formData.neq_number || !formData.qst_number) {
          toast.error('Quebec businesses must provide NEQ and QST registration numbers');
          return false;
        }
        if (formData.neq_number.replace(/\D/g, '').length !== 10) {
          toast.error('NEQ must be 10 digits');
          return false;
        }
      }
      
      // GST/HST required for all provinces (format varies)
      if (!formData.gst_number) {
        toast.error('GST/HST registration number is required');
        return false;
      }
    }
    
    return true;
  };

  const handleSubmit = async () => {
    if (!agreedToReport) {
      toast.error('You must consent to CRA/Revenu Québec reporting to proceed');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        seller_type: sellerType,
        tax_onboarding_completed: true,
        ...(sellerType === 'individual' ? {
          tax_id: formData.sin,
          date_of_birth: formData.date_of_birth,
          address: formData.principal_address,
          is_tax_registered: false
        } : {
          tax_id: formData.business_number,
          neq_number: formData.neq_number,
          gst_number: formData.gst_number,
          qst_number: formData.qst_number,
          legal_business_name: formData.legal_business_name,
          registered_office_address: formData.registered_office_address,
          is_tax_registered: true,
          account_type: 'business'
        })
      };

      await axios.put(`${API}/users/me/tax-profile`, payload);
      toast.success('Tax profile completed successfully!');
      onComplete();
    } catch (error) {
      toast.error('Failed to save tax profile: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const declarations = TAX_DECLARATIONS[lang];

  return (
    <div className="fixed inset-0 bg-black/80 z-[70] overflow-y-auto">
      {/* Flexbox Container for Proper Centering */}
      <div className="min-h-screen flex items-center justify-center p-4 py-8">
        <Card className="w-full max-w-3xl my-auto">
          <CardHeader className="bg-gradient-to-r from-blue-600 to-cyan-500 text-white">
            <div className="flex items-center gap-3">
              <Shield className="h-8 w-8" />
              <div>
                <CardTitle className="text-2xl text-white">{declarations.title}</CardTitle>
                <p className="text-sm text-white/90 mt-1">{declarations.subtitle}</p>
              </div>
            </div>
          </CardHeader>
        
        <CardContent className="p-6 space-y-6">
          {/* Step 1: Seller Type Selection */}
          {step === 1 && (
            <div className="space-y-6">
              <div className="text-center mb-6">
                <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">
                  {lang === 'en' ? 'Select Your Seller Type' : 'Sélectionnez votre type de vendeur'}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {lang === 'en' 
                    ? 'This determines your tax obligations and reporting requirements'
                    : 'Ceci détermine vos obligations fiscales et exigences de déclaration'}
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                {/* Individual Option */}
                <button
                  onClick={() => setSellerType('individual')}
                  className={`p-6 border-2 rounded-xl transition-all hover:scale-105 ${
                    sellerType === 'individual'
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:border-blue-300'
                  }`}
                >
                  <User className="h-12 w-12 mx-auto mb-3 text-blue-600" />
                  <h4 className="font-bold text-lg mb-2 text-slate-900 dark:text-slate-100">
                    {lang === 'en' ? 'Individual / Casual Seller' : 'Vendeur Individuel / Occasionnel'}
                  </h4>
                  <ul className="text-sm text-slate-600 dark:text-slate-400 space-y-1 text-left">
                    <li>• {lang === 'en' ? 'Personal sales' : 'Ventes personnelles'}</li>
                    <li>• {lang === 'en' ? 'SIN required' : 'NAS requis'}</li>
                    <li>• {lang === 'en' ? 'Platform handles tax' : 'Plateforme gère taxes'}</li>
                  </ul>
                  {sellerType === 'individual' && (
                    <Badge className="mt-3 bg-blue-500 text-white">
                      {lang === 'en' ? 'Selected' : 'Sélectionné'}
                    </Badge>
                  )}
                </button>

                {/* Business Option */}
                <button
                  onClick={() => setSellerType('business')}
                  className={`p-6 border-2 rounded-xl transition-all hover:scale-105 ${
                    sellerType === 'business'
                      ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:border-purple-300'
                  }`}
                >
                  <Building2 className="h-12 w-12 mx-auto mb-3 text-purple-600" />
                  <h4 className="font-bold text-lg mb-2 text-slate-900 dark:text-slate-100">
                    {lang === 'en' ? 'Registered Business' : 'Entreprise Enregistrée'}
                  </h4>
                  <ul className="text-sm text-slate-600 dark:text-slate-400 space-y-1 text-left">
                    <li>• {lang === 'en' ? 'Corporation/LLC' : 'Société/SARL'}</li>
                    <li>• {lang === 'en' ? 'BN + NEQ required' : 'NE + NEQ requis'}</li>
                    <li>• {lang === 'en' ? 'Self-remit taxes' : 'Auto-remise taxes'}</li>
                  </ul>
                  {sellerType === 'business' && (
                    <Badge className="mt-3 bg-purple-500 text-white">
                      {lang === 'en' ? 'Selected' : 'Sélectionné'}
                    </Badge>
                  )}
                </button>
              </div>

              <Button
                onClick={() => setStep(2)}
                disabled={!sellerType}
                className="w-full gradient-button text-white"
              >
                {lang === 'en' ? 'Continue' : 'Continuer'}
              </Button>
            </div>
          )}

          {/* Step 2: Data Collection */}
          {step === 2 && sellerType && (
            <div className="space-y-6">
              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-yellow-900 dark:text-yellow-100">
                    <p className="font-semibold mb-1">
                      {lang === 'en' ? 'Tax Information Required' : 'Informations Fiscales Requises'}
                    </p>
                    <p>
                      {sellerType === 'individual' 
                        ? declarations.individual.description
                        : declarations.business.description}
                    </p>
                  </div>
                </div>
              </div>

              {/* Individual Fields */}
              {sellerType === 'individual' && (
                <div className="space-y-4">
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'Full Legal Name' : 'Nom Légal Complet'} *
                    </Label>
                    <Input
                      value={formData.legal_name}
                      onChange={(e) => handleInputChange('legal_name', e.target.value)}
                      placeholder={lang === 'en' ? 'As it appears on government ID' : 'Tel qu\'il apparaît sur votre pièce d\'identité'}
                      className="text-slate-900 dark:text-slate-100"
                    />
                  </div>
                  
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'Date of Birth' : 'Date de Naissance'} *
                    </Label>
                    <Input
                      type="date"
                      value={formData.date_of_birth}
                      onChange={(e) => handleInputChange('date_of_birth', e.target.value)}
                      className="text-slate-900 dark:text-slate-100"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {lang === 'en' ? 'Required for CRA Part XX reporting' : 'Requis pour la déclaration ARC Partie XX'}
                    </p>
                  </div>
                  
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'Social Insurance Number (SIN)' : 'Numéro d\'Assurance Sociale (NAS)'} *
                    </Label>
                    <Input
                      value={formData.sin}
                      onChange={(e) => handleInputChange('sin', e.target.value.replace(/\D/g, '').slice(0, 9))}
                      placeholder="123-456-789"
                      maxLength={11}
                      className="text-slate-900 dark:text-slate-100 font-mono"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {lang === 'en' ? '9 digits - Encrypted and secure' : '9 chiffres - Crypté et sécurisé'}
                    </p>
                  </div>
                  
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'Principal Residential Address' : 'Adresse Résidentielle Principale'} *
                    </Label>
                    <Input
                      value={formData.principal_address}
                      onChange={(e) => handleInputChange('principal_address', e.target.value)}
                      placeholder={lang === 'en' ? 'Full street address' : 'Adresse complète'}
                      className="text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>
              )}

              {/* Business Fields */}
              {sellerType === 'business' && (
                <div className="space-y-4">
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'Registered Corporation Name' : 'Nom de la Société Enregistrée'} *
                    </Label>
                    <Input
                      value={formData.legal_business_name}
                      onChange={(e) => handleInputChange('legal_business_name', e.target.value)}
                      placeholder={lang === 'en' ? 'As registered with provincial/federal authorities' : 'Tel qu\'enregistré auprès des autorités'}
                      className="text-slate-900 dark:text-slate-100"
                    />
                  </div>
                  
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'Business Province/Territory' : 'Province/Territoire d\'Entreprise'} *
                    </Label>
                    <select
                      value={formData.business_province}
                      onChange={(e) => handleInputChange('business_province', e.target.value)}
                      className="w-full px-3 py-2 border rounded-md text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-800"
                      required
                    >
                      <option value="">{lang === 'en' ? 'Select Province' : 'Sélectionner la Province'}</option>
                      <option value="QC">Quebec (QC)</option>
                      <option value="ON">Ontario (ON)</option>
                      <option value="BC">British Columbia (BC)</option>
                      <option value="AB">Alberta (AB)</option>
                      <option value="MB">Manitoba (MB)</option>
                      <option value="SK">Saskatchewan (SK)</option>
                      <option value="NS">Nova Scotia (NS)</option>
                      <option value="NB">New Brunswick (NB)</option>
                      <option value="NL">Newfoundland and Labrador (NL)</option>
                      <option value="PE">Prince Edward Island (PE)</option>
                      <option value="YT">Yukon (YT)</option>
                      <option value="NT">Northwest Territories (NT)</option>
                      <option value="NU">Nunavut (NU)</option>
                      <option value="FEDERAL">{lang === 'en' ? 'Federal Corporation' : 'Société Fédérale'}</option>
                    </select>
                    <p className="text-xs text-muted-foreground mt-1">
                      {lang === 'en' ? 'Province where business is registered' : 'Province où l\'entreprise est enregistrée'}
                    </p>
                  </div>
                  
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'Business Number (BN)' : 'Numéro d\'Entreprise (NE)'} *
                    </Label>
                    <Input
                      value={formData.business_number}
                      onChange={(e) => handleInputChange('business_number', e.target.value.replace(/\D/g, '').slice(0, 9))}
                      placeholder="123456789"
                      maxLength={9}
                      className="text-slate-900 dark:text-slate-100 font-mono"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {lang === 'en' ? '9-digit federal business number' : 'Numéro d\'entreprise fédéral à 9 chiffres'}
                    </p>
                  </div>
                  
                  {/* NEQ - Quebec Only */}
                  {(formData.business_province === 'QC' || formData.business_province === 'Quebec') && (
                    <div>
                      <Label className="text-slate-900 dark:text-slate-100">
                        {lang === 'en' ? 'Quebec Enterprise Number (NEQ)' : 'Numéro d\'Entreprise du Québec (NEQ)'} *
                      </Label>
                      <Input
                        value={formData.neq_number}
                        onChange={(e) => handleInputChange('neq_number', e.target.value.replace(/\D/g, '').slice(0, 10))}
                        placeholder="1234567890"
                        maxLength={10}
                        className="text-slate-900 dark:text-slate-100 font-mono"
                      />
                      <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                        {lang === 'en' ? '✓ Required for Quebec businesses only' : '✓ Requis uniquement pour les entreprises du Québec'}
                      </p>
                    </div>
                  )}
                  
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'GST/HST Registration Number' : 'Numéro d\'inscription TPS/TVH'} *
                    </Label>
                    <Input
                      value={formData.gst_number}
                      onChange={(e) => handleInputChange('gst_number', e.target.value)}
                      placeholder="123456789RT0001"
                      className="text-slate-900 dark:text-slate-100 font-mono"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {formData.business_province === 'ON' 
                        ? (lang === 'en' ? 'HST number for Ontario' : 'Numéro TVH pour l\'Ontario')
                        : (lang === 'en' ? 'GST/HST registration number' : 'Numéro d\'inscription TPS/TVH')}
                    </p>
                  </div>
                  
                  {/* QST - Quebec Only */}
                  {(formData.business_province === 'QC' || formData.business_province === 'Quebec') && (
                    <div>
                      <Label className="text-slate-900 dark:text-slate-100">
                        {lang === 'en' ? 'QST Registration Number' : 'Numéro d\'inscription TVQ'} *
                      </Label>
                      <Input
                        value={formData.qst_number}
                        onChange={(e) => handleInputChange('qst_number', e.target.value)}
                        placeholder="1234567890TQ0001"
                        className="text-slate-900 dark:text-slate-100 font-mono"
                      />
                      <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                        {lang === 'en' ? '✓ Required for Quebec businesses only' : '✓ Requis uniquement pour les entreprises du Québec'}
                      </p>
                    </div>
                  )}
                  
                  <div>
                    <Label className="text-slate-900 dark:text-slate-100">
                      {lang === 'en' ? 'Registered Office Address' : 'Adresse du Bureau Enregistré'} *
                    </Label>
                    <Input
                      value={formData.registered_office_address}
                      onChange={(e) => handleInputChange('registered_office_address', e.target.value)}
                      placeholder={lang === 'en' ? 'Official business address' : 'Adresse commerciale officielle'}
                      className="text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>
              )}

              {/* Legal Points */}
              <div className="bg-slate-50 dark:bg-slate-800/50 border rounded-lg p-4">
                <h4 className="font-semibold text-slate-900 dark:text-slate-100 mb-3">
                  {sellerType === 'individual' ? declarations.individual.header : declarations.business.header}
                </h4>
                <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
                  {(sellerType === 'individual' ? declarations.individual.points : declarations.business.points).map((point, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0 mt-0.5" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Consent Checkbox */}
              <div className="bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-300 dark:border-blue-700 rounded-lg p-4">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={agreedToReport}
                    onChange={(e) => setAgreedToReport(e.target.checked)}
                    className="mt-1 w-5 h-5 accent-blue-600"
                  />
                  <div className="text-sm text-slate-900 dark:text-slate-100">
                    <p className="font-semibold mb-2">
                      {lang === 'en' 
                        ? 'Consent to CRA/Revenu Québec Reporting' 
                        : 'Consentement à la Déclaration ARC/Revenu Québec'}
                    </p>
                    <p>
                      {sellerType === 'individual' ? declarations.individual.agreement : declarations.business.agreement}
                    </p>
                    <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 italic">
                      {declarations.cra_reference}
                    </p>
                  </div>
                </label>
              </div>

              <div className="flex gap-3">
                <Button variant="outline" onClick={() => setStep(1)} className="flex-1">
                  {lang === 'en' ? 'Back' : 'Retour'}
                </Button>
                <Button
                  onClick={() => {
                    if (validateStep2()) {
                      handleSubmit();
                    }
                  }}
                  disabled={!agreedToReport || loading}
                  className="flex-1 gradient-button text-white"
                >
                  {loading ? (
                    lang === 'en' ? 'Saving...' : 'Sauvegarde...'
                  ) : (
                    lang === 'en' ? 'Complete Tax Profile' : 'Compléter le Profil Fiscal'
                  )}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      </div>
    </div>
  );
};

export default TaxInterviewModal;
