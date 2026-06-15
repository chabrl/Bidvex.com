import React, { Suspense, lazy, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useTranslation, I18nextProvider } from 'react-i18next';
import i18n from './i18n';
import { useAuth } from './contexts/AuthContext';
import { FeatureFlagsProvider } from './contexts/FeatureFlagsContext';
import { SiteConfigProvider } from './contexts/SiteConfigContext';
import { CurrencyProvider } from './contexts/CurrencyContext';
import { SiteModeProvider, useSiteMode } from './contexts/SiteModeContext';
import { PromoBannerProvider } from './contexts/PromoBannerContext';
import { Toaster } from './components/ui/sonner';
import { HelmetProvider } from 'react-helmet-async';
// iter268 Mission 3 — Catch any route-level render crash and show a friendly
// retry/home UI instead of a blank screen.
import ErrorBoundary from './components/ErrorBoundary';
// iter272 — Campaign attribution lifecycle helper.
import { captureCampaignTracking } from './lib/campaignTracking';

// Shell components — kept eager (always visible on every page)
import Navbar from './components/Navbar';
// iter243 Mission 1 — Platform-wide promotional banner.
import PromotionalBanner from './components/PromotionalBanner';
import GlobalDealerFeeBanner from './components/GlobalDealerFeeBanner';
import Footer from './components/Footer';
import TrendyAnnouncementBar from './components/TrendyAnnouncementBar';
import MobileBottomNav from './components/MobileBottomNav';
import ScrollToTop from './components/ScrollToTop';
import FbPixelTracker from './components/FbPixelTracker';
import MarketingPixelLoader from './components/MarketingPixelLoader';
import CookieConsentBanner from './components/CookieConsentBanner';
import MessageNotificationListener from './components/MessageNotificationListener';

import { registerServiceWorker } from './utils/pushNotifications';
import './App.css';

// ─── Lazy-loaded pages (route-level code splitting) ───────────────
const HomePage = lazy(() => import('./pages/HomePage'));
const MarketplacePage = lazy(() => import('./pages/MarketplacePage'));
const ListingDetailPage = lazy(() => import('./pages/ListingDetailPage'));
const AuthPage = lazy(() => import('./pages/AuthPage'));
const SellerDashboard = lazy(() => import('./pages/SellerDashboard'));
const GoogleAuthFinishPage = lazy(() => import('./pages/GoogleAuthFinishPage'));
const BuyerDashboard = lazy(() => import('./pages/BuyerDashboard'));
const CreateListingPage = lazy(() => import('./pages/CreateListingPage'));
const PaymentSuccessPage = lazy(() => import('./pages/PaymentSuccessPage'));
const ProfileSettingsPage = lazy(() => import('./pages/ProfileSettingsPage'));
const AffiliateDashboard = lazy(() => import('./pages/AffiliateDashboard'));
const MessagesPage = lazy(() => import('./pages/MessagesPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const CreateMultiItemListing = lazy(() => import('./pages/CreateMultiItemListing'));
const LotsMarketplacePage = lazy(() => import('./pages/LotsMarketplacePage'));
const MultiItemListingDetailPage = lazy(() => import('./pages/MultiItemListingDetailPage'));
const ItemsMarketplacePage = lazy(() => import('./pages/ItemsMarketplacePage'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const AdminTaxDashboard = lazy(() => import('./pages/AdminTaxDashboard'));
// iter217 Phase 5 Hotfix v5b — Broker Ecosystem
const AdminBrokersPage = lazy(() => import('./pages/admin/AdminBrokersPage'));
// iter217 Phase 5 Hotfix v6.5 — Admin Subscription Management
const AdminSubscriptionsPage = lazy(() => import('./pages/admin/AdminSubscriptionsPage'));
const StorageHoldSettlementsTab = lazy(() => import('./pages/admin/StorageHoldSettlementsTab'));
// iter217 Phase 5 Hotfix v7 — Public bilingual "How Brokers Work" landing page
const HowBrokersWorkPage = lazy(() => import('./pages/HowBrokersWorkPage'));
// iter217 Phase 5 Hotfix v8.1 — Token-secured buyer transaction receipt
const MyReceiptPage = lazy(() => import('./pages/MyReceiptPage'));
const BecomeABrokerPage = lazy(() => import('./pages/BecomeABrokerPage'));
const BrokerDirectoryPage = lazy(() => import('./pages/BrokerDirectoryPage'));
const BrokerBindingRequestPage = lazy(() => import('./pages/BrokerBindingRequestPage'));
const BrokerDashboardPage = lazy(() => import('./pages/BrokerDashboardPage'));
const WatchlistPage = lazy(() => import('./pages/WatchlistPage'));
const HowItWorksPage = lazy(() => import('./pages/HowItWorksPage'));
const SellerProfilePage = lazy(() => import('./pages/SellerProfilePage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const PrivacyPolicyPage = lazy(() => import('./pages/PrivacyPolicyPage'));
const TermsOfServicePage = lazy(() => import('./pages/TermsOfServicePage'));
const RefundPolicyPage = lazy(() => import('./pages/RefundPolicyPage'));
const ContactUsPage = lazy(() => import('./pages/ContactUsPage'));
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));

// ── Storage Unit Auctions (iteration 169) ──
const StorageAuctionsBrowse = lazy(() => import('./pages/storage/StorageAuctionsBrowse'));
const StorageAuctionDetail = lazy(() => import('./pages/storage/StorageAuctionDetail'));
const StorageFacilityRegister = lazy(() => import('./pages/storage/StorageFacilityRegister'));
const MyStorageDeposits = lazy(() => import('./pages/storage/MyStorageDeposits'));
const StorageDashboard = lazy(() => import('./pages/storage/StorageDashboard'));
const MyCleanoutsPage = lazy(() => import('./pages/storage/MyCleanoutsPage'));
const FacilityDashboard = lazy(() => import('./pages/facility/FacilityDashboard'));
const FacilityPublicProfile = lazy(() => import('./pages/facility/FacilityPublicProfile'));
const StorageAuctionCreate = lazy(() => import('./pages/storage/StorageAuctionCreate'));
const StorageHowItWorks = lazy(() => import('./pages/storage/StoragePolicies').then(m => ({ default: m.HowItWorks })));
const StorageTerms = lazy(() => import('./pages/storage/StoragePolicies').then(m => ({ default: m.StorageTerms })));
const StorageForFacilities = lazy(() => import('./pages/storage/StoragePolicies').then(m => ({ default: m.StorageForFacilities })));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));
const PhoneVerificationPage = lazy(() => import('./pages/PhoneVerificationPage'));
const ClientEmailMarketing = lazy(() => import('./pages/ClientEmailMarketing'));
const EmailMarketingPricing = lazy(() => import('./pages/EmailMarketingPricing'));
const SubscriptionPricingPage = lazy(() => import('./pages/SubscriptionPricingPage'));
const MaintenancePage = lazy(() => import('./pages/MaintenancePage'));
const CheckoutPage = lazy(() => import('./pages/CheckoutPage'));
const BecomePartnerPage = lazy(() => import('./pages/BecomePartnerPage'));
const PartnerDashboard = lazy(() => import('./pages/PartnerDashboard'));
const PaymentPage = lazy(() => import('./pages/PaymentPage'));
const PayRequestSuccessPage = lazy(() => import('./pages/PayRequestSuccessPage'));
const PartnerPaymentSettings = lazy(() => import('./pages/PartnerPaymentSettings'));
const LegalPage = lazy(() => import('./pages/LegalPage'));
const PlatformPoliciesPage = lazy(() => import('./pages/PlatformPoliciesPage'));
const InviteAcceptPage = lazy(() => import('./pages/InviteAcceptPage'));
const CompareListingsPage = lazy(() => import('./pages/CompareListingsPage'));
const StorefrontPage = lazy(() => import('./pages/StorefrontPage'));
const BulkImportPage = lazy(() => import('./pages/BulkImportPage'));
const ReviewPage = lazy(() => import('./pages/ReviewPage'));
const ReviewSubmitPage = lazy(() => import('./pages/ReviewSubmitPage'));
const CommunityPage = lazy(() => import('./pages/CommunityPage'));
const AboutUsPage = lazy(() => import('./pages/AboutUsPage'));
const UnsubscribePage = lazy(() => import('./pages/UnsubscribePage'));
const EmailPreferencesPage = lazy(() => import('./pages/EmailPreferencesPage'));
const ResubscribePage = lazy(() => import('./pages/ResubscribePage'));
const ProhibitedItemsPage = lazy(() => import('./pages/ProhibitedItemsPage'));

// Vehicle Auction Module
const VehicleAuctionsRoute = lazy(() => import('./pages/vehicles/VehicleAuctionsRoute'));
const VehicleDetailPage = lazy(() => import('./pages/vehicles/VehicleDetailPage'));
const CreateVehicleListingPage = lazy(() => import('./pages/vehicles/CreateVehicleListingPage'));
const DealerLicenseVerificationPage = lazy(() => import('./pages/vehicles/DealerLicenseVerificationPage'));
const VehicleUnlockPage = lazy(() => import('./pages/vehicles/VehicleUnlockPage'));
const SellerRegistrationPage = lazy(() => import('./pages/vehicles/SellerRegistrationPage'));
const MyVehicleListingsPage = lazy(() => import('./pages/vehicles/MyVehicleListingsPage'));
const VehicleInvoicesPage = lazy(() => import('./pages/vehicles/VehicleInvoicesPage'));
const SellerFinancialsPage = lazy(() => import('./pages/vehicles/SellerFinancialsPage'));
// iter293 — Multi-Lot Vehicle Auction (Copart-style sequential events)
const CreateVehicleMultiLotPage = lazy(() => import('./pages/vehicles/CreateVehicleMultiLotPage'));
const LotTemplatesManagerPage = lazy(() => import('./pages/vehicles/LotTemplatesManagerPage'));
const VehicleMultiLotDetailPage = lazy(() => import('./pages/vehicles/VehicleMultiLotDetailPage'));

// Lazy-loaded heavy components
const AIAssistant = lazy(() => import('./components/AIAssistant'));
// iter280 — Single, unified site-wide AI Core widget. The iter277
// dashboard-only `AICoreSupportWidget` was unmounted in this sprint
// to resolve the visual collision (two FABs overlapping on dashboard
// + admin routes). The legacy `AIAssistant` already supports the full
// iter278/279 streaming UX (typewriter cursor + rose Stop button +
// graceful abort) so it serves as the canonical surface across every
// route. The `AICoreSupportWidget.jsx` file is kept on disk for
// potential future contextual surfaces but NEVER mounted in App.js.

// ─── Global Loading Fallback ──────────────────────────────────────
const PageLoader = () => {
  const [elapsed, setElapsed] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(t);
  }, []);

  if (elapsed >= 25) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center" data-testid="page-loader-timeout">
        <div className="text-center space-y-4 max-w-sm">
          <div className="mx-auto w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
            <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M18.364 5.636a9 9 0 11-12.728 0M12 9v4"/></svg>
          </div>
          <p className="text-sm font-semibold text-slate-700">Having trouble connecting.</p>
          <p className="text-xs text-slate-500">Please refresh the page.</p>
          <button onClick={() => window.location.reload()} className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90">
            Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center" data-testid="page-loader">
      <div className="text-center space-y-4">
        <div className="relative mx-auto w-12 h-12">
          <div className="absolute inset-0 rounded-full border-4 border-slate-200 dark:border-slate-700" />
          <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-[#1E3A8A] border-r-[#06B6D4] animate-spin" />
        </div>
        <p className="text-sm text-muted-foreground font-medium tracking-wide">
          {elapsed >= 12 ? 'Taking longer than usual... still loading' : 'Loading...'}
        </p>
      </div>
    </div>
  );
};

// ─── Service Worker ───────────────────────────────────────────────
if (typeof window !== 'undefined') {
  registerServiceWorker().then((registration) => {
    if (registration) {
      console.log('[BidVex] Push notifications ready');
    }
  });
}

// Routes that require phone verification before access
const VERIFICATION_REQUIRED_ROUTES = [
  '/create-listing',
  '/create-multi-item-listing',
  '/seller/dashboard',
  '/buyer/dashboard',
  '/messages',
];

const ProtectedRoute = ({ children, requireVerification = false }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/auth" state={{ from: location }} replace />;
  
  const needsVerification = requireVerification || 
    VERIFICATION_REQUIRED_ROUTES.some(route => location.pathname.startsWith(route));
  
  if (needsVerification && !user.phone_verified && user.role !== 'admin' && location.pathname !== '/verify-phone') {
    return <Navigate to="/verify-phone" state={{ from: location }} replace />;
  }
  
  return children;
};

const PhoneVerificationRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/auth" state={{ from: location }} replace />;
  
  if (user.phone_verified) {
    const from = location.state?.from?.pathname || '/seller/dashboard';
    return <Navigate to={from} replace />;
  }
  
  return children;
};

// iter212 — Routes that don't apply to storage-facility-only users.
// Silently redirects them to their storage dashboard (no error banner).
// Admins on facility accounts still pass through.
const BlockForStorageFacility = ({ children, redirectTo = '/storage-dashboard' }) => {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  const isStorageOnly = !!(
    user
    && (user.account_type === 'storage_facility' || user.is_storage_facility === true)
    && user.role !== 'admin'
    && user.role !== 'superadmin'
  );
  if (isStorageOnly) {
    return <Navigate to={redirectTo} replace />;
  }
  return children;
};

// Convenience redirect: /dashboard → role-aware dashboard
const DashboardRedirect = () => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/auth" state={{ from: location }} replace />;
  if (user.role === 'admin' || user.role === 'super_admin') {
    return <Navigate to="/admin" replace />;
  }
  // iter212 — Storage Facility users get the focused storage dashboard
  if (user.account_type === 'storage_facility' || user.is_storage_facility === true) {
    return <Navigate to="/storage-dashboard" replace />;
  }
  if (user.role === 'seller' || user.account_type === 'business') {
    return <Navigate to="/seller/dashboard" replace />;
  }
  return <Navigate to="/buyer/dashboard" replace />;
};

const FooterWrapper = () => {
  const location = useLocation();
  if (location.pathname === '/messages') return null;
  return <Footer />;
};

const MobileNavWrapper = () => {
  const location = useLocation();
  if (location.pathname === '/messages') return null;
  return <MobileBottomNav />;
};

const AIAssistantWrapper = () => {
  const location = useLocation();
  if (location.pathname === '/messages') return null;
  return <AIAssistant />;
};

// iter280 — REMOVED: AICoreSupportWidgetWrapper.
// The dashboard-only widget caused a bottom-right FAB collision with
// the legacy public AIAssistant. The legacy assistant is now the
// single, unified, site-wide AI Core surface across every route
// (public marketplace + homepage + dashboards + admin). It already
// carries the full iter278/279 streaming UX + bilingual i18n + auth-
// aware history.

// iter272 — Captures UTM / campaign params on every URL change.
// Mounts once inside <BrowserRouter>; the underlying util is a no-op
// when no UTM params are present, so this is essentially free.
const CampaignAttributionTracker = () => {
  const location = useLocation();
  React.useEffect(() => {
    try { captureCampaignTracking(location.search); } catch (_) { /* noop */ }
  }, [location.search]);
  return null;
};

const MaintenanceGuard = ({ children }) => {
  const { mode, message, expectedBack, socialLinks, loading, isMaintenanceOrComingSoon } = useSiteMode();
  const { user, loading: authLoading } = useAuth();
  const location = useLocation();
  
  const searchParams = new URLSearchParams(location.search);
  const isPreview = searchParams.get('preview_mode') === 'true';
  
  const isAdminRoute = location.pathname.startsWith('/admin');
  if (isAdminRoute) return children;
  
  const isAuthRoute = location.pathname === '/auth';
  const isPartnerRoute = location.pathname === '/become-a-partner' || location.pathname.startsWith('/partner');
  const isLegalRoute = location.pathname === '/legal';
  const isInviteRoute = location.pathname.startsWith('/invite/');
  const isMessagesRoute = location.pathname === '/messages';
  if (isAuthRoute || isPartnerRoute || isLegalRoute || isInviteRoute || isMessagesRoute) return children;
  
  if (loading || authLoading) return <PageLoader />;
  
  const isAdmin = user?.email?.endsWith('@bidvex.com');
  
  if (isMaintenanceOrComingSoon && !isAdmin && !isPreview) {
    return (
      <Suspense fallback={<PageLoader />}>
        <MaintenancePage mode={mode} message={message} expectedBack={expectedBack} socialLinks={socialLinks} />
      </Suspense>
    );
  }
  
  return children;
};

const App = () => {
  const { i18n } = useTranslation();
  const { user, processGoogleSession } = useAuth();
  const [sessionProcessing, setSessionProcessing] = useState(false);

  // Phase 5 — Boot Meta Pixel (CASL-gated by consent inside the helper)
  useEffect(() => {
    import('./utils/metaPixel').then(({ initMetaPixel }) => initMetaPixel());
  }, []);

  // iter301 P2 — bilingual SEO: keep <html lang> in sync with the active language
  useEffect(() => {
    const apply = (lng) => {
      document.documentElement.lang = (lng || 'en').toLowerCase().startsWith('fr') ? 'fr' : 'en';
    };
    apply(i18n.language);
    i18n.on('languageChanged', apply);
    return () => i18n.off('languageChanged', apply);
  }, [i18n]);

  useEffect(() => {
    const checkForSession = async () => {
      const hash = window.location.hash;
      if (hash.includes('session_id=')) {
        setSessionProcessing(true);
        const sessionId = hash.split('session_id=')[1].split('&')[0];
        try {
          await processGoogleSession(sessionId);
          window.location.hash = '';
          window.location.href = '/marketplace';
        } catch (error) {
          console.error('Session processing failed:', error);
        } finally {
          setSessionProcessing(false);
        }
      }
    };

    if (!user) {
      checkForSession();
    }
  }, [user, processGoogleSession]);

  if (sessionProcessing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-teal-50 dark:from-gray-900 dark:to-gray-800">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary border-t-transparent mx-auto mb-4"></div>
          <p className="text-lg font-medium">Processing authentication...</p>
        </div>
      </div>
    );
  }

  return (
    <HelmetProvider>
    <I18nextProvider i18n={i18n}>
      <BrowserRouter>
        <SiteConfigProvider>
          <CurrencyProvider>
          <FeatureFlagsProvider>
          <SiteModeProvider>
          <PromoBannerProvider>
            <ScrollToTop />
            <MarketingPixelLoader />
            {/* iter272 — Capture incoming UTM/campaign params on every route change. */}
            <CampaignAttributionTracker />
            <FbPixelTracker />
            <CookieConsentBanner />
            <MaintenanceGuard>
        <div className="App min-h-screen bg-gradient-to-br from-blue-50 via-white to-teal-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
          {/* iter214 P3 — Sticky site-wide dealer-fee banner (above the navbar) */}
          <GlobalDealerFeeBanner />
          <TrendyAnnouncementBar />
          {/* iter243 Mission 1 — Platform-wide promotional banner stack. */}
          <PromotionalBanner />
          <Navbar />
          <Suspense fallback={<PageLoader />}>
          <Routes>
          <Route path="/" element={<ErrorBoundary scope="home"><HomePage /></ErrorBoundary>} />
          <Route path="/marketplace" element={<ErrorBoundary scope="marketplace"><MarketplacePage /></ErrorBoundary>} />
          <Route path="/items" element={<ErrorBoundary scope="items"><ItemsMarketplacePage /></ErrorBoundary>} />
          <Route path="/lots" element={<ErrorBoundary scope="lots"><LotsMarketplacePage /></ErrorBoundary>} />
          <Route path="/lots/:id" element={<ErrorBoundary scope="lot-detail"><MultiItemListingDetailPage /></ErrorBoundary>} />
          <Route path="/listing/:id" element={<ErrorBoundary scope="listing-detail"><ListingDetailPage /></ErrorBoundary>} />
          <Route path="/compare" element={<CompareListingsPage />} />
          <Route path="/store/:userId" element={<StorefrontPage />} />
          <Route path="/bulk-import" element={<ProtectedRoute><BulkImportPage /></ProtectedRoute>} />
          <Route path="/auth" element={<AuthPage />} />
          {/* iter293 — /login is a common deep link; redirect to /auth */}
          <Route path="/login" element={<Navigate to="/auth" replace />} />
          <Route path="/auth/google/finish" element={<GoogleAuthFinishPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/verify-phone" element={
            <PhoneVerificationRoute><PhoneVerificationPage /></PhoneVerificationRoute>
          } />
          <Route path="/how-it-works" element={<HowItWorksPage />} />
          {/* iter261 — Public payment page (no auth) for admin-issued payment requests. */}
          <Route path="/pay/:payment_request_id" element={<PaymentPage />} />
          <Route path="/pay/:payment_request_id/success" element={<PayRequestSuccessPage />} />
          <Route path="/community" element={<CommunityPage />} />
          <Route path="/about" element={<AboutUsPage />} />
          <Route path="/about-us" element={<AboutUsPage />} />
          <Route path="/unsubscribe" element={<UnsubscribePage />} />
          <Route path="/desabonnement" element={<UnsubscribePage />} />
          <Route path="/email-preferences" element={<EmailPreferencesPage />} />
          <Route path="/preferences-courriel" element={<EmailPreferencesPage />} />
          <Route path="/resubscribe" element={<ResubscribePage />} />
          <Route path="/reabonnement" element={<ResubscribePage />} />
          <Route path="/watchlist" element={
            <ProtectedRoute><WatchlistPage /></ProtectedRoute>
          } />
          <Route path="/seller/:sellerId" element={<SellerProfilePage />} />
          <Route path="/seller/dashboard" element={
            <ProtectedRoute>
              <BlockForStorageFacility>
                <SellerDashboard />
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          <Route path="/buyer/dashboard" element={
            <ProtectedRoute>
              <BlockForStorageFacility>
                <BuyerDashboard />
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          {/* Convenience aliases — /dashboard, /seller-dashboard, /buyer-dashboard */}
          <Route path="/dashboard" element={<DashboardRedirect />} />
          <Route path="/seller-dashboard" element={<Navigate to="/seller/dashboard" replace />} />
          <Route path="/buyer-dashboard" element={<Navigate to="/buyer/dashboard" replace />} />
          <Route path="/create-listing" element={
            <ProtectedRoute>
              <BlockForStorageFacility redirectTo="/storage-auctions/create">
                <CreateListingPage />
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          <Route path="/payment/success" element={
            <ProtectedRoute><PaymentSuccessPage /></ProtectedRoute>
          } />
          <Route path="/settings" element={
            <ProtectedRoute><ProfileSettingsPage /></ProtectedRoute>
          } />
          {/* iter201 — Phase 3 / 3A — Alias so /profile/settings deep-links resolve */}
          <Route path="/profile/settings" element={<Navigate to="/settings" replace />} />
          <Route path="/profile/verification" element={<Navigate to="/settings" replace />} />
          <Route path="/affiliate" element={
            <ProtectedRoute>
              <BlockForStorageFacility>
                <ErrorBoundary scope="affiliate-dashboard">
                  <AffiliateDashboard />
                </ErrorBoundary>
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          <Route path="/messages" element={
            <ProtectedRoute><MessagesPage /></ProtectedRoute>
          } />
          {/* iter217 Phase 4 — Dedicated notifications page */}
          <Route path="/notifications" element={
            <ProtectedRoute><NotificationsPage /></ProtectedRoute>
          } />
          <Route path="/create-multi-item-listing" element={
            <ProtectedRoute>
              <BlockForStorageFacility redirectTo="/storage-auctions/create">
                <CreateMultiItemListing />
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          {/* iter217 — Partner-friendly alias for the lot auction creator */}
          <Route path="/lots/create" element={<Navigate to="/create-multi-item-listing" replace />} />
          {/* Phase 6.0 / Failure 3 — admin notification deep-link target */}
          <Route path="/admin/flagged-listings" element={
            <ProtectedRoute><AdminDashboard /></ProtectedRoute>
          } />
          <Route path="/admin-control-panel" element={
            <ProtectedRoute><AdminDashboard /></ProtectedRoute>
          } />
          <Route path="/admin" element={
            <ProtectedRoute><ErrorBoundary scope="admin"><AdminDashboard /></ErrorBoundary></ProtectedRoute>
          } />
          <Route path="/admin/tax-dashboard" element={
            <ProtectedRoute><AdminTaxDashboard /></ProtectedRoute>
          } />
          {/* iter217 Phase 5 Hotfix v5b — Broker Ecosystem */}
          <Route path="/admin/brokers" element={
            <ProtectedRoute><AdminBrokersPage /></ProtectedRoute>
          } />
          {/* iter217 Phase 5 Hotfix v6.5 — Subscription Management */}
          <Route path="/admin/subscriptions" element={
            <ProtectedRoute><AdminSubscriptionsPage /></ProtectedRoute>
          } />
          {/* Phase 6.2 Task 5 — Admin Storage Hold Settlements */}
          <Route path="/admin/storage-settlements" element={
            <ProtectedRoute><StorageHoldSettlementsTab /></ProtectedRoute>
          } />
          {/* iter217 Phase 5 Hotfix v7 — Public "How brokers work" (EN + FR) */}
          <Route path="/how-brokers-work" element={<HowBrokersWorkPage />} />
          <Route path="/comment-fonctionnent-les-courtiers" element={<HowBrokersWorkPage />} />
          {/* iter217 Phase 5 Hotfix v8.1 — Token-secured buyer receipt */}
          <Route path="/my-receipt/:invoice_id" element={<MyReceiptPage />} />
          <Route path="/become-a-broker" element={
            <ProtectedRoute><BecomeABrokerPage /></ProtectedRoute>
          } />
          <Route path="/devenir-courtier" element={
            <ProtectedRoute><BecomeABrokerPage /></ProtectedRoute>
          } />
          <Route path="/brokers" element={<BrokerDirectoryPage />} />
          <Route path="/courtiers" element={<BrokerDirectoryPage />} />
          <Route path="/brokers/:broker_id/request" element={
            <ProtectedRoute><BrokerBindingRequestPage /></ProtectedRoute>
          } />
          <Route path="/broker/dashboard" element={
            <ProtectedRoute><ErrorBoundary scope="broker-dashboard"><BrokerDashboardPage /></ErrorBoundary></ProtectedRoute>
          } />
          <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
          <Route path="/privacy" element={<Navigate to="/privacy-policy" replace />} />
          {/* iter304 — Cookie policy alias per user spec; banner link target */}
          <Route path="/legal/cookies" element={<PrivacyPolicyPage />} />
          <Route path="/legal/cookie-policy" element={<Navigate to="/legal/cookies" replace />} />
          <Route path="/terms-of-service" element={<TermsOfServicePage />} />
          <Route path="/terms" element={<Navigate to="/terms-of-service" replace />} />
          <Route path="/refund-policy" element={<RefundPolicyPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/refunds" element={<Navigate to="/refund-policy" replace />} />
          <Route path="/returns" element={<Navigate to="/refund-policy" replace />} />
          <Route path="/contact-us" element={<ContactUsPage />} />
          <Route path="/contact" element={<Navigate to="/contact-us" replace />} />
          <Route path="/legal" element={<LegalPage />} />
          {/* iter214 P5 — Bilingual prohibited-items page */}
          <Route path="/prohibited-items" element={<ProhibitedItemsPage />} />
          <Route path="/articles-interdits" element={<ProhibitedItemsPage />} />
          <Route path="/policies" element={<PlatformPoliciesPage />} />
          <Route path="/invite/:token" element={<InviteAcceptPage />} />
          <Route path="/become-a-partner" element={
            <BlockForStorageFacility>
              <BecomePartnerPage />
            </BlockForStorageFacility>
          } />
          <Route path="/partner/dashboard" element={
            <ProtectedRoute>
              <BlockForStorageFacility>
                <PartnerDashboard />
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          <Route path="/partner/payment-settings" element={
            <ProtectedRoute>
              <BlockForStorageFacility>
                <PartnerPaymentSettings />
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          <Route path="/client-marketing" element={
            <ProtectedRoute><ClientEmailMarketing /></ProtectedRoute>
          } />
          <Route path="/email-marketing-pricing" element={<EmailMarketingPricing />} />
          <Route path="/pricing" element={<SubscriptionPricingPage />} />
          <Route path="/subscription/success" element={<PaymentSuccessPage />} />
          <Route path="/checkout/:listingId" element={
            <ProtectedRoute><CheckoutPage /></ProtectedRoute>
          } />
          <Route path="/review/submit" element={
            <ProtectedRoute><ReviewSubmitPage /></ProtectedRoute>
          } />
          <Route path="/review/:transactionId" element={
            <ProtectedRoute><ReviewPage /></ProtectedRoute>
          } />
          
          {/* Vehicle Auction Module */}
          <Route path="/vehicle-auctions" element={<ErrorBoundary scope="vehicle-auctions"><VehicleAuctionsRoute /></ErrorBoundary>} />
          <Route path="/encheres-de-vehicules" element={<ErrorBoundary scope="vehicle-auctions"><VehicleAuctionsRoute /></ErrorBoundary>} />
          <Route path="/vehicle-auctions/:id" element={<ErrorBoundary scope="vehicle-detail"><VehicleDetailPage /></ErrorBoundary>} />
          <Route path="/vehicle-auctions/create" element={
            <ProtectedRoute>
              <BlockForStorageFacility redirectTo="/storage-auctions/create">
                <ErrorBoundary scope="vehicle-listing-create">
                  <CreateVehicleListingPage />
                </ErrorBoundary>
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/dealer-license" element={
            <ProtectedRoute>
              <BlockForStorageFacility>
                <DealerLicenseVerificationPage />
              </BlockForStorageFacility>
            </ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/:id/unlock" element={
            <ProtectedRoute><VehicleUnlockPage /></ProtectedRoute>
          } />
          {/* iter293 — Multi-Lot Vehicle Auction (Copart-style sequential events) */}
          <Route path="/vehicle-multi-lot/create" element={
            <ProtectedRoute>
              <ErrorBoundary scope="vehicle-multi-lot-create">
                <CreateVehicleMultiLotPage />
              </ErrorBoundary>
            </ProtectedRoute>
          } />
          <Route path="/vehicle-multi-lot/:eventId" element={
            <ErrorBoundary scope="vehicle-multi-lot-detail">
              <VehicleMultiLotDetailPage />
            </ErrorBoundary>
          } />
          <Route path="/vehicle-auctions/seller/register" element={
            <ProtectedRoute><SellerRegistrationPage /></ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/my-listings" element={
            <ProtectedRoute>
              <ErrorBoundary scope="vehicle-my-listings">
                <MyVehicleListingsPage />
              </ErrorBoundary>
            </ProtectedRoute>
          } />
          {/* iter304 — Lot Templates manager (dealer tab) */}
          <Route path="/vehicle-auctions/lot-templates" element={
            <ProtectedRoute>
              <ErrorBoundary scope="lot-templates-manager">
                <LotTemplatesManagerPage />
              </ErrorBoundary>
            </ProtectedRoute>
          } />
          {/* iter293 — Convenience aliases for common deep-link URLs */}
          <Route path="/vehicles/my-listings" element={<Navigate to="/vehicle-auctions/my-listings" replace />} />
          <Route path="/my-vehicle-listings" element={<Navigate to="/vehicle-auctions/my-listings" replace />} />
          <Route path="/vehicle-auctions/invoices" element={
            <ProtectedRoute><VehicleInvoicesPage /></ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/invoices/:invoiceId" element={
            <ProtectedRoute><VehicleInvoicesPage /></ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/seller/financials" element={
            <ProtectedRoute><SellerFinancialsPage /></ProtectedRoute>
          } />

          {/* ── Storage Unit Auctions (iteration 169) ── */}
          <Route path="/storage-auctions" element={<ErrorBoundary scope="storage-auctions"><StorageAuctionsBrowse /></ErrorBoundary>} />
          <Route path="/storage-auctions/browse" element={<ErrorBoundary scope="storage-browse"><StorageAuctionsBrowse /></ErrorBoundary>} />
          <Route path="/storage-auctions/how-it-works" element={<StorageHowItWorks />} />
          <Route path="/storage-auctions/terms" element={<StorageTerms />} />
          <Route path="/storage-auctions/for-facilities" element={<StorageForFacilities />} />
          <Route path="/storage-auctions/register-facility" element={
            <ProtectedRoute><StorageFacilityRegister /></ProtectedRoute>
          } />
          <Route path="/storage-auctions/my-deposits" element={
            <ProtectedRoute><MyStorageDeposits /></ProtectedRoute>
          } />
          <Route path="/storage-auctions/create" element={
            <ProtectedRoute><StorageAuctionCreate /></ProtectedRoute>
          } />
          <Route path="/storage-dashboard" element={
            <ProtectedRoute><StorageDashboard /></ProtectedRoute>
          } />
          <Route path="/storage-auctions/:id" element={<StorageAuctionDetail />} />

          {/* ── Phase 6.2 Task 4 — Buyer cleanouts ── */}
          <Route path="/storage-auctions/my-cleanouts" element={
            <ProtectedRoute><MyCleanoutsPage /></ProtectedRoute>
          } />

          {/* ── Phase 6.2 Task 6 — Facility Manager Dashboard ── */}
          <Route path="/facility/dashboard" element={
            <ProtectedRoute><FacilityDashboard /></ProtectedRoute>
          } />
          <Route path="/facility/dashboard/:tab" element={
            <ProtectedRoute><FacilityDashboard /></ProtectedRoute>
          } />
          <Route path="/storage/facility/:facilityId" element={<FacilityPublicProfile />} />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
          </Suspense>
          <FooterWrapper />
          <Suspense fallback={null}>
            <AIAssistantWrapper />
          </Suspense>
          <MessageNotificationListener />
          <Toaster position="top-right" />
            <MobileNavWrapper />
          </div>
          </MaintenanceGuard>
          </PromoBannerProvider>
          </SiteModeProvider>
        </FeatureFlagsProvider>
        </CurrencyProvider>
      </SiteConfigProvider>
    </BrowserRouter>
    </I18nextProvider>
    </HelmetProvider>
  );
};

export default App;
