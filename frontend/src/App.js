import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useTranslation, I18nextProvider } from 'react-i18next';
import i18n from './i18n';
import { useAuth } from './contexts/AuthContext';
import { FeatureFlagsProvider } from './contexts/FeatureFlagsContext';
import { SiteConfigProvider } from './contexts/SiteConfigContext';
import { CurrencyProvider } from './contexts/CurrencyContext';
import { Toaster } from './components/ui/sonner';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import MobileBottomNav from './components/MobileBottomNav';
import AIAssistant from './components/AIAssistant';
import MessageNotificationListener from './components/MessageNotificationListener';
import ScrollToTop from './components/ScrollToTop';
import CookieConsentBanner from './components/CookieConsentBanner';
import HomePage from './pages/HomePage';
import MarketplacePage from './pages/MarketplacePage';
import ListingDetailPage from './pages/ListingDetailPage';
import AuthPage from './pages/AuthPage';
import SellerDashboard from './pages/SellerDashboard';
import BuyerDashboard from './pages/BuyerDashboard';
import CreateListingPage from './pages/CreateListingPage';
import PaymentSuccessPage from './pages/PaymentSuccessPage';
import ProfileSettingsPage from './pages/ProfileSettingsPage';
import AffiliateDashboard from './pages/AffiliateDashboard';
import MessagesPage from './pages/MessagesPage';
import CreateMultiItemListing from './pages/CreateMultiItemListing';
import LotsMarketplacePage from './pages/LotsMarketplacePage';
import MultiItemListingDetailPage from './pages/MultiItemListingDetailPage';
import ItemsMarketplacePage from './pages/ItemsMarketplacePage';
import AdminDashboard from './pages/AdminDashboard';
import WatchlistPage from './pages/WatchlistPage';
import HowItWorksPage from './pages/HowItWorksPage';
import SellerProfilePage from './pages/SellerProfilePage';
import NotFoundPage from './pages/NotFoundPage';
import PrivacyPolicyPage from './pages/PrivacyPolicyPage';
import TermsOfServicePage from './pages/TermsOfServicePage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import PhoneVerificationPage from './pages/PhoneVerificationPage';
import { registerServiceWorker } from './utils/pushNotifications';
import './App.css';

// Initialize Service Worker for push notifications
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
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }
  
  // Check if route requires phone verification
  const needsVerification = requireVerification || 
    VERIFICATION_REQUIRED_ROUTES.some(route => location.pathname.startsWith(route));
  
  // Redirect unverified users to phone verification (except admins and already on verify page)
  if (needsVerification && 
      !user.phone_verified && 
      user.role !== 'admin' && 
      location.pathname !== '/verify-phone') {
    return <Navigate to="/verify-phone" state={{ from: location }} replace />;
  }
  
  return children;
};

// Wrapper for phone verification page - allow access but redirect if already verified
const PhoneVerificationRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }
  
  // If already verified, redirect to intended destination or dashboard
  if (user.phone_verified) {
    const from = location.state?.from?.pathname || '/seller/dashboard';
    return <Navigate to={from} replace />;
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

  // Performance: Enforce lazy loading on all images globally
  useEffect(() => {
    const images = document.querySelectorAll('img:not([loading])');
    images.forEach(img => {
      if (!img.getAttribute('loading')) {
        img.setAttribute('loading', 'lazy');
      }
    });
  }, []);

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
    <I18nextProvider i18n={i18n}>
      <BrowserRouter>
        <SiteConfigProvider>
          <CurrencyProvider>
          <FeatureFlagsProvider>
            <ScrollToTop />
        <div className="App min-h-screen bg-gradient-to-br from-blue-50 via-white to-teal-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
          <Navbar />
          <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/items" element={<ItemsMarketplacePage />} />
          <Route path="/lots" element={<LotsMarketplacePage />} />
          <Route path="/lots/:id" element={<MultiItemListingDetailPage />} />
          <Route path="/listing/:id" element={<ListingDetailPage />} />
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
          <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
          <Route path="/terms-of-service" element={<TermsOfServicePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
          <Footer />
          <AIAssistant />
          <MessageNotificationListener />
          <Toaster position="top-right" />
          <CookieConsentBanner />
            <MobileBottomNav />
          </div>
        </FeatureFlagsProvider>
        </CurrencyProvider>
      </SiteConfigProvider>
    </BrowserRouter>
    </I18nextProvider>
  );
};

export default App;
