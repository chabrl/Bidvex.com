import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { FileText, Globe, Save, RefreshCw, Mail, MessageCircle, ExternalLink } from 'lucide-react';
import RichTextEditor from '../../components/RichTextEditor';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SiteContentManager = () => {
  const [pages, setPages] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeLanguage, setActiveLanguage] = useState('en');
  const [hasChanges, setHasChanges] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    fetchPages();
  }, []);

  const fetchPages = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      
      if (!token) {
        toast.error('Not authenticated. Please login.');
        setLoading(false);
        return;
      }

      console.log('[SiteContentManager] Fetching pages...', {
        apiUrl: `${API}/admin/site-config/legal-pages`
      });

      const response = await axios.get(`${API}/admin/site-config/legal-pages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      console.log('[SiteContentManager] Fetch response:', {
        success: response.data.success,
        pageCount: response.data.pages ? Object.keys(response.data.pages).length : 0,
        updated_at: response.data.updated_at
      });

      if (response.data.success) {
        setPages(response.data.pages);
        setLastUpdated(response.data.updated_at);
        setHasChanges(false); // Reset changes flag after fresh fetch
      } else {
        toast.error('Failed to load pages: ' + (response.data.message || 'Unknown error'));
      }
    } catch (error) {
      console.error('[SiteContentManager] Fetch error:', error);
      
      if (error.response?.status === 401) {
        toast.error('Authentication failed. Please login again.');
      } else if (error.response?.status === 403) {
        toast.error('Access denied. Admin permissions required.');
      } else {
        toast.error('Failed to load pages. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleContentChange = (pageKey, language, field, value) => {
    setPages(prev => ({
      ...prev,
      [pageKey]: {
        ...prev[pageKey],
        [language]: {
          ...prev[pageKey][language],
          [field]: value
        }
      }
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!pages) {
      toast.error('No pages to save');
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      
      if (!token) {
        toast.error('❌ Not authenticated. Please login again.');
        setSaving(false);
        return;
      }

      console.log('[SiteContentManager] Saving pages...', { 
        pageKeys: Object.keys(pages),
        apiUrl: `${API}/admin/site-config/legal-pages`
      });

      const response = await axios.put(
        `${API}/admin/site-config/legal-pages`,
        pages,
        { 
          headers: { 
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          } 
        }
      );

      console.log('[SiteContentManager] Save response:', response.data);

      if (response.data.success) {
        toast.success('✅ Pages updated successfully! Changes are live.', {
          duration: 3000,
        });
        setHasChanges(false);
        setLastUpdated(response.data.updated_at);
        
        // Fetch fresh data from database to confirm save
        await fetchPages();
      } else {
        toast.error('❌ Save failed: ' + (response.data.message || 'Unknown error'));
      }
    } catch (error) {
      console.error('[SiteContentManager] Save error:', error);
      
      if (error.response) {
        // Server responded with error
        const status = error.response.status;
        const message = error.response.data?.detail || error.response.data?.message || 'Unknown error';
        
        if (status === 401) {
          toast.error('❌ Authentication failed. Please login again.');
        } else if (status === 403) {
          toast.error('❌ Access denied. Admin permissions required.');
        } else {
          toast.error(`❌ Save failed (${status}): ${message}`);
        }
      } else if (error.request) {
        // Request made but no response
        toast.error('❌ No response from server. Please check your connection.');
      } else {
        // Error setting up request
        toast.error('❌ Failed to save changes: ' + error.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const getLinkTypeIcon = (linkType) => {
    switch (linkType) {
      case 'page': return <FileText className="h-4 w-4" />;
      case 'mailto': return <Mail className="h-4 w-4" />;
      case 'chatbot': return <MessageCircle className="h-4 w-4" />;
      default: return <ExternalLink className="h-4 w-4" />;
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading site content...</p>
        </div>
      </div>
    );
  }

  if (!pages) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No pages configured yet.</p>
        <Button onClick={fetchPages} className="mt-4">
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  const pageConfigs = [
    { key: 'how_it_works', title: 'How It Works', icon: '📚', frTitle: 'Comment ça marche' },
    { key: 'privacy_policy', title: 'Privacy Policy', icon: '🔒', frTitle: 'Confidentialité' },
    { key: 'terms_of_service', title: 'Terms & Conditions', icon: '📜', frTitle: 'Conditions d\'utilisation' },
    { key: 'support', title: 'Contact Support', icon: '💬', frTitle: 'Contacter le support' }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="h-6 w-6" />
            Site Content & Pages
          </h2>
          <p className="text-muted-foreground mt-1">
            Manage footer links and legal pages content (English & French)
          </p>
          {lastUpdated && (
            <p className="text-xs text-muted-foreground mt-1">
              Last updated: {new Date(lastUpdated).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button 
            onClick={fetchPages} 
            variant="outline"
            disabled={saving}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={!hasChanges || saving}
            className={hasChanges ? 'bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0' : ''}
          >
            {saving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                {hasChanges ? 'Save Changes' : 'No Changes'}
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Unsaved Changes Warning */}
      {hasChanges && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center gap-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <p className="font-medium text-amber-900">You have unsaved changes</p>
            <p className="text-sm text-amber-700">Don't forget to click "Save Changes" to apply your edits.</p>
          </div>
        </div>
      )}

      {/* Language Toggle */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-4">
            <Globe className="h-5 w-5 text-muted-foreground" />
            <span className="font-medium">Editing Language:</span>
            <div className="flex gap-2">
              <Button
                variant={activeLanguage === 'en' ? 'default' : 'outline'}
                onClick={() => setActiveLanguage('en')}
                className={activeLanguage === 'en' ? 'bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white border-0' : ''}
              >
                🇬🇧 English
              </Button>
              <Button
                variant={activeLanguage === 'fr' ? 'default' : 'outline'}
                onClick={() => setActiveLanguage('fr')}
                className={activeLanguage === 'fr' ? 'bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white border-0' : ''}
              >
                🇫🇷 Français
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pages Editor */}
      {pageConfigs.map((config) => {
        const pageData = pages[config.key];
        const currentLang = activeLanguage;
        const langData = pageData?.[currentLang];

        if (!langData) return null;

        return (
          <Card key={config.key}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{config.icon}</span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span>{activeLanguage === 'en' ? config.title : config.frTitle}</span>
                      <Badge variant="outline" className="font-normal">
                        {activeLanguage === 'en' ? 'English' : 'Français'}
                      </Badge>
                    </div>
                    <p className="text-sm font-normal text-muted-foreground mt-1">
                      {langData.link_value || 'No link configured'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {getLinkTypeIcon(langData.link_type)}
                  <Badge variant="secondary">{langData.link_type}</Badge>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Title */}
              <div>
                <label className="text-sm font-medium mb-2 block">Page Title</label>
                <Input
                  value={langData.title || ''}
                  onChange={(e) => handleContentChange(config.key, currentLang, 'title', e.target.value)}
                  placeholder={`Enter ${currentLang === 'en' ? 'English' : 'French'} title...`}
                  className="max-w-xl"
                />
              </div>

              {/* Link Type */}
              <div>
                <label className="text-sm font-medium mb-2 block">Link Type</label>
                <div className="flex gap-2">
                  <Button
                    variant={langData.link_type === 'page' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handleContentChange(config.key, currentLang, 'link_type', 'page')}
                  >
                    <FileText className="h-4 w-4 mr-2" />
                    Page
                  </Button>
                  <Button
                    variant={langData.link_type === 'mailto' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handleContentChange(config.key, currentLang, 'link_type', 'mailto')}
                  >
                    <Mail className="h-4 w-4 mr-2" />
                    Email
                  </Button>
                  <Button
                    variant={langData.link_type === 'chatbot' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handleContentChange(config.key, currentLang, 'link_type', 'chatbot')}
                  >
                    <MessageCircle className="h-4 w-4 mr-2" />
                    AI Chatbot
                  </Button>
                </div>
              </div>

              {/* Link Value (only for page and mailto) */}
              {langData.link_type !== 'chatbot' && (
                <div>
                  <label className="text-sm font-medium mb-2 block">
                    {langData.link_type === 'mailto' ? 'Email Address' : 'Page URL'}
                  </label>
                  <Input
                    value={langData.link_value || ''}
                    onChange={(e) => handleContentChange(config.key, currentLang, 'link_value', e.target.value)}
                    placeholder={langData.link_type === 'mailto' ? 'support@bidvex.com' : '/page-url'}
                    className="max-w-xl"
                  />
                </div>
              )}

              {/* Rich Text Editor */}
              <div>
                <label className="text-sm font-medium mb-2 block">Page Content (HTML)</label>
                <RichTextEditor
                  content={langData.content || ''}
                  onChange={(value) => handleContentChange(config.key, currentLang, 'content', value)}
                  placeholder={`Enter ${currentLang === 'en' ? 'English' : 'French'} content...`}
                />
                <p className="text-xs text-muted-foreground mt-2">
                  Use the editor toolbar to format text, add links, lists, and more. HTML is supported.
                </p>
              </div>
            </CardContent>
          </Card>
        );
      })}

      {/* Footer Save Button */}
      {hasChanges && (
        <div className="sticky bottom-4 flex justify-center">
          <Button 
            onClick={handleSave} 
            disabled={saving}
            size="lg"
            className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0 shadow-lg"
          >
            {saving ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent mr-2"></div>
                Saving Changes...
              </>
            ) : (
              <>
                <Save className="h-5 w-5 mr-2" />
                Save All Changes
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  );
};

export default SiteContentManager;
