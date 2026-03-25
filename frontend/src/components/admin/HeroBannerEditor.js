import API_BASE from '../../config';
/**
 * BidVex Hero Banner Editor
 * Fully customizable banner management with live preview
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Slider } from '../ui/slider';
import { Badge } from '../ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { useTranslation } from 'react-i18next';
import {
  Image as ImageIcon, 
  Save, 
  Loader2, 
  Plus, 
  Trash2, 
  Edit2, 
  Eye,
  EyeOff,
  Upload,
  RefreshCw,
  Palette,
  Type,
  Move,
  X,
  ChevronUp,
  ChevronDown
} from 'lucide-react';

const API = API_BASE;

// Available font families
const FONT_FAMILIES = [
  { value: 'Inter', label: 'Inter' },
  { value: 'Poppins', label: 'Poppins' },
  { value: 'Roboto', label: 'Roboto' },
  { value: 'Montserrat', label: 'Montserrat' },
  { value: 'Open Sans', label: 'Open Sans' },
  { value: 'Lato', label: 'Lato' },
  { value: 'Nunito', label: 'Nunito' },
  { value: 'Playfair Display', label: 'Playfair Display' },
  { value: 'Oswald', label: 'Oswald' },
];

// Font size presets
const FONT_SIZES = [
  { value: '24px', label: '24px (Small)' },
  { value: '32px', label: '32px (Medium)' },
  { value: '40px', label: '40px (Large)' },
  { value: '48px', label: '48px (XL)' },
  { value: '56px', label: '56px (XXL)' },
  { value: '64px', label: '64px (Huge)' },
  { value: '72px', label: '72px (Giant)' },
];

const SUBTITLE_SIZES = [
  { value: '14px', label: '14px (Small)' },
  { value: '16px', label: '16px (Medium)' },
  { value: '18px', label: '18px (Large)' },
  { value: '20px', label: '20px (XL)' },
  { value: '24px', label: '24px (XXL)' },
];

// Default banner form values
const DEFAULT_BANNER = {
  // Bilingual content
  title_en: '',
  title_fr: '',
  subtitle_en: '',
  subtitle_fr: '',
  cta_text_en: 'Learn More',
  cta_text_fr: 'En savoir plus',
  // Legacy fields
  title: '',
  subtitle: '',
  cta_text: 'Learn More',
  // Images
  image_desktop: '',
  image_mobile: '',
  cta_link: '/marketplace',
  // Styling - all independent
  title_color: '#FFFFFF',
  subtitle_color: '#FFFFFF',
  button_color: '#FFFFFF',
  button_text_color: '#000000',
  text_color: '#FFFFFF',
  font_family: 'Inter',
  title_font_size: '48px',
  subtitle_font_size: '18px',
  overlay_color: '#000000',
  overlay_opacity: 0.4,
  active: true,
  order: 0,
};

const HeroBannerEditor = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingBanner, setEditingBanner] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [bannerForm, setBannerForm] = useState(DEFAULT_BANNER);
  const [previewLang, setPreviewLang] = useState('en'); // For live preview language toggle

  // Fetch banners
  const fetchBanners = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/admin/hero-banners`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBanners(response.data || []);
    } catch (error) {
      console.error('Failed to fetch banners:', error);
      toast.error('Failed to load banners');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchBanners();
  }, [fetchBanners]);

  // Handle image upload
  const handleImageUpload = (e, field) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image must be less than 5MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      setBannerForm(prev => ({ ...prev, [field]: reader.result }));
    };
    reader.readAsDataURL(file);
  };

  // Save banner
  const saveBanner = async () => {
    if (!bannerForm.title.trim()) {
      toast.error('Please enter a banner title');
      return;
    }

    setSaving(true);
    try {
      if (editingBanner) {
        await axios.put(`${API}/admin/hero-banners/${editingBanner.id}`, bannerForm, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Banner updated successfully!');
      } else {
        await axios.post(`${API}/admin/hero-banners`, bannerForm, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Banner created successfully!');
      }
      resetForm();
      fetchBanners();
    } catch (error) {
      console.error('Failed to save banner:', error);
      toast.error('Failed to save banner');
    } finally {
      setSaving(false);
    }
  };

  // Delete banner
  const deleteBanner = async (bannerId) => {
    if (!window.confirm('Are you sure you want to delete this banner?')) return;

    try {
      await axios.delete(`${API}/admin/hero-banners/${bannerId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Banner deleted');
      fetchBanners();
    } catch (error) {
      toast.error('Failed to delete banner');
    }
  };

  // Toggle banner active status
  const toggleBannerActive = async (banner) => {
    try {
      await axios.put(`${API}/admin/hero-banners/${banner.id}`, {
        ...banner,
        active: !banner.active
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Banner ${!banner.active ? 'activated' : 'deactivated'}`);
      fetchBanners();
    } catch (error) {
      toast.error('Failed to update banner');
    }
  };

  // Edit banner
  const editBanner = (banner) => {
    setEditingBanner(banner);
    setBannerForm({
      ...DEFAULT_BANNER,
      ...banner,
    });
    setShowForm(true);
  };

  // Reset form
  const resetForm = () => {
    setBannerForm(DEFAULT_BANNER);
    setEditingBanner(null);
    setShowForm(false);
  };

  // Move banner order
  const moveBanner = async (banner, direction) => {
    const currentIndex = banners.findIndex(b => b.id === banner.id);
    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
    
    if (newIndex < 0 || newIndex >= banners.length) return;

    const otherBanner = banners[newIndex];
    
    try {
      // Swap orders
      await Promise.all([
        axios.put(`${API}/admin/hero-banners/${banner.id}`, { ...banner, order: otherBanner.order }, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.put(`${API}/admin/hero-banners/${otherBanner.id}`, { ...otherBanner, order: banner.order }, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      fetchBanners();
    } catch (error) {
      toast.error('Failed to reorder banners');
    }
  };

  // Render live preview
  const renderPreview = () => {
    const overlayRgba = hexToRgba(bannerForm.overlay_color, bannerForm.overlay_opacity);
    
    // Get content based on preview language
    const previewTitle = previewLang === 'fr' 
      ? (bannerForm.title_fr || bannerForm.title_en || bannerForm.title || 'Titre de la bannière')
      : (bannerForm.title_en || bannerForm.title || 'Banner Title');
    const previewSubtitle = previewLang === 'fr'
      ? (bannerForm.subtitle_fr || bannerForm.subtitle_en || bannerForm.subtitle || 'Texte de sous-titre ici')
      : (bannerForm.subtitle_en || bannerForm.subtitle || 'Subtitle text goes here');
    const previewCta = previewLang === 'fr'
      ? (bannerForm.cta_text_fr || bannerForm.cta_text_en || bannerForm.cta_text || 'En savoir plus')
      : (bannerForm.cta_text_en || bannerForm.cta_text || 'Learn More');
    
    return (
      <div className="space-y-3">
        {/* Language Toggle for Preview */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-muted-foreground">Preview Language:</span>
          <div className="flex gap-2">
            <Button
              variant={previewLang === 'en' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setPreviewLang('en')}
            >
              🇬🇧 English
            </Button>
            <Button
              variant={previewLang === 'fr' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setPreviewLang('fr')}
            >
              🇫🇷 Français
            </Button>
          </div>
        </div>
        
        {/* Preview Container */}
        <div className="relative w-full h-[300px] rounded-lg overflow-hidden bg-gray-100">
          {/* Background Image */}
          {bannerForm.image_desktop ? (
            <img
              src={bannerForm.image_desktop}
              alt="Preview"
              className="absolute inset-0 w-full h-full object-cover"
            />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-cyan-500" />
          )}
          
          {/* Overlay */}
          <div 
            className="absolute inset-0"
            style={{ backgroundColor: overlayRgba }}
          />
          
          {/* Content */}
          <div className="relative z-10 h-full flex items-center px-8">
            <div className="max-w-2xl space-y-4">
              <h2 
                style={{
                  color: bannerForm.title_color,
                  fontFamily: bannerForm.font_family,
                  fontSize: bannerForm.title_font_size,
                  fontWeight: 'bold',
                  lineHeight: 1.2,
                }}
              >
                {previewTitle}
              </h2>
              <p
                style={{
                  color: bannerForm.subtitle_color,
                  fontFamily: bannerForm.font_family,
                  fontSize: bannerForm.subtitle_font_size,
                  opacity: 0.9,
                }}
              >
                {previewSubtitle}
              </p>
              <Button
                className="mt-4"
                style={{
                  backgroundColor: bannerForm.button_color,
                  color: bannerForm.button_text_color,
                }}
              >
                {previewCta}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Convert hex to rgba
  const hexToRgba = (hex, alpha) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <ImageIcon className="h-6 w-6 text-primary" />
            Hero Banner Manager
          </h2>
          <p className="text-muted-foreground">
            Create and customize homepage banners with full styling control
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={fetchBanners} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={() => setShowForm(true)} disabled={showForm}>
            <Plus className="h-4 w-4 mr-2" />
            Add Banner
          </Button>
        </div>
      </div>

      {/* Info Card */}
      <Card className="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <CardContent className="p-4">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>📐 Recommended Size:</strong> 1920x600px for desktop, 800x400px for mobile.
            Banners display full-width on the homepage with customizable overlay and text styling.
          </p>
        </CardContent>
      </Card>

      {/* Banner Form */}
      {showForm && (
        <Card className="border-2 border-primary">
          <CardHeader className="pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                {editingBanner ? <Edit2 className="h-5 w-5" /> : <Plus className="h-5 w-5" />}
                {editingBanner ? 'Edit Banner' : 'Create New Banner'}
              </CardTitle>
              <Button variant="ghost" size="icon" onClick={resetForm}>
                <X className="h-5 w-5" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Live Preview */}
            <div>
              <Label className="text-base font-semibold flex items-center gap-2 mb-3">
                <Eye className="h-4 w-4" />
                Live Preview
              </Label>
              {renderPreview()}
            </div>

            {/* Content Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column - Bilingual Content */}
              <div className="space-y-4">
                <h4 className="font-semibold flex items-center gap-2 text-sm text-muted-foreground uppercase tracking-wide">
                  <Type className="h-4 w-4" />
                  Content (Bilingual)
                </h4>
                
                {/* English Content */}
                <div className="space-y-3 p-4 border rounded-lg bg-blue-50/50 dark:bg-blue-900/10">
                  <div className="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300">
                    🇬🇧 English
                  </div>
                  <div>
                    <Label htmlFor="title_en">Title (EN) *</Label>
                    <Input
                      id="title_en"
                      value={bannerForm.title_en}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, title_en: e.target.value, title: e.target.value }))}
                      placeholder="Discover. Bid. Win."
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="subtitle_en">Subtitle (EN)</Label>
                    <Input
                      id="subtitle_en"
                      value={bannerForm.subtitle_en}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, subtitle_en: e.target.value, subtitle: e.target.value }))}
                      placeholder="Experience the thrill of live auctions"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="cta_text_en">Button Text (EN)</Label>
                    <Input
                      id="cta_text_en"
                      value={bannerForm.cta_text_en}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, cta_text_en: e.target.value, cta_text: e.target.value }))}
                      placeholder="Learn More"
                      className="mt-1"
                    />
                  </div>
                </div>

                {/* French Content */}
                <div className="space-y-3 p-4 border rounded-lg bg-red-50/50 dark:bg-red-900/10">
                  <div className="flex items-center gap-2 text-sm font-medium text-red-700 dark:text-red-300">
                    🇫🇷 Français
                  </div>
                  <div>
                    <Label htmlFor="title_fr">Titre (FR) *</Label>
                    <Input
                      id="title_fr"
                      value={bannerForm.title_fr}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, title_fr: e.target.value }))}
                      placeholder="Découvrez. Enchérissez. Gagnez."
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="subtitle_fr">Sous-titre (FR)</Label>
                    <Input
                      id="subtitle_fr"
                      value={bannerForm.subtitle_fr}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, subtitle_fr: e.target.value }))}
                      placeholder="Vivez le frisson des enchères en direct"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="cta_text_fr">Texte du bouton (FR)</Label>
                    <Input
                      id="cta_text_fr"
                      value={bannerForm.cta_text_fr}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, cta_text_fr: e.target.value }))}
                      placeholder="En savoir plus"
                      className="mt-1"
                    />
                  </div>
                </div>
                
                {/* Button Link (same for both languages) */}
                <div>
                  <Label htmlFor="cta_link">Button Link (both languages)</Label>
                  <Input
                    id="cta_link"
                    value={bannerForm.cta_link}
                    onChange={(e) => setBannerForm(prev => ({ ...prev, cta_link: e.target.value }))}
                    placeholder="/marketplace"
                    className="mt-1"
                  />
                </div>

                {/* Images */}
                <h4 className="font-semibold flex items-center gap-2 text-sm text-muted-foreground uppercase tracking-wide pt-4">
                  <Upload className="h-4 w-4" />
                  Images
                </h4>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>{t("admin.desktopImage")}</Label>
                    <div className="mt-1 space-y-2">
                      <div className="w-full h-24 rounded-lg overflow-hidden bg-gray-100 border-2 border-dashed">
                        {bannerForm.image_desktop ? (
                          <img src={bannerForm.image_desktop} alt="Desktop" className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-400">
                            <ImageIcon className="h-8 w-8" />
                          </div>
                        )}
                      </div>
                      <Input
                        type="file"
                        accept="image/*"
                        onChange={(e) => handleImageUpload(e, 'image_desktop')}
                        className="text-xs"
                      />
                    </div>
                  </div>
                  <div>
                    <Label>{t("admin.mobileImage")}</Label>
                    <div className="mt-1 space-y-2">
                      <div className="w-full h-24 rounded-lg overflow-hidden bg-gray-100 border-2 border-dashed">
                        {bannerForm.image_mobile ? (
                          <img src={bannerForm.image_mobile} alt="Mobile" className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-400">
                            <ImageIcon className="h-8 w-8" />
                          </div>
                        )}
                      </div>
                      <Input
                        type="file"
                        accept="image/*"
                        onChange={(e) => handleImageUpload(e, 'image_mobile')}
                        className="text-xs"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column - Styling */}
              <div className="space-y-4">
                <h4 className="font-semibold flex items-center gap-2 text-sm text-muted-foreground uppercase tracking-wide">
                  <Palette className="h-4 w-4" />
                  Colors
                </h4>

                {/* Title & Subtitle Colors */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>{t("admin.titleColor")}</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="color"
                        value={bannerForm.title_color || '#FFFFFF'}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, title_color: e.target.value }))}
                        className="w-10 h-10 rounded cursor-pointer border"
                      />
                      <Input
                        value={bannerForm.title_color || '#FFFFFF'}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, title_color: e.target.value }))}
                        className="flex-1 font-mono text-sm"
                        maxLength={7}
                      />
                    </div>
                  </div>
                  <div>
                    <Label>{t("admin.subtitleColor")}</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="color"
                        value={bannerForm.subtitle_color || '#FFFFFF'}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, subtitle_color: e.target.value }))}
                        className="w-10 h-10 rounded cursor-pointer border"
                      />
                      <Input
                        value={bannerForm.subtitle_color || '#FFFFFF'}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, subtitle_color: e.target.value }))}
                        className="flex-1 font-mono text-sm"
                        maxLength={7}
                      />
                    </div>
                  </div>
                </div>

                {/* Button Colors */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>{t("admin.buttonBackground")}</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="color"
                        value={bannerForm.button_color || '#FFFFFF'}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, button_color: e.target.value }))}
                        className="w-10 h-10 rounded cursor-pointer border"
                      />
                      <Input
                        value={bannerForm.button_color || '#FFFFFF'}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, button_color: e.target.value }))}
                        className="flex-1 font-mono text-sm"
                        maxLength={7}
                      />
                    </div>
                  </div>
                  <div>
                    <Label>{t("admin.buttonTextColor")}</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="color"
                        value={bannerForm.button_text_color || '#000000'}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, button_text_color: e.target.value }))}
                        className="w-10 h-10 rounded cursor-pointer border"
                      />
                      <Input
                        value={bannerForm.button_text_color || '#000000'}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, button_text_color: e.target.value }))}
                        className="flex-1 font-mono text-sm"
                        maxLength={7}
                      />
                    </div>
                  </div>
                </div>

                {/* Overlay Colors */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>{t("admin.overlayColor")}</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="color"
                        value={bannerForm.overlay_color}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, overlay_color: e.target.value }))}
                        className="w-10 h-10 rounded cursor-pointer border"
                      />
                      <Input
                        value={bannerForm.overlay_color}
                        onChange={(e) => setBannerForm(prev => ({ ...prev, overlay_color: e.target.value }))}
                        className="flex-1 font-mono text-sm"
                        maxLength={7}
                      />
                    </div>
                  </div>
                  <div>
                    <Label className="flex items-center justify-between">
                      <span>{t("admin.overlayOpacity")}</span>
                      <span className="text-muted-foreground">{Math.round(bannerForm.overlay_opacity * 100)}%</span>
                    </Label>
                    <Slider
                      value={[bannerForm.overlay_opacity * 100]}
                      onValueChange={(value) => setBannerForm(prev => ({ ...prev, overlay_opacity: value[0] / 100 }))}
                      min={0}
                      max={100}
                      step={5}
                      className="mt-3"
                    />
                  </div>
                </div>

                {/* Typography */}
                <h4 className="font-semibold flex items-center gap-2 text-sm text-muted-foreground uppercase tracking-wide pt-4">
                  <Type className="h-4 w-4" />
                  Typography
                </h4>

                <div>
                  <Label>{t("admin.fontFamily")}</Label>
                  <Select
                    value={bannerForm.font_family}
                    onValueChange={(value) => setBannerForm(prev => ({ ...prev, font_family: value }))}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {FONT_FAMILIES.map(font => (
                        <SelectItem key={font.value} value={font.value}>
                          <span style={{ fontFamily: font.value }}>{font.label}</span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>{t("admin.titleSize")}</Label>
                    <Select
                      value={bannerForm.title_font_size}
                      onValueChange={(value) => setBannerForm(prev => ({ ...prev, title_font_size: value }))}
                    >
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {FONT_SIZES.map(size => (
                          <SelectItem key={size.value} value={size.value}>{size.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>{t("admin.subtitleSize")}</Label>
                    <Select
                      value={bannerForm.subtitle_font_size}
                      onValueChange={(value) => setBannerForm(prev => ({ ...prev, subtitle_font_size: value }))}
                    >
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SUBTITLE_SIZES.map(size => (
                          <SelectItem key={size.value} value={size.value}>{size.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Status */}
                <div className="flex items-center gap-3 pt-4">
                  <Switch
                    checked={bannerForm.active}
                    onCheckedChange={(checked) => setBannerForm(prev => ({ ...prev, active: checked }))}
                  />
                  <Label>Active (visible on homepage)</Label>
                </div>

                {/* Priority/Order */}
                <div>
                  <Label htmlFor="order">Display Order (lower = first)</Label>
                  <Input
                    id="order"
                    type="number"
                    value={bannerForm.order}
                    onChange={(e) => setBannerForm(prev => ({ ...prev, order: parseInt(e.target.value) || 0 }))}
                    className="mt-1 w-24"
                    min={0}
                  />
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t">
              <Button variant="outline" onClick={resetForm}>
                Cancel
              </Button>
              <Button onClick={saveBanner} disabled={saving}>
                {saving ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving...</>
                ) : (
                  <><Save className="h-4 w-4 mr-2" /> {editingBanner ? 'Update Banner' : 'Create Banner'}</>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Banner List */}
      {!showForm && (
        <div className="space-y-4">
          {banners.length === 0 ? (
            <Card className="py-12">
              <CardContent className="text-center">
                <ImageIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-muted-foreground mb-4">No banners configured yet</p>
                <Button onClick={() => setShowForm(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Your First Banner
                </Button>
              </CardContent>
            </Card>
          ) : (
            banners.map((banner, index) => (
              <Card 
                key={banner.id} 
                className={`overflow-hidden transition-all ${!banner.active ? 'opacity-60' : ''}`}
              >
                <div className="flex">
                  {/* Thumbnail with overlay preview */}
                  <div className="w-64 h-40 flex-shrink-0 relative">
                    {banner.image_desktop ? (
                      <>
                        <img 
                          src={banner.image_desktop} 
                          alt={banner.title} 
                          className="w-full h-full object-cover" 
                        />
                        <div 
                          className="absolute inset-0"
                          style={{ 
                            backgroundColor: hexToRgba(
                              banner.overlay_color || '#000000', 
                              banner.overlay_opacity || 0.4
                            ) 
                          }}
                        />
                      </>
                    ) : (
                      <div className="w-full h-full bg-gradient-to-r from-blue-600 to-cyan-500" />
                    )}
                    {/* Preview text */}
                    <div className="absolute inset-0 flex items-center justify-center p-4">
                      <span 
                        className="text-center font-bold truncate"
                        style={{ 
                          color: banner.text_color || '#FFFFFF',
                          fontFamily: banner.font_family || 'Inter',
                          fontSize: '16px'
                        }}
                      >
                        {banner.title || 'Untitled'}
                      </span>
                    </div>
                  </div>

                  {/* Details */}
                  <div className="flex-1 p-4">
                    <div className="flex items-start justify-between">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <h4 className="font-semibold text-lg">{banner.title || 'Untitled Banner'}</h4>
                          <Badge variant={banner.active ? 'default' : 'secondary'}>
                            {banner.active ? 'Active' : 'Inactive'}
                          </Badge>
                          <Badge variant="outline">Order: {banner.order || 0}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">{banner.subtitle}</p>
                        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Palette className="h-3 w-3" />
                            Text: {banner.text_color || '#FFFFFF'}
                          </span>
                          <span className="flex items-center gap-1">
                            <Type className="h-3 w-3" />
                            {banner.font_family || 'Inter'}, {banner.title_font_size || '48px'}
                          </span>
                          <span>
                            Overlay: {Math.round((banner.overlay_opacity || 0.4) * 100)}%
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <span className="text-primary">CTA:</span>
                          <span>{banner.cta_text}</span>
                          <span className="text-muted-foreground">→</span>
                          <span className="text-muted-foreground">{banner.cta_link}</span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => moveBanner(banner, 'up')}
                          disabled={index === 0}
                          title="Move Up"
                        >
                          <ChevronUp className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => moveBanner(banner, 'down')}
                          disabled={index === banners.length - 1}
                          title="Move Down"
                        >
                          <ChevronDown className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => toggleBannerActive(banner)}
                          title={banner.active ? 'Deactivate' : 'Activate'}
                        >
                          {banner.active ? (
                            <Eye className="h-4 w-4 text-green-500" />
                          ) : (
                            <EyeOff className="h-4 w-4 text-gray-400" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => editBanner(banner)}
                          title="Edit"
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => deleteBanner(banner.id)}
                          className="text-red-500 hover:text-red-600 hover:bg-red-50"
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default HeroBannerEditor;
