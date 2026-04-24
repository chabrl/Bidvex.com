import API_BASE from '../../config';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import { Switch } from '../../components/ui/switch';
import { Checkbox } from '../../components/ui/checkbox';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter 
} from '../../components/ui/dialog';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { useTranslation } from 'react-i18next';
import { 
  Mail, Send, Users, Calendar, BarChart3, Plus, Edit3, 
  Trash2, Eye, Play, Pause, Clock, CheckCircle, XCircle,
  AlertTriangle, RefreshCw, Filter, Search, MousePointer,
  TrendingUp, ArrowLeft, Copy, FileText, Settings, Upload,
  UserPlus, UserMinus, Download, ListFilter, Target,
  MailOpen, MousePointerClick, AlertCircle, Loader2
} from 'lucide-react';

const API = API_BASE;

// Status colors
const STATUS_COLORS = {
  draft: 'bg-gray-500',
  scheduled: 'bg-blue-500',
  sending: 'bg-amber-500',
  sent: 'bg-green-500',
  paused: 'bg-purple-500',
  cancelled: 'bg-red-500',
  failed: 'bg-red-600'
};

// Subscription tier options
const SUBSCRIPTION_TIERS = [
  { value: 'free', label: 'Free' },
  { value: 'premium', label: 'Premium' },
  { value: 'vip', label: 'VIP' }
];

// Account type options
const ACCOUNT_TYPES = [
  { value: 'personal', label: 'Personal' },
  { value: 'business', label: 'Business' }
];

// Activity status options
const ACTIVITY_STATUS = [
  { value: 'active', label: 'Active (last 30 days)' },
  { value: 'inactive', label: 'Inactive (30+ days)' },
  { value: 'new', label: 'New (last 7 days)' }
];

// Region options (Canadian provinces)
const REGIONS = [
  { value: 'ON', label: 'Ontario' },
  { value: 'QC', label: 'Quebec' },
  { value: 'BC', label: 'British Columbia' },
  { value: 'AB', label: 'Alberta' },
  { value: 'SK', label: 'Saskatchewan' },
  { value: 'MB', label: 'Manitoba' },
  { value: 'NS', label: 'Nova Scotia' },
  { value: 'NB', label: 'New Brunswick' },
  { value: 'NL', label: 'Newfoundland' },
  { value: 'PE', label: 'Prince Edward Island' },
  { value: 'NT', label: 'Northwest Territories' },
  { value: 'YT', label: 'Yukon' },
  { value: 'NU', label: 'Nunavut' }
];

const EmailMarketingManager = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [config, setConfig] = useState(null);
  
  // Selected campaign for viewing
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [campaignStats, setCampaignStats] = useState(null);
  const [loadingStats, setLoadingStats] = useState(false);
  
  // Campaign builder state
  const [builderOpen, setBuilderOpen] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState(null);
  const [campaignData, setCampaignData] = useState({
    name: '',
    subject: '',
    html_content: '',
    plain_text_content: '',
    audience_filters: {
      subscription_tiers: [],
      account_types: [],
      regions: [],
      activity_status: '',
      exclude_unsubscribed: true
    },
    manual_emails: [],
    exclude_emails: [],
    scheduled_at: '',
    from_name: '',
    reply_to: ''
  });
  const [audiencePreview, setAudiencePreview] = useState({ 
    count: 0, 
    preview: [],
    breakdown: null,
    excluded_count: 0,
    suppressed_count: 0
  });
  const [loadingAudience, setLoadingAudience] = useState(false);
  const [saving, setSaving] = useState(false);
  
  // Advanced targeting state
  const [manualEmailsText, setManualEmailsText] = useState('');
  const [excludeEmailsText, setExcludeEmailsText] = useState('');
  const [csvParseResult, setCsvParseResult] = useState(null);
  const [uploadingCsv, setUploadingCsv] = useState(false);
  const csvInputRef = useRef(null);
  
  // Test email state
  const [testEmailDialogOpen, setTestEmailDialogOpen] = useState(false);
  const [testEmail, setTestEmail] = useState('');
  const [sendingTest, setSendingTest] = useState(false);
  
  // Schedule dialog
  const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleTime, setScheduleTime] = useState('');
  const [scheduling, setScheduling] = useState(false);
  
  // Cancel dialog
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelling, setCancelling] = useState(false);

  const [dashboardStats, setDashboardStats] = useState(null);
  const [syncingContacts, setSyncingContacts] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [insightsModal, setInsightsModal] = useState({ open: false, campaign: null, stats: null, loading: false });

  useEffect(() => {
    fetchCampaigns();
    fetchConfig();
    fetchDashboardStats();
  }, [statusFilter]);

  const fetchDashboardStats = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/admin/marketing/dashboard-stats`, { headers });
      setDashboardStats(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
    }
  };

  const handleSyncContacts = async () => {
    setSyncingContacts(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.post(`${API}/admin/marketing/sync-contacts`, {}, { headers });
      toast.success(`Synced ${response.data.synced} contacts from ${response.data.total_users} users`);
    } catch (error) {
      toast.error('Failed to sync contacts');
    } finally {
      setSyncingContacts(false);
    }
  };

  const fetchCampaigns = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const params = statusFilter !== 'all' ? `?status=${statusFilter}` : '';
      const response = await axios.get(`${API}/admin/marketing/campaigns${params}`, { headers });
      setCampaigns(response.data.campaigns || []);
    } catch (error) {
      console.error('Failed to fetch campaigns:', error);
      toast.error('Failed to load campaigns');
    } finally {
      setLoading(false);
    }
  };

  const fetchConfig = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/admin/marketing/config`, { headers });
      setConfig(response.data);
    } catch (error) {
      console.error('Failed to fetch config:', error);
    }
  };

  const fetchAdvancedAudiencePreview = useCallback(async () => {
    setLoadingAudience(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.post(`${API}/admin/marketing/audience/advanced-preview`, {
        audience_filters: campaignData.audience_filters,
        manual_emails: campaignData.manual_emails,
        exclude_emails: campaignData.exclude_emails
      }, { headers });
      setAudiencePreview(response.data);
    } catch (error) {
      console.error('Failed to fetch advanced audience:', error);
      toast.error('Failed to preview audience');
    } finally {
      setLoadingAudience(false);
    }
  }, [token, campaignData.audience_filters, campaignData.manual_emails, campaignData.exclude_emails]);

  const fetchAudiencePreview = useCallback(async (filters) => {
    setLoadingAudience(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.post(`${API}/admin/marketing/audience/preview`, filters, { headers });
      setAudiencePreview(response.data);
    } catch (error) {
      console.error('Failed to fetch audience:', error);
    } finally {
      setLoadingAudience(false);
    }
  }, [token]);

  const fetchCampaignStats = async (campaignId) => {
    setLoadingStats(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/admin/marketing/campaigns/${campaignId}/stats`, { headers });
      setCampaignStats(response.data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      toast.error('Failed to load campaign stats');
    } finally {
      setLoadingStats(false);
    }
  };

  const parseManualEmails = async (text) => {
    if (!text.trim()) {
      setCampaignData(prev => ({ ...prev, manual_emails: [] }));
      return;
    }
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.post(`${API}/admin/marketing/parse-emails`, { emails: text }, { headers });
      setCampaignData(prev => ({ ...prev, manual_emails: response.data.valid }));
      if (response.data.invalid?.length > 0) {
        toast.warning(`${response.data.invalid.length} invalid email(s) skipped`);
      }
    } catch (error) {
      console.error('Failed to parse emails:', error);
    }
  };

  const parseExcludeEmails = async (text) => {
    if (!text.trim()) {
      setCampaignData(prev => ({ ...prev, exclude_emails: [] }));
      return;
    }
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.post(`${API}/admin/marketing/parse-emails`, { emails: text }, { headers });
      setCampaignData(prev => ({ ...prev, exclude_emails: response.data.valid }));
      if (response.data.invalid?.length > 0) {
        toast.warning(`${response.data.invalid.length} invalid email(s) skipped`);
      }
    } catch (error) {
      console.error('Failed to parse exclude emails:', error);
    }
  };

  const handleCsvUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    if (!file.name.endsWith('.csv')) {
      toast.error('Please upload a CSV file');
      return;
    }
    
    setUploadingCsv(true);
    try {
      const headers = { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      };
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API}/admin/marketing/parse-csv`, formData, { headers });
      setCsvParseResult(response.data);
      
      // Add valid emails to manual emails
      if (response.data.valid?.length > 0) {
        setCampaignData(prev => ({
          ...prev,
          manual_emails: [...new Set([...prev.manual_emails, ...response.data.valid])]
        }));
        setManualEmailsText(prev => {
          const existingEmails = prev ? prev.split('\n').filter(e => e.trim()) : [];
          const allEmails = [...new Set([...existingEmails, ...response.data.valid])];
          return allEmails.join('\n');
        });
        toast.success(`Added ${response.data.valid.length} valid emails from CSV`);
      }
      
      if (response.data.invalid?.length > 0 || response.data.duplicates?.length > 0) {
        toast.warning(`${response.data.invalid?.length || 0} invalid, ${response.data.duplicates?.length || 0} duplicates skipped`);
      }
    } catch (error) {
      console.error('Failed to parse CSV:', error);
      toast.error('Failed to parse CSV file');
    } finally {
      setUploadingCsv(false);
      if (csvInputRef.current) {
        csvInputRef.current.value = '';
      }
    }
  };

  const openBuilder = (campaign = null) => {
    if (campaign) {
      setEditingCampaign(campaign);
      setCampaignData({
        name: campaign.name,
        subject: campaign.subject,
        html_content: campaign.html_content,
        plain_text_content: campaign.plain_text_content || '',
        audience_filters: campaign.audience_filters || {
          subscription_tiers: [],
          account_types: [],
          regions: [],
          activity_status: '',
          exclude_unsubscribed: true
        },
        manual_emails: campaign.manual_emails || [],
        exclude_emails: campaign.exclude_emails || [],
        scheduled_at: campaign.scheduled_at || '',
        from_name: campaign.from_name || '',
        reply_to: campaign.reply_to || ''
      });
      setManualEmailsText((campaign.manual_emails || []).join('\n'));
      setExcludeEmailsText((campaign.exclude_emails || []).join('\n'));
      setAudiencePreview({ 
        count: campaign.audience_count || 0, 
        preview: [],
        breakdown: campaign.audience_breakdown || null
      });
    } else {
      setEditingCampaign(null);
      setCampaignData({
        name: '',
        subject: '',
        html_content: getDefaultEmailTemplate(),
        plain_text_content: '',
        audience_filters: {
          subscription_tiers: [],
          account_types: [],
          regions: [],
          activity_status: '',
          exclude_unsubscribed: true
        },
        manual_emails: [],
        exclude_emails: [],
        scheduled_at: '',
        from_name: '',
        reply_to: ''
      });
      setManualEmailsText('');
      setExcludeEmailsText('');
      setAudiencePreview({ count: 0, preview: [], breakdown: null });
    }
    setCsvParseResult(null);
    setBuilderOpen(true);
  };

  const getDefaultEmailTemplate = () => {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #3B82F6, #8B5CF6); padding: 30px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">BidVex</h1>
    </div>
    
    <!-- Content -->
    <div style="padding: 30px;">
      <p style="color: #333; font-size: 16px; line-height: 1.6;">
        Hello {{name}},
      </p>
      
      <p style="color: #333; font-size: 16px; line-height: 1.6;">
        Your email content goes here. Use personalization variables like {{name}} and {{email}}.
      </p>
      
      <div style="text-align: center; margin: 30px 0;">
        <a href="https://www.bidvex.com" style="display: inline-block; background: #3B82F6; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">
          Visit BidVex
        </a>
      </div>
    </div>
    
    <!-- Footer -->
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
      <p style="color: #666; font-size: 12px; margin: 0;">
        © 2026 BidVex Inc. All rights reserved.
      </p>
      <p style="margin: 10px 0 0; font-size: 12px;">
        <a href="{{unsubscribe_url}}" style="color: #999;">{t("common.unsubscribe")}</a>
      </p>
    </div>
  </div>
</body>
</html>`;
  };

  const handleFilterChange = (filterType, value, checked) => {
    setCampaignData(prev => {
      const newFilters = { ...prev.audience_filters };
      
      if (filterType === 'activity_status' || filterType === 'exclude_unsubscribed') {
        newFilters[filterType] = value;
      } else {
        const currentValues = newFilters[filterType] || [];
        if (checked) {
          newFilters[filterType] = [...currentValues, value];
        } else {
          newFilters[filterType] = currentValues.filter(v => v !== value);
        }
      }
      
      return { ...prev, audience_filters: newFilters };
    });
  };

  const saveCampaign = async (sendNow = false) => {
    if (!campaignData.name.trim()) {
      toast.error('Campaign name is required');
      return;
    }
    if (!campaignData.subject.trim()) {
      toast.error('Email subject is required');
      return;
    }
    if (!campaignData.html_content.trim()) {
      toast.error('Email content is required');
      return;
    }

    setSaving(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      
      let campaign;
      if (editingCampaign) {
        const response = await axios.put(
          `${API}/admin/marketing/campaigns/${editingCampaign.id}`,
          campaignData,
          { headers }
        );
        campaign = response.data;
        toast.success('Campaign updated');
      } else {
        const response = await axios.post(
          `${API}/admin/marketing/campaigns`,
          campaignData,
          { headers }
        );
        campaign = response.data;
        toast.success('Campaign created');
      }
      
      if (sendNow && campaign.id) {
        await axios.post(`${API}/admin/marketing/campaigns/${campaign.id}/send`, {}, { headers });
        toast.success('Campaign sending started');
      }
      
      setBuilderOpen(false);
      fetchCampaigns();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to save campaign';
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const sendTestEmail = async () => {
    if (!testEmail.trim()) {
      toast.error('Please enter a test email address');
      return;
    }

    setSendingTest(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const campaignId = editingCampaign?.id || selectedCampaign?.id;
      
      if (!campaignId) {
        // Save campaign first if new
        const response = await axios.post(
          `${API}/admin/marketing/campaigns`,
          campaignData,
          { headers }
        );
        const newCampaignId = response.data.id;
        
        await axios.post(
          `${API}/admin/marketing/campaigns/${newCampaignId}/test`,
          { email: testEmail },
          { headers }
        );
      } else {
        await axios.post(
          `${API}/admin/marketing/campaigns/${campaignId}/test`,
          { email: testEmail },
          { headers }
        );
      }
      
      toast.success(`Test email sent to ${testEmail}`);
      setTestEmailDialogOpen(false);
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to send test email';
      toast.error(message);
    } finally {
      setSendingTest(false);
    }
  };

  const scheduleCampaign = async () => {
    if (!scheduleDate || !scheduleTime) {
      toast.error('Please select date and time');
      return;
    }

    setScheduling(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const scheduledAt = new Date(`${scheduleDate}T${scheduleTime}`).toISOString();
      
      await axios.post(
        `${API}/admin/marketing/campaigns/${selectedCampaign.id}/schedule`,
        { scheduled_at: scheduledAt },
        { headers }
      );
      
      toast.success('Campaign scheduled');
      setScheduleDialogOpen(false);
      fetchCampaigns();
      setSelectedCampaign(null);
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to schedule campaign';
      toast.error(message);
    } finally {
      setScheduling(false);
    }
  };

  const cancelCampaign = async () => {
    if (!cancelReason.trim()) {
      toast.error('Please provide a cancellation reason');
      return;
    }

    setCancelling(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      
      await axios.post(
        `${API}/admin/marketing/campaigns/${selectedCampaign.id}/cancel`,
        { reason: cancelReason },
        { headers }
      );
      
      toast.success('Campaign cancelled');
      setCancelDialogOpen(false);
      setCancelReason('');
      fetchCampaigns();
      setSelectedCampaign(null);
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to cancel campaign';
      toast.error(message);
    } finally {
      setCancelling(false);
    }
  };

  const sendCampaignNow = async (campaignId) => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(`${API}/admin/marketing/campaigns/${campaignId}/send`, {}, { headers });
      toast.success('Campaign sending started');
      fetchCampaigns();
      setSelectedCampaign(null);
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to send campaign';
      toast.error(message);
    }
  };

  const selectCampaign = async (campaign) => {
    setSelectedCampaign(campaign);
    if (campaign.status === 'sent') {
      await fetchCampaignStats(campaign.id);
    }
  };

  // Campaign management actions
  const [deletingId, setDeletingId] = useState(null);
  const [cloningId, setCloningId] = useState(null);
  const [resendingId, setResendingId] = useState(null);

  const deleteCampaign = (campaignId, name) => {
    setConfirm({
      title: 'Delete this campaign permanently?',
      description: `"${name || campaignId}" will be removed from the database. Historical email_events already sent to SendGrid will remain in their records.\n\nCette action est irréversible.`,
      variant: 'destructive',
      confirmText: 'Delete Campaign',
      successMessage: 'Campaign deleted',
      onConfirm: async () => {
        const headers = { Authorization: `Bearer ${token}` };
        await axios.delete(`${API}/admin/marketing/campaigns/${campaignId}`, { headers });
        if (selectedCampaign?.id === campaignId) setSelectedCampaign(null);
        fetchCampaigns();
      },
    });
  };

  const showInsights = async (campaign) => {
    setInsightsModal({ open: true, campaign, stats: null, loading: true });
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.get(`${API}/admin/marketing/campaigns/${campaign.id}/stats`, { headers });
      setInsightsModal((m) => ({ ...m, stats: res.data, loading: false }));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load campaign insights');
      setInsightsModal((m) => ({ ...m, loading: false }));
    }
  };

  const cloneCampaign = async (campaignId, e) => {
    e?.stopPropagation();
    setCloningId(campaignId);
    try {
      const res = await axios.post(`${API}/admin/marketing/campaigns/${campaignId}/clone`, {}, { headers });
      toast.success(`Cloned as "${res.data.name}"`);
      fetchCampaigns();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to clone');
    } finally { setCloningId(null); }
  };

  const resendCampaign = async (campaignId, e) => {
    e?.stopPropagation();
    if (!window.confirm('Resend this campaign to all original recipients?')) return;
    setResendingId(campaignId);
    try {
      const res = await axios.post(`${API}/admin/marketing/campaigns/${campaignId}/resend`, {}, { headers });
      toast.success(`Resent: ${res.data.sent || 0} delivered`);
      fetchCampaigns();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to resend');
    } finally { setResendingId(null); }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString('en-CA', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  // Filter campaigns
  const filteredCampaigns = campaigns.filter(c => 
    c.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.subject?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Campaign Detail View
  const CampaignDetailView = () => {
    if (!selectedCampaign) return null;

    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => setSelectedCampaign(null)} className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to Campaigns
        </Button>

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="text-xl">{selectedCampaign.name}</CardTitle>
                <CardDescription>Subject: {selectedCampaign.subject}</CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={`${STATUS_COLORS[selectedCampaign.status]} text-white`}>
                  {selectedCampaign.status}
                </Badge>
                {selectedCampaign.status === 'failed' && selectedCampaign.error_message && (
                  <span title={selectedCampaign.error_message} className="cursor-help text-red-500 text-xs flex items-center gap-1">
                    <AlertTriangle className="h-3.5 w-3.5" /> hover for error
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-2 mt-2">
              <Button size="sm" variant="outline" onClick={(e) => cloneCampaign(selectedCampaign.id, e)} disabled={cloningId === selectedCampaign.id} data-testid="detail-clone-btn">
                {cloningId === selectedCampaign.id ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : <Copy className="h-4 w-4 mr-1" />} Clone
              </Button>
              {(selectedCampaign.status === 'sent' || selectedCampaign.status === 'completed' || selectedCampaign.status === 'failed') && (
                <Button size="sm" variant="outline" onClick={(e) => resendCampaign(selectedCampaign.id, e)} disabled={resendingId === selectedCampaign.id} data-testid="detail-resend-btn">
                  {resendingId === selectedCampaign.id ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : <RefreshCw className="h-4 w-4 mr-1 text-blue-600" />} Resend
                </Button>
              )}
              <Button size="sm" variant="outline" className="text-red-500 hover:bg-red-50" onClick={(e) => deleteCampaign(selectedCampaign.id, e)} disabled={deletingId === selectedCampaign.id} data-testid="detail-delete-btn">
                {deletingId === selectedCampaign.id ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : <Trash2 className="h-4 w-4 mr-1" />} Delete
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Campaign Info */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                <p className="text-xs text-muted-foreground">Audience</p>
                <p className="font-bold text-lg">{selectedCampaign.audience_count || 0}</p>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                <p className="text-xs text-muted-foreground">Created</p>
                <p className="text-sm font-medium">{formatDate(selectedCampaign.created_at)}</p>
              </div>
              {selectedCampaign.scheduled_at && (
                <div className="p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">Scheduled For</p>
                  <p className="text-sm font-medium">{formatDate(selectedCampaign.scheduled_at)}</p>
                </div>
              )}
              {selectedCampaign.sent_at && (
                <div className="p-3 bg-green-50 dark:bg-green-950/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">Sent At</p>
                  <p className="text-sm font-medium">{formatDate(selectedCampaign.sent_at)}</p>
                </div>
              )}
            </div>

            {/* Stats for sent campaigns */}
            {selectedCampaign.status === 'sent' && campaignStats && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg text-center">
                  <p className="text-2xl font-bold">{campaignStats.stats?.sent || 0}</p>
                  <p className="text-xs text-muted-foreground">Sent</p>
                </div>
                <div className="p-3 bg-green-50 dark:bg-green-950/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-green-600">{campaignStats.stats?.open_rate || 0}%</p>
                  <p className="text-xs text-muted-foreground">Open Rate</p>
                </div>
                <div className="p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-blue-600">{campaignStats.stats?.click_rate || 0}%</p>
                  <p className="text-xs text-muted-foreground">Click Rate</p>
                </div>
                <div className="p-3 bg-red-50 dark:bg-red-950/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-red-600">{campaignStats.stats?.bounced || 0}</p>
                  <p className="text-xs text-muted-foreground">Bounced</p>
                </div>
                <div className="p-3 bg-amber-50 dark:bg-amber-950/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-amber-600">{campaignStats.stats?.unsubscribed || 0}</p>
                  <p className="text-xs text-muted-foreground">Unsubscribed</p>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-wrap gap-2 pt-4 border-t">
              {selectedCampaign.status === 'draft' && (
                <>
                  <Button onClick={() => openBuilder(selectedCampaign)} className="gap-2">
                    <Edit3 className="h-4 w-4" /> Edit
                  </Button>
                  <Button variant="outline" onClick={() => setScheduleDialogOpen(true)} className="gap-2">
                    <Calendar className="h-4 w-4" /> Schedule
                  </Button>
                  <Button 
                    variant="default" 
                    onClick={() => sendCampaignNow(selectedCampaign.id)}
                    className="gap-2 bg-green-600 hover:bg-green-700"
                  >
                    <Send className="h-4 w-4" /> Send Now
                  </Button>
                </>
              )}
              {selectedCampaign.status === 'scheduled' && (
                <>
                  <Button onClick={() => openBuilder(selectedCampaign)} className="gap-2">
                    <Edit3 className="h-4 w-4" /> Edit
                  </Button>
                  <Button 
                    variant="destructive" 
                    onClick={() => setCancelDialogOpen(true)}
                    className="gap-2"
                  >
                    <XCircle className="h-4 w-4" /> Cancel
                  </Button>
                </>
              )}
              <Button 
                variant="outline" 
                onClick={() => {
                  setTestEmail('');
                  setTestEmailDialogOpen(true);
                }}
                className="gap-2"
              >
                <Mail className="h-4 w-4" /> Send Test
              </Button>
            </div>

            {/* Email Preview */}
            <div className="mt-4">
              <Label className="text-sm font-medium">Email Preview</Label>
              <div className="mt-2 border rounded-lg overflow-hidden">
                <iframe
                  srcDoc={selectedCampaign.html_content}
                  className="w-full h-96 bg-white"
                  title="Email Preview"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading campaigns...</p>
        </CardContent>
      </Card>
    );
  }

  // Show campaign detail if selected
  if (selectedCampaign) {
    return (
      <>
        <CampaignDetailView />
        
        {/* Test Email Dialog */}
        <Dialog open={testEmailDialogOpen} onOpenChange={setTestEmailDialogOpen}>
          <DialogContent className="w-[95vw] max-w-[400px]">
            <DialogHeader>
              <DialogTitle>{t("admin.sendTestEmail")}</DialogTitle>
              <DialogDescription>{t("admin.previewCampaign")}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>{t("admin.emailAddress")}</Label>
                <Input
                  type="email"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="your@email.com"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setTestEmailDialogOpen(false)}>Cancel</Button>
              <Button onClick={sendTestEmail} disabled={sendingTest} className="gap-2">
                {sendingTest ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Send Test
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Schedule Dialog */}
        <Dialog open={scheduleDialogOpen} onOpenChange={setScheduleDialogOpen}>
          <DialogContent className="w-[95vw] max-w-[400px]">
            <DialogHeader>
              <DialogTitle>{t("admin.scheduleCampaign")}</DialogTitle>
              <DialogDescription>{t("admin.chooseWhenToSend")}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Date</Label>
                <Input
                  type="date"
                  value={scheduleDate}
                  onChange={(e) => setScheduleDate(e.target.value)}
                  min={new Date().toISOString().split('T')[0]}
                />
              </div>
              <div className="space-y-2">
                <Label>Time</Label>
                <Input
                  type="time"
                  value={scheduleTime}
                  onChange={(e) => setScheduleTime(e.target.value)}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setScheduleDialogOpen(false)}>Cancel</Button>
              <Button onClick={scheduleCampaign} disabled={scheduling} className="gap-2">
                {scheduling ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Calendar className="h-4 w-4" />}
                Schedule
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Cancel Dialog */}
        <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
          <DialogContent className="w-[95vw] max-w-[400px]">
            <DialogHeader>
              <DialogTitle className="text-red-600">Cancel Campaign</DialogTitle>
              <DialogDescription>{t("admin.cancelScheduledCampaign")}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Reason *</Label>
                <Textarea
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  placeholder="Why is this campaign being cancelled?"
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>{t("admin.keepScheduled")}</Button>
              <Button variant="destructive" onClick={cancelCampaign} disabled={cancelling} className="gap-2">
                {cancelling ? <RefreshCw className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                Cancel Campaign
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  return (
    <div className="space-y-6">
      {/* Configuration Warning */}
      {config && !config.marketing_configured && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200 dark:border-amber-800">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
          <div>
            <p className="font-medium text-amber-700 dark:text-amber-300">SendGrid Not Configured</p>
            <p className="text-sm text-amber-600 dark:text-amber-400">
              Email sending is disabled. Add your SendGrid API key to enable campaign sending.
            </p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Marketing
          </h2>
          <p className="text-sm text-muted-foreground">Create, schedule, and track email campaigns</p>
        </div>
        <Button onClick={() => openBuilder()} className="gap-2" data-testid="create-campaign-btn">
          <Plus className="h-4 w-4" />
          New Campaign
        </Button>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4" data-testid="marketing-dashboard-stats">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
                <FileText className="h-5 w-5 text-slate-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{dashboardStats?.total_campaigns || campaigns.length}</p>
                <p className="text-xs text-muted-foreground">Total Campaigns</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                <Send className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{dashboardStats?.total_sent || 0}</p>
                <p className="text-xs text-muted-foreground">Emails Sent</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
                <MailOpen className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">{dashboardStats?.open_rate || 0}%</p>
                <p className="text-xs text-muted-foreground">Open Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-cyan-100 dark:bg-cyan-900 rounded-full flex items-center justify-center">
                <MousePointerClick className="h-5 w-5 text-cyan-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-cyan-600">{dashboardStats?.click_rate || 0}%</p>
                <p className="text-xs text-muted-foreground">Click Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center">
                <AlertCircle className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">{dashboardStats?.total_bounced || 0}</p>
                <p className="text-xs text-muted-foreground">Bounced</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="cursor-pointer hover:border-primary/40 transition-colors" onClick={handleSyncContacts}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center">
                {syncingContacts ? <Loader2 className="h-5 w-5 text-purple-600 animate-spin" /> : <Users className="h-5 w-5 text-purple-600" />}
              </div>
              <div>
                <p className="text-sm font-semibold text-purple-600">{syncingContacts ? 'Syncing...' : 'Sync Contacts'}</p>
                <p className="text-xs text-muted-foreground">Auto-import users</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Campaigns</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search campaigns..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("admin.allStatus")}</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="scheduled">{t("admin.scheduled")}</SelectItem>
                <SelectItem value="sent">Sent</SelectItem>
                <SelectItem value="cancelled">{t("admin.cancelled")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Campaign List */}
          <div className="space-y-2">
            {filteredCampaigns.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No campaigns found. Create your first campaign!
              </div>
            ) : (
              filteredCampaigns.map(campaign => (
                <div
                  key={campaign.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                  onClick={() => selectCampaign(campaign)}
                  data-testid={`campaign-${campaign.id}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{campaign.name}</p>
                      <Badge className={`${STATUS_COLORS[campaign.status]} text-white text-xs`}>
                        {campaign.status}
                      </Badge>
                      {campaign.status === 'failed' && campaign.error_message && (
                        <span title={campaign.error_message} className="cursor-help">
                          <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground truncate">{campaign.subject}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Users className="h-3 w-3" /> {campaign.audience_count || 0}
                      </span>
                      {campaign.sent_count > 0 && (
                        <span className="flex items-center gap-1">
                          <Send className="h-3 w-3" /> {campaign.sent_count} sent
                        </span>
                      )}
                      {campaign.scheduled_at && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {formatDate(campaign.scheduled_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                    <Button variant="ghost" size="sm" onClick={() => showInsights(campaign)} title="View insights" data-testid={`insights-campaign-${campaign.id}`} className="text-blue-600 hover:text-blue-800 hover:bg-blue-50">
                      <BarChart3 className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => selectCampaign(campaign)} title="View details" data-testid={`view-campaign-${campaign.id}`}>
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={(e) => cloneCampaign(campaign.id, e)} disabled={cloningId === campaign.id} title="Clone as draft" data-testid={`clone-campaign-${campaign.id}`}>
                      {cloningId === campaign.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}
                    </Button>
                    {(campaign.status === 'sent' || campaign.status === 'completed' || campaign.status === 'failed') && (
                      <Button variant="ghost" size="sm" onClick={(e) => resendCampaign(campaign.id, e)} disabled={resendingId === campaign.id} title="Resend campaign" data-testid={`resend-campaign-${campaign.id}`}>
                        {resendingId === campaign.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 text-blue-600" />}
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => deleteCampaign(campaign.id, campaign.name)} title="Delete campaign" className="text-red-500 hover:text-red-700 hover:bg-red-50" data-testid={`delete-campaign-${campaign.id}`}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Campaign Builder Dialog */}
      <Dialog open={builderOpen} onOpenChange={setBuilderOpen}>
        <DialogContent className="w-[95vw] max-w-[900px] max-h-[90vh] overflow-y-auto p-0 gap-0">
          <DialogHeader className="sticky top-0 bg-background z-10 p-4 sm:p-6 pb-4 border-b">
            <DialogTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5" />
              {editingCampaign ? 'Edit Campaign' : 'New Campaign'}
            </DialogTitle>
          </DialogHeader>

          <div className="p-4 sm:p-6 space-y-6">
            {/* Basic Info */}
            <div className="space-y-4">
              <h3 className="font-medium">Campaign Details</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Campaign Name *</Label>
                  <Input
                    value={campaignData.name}
                    onChange={(e) => setCampaignData(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Monthly Newsletter"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Email Subject *</Label>
                  <Input
                    value={campaignData.subject}
                    onChange={(e) => setCampaignData(prev => ({ ...prev, subject: e.target.value }))}
                    placeholder="Don't miss our latest deals!"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t("admin.fromName")}</Label>
                  <Input
                    value={campaignData.from_name}
                    onChange={(e) => setCampaignData(prev => ({ ...prev, from_name: e.target.value }))}
                    placeholder="BidVex Updates"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Reply-To</Label>
                  <Input
                    type="email"
                    value={campaignData.reply_to}
                    onChange={(e) => setCampaignData(prev => ({ ...prev, reply_to: e.target.value }))}
                    placeholder="support@bidvex.com"
                  />
                </div>
              </div>
            </div>

            {/* Audience Filters */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Audience Targeting</h3>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchAudiencePreview(campaignData.audience_filters)}
                  disabled={loadingAudience}
                  className="gap-2"
                >
                  {loadingAudience ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Users className="h-3 w-3" />}
                  Preview ({audiencePreview.count})
                </Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Subscription Tiers */}
                <div className="space-y-2">
                  <Label className="text-sm">Subscription Tiers</Label>
                  <div className="space-y-2 p-3 border rounded-lg">
                    {SUBSCRIPTION_TIERS.map(tier => (
                      <div key={tier.value} className="flex items-center gap-2">
                        <Checkbox
                          id={`tier-${tier.value}`}
                          checked={campaignData.audience_filters.subscription_tiers?.includes(tier.value)}
                          onCheckedChange={(checked) => handleFilterChange('subscription_tiers', tier.value, checked)}
                        />
                        <label htmlFor={`tier-${tier.value}`} className="text-sm cursor-pointer">
                          {tier.label}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Account Types */}
                <div className="space-y-2">
                  <Label className="text-sm">Account Types</Label>
                  <div className="space-y-2 p-3 border rounded-lg">
                    {ACCOUNT_TYPES.map(type => (
                      <div key={type.value} className="flex items-center gap-2">
                        <Checkbox
                          id={`type-${type.value}`}
                          checked={campaignData.audience_filters.account_types?.includes(type.value)}
                          onCheckedChange={(checked) => handleFilterChange('account_types', type.value, checked)}
                        />
                        <label htmlFor={`type-${type.value}`} className="text-sm cursor-pointer">
                          {type.label}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Activity Status */}
                <div className="space-y-2">
                  <Label className="text-sm">Activity Status</Label>
                  <Select
                    value={campaignData.audience_filters.activity_status || 'all'}
                    onValueChange={(v) => handleFilterChange('activity_status', v === 'all' ? '' : v, true)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Any" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t("admin.anyActivity")}</SelectItem>
                      {ACTIVITY_STATUS.map(s => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* User Role Segment */}
                <div className="space-y-2">
                  <Label className="text-sm">User Role</Label>
                  <Select
                    value={campaignData.audience_filters.user_role || 'all'}
                    onValueChange={(v) => handleFilterChange('user_role', v === 'all' ? '' : v, true)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Any" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Users</SelectItem>
                      <SelectItem value="buyers">Buyers (placed bids)</SelectItem>
                      <SelectItem value="sellers">Sellers (created listings)</SelectItem>
                      <SelectItem value="partners">Partners</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Regions */}
              <div className="space-y-2">
                <Label className="text-sm">Regions (Provinces)</Label>
                <div className="flex flex-wrap gap-2 p-3 border rounded-lg">
                  {REGIONS.map(region => (
                    <div key={region.value} className="flex items-center gap-1">
                      <Checkbox
                        id={`region-${region.value}`}
                        checked={campaignData.audience_filters.regions?.includes(region.value)}
                        onCheckedChange={(checked) => handleFilterChange('regions', region.value, checked)}
                      />
                      <label htmlFor={`region-${region.value}`} className="text-xs cursor-pointer">
                        {region.value}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Exclude unsubscribed */}
              <div className="flex items-center gap-2">
                <Checkbox
                  id="exclude-unsub"
                  checked={campaignData.audience_filters.exclude_unsubscribed}
                  onCheckedChange={(checked) => handleFilterChange('exclude_unsubscribed', checked, true)}
                />
                <label htmlFor="exclude-unsub" className="text-sm cursor-pointer">
                  Exclude unsubscribed users
                </label>
              </div>

              {/* Audience Preview */}
              {audiencePreview.preview?.length > 0 && (
                <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                  <p className="text-sm font-medium mb-2">Sample Recipients ({audiencePreview.count} total)</p>
                  <div className="space-y-1">
                    {audiencePreview.preview.map((user, idx) => (
                      <p key={idx} className="text-xs text-muted-foreground">
                        {user.name || 'No name'} - {user.email}
                        {user.source && user.source !== 'segmented' && (
                          <Badge variant="outline" className="ml-2 text-xs py-0">
                            {user.source === 'manual_external' ? 'external' : user.source}
                          </Badge>
                        )}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Advanced Targeting Section */}
            <div className="space-y-4 border-t pt-4">
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" />
                <h3 className="font-medium">Advanced Targeting</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Final Audience = (Segmented Users + Manual Emails) − Exclusions − Suppressed
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Manual Emails */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm flex items-center gap-2">
                      <UserPlus className="h-4 w-4 text-green-600" />
                      Add Emails Manually
                    </Label>
                    <Badge variant="outline" className="text-xs">
                      {campaignData.manual_emails?.length || 0} added
                    </Badge>
                  </div>
                  <Textarea
                    value={manualEmailsText}
                    onChange={(e) => setManualEmailsText(e.target.value)}
                    onBlur={() => parseManualEmails(manualEmailsText)}
                    placeholder="Enter emails separated by commas, semicolons, or new lines:&#10;email1@example.com&#10;email2@example.com, email3@example.com"
                    rows={4}
                    className="text-sm"
                  />
                  <div className="flex gap-2">
                    <input
                      type="file"
                      ref={csvInputRef}
                      accept=".csv"
                      onChange={handleCsvUpload}
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => csvInputRef.current?.click()}
                      disabled={uploadingCsv}
                      className="gap-2"
                    >
                      {uploadingCsv ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Upload className="h-3 w-3" />}
                      Upload CSV
                    </Button>
                    {csvParseResult && (
                      <span className="text-xs text-muted-foreground self-center">
                        {csvParseResult.valid?.length || 0} valid from CSV
                      </span>
                    )}
                  </div>
                </div>

                {/* Exclude Emails */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm flex items-center gap-2">
                      <UserMinus className="h-4 w-4 text-red-600" />
                      Exclude Emails
                    </Label>
                    <Badge variant="outline" className="text-xs">
                      {campaignData.exclude_emails?.length || 0} excluded
                    </Badge>
                  </div>
                  <Textarea
                    value={excludeEmailsText}
                    onChange={(e) => setExcludeEmailsText(e.target.value)}
                    onBlur={() => parseExcludeEmails(excludeEmailsText)}
                    placeholder="Enter emails to exclude:&#10;competitor@example.com&#10;optout@example.com"
                    rows={4}
                    className="text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    Exclusions override all other targeting rules
                  </p>
                </div>
              </div>

              {/* Final Audience Count */}
              <div className="flex items-center justify-between p-4 bg-primary/5 rounded-lg border border-primary/20">
                <div>
                  <p className="font-medium">Final Recipient Count</p>
                  <p className="text-xs text-muted-foreground">
                    Click preview to calculate with all targeting rules
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-2xl font-bold text-primary">{audiencePreview.count || 0}</p>
                    {audiencePreview.breakdown && (
                      <p className="text-xs text-muted-foreground">
                        {audiencePreview.breakdown.segmented_count || 0} segmented + 
                        {(audiencePreview.breakdown.manual_existing_count || 0) + (audiencePreview.breakdown.manual_external_count || 0)} manual
                      </p>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="default"
                    size="sm"
                    onClick={fetchAdvancedAudiencePreview}
                    disabled={loadingAudience}
                    className="gap-2"
                  >
                    {loadingAudience ? <RefreshCw className="h-4 w-4 animate-spin" /> : <ListFilter className="h-4 w-4" />}
                    Preview
                  </Button>
                </div>
              </div>

              {/* Breakdown Details */}
              {audiencePreview.breakdown && (
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center">
                  <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                    <p className="text-lg font-bold">{audiencePreview.breakdown.segmented_count || 0}</p>
                    <p className="text-xs text-muted-foreground">Segmented</p>
                  </div>
                  <div className="p-2 bg-green-50 dark:bg-green-950/30 rounded">
                    <p className="text-lg font-bold text-green-600">{audiencePreview.breakdown.manual_existing_count || 0}</p>
                    <p className="text-xs text-muted-foreground">Manual (Existing)</p>
                  </div>
                  <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded">
                    <p className="text-lg font-bold text-blue-600">{audiencePreview.breakdown.manual_external_count || 0}</p>
                    <p className="text-xs text-muted-foreground">Manual (External)</p>
                  </div>
                  <div className="p-2 bg-red-50 dark:bg-red-950/30 rounded">
                    <p className="text-lg font-bold text-red-600">{audiencePreview.excluded_count || 0}</p>
                    <p className="text-xs text-muted-foreground">Excluded</p>
                  </div>
                  <div className="p-2 bg-amber-50 dark:bg-amber-950/30 rounded">
                    <p className="text-lg font-bold text-amber-600">{audiencePreview.suppressed_count || 0}</p>
                    <p className="text-xs text-muted-foreground">Suppressed</p>
                  </div>
                </div>
              )}
            </div>

            {/* Email Content */}
            <div className="space-y-4">
              <h3 className="font-medium">Email Content</h3>
              <div className="space-y-2">
                <Label>HTML Content *</Label>
                <p className="text-xs text-muted-foreground">
                  Use {'{{name}}'}, {'{{email}}'}, {'{{unsubscribe_url}}'} for personalization
                </p>
                <Textarea
                  value={campaignData.html_content}
                  onChange={(e) => setCampaignData(prev => ({ ...prev, html_content: e.target.value }))}
                  placeholder="<html>..."
                  rows={12}
                  className="font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label>Plain Text (Fallback)</Label>
                <Textarea
                  value={campaignData.plain_text_content}
                  onChange={(e) => setCampaignData(prev => ({ ...prev, plain_text_content: e.target.value }))}
                  placeholder="Plain text version..."
                  rows={4}
                />
              </div>
            </div>
          </div>

          <DialogFooter className="sticky bottom-0 bg-background z-10 p-4 sm:p-6 pt-4 border-t flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setBuilderOpen(false)} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setTestEmail('');
                setTestEmailDialogOpen(true);
              }}
              className="w-full sm:w-auto gap-2"
            >
              <Mail className="h-4 w-4" /> Send Test
            </Button>
            <Button onClick={() => saveCampaign(false)} disabled={saving} className="w-full sm:w-auto gap-2">
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
              Save Draft
            </Button>
            <Button
              onClick={() => saveCampaign(true)}
              disabled={saving}
              className="w-full sm:w-auto gap-2 bg-green-600 hover:bg-green-700"
            >
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Save & Send Now
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Test Email Dialog (for builder) */}
      <Dialog open={testEmailDialogOpen} onOpenChange={setTestEmailDialogOpen}>
        <DialogContent className="w-[95vw] max-w-[400px]">
          <DialogHeader>
            <DialogTitle>{t("admin.sendTestEmail")}</DialogTitle>
            <DialogDescription>{t("admin.previewCampaign")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>{t("admin.emailAddress")}</Label>
              <Input
                type="email"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
                placeholder="your@email.com"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTestEmailDialogOpen(false)}>Cancel</Button>
            <Button onClick={sendTestEmail} disabled={sendingTest} className="gap-2">
              {sendingTest ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send Test
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Campaign Insights Modal */}
      <Dialog open={insightsModal.open} onOpenChange={(v) => !v && setInsightsModal({ open: false, campaign: null, stats: null, loading: false })}>
        <DialogContent className="max-w-2xl" data-testid="campaign-insights-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-600" />
              Campaign Insights — {insightsModal.campaign?.name || ''}
            </DialogTitle>
          </DialogHeader>
          {insightsModal.loading ? (
            <div className="py-8 text-center text-muted-foreground">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-3" />
              Loading insights…
            </div>
          ) : insightsModal.stats ? (
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {(() => {
                  const s = insightsModal.stats?.stats || insightsModal.stats || {};
                  const sent = s.sent || s.total_sent || insightsModal.campaign?.sent_count || 0;
                  const delivered = s.delivered || 0;
                  const opened = s.opened || s.unique_opens || 0;
                  const clicked = s.clicked || s.unique_clicks || 0;
                  const bounced = s.bounced || s.bounces || 0;
                  const unsubscribed = s.unsubscribed || s.unsubs || 0;
                  const openRate = sent > 0 ? ((opened / sent) * 100).toFixed(1) : '0.0';
                  const clickRate = sent > 0 ? ((clicked / sent) * 100).toFixed(1) : '0.0';
                  const deliveryRate = sent > 0 ? ((delivered / sent) * 100).toFixed(1) : '0.0';
                  const cards = [
                    { label: 'Total Sent / Envoyés', value: sent, color: 'text-slate-900' },
                    { label: 'Delivered', value: `${delivered} (${deliveryRate}%)`, color: 'text-green-600' },
                    { label: 'Opened', value: `${opened} (${openRate}%)`, color: 'text-blue-600' },
                    { label: 'Clicked', value: `${clicked} (${clickRate}%)`, color: 'text-purple-600' },
                    { label: 'Bounced', value: bounced, color: 'text-amber-600' },
                    { label: 'Unsubscribed', value: unsubscribed, color: 'text-red-600' },
                    { label: 'Status', value: insightsModal.campaign?.status || '—', color: 'text-slate-600' },
                    { label: 'Sent At', value: insightsModal.campaign?.sent_at ? new Date(insightsModal.campaign.sent_at).toLocaleString() : '—', color: 'text-slate-600' },
                  ];
                  return cards.map((c, i) => (
                    <div key={i} className="border rounded-md p-3 bg-background">
                      <p className="text-xs text-muted-foreground">{c.label}</p>
                      <p className={`text-lg font-semibold ${c.color}`} data-testid={`insight-${c.label.replace(/[^a-z0-9]/gi,'-').toLowerCase()}`}>{c.value}</p>
                    </div>
                  ));
                })()}
              </div>
              <p className="text-xs text-muted-foreground border-t pt-3">
                Stats are pulled from our local DB and combined with SendGrid event webhook data (/api/webhooks/sendgrid).<br />
                <span className="italic">Les statistiques proviennent de notre base de données et des événements SendGrid.</span>
              </p>
            </div>
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              Could not load stats. Please retry.
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setInsightsModal({ open: false, campaign: null, stats: null, loading: false })}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />
    </div>
  );
};

export default EmailMarketingManager;
