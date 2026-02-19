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
import { 
  Mail, Send, Users, Calendar, BarChart3, Plus, Edit3, 
  Trash2, Eye, Play, Pause, Clock, CheckCircle, XCircle,
  AlertTriangle, RefreshCw, Filter, Search, MousePointer,
  TrendingUp, ArrowLeft, Copy, FileText, Settings, Upload,
  UserPlus, UserMinus, Download, ListFilter, Target
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
    scheduled_at: '',
    from_name: '',
    reply_to: ''
  });
  const [audiencePreview, setAudiencePreview] = useState({ count: 0, preview: [] });
  const [loadingAudience, setLoadingAudience] = useState(false);
  const [saving, setSaving] = useState(false);
  
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

  useEffect(() => {
    fetchCampaigns();
    fetchConfig();
  }, [statusFilter]);

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
        scheduled_at: campaign.scheduled_at || '',
        from_name: campaign.from_name || '',
        reply_to: campaign.reply_to || ''
      });
      setAudiencePreview({ count: campaign.audience_count || 0, preview: [] });
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
        scheduled_at: '',
        from_name: '',
        reply_to: ''
      });
      setAudiencePreview({ count: 0, preview: [] });
    }
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
        <a href="{{unsubscribe_url}}" style="color: #999;">Unsubscribe</a>
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
              <Badge className={`${STATUS_COLORS[selectedCampaign.status]} text-white`}>
                {selectedCampaign.status}
              </Badge>
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
              <DialogTitle>Send Test Email</DialogTitle>
              <DialogDescription>Preview the campaign in your inbox</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Email Address</Label>
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
              <DialogTitle>Schedule Campaign</DialogTitle>
              <DialogDescription>Choose when to send this campaign</DialogDescription>
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
              <DialogDescription>This will cancel the scheduled campaign</DialogDescription>
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
              <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>Keep Scheduled</Button>
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
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
                <FileText className="h-5 w-5 text-slate-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{campaigns.length}</p>
                <p className="text-xs text-muted-foreground">Total Campaigns</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                <Clock className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{campaigns.filter(c => c.status === 'scheduled').length}</p>
                <p className="text-xs text-muted-foreground">Scheduled</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{campaigns.filter(c => c.status === 'sent').length}</p>
                <p className="text-xs text-muted-foreground">Sent</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
                <Edit3 className="h-5 w-5 text-gray-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{campaigns.filter(c => c.status === 'draft').length}</p>
                <p className="text-xs text-muted-foreground">Drafts</p>
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
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="scheduled">Scheduled</SelectItem>
                <SelectItem value="sent">Sent</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
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
                    </div>
                    <p className="text-sm text-muted-foreground truncate">{campaign.subject}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Users className="h-3 w-3" /> {campaign.audience_count || 0}
                      </span>
                      {campaign.scheduled_at && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {formatDate(campaign.scheduled_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm">
                    <Eye className="h-4 w-4" />
                  </Button>
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
                  <Label>From Name</Label>
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
                      <SelectItem value="all">Any Activity</SelectItem>
                      {ACTIVITY_STATUS.map(s => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
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
              {audiencePreview.preview.length > 0 && (
                <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                  <p className="text-sm font-medium mb-2">Sample Recipients ({audiencePreview.count} total)</p>
                  <div className="space-y-1">
                    {audiencePreview.preview.map((user, idx) => (
                      <p key={idx} className="text-xs text-muted-foreground">
                        {user.name || 'No name'} - {user.email}
                      </p>
                    ))}
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
            <DialogTitle>Send Test Email</DialogTitle>
            <DialogDescription>Preview the campaign in your inbox</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Email Address</Label>
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
    </div>
  );
};

export default EmailMarketingManager;
