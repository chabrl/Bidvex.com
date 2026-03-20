/**
 * Create Vehicle Listing Page
 * Multi-step form with VIN auto-fill and photo upload
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
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
import useGeoLocation from '../../hooks/useGeoLocation';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
  const { t } = useTranslation();
  const { token, user } = useAuth();
  const geo = useGeoLocation();
  const [currentStep, setCurrentStep] = useState(0);

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
  const [photos, setPhotos] = useState({});
  
  // Form data
  const [formData, setFormData] = useState({
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
    start_time: '',
    end_time: '',
    starting_price: '',
    reserve_price: '',
    buy_now_price: '',
    bid_increment: '100',
    requires_deposit: true,
    deposit_amount: '500',
    
    // Description
    title: '',
    description: '',
    features: [],
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
        
        if (response.data.verification_status !== 'approved') {
          toast.error('Your seller account is not yet approved');
          navigate('/vehicle-auctions');
        }
      } catch (error) {
        if (error.response?.status === 404) {
          toast.error('Please register as a vehicle seller first');
          navigate('/vehicle-auctions/seller/register');
        }
      }
    };
    
    checkSeller();
  }, [token, navigate]);

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
      toast.error(error.response?.data?.detail || 'Failed to decode VIN');
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

  // Submit listing
  const handleSubmit = async () => {
    if (getTotalPhotos() < 10) {
      toast.error('Please upload at least 10 photos');
      return;
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
        deposit_amount: parseFloat(formData.deposit_amount),
        title: formData.title,
        description: formData.description,
        features: formData.features,
      };
      
      // Create listing
      const createResponse = await axios.post(`${API}/vehicles`, listingData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const vehicleId = createResponse.data.id;
      toast.success('Listing created! Uploading photos...');
      
      // Upload photos (in production, would use cloud storage)
      // For now, we'll simulate the upload
      for (const [category, categoryPhotos] of Object.entries(photos)) {
        for (const photo of categoryPhotos) {
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
        }
      }
      
      toast.success('Vehicle listing created successfully!');
      navigate(`/vehicle-auctions/my-listings`);
      
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create listing');
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
                    <SelectItem value="financed">Financed</SelectItem>
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
                    <SelectItem value="lien_exists">Lien Exists</SelectItem>
                    <SelectItem value="pending_release">Pending Release</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
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
                <Label>Mechanical Notes</Label>
                <Textarea
                  value={formData.mechanical_notes}
                  onChange={(e) => updateField('mechanical_notes', e.target.value)}
                  placeholder="Describe any mechanical issues or recent repairs..."
                  rows={4}
                />
              </div>
              <div className="space-y-2">
                <Label>Cosmetic Notes</Label>
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
          </div>
        );
        
      case 'auction':
        return (
          <div className="space-y-6">
            {/* Title & Description */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Listing Title *</Label>
                <Input
                  value={formData.title}
                  onChange={(e) => updateField('title', e.target.value)}
                  placeholder="e.g., 2020 Toyota Camry XSE - Low Mileage, One Owner"
                />
              </div>
              
              <div className="space-y-2">
                <Label>Description *</Label>
                <Textarea
                  value={formData.description}
                  onChange={(e) => updateField('description', e.target.value)}
                  placeholder="Describe your vehicle in detail..."
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
                    <SelectItem value="timed">Timed Auction</SelectItem>
                    <SelectItem value="live">Live Auction</SelectItem>
                    <SelectItem value="buy_now">Buy Now Only</SelectItem>
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
                    <SelectItem value="dealer_only">Dealers Only</SelectItem>
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
            
            {/* Deposit */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 p-4 bg-slate-50 rounded-lg">
              <Checkbox
                checked={formData.requires_deposit}
                onCheckedChange={(checked) => updateField('requires_deposit', checked)}
              />
              <div className="flex-1">
                <Label className="cursor-pointer">{t('vehicleListing.requireDeposit', 'Require Bid Deposit')}</Label>
                <p className="text-sm text-slate-500">{t('vehicleListing.depositDescription', 'Bidders must pay a refundable deposit before bidding')}</p>
              </div>
              {formData.requires_deposit && (
                <Input
                  type="number"
                  inputMode="decimal"
                  value={formData.deposit_amount}
                  onChange={(e) => updateField('deposit_amount', e.target.value)}
                  className="w-full sm:w-32 min-h-[48px]"
                  placeholder="500"
                />
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
                      <li>All information provided is accurate and complete</li>
                      <li>You have legal authority to sell this vehicle</li>
                      <li>You will respond to buyer inquiries promptly</li>
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
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            {t('vehicleListing.title', 'List Your Vehicle')}
          </h1>
          <p className="text-slate-500 mt-1">
            {t('vehicleListing.subtitle', 'Create a professional vehicle auction listing')}
          </p>
          
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
            <Button 
              onClick={handleSubmit}
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
                  <CheckCircle className="h-4 w-4" /> {t('vehicleListing.submitListing', 'Submit Listing')}
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default CreateVehicleListingPage;
