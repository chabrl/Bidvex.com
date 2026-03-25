import API_BASE from '../../config';
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
import HeroBannerEditor from '../../components/admin/HeroBannerEditor';
import { useTranslation } from 'react-i18next';

const API = `${API_BASE}/api`;

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
  const { t } = useTranslation();
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
          Customize your site&apos;s appearance and homepage structure
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex w-full bg-transparent">
          <TabsTrigger value="branding" className="flex-1 flex items-center justify-center gap-2 bg-transparent">
            <Palette className="h-4 w-4" />
            Branding
          </TabsTrigger>
          <TabsTrigger value="layout" className="flex-1 flex items-center justify-center gap-2 bg-transparent">
            <Layout className="h-4 w-4" />
            Homepage Layout
          </TabsTrigger>
          <TabsTrigger value="banners" className="flex-1 flex items-center justify-center gap-2 bg-transparent">
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
              <CardDescription>{t("admin.defineBrandColors")}</CardDescription>
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
              <CardDescription>Choose your site&apos;s font family</CardDescription>
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
          <HeroBannerEditor />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default BrandingLayoutManager;
