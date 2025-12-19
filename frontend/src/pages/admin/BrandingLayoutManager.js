import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Switch } from '../../components/ui/switch';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { 
  Palette, Type, Image, Layout, Save, RotateCcw, Loader2, 
  ChevronUp, ChevronDown, Eye, EyeOff, Upload, Check, Trash2,
  Plus, Edit2, GripVertical
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Available Google Fonts
const GOOGLE_FONTS = [
  { name: 'Inter', preview: 'The quick brown fox' },
  { name: 'Montserrat', preview: 'The quick brown fox' },
  { name: 'Poppins', preview: 'The quick brown fox' },
  { name: 'Roboto', preview: 'The quick brown fox' },
  { name: 'Open Sans', preview: 'The quick brown fox' },
  { name: 'Lato', preview: 'The quick brown fox' },
  { name: 'Nunito', preview: 'The quick brown fox' },
];

const BrandingLayoutManager = () => {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState('branding');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Branding state
  const [branding, setBranding] = useState({
    logo_url: null,
    logo_type: 'default',
    primary_color: '#3B82F6',
    secondary_color: '#10B981',
    accent_color: '#8B5CF6',
    surface_color: '#F8FAFC',
    font_family: 'Inter',
  });
  const [originalBranding, setOriginalBranding] = useState(null);
  
  // Layout state
  const [sections, setSections] = useState([]);
  const [originalSections, setOriginalSections] = useState([]);
  
  // Hero banners state
  const [banners, setBanners] = useState([]);
  const [editingBanner, setEditingBanner] = useState(null);
  const [showBannerForm, setShowBannerForm] = useState(false);
  
  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/admin/site-config`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const data = response.data;
      
      // Set branding
      if (data.branding) {
        setBranding(data.branding);
        setOriginalBranding(data.branding);
      }
      
      // Set layout sections
      if (data.homepage_layout?.sections) {
        const sortedSections = [...data.homepage_layout.sections].sort((a, b) => a.order - b.order);
        setSections(sortedSections);
        setOriginalSections(sortedSections);
      }
      
      // Set banners
      if (data.hero_banners) {
        setBanners(data.hero_banners);
      }
    } catch (error) {
      toast.error('Failed to load site configuration');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Branding handlers
  const handleColorChange = (field, value) => {
    setBranding(prev => ({ ...prev, [field]: value }));
  };

  const handleFontChange = (font) => {
    setBranding(prev => ({ ...prev, font_family: font }));
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    const validTypes = ['image/png', 'image/svg+xml', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      toast.error('Please upload a PNG, SVG, or WebP file');
      return;
    }

    // Convert to base64
    const reader = new FileReader();
    reader.onload = () => {
      setBranding(prev => ({
        ...prev,
        logo_url: reader.result,
        logo_type: 'uploaded'
      }));
    };
    reader.readAsDataURL(file);
  };

  const saveBranding = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/site-config/branding`, branding, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setOriginalBranding(branding);
      toast.success('Branding saved successfully!', {
        description: 'Changes will appear across the site within 5 seconds.'
      });
    } catch (error) {
      toast.error('Failed to save branding', {
        description: error.response?.data?.detail || 'Please try again.'
      });
    } finally {
      setSaving(false);
    }
  };

  const isBrandingDirty = JSON.stringify(branding) !== JSON.stringify(originalBranding);

  // Layout handlers
  const toggleSectionVisibility = (sectionId) => {
    setSections(prev => prev.map(s => 
      s.id === sectionId ? { ...s, visible: !s.visible } : s
    ));
  };

  const moveSectionUp = (index) => {
    if (index === 0) return;
    const newSections = [...sections];
    [newSections[index - 1], newSections[index]] = [newSections[index], newSections[index - 1]];
    // Update order values
    newSections.forEach((s, i) => s.order = i);
    setSections(newSections);
  };

  const moveSectionDown = (index) => {
    if (index === sections.length - 1) return;
    const newSections = [...sections];
    [newSections[index], newSections[index + 1]] = [newSections[index + 1], newSections[index]];
    // Update order values
    newSections.forEach((s, i) => s.order = i);
    setSections(newSections);
  };

  const saveLayout = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/site-config/homepage-layout`, { sections }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setOriginalSections(sections);
      toast.success('Layout saved successfully!', {
        description: 'Homepage will update within 5 seconds.'
      });
    } catch (error) {
      toast.error('Failed to save layout');
    } finally {
      setSaving(false);
    }
  };

  const isLayoutDirty = JSON.stringify(sections) !== JSON.stringify(originalSections);

  // Banner handlers
  const [bannerForm, setBannerForm] = useState({
    title: '',
    subtitle: '',
    image_desktop: '',
    image_mobile: '',
    cta_text: 'Learn More',
    cta_link: '/marketplace',
    overlay_opacity: 0.3,
    text_color: '#FFFFFF',
    active: true,
  });

  const handleBannerImageUpload = async (e, field) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      setBannerForm(prev => ({ ...prev, [field]: reader.result }));
    };
    reader.readAsDataURL(file);
  };

  const saveBanner = async () => {
    setSaving(true);
    try {
      if (editingBanner) {
        await axios.put(`${API}/admin/hero-banners/${editingBanner.id}`, bannerForm, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Banner updated!');
      } else {
        await axios.post(`${API}/admin/hero-banners`, bannerForm, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Banner created!');
      }
      setShowBannerForm(false);
      setEditingBanner(null);
      setBannerForm({
        title: '', subtitle: '', image_desktop: '', image_mobile: '',
        cta_text: 'Learn More', cta_link: '/marketplace',
        overlay_opacity: 0.3, text_color: '#FFFFFF', active: true,
      });
      fetchConfig();
    } catch (error) {
      toast.error('Failed to save banner');
    } finally {
      setSaving(false);
    }
  };

  const deleteBanner = async (bannerId) => {
    if (!window.confirm('Are you sure you want to delete this banner?')) return;
    
    try {
      await axios.delete(`${API}/admin/hero-banners/${bannerId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Banner deleted');
      fetchConfig();
    } catch (error) {
      toast.error('Failed to delete banner');
    }
  };

  const editBanner = (banner) => {
    setEditingBanner(banner);
    setBannerForm(banner);
    setShowBannerForm(true);
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
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Palette className="h-6 w-6 text-primary" />
          Branding & Layout Manager
        </h2>
        <p className="text-muted-foreground">
          Customize your site's appearance and homepage structure
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="branding" className="flex items-center gap-2">
            <Palette className="h-4 w-4" />
            Branding
          </TabsTrigger>
          <TabsTrigger value="layout" className="flex items-center gap-2">
            <Layout className="h-4 w-4" />
            Homepage Layout
          </TabsTrigger>
          <TabsTrigger value="banners" className="flex items-center gap-2">
            <Image className="h-4 w-4" />
            Hero Banners
          </TabsTrigger>
        </TabsList>

        {/* BRANDING TAB */}
        <TabsContent value="branding" className="space-y-6 mt-6">
          {/* Logo Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Image className="h-5 w-5" />
                Logo Management
              </CardTitle>
              <CardDescription>Upload your site logo (PNG, SVG, or WebP)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-6">
                <div className="w-48 h-24 border-2 border-dashed rounded-lg flex items-center justify-center bg-gray-50">
                  {branding.logo_url ? (
                    <img src={branding.logo_url} alt="Logo" className="max-h-20 max-w-44 object-contain" />
                  ) : (
                    <span className="text-muted-foreground text-sm">No logo uploaded</span>
                  )}
                </div>
                <div className="space-y-2">
                  <label className="cursor-pointer">
                    <input
                      type="file"
                      accept="image/png,image/svg+xml,image/webp"
                      onChange={handleLogoUpload}
                      className="hidden"
                    />
                    <Button variant="outline" asChild>
                      <span><Upload className="h-4 w-4 mr-2" /> Upload Logo</span>
                    </Button>
                  </label>
                  {branding.logo_url && (
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={() => setBranding(prev => ({ ...prev, logo_url: null, logo_type: 'default' }))}
                    >
                      <Trash2 className="h-4 w-4 mr-2" /> Remove
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Color Palette */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Palette className="h-5 w-5" />
                Color Palette
              </CardTitle>
              <CardDescription>Define your brand colors</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { key: 'primary_color', label: 'Primary', desc: 'Buttons, links' },
                  { key: 'secondary_color', label: 'Secondary', desc: 'Highlights' },
                  { key: 'accent_color', label: 'Accent', desc: 'Decorative' },
                  { key: 'surface_color', label: 'Surface', desc: 'Backgrounds' },
                ].map(({ key, label, desc }) => (
                  <div key={key} className="space-y-2">
                    <label className="text-sm font-medium">{label}</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={branding[key]}
                        onChange={(e) => handleColorChange(key, e.target.value)}
                        className="w-12 h-10 rounded cursor-pointer border-0"
                      />
                      <Input
                        value={branding[key]}
                        onChange={(e) => handleColorChange(key, e.target.value)}
                        className="font-mono text-sm"
                        placeholder="#000000"
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">{desc}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Typography */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Type className="h-5 w-5" />
                Typography
              </CardTitle>
              <CardDescription>Choose your site's font family</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {GOOGLE_FONTS.map((font) => (
                  <button
                    key={font.name}
                    onClick={() => handleFontChange(font.name)}
                    className={`p-4 rounded-lg border-2 text-left transition-all ${
                      branding.font_family === font.name
                        ? 'border-primary bg-primary/5'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <p className="font-medium text-sm">{font.name}</p>
                    <p 
                      className="text-muted-foreground mt-1"
                      style={{ fontFamily: `"${font.name}", sans-serif` }}
                    >
                      {font.preview}
                    </p>
                    {branding.font_family === font.name && (
                      <Badge className="mt-2 bg-primary">Selected</Badge>
                    )}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <div className="flex justify-end">
            <Button
              onClick={saveBranding}
              disabled={!isBrandingDirty || saving}
              className={isBrandingDirty ? 'bg-primary' : 'bg-gray-300'}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
              {isBrandingDirty ? 'Save Branding' : 'No Changes'}
            </Button>
          </div>
        </TabsContent>

        {/* LAYOUT TAB */}
        <TabsContent value="layout" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layout className="h-5 w-5" />
                Homepage Sections
              </CardTitle>
              <CardDescription>
                Toggle visibility and reorder sections on the homepage
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {sections.map((section, index) => (
                  <div
                    key={section.id}
                    className={`flex items-center justify-between p-3 rounded-lg border ${
                      section.visible ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-100'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <GripVertical className="h-5 w-5 text-gray-400" />
                      <span className={`font-medium ${!section.visible && 'text-gray-400'}`}>
                        {section.name}
                      </span>
                      {section.id === 'browse_items' && (
                        <Badge variant="outline" className="text-xs">Requested Toggle</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => moveSectionUp(index)}
                        disabled={index === 0}
                      >
                        <ChevronUp className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => moveSectionDown(index)}
                        disabled={index === sections.length - 1}
                      >
                        <ChevronDown className="h-4 w-4" />
                      </Button>
                      <Switch
                        checked={section.visible}
                        onCheckedChange={() => toggleSectionVisibility(section.id)}
                      />
                      {section.visible ? (
                        <Eye className="h-4 w-4 text-green-600" />
                      ) : (
                        <EyeOff className="h-4 w-4 text-gray-400" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button
              onClick={saveLayout}
              disabled={!isLayoutDirty || saving}
              className={isLayoutDirty ? 'bg-primary' : 'bg-gray-300'}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
              {isLayoutDirty ? 'Save Layout' : 'No Changes'}
            </Button>
          </div>
        </TabsContent>

        {/* BANNERS TAB */}
        <TabsContent value="banners" className="space-y-6 mt-6">
          {!showBannerForm ? (
            <>
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold">Hero Banners</h3>
                <Button onClick={() => setShowBannerForm(true)}>
                  <Plus className="h-4 w-4 mr-2" /> Add Banner
                </Button>
              </div>

              {banners.length === 0 ? (
                <Card className="p-8 text-center">
                  <Image className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                  <p className="text-muted-foreground">No banners yet. Create your first hero banner!</p>
                </Card>
              ) : (
                <div className="grid gap-4">
                  {banners.map((banner) => (
                    <Card key={banner.id} className="overflow-hidden">
                      <div className="flex">
                        <div className="w-48 h-32 bg-gray-100 flex-shrink-0">
                          {banner.image_desktop ? (
                            <img src={banner.image_desktop} alt={banner.title} className="w-full h-full object-cover" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-gray-400">
                              <Image className="h-8 w-8" />
                            </div>
                          )}
                        </div>
                        <div className="flex-1 p-4">
                          <div className="flex items-start justify-between">
                            <div>
                              <h4 className="font-semibold">{banner.title || 'Untitled Banner'}</h4>
                              <p className="text-sm text-muted-foreground">{banner.subtitle}</p>
                              <div className="flex items-center gap-2 mt-2">
                                <Badge variant={banner.active ? 'default' : 'secondary'}>
                                  {banner.active ? 'Active' : 'Inactive'}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                  CTA: {banner.cta_text} → {banner.cta_link}
                                </span>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <Button variant="ghost" size="sm" onClick={() => editBanner(banner)}>
                                <Edit2 className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => deleteBanner(banner.id)}>
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{editingBanner ? 'Edit Banner' : 'Create New Banner'}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Title</label>
                    <Input
                      value={bannerForm.title}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, title: e.target.value }))}
                      placeholder="Banner headline"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Subtitle</label>
                    <Input
                      value={bannerForm.subtitle}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, subtitle: e.target.value }))}
                      placeholder="Supporting text"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Desktop Image</label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => handleBannerImageUpload(e, 'image_desktop')}
                      className="block w-full text-sm mt-1"
                    />
                    {bannerForm.image_desktop && (
                      <img src={bannerForm.image_desktop} alt="Preview" className="mt-2 h-20 object-cover rounded" />
                    )}
                  </div>
                  <div>
                    <label className="text-sm font-medium">Mobile Image</label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => handleBannerImageUpload(e, 'image_mobile')}
                      className="block w-full text-sm mt-1"
                    />
                    {bannerForm.image_mobile && (
                      <img src={bannerForm.image_mobile} alt="Preview" className="mt-2 h-20 object-cover rounded" />
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="text-sm font-medium">CTA Button Text</label>
                    <Input
                      value={bannerForm.cta_text}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, cta_text: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">CTA Link</label>
                    <Input
                      value={bannerForm.cta_link}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, cta_link: e.target.value }))}
                      placeholder="/marketplace"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Overlay Opacity</label>
                    <Input
                      type="number"
                      min={0}
                      max={1}
                      step={0.1}
                      value={bannerForm.overlay_opacity}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, overlay_opacity: parseFloat(e.target.value) }))}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={bannerForm.active}
                      onCheckedChange={(checked) => setBannerForm(prev => ({ ...prev, active: checked }))}
                    />
                    <span className="text-sm">Active</span>
                  </div>
                  <div>
                    <label className="text-sm font-medium mr-2">Text Color</label>
                    <input
                      type="color"
                      value={bannerForm.text_color}
                      onChange={(e) => setBannerForm(prev => ({ ...prev, text_color: e.target.value }))}
                      className="w-10 h-8 rounded cursor-pointer"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <Button variant="outline" onClick={() => { setShowBannerForm(false); setEditingBanner(null); }}>
                    Cancel
                  </Button>
                  <Button onClick={saveBanner} disabled={saving}>
                    {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                    {editingBanner ? 'Update Banner' : 'Create Banner'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default BrandingLayoutManager;
