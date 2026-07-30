import API_BASE from '../config';
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
import AdminFeedsPage from './admin/AdminFeedsPage';
import AdminBrokersPage from './admin/AdminBrokersPage';
import AdminSubscriptionsPage from './admin/AdminSubscriptionsPage';
// iter292 — LotsModeration is merged into ListingsModeration; the
// `?tab=lots` URL alias now renders the unified panel.
import ListingsModeration from './admin/ListingsModeration';
import FlaggedListingsTab from './admin/FlaggedListingsTab';
import ConversionFunnelDashboard from './admin/ConversionFunnelDashboard';
import DisputedSettlements from './admin/DisputedSettlements';
import ManageAllAuctions from './admin/ManageAllAuctions';
import DeletionRequestsManager from './admin/DeletionRequestsManager';
// iter288 — Listing change-request inbox (admin moderation triage).
import ListingRequestsManager from './admin/ListingRequestsManager';
import TaxVerificationQueue from './admin/TaxVerificationQueue';
import AuctionControl from './admin/AuctionControl';
import CategoryManager from './admin/CategoryManager';
import PromotionManager from './admin/PromotionManager';
import AffiliateManager from './admin/AffiliateManager';
import AdminAffiliatePayouts from './admin/AdminAffiliatePayouts';
// iter271 — External email campaigns (acquisition marketing)
import AdminExternalCampaigns from './admin/AdminExternalCampaigns';
import AdminUnsubscribeAudit from './admin/AdminUnsubscribeAudit';
import ReportManager from './admin/ReportManager';
import AnalyticsDashboard from './admin/AnalyticsDashboard';
// iter299 P2 — Advanced Analytics (GMV, revenue, usage charts)
import AdvancedAnalytics from './admin/AdvancedAnalytics';
import MessagingOversight from './admin/MessagingOversight';
import TrustSafetyDashboard from './admin/TrustSafetyDashboard';
import AnnouncementManager from './admin/AnnouncementManager';
import AdminBannerManager from '../components/AdminBannerManager';
import AdminLogs from './admin/AdminLogs';
import CurrencyAppealsManager from './admin/CurrencyAppealsManager';
import SubscriptionManager from './admin/SubscriptionManager';
import EmailTemplates from './admin/EmailTemplates';
import EmailMarketingManager from './admin/EmailMarketingManager';
import MarketplaceSettings from './admin/MarketplaceSettings';
import BrandingLayoutManager from './admin/BrandingLayoutManager';
import SiteContentManager from './admin/SiteContentManager';
import VehicleAdminManager from './admin/VehicleAdminManager';
import AdminDealerLicenses from './admin/AdminDealerLicenses';
// iter420 — Vehicle dealer & broker management (list / profile / activity)
import AdminVehicleDealersPage from './admin/AdminVehicleDealersPage';
import AdminBuyerVerifications from './admin/AdminBuyerVerifications';
import AdminComplianceAlerts from './admin/AdminComplianceAlerts';
// iter307 — single-page Compliance Dashboard
import AdminCompliancePage from './admin/AdminCompliancePage';
import AIGuardDashboard from './admin/AIGuardDashboard';
import RiskMonitoringDashboard from './admin/RiskMonitoringDashboard';
import PricingManager from './admin/PricingManager';
import PricingEnginePage from './admin/PricingEnginePage'; // iter210 Step 3
import DemoAccountsPage from './admin/DemoAccountsPage'; // iter210 Step 5
import CouponManager from './admin/CouponManager';
import AdminEscrowManager from './admin/AdminEscrowManager';
import SubscriptionAnalytics from './admin/SubscriptionAnalytics';
import SiteModeManager from './admin/SiteModeManager';
import PartnerManager from './admin/PartnerManager';
import FinanceDashboard from './admin/FinanceDashboard';
import AdminPaymentChargesPage from './admin/AdminPaymentChargesPage';
import EmailSettings from './admin/EmailSettings';
import SystemMonitoringDashboard from './admin/SystemMonitoringDashboard';
import PlatformCleanupManager from './admin/PlatformCleanupManager';
import CommunityModerationManager from './admin/CommunityModerationManager';
import TeamManager from '../components/admin/TeamManager';
// iter318 — Admin Careers console (lazy)
import { lazy as _lazyCareers, Suspense as _SuspenseCareers } from 'react';
import { extractErrorMessage } from '../utils/errorHandler';
const _AdminCareersConsole = _lazyCareers(() => import('./admin/AdminCareersConsole'));
const AdminCareersConsoleLazy = (props) => (
  <_SuspenseCareers fallback={<div className="p-8 text-center text-slate-500">Loading…</div>}>
    <_AdminCareersConsole {...props} />
  </_SuspenseCareers>
);
// iter320 — Admin Escalations console (lazy)
const _AdminEscalationsConsole = _lazyCareers(() => import('./admin/AdminEscalationsConsole'));
const AdminEscalationsConsoleLazy = (props) => (
  <_SuspenseCareers fallback={<div className="p-8 text-center text-slate-500">Loading…</div>}>
    <_AdminEscalationsConsole {...props} />
  </_SuspenseCareers>
);
// iter331 — Admin Blogs / Press console (lazy)
const _AdminBlogsConsole = _lazyCareers(() => import('./admin/AdminBlogsConsole'));
const AdminBlogsConsoleLazy = (props) => (
  <_SuspenseCareers fallback={<div className="p-8 text-center text-slate-500">Loading…</div>}>
    <_AdminBlogsConsole {...props} />
  </_SuspenseCareers>
);
// iter334 — Admin AI Voice Calls console (lazy)
const _AdminAIVoiceCalls = _lazyCareers(() => import('./admin/AdminAIVoiceCalls'));
const AdminAIVoiceCallsLazy = (props) => (
  <_SuspenseCareers fallback={<div className="p-8 text-center text-slate-500">Loading…</div>}>
    <_AdminAIVoiceCalls {...props} />
  </_SuspenseCareers>
);
// iter335 — Admin AI Coach Sessions (outbound silent coach) (lazy)
const _AdminAICoachSessions = _lazyCareers(() => import('./admin/AdminAICoachSessions'));
const AdminAICoachSessionsLazy = (props) => (
  <_SuspenseCareers fallback={<div className="p-8 text-center text-slate-500">Loading…</div>}>
    <_AdminAICoachSessions {...props} />
  </_SuspenseCareers>
);
// iter337 — Admin Ad Campaigns (Gemini-drafted ad copy + CSV export) (lazy)
const _AdminAdCampaigns = _lazyCareers(() => import('./admin/AdminAdCampaigns'));
const AdminAdCampaignsLazy = (props) => (
  <_SuspenseCareers fallback={<div className="p-8 text-center text-slate-500">Loading…</div>}>
    <_AdminAdCampaigns {...props} />
  </_SuspenseCareers>
);
// iter321 — Real-time escalation alerts (SSE + chime + desktop notification + tab flash)
import { EscalationAlertProvider, useEscalationAlerts } from '../components/admin/EscalationAlertProvider';
import { LifeBuoy } from 'lucide-react';
import AdminTaxDashboard from './AdminTaxDashboard';
import AdminStorageDeposits from './admin/AdminStorageDeposits';
import AdminStorageAuctions from './admin/AdminStorageAuctions';
import AdminFeatureFlags from './admin/AdminFeatureFlags';
import AdminFacilities from './admin/AdminFacilities';
import AdminMarketingIntegrations from './admin/AdminMarketingIntegrations';
// iter316 Phase B — Mission B5: Admin Contractor Management + Commission Rate Editor
import AdminContractorsPage from './admin/AdminContractorsPage';
import AdminContractorsLeaderboard from './admin/AdminContractorsLeaderboard';
import AdminDialer from './admin/AdminDialer';
import SchedulerStatusCard from '../components/SchedulerStatusCard';
// iter363 — Admin left sidebar (replaces horizontal PRIMARY/SECONDARY tabs).
import AdminSidebar from '../components/admin/AdminSidebar';
import { Menu as MenuIcon } from 'lucide-react';
// iter364 — Admin notification bell.
import NotificationBell from '../components/admin/NotificationBell';
import { 
  Users, Package, Gavel, Shield, TrendingUp, Bell, Settings, FileText, 
  MessageSquare, DollarSign, Search, Image, CreditCard, Megaphone, 
  Activity, AlertTriangle, ChevronRight, Power, Zap, Eye, History,
  ToggleLeft, ToggleRight, Clock, Mail, Sliders, Car, Send, Bot, Ticket, BarChart3, Globe, Building2, BarChart2, ShieldAlert, ShieldCheck, Lock, Inbox, Briefcase, LayoutTemplate
} from 'lucide-react';

const API = API_BASE;

// ========== PRIMARY NAVIGATION CATEGORIES ==========
const PRIMARY_TABS = [
  { id: 'marketplace', label: 'Marketplace', icon: '🛒', lucideIcon: Package },
  { id: 'vehicles', label: 'Vehicles', icon: '🚗', lucideIcon: Car },
  { id: 'dialer', label: 'Dialer & Contractors', icon: '📞', lucideIcon: Megaphone },
  { id: 'settings', label: 'Settings', icon: '⚙️', lucideIcon: Settings },
  { id: 'banners', label: 'Banners', icon: '🎨', lucideIcon: Image },
  { id: 'analytics', label: 'Analytics', icon: '📊', lucideIcon: TrendingUp },
  { id: 'partners-finance', label: 'Partners & Finance', icon: '💰', lucideIcon: Building2 },
  { id: 'team', label: 'Team', icon: '👥', lucideIcon: Users },
  { id: 'logs', label: 'Admin Logs', icon: '📋', lucideIcon: FileText },
];

// ========== SECONDARY NAVIGATION (Context-Specific) ==========
const SECONDARY_TABS = {
  marketplace: [
    { id: 'users', label: 'User Management', icon: '👥', lucideIcon: Users },
    // iter292 — Listings Moderation already aggregates single + multi (lots);
    // the standalone "Lots Moderation" tab was a stripped-down duplicate
    // and is now removed. Routes for ?tab=lots redirect transparently
    // to ?tab=listings-moderation (handled in renderContent below).
    { id: 'listings-moderation', label: 'Listings Moderation', icon: '🛡️', lucideIcon: Shield },
    { id: 'flagged-listings',    label: 'Flagged Listings (AI Review)', icon: '🤖', lucideIcon: ShieldAlert },
    { id: 'disputed-settlements', label: 'Disputed Settlements', icon: '⚠️', lucideIcon: Shield },
    { id: 'all-auctions', label: 'Manage All Auctions', icon: '🏛️', lucideIcon: Package },
    { id: 'deletion-requests', label: 'Deletion Requests', icon: '🗑️', lucideIcon: AlertTriangle },
    // iter288 — Per-listing change-request inbox (edit / delete triage)
    { id: 'listing-requests', label: 'Listing Change Requests', icon: '📝', lucideIcon: Inbox },
    { id: 'tax-verification', label: 'Tax Verification', icon: '🛡️', lucideIcon: Shield },
    { id: 'tax-dashboard', label: 'Tax Dashboard', icon: '📊', lucideIcon: BarChart2 },
    { id: 'auctions', label: 'Auction Control', icon: '🔨', lucideIcon: Gavel },
    { id: 'storage-deposits', label: 'Storage Deposits', icon: '💰', lucideIcon: DollarSign },
    { id: 'storage-auctions-admin', label: 'Storage Auctions', icon: '📦', lucideIcon: Package },
    { id: 'facilities', label: 'Facilities', icon: '🏢', lucideIcon: Package },
    { id: 'categories', label: 'Categories', icon: '📂', lucideIcon: Settings },
    { id: 'partner-applications', label: 'Partner Applications', icon: '🏢', lucideIcon: Building2 },
    // iter217 Phase 5 Hotfix v5b — Broker Ecosystem
    { id: 'brokers', label: 'Broker Management', icon: '🤝', lucideIcon: Building2 },
  ],
  vehicles: [
    { id: 'vehicle-admin', label: 'Vehicle Administration', icon: '🚗', lucideIcon: Car },
    // iter420 — Dealer & broker management (list / profile / activity)
    { id: 'dealer-management', label: 'Dealer Management', icon: '🏢', lucideIcon: Building2 },
    { id: 'dealer-licenses', label: 'Dealer Licenses', icon: '🪪', lucideIcon: ShieldAlert },
    { id: 'buyer-verifications', label: 'Buyer Verifications', icon: '🛂', lucideIcon: ShieldAlert },
    { id: 'compliance-alerts', label: 'Compliance Alerts', icon: '🚨', lucideIcon: AlertTriangle },
    // iter307 — Single-page Compliance Dashboard (5 sections)
    { id: 'compliance-dashboard', label: 'Compliance', icon: '🛡️', lucideIcon: ShieldAlert },
    { id: 'feature-flags', label: 'Feature Flags', icon: '🚩', lucideIcon: Car },
    { id: 'ai-guard', label: 'AI Guard', icon: '🤖', lucideIcon: Bot },
    { id: 'risk-monitoring', label: 'Risk Monitoring', icon: '🔴', lucideIcon: ShieldAlert },
  ],
  // iter316 Phase B — Dialer + Contractor commission management
  dialer: [
    { id: 'dialer-ui', label: 'Dialer', icon: '📞', lucideIcon: Megaphone },
    { id: 'contractors', label: 'Contractor Management', icon: '👤', lucideIcon: Users },
    { id: 'leaderboard', label: 'Leaderboard', icon: '🏆', lucideIcon: TrendingUp },
  ],
  settings: [
    { id: 'site-mode', label: 'Site Mode', icon: '🌐', lucideIcon: Globe },
    { id: 'site-content', label: 'Site Content & Pages', icon: '📄', lucideIcon: FileText },
    { id: 'branding-layout', label: 'Branding & Layout', icon: '🎨', lucideIcon: Settings },
    { id: 'marketplace-settings', label: 'Marketplace Settings', icon: '⚙️', lucideIcon: Sliders },
    { id: 'subscriptions', label: 'Subscriptions', icon: '💎', lucideIcon: CreditCard },
    { id: 'broker-subscriptions', label: 'Broker Subscriptions', icon: '🤝💎', lucideIcon: CreditCard },
    { id: 'subscription-analytics', label: 'Subscription Analytics', icon: '📊', lucideIcon: BarChart3 },
    { id: 'pricing-engine', label: 'Pricing Engine (Tiers)', icon: '💰', lucideIcon: DollarSign },
    { id: 'pricing-engine-v2', label: 'Pricing Engine (Subs)', icon: '💵', lucideIcon: DollarSign },
    { id: 'demo-accounts', label: 'Demo Accounts', icon: '🎭', lucideIcon: DollarSign },
    { id: 'coupon-codes', label: 'Coupon Codes', icon: '🎟️', lucideIcon: Ticket },
    { id: 'email-marketing', label: 'Email Marketing', icon: '📤', lucideIcon: Send },
    // iter271 — External acquisition campaigns
    { id: 'external-campaigns', label: 'External Campaigns', icon: '📬', lucideIcon: Send },
    // iter310 — Unsubscribe deliverability monitor
    { id: 'unsubscribe-audit', label: 'Unsubscribe Audit', icon: '📉', lucideIcon: Send },
    { id: 'marketing-integrations', label: 'Marketing Integrations', icon: '📣', lucideIcon: Send },
    { id: 'trust-safety', label: 'Trust & Safety', icon: '🛡️', lucideIcon: Shield },
    { id: 'escrow-manager', label: 'Escrow & Penalties', icon: '🔒', lucideIcon: Lock },
    { id: 'community-moderation', label: 'Community Moderation', icon: '💬', lucideIcon: MessageSquare },
    { id: 'platform-cleanup', label: 'Platform Cleanup', icon: '🧹', lucideIcon: AlertTriangle },
    { id: 'email-templates', label: 'Email Templates', icon: '📧', lucideIcon: Mail },
  ],
  banners: [
    { id: 'banner-manager', label: 'Banner Manager', icon: '🖼️', lucideIcon: Image },
    { id: 'announcements', label: 'Announcements', icon: '📢', lucideIcon: Bell },
  ],
  analytics: [
    { id: 'dashboard', label: 'Dashboard', icon: '📈', lucideIcon: TrendingUp },
    // iter299 P2 — GMV / revenue / usage deep-dive
    { id: 'advanced-analytics', label: 'Advanced Analytics', icon: '📊', lucideIcon: BarChart3 },
    { id: 'conversion-funnel', label: 'Conversion Funnel', icon: '🪜', lucideIcon: TrendingUp },
    { id: 'reports', label: 'Reports', icon: '📑', lucideIcon: FileText },
    { id: 'system-monitoring', label: 'System Monitoring', icon: '🔧', lucideIcon: Activity },
  ],
  'partners-finance': [
    { id: 'finance-overview', label: 'Finance Dashboard', icon: '📊', lucideIcon: TrendingUp },
    { id: 'payment-charges', label: 'Strict Payment Charges', icon: '🔒', lucideIcon: Lock },
    { id: 'email-settings', label: 'Email Settings', icon: '✉️', lucideIcon: Mail },
  ],
  team: [
    { id: 'team-members', label: 'Team Members & Invites', icon: '👥', lucideIcon: Users },
    { id: 'careers', label: 'Careers', icon: '💼', lucideIcon: Briefcase },
    { id: 'escalations', label: 'Live Support', icon: '🆘', lucideIcon: Briefcase },
    { id: 'press-blogs', label: 'Press / Blog', icon: '📰', lucideIcon: FileText },
    { id: 'ai-voice-calls', label: 'AI Voice Calls', icon: '🎙️', lucideIcon: Users },
    { id: 'ai-coach-sessions', label: 'AI Coach Sessions', icon: '🤖', lucideIcon: Users },
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
  // iter266 Mission 1 — Affiliate payouts oversight tab
  { id: 'affiliate-payouts', label: 'Affiliate Payouts', icon: '💰', lucideIcon: DollarSign },
  // iter217 Phase 5 — Meta Ad Feeds
  { id: 'ad-feeds', label: 'Ad Feeds', icon: '📡', lucideIcon: Megaphone },
  // iter337 — Gemini-drafted per-listing ad copy for Google + Meta.
  { id: 'ad-campaigns', label: 'Ad Campaigns', icon: '📢', lucideIcon: Megaphone },
  // iter374 — Admin Landing Page Builder (dedicated route)
  { id: 'landing-pages', label: 'Landing Pages', icon: '🧩', lucideIcon: LayoutTemplate, route: '/admin/landing-pages' },
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
  // iter363 — mobile sidebar visibility (drawer on <lg screens).
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Phase 6.0 / Repair 2 — read ?tab= from URL on mount + activate the
  // matching secondary tab (incl. cross-primary-section routing). Also
  // honour the explicit `/admin/flagged-listings` route alias.
  React.useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      let tab = params.get('tab');
      // Route alias /admin/flagged-listings → force the flagged-listings tab.
      if (!tab && window.location.pathname.endsWith('/flagged-listings')) {
        tab = 'flagged-listings';
      }
      if (!tab) return;
      const SECONDARY_TO_PRIMARY = {
        'flagged-listings':   'marketplace',
        'listings-moderation': 'marketplace',
        'lots':               'marketplace',
        'conversion-funnel':  'analytics',
        'advanced-analytics': 'analytics',
        'dashboard':          'analytics',
        'reports':            'analytics',
        'system-monitoring':  'analytics',
        // iter321 — deep-link to Live Support tab
        'escalations':        'team',
        // iter336 — deep-link into the Team → AI Coach Sessions tab so
        // the ContractorEmailHub "Regenerate" link opens the correct
        // primary + secondary tabs (and the row auto-expands via router state).
        'ai-coach-sessions':  'team',
        'ai-voice-calls':     'team',
        'careers':            'team',
        'press-blogs':        'team',
        'team-members':       'team',
      };
      const inferredPrimary = SECONDARY_TO_PRIMARY[tab];
      if (inferredPrimary) setPrimaryTab(inferredPrimary);
      setSecondaryTab(tab);
    } catch { /* noop */ }
  }, []);
  
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

  // iter196 — Pending dealer license count for red-dot badge + home card
  const [pendingDealerLicenses, setPendingDealerLicenses] = useState(0);
  // iter197 — Triage counters for the Admin Home (hidden when 0)
  const [pendingDisputes, setPendingDisputes] = useState(0);
  const [pendingCurrencyAppeals, setPendingCurrencyAppeals] = useState(0);
  // iter201 Phase 3 — Compliance alerts KPI (expired/expiring licences + high-fraud + unreviewed)
  const [pendingComplianceAlerts, setPendingComplianceAlerts] = useState(0);
  // iter203 — Compliance Health traffic-light KPI (vehicle gate / AI scanner / watchdog)
  const [complianceHealth, setComplianceHealth] = useState(null);

  useEffect(() => {
    if (!user || !token) return;
    const fetchPendingCount = async () => {
      try {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/admin/dealer-licenses?status=pending`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const d = await res.json();
          setPendingDealerLicenses(d.total || 0);
        }
      } catch (_) {}
    };
    const fetchTriageCounts = async () => {
      const headers = { Authorization: `Bearer ${token}` };
      const root = process.env.REACT_APP_BACKEND_URL;
      try {
        const r = await fetch(`${root}/api/admin/vehicles/disputed-settlements/count`, { headers });
        if (r.ok) {
          const d = await r.json();
          setPendingDisputes(d.total || 0);
        }
      } catch (_) {}
      try {
        const r = await fetch(`${root}/api/admin/currency-appeals/pending-count`, { headers });
        if (r.ok) {
          const d = await r.json();
          setPendingCurrencyAppeals(d.total || 0);
        }
      } catch (_) {}
      try {
        const r = await fetch(`${root}/api/admin/compliance-alerts/count`, { headers });
        if (r.ok) {
          const d = await r.json();
          setPendingComplianceAlerts(d.total || 0);
        }
      } catch (_) {}
      // iter203 — Compliance Health KPI traffic light
      try {
        const r = await fetch(`${root}/api/admin/compliance/health`, { headers });
        if (r.ok) {
          const d = await r.json();
          setComplianceHealth(d || null);
        }
      } catch (_) {}
    };
    fetchPendingCount();
    fetchTriageCounts();
    const id = setInterval(() => {
      fetchPendingCount();
      fetchTriageCounts();
    }, 60000); // 1 min refresh
    return () => clearInterval(id);
  }, [user, token]);

  useEffect(() => {
    if (!user) {
      navigate('/auth');
      return;
    }

    const isAdmin = user.role === 'admin' || 
                    user.role === 'super_admin' ||
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

  // Update secondary tab when primary changes — but respect any ?tab= override.
  // iter301 — cross-cutting tabs (Marketing/Financial groups) live outside the
  // SECONDARY_TABS map; honour them on deep-link (?tab=messaging etc.). The
  // param is cleared when the user manually picks a primary tab (see onClick),
  // so this stays StrictMode-safe without one-shot refs.
  useEffect(() => {
    const secondaryOptions = SECONDARY_TABS[primaryTab];
    if (!secondaryOptions || secondaryOptions.length === 0) return;
    let urlTab = null;
    try { urlTab = new URLSearchParams(window.location.search).get('tab'); } catch { /* noop */ }
    // If the URL specifies a tab that exists under the current primary, keep it.
    if (urlTab && secondaryOptions.some((t) => t.id === urlTab)) {
      setSecondaryTab(urlTab);
      return;
    }
    // Cross-cutting deep-link (e.g. /admin?tab=messaging) — keep it active.
    if (urlTab && [...MARKETING_TABS, ...FINANCIAL_TABS].some((t) => t.id === urlTab)) {
      setSecondaryTab(urlTab);
      return;
    }
    setSecondaryTab(secondaryOptions[0].id);
  }, [primaryTab]);

  // iter301 — manual primary-tab navigation clears any ?tab= deep-link so the
  // effect above falls back to the primary's default subtab.
  const handlePrimaryTabClick = (tabId) => {
    try {
      const u = new URL(window.location.href);
      if (u.searchParams.has('tab')) {
        u.searchParams.delete('tab');
        window.history.replaceState({}, '', u.toString());
      }
    } catch { /* noop */ }
    if (tabId === primaryTab) {
      const opts = SECONDARY_TABS[tabId];
      if (opts && opts.length > 0) setSecondaryTab(opts[0].id);
    } else {
      setPrimaryTab(tabId);
    }
  };

  // Scroll to top when navigating between admin tabs
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [primaryTab, secondaryTab]);

  const fetchDashboardStats = async () => {
    try {
      const [usersRes, listingsRes, revenueRes] = await Promise.all([
        axios.get(`${API}/admin/users?limit=1`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/admin/analytics`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/admin/analytics/revenue`, { headers: { Authorization: `Bearer ${token}` } })
      ]);

      setStats({
        totalUsers: usersRes.data.total || 0,
        totalListings: listingsRes.data.active_listings || 0,
        activeAuctions: listingsRes.data.active_listings || 0,
        revenue: revenueRes.data.total_gmv || 0
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
          description: extractErrorMessage(error) || 'Please try again.',
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
    // iter266 Mission 1 — Affiliate payouts oversight tab
    if (secondaryTab === 'affiliate-payouts') return <AdminAffiliatePayouts />;
    if (secondaryTab === 'currency-appeals') return <CurrencyAppealsManager />;
    if (secondaryTab === 'messaging') return <MessagingOversight />;
    // iter217 Phase 5 — Meta Ad Feeds health dashboard
    if (secondaryTab === 'ad-feeds') return <AdminFeedsPage />;
    // iter337 — Gemini-drafted ad campaigns (per-listing copy + CSV export)
    if (secondaryTab === 'ad-campaigns') return <AdminAdCampaignsLazy />;

    // Primary tab specific content
    switch (primaryTab) {
      case 'marketplace':
        switch (secondaryTab) {
          case 'users': return <EnhancedUserManager />;
          case 'listings-moderation': return <ListingsModeration />;
          case 'flagged-listings': return <FlaggedListingsTab />;
          case 'disputed-settlements': return <DisputedSettlements />;
          // iter292 — `?tab=lots` is a legacy alias. Listings Moderation
          // already aggregates single + multi pending listings (lots);
          // route both URLs to the unified UI.
          case 'lots': return <ListingsModeration />;
          case 'all-auctions': return <ManageAllAuctions />;
          case 'deletion-requests': return <DeletionRequestsManager />;
          // iter288 — New listing-change request triage queue
          case 'listing-requests': return <ListingRequestsManager />;
          case 'tax-verification': return <TaxVerificationQueue />;
          case 'tax-dashboard': return <AdminTaxDashboard />;
          case 'auctions': return <AuctionControl />;
          case 'storage-deposits': return <AdminStorageDeposits />;
          case 'storage-auctions-admin': return <AdminStorageAuctions />;
          case 'facilities': return <AdminFacilities />;
          case 'categories': return <CategoryManager />;
          case 'partner-applications': return <PartnerManager />;
          case 'brokers': return <AdminBrokersPage />;
          default: return <EnhancedUserManager />;
        }
      case 'vehicles':
        switch (secondaryTab) {
          case 'vehicle-admin': return <VehicleAdminManager />;
          case 'dealer-management': return <AdminVehicleDealersPage />;
          case 'dealer-licenses': return <AdminDealerLicenses />;
          case 'buyer-verifications': return <AdminBuyerVerifications />;
          case 'compliance-alerts': return <AdminComplianceAlerts />;
          case 'compliance-dashboard': return <AdminCompliancePage />;
          case 'feature-flags': return <AdminFeatureFlags />;
          case 'ai-guard': return <AIGuardDashboard />;
          case 'risk-monitoring': return <RiskMonitoringDashboard />;
          default: return <VehicleAdminManager />;
        }
      case 'dialer':
        switch (secondaryTab) {
          case 'dialer-ui': return <AdminDialer />;
          case 'contractors': return <AdminContractorsPage />;
          case 'leaderboard': return <AdminContractorsLeaderboard />;
          default: return <AdminDialer />;
        }
      case 'settings':
        switch (secondaryTab) {
          case 'site-mode': return <SiteModeManager />;
          case 'site-content': return <SiteContentManager />;
          case 'branding-layout': return <BrandingLayoutManager />;
          case 'marketplace-settings': return <MarketplaceSettings />;
          case 'subscriptions': return <SubscriptionManager />;
          case 'subscription-analytics': return <SubscriptionAnalytics />;
          case 'pricing-engine': return <PricingManager />;
          case 'pricing-engine-v2': return <PricingEnginePage />;
          case 'demo-accounts': return <DemoAccountsPage />;
          case 'coupon-codes': return <CouponManager />;
          case 'email-marketing': return <EmailMarketingManager />;
          // iter271 — External acquisition campaigns
          case 'external-campaigns': return <AdminExternalCampaigns />;
          // iter310 — Unsubscribe Audit Trail
          case 'unsubscribe-audit': return <AdminUnsubscribeAudit />;
          case 'marketing-integrations': return <AdminMarketingIntegrations />;
          case 'trust-safety': return <TrustSafetyDashboard />;
          case 'escrow-manager': return <AdminEscrowManager />;
          case 'community-moderation': return <CommunityModerationManager />;
          case 'platform-cleanup': return <PlatformCleanupManager />;
          case 'email-templates': return <EmailTemplates />;
          default: return <SiteModeManager />;
        }
      case 'banners':
        switch (secondaryTab) {
          case 'banner-manager': return <AdminBannerManager />;
          case 'announcements': return <AnnouncementManager />;
          default: return <AdminBannerManager />;
        }
      case 'analytics':
        switch (secondaryTab) {
          case 'dashboard': return <AnalyticsDashboard />;
          case 'advanced-analytics': return <AdvancedAnalytics />;
          case 'conversion-funnel': return <ConversionFunnelDashboard />;
          case 'reports': return <ReportManager />;
          case 'system-monitoring': return <SystemMonitoringDashboard />;
          default: return <AnalyticsDashboard />;
        }
      case 'partners-finance':
        switch (secondaryTab) {
          case 'email-settings': return <EmailSettings />;
          case 'payment-charges': return <AdminPaymentChargesPage />;
          default: return <FinanceDashboard />;
        }
      case 'team':
        if (secondaryTab === 'careers') {
          return <AdminCareersConsoleLazy />;
        }
        if (secondaryTab === 'escalations') {
          return <AdminEscalationsConsoleLazy />;
        }
        if (secondaryTab === 'press-blogs') {
          return <AdminBlogsConsoleLazy />;
        }
        if (secondaryTab === 'ai-voice-calls') {
          return <AdminAIVoiceCallsLazy />;
        }
        if (secondaryTab === 'ai-coach-sessions') {
          return <AdminAICoachSessionsLazy />;
        }
        return <TeamManager />;
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
        <div className="max-w-full mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* iter363 — mobile hamburger to open the sidebar drawer */}
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden p-2 -ml-2 rounded-lg hover:bg-slate-100"
                aria-label="Open admin menu"
                data-testid="admin-sidebar-open"
              >
                <MenuIcon className="h-6 w-6 text-slate-700" />
              </button>
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
                {user.role === 'super_admin' ? '👑 Super Admin' : '⚡ Admin'}
              </Badge>
              {/* iter364 — Notification bell (60s poll, dropdown with category counts) */}
              <NotificationBell
                token={token}
                lang={typeof navigator !== 'undefined' && navigator.language?.startsWith('fr') ? 'fr' : 'en'}
                onNavigate={(dest) => {
                  handlePrimaryTabClick(dest.primary);
                  if (dest.secondary) setSecondaryTab(dest.secondary);
                }}
              />
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
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7">
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
            {/* iter321 — Live Support card (always visible, pulses red when open_count > 0) */}
            <LiveSupportStatCard
              onOpen={() => { setPrimaryTab('team'); setSecondaryTab('escalations'); }}
            />
            {pendingDealerLicenses > 0 && (
              <button
                type="button"
                onClick={() => { setPrimaryTab('vehicles'); setSecondaryTab('dealer-licenses'); }}
                className="flex items-center gap-3 p-3 bg-red-50 hover:bg-red-100 rounded-lg ring-2 ring-red-300 transition-all text-left animate-pulse"
                data-testid="admin-pending-reviews-card"
                title="Click to review pending dealer licenses"
              >
                <ShieldAlert className="h-8 w-8 text-red-600" />
                <div>
                  <p className="text-2xl font-bold text-red-700" data-testid="admin-pending-reviews-count">
                    {pendingDealerLicenses.toLocaleString()}
                  </p>
                  <p className="text-xs text-red-600 font-medium">Pending Reviews</p>
                </div>
              </button>
            )}
            {pendingDisputes > 0 && (
              <button
                type="button"
                onClick={() => { setPrimaryTab('marketplace'); setSecondaryTab('disputed-settlements'); }}
                className="flex items-center gap-3 p-3 bg-orange-50 hover:bg-orange-100 rounded-lg ring-2 ring-orange-300 transition-all text-left animate-pulse"
                data-testid="admin-pending-disputes-card"
                title="Click to review disputed settlements"
              >
                <AlertTriangle className="h-8 w-8 text-orange-600" />
                <div>
                  <p className="text-2xl font-bold text-orange-700" data-testid="admin-pending-disputes-count">
                    {pendingDisputes.toLocaleString()}
                  </p>
                  <p className="text-xs text-orange-600 font-medium">Disputes</p>
                </div>
              </button>
            )}
            {pendingCurrencyAppeals > 0 && (
              <button
                type="button"
                onClick={() => { setSecondaryTab('currency-appeals'); }}
                className="flex items-center gap-3 p-3 bg-yellow-50 hover:bg-yellow-100 rounded-lg ring-2 ring-yellow-300 transition-all text-left animate-pulse"
                data-testid="admin-pending-appeals-card"
                title="Click to review currency appeals"
              >
                <DollarSign className="h-8 w-8 text-yellow-600" />
                <div>
                  <p className="text-2xl font-bold text-yellow-700" data-testid="admin-pending-appeals-count">
                    {pendingCurrencyAppeals.toLocaleString()}
                  </p>
                  <p className="text-xs text-yellow-600 font-medium">Currency Appeals</p>
                </div>
              </button>
            )}
            {pendingComplianceAlerts > 0 && (
              <button
                type="button"
                onClick={() => { setPrimaryTab('vehicles'); setSecondaryTab('compliance-alerts'); }}
                className="flex items-center gap-3 p-3 bg-rose-50 hover:bg-rose-100 rounded-lg ring-2 ring-rose-400 transition-all text-left animate-pulse"
                data-testid="admin-compliance-alerts-card"
                title="Click to review compliance alerts"
              >
                <ShieldAlert className="h-8 w-8 text-rose-600" />
                <div>
                  <p className="text-2xl font-bold text-rose-700" data-testid="admin-compliance-alerts-count">
                    {pendingComplianceAlerts.toLocaleString()}
                  </p>
                  <p className="text-xs text-rose-600 font-medium">Compliance Alerts</p>
                </div>
              </button>
            )}
            {/* iter203 — Compliance Health KPI traffic light (always visible) */}
            {complianceHealth && (() => {
              const s = complianceHealth.status || 'green';
              const palette = {
                green:  { bg: 'bg-emerald-50 hover:bg-emerald-100', ring: 'ring-emerald-300', icon: 'text-emerald-600', label: 'text-emerald-700', dot: 'bg-emerald-500' },
                yellow: { bg: 'bg-amber-50 hover:bg-amber-100',     ring: 'ring-amber-400',   icon: 'text-amber-600',   label: 'text-amber-700',   dot: 'bg-amber-500' },
                red:    { bg: 'bg-rose-50 hover:bg-rose-100',       ring: 'ring-rose-500',    icon: 'text-rose-600',    label: 'text-rose-700',    dot: 'bg-rose-500 animate-pulse' },
              }[s];
              const tooltip = (complianceHealth.status_reasons || []).join(' • ');
              return (
                <button
                  type="button"
                  onClick={() => { setPrimaryTab('vehicles'); setSecondaryTab('compliance-alerts'); }}
                  className={`flex items-center gap-3 p-3 ${palette.bg} rounded-lg ring-2 ${palette.ring} transition-all text-left`}
                  data-testid="admin-compliance-health-card"
                  data-status={s}
                  title={`Compliance Health: ${s.toUpperCase()} — ${tooltip}`}
                >
                  <div className="relative">
                    <ShieldCheck className={`h-8 w-8 ${palette.icon}`} />
                    <span className={`absolute -top-1 -right-1 inline-block w-3 h-3 rounded-full ${palette.dot} ring-2 ring-white`} />
                  </div>
                  <div className="min-w-0">
                    <p className={`text-base font-bold ${palette.label} uppercase tracking-wide leading-tight`} data-testid="admin-compliance-health-status">
                      {s === 'green' ? 'All clear' : s === 'yellow' ? 'Watch' : 'Action required'}
                    </p>
                    <p className="text-[11px] text-slate-600 leading-tight truncate max-w-[180px]">
                      {(complianceHealth.pending_review || 0) === 0
                        ? `Watchdog: ${complianceHealth.minutes_since_last_watchdog ?? '—'} min ago`
                        : `${complianceHealth.pending_review} pending review`}
                    </p>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Today: {complianceHealth.blocked_today || 0} blocked · {(complianceHealth.paused_by_ai_today || 0) + (complianceHealth.paused_by_watchdog_today || 0)} paused
                    </p>
                  </div>
                </button>
              );
            })()}
          </div>
        </div>
      </div>

      {/* iter363 — Sidebar layout replaces the old horizontal PRIMARY /
          CROSS-CUTTING / SECONDARY tab strips. The AdminSidebar keeps
          the same 4 groupings (primary sections, per-primary secondary,
          marketing cross-cutting, finance & safety cross-cutting) but
          renders them as a professional left rail with a mobile drawer. */}
      <div className="flex" data-testid="admin-shell">
        <AdminSidebar
          primaryTabs={PRIMARY_TABS}
          secondaryTabs={SECONDARY_TABS}
          marketingTabs={MARKETING_TABS}
          financialTabs={FINANCIAL_TABS}
          primaryTab={primaryTab}
          secondaryTab={secondaryTab}
          onPrimaryClick={(id) => { handlePrimaryTabClick(id); setSidebarOpen(false); }}
          onSecondaryClick={(id) => {
            // iter374 — Marketing/Finance tabs may carry a `route` field
            // (e.g. Landing Pages → /admin/landing-pages). Navigate
            // directly instead of trying to render inline.
            const found = [...MARKETING_TABS, ...FINANCIAL_TABS].find((t) => t.id === id);
            if (found?.route) {
              navigate(found.route);
              setSidebarOpen(false);
              return;
            }
            setSecondaryTab(id);
            setSidebarOpen(false);
          }}
          pendingDealerLicenses={pendingDealerLicenses}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        {/* Main Content Area */}
        <main className="flex-1 min-w-0 px-4 lg:px-6 py-6">
          <div className={`${liveControlsOpen ? 'mr-80' : ''}`}>
            {/* Scheduler Status — production health card */}
            <div className="mb-6">
              <SchedulerStatusCard token={token} />
            </div>
            {renderContent()}
          </div>
        </main>
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
                liveAuditLog.map((log, idx) => (
                  <div key={log.id || `${log.timestamp || idx}-${log.setting || ''}`} className="bg-gray-50 rounded-lg p-2 text-xs">
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


// ─── iter321 — Live Support stat card (consumes the SSE provider) ──────
function LiveSupportStatCard({ onOpen }) {
  const { openCount, connected, enableSound, setEnableSound, acknowledgeAll } = useEscalationAlerts();
  const hasOpen = openCount > 0;
  return (
    <button
      type="button"
      onClick={() => { acknowledgeAll(); onOpen?.(); }}
      className={`flex items-center gap-3 p-3 rounded-lg text-left transition-all ring-2 ${
        hasOpen
          ? 'bg-rose-50 hover:bg-rose-100 ring-rose-400 animate-pulse'
          : 'bg-emerald-50 hover:bg-emerald-100 ring-emerald-300'
      }`}
      data-testid="admin-live-support-card"
      title={hasOpen
        ? `${openCount} open Live Support ticket${openCount > 1 ? 's' : ''} — click to view`
        : 'Live Support — all clear'}
    >
      <div className="relative">
        <LifeBuoy className={`h-8 w-8 ${hasOpen ? 'text-rose-600' : 'text-emerald-600'}`} />
        <span
          className={`absolute -top-1 -right-1 inline-block w-3 h-3 rounded-full ring-2 ring-white ${
            connected ? 'bg-emerald-500' : 'bg-slate-400'
          }`}
          title={connected ? 'Real-time alerts ON' : 'Reconnecting…'}
        />
      </div>
      <div className="min-w-0">
        <p
          className={`text-2xl font-bold leading-tight ${hasOpen ? 'text-rose-700' : 'text-emerald-700'}`}
          data-testid="admin-live-support-count"
        >
          {openCount}
        </p>
        <p className={`text-xs font-medium ${hasOpen ? 'text-rose-600' : 'text-emerald-600'}`}>
          {hasOpen ? 'Open Tickets' : 'Live Support'}
        </p>
        <p
          className="text-[10px] text-slate-500 leading-tight cursor-pointer hover:underline"
          onClick={(e) => {
            e.stopPropagation();
            setEnableSound(!enableSound);
          }}
          data-testid="admin-live-support-sound-toggle"
        >
          🔔 Sound: {enableSound ? 'ON' : 'OFF'}
        </p>
      </div>
    </button>
  );
}


// ─── iter321 — Outer wrapper mounts the EscalationAlertProvider so the
//    SSE connection lives for the entire Admin Dashboard tree and the
//    LiveSupportStatCard can consume the live open_count. ───────────
function InnerAdminEscalationListener({ onNavigate }) {
  // Listen for the global `bidvex:open-escalations` custom event fired by
  // the toast "View" CTA — admin clicks anywhere in the app and lands on
  // the Live Support tab.
  React.useEffect(() => {
    const handler = () => { onNavigate?.(); };
    window.addEventListener('bidvex:open-escalations', handler);
    return () => window.removeEventListener('bidvex:open-escalations', handler);
  }, [onNavigate]);
  return null;
}


function AdminDashboardWithAlerts() {
  // Bridge: the toast "View" CTA wants to navigate to the escalations tab.
  // Since AdminDashboard owns the primaryTab/secondaryTab state, we route
  // via window.history + a re-mount trigger.
  const onNavigate = React.useCallback(() => {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('tab', 'escalations');
      window.history.replaceState({}, '', url.toString());
      // Trigger AdminDashboard's deep-link useEffect re-eval by dispatching
      // a hashchange — but easier: just full-reload to the escalations tab.
      window.location.search = '?tab=escalations';
    } catch { /* noop */ }
  }, []);

  return (
    <EscalationAlertProvider>
      <InnerAdminEscalationListener onNavigate={onNavigate} />
      <AdminDashboard />
    </EscalationAlertProvider>
  );
}


export default AdminDashboardWithAlerts;
