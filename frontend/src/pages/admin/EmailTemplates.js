import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Label } from '../../components/ui/label';
import { ScrollArea } from '../../components/ui/scroll-area';
import { toast } from 'sonner';
import { 
  Mail, Save, Search, AlertCircle, CheckCircle, 
  Clock, Shield, DollarSign, Gavel, ShoppingBag,
  Megaphone, Users, RefreshCw, History
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Category icons mapping
const CATEGORY_ICONS = {
  authentication: Shield,
  financial: DollarSign,
  bidding: Gavel,
  seller: ShoppingBag,
  communication: Megaphone,
  affiliate: Users
};

// Validation helper for SendGrid template IDs
const isValidTemplateId = (id) => {
  if (!id) return true; // Empty is valid (will use default)
  return id.match(/^d-[a-f0-9]{32}$/);
};

const EmailTemplates = () => {
  const { token } = useAuth();
  const [templates, setTemplates] = useState(null);
  const [editedTemplates, setEditedTemplates] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [showAuditLog, setShowAuditLog] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});
  const [hasChanges, setHasChanges] = useState(false);

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/admin/email-templates`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTemplates(response.data);
      setEditedTemplates({});
      setValidationErrors({});
      setHasChanges(false);
    } catch (error) {
      console.error('Failed to fetch templates:', error);
      toast.error('Failed to load email templates');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchAuditLog = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/email-templates/audit-log`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAuditLog(response.data);
    } catch (error) {
      console.error('Failed to fetch audit log:', error);
    }
  }, [token]);

  useEffect(() => {
    fetchTemplates();
    fetchAuditLog();
  }, [fetchTemplates, fetchAuditLog]);

  const handleTemplateChange = (key, lang, value) => {
    const fullKey = `${key}_${lang}`;
    
    // Validate
    if (value && !isValidTemplateId(value)) {
      setValidationErrors(prev => ({
        ...prev,
        [fullKey]: 'Invalid format. Must be d- followed by 32 hex characters'
      }));
    } else {
      setValidationErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fullKey];
        return newErrors;
      });
    }
    
    setEditedTemplates(prev => ({
      ...prev,
      [fullKey]: value
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    // Check for validation errors
    if (Object.keys(validationErrors).length > 0) {
      toast.error('Please fix validation errors before saving');
      return;
    }

    try {
      setSaving(true);
      await axios.put(
        `${API}/admin/email-templates`,
        { templates: editedTemplates },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Email templates updated successfully');
      fetchTemplates();
      fetchAuditLog();
    } catch (error) {
      console.error('Failed to save templates:', error);
      toast.error(error.response?.data?.detail || 'Failed to save templates');
    } finally {
      setSaving(false);
    }
  };

  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }
    
    try {
      const response = await axios.get(`${API}/admin/email-templates/search?q=${query}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSearchResults(response.data);
    } catch (error) {
      console.error('Search failed:', error);
    }
  };

  const getCurrentValue = (key, lang) => {
    const fullKey = `${key}_${lang}`;
    if (editedTemplates.hasOwnProperty(fullKey)) {
      return editedTemplates[fullKey];
    }
    // Find in original templates
    const category = Object.values(templates?.categories || {}).find(cat =>
      cat.templates.some(t => t.key === key)
    );
    const template = category?.templates.find(t => t.key === key);
    return lang === 'en' ? template?.en_id : template?.fr_id;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="bidvex-spinner" />
      </div>
    );
  }

  return (
    <div className="space-y-6 page-transition">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Mail className="h-6 w-6 text-primary" />
            Email Template Manager
          </h2>
          <p className="text-muted-foreground mt-1">
            Manage SendGrid template IDs for all system emails
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setShowAuditLog(!showAuditLog)}
            className="gap-2"
          >
            <History className="h-4 w-4" />
            {showAuditLog ? 'Hide' : 'Show'} Audit Log
          </Button>
          
          <Button
            onClick={handleSave}
            disabled={!hasChanges || saving || Object.keys(validationErrors).length > 0}
            className="gradient-button text-white border-0 gap-2"
          >
            {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save Changes
          </Button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search templates by name or ID..."
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Search Results */}
      {searchResults && (
        <Card className="premium-card-static">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Search Results ({searchResults.count})</CardTitle>
          </CardHeader>
          <CardContent>
            {searchResults.results.length > 0 ? (
              <div className="space-y-2">
                {searchResults.results.map((result) => (
                  <div 
                    key={result.key}
                    className="flex items-center justify-between p-2 rounded-lg bg-accent/50"
                  >
                    <div>
                      <span className="font-medium">{result.name}</span>
                      <Badge variant="outline" className="ml-2 text-xs">{result.category}</Badge>
                    </div>
                    <code className="text-xs text-muted-foreground">{result.template_id}</code>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No templates found</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Audit Log Panel */}
      {showAuditLog && (
        <Card className="premium-card-static">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <History className="h-4 w-4" />
              Recent Changes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-48">
              {auditLog.length > 0 ? (
                <div className="space-y-2">
                  {auditLog.map((log, idx) => (
                    <div key={idx} className="text-sm p-2 rounded bg-accent/30 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{log.target_id}</span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(log.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        <span className="line-through">{log.old_value || 'empty'}</span>
                        <span className="mx-2">→</span>
                        <code className="text-primary">{log.new_value}</code>
                      </div>
                      <div className="text-xs">Changed by {log.admin_email}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">No changes recorded</p>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {/* Template Categories */}
      <div className="grid gap-6">
        {templates?.categories && Object.entries(templates.categories).map(([catKey, category]) => {
          const Icon = CATEGORY_ICONS[catKey] || Mail;
          
          return (
            <Card key={catKey} className="premium-card-static overflow-hidden">
              <CardHeader className="bg-accent/30 border-b border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{category.icon} {category.name}</CardTitle>
                      <CardDescription>{category.description}</CardDescription>
                    </div>
                  </div>
                  <Badge variant="outline">{category.count} templates</Badge>
                </div>
              </CardHeader>
              
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {category.templates.map((template) => (
                    <div key={template.key} className="p-4 hover:bg-accent/20 transition-colors">
                      <div className="flex flex-col gap-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <Label className="font-semibold">{template.name}</Label>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              Key: <code className="bg-muted px-1 rounded">{template.key}</code>
                            </p>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* English Template ID */}
                          <div className="space-y-1.5">
                            <Label className="text-xs flex items-center gap-1">
                              🇬🇧 English Template ID
                              {validationErrors[`${template.key}_en`] && (
                                <AlertCircle className="h-3 w-3 text-destructive" />
                              )}
                            </Label>
                            <Input
                              value={getCurrentValue(template.key, 'en') || ''}
                              onChange={(e) => handleTemplateChange(template.key, 'en', e.target.value)}
                              placeholder="d-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                              className={`font-mono text-sm ${
                                validationErrors[`${template.key}_en`] 
                                  ? 'border-destructive' 
                                  : editedTemplates[`${template.key}_en`] !== undefined 
                                    ? 'border-primary' 
                                    : ''
                              }`}
                            />
                            {validationErrors[`${template.key}_en`] && (
                              <p className="text-xs text-destructive">
                                {validationErrors[`${template.key}_en`]}
                              </p>
                            )}
                          </div>
                          
                          {/* French Template ID */}
                          <div className="space-y-1.5">
                            <Label className="text-xs flex items-center gap-1">
                              🇫🇷 French Template ID
                              {validationErrors[`${template.key}_fr`] && (
                                <AlertCircle className="h-3 w-3 text-destructive" />
                              )}
                            </Label>
                            <Input
                              value={getCurrentValue(template.key, 'fr') || ''}
                              onChange={(e) => handleTemplateChange(template.key, 'fr', e.target.value)}
                              placeholder="d-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                              className={`font-mono text-sm ${
                                validationErrors[`${template.key}_fr`] 
                                  ? 'border-destructive' 
                                  : editedTemplates[`${template.key}_fr`] !== undefined 
                                    ? 'border-primary' 
                                    : ''
                              }`}
                            />
                            {validationErrors[`${template.key}_fr`] && (
                              <p className="text-xs text-destructive">
                                {validationErrors[`${template.key}_fr`]}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Configuration Summary */}
      <Card className="premium-card-static">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-success" />
            Current Configuration Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 rounded-lg bg-accent/30">
              <div className="text-3xl font-bold text-primary">{templates?.total_templates || 0}</div>
              <div className="text-sm text-muted-foreground">Total Templates</div>
            </div>
            
            <div className="text-center p-4 rounded-lg bg-accent/30">
              <div className="text-3xl font-bold text-primary">
                {Object.keys(templates?.categories || {}).length}
              </div>
              <div className="text-sm text-muted-foreground">Categories</div>
            </div>
            
            <div className="text-center p-4 rounded-lg bg-accent/30">
              <div className="text-3xl font-bold text-primary">
                {Object.keys(editedTemplates).length}
              </div>
              <div className="text-sm text-muted-foreground">Pending Changes</div>
            </div>
            
            <div className="text-center p-4 rounded-lg bg-accent/30">
              <div className="text-3xl font-bold text-destructive">
                {Object.keys(validationErrors).length}
              </div>
              <div className="text-sm text-muted-foreground">Validation Errors</div>
            </div>
          </div>
          
          {templates?.updated_at && (
            <div className="mt-4 text-sm text-muted-foreground flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Last updated: {new Date(templates.updated_at).toLocaleString()} by {templates.updated_by}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Unsaved Changes Warning */}
      {hasChanges && (
        <div className="fixed bottom-20 md:bottom-4 left-1/2 -translate-x-1/2 z-50">
          <div className="bg-card border border-border rounded-xl shadow-lg px-6 py-3 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-warning" />
            <span className="text-sm font-medium">You have unsaved changes</span>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || Object.keys(validationErrors).length > 0}
              className="gradient-button text-white border-0"
            >
              Save Now
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmailTemplates;
