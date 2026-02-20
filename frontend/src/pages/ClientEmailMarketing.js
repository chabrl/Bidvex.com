import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter 
} from '../components/ui/dialog';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { 
  Mail, Users, Send, Plus, Trash2, Upload, Search, RefreshCw,
  Lock, Crown, AlertTriangle, CheckCircle, Eye, BarChart3,
  UserPlus, FileText, ArrowRight, Zap, XCircle, Edit3, DollarSign
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ClientEmailMarketing = () => {
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const [activeTab, setActiveTab] = useState('contacts');
  const [loading, setLoading] = useState(true);
  const [access, setAccess] = useState(null);
  
  // Contacts state
  const [contacts, setContacts] = useState([]);
  const [contactStats, setContactStats] = useState(null);
  const [contactSearch, setContactSearch] = useState('');
  const [selectedContacts, setSelectedContacts] = useState([]);
  const [addContactDialogOpen, setAddContactDialogOpen] = useState(false);
  const [bulkAddDialogOpen, setBulkAddDialogOpen] = useState(false);
  const [newContactEmail, setNewContactEmail] = useState('');
  const [newContactName, setNewContactName] = useState('');
  const [bulkEmails, setBulkEmails] = useState('');
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [addingContact, setAddingContact] = useState(false);
  const csvInputRef = useRef(null);
  
  // Campaigns state
  const [campaigns, setCampaigns] = useState([]);
  const [campaignBuilderOpen, setCampaignBuilderOpen] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState(null);
  const [campaignData, setCampaignData] = useState({
    name: '',
    subject: '',
    html_content: '',
    contact_ids: []
  });
  const [sendConsentConfirmed, setSendConsentConfirmed] = useState(false);
  const [savingCampaign, setSavingCampaign] = useState(false);
  const [sendingCampaign, setSendingCampaign] = useState(false);
  
  // Selected campaign for viewing
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [campaignStats, setCampaignStats] = useState(null);
  
  // Templates state
  const [templates, setTemplates] = useState({});
  const [templateSelectorOpen, setTemplateSelectorOpen] = useState(false);

  useEffect(() => {
    checkAccess();
    fetchTemplates();
  }, []);

  useEffect(() => {
    // All users can view contacts - removed can_access check
    if (activeTab === 'contacts') {
      fetchContacts();
      fetchContactStats();
    } else if (activeTab === 'campaigns') {
      fetchCampaigns();
    }
  }, [activeTab]);

  const checkAccess = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/user/marketing/access`, { headers });
      setAccess(response.data);
    } catch (error) {
      console.error('Failed to check access:', error);
      toast.error('Failed to load marketing access');
    } finally {
      setLoading(false);
    }
  };

  const fetchTemplates = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/user/marketing/templates`, { headers });
      setTemplates(response.data.templates || {});
    } catch (error) {
      console.error('Failed to fetch templates:', error);
    }
  };

  const fetchContacts = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const params = contactSearch ? `?search=${encodeURIComponent(contactSearch)}` : '';
      const response = await axios.get(`${API}/user/marketing/contacts${params}`, { headers });
      setContacts(response.data.contacts || []);
    } catch (error) {
      if (error.response?.status !== 403) {
        console.error('Failed to fetch contacts:', error);
      }
    }
  };

  const fetchContactStats = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/user/marketing/contacts/stats`, { headers });
      setContactStats(response.data);
    } catch (error) {
      if (error.response?.status !== 403) {
        console.error('Failed to fetch contact stats:', error);
      }
    }
  };

  const fetchCampaigns = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/user/marketing/campaigns`, { headers });
      setCampaigns(response.data.campaigns || []);
    } catch (error) {
      if (error.response?.status !== 403) {
        console.error('Failed to fetch campaigns:', error);
      }
    }
  };

  const fetchCampaignStats = async (campaignId) => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/user/marketing/campaigns/${campaignId}/stats`, { headers });
      setCampaignStats(response.data);
    } catch (error) {
      console.error('Failed to fetch campaign stats:', error);
    }
  };

  const selectTemplate = (templateKey) => {
    const template = templates[templateKey];
    if (template) {
      setCampaignData(prev => ({
        ...prev,
        name: prev.name || template.name,
        subject: template.subject,
        html_content: template.html_content
      }));
      setTemplateSelectorOpen(false);
      toast.success(`Loaded "${template.name}" template`);
    }
  };

  const addSingleContact = async () => {
    if (!newContactEmail.trim()) {
      toast.error('Please enter an email address');
      return;
    }
    if (!consentConfirmed) {
      toast.error('Please confirm you have permission to email this contact');
      return;
    }

    setAddingContact(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(`${API}/user/marketing/contacts`, {
        email: newContactEmail,
        name: newContactName || null,
        consent_confirmed: true
      }, { headers });
      
      toast.success('Contact added successfully');
      setAddContactDialogOpen(false);
      setNewContactEmail('');
      setNewContactName('');
      setConsentConfirmed(false);
      fetchContacts();
      fetchContactStats();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to add contact';
      toast.error(message);
    } finally {
      setAddingContact(false);
    }
  };

  const addBulkContacts = async () => {
    if (!bulkEmails.trim()) {
      toast.error('Please enter email addresses');
      return;
    }
    if (!consentConfirmed) {
      toast.error('Please confirm you have permission to email these contacts');
      return;
    }

    setAddingContact(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      
      // First parse the emails
      const parseResponse = await axios.post(`${API}/user/marketing/contacts/parse`, {
        emails: bulkEmails
      }, { headers });
      
      const validEmails = parseResponse.data.valid || [];
      
      if (validEmails.length === 0) {
        toast.error('No valid emails found');
        setAddingContact(false);
        return;
      }
      
      // Then add them
      const addResponse = await axios.post(`${API}/user/marketing/contacts/bulk`, {
        emails: validEmails,
        consent_confirmed: true
      }, { headers });
      
      const result = addResponse.data;
      
      if (result.added_count > 0) {
        toast.success(`Added ${result.added_count} contacts`);
      }
      if (result.duplicates_count > 0) {
        toast.info(`${result.duplicates_count} duplicates skipped`);
      }
      if (result.invalid_count > 0) {
        toast.warning(`${result.invalid_count} invalid emails skipped`);
      }
      
      setBulkAddDialogOpen(false);
      setBulkEmails('');
      setConsentConfirmed(false);
      fetchContacts();
      fetchContactStats();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to add contacts';
      toast.error(message);
    } finally {
      setAddingContact(false);
    }
  };

  const handleCsvUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    if (!consentConfirmed) {
      toast.error('Please confirm you have permission to email these contacts first');
      if (csvInputRef.current) csvInputRef.current.value = '';
      return;
    }

    setAddingContact(true);
    try {
      const headers = { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      };
      const formData = new FormData();
      formData.append('file', file);
      
      const parseResponse = await axios.post(`${API}/user/marketing/contacts/csv`, formData, { headers });
      
      const validEmails = parseResponse.data.valid || [];
      
      if (validEmails.length === 0) {
        toast.error('No valid emails found in CSV');
        setAddingContact(false);
        if (csvInputRef.current) csvInputRef.current.value = '';
        return;
      }
      
      // Add the parsed emails
      const addResponse = await axios.post(`${API}/user/marketing/contacts/bulk`, {
        emails: validEmails,
        consent_confirmed: true
      }, { headers });
      
      const result = addResponse.data;
      toast.success(`Added ${result.added_count} contacts from CSV`);
      
      if (result.duplicates_count > 0) {
        toast.info(`${result.duplicates_count} duplicates skipped`);
      }
      
      fetchContacts();
      fetchContactStats();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to upload CSV';
      toast.error(message);
    } finally {
      setAddingContact(false);
      if (csvInputRef.current) csvInputRef.current.value = '';
    }
  };

  const deleteSelectedContacts = async () => {
    if (selectedContacts.length === 0) return;
    
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(`${API}/user/marketing/contacts/delete-bulk`, {
        contact_ids: selectedContacts
      }, { headers });
      
      toast.success(`Deleted ${selectedContacts.length} contacts`);
      setSelectedContacts([]);
      fetchContacts();
      fetchContactStats();
    } catch (error) {
      toast.error('Failed to delete contacts');
    }
  };

  const openCampaignBuilder = (campaign = null) => {
    if (campaign) {
      setEditingCampaign(campaign);
      setCampaignData({
        name: campaign.name,
        subject: campaign.subject,
        html_content: campaign.html_content,
        contact_ids: campaign.contact_ids || []
      });
    } else {
      setEditingCampaign(null);
      setCampaignData({
        name: '',
        subject: '',
        html_content: getDefaultTemplate(),
        contact_ids: []
      });
    }
    setSendConsentConfirmed(false);
    setCampaignBuilderOpen(true);
  };

  const getDefaultTemplate = () => {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #3B82F6, #8B5CF6); padding: 30px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">Auction Alert</h1>
    </div>
    
    <div style="padding: 30px;">
      <p style="color: #333; font-size: 16px;">Hello {{name}},</p>
      
      <p style="color: #333; font-size: 16px;">
        I wanted to share an exciting auction opportunity with you!
      </p>
      
      <p style="color: #333; font-size: 16px;">
        [Add your auction details here]
      </p>
      
      <div style="text-align: center; margin: 30px 0;">
        <a href="#" style="display: inline-block; background: #3B82F6; color: white; padding: 14px 40px; text-decoration: none; border-radius: 6px; font-weight: bold;">
          View Auction
        </a>
      </div>
    </div>
    
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
      <p style="color: #666; font-size: 12px; margin: 0;">
        You received this email from ${user?.name || 'a BidVex seller'}.
      </p>
      <p style="margin: 10px 0 0; font-size: 12px;">
        <a href="{{unsubscribe_url}}" style="color: #999;">Unsubscribe</a>
      </p>
    </div>
  </div>
</body>
</html>`;
  };

  const saveCampaign = async () => {
    if (!campaignData.name.trim() || !campaignData.subject.trim()) {
      toast.error('Please fill in campaign name and subject');
      return;
    }

    setSavingCampaign(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      
      if (editingCampaign) {
        await axios.put(`${API}/user/marketing/campaigns/${editingCampaign.id}`, campaignData, { headers });
        toast.success('Campaign updated');
      } else {
        await axios.post(`${API}/user/marketing/campaigns`, campaignData, { headers });
        toast.success('Campaign created');
      }
      
      setCampaignBuilderOpen(false);
      fetchCampaigns();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to save campaign';
      toast.error(message);
    } finally {
      setSavingCampaign(false);
    }
  };

  const sendCampaign = async (campaignId) => {
    if (!sendConsentConfirmed) {
      toast.error('Please confirm you have permission to email these contacts');
      return;
    }

    setSendingCampaign(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      
      // Confirm consent
      await axios.post(`${API}/user/marketing/campaigns/${campaignId}/confirm-consent`, {}, { headers });
      
      // Send
      const response = await axios.post(`${API}/user/marketing/campaigns/${campaignId}/send`, {}, { headers });
      
      toast.success(`Campaign sent to ${response.data.sent} contacts`);
      setCampaignBuilderOpen(false);
      setSelectedCampaign(null);
      fetchCampaigns();
      checkAccess(); // Refresh quota
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to send campaign';
      toast.error(message);
    } finally {
      setSendingCampaign(false);
    }
  };

  const viewCampaign = async (campaign) => {
    setSelectedCampaign(campaign);
    if (campaign.status === 'sent') {
      await fetchCampaignStats(campaign.id);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-CA', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  // Locked state for free users
  const LockedState = () => (
    <div className="flex flex-col items-center justify-center py-16 px-4" data-testid="locked-state">
      <div className="w-20 h-20 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center mb-6">
        <Lock className="h-10 w-10 text-slate-400" />
      </div>
      <h2 className="text-2xl font-bold text-center mb-2">Client Email Marketing</h2>
      <p className="text-muted-foreground text-center max-w-md mb-6">
        {access?.upgrade_message || 'Upgrade to Premium or VIP to send auctions to your client list.'}
      </p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl w-full mb-8">
        <Card 
          className="border-2 border-blue-500/20 cursor-pointer hover:border-blue-500/50 hover:shadow-lg transition-all"
          onClick={() => navigate('/seller/dashboard?tab=subscription')}
          data-testid="premium-card"
        >
          <CardHeader className="text-center pb-2">
            <Badge className="w-fit mx-auto bg-blue-500">Premium</Badge>
            <CardTitle className="text-lg mt-2">1 free campaign/month</CardTitle>
          </CardHeader>
          <CardContent className="text-center text-sm text-muted-foreground">
            <ul className="space-y-1">
              <li>10% discount on all emails</li>
              <li>All premium templates</li>
              <li>Open & click analytics</li>
            </ul>
            <Button 
              className="w-full mt-4 bg-blue-600 hover:bg-blue-700"
              onClick={(e) => { e.stopPropagation(); navigate('/seller/dashboard?tab=subscription'); }}
              data-testid="upgrade-premium-btn"
            >
              Upgrade to Premium
            </Button>
          </CardContent>
        </Card>
        
        <Card 
          className="border-2 border-purple-500/20 cursor-pointer hover:border-purple-500/50 hover:shadow-lg transition-all"
          onClick={() => navigate('/seller/dashboard?tab=subscription')}
          data-testid="vip-card"
        >
          <CardHeader className="text-center pb-2">
            <Badge className="w-fit mx-auto bg-purple-500">VIP</Badge>
            <CardTitle className="text-lg mt-2">2 free campaigns/month</CardTitle>
          </CardHeader>
          <CardContent className="text-center text-sm text-muted-foreground">
            <ul className="space-y-1">
              <li>20% discount on all emails</li>
              <li>Priority delivery queue</li>
              <li>Advanced analytics</li>
            </ul>
            <Button 
              className="w-full mt-4 bg-purple-600 hover:bg-purple-700"
              onClick={(e) => { e.stopPropagation(); navigate('/seller/dashboard?tab=subscription'); }}
              data-testid="upgrade-vip-btn"
            >
              Upgrade to VIP
            </Button>
          </CardContent>
        </Card>
      </div>
      
      <div className="flex flex-col sm:flex-row gap-3">
        <Button 
          size="lg" 
          className="gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
          onClick={() => navigate('/seller/dashboard?tab=subscription')}
          data-testid="view-subscription-plans-btn"
        >
          <Crown className="h-5 w-5" />
          View Subscription Plans
        </Button>
        <Button 
          size="lg" 
          variant="outline"
          className="gap-2"
          onClick={() => navigate('/email-marketing-pricing')}
          data-testid="see-pricing-btn"
        >
          <DollarSign className="h-5 w-5" />
          See Pay-As-You-Go Pricing
        </Button>
      </div>
      
      <p className="text-sm text-muted-foreground mt-4">
        Free plan: Build your list with up to 50 contacts. Upgrade to start sending.
      </p>
    </div>
  );

  if (loading) {
    return (
      <div className="p-8 text-center">
        <RefreshCw className="h-8 w-8 animate-spin mx-auto text-primary" />
        <p className="mt-4 text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Mail className="h-6 w-6 text-primary" />
            Client Email Marketing
          </h1>
          <p className="text-muted-foreground flex items-center gap-2">
            {access?.can_send 
              ? 'Send auction campaigns to your client list'
              : 'Build your contact list and upgrade to send campaigns'
            }
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {access?.can_send ? (
            <Button 
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white gap-2"
              onClick={() => {
                setActiveTab('campaigns');
                openCampaignBuilder();
              }}
              data-testid="send-campaign-btn"
            >
              <Send className="h-4 w-4" />
              Send Campaign
            </Button>
          ) : (
            <Button 
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white gap-2"
              onClick={() => navigate('/seller/dashboard?tab=subscription')}
              data-testid="upgrade-to-send-btn"
            >
              <Crown className="h-4 w-4" />
              Upgrade to Send
            </Button>
          )}
          <Badge 
            variant={access?.subscription_tier === 'vip' ? 'default' : access?.subscription_tier === 'premium' ? 'default' : 'secondary'} 
            className="uppercase cursor-pointer hover:opacity-80"
            onClick={() => navigate('/seller/dashboard?tab=subscription')}
            data-testid="subscription-badge"
          >
            {access?.subscription_tier || 'free'}
          </Badge>
        </div>
      </div>

      {/* Upgrade banner for free users */}
      {!access?.can_send && (
        <div className="flex items-start gap-3 p-4 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-950/30 dark:to-purple-950/30 rounded-lg border border-blue-200 dark:border-blue-800" data-testid="upgrade-banner">
          <Lock className="h-5 w-5 text-blue-600 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium text-blue-700 dark:text-blue-300">
              Turn your buyer list into revenue
            </p>
            <p className="text-sm text-blue-600 dark:text-blue-400">
              Upgrade to Premium to send auction announcements to your contacts. 
              Free plan lets you build a list of up to 50 contacts.{' '}
              <button 
                onClick={() => navigate('/email-marketing-pricing')} 
                className="underline font-medium hover:text-blue-800 cursor-pointer"
                data-testid="see-pricing-link"
              >
                See pricing & how it works
              </button>
            </p>
          </div>
          <Button 
            size="sm" 
            className="gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white" 
            onClick={() => navigate('/seller/dashboard?tab=subscription')}
            data-testid="upgrade-banner-btn"
          >
            <Crown className="h-4 w-4" />
            Upgrade
          </Button>
        </div>
      )}

      {/* Quota Warning for paid users */}
      {access?.can_send && access?.quota?.monthly_remaining < 100 && access?.quota?.monthly_remaining > 0 && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200 dark:border-amber-800">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
          <div>
            <p className="font-medium text-amber-700 dark:text-amber-300">Low Quota</p>
            <p className="text-sm text-amber-600 dark:text-amber-400">
              You have {access.quota.monthly_remaining} emails remaining this month.
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4 max-w-lg">
          <TabsTrigger value="contacts" className="gap-2" data-testid="tab-contacts">
            <Users className="h-4 w-4" />
            <span className="hidden sm:inline">Contacts</span>
          </TabsTrigger>
          <TabsTrigger value="campaigns" className="gap-2" disabled={!access?.can_send} data-testid="tab-campaigns">
            <Send className="h-4 w-4" />
            <span className="hidden sm:inline">Campaigns</span>
            {!access?.can_send && <Lock className="h-3 w-3 ml-1" />}
          </TabsTrigger>
          <TabsTrigger value="analytics" className="gap-2" disabled={!access?.can_send} data-testid="tab-analytics">
            <BarChart3 className="h-4 w-4" />
            <span className="hidden sm:inline">Analytics</span>
            {!access?.can_send && <Lock className="h-3 w-3 ml-1" />}
          </TabsTrigger>
          <TabsTrigger 
            value="pricing" 
            className="gap-2" 
            onClick={(e) => {
              e.preventDefault();
              navigate('/email-marketing-pricing');
            }}
            data-testid="tab-pricing"
          >
            <DollarSign className="h-4 w-4" />
            <span className="hidden sm:inline">Pricing</span>
          </TabsTrigger>
        </TabsList>

        {/* Contacts Tab */}
        <TabsContent value="contacts" className="space-y-4">
          {/* Contact Limit for free users */}
          {!access?.can_send && contactStats && (
            <Card className="border-blue-200 dark:border-blue-800">
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="font-medium">Contact Storage</p>
                  <p className="text-sm text-muted-foreground">
                    {contactStats.total} / {access?.contact_limit?.limit || 50} contacts used
                  </p>
                </div>
                <div className="w-32 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-blue-500" 
                    style={{ width: `${Math.min(100, (contactStats.total / (access?.contact_limit?.limit || 50)) * 100)}%` }}
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Stats */}
          {contactStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="p-4 text-center">
                  <p className="text-3xl font-bold">{contactStats.total}</p>
                  <p className="text-sm text-muted-foreground">Total</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 text-center">
                  <p className="text-3xl font-bold text-green-600">{contactStats.active}</p>
                  <p className="text-sm text-muted-foreground">Active</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 text-center">
                  <p className="text-3xl font-bold text-amber-600">{contactStats.unsubscribed}</p>
                  <p className="text-sm text-muted-foreground">Unsubscribed</p>
                </CardContent>
              </Card>
              <Card>
                    <CardContent className="p-4 text-center">
                      <p className="text-3xl font-bold text-red-600">{contactStats.bounced}</p>
                      <p className="text-sm text-muted-foreground">Bounced</p>
                    </CardContent>
                  </Card>
                </div>
              )}

              {/* Actions */}
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => setAddContactDialogOpen(true)} className="gap-2">
                  <UserPlus className="h-4 w-4" />
                  Add Contact
                </Button>
                <Button variant="outline" onClick={() => setBulkAddDialogOpen(true)} className="gap-2">
                  <Plus className="h-4 w-4" />
                  Bulk Add
                </Button>
                <input
                  type="file"
                  ref={csvInputRef}
                  accept=".csv"
                  onChange={handleCsvUpload}
                  className="hidden"
                />
                <Button 
                  variant="outline" 
                  onClick={() => {
                    if (!consentConfirmed) {
                      setConsentConfirmed(true);
                      toast.info('Please confirm consent then click Upload CSV again');
                      return;
                    }
                    csvInputRef.current?.click();
                  }}
                  disabled={addingContact}
                  className="gap-2"
                >
                  <Upload className="h-4 w-4" />
                  Upload CSV
                </Button>
                {selectedContacts.length > 0 && (
                  <Button variant="destructive" onClick={deleteSelectedContacts} className="gap-2">
                    <Trash2 className="h-4 w-4" />
                    Delete ({selectedContacts.length})
                  </Button>
                )}
              </div>

              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search contacts..."
                  value={contactSearch}
                  onChange={(e) => setContactSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && fetchContacts()}
                  className="pl-10"
                />
              </div>

              {/* Contacts List */}
              <Card>
                <CardContent className="p-0">
                  {contacts.length === 0 ? (
                    <div className="p-8 text-center text-muted-foreground">
                      <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>No contacts yet. Add your first contact!</p>
                    </div>
                  ) : (
                    <div className="divide-y">
                      {contacts.map(contact => (
                        <div 
                          key={contact.id}
                          className="flex items-center gap-3 p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        >
                          <Checkbox
                            checked={selectedContacts.includes(contact.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedContacts([...selectedContacts, contact.id]);
                              } else {
                                setSelectedContacts(selectedContacts.filter(id => id !== contact.id));
                              }
                            }}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate">{contact.email}</p>
                            {contact.name && (
                              <p className="text-sm text-muted-foreground">{contact.name}</p>
                            )}
                          </div>
                          <Badge variant={contact.status === 'active' ? 'default' : 'secondary'}>
                            {contact.status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Campaigns Tab */}
            <TabsContent value="campaigns" className="space-y-4">
              <Button onClick={() => openCampaignBuilder()} className="gap-2">
                <Plus className="h-4 w-4" />
                New Campaign
              </Button>

              {selectedCampaign ? (
                <Card>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle>{selectedCampaign.name}</CardTitle>
                        <CardDescription>Subject: {selectedCampaign.subject}</CardDescription>
                      </div>
                      <Button variant="ghost" onClick={() => setSelectedCampaign(null)}>
                        <XCircle className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center gap-2">
                      <Badge variant={selectedCampaign.status === 'sent' ? 'default' : 'secondary'}>
                        {selectedCampaign.status}
                      </Badge>
                      <span className="text-sm text-muted-foreground">
                        {selectedCampaign.recipient_count} recipients
                      </span>
                    </div>

                    {campaignStats && selectedCampaign.status === 'sent' && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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
                      </div>
                    )}

                    {selectedCampaign.status === 'draft' && (
                      <div className="flex gap-2">
                        <Button onClick={() => openCampaignBuilder(selectedCampaign)} className="gap-2">
                          <Edit3 className="h-4 w-4" />
                          Edit
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="p-0">
                    {campaigns.length === 0 ? (
                      <div className="p-8 text-center text-muted-foreground">
                        <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>No campaigns yet. Create your first campaign!</p>
                      </div>
                    ) : (
                      <div className="divide-y">
                        {campaigns.map(campaign => (
                          <div 
                            key={campaign.id}
                            className="flex items-center justify-between gap-3 p-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer"
                            onClick={() => viewCampaign(campaign)}
                          >
                            <div className="flex-1 min-w-0">
                              <p className="font-medium truncate">{campaign.name}</p>
                              <p className="text-sm text-muted-foreground truncate">{campaign.subject}</p>
                              <p className="text-xs text-muted-foreground mt-1">
                                {campaign.recipient_count} recipients • {formatDate(campaign.created_at)}
                              </p>
                            </div>
                            <Badge variant={campaign.status === 'sent' ? 'default' : 'secondary'}>
                              {campaign.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Analytics Tab */}
            <TabsContent value="analytics" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Campaign Performance</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg text-center">
                      <p className="text-3xl font-bold">{campaigns.length}</p>
                      <p className="text-sm text-muted-foreground">Total Campaigns</p>
                    </div>
                    <div className="p-4 bg-green-50 dark:bg-green-950/30 rounded-lg text-center">
                      <p className="text-3xl font-bold text-green-600">
                        {campaigns.filter(c => c.status === 'sent').length}
                      </p>
                      <p className="text-sm text-muted-foreground">Sent</p>
                    </div>
                    <div className="p-4 bg-blue-50 dark:bg-blue-950/30 rounded-lg text-center">
                      <p className="text-3xl font-bold text-blue-600">{access.quota?.used || 0}</p>
                      <p className="text-sm text-muted-foreground">Emails This Month</p>
                    </div>
                    <div className="p-4 bg-purple-50 dark:bg-purple-950/30 rounded-lg text-center">
                      <p className="text-3xl font-bold text-purple-600">{contactStats?.total || 0}</p>
                      <p className="text-sm text-muted-foreground">Total Contacts</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

      {/* Add Single Contact Dialog */}
      <Dialog open={addContactDialogOpen} onOpenChange={setAddContactDialogOpen}>
        <DialogContent className="w-[95vw] max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Add Contact</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Email *</Label>
              <Input
                type="email"
                value={newContactEmail}
                onChange={(e) => setNewContactEmail(e.target.value)}
                placeholder="contact@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label>Name (optional)</Label>
              <Input
                value={newContactName}
                onChange={(e) => setNewContactName(e.target.value)}
                placeholder="John Doe"
              />
            </div>
            <div className="flex items-start gap-2">
              <Checkbox
                id="consent"
                checked={consentConfirmed}
                onCheckedChange={setConsentConfirmed}
              />
              <label htmlFor="consent" className="text-sm cursor-pointer">
                I confirm I have permission to email this contact
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddContactDialogOpen(false)}>Cancel</Button>
            <Button onClick={addSingleContact} disabled={addingContact} className="gap-2">
              {addingContact ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Add Contact
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Add Dialog */}
      <Dialog open={bulkAddDialogOpen} onOpenChange={setBulkAddDialogOpen}>
        <DialogContent className="w-[95vw] max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Bulk Add Contacts</DialogTitle>
            <DialogDescription>
              Enter email addresses separated by commas, semicolons, or new lines
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Textarea
              value={bulkEmails}
              onChange={(e) => setBulkEmails(e.target.value)}
              placeholder="email1@example.com&#10;email2@example.com&#10;email3@example.com"
              rows={8}
            />
            <div className="flex items-start gap-2">
              <Checkbox
                id="bulkConsent"
                checked={consentConfirmed}
                onCheckedChange={setConsentConfirmed}
              />
              <label htmlFor="bulkConsent" className="text-sm cursor-pointer">
                I confirm I have permission to email all these contacts
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkAddDialogOpen(false)}>Cancel</Button>
            <Button onClick={addBulkContacts} disabled={addingContact} className="gap-2">
              {addingContact ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Add Contacts
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Campaign Builder Dialog */}
      <Dialog open={campaignBuilderOpen} onOpenChange={setCampaignBuilderOpen}>
        <DialogContent className="w-[95vw] max-w-[800px] max-h-[90vh] overflow-y-auto p-0 gap-0">
          <DialogHeader className="sticky top-0 bg-background z-10 p-4 sm:p-6 pb-4 border-b">
            <DialogTitle>
              {editingCampaign ? 'Edit Campaign' : 'New Campaign'}
            </DialogTitle>
          </DialogHeader>
          
          <div className="p-4 sm:p-6 space-y-4">
            {/* Template Selector */}
            <div className="space-y-2">
              <Label>Start with a Template</Label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(templates).map(([key, template]) => (
                  <button
                    key={key}
                    onClick={() => selectTemplate(key)}
                    className="p-3 text-left border rounded-lg hover:border-primary hover:bg-primary/5 transition-colors"
                  >
                    <p className="font-medium text-sm">{template.name}</p>
                    <p className="text-xs text-muted-foreground line-clamp-2">{template.description}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Campaign Name *</Label>
                <Input
                  value={campaignData.name}
                  onChange={(e) => setCampaignData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Summer Auction Alert"
                />
              </div>
              <div className="space-y-2">
                <Label>Email Subject *</Label>
                <Input
                  value={campaignData.subject}
                  onChange={(e) => setCampaignData(prev => ({ ...prev, subject: e.target.value }))}
                  placeholder="Don't miss this auction!"
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Email Content (HTML)</Label>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setTemplateSelectorOpen(!templateSelectorOpen)}
                >
                  Preview
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Use {'{{name}}'}, {'{{email}}'}, {'{{unsubscribe_url}}'} for personalization
              </p>
              {templateSelectorOpen && campaignData.html_content && (
                <Card className="p-4 mb-2">
                  <div 
                    className="prose dark:prose-invert max-w-none text-sm"
                    dangerouslySetInnerHTML={{ 
                      __html: campaignData.html_content
                        .replace(/\{\{name\}\}/g, 'John')
                        .replace(/\{\{email\}\}/g, 'john@example.com')
                        .replace(/\{\{unsubscribe_url\}\}/g, '#') 
                    }} 
                  />
                </Card>
              )}
              <Textarea
                value={campaignData.html_content}
                onChange={(e) => setCampaignData(prev => ({ ...prev, html_content: e.target.value }))}
                rows={12}
                className="font-mono text-sm"
              />
            </div>

            <div className="p-4 bg-amber-50 dark:bg-amber-950/30 rounded-lg">
              <div className="flex items-start gap-2">
                <Checkbox
                  id="sendConsent"
                  checked={sendConsentConfirmed}
                  onCheckedChange={setSendConsentConfirmed}
                />
                <label htmlFor="sendConsent" className="text-sm cursor-pointer">
                  <strong>I confirm I have permission to email these contacts.</strong>
                  <br />
                  <span className="text-muted-foreground">
                    All emails include an unsubscribe link. Sending to contacts without consent 
                    violates CAN-SPAM, GDPR, and CASL regulations.
                  </span>
                </label>
              </div>
            </div>
          </div>

          <DialogFooter className="sticky bottom-0 bg-background z-10 p-4 sm:p-6 pt-4 border-t flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setCampaignBuilderOpen(false)} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button onClick={saveCampaign} disabled={savingCampaign} className="w-full sm:w-auto gap-2">
              {savingCampaign ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
              Save Draft
            </Button>
            <Button
              onClick={async () => {
                await saveCampaign();
                // Get the campaign ID and send
                if (editingCampaign?.id) {
                  await sendCampaign(editingCampaign.id);
                }
              }}
              disabled={savingCampaign || sendingCampaign || !sendConsentConfirmed}
              className="w-full sm:w-auto gap-2 bg-green-600 hover:bg-green-700"
            >
              {sendingCampaign ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Save & Send
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ClientEmailMarketing;
