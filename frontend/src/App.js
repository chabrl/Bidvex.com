import React, { Suspense, lazy, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useTranslation, I18nextProvider } from 'react-i18next';
import i18n from './i18n';
import { useAuth } from './contexts/AuthContext';
import { FeatureFlagsProvider } from './contexts/FeatureFlagsContext';
import { SiteConfigProvider } from './contexts/SiteConfigContext';
import { CurrencyProvider } from './contexts/CurrencyContext';
import { SiteModeProvider, useSiteMode } from './contexts/SiteModeContext';
import { Toaster } from './components/ui/sonner';
import { HelmetProvider } from 'react-helmet-async';

// Shell components — kept eager (always visible on every page)
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import TrendyAnnouncementBar from './components/TrendyAnnouncementBar';
import MobileBottomNav from './components/MobileBottomNav';
import ScrollToTop from './components/ScrollToTop';
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
const BuyerDashboard = lazy(() => import('./pages/BuyerDashboard'));
const CreateListingPage = lazy(() => import('./pages/CreateListingPage'));
const PaymentSuccessPage = lazy(() => import('./pages/PaymentSuccessPage'));
const ProfileSettingsPage = lazy(() => import('./pages/ProfileSettingsPage'));
const AffiliateDashboard = lazy(() => import('./pages/AffiliateDashboard'));
const MessagesPage = lazy(() => import('./pages/MessagesPage'));
const CreateMultiItemListing = lazy(() => import('./pages/CreateMultiItemListing'));
const LotsMarketplacePage = lazy(() => import('./pages/LotsMarketplacePage'));
const MultiItemListingDetailPage = lazy(() => import('./pages/MultiItemListingDetailPage'));
const ItemsMarketplacePage = lazy(() => import('./pages/ItemsMarketplacePage'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const AdminTaxDashboard = lazy(() => import('./pages/AdminTaxDashboard'));
const WatchlistPage = lazy(() => import('./pages/WatchlistPage'));
const HowItWorksPage = lazy(() => import('./pages/HowItWorksPage'));
const SellerProfilePage = lazy(() => import('./pages/SellerProfilePage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const PrivacyPolicyPage = lazy(() => import('./pages/PrivacyPolicyPage'));
const TermsOfServicePage = lazy(() => import('./pages/TermsOfServicePage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));
const PhoneVerificationPage = lazy(() => import('./pages/PhoneVerificationPage'));
const ClientEmailMarketing = lazy(() => import('./pages/ClientEmailMarketing'));
const EmailMarketingPricing = lazy(() => import('./pages/EmailMarketingPricing'));
const SubscriptionPricingPage = lazy(() => import('./pages/SubscriptionPricingPage'));
const MaintenancePage = lazy(() => import('./pages/MaintenancePage'));
const CheckoutPage = lazy(() => import('./pages/CheckoutPage'));
const BecomePartnerPage = lazy(() => import('./pages/BecomePartnerPage'));
const PartnerDashboard = lazy(() => import('./pages/PartnerDashboard'));
const LegalPage = lazy(() => import('./pages/LegalPage'));
const InviteAcceptPage = lazy(() => import('./pages/InviteAcceptPage'));
const CompareListingsPage = lazy(() => import('./pages/CompareListingsPage'));
const StorefrontPage = lazy(() => import('./pages/StorefrontPage'));
const BulkImportPage = lazy(() => import('./pages/BulkImportPage'));
const ReviewPage = lazy(() => import('./pages/ReviewPage'));

// Vehicle Auction Module
const VehicleAuctionsPage = lazy(() => import('./pages/vehicles/VehicleAuctionsPage'));
const VehicleDetailPage = lazy(() => import('./pages/vehicles/VehicleDetailPage'));
const CreateVehicleListingPage = lazy(() => import('./pages/vehicles/CreateVehicleListingPage'));
const SellerRegistrationPage = lazy(() => import('./pages/vehicles/SellerRegistrationPage'));
const MyVehicleListingsPage = lazy(() => import('./pages/vehicles/MyVehicleListingsPage'));
const VehicleInvoicesPage = lazy(() => import('./pages/vehicles/VehicleInvoicesPage'));
const SellerFinancialsPage = lazy(() => import('./pages/vehicles/SellerFinancialsPage'));

// Lazy-loaded heavy components
const AIAssistant = lazy(() => import('./components/AIAssistant'));

// ─── Global Loading Fallback ──────────────────────────────────────
const PageLoader = () => {
  const [elapsed, setElapsed] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(t);
  }, []);

  if (elapsed >= 15) {
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
          {elapsed >= 8 ? 'Taking longer than usual... still loading' : 'Loading...'}
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

const MaintenanceGuard = ({ children }) => {
  const { mode, message, expectedBack, socialLinks, loading, isMaintenanceOrComingSoon } = useSiteMode();
  const { user, loading: authLoading } = useAuth();
  const location = useLocation();
  
  const searchParams = new URLSearchParams(location.search);
  const isPreview = searchParams.get('preview_mode') === 'true';
  
  const isAdminRoute = location.pathname.startsWith('/admin');
  if (isAdminRoute) return children;
  
  const isAuthRoute = location.pathname === '/auth';
  const isPartnerRoute = location.pathname === '/become-a-partner';
  const isLegalRoute = location.pathname === '/legal';
  const isInviteRoute = location.pathname.startsWith('/invite/');
  if (isAuthRoute || isPartnerRoute || isLegalRoute || isInviteRoute) return children;
  
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
            <ScrollToTop />
            <MaintenanceGuard>
        <div className="App min-h-screen bg-gradient-to-br from-blue-50 via-white to-teal-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
          <TrendyAnnouncementBar />
          <Navbar />
          <Suspense fallback={<PageLoader />}>
          <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/items" element={<ItemsMarketplacePage />} />
          <Route path="/lots" element={<LotsMarketplacePage />} />
          <Route path="/lots/:id" element={<MultiItemListingDetailPage />} />
          <Route path="/listing/:id" element={<ListingDetailPage />} />
          <Route path="/compare" element={<CompareListingsPage />} />
          <Route path="/store/:userId" element={<StorefrontPage />} />
          <Route path="/bulk-import" element={<ProtectedRoute><BulkImportPage /></ProtectedRoute>} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/verify-phone" element={
            <PhoneVerificationRoute><PhoneVerificationPage /></PhoneVerificationRoute>
          } />
          <Route path="/how-it-works" element={<HowItWorksPage />} />
          <Route path="/watchlist" element={
            <ProtectedRoute><WatchlistPage /></ProtectedRoute>
          } />
          <Route path="/seller/:sellerId" element={<SellerProfilePage />} />
          <Route path="/seller/dashboard" element={
            <ProtectedRoute><SellerDashboard /></ProtectedRoute>
          } />
          <Route path="/buyer/dashboard" element={
            <ProtectedRoute><BuyerDashboard /></ProtectedRoute>
          } />
          <Route path="/create-listing" element={
            <ProtectedRoute><CreateListingPage /></ProtectedRoute>
          } />
          <Route path="/payment/success" element={
            <ProtectedRoute><PaymentSuccessPage /></ProtectedRoute>
          } />
          <Route path="/settings" element={
            <ProtectedRoute><ProfileSettingsPage /></ProtectedRoute>
          } />
          <Route path="/affiliate" element={
            <ProtectedRoute><AffiliateDashboard /></ProtectedRoute>
          } />
          <Route path="/messages" element={
            <ProtectedRoute><MessagesPage /></ProtectedRoute>
          } />
          <Route path="/create-multi-item-listing" element={
            <ProtectedRoute><CreateMultiItemListing /></ProtectedRoute>
          } />
          <Route path="/admin" element={
            <ProtectedRoute><AdminDashboard /></ProtectedRoute>
          } />
          <Route path="/admin/tax-dashboard" element={
            <ProtectedRoute><AdminTaxDashboard /></ProtectedRoute>
          } />
          <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
          <Route path="/privacy" element={<Navigate to="/privacy-policy" replace />} />
          <Route path="/terms-of-service" element={<TermsOfServicePage />} />
          <Route path="/legal" element={<LegalPage />} />
          <Route path="/invite/:token" element={<InviteAcceptPage />} />
          <Route path="/become-a-partner" element={<BecomePartnerPage />} />
          <Route path="/partner/dashboard" element={
            <ProtectedRoute><PartnerDashboard /></ProtectedRoute>
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
          <Route path="/review/:transactionId" element={
            <ProtectedRoute><ReviewPage /></ProtectedRoute>
          } />
          
          {/* Vehicle Auction Module */}
          <Route path="/vehicle-auctions" element={<VehicleAuctionsPage />} />
          <Route path="/vehicle-auctions/:id" element={<VehicleDetailPage />} />
          <Route path="/vehicle-auctions/create" element={
            <ProtectedRoute><CreateVehicleListingPage /></ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/seller/register" element={
            <ProtectedRoute><SellerRegistrationPage /></ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/my-listings" element={
            <ProtectedRoute><MyVehicleListingsPage /></ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/invoices" element={
            <ProtectedRoute><VehicleInvoicesPage /></ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/invoices/:invoiceId" element={
            <ProtectedRoute><VehicleInvoicesPage /></ProtectedRoute>
          } />
          <Route path="/vehicle-auctions/seller/financials" element={
            <ProtectedRoute><SellerFinancialsPage /></ProtectedRoute>
          } />
          
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
          </Suspense>
          <Footer />
          <Suspense fallback={null}>
            <AIAssistant />
          </Suspense>
          <MessageNotificationListener />
          <Toaster position="top-right" />
          <CookieConsentBanner />
            <MobileBottomNav />
          </div>
          </MaintenanceGuard>
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
