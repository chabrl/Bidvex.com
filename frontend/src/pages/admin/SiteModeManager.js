import API_BASE from '../../config';
/**
 * SiteModeManager - Admin control for website maintenance/coming soon mode
 * Features: Toggle between Live/Maintenance/Coming Soon, custom messages, subscriber management
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import { toast } from 'sonner';
import {
  Globe, Wrench, Rocket, RefreshCw, Save, Eye, Users, Mail,
  Download, Trash2, Search, Calendar, TrendingUp, AlertTriangle,
  CheckCircle, Clock, ExternalLink, Copy, Twitter, Facebook, Instagram, Linkedin, Lock, Info
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../../components/ui/dialog';
import { useTranslation } from 'react-i18next';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';

const API = API_BASE;

const SITE_MODES = [
  {
    id: 'live',
    label: 'Live Mode',
    description: 'Normal website access for all users',
    icon: Globe,
    color: 'bg-green-500',
    textColor: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-900/20',
    borderColor: 'border-green-200 dark:border-green-800'
  },
  {
    id: 'maintenance',
    label: 'Maintenance Mode',
    description: 'Website under maintenance - shows maintenance page',
    icon: Wrench,
    color: 'bg-amber-500',
    textColor: 'text-amber-600 dark:text-amber-400',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    borderColor: 'border-amber-200 dark:border-amber-800'
  },
  {
    id: 'coming_soon',
    label: 'Coming Soon Mode',
    description: 'Website not launched - shows coming soon page with email signup',
    icon: Rocket,
    color: 'bg-blue-500',
    textColor: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    borderColor: 'border-blue-200 dark:border-blue-800'
  }
];

const SiteModeManager = () => {
  const { t } = useTranslation();
  const [currentMode, setCurrentMode] = useState('live');
  const [message, setMessage] = useState('');
  const [expectedBack, setExpectedBack] = useState('');
  const [messageFr, setMessageFr] = useState('');
  const [scheduledStart, setScheduledStart] = useState('');
  const [scheduledEnd, setScheduledEnd] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [updatedAt, setUpdatedAt] = useState(null);
  
  // Social links state
  const [socialLinks, setSocialLinks] = useState({
    twitter: '',
    facebook: '',
    instagram: '',
    linkedin: ''
  });
  
  // Subscribers state
  const [subscribers, setSubscribers] = useState([]);
  const [subscriberStats, setSubscriberStats] = useState(null);
  const [loadingSubscribers, setLoadingSubscribers] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showSubscribers, setShowSubscribers] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [subscriberToDelete, setSubscriberToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchSiteMode();
    fetchSubscriberStats();
  }, []);

  const fetchSiteMode = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/site-mode`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCurrentMode(response.data.mode || 'live');
      setMessage(response.data.message || '');
      setMessageFr(response.data.message_fr || '');
      setExpectedBack(response.data.expected_back || '');
      setScheduledStart(response.data.scheduled_start || '');
      setScheduledEnd(response.data.scheduled_end || '');
      setSocialLinks(response.data.social_links || { twitter: '', facebook: '', instagram: '', linkedin: '' });
      setUpdatedAt(response.data.updated_at);
    } catch (error) {
      console.error('Error fetching site mode:', error);
      toast.error('Failed to fetch site mode');
    } finally {
      setLoading(false);
    }
  };

  const fetchSubscriberStats = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/admin/subscribers/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data.success) {
        setSubscriberStats(response.data);
      }
    } catch (error) {
      console.error('Error fetching subscriber stats:', error);
    }
  };

  const fetchSubscribers = async () => {
    setLoadingSubscribers(true);
    try {
      const token = localStorage.getItem('token');
      const params = searchTerm ? { search: searchTerm } : {};
      const response = await axios.get(`${API}/admin/subscribers`, {
        headers: { Authorization: `Bearer ${token}` },
        params
      });
      if (response.data.success) {
        setSubscribers(response.data.subscribers);
      }
    } catch (error) {
      console.error('Error fetching subscribers:', error);
      toast.error('Failed to load subscribers');
    } finally {
      setLoadingSubscribers(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      await axios.put(`${API}/admin/site-mode`, {
        mode: currentMode,
        message: message || null,
        message_fr: messageFr || null,
        expected_back: expectedBack || null,
        scheduled_start: scheduledStart || null,
        scheduled_end: scheduledEnd || null,
        social_links: socialLinks
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Site mode updated to: ${SITE_MODES.find(m => m.id === currentMode)?.label}`);
      fetchSiteMode();
    } catch (error) {
      console.error('Error updating site mode:', error);
      toast.error(error.response?.data?.detail || 'Failed to update site mode');
    } finally {
      setSaving(false);
    }
  };

  const handleExportCSV = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/admin/subscribers/export`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.success) {
        // Create and download CSV file
        const blob = new Blob([response.data.csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = response.data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        toast.success(`Exported ${response.data.total} subscribers`);
      }
    } catch (error) {
      console.error('Error exporting subscribers:', error);
      toast.error('Failed to export subscribers');
    }
  };

  const handleDeleteSubscriber = async () => {
    if (!subscriberToDelete) return;
    
    setDeleting(true);
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API}/admin/subscribers/${subscriberToDelete.subscriber_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Subscriber deleted');
      setDeleteDialogOpen(false);
      setSubscriberToDelete(null);
      fetchSubscribers();
      fetchSubscriberStats();
    } catch (error) {
      console.error('Error deleting subscriber:', error);
      toast.error('Failed to delete subscriber');
    } finally {
      setDeleting(false);
    }
  };

  const handleViewSubscribers = () => {
    setShowSubscribers(true);
    fetchSubscribers();
  };

  const handlePreview = () => {
    window.open('/?preview_mode=true', '_blank');
  };

  const modeConfig = SITE_MODES.find(m => m.id === currentMode);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="site-mode-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Globe className="h-6 w-6 text-primary" />
            Site Mode
          </h2>
          <p className="text-muted-foreground">Control website access and maintenance mode</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handlePreview} className="gap-2">
            <Eye className="h-4 w-4" />
            Preview
          </Button>
          <Button onClick={handleSave} disabled={saving} className="gap-2">
            {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save Changes
          </Button>
        </div>
      </div>

      {/* Current Status */}
      {modeConfig && (
        <Card className={`${modeConfig.bgColor} ${modeConfig.borderColor} border-2`}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-xl ${modeConfig.color}`}>
                  <modeConfig.icon className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h3 className={`text-lg font-semibold ${modeConfig.textColor}`}>
                    Current: {modeConfig.label}
                  </h3>
                  <p className="text-sm text-muted-foreground">{modeConfig.description}</p>
                </div>
              </div>
              {updatedAt && (
                <Badge variant="secondary" className="gap-1">
                  <Clock className="h-3 w-3" />
                  Updated: {new Date(updatedAt).toLocaleString()}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Admin Access Info - Show when not in live mode */}
      {currentMode !== 'live' && (
        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-800 rounded-lg">
              <Lock className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h4 className="font-semibold text-blue-900 dark:text-blue-200">Admin Access</h4>
              <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                While the site is in {currentMode === 'maintenance' ? 'Maintenance' : 'Coming Soon'} mode:
              </p>
              <ul className="text-sm text-blue-600 dark:text-blue-400 mt-2 space-y-1 list-disc list-inside">
                <li>Go to <code className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-800 rounded text-xs">/admin</code> to access the admin panel</li>
                <li>Login with your <code className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-800 rounded text-xs">@bidvex.com</code> admin email</li>
                <li>A lock icon <Lock className="h-3 w-3 inline" /> on the maintenance page links to admin</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Mode Selection */}
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.selectSiteMode")}</CardTitle>
          <CardDescription>{t("admin.chooseSiteMode")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-4">
            {SITE_MODES.map((mode) => {
              const Icon = mode.icon;
              const isSelected = currentMode === mode.id;
              
              return (
                <div
                  key={mode.id}
                  onClick={() => setCurrentMode(mode.id)}
                  className={`cursor-pointer p-6 rounded-xl border-2 transition-all duration-200 ${
                    isSelected 
                      ? `${mode.bgColor} ${mode.borderColor} ring-2 ring-offset-2 ring-${mode.id === 'live' ? 'green' : mode.id === 'maintenance' ? 'amber' : 'blue'}-500/30`
                      : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
                  }`}
                  data-testid={`mode-option-${mode.id}`}
                >
                  <div className="flex items-start gap-4">
                    <div className={`p-3 rounded-xl ${isSelected ? mode.color : 'bg-slate-100 dark:bg-slate-700'}`}>
                      <Icon className={`h-6 w-6 ${isSelected ? 'text-white' : 'text-slate-500'}`} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold">{mode.label}</h4>
                        {isSelected && <CheckCircle className={`h-4 w-4 ${mode.textColor}`} />}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">{mode.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Custom Settings (for Maintenance/Coming Soon) */}
      {currentMode !== 'live' && (
        <Card>
          <CardHeader>
            <CardTitle>{t("admin.pageSettings")}</CardTitle>
            <CardDescription>{t("admin.customizeMessage")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Custom Message — English <span className="text-xs text-muted-foreground">(Optional)</span></Label>
              <Textarea
                placeholder="Enter a custom message for visitors..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={3}
                data-testid="site-mode-message-en"
              />
            </div>

            <div className="space-y-2">
              <Label>Custom Message — Français <span className="text-xs text-muted-foreground">(Optionnel)</span></Label>
              <Textarea
                placeholder="Entrez un message personnalisé en français..."
                value={messageFr}
                onChange={(e) => setMessageFr(e.target.value)}
                rows={3}
                data-testid="site-mode-message-fr"
              />
              <p className="text-xs text-muted-foreground">
                Shown to French-speaking visitors. Leave empty to use English for both.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="space-y-2">
                <Label>Expected Back Online</Label>
                <Input
                  type="datetime-local"
                  value={expectedBack}
                  onChange={(e) => setExpectedBack(e.target.value)}
                  data-testid="site-mode-expected-back"
                />
                <p className="text-xs text-muted-foreground">Display as countdown</p>
              </div>
              <div className="space-y-2">
                <Label>Scheduled Start</Label>
                <Input
                  type="datetime-local"
                  value={scheduledStart}
                  onChange={(e) => setScheduledStart(e.target.value)}
                  data-testid="site-mode-scheduled-start"
                />
                <p className="text-xs text-muted-foreground">Auto-activate at this time</p>
              </div>
              <div className="space-y-2">
                <Label>Scheduled End</Label>
                <Input
                  type="datetime-local"
                  value={scheduledEnd}
                  onChange={(e) => setScheduledEnd(e.target.value)}
                  data-testid="site-mode-scheduled-end"
                />
                <p className="text-xs text-muted-foreground">Auto-revert to live</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Social Media Links */}
      {currentMode !== 'live' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ExternalLink className="h-5 w-5" />
              Social Media Links
            </CardTitle>
            <CardDescription>Configure social media links shown on the coming soon / maintenance page</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Twitter className="h-4 w-4 text-blue-400" />
                  Twitter / X
                </Label>
                <Input
                  placeholder="https://twitter.com/bidvex"
                  value={socialLinks.twitter || ''}
                  onChange={(e) => setSocialLinks(prev => ({ ...prev, twitter: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Facebook className="h-4 w-4 text-blue-600" />
                  Facebook
                </Label>
                <Input
                  placeholder="https://facebook.com/bidvex"
                  value={socialLinks.facebook || ''}
                  onChange={(e) => setSocialLinks(prev => ({ ...prev, facebook: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Instagram className="h-4 w-4 text-pink-500" />
                  Instagram
                </Label>
                <Input
                  placeholder="https://instagram.com/bidvex"
                  value={socialLinks.instagram || ''}
                  onChange={(e) => setSocialLinks(prev => ({ ...prev, instagram: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Linkedin className="h-4 w-4 text-blue-700" />
                  LinkedIn
                </Label>
                <Input
                  placeholder="https://linkedin.com/company/bidvex"
                  value={socialLinks.linkedin || ''}
                  onChange={(e) => setSocialLinks(prev => ({ ...prev, linkedin: e.target.value }))}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-4">
              Leave empty to hide the icon. Social icons appear in the footer of the maintenance/coming soon page.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Subscriber Stats */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Launch Subscribers
              </CardTitle>
              <CardDescription>{t("admin.emailSignups")}</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={handleExportCSV} className="gap-2">
                <Download className="h-4 w-4" />
                Export CSV
              </Button>
              <Button onClick={handleViewSubscribers} className="gap-2">
                <Users className="h-4 w-4" />
                View All
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {subscriberStats ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                <p className="text-sm text-blue-600 dark:text-blue-400">Total Subscribers</p>
                <p className="text-3xl font-bold text-blue-700 dark:text-blue-300">{subscriberStats.total}</p>
              </div>
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-xl">
                <p className="text-sm text-green-600 dark:text-green-400">Today</p>
                <p className="text-3xl font-bold text-green-700 dark:text-green-300">{subscriberStats.today}</p>
              </div>
              <div className="col-span-2 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl">
                <p className="text-sm text-muted-foreground mb-2">Last 7 Days</p>
                <div className="flex items-end gap-1 h-12">
                  {subscriberStats.daily_trend?.map((day, idx) => {
                    const maxCount = Math.max(...subscriberStats.daily_trend.map(d => d.count), 1);
                    const height = (day.count / maxCount) * 100;
                    return (
                      <div
                        key={idx}
                        className="flex-1 flex flex-col items-center gap-1"
                        title={`${day.date}: ${day.count}`}
                      >
                        <div
                          className="w-full bg-primary/80 rounded-t transition-all"
                          style={{ height: `${Math.max(height, 4)}%` }}
                        />
                        <span className="text-[10px] text-muted-foreground">{day.date.split(' ')[0]}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No subscriber data available</p>
          )}
        </CardContent>
      </Card>

      {/* Subscribers Dialog */}
      <Dialog open={showSubscribers} onOpenChange={setShowSubscribers}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>{t("admin.launchSubscribers")}</DialogTitle>
            <DialogDescription>{t("admin.manageSubscribers")}</DialogDescription>
          </DialogHeader>
          
          <div className="flex items-center gap-4 py-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchSubscribers()}
                className="pl-10"
              />
            </div>
            <Button onClick={fetchSubscribers} variant="outline" className="gap-2">
              <Search className="h-4 w-4" />
              Search
            </Button>
          </div>
          
          <div className="flex-1 overflow-auto">
            {loadingSubscribers ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : subscribers.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Mail className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No subscribers found</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>{t("common.subscribed")}</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {subscribers.map((sub) => (
                    <TableRow key={sub.subscriber_id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          {sub.email}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={() => {
                              navigator.clipboard.writeText(sub.email);
                              toast.success('Email copied');
                            }}
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                          {new Date(sub.subscribed_at).toLocaleDateString()}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{sub.source || 'coming_soon'}</Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                          onClick={() => {
                            setSubscriberToDelete(sub);
                            setDeleteDialogOpen(true);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              Delete Subscriber
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <strong>{subscriberToDelete?.email}</strong>?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteSubscriber} disabled={deleting}>
              {deleting ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : null}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SiteModeManager;
