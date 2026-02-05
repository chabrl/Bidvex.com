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

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SELLER_TYPES = [
  {
    id: 'private',
    title: 'Private Seller',
    description: 'Individual selling personal vehicles',
    icon: User,
    limit: '1 vehicle per month',
    requirements: ['Valid ID', 'Proof of address'],
    color: 'blue',
  },
  {
    id: 'dealer',
    title: 'Licensed Dealer',
    description: 'Registered automotive dealership',
    icon: Building2,
    limit: 'Up to 500 vehicles per month',
    requirements: ['Business registration', 'Dealer license', 'Tax ID'],
    color: 'green',
  },
  {
    id: 'auctioneer',
    title: 'Verified Auctioneer',
    description: 'Professional auction house',
    icon: Gavel,
    limit: 'Up to 500 vehicles per month',
    requirements: ['Auctioneer license', 'Business registration', 'Insurance'],
    color: 'purple',
  },
];

const SellerRegistrationPage = () => {
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
              <CardTitle>Seller Account Status</CardTitle>
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
                    <p className="text-yellow-700 flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5" />
                      Your application is under review. This usually takes 1-2 business days.
                    </p>
              )}
              
              {existingSeller.verification_status === 'rejected' && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-red-700">
                    Your application was rejected. Reason: {existingSeller.rejection_reason || 'Not specified'}
                  </p>
                  <p className="text-sm text-red-600 mt-2">
                    Please contact support for more information.
                  </p>
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
        {/* Header */}
        <div className="text-center mb-8">
          <Badge className="mb-4">Vehicle Auctions</Badge>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
            Become a Vehicle Seller
          </h1>
          <p className="text-slate-500 max-w-xl mx-auto">
            Join BidVex&apos;s trusted network of vehicle sellers. Choose your seller type to get started.
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
                        <Label>Business Phone</Label>
                        <Input
                          value={formData.business_phone}
                          onChange={(e) => updateField('business_phone', e.target.value)}
                          placeholder="+1 (555) 000-0000"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>Business Address</Label>
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
                        <Label>License Province</Label>
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
                        <li>Your application will be reviewed by our team</li>
                        <li>We may contact you for additional documentation</li>
                        <li>Approval typically takes 1-2 business days</li>
                        <li>You&apos;ll be notified via email once approved</li>
                      </ul>
                    </div>
                  </div>
                </div>
                
                {/* Agreement */}
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-sm text-slate-600">
                    By submitting this application, you agree to BidVex&apos;s seller terms and conditions, 
                    including compliance with all applicable vehicle sales regulations.
                  </p>
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
