import API_BASE from '../../config';
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
  Megaphone, Users, RefreshCw, History, Eye, EyeOff,
  Rocket, MapPin, Zap, X, Code, Globe, Send, FileText
} from 'lucide-react';

const API = API_BASE;

// Category icons mapping
const CATEGORY_ICONS = {
  authentication: Shield,
  financial: DollarSign,
  bidding: Gavel,
  seller: ShoppingBag,
  communication: Megaphone,
  affiliate: Users,
  lifecycle: Rocket,
  geo: MapPin,
  triggers: Zap
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
  const [previewKey, setPreviewKey] = useState(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [showTestPanel, setShowTestPanel] = useState(false);
  const [testConfig, setTestConfig] = useState({
    to_email: '',
    hammer_price: '25000',
    buyer_province: 'QC',
    buyer_tier: 'free',
    seller_tier: 'free',
    category: 'vehicle',
  });
  const [testSending, setTestSending] = useState(false);
  const [testInvoicePreview, setTestInvoicePreview] = useState(null);
  const [testInvoiceHtml, setTestInvoiceHtml] = useState('');
  const [testInvoiceLoading, setTestInvoiceLoading] = useState(false);

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/admin/email-templates`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const d = response.data;
      setTemplates(d.categories ? d : { categories: [], total_templates: 0 });
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

  const loadPreview = async (templateKey) => {
    if (previewKey === templateKey) {
      setPreviewKey(null);
      setPreviewHtml('');
      return;
    }
    try {
      setPreviewLoading(true);
      setPreviewKey(templateKey);
      const response = await axios.get(`${API}/admin/email-templates/${templateKey}/preview`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPreviewHtml(response.data.html_content || '');
      setShowCode(false);
    } catch {
      setPreviewHtml('');
      toast.error('No HTML preview available for this template');
    } finally {
      setPreviewLoading(false);
    }
  };

  const previewInvoice = async () => {
    try {
      setTestInvoiceLoading(true);
      const response = await axios.post(`${API}/admin/email-templates/preview-invoice`, {
        hammer_price: parseFloat(testConfig.hammer_price) || 25000,
        buyer_province: testConfig.buyer_province,
        buyer_tier: testConfig.buyer_tier,
        seller_tier: testConfig.seller_tier,
        category: testConfig.category,
      }, { headers: { Authorization: `Bearer ${token}` } });
      setTestInvoicePreview(response.data.invoice);
      setTestInvoiceHtml(response.data.html_content || '');
    } catch (err) {
      toast.error('Failed to generate invoice preview');
    } finally {
      setTestInvoiceLoading(false);
    }
  };

  const sendTestEmail = async () => {
    if (!testConfig.to_email) {
      toast.error('Please enter a recipient email address');
      return;
    }
    try {
      setTestSending(true);
      const response = await axios.post(`${API}/admin/email-templates/send-test`, {
        to_email: testConfig.to_email,
        hammer_price: parseFloat(testConfig.hammer_price) || 25000,
        buyer_province: testConfig.buyer_province,
        buyer_tier: testConfig.buyer_tier,
        seller_tier: testConfig.seller_tier,
        category: testConfig.category,
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Test email sent to ${response.data.to_email} (${response.data.status_code})`);
      setTestInvoicePreview(response.data.invoice_summary);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to send test email');
    } finally {
      setTestSending(false);
    }
  };


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
            onClick={() => setShowTestPanel(!showTestPanel)}
            className="gap-2"
            data-testid="send-test-email-toggle"
          >
            <Send className="h-4 w-4" />
            {showTestPanel ? 'Hide' : 'Send Test Email'}
          </Button>

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

      {/* Send Test Email Panel */}
      {showTestPanel && (
        <Card className="premium-card-static border-primary/30" data-testid="test-email-panel">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              Draft Invoice Test Email
            </CardTitle>
            <CardDescription>
              Send a bilingual draft invoice using the Master Pricing Structure. Tax rates adjust automatically by province.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Recipient Email</Label>
                <Input
                  type="email"
                  value={testConfig.to_email}
                  onChange={(e) => setTestConfig(p => ({ ...p, to_email: e.target.value }))}
                  placeholder="you@example.com"
                  data-testid="test-email-recipient"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Hammer Price (CAD)</Label>
                <Input
                  type="number"
                  value={testConfig.hammer_price}
                  onChange={(e) => setTestConfig(p => ({ ...p, hammer_price: e.target.value }))}
                  placeholder="25000"
                  data-testid="test-email-price"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Category</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={testConfig.category}
                  onChange={(e) => setTestConfig(p => ({ ...p, category: e.target.value }))}
                  data-testid="test-email-category"
                >
                  <option value="vehicle">Vehicle</option>
                  <option value="general">General</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Buyer Province</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={testConfig.buyer_province}
                  onChange={(e) => setTestConfig(p => ({ ...p, buyer_province: e.target.value }))}
                  data-testid="test-email-province"
                >
                  <option value="QC">Quebec (GST 5% + QST 9.975% = 14.975%)</option>
                  <option value="ON">Ontario (HST 13%)</option>
                  <option value="BC">British Columbia (GST 5% + PST 7%)</option>
                  <option value="AB">Alberta (GST 5%)</option>
                  <option value="NS">Nova Scotia (HST 15%)</option>
                  <option value="NB">New Brunswick (HST 15%)</option>
                  <option value="MB">Manitoba (GST 5% + RST 7%)</option>
                  <option value="SK">Saskatchewan (GST 5% + PST 6%)</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Buyer Tier</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={testConfig.buyer_tier}
                  onChange={(e) => setTestConfig(p => ({ ...p, buyer_tier: e.target.value }))}
                  data-testid="test-email-buyer-tier"
                >
                  <option value="free">Free (5% Premium)</option>
                  <option value="premium">Premium (3.5% Premium)</option>
                  <option value="vip">VIP Elite (3% Premium)</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Seller Tier</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={testConfig.seller_tier}
                  onChange={(e) => setTestConfig(p => ({ ...p, seller_tier: e.target.value }))}
                  data-testid="test-email-seller-tier"
                >
                  <option value="free">Free (4% Commission)</option>
                  <option value="premium">Premium (2.5% Commission)</option>
                  <option value="vip">VIP Elite (2% Commission)</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Button
                onClick={previewInvoice}
                disabled={testInvoiceLoading}
                variant="outline"
                className="gap-2"
                data-testid="preview-invoice-btn"
              >
                {testInvoiceLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
                Preview Invoice
              </Button>
              <Button
                onClick={sendTestEmail}
                disabled={testSending || !testConfig.to_email}
                className="gradient-button text-white border-0 gap-2"
                data-testid="send-test-email-btn"
              >
                {testSending ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Send Test Email
              </Button>
            </div>

            {/* Pricing Breakdown */}
            {testInvoicePreview && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4" data-testid="invoice-breakdown">
                <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4 space-y-2">
                  <h4 className="text-sm font-bold text-blue-900 flex items-center gap-1.5">
                    <DollarSign className="h-4 w-4" /> Buyer Charges
                  </h4>
                  <div className="text-xs space-y-1 text-blue-800">
                    <div className="flex justify-between"><span>Hammer Price</span><span className="font-mono">${Number(testInvoicePreview.hammer_price).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between"><span>Buyer Premium ({(testInvoicePreview.buyer_premium_rate * 100).toFixed(1)}%)</span><span className="font-mono">${Number(testInvoicePreview.buyer_premium).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between"><span>Platform Fee (2.5%)</span><span className="font-mono">${Number(testInvoicePreview.buyer_platform_fee).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between"><span>Stripe Processing</span><span className="font-mono">${Number(testInvoicePreview.buyer_stripe_fee).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between border-t border-blue-200 pt-1"><span>Subtotal</span><span className="font-mono font-bold">${Number(testInvoicePreview.buyer_subtotal).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between text-amber-700"><span>Tax ({testInvoicePreview.buyer_tax_label})</span><span className="font-mono">${Number(testInvoicePreview.buyer_total_tax).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between border-t border-blue-300 pt-1 font-bold text-blue-900"><span>TOTAL</span><span className="font-mono">${Number(testInvoicePreview.buyer_total).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                  </div>
                </div>
                <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 space-y-2">
                  <h4 className="text-sm font-bold text-amber-900 flex items-center gap-1.5">
                    <ShoppingBag className="h-4 w-4" /> Seller Deductions
                  </h4>
                  <div className="text-xs space-y-1 text-amber-800">
                    <div className="flex justify-between"><span>Hammer Price</span><span className="font-mono">${Number(testInvoicePreview.hammer_price).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between text-red-600"><span>Commission ({(testInvoicePreview.seller_commission_rate * 100).toFixed(1)}%)</span><span className="font-mono">-${Number(testInvoicePreview.seller_commission).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between text-red-600"><span>Platform Fee (2.5%)</span><span className="font-mono">-${Number(testInvoicePreview.seller_platform_fee).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between text-red-600"><span>Stripe Processing</span><span className="font-mono">-${Number(testInvoicePreview.seller_stripe_fee).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between text-red-600 border-t border-amber-200 pt-1"><span>Total Deductions</span><span className="font-mono font-bold">-${Number(testInvoicePreview.seller_subtotal_deductions).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between text-amber-700"><span>Tax on Fees ({testInvoicePreview.seller_tax_label})</span><span className="font-mono">-${Number(testInvoicePreview.seller_total_tax).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                    <div className="flex justify-between border-t border-amber-300 pt-1 font-bold text-green-700"><span>NET PAYOUT</span><span className="font-mono">${Number(testInvoicePreview.seller_net_payout).toLocaleString('en', {minimumFractionDigits: 2})}</span></div>
                  </div>
                </div>
              </div>
            )}

            {/* Invoice HTML Preview */}
            {testInvoiceHtml && (
              <div className="mt-4 border border-border rounded-lg overflow-hidden" data-testid="invoice-html-preview">
                <div className="bg-accent/40 px-4 py-2 border-b border-border flex items-center justify-between">
                  <span className="text-xs font-semibold flex items-center gap-1.5"><Eye className="h-3.5 w-3.5" /> Invoice Email Preview</span>
                  <Button variant="ghost" size="sm" onClick={() => setTestInvoiceHtml('')} className="h-7 w-7 p-0"><X className="h-3.5 w-3.5" /></Button>
                </div>
                <div className="bg-white">
                  <iframe
                    srcDoc={testInvoiceHtml}
                    title="Draft Invoice Preview"
                    className="w-full border-0"
                    style={{ height: '700px' }}
                    sandbox="allow-same-origin"
                    data-testid="invoice-preview-iframe"
                  />
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

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
                              {template.is_bilingual && (
                                <Badge variant="outline" className="ml-2 text-[10px] py-0" data-testid={`bilingual-badge-${template.key}`}>
                                  <Globe className="h-3 w-3 mr-1" /> Bilingual
                                </Badge>
                              )}
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => loadPreview(template.key)}
                            className="gap-1.5"
                            data-testid={`preview-btn-${template.key}`}
                          >
                            {previewKey === template.key ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                            {previewKey === template.key ? 'Hide' : 'Preview'}
                          </Button>
                        </div>
                        
                        {template.is_bilingual ? (
                          <div className="space-y-1.5">
                            <Label className="text-xs flex items-center gap-1">
                              <Globe className="h-3 w-3" /> Bilingual Template ID (EN+FR)
                            </Label>
                            <Input
                              value={getCurrentValue(template.key, 'en') || ''}
                              onChange={(e) => {
                                handleTemplateChange(template.key, 'en', e.target.value);
                                handleTemplateChange(template.key, 'fr', e.target.value);
                              }}
                              placeholder="d-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                              className={`font-mono text-sm ${
                                editedTemplates[`${template.key}_en`] !== undefined ? 'border-primary' : ''
                              }`}
                              data-testid={`template-id-bl-${template.key}`}
                            />
                          </div>
                        ) : (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                              <Label className="text-xs flex items-center gap-1">
                                EN English Template ID
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
                                data-testid={`template-id-en-${template.key}`}
                              />
                              {validationErrors[`${template.key}_en`] && (
                                <p className="text-xs text-destructive">
                                  {validationErrors[`${template.key}_en`]}
                                </p>
                              )}
                            </div>
                            
                            <div className="space-y-1.5">
                              <Label className="text-xs flex items-center gap-1">
                                FR French Template ID
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
                                data-testid={`template-id-fr-${template.key}`}
                              />
                              {validationErrors[`${template.key}_fr`] && (
                                <p className="text-xs text-destructive">
                                  {validationErrors[`${template.key}_fr`]}
                                </p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* HTML Preview Panel */}
                        {previewKey === template.key && (
                          <div className="mt-2 border border-border rounded-lg overflow-hidden" data-testid={`preview-panel-${template.key}`}>
                            <div className="flex items-center justify-between bg-accent/40 px-4 py-2 border-b border-border">
                              <span className="text-xs font-semibold flex items-center gap-1.5">
                                <Eye className="h-3.5 w-3.5" /> Template Preview
                              </span>
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setShowCode(!showCode)}
                                  className="h-7 text-xs gap-1"
                                  data-testid={`toggle-code-${template.key}`}
                                >
                                  <Code className="h-3 w-3" />
                                  {showCode ? 'Visual' : 'HTML Code'}
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => { setPreviewKey(null); setPreviewHtml(''); }}
                                  className="h-7 w-7 p-0"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            </div>
                            {previewLoading ? (
                              <div className="flex items-center justify-center h-48">
                                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
                              </div>
                            ) : previewHtml ? (
                              showCode ? (
                                <ScrollArea className="h-[400px]">
                                  <pre className="p-4 text-xs font-mono whitespace-pre-wrap break-all bg-muted/30">{previewHtml}</pre>
                                </ScrollArea>
                              ) : (
                                <div className="bg-white">
                                  <iframe
                                    srcDoc={previewHtml}
                                    title={`Preview: ${template.key}`}
                                    className="w-full border-0"
                                    style={{ height: '600px' }}
                                    sandbox="allow-same-origin"
                                    data-testid={`preview-iframe-${template.key}`}
                                  />
                                </div>
                              )
                            ) : (
                              <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
                                No HTML preview available for this template
                              </div>
                            )}
                          </div>
                        )}
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
