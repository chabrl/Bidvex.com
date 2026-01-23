import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import EnhancedUserManager from './admin/EnhancedUserManager';
import LotsModeration from './admin/LotsModeration';
import ManageAllAuctions from './admin/ManageAllAuctions';
import DeletionRequestsManager from './admin/DeletionRequestsManager';
import AuctionControl from './admin/AuctionControl';
import CategoryManager from './admin/CategoryManager';
import PromotionManager from './admin/PromotionManager';
import AffiliateManager from './admin/AffiliateManager';
import ReportManager from './admin/ReportManager';
import AnalyticsDashboard from './admin/AnalyticsDashboard';
import MessagingOversight from './admin/MessagingOversight';
import TrustSafetyDashboard from './admin/TrustSafetyDashboard';
import AnnouncementManager from './admin/AnnouncementManager';
import AdminBannerManager from '../components/AdminBannerManager';
import AdminLogs from './admin/AdminLogs';
import CurrencyAppealsManager from './admin/CurrencyAppealsManager';
import SubscriptionManager from './admin/SubscriptionManager';
import EmailTemplates from './admin/EmailTemplates';
import MarketplaceSettings from './admin/MarketplaceSettings';
import BrandingLayoutManager from './admin/BrandingLayoutManager';
import SiteContentManager from './admin/SiteContentManager';
import { 
  Users, Package, Gavel, Shield, TrendingUp, Bell, Settings, FileText, 
  MessageSquare, DollarSign, Search, Image, CreditCard, Megaphone, 
  Activity, AlertTriangle, ChevronRight, Power, Zap, Eye, History,
  ToggleLeft, ToggleRight, Clock, Mail, Sliders
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ========== PRIMARY NAVIGATION CATEGORIES ==========
const PRIMARY_TABS = [
  { id: 'marketplace', label: 'Marketplace', icon: '🛒', lucideIcon: Package },
  { id: 'settings', label: 'Settings', icon: '⚙️', lucideIcon: Settings },
  { id: 'banners', label: 'Banners', icon: '🎨', lucideIcon: Image },
  { id: 'analytics', label: 'Analytics', icon: '📊', lucideIcon: TrendingUp },
  { id: 'logs', label: 'Admin Logs', icon: '📋', lucideIcon: FileText },
];

// ========== SECONDARY NAVIGATION (Context-Specific) ==========
const SECONDARY_TABS = {
  marketplace: [
    { id: 'users', label: 'User Management', icon: '👥', lucideIcon: Users },
    { id: 'lots', label: 'Lots Moderation', icon: '📦', lucideIcon: Package },
    { id: 'all-auctions', label: 'Manage All Auctions', icon: '🏛️', lucideIcon: Package },
    { id: 'deletion-requests', label: 'Deletion Requests', icon: '🗑️', lucideIcon: AlertTriangle },
    { id: 'auctions', label: 'Auction Control', icon: '🔨', lucideIcon: Gavel },
    { id: 'categories', label: 'Categories', icon: '📂', lucideIcon: Settings },
  ],
  settings: [
    { id: 'site-content', label: 'Site Content & Pages', icon: '📄', lucideIcon: FileText },
    { id: 'branding-layout', label: 'Branding & Layout', icon: '🎨', lucideIcon: Settings },
    { id: 'marketplace-settings', label: 'Marketplace Settings', icon: '⚙️', lucideIcon: Sliders },
    { id: 'subscriptions', label: 'Subscriptions', icon: '💎', lucideIcon: CreditCard },
    { id: 'trust-safety', label: 'Trust & Safety', icon: '🛡️', lucideIcon: Shield },
    { id: 'email-templates', label: 'Email Templates', icon: '📧', lucideIcon: Mail },
  ],
  banners: [
    { id: 'banner-manager', label: 'Banner Manager', icon: '🖼️', lucideIcon: Image },
    { id: 'announcements', label: 'Announcements', icon: '📢', lucideIcon: Bell },
  ],
  analytics: [
    { id: 'dashboard', label: 'Dashboard', icon: '📈', lucideIcon: TrendingUp },
    { id: 'reports', label: 'Reports', icon: '📑', lucideIcon: FileText },
  ],
  logs: [
    { id: 'action-history', label: 'Action History', icon: '📜', lucideIcon: History },
    { id: 'live-audit', label: 'Live Audit', icon: '👁️', lucideIcon: Eye },
  ],
};

// ========== PROMOTIONS & AFFILIATES (Cross-Cutting) ==========
const MARKETING_TABS = [
  { id: 'promotions', label: 'Promotions', icon: '🎯', lucideIcon: Megaphone },
  { id: 'affiliates', label: 'Affiliates', icon: '🤝', lucideIcon: Users },
];

// ========== FINANCIAL & SAFETY (Cross-Cutting) ==========
const FINANCIAL_TABS = [
  { id: 'currency-appeals', label: 'Currency Appeals', icon: '💰', lucideIcon: DollarSign },
  { id: 'messaging', label: 'Messaging Oversight', icon: '💬', lucideIcon: MessageSquare },
];

const AdminDashboard = () => {
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  
  // Navigation State
  const [primaryTab, setPrimaryTab] = useState('marketplace');
  const [secondaryTab, setSecondaryTab] = useState('users');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Live Controls State
  const [liveControlsOpen, setLiveControlsOpen] = useState(false);
  const [liveSettings, setLiveSettings] = useState({
    biddingEnabled: true,
    buyNowEnabled: true,
    newRegistrations: true,
    promotionsEnabled: true,
    antiSnipingEnabled: true,
    maintenanceMode: false,
  });
  const [liveAuditLog, setLiveAuditLog] = useState([]);
  
  // Stats State
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalListings: 0,
    activeAuctions: 0,
    revenue: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      navigate('/auth');
      return;
    }

    const isAdmin = user.role === 'admin' || 
                    user.role === 'superadmin' || 
                    user.account_type === 'admin' || 
                    user.email?.endsWith('@admin.bazario.com');
    
    if (!isAdmin) {
      toast.error('You do not have permission to access this page');
      navigate('/');
      return;
    }

    fetchDashboardStats();
    fetchLiveSettings();
  }, [user, navigate]);

  // Update secondary tab when primary changes
  useEffect(() => {
    const secondaryOptions = SECONDARY_TABS[primaryTab];
    if (secondaryOptions && secondaryOptions.length > 0) {
      setSecondaryTab(secondaryOptions[0].id);
    }
  }, [primaryTab]);

  // Scroll to top when navigating between admin tabs
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [primaryTab, secondaryTab]);

  const fetchDashboardStats = async () => {
    try {
      const [usersRes, listingsRes, revenueRes] = await Promise.all([
        axios.get(`${API}/admin/users?limit=1`),
        axios.get(`${API}/listings?limit=1`),
        axios.get(`${API}/admin/stats/revenue`)
      ]);

      setStats({
        totalUsers: usersRes.data.total || 0,
        totalListings: listingsRes.data.total || 0,
        activeAuctions: listingsRes.data.active || 0,
        revenue: revenueRes.data.total_revenue || 0
      });
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchLiveSettings = async () => {
    try {
      const response = await axios.get(`${API}/admin/marketplace-settings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = response.data;
      
      // Map backend settings to live controls
      setLiveSettings(prev => ({
        ...prev,
        buyNowEnabled: data.enable_buy_now ?? true,
        antiSnipingEnabled: data.enable_anti_sniping ?? true,
      }));
    } catch (error) {
      console.error('Failed to fetch live settings:', error);
    }
  };

  const handleLiveSettingChange = async (setting, value) => {
    const oldValue = liveSettings[setting];
    
    // Optimistically update UI
    setLiveSettings(prev => ({ ...prev, [setting]: value }));
    
    // Map frontend settings to backend field names
    const settingMap = {
      'buyNowEnabled': 'enable_buy_now',
      'antiSnipingEnabled': 'enable_anti_sniping',
    };
    
    const backendField = settingMap[setting];
    
    // If this is a backend-persisted setting, save it
    if (backendField) {
      try {
        await axios.put(`${API}/admin/marketplace-settings`, {
          [backendField]: value
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        toast.success(`${setting} ${value ? 'enabled' : 'disabled'}`, {
          description: `Saved to server • Changed by ${user.name || user.email}`,
        });
      } catch (error) {
        // Rollback on failure
        setLiveSettings(prev => ({ ...prev, [setting]: oldValue }));
        toast.error('Failed to save setting', {
          description: error.response?.data?.detail || 'Please try again.',
        });
        return;
      }
    } else {
      toast.success(`${setting} ${value ? 'enabled' : 'disabled'}`, {
        description: `Changed by ${user.name || user.email}`,
      });
    }
    
    // Add to audit log
    const logEntry = {
      id: Date.now(),
      admin: user.name || user.email,
      setting: setting,
      oldValue: oldValue,
      newValue: value,
      timestamp: new Date().toISOString(),
    };
    setLiveAuditLog(prev => [logEntry, ...prev].slice(0, 50));
  };

  // Render the active content based on current tab selection
  const renderContent = () => {
    // Check for cross-cutting tabs first
    if (secondaryTab === 'promotions') return <PromotionManager />;
    if (secondaryTab === 'affiliates') return <AffiliateManager />;
    if (secondaryTab === 'currency-appeals') return <CurrencyAppealsManager />;
    if (secondaryTab === 'messaging') return <MessagingOversight />;

    // Primary tab specific content
    switch (primaryTab) {
      case 'marketplace':
        switch (secondaryTab) {
          case 'users': return <EnhancedUserManager />;
          case 'lots': return <LotsModeration />;
          case 'all-auctions': return <ManageAllAuctions />;
          case 'deletion-requests': return <DeletionRequestsManager />;
          case 'auctions': return <AuctionControl />;
          case 'categories': return <CategoryManager />;
          default: return <EnhancedUserManager />;
        }
      case 'settings':
        switch (secondaryTab) {
          case 'site-content': return <SiteContentManager />;
          case 'branding-layout': return <BrandingLayoutManager />;
          case 'marketplace-settings': return <MarketplaceSettings />;
          case 'subscriptions': return <SubscriptionManager />;
          case 'trust-safety': return <TrustSafetyDashboard />;
          case 'email-templates': return <EmailTemplates />;
          default: return <SiteContentManager />;
        }
      case 'banners':
        switch (secondaryTab) {
          case 'banner-manager': return <BannerManager />;
          case 'announcements': return <AnnouncementManager />;
          default: return <BannerManager />;
        }
      case 'analytics':
        switch (secondaryTab) {
          case 'dashboard': return <AnalyticsDashboard />;
          case 'reports': return <ReportManager />;
          default: return <AnalyticsDashboard />;
        }
      case 'logs':
        return (
          <div className="space-y-4">
            {/* Search Bar for Admin Logs */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search admin logs by action, user, or date..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 w-full h-12 text-lg rounded-xl border-2 focus:border-primary"
              />
            </div>
            <AdminLogs searchQuery={searchQuery} />
          </div>
        );
      default:
        return <EnhancedUserManager />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-primary to-accent rounded-lg">
                <Shield className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">Admin Control Panel</h1>
                <p className="text-sm text-muted-foreground">Manage your platform</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Badge className="gradient-bg text-white border-0 px-4 py-1.5">
                {user.role === 'superadmin' ? '👑 Super Admin' : '⚡ Admin'}
              </Badge>
              <Button 
                variant={liveControlsOpen ? "default" : "outline"}
                onClick={() => setLiveControlsOpen(!liveControlsOpen)}
                className="flex items-center gap-2"
              >
                <Zap className="h-4 w-4" />
                Live Controls
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats Row */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="grid grid-cols-4 gap-4">
            <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
              <Users className="h-8 w-8 text-blue-600" />
              <div>
                <p className="text-2xl font-bold text-blue-700">{stats.totalUsers.toLocaleString()}</p>
                <p className="text-xs text-blue-600">Total Users</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
              <Package className="h-8 w-8 text-green-600" />
              <div>
                <p className="text-2xl font-bold text-green-700">{stats.totalListings.toLocaleString()}</p>
                <p className="text-xs text-green-600">Listings</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
              <Gavel className="h-8 w-8 text-purple-600" />
              <div>
                <p className="text-2xl font-bold text-purple-700">{stats.activeAuctions.toLocaleString()}</p>
                <p className="text-xs text-purple-600">Active Auctions</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-amber-50 rounded-lg">
              <DollarSign className="h-8 w-8 text-amber-600" />
              <div>
                <p className="text-2xl font-bold text-amber-700">${stats.revenue.toLocaleString()}</p>
                <p className="text-xs text-amber-600">Revenue</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* PRIMARY NAVIGATION ROW */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center gap-2 py-2 overflow-x-auto">
            {PRIMARY_TABS.map((tab) => {
              const Icon = tab.lucideIcon;
              const isActive = primaryTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setPrimaryTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-full font-medium transition-all whitespace-nowrap ${
                    isActive 
                      ? 'bg-primary text-white shadow-lg' 
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  <span className="text-lg">{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              );
            })}
            
            {/* Separator */}
            <div className="h-8 w-px bg-gray-300 mx-2" />
            
            {/* Marketing Tools */}
            {MARKETING_TABS.map((tab) => {
              const Icon = tab.lucideIcon;
              const isActive = secondaryTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setSecondaryTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-full font-medium transition-all whitespace-nowrap ${
                    isActive 
                      ? 'bg-amber-500 text-white shadow-lg' 
                      : 'bg-amber-50 text-amber-700 hover:bg-amber-100'
                  }`}
                >
                  <span className="text-lg">{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              );
            })}
            
            {/* Financial Tools */}
            {FINANCIAL_TABS.map((tab) => {
              const Icon = tab.lucideIcon;
              const isActive = secondaryTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setSecondaryTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-full font-medium transition-all whitespace-nowrap ${
                    isActive 
                      ? 'bg-emerald-500 text-white shadow-lg' 
                      : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                  }`}
                >
                  <span className="text-lg">{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* SECONDARY NAVIGATION ROW */}
      <div className="bg-gray-100 border-b">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center gap-2 py-2 overflow-x-auto">
            <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
            {SECONDARY_TABS[primaryTab]?.map((tab) => {
              const Icon = tab.lucideIcon;
              const isActive = secondaryTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setSecondaryTab(tab.id)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg font-medium text-sm transition-all whitespace-nowrap ${
                    isActive 
                      ? 'bg-white text-primary shadow border border-primary/20' 
                      : 'text-gray-600 hover:bg-white hover:shadow-sm'
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex gap-6">
          {/* Main Content */}
          <div className={`flex-1 ${liveControlsOpen ? 'mr-80' : ''}`}>
            {renderContent()}
          </div>
        </div>
      </div>

      {/* LIVE CONTROLS PANEL (Fixed Right Sidebar) */}
      {liveControlsOpen && (
        <div className="fixed right-0 top-0 h-screen w-80 bg-white border-l shadow-2xl z-50 overflow-y-auto">
          <div className="sticky top-0 bg-gradient-to-r from-red-600 to-orange-500 text-white p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="h-5 w-5" />
                <h2 className="font-bold text-lg">Live Controls</h2>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setLiveControlsOpen(false)}
                className="text-white hover:bg-white/20"
              >
                ✕
              </Button>
            </div>
            <p className="text-xs text-white/80 mt-1">⚠️ Changes take effect immediately</p>
          </div>

          {/* Live Toggle Controls */}
          <div className="p-4 space-y-4">
            <h3 className="font-semibold text-sm text-gray-500 uppercase tracking-wider">Feature Toggles</h3>
            
            <LiveToggle
              label="Bidding System"
              description="Enable/disable all bidding"
              enabled={liveSettings.biddingEnabled}
              onChange={(v) => handleLiveSettingChange('biddingEnabled', v)}
              icon={<Gavel className="h-4 w-4" />}
            />
            
            <LiveToggle
              label="Buy Now"
              description="Enable/disable Buy Now feature"
              enabled={liveSettings.buyNowEnabled}
              onChange={(v) => handleLiveSettingChange('buyNowEnabled', v)}
              icon={<DollarSign className="h-4 w-4" />}
            />
            
            <LiveToggle
              label="New Registrations"
              description="Allow new user signups"
              enabled={liveSettings.newRegistrations}
              onChange={(v) => handleLiveSettingChange('newRegistrations', v)}
              icon={<Users className="h-4 w-4" />}
            />
            
            <LiveToggle
              label="Promotions"
              description="Enable seller promotions"
              enabled={liveSettings.promotionsEnabled}
              onChange={(v) => handleLiveSettingChange('promotionsEnabled', v)}
              icon={<Megaphone className="h-4 w-4" />}
            />
            
            <LiveToggle
              label="Anti-Sniping"
              description="2-minute extension rule"
              enabled={liveSettings.antiSnipingEnabled}
              onChange={(v) => handleLiveSettingChange('antiSnipingEnabled', v)}
              icon={<Clock className="h-4 w-4" />}
            />
            
            <div className="border-t pt-4 mt-4">
              <LiveToggle
                label="Maintenance Mode"
                description="⚠️ CAUTION: Disables entire site"
                enabled={liveSettings.maintenanceMode}
                onChange={(v) => handleLiveSettingChange('maintenanceMode', v)}
                icon={<AlertTriangle className="h-4 w-4" />}
                dangerous
              />
            </div>
          </div>

          {/* Live Audit Log */}
          <div className="border-t">
            <div className="p-4">
              <h3 className="font-semibold text-sm text-gray-500 uppercase tracking-wider flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Live Edit Audit Log
              </h3>
            </div>
            <div className="max-h-64 overflow-y-auto px-4 pb-4 space-y-2">
              {liveAuditLog.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No changes yet</p>
              ) : (
                liveAuditLog.map((log) => (
                  <div key={log.id} className="bg-gray-50 rounded-lg p-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{log.setting}</span>
                      <span className={log.newValue ? 'text-green-600' : 'text-red-600'}>
                        {log.newValue ? 'ON' : 'OFF'}
                      </span>
                    </div>
                    <div className="text-gray-500 mt-1">
                      {log.admin} • {new Date(log.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ========== LIVE TOGGLE COMPONENT ==========
const LiveToggle = ({ label, description, enabled, onChange, icon, dangerous = false }) => {
  return (
    <div className={`flex items-center justify-between p-3 rounded-lg border ${
      dangerous ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-white'
    }`}>
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${dangerous ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-600'}`}>
          {icon}
        </div>
        <div>
          <p className={`font-medium text-sm ${dangerous ? 'text-red-700' : ''}`}>{label}</p>
          <p className="text-xs text-gray-500">{description}</p>
        </div>
      </div>
      <Switch 
        checked={enabled} 
        onCheckedChange={onChange}
        className={dangerous && enabled ? 'bg-red-500' : ''}
      />
    </div>
  );
};

// ========== BANNER MANAGER COMPONENT ==========
const BannerManager = () => {
  const [banners, setBanners] = useState([
    { id: 1, title: 'Anniversary Sale', location: 'Homepage Hero', active: true, startDate: '2025-12-15', endDate: '2025-12-25' },
    { id: 2, title: 'Holiday Special', location: 'Auction Page', active: false, startDate: '2025-12-20', endDate: '2025-12-31' },
  ]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Image className="h-5 w-5" />
            Banner Manager
          </CardTitle>
          <Button className="gradient-button text-white">
            + Add Banner
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {banners.map((banner) => (
            <div key={banner.id} className="flex items-center justify-between p-4 border rounded-lg">
              <div className="flex items-center gap-4">
                <div className="w-24 h-16 bg-gradient-to-br from-primary/20 to-accent/20 rounded-lg flex items-center justify-center">
                  <Image className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">{banner.title}</h3>
                  <p className="text-sm text-muted-foreground">{banner.location}</p>
                  <p className="text-xs text-gray-500">{banner.startDate} → {banner.endDate}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant={banner.active ? "default" : "secondary"}>
                  {banner.active ? 'Active' : 'Inactive'}
                </Badge>
                <Button variant="outline" size="sm">Edit</Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export default AdminDashboard;
