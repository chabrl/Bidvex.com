import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { User, CreditCard, Bell, MapPin, Loader2, Plus, Trash2, Globe, DollarSign, Crown, Star, Check, X, Bot, TrendingUp, Shield, Phone, Lock, Eye, EyeOff } from 'lucide-react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import AvatarUpload from '../components/AvatarUpload';
import SubscriptionBadge from '../components/SubscriptionBadge';
import TrustBadge from '../components/TrustBadge';
import PushNotificationToggle from '../components/PushNotificationToggle';
import UserTierGrid from '../components/UserTierGrid';
import PartnerLicenseCard from '../components/PartnerLicenseCard';
import SubscriptionManagement from '../components/SubscriptionManagement';
import PersonalizedSavingsCalculator from '../components/PersonalizedSavingsCalculator';
import B2BCouponActivationCard from '../components/B2BCouponActivationCard';
import PaymentTrustBox from '../components/PaymentTrustBox';
import { useTranslation } from 'react-i18next';

const API = API_BASE;
const stripePromise = loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY);

const ProfileSettingsPage = () => {
  const { user, updateUserPreferences, refreshUser } = useAuth();
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const defaultTab = searchParams.get('tab') || 'profile';
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [profileData, setProfileData] = useState({
    name: '',
    email: '',
    phone: '',
    address: '',
    province: '',
    company_name: '',
    tax_number: '',
    preferred_language: 'en',
    preferred_currency: 'CAD',
  });
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [showAddCard, setShowAddCard] = useState(false);
  const [recommendationsEnabled, setRecommendationsEnabled] = useState(true);

  // iter211 Step 3 — notification settings (auto-saved on change)
  const [notificationSettings, setNotificationSettings] = useState({
    email_summaries: true,
    bid_alerts: true,
    message_alerts: true,
    auction_win_alerts: true,
  });
  const [notifSettingsSaving, setNotifSettingsSaving] = useState(false);
  const [notifSettingsHydrated, setNotifSettingsHydrated] = useState(false);
  // Email change flow state
  const [showEmailChange, setShowEmailChange] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [emailChangePassword, setEmailChangePassword] = useState('');
  const [emailChangeLoading, setEmailChangeLoading] = useState(false);
  const [emailChangeRequested, setEmailChangeRequested] = useState(false);

  // Auto-confirm if user lands on /settings?email_change_token=...
  useEffect(() => {
    const token = searchParams.get('email_change_token');
    if (!token) return;
    (async () => {
      try {
        const r = await axios.post(`${API}/auth/email-change/confirm`, { token });
        toast.success(r.data?.message || 'Email confirmed. Please log in with your new email.');
        // Clear token from URL
        window.history.replaceState({}, '', '/settings');
        // Force logout because email changed → all sessions invalidated
        setTimeout(() => { localStorage.removeItem('token'); window.location.href = '/login'; }, 1500);
      } catch (err) {
        toast.error(err?.response?.data?.detail || 'Failed to confirm email change.');
      }
    })();
  }, [searchParams]);

  // Handler to switch to payment tab and open add card form
  const handleAddPaymentClick = () => {
    setActiveTab('payment');
    setShowAddCard(true);
  };

  useEffect(() => {
    if (user) {
      setProfileData({
        name: user.name || '',
        email: user.email || '',
        phone: user.phone || '',
        address: user.address || '',
        province: user.province || '',
        company_name: user.company_name || '',
        tax_number: user.tax_number || '',
        preferred_language: user.preferred_language || 'en',
        preferred_currency: user.preferred_currency || 'CAD',
      });
      setRecommendationsEnabled(user.personalized_recommendations !== false);
      // iter211 Step 3 — Hydrate notification settings from server (default ON
      // for every key the user hasn't touched yet).
      const ns = user.notification_settings || {};
      setNotificationSettings({
        email_summaries: ns.email_summaries !== false,
        bid_alerts: ns.bid_alerts !== false,
        message_alerts: ns.message_alerts !== false,
        auction_win_alerts: ns.auction_win_alerts !== false,
      });
      setNotifSettingsHydrated(true);
      fetchPaymentMethods();
    }
  }, [user]);

  // iter211 Step 3 — Auto-save notification settings on every toggle change
  // (with optimistic UI). useEffect fires AFTER user-triggered state changes,
  // not on initial hydration thanks to the `notifSettingsHydrated` guard.
  useEffect(() => {
    if (!notifSettingsHydrated) return;
    let cancelled = false;
    setNotifSettingsSaving(true);
    (async () => {
      try {
        await axios.put(`${API}/users/me`, {
          notification_settings: notificationSettings,
        });
        if (!cancelled) {
          toast.success(t('profile.notifSaved', 'Notification preference saved'));
        }
      } catch (err) {
        if (!cancelled) {
          // eslint-disable-next-line no-console
          console.error('notification_settings save failed', err);
          toast.error(t('profile.notifSaveFailed', 'Failed to save preference'));
        }
      } finally {
        if (!cancelled) setNotifSettingsSaving(false);
      }
    })();
    return () => { cancelled = true; };
  }, [notificationSettings]); // eslint-disable-line

  const handleToggleNotification = (key) => (checked) => {
    setNotificationSettings(prev => ({ ...prev, [key]: !!checked }));
  };

  const fetchPaymentMethods = async () => {
    try {
      const response = await axios.get(`${API}/payments/payment-methods`);
      setPaymentMethods(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to fetch payment methods:', error);
    }
  };

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await updateUserPreferences(profileData);
      // iter201 — Phase 3 mirror: keep the structured `province` field in sync
      // so the vehicle-auction buyer gate reads the same value the user just saved.
      if (profileData.province) {
        try {
          const token = localStorage.getItem('token');
          await axios.post(
            `${API}/vehicles/buyer-province`,
            { province: profileData.province },
            { headers: { Authorization: `Bearer ${token}` } },
          );
        } catch (_e) {
          // Non-fatal — main profile save already succeeded
        }
      }
      toast.success(t('profile.changesSaved'));
    } catch (error) {
      // iter189 Bug 4: Surface specific error from API instead of generic toast
      const detail = error?.response?.data?.detail;
      let msg = t('common.error');
      if (typeof detail === 'string') msg = detail;
      else if (detail?.message) msg = detail.message;
      else if (detail?.message_en) msg = detail.message_en;
      else if (error?.response?.data?.message) msg = error.response.data.message;
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleAvatarUpdate = async (avatarDataUrl) => {
    await axios.put(`${API}/profile`, { picture: avatarDataUrl });
  };

  const handleToggleRecommendations = async (checked) => {
    setRecommendationsEnabled(checked);
    try {
      await updateUserPreferences({ personalized_recommendations: checked });
      toast.success(checked ? 'Personalized recommendations enabled' : 'Personalized recommendations disabled');
    } catch {
      setRecommendationsEnabled(!checked);
      toast.error('Failed to update preference');
    }
  };

  const handleDeletePaymentMethod = async (methodId) => {
    if (window.confirm(t('payment.confirmDelete'))) {
      try {
        await axios.delete(`${API}/payments/payment-methods/${methodId}`);
        toast.success(t('payment.cardDeleted'));
        fetchPaymentMethods();
      } catch (error) {
        toast.error(t('payment.cardDeleteFailed'));
      }
    }
  };

  return (
    <div className="min-h-screen py-6 sm:py-8 px-3 sm:px-4 bg-gradient-to-br from-slate-50 via-white to-blue-50/30 dark:from-slate-950 dark:via-slate-900 dark:to-blue-950/20" data-testid="profile-settings-page">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white">
          {t('profile.accountSettings')}
        </h1>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          {/* Responsive Tab Navigation */}
          <TabsList className="flex w-full overflow-x-auto scrollbar-none bg-white/60 dark:bg-slate-800/60 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 rounded-2xl p-1.5 shadow-sm gap-1 no-scrollbar" style={{ WebkitOverflowScrolling: 'touch' }}>
            <TabsTrigger 
              value="profile" 
              data-testid="profile-tab"
              className="flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium data-[state=active]:bg-white data-[state=active]:dark:bg-slate-700 data-[state=active]:shadow-sm data-[state=active]:text-blue-600 data-[state=active]:dark:text-blue-400 text-slate-500 dark:text-slate-400 transition-all"
            >
              <User className="h-4 w-4" />
              <span className="hidden sm:inline">{t('profile.profileTab')}</span>
              <span className="sm:hidden">Profile</span>
            </TabsTrigger>
            <TabsTrigger 
              value="payment" 
              data-testid="payment-tab"
              className="flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium data-[state=active]:bg-white data-[state=active]:dark:bg-slate-700 data-[state=active]:shadow-sm data-[state=active]:text-blue-600 data-[state=active]:dark:text-blue-400 text-slate-500 dark:text-slate-400 transition-all"
            >
              <Shield className="h-4 w-4" />
              <span className="hidden sm:inline">{t('profile.paymentTab')}</span>
              <span className="sm:hidden">Payment</span>
              {!user?.has_payment_method && (
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse flex-shrink-0" title="Action required"></span>
              )}
            </TabsTrigger>
            <TabsTrigger 
              value="subscription" 
              data-testid="subscription-tab"
              className="flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium data-[state=active]:bg-white data-[state=active]:dark:bg-slate-700 data-[state=active]:shadow-sm data-[state=active]:text-blue-600 data-[state=active]:dark:text-blue-400 text-slate-500 dark:text-slate-400 transition-all"
            >
              <Crown className="h-4 w-4" />
              <span className="hidden sm:inline">{t('profile.subscription')}</span>
              <span className="sm:hidden">Plans</span>
            </TabsTrigger>
            <TabsTrigger 
              value="notifications" 
              data-testid="notifications-tab"
              className="flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium data-[state=active]:bg-white data-[state=active]:dark:bg-slate-700 data-[state=active]:shadow-sm data-[state=active]:text-blue-600 data-[state=active]:dark:text-blue-400 text-slate-500 dark:text-slate-400 transition-all"
            >
              <Bell className="h-4 w-4" />
              <span className="hidden sm:inline">{t('profile.notificationsTab')}</span>
              <span className="sm:hidden">Alerts</span>
            </TabsTrigger>
            <TabsTrigger 
              value="security" 
              data-testid="security-tab"
              className="flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium data-[state=active]:bg-white data-[state=active]:dark:bg-slate-700 data-[state=active]:shadow-sm data-[state=active]:text-blue-600 data-[state=active]:dark:text-blue-400 text-slate-500 dark:text-slate-400 transition-all"
            >
              <Lock className="h-4 w-4" />
              <span className="hidden sm:inline">Security</span>
              <span className="sm:hidden">Security</span>
            </TabsTrigger>
          </TabsList>

          {/* Trust Status Card — Glass Style */}
          <div className="rounded-2xl bg-white/70 dark:bg-slate-800/50 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 shadow-sm p-4 sm:p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
                  <Shield className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="font-semibold text-sm text-slate-900 dark:text-white">
                    {t('profile.trustStatus') || 'Trust Status'}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {t('profile.completeVerification') || 'Complete verification to bid and sell'}
                  </p>
                </div>
              </div>
              <TrustBadge 
                phoneVerified={user?.phone_verified} 
                hasPaymentMethod={user?.has_payment_method}
                size="default"
              />
            </div>
              
              {/* Action prompts for incomplete verification */}
              {(!user?.phone_verified || !user?.has_payment_method) && (
                <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700 flex flex-wrap gap-3">
                  {!user?.phone_verified && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => window.location.href = '/verify-phone'}
                      className="border-[#06B6D4] text-[#06B6D4] hover:bg-[#06B6D4]/10"
                      data-testid="verify-phone-btn"
                    >
                      <Phone className="h-4 w-4 mr-2" />
                      {t('profile.verifyPhone') || 'Verify Phone'}
                    </Button>
                  )}
                  {!user?.has_payment_method && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleAddPaymentClick}
                      className="border-[#1E3A8A] text-[#1E3A8A] hover:bg-[#1E3A8A]/10"
                    >
                      <CreditCard className="h-4 w-4 mr-2" />
                      {t('profile.addPayment') || 'Add Payment'}
                    </Button>
                  )}
                </div>
              )}
              {/* iter217 — Phone-verify explainer */}
              {!user?.phone_verified && (
                <p
                  className="text-[11px] mt-2 leading-relaxed"
                  style={{ color: '#94a3b8' }}
                  data-testid="phone-verify-explain"
                >
                  {t('paymentTrust.phoneExplain', 'We send a one-time code to confirm your number. This helps prevent fake accounts.')}
                </p>
              )}
          </div>

          <TabsContent value="profile">
            <div className="rounded-2xl bg-white/70 dark:bg-slate-800/50 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 shadow-sm">
              <CardHeader>
                <CardTitle>{t('profile.personalInformation')}</CardTitle>
                <CardDescription>{t('profile.updateDetails')}</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleProfileUpdate} className="space-y-6">
                  <AvatarUpload 
                    currentAvatar={user?.picture}
                    onAvatarUpdate={handleAvatarUpdate}
                  />
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">{t('profile.fullName')}</Label>
                      <Input
                        id="name"
                        value={profileData.name}
                        onChange={(e) => setProfileData({ ...profileData, name: e.target.value })}
                        data-testid="name-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="phone">{t('profile.phoneNumber')}</Label>
                      <Input
                        id="phone"
                        type="tel"
                        value={profileData.phone}
                        onChange={(e) => setProfileData({ ...profileData, phone: e.target.value })}
                        data-testid="phone-input"
                      />
                    </div>
                  </div>

                  {/* Email — read-only with Change Email button */}
                  <div className="space-y-2" data-testid="email-section">
                    <Label htmlFor="email">{t('profile.email', 'Email')}</Label>
                    <div className="flex flex-col sm:flex-row gap-2">
                      <Input
                        id="email"
                        type="email"
                        value={profileData.email}
                        readOnly
                        className="flex-1 bg-slate-50 dark:bg-slate-800/50"
                        data-testid="email-input"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setShowEmailChange(true)}
                        data-testid="open-email-change-btn"
                        className="whitespace-nowrap"
                      >
                        {t('profile.changeEmail', 'Change Email')}
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {t('profile.emailVerifyNotice', 'Changing your email requires verification at the new address (Law 25 compliance).')}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="address">{t('profile.address')}</Label>
                    <Input
                      id="address"
                      value={profileData.address}
                      onChange={(e) => setProfileData({ ...profileData, address: e.target.value })}
                      data-testid="address-input"
                    />
                  </div>

                  {/* Province — Canadian provinces dropdown */}
                  <div className="space-y-2">
                    <Label htmlFor="province">{t('profile.province', 'Province / Territory')}</Label>
                    <select
                      id="province"
                      value={profileData.province}
                      onChange={(e) => setProfileData({ ...profileData, province: e.target.value })}
                      className="w-full px-3 py-2 border border-input rounded-md bg-background"
                      data-testid="province-select"
                    >
                      <option value="">{t('profile.selectProvince', 'Select province / territory...')}</option>
                      <option value="AB">Alberta</option>
                      <option value="BC">British Columbia / Colombie-Britannique</option>
                      <option value="MB">Manitoba</option>
                      <option value="NB">New Brunswick / Nouveau-Brunswick</option>
                      <option value="NL">Newfoundland and Labrador / Terre-Neuve-et-Labrador</option>
                      <option value="NS">Nova Scotia / Nouvelle-Écosse</option>
                      <option value="NT">Northwest Territories / Territoires du Nord-Ouest</option>
                      <option value="NU">Nunavut</option>
                      <option value="ON">Ontario</option>
                      <option value="PE">Prince Edward Island / Île-du-Prince-Édouard</option>
                      <option value="QC">Québec</option>
                      <option value="SK">Saskatchewan</option>
                      <option value="YT">Yukon</option>
                    </select>
                  </div>

                  {user?.account_type === 'business' && (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="company_name">{t('profile.companyName')}</Label>
                        <Input
                          id="company_name"
                          value={profileData.company_name}
                          onChange={(e) => setProfileData({ ...profileData, company_name: e.target.value })}
                          data-testid="company-name-input"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="tax_number">{t('profile.taxNumber')}</Label>
                        <Input
                          id="tax_number"
                          value={profileData.tax_number}
                          onChange={(e) => setProfileData({ ...profileData, tax_number: e.target.value })}
                          data-testid="tax-number-input"
                        />
                      </div>
                    </>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="language" className="flex items-center gap-2">
                        <Globe className="h-4 w-4" />
                        {t('profile.language')}
                      </Label>
                      <select
                        id="language"
                        value={profileData.preferred_language}
                        onChange={(e) => setProfileData({ ...profileData, preferred_language: e.target.value })}
                        className="w-full px-3 py-2 border border-input rounded-md bg-background"
                        data-testid="language-select"
                      >
                        <option value="en">{t('profile.english')}</option>
                        <option value="fr">{t('profile.french')}</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="currency" className="flex items-center gap-2">
                        <DollarSign className="h-4 w-4" />
                        {t('profile.currency')}
                        {user?.currency_locked && (
                          <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">
                            🔒 {t('currency.locked')}
                          </span>
                        )}
                      </Label>
                      <select
                        id="currency"
                        value={profileData.preferred_currency}
                        onChange={(e) => setProfileData({ ...profileData, preferred_currency: e.target.value })}
                        className="w-full px-3 py-2 border border-input rounded-md bg-background"
                        data-testid="currency-select"
                        disabled={user?.currency_locked}
                      >
                        <option value="CAD">🇨🇦 {t('common.cad')}</option>
                        <option value="USD">🇺🇸 {t('common.usd')}</option>
                      </select>
                      {user?.currency_locked && (
                        <div className="text-sm p-3 bg-blue-50 border border-blue-200 rounded-md">
                          <p className="text-blue-800 mb-2">
                            💡 {t('currency.complianceMessage')}
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => window.location.href = '/currency-appeal'}
                            className="text-blue-600 hover:text-blue-700"
                          >
                            {t('currency.requestChange')}
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>

                  <Button
                    type="submit"
                    className="gradient-button text-white border-0"
                    disabled={loading}
                    data-testid="save-profile-btn"
                  >
                    {loading ? (
                      <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> {t('common.loading')}</>
                    ) : (
                      t('profile.saveChanges')
                    )}
                  </Button>
                </form>
              </CardContent>
            </div>
          </TabsContent>

          <TabsContent value="payment">
            <div className="rounded-2xl bg-white/70 dark:bg-slate-800/50 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Shield className="h-5 w-5 text-blue-500" />{t('profile.paymentMethods', 'Payment Methods')}</CardTitle>
                <CardDescription>{t("profile.managePaymentMethods")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* iter217 — Trust messaging above the Add Payment Method block */}
                <PaymentTrustBox />

                {paymentMethods.length > 0 ? (
                  <div className="space-y-3">
                    {paymentMethods.map((method) => (
                      <div key={method.id} className="p-4 border rounded-lg" data-testid={`payment-method-${method.id}`}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <CreditCard className="h-8 w-8 text-muted-foreground" />
                            <div>
                              <p className="font-medium capitalize">{method.card_brand} •••• {method.last4}</p>
                              <p className="text-sm text-muted-foreground">
                                {method.exp_month}/{method.exp_year}
                                {method.is_verified && <span className="ml-2 text-green-600">✓ {t('common.verified', 'Verified')}</span>}
                              </p>
                              {method.created_at && (
                                <p className="text-xs text-muted-foreground mt-0.5">
                                  {t('paymentTrust.savedAddedOn', { date: new Date(method.created_at).toLocaleDateString(), defaultValue: 'Added on {{date}}' })}
                                </p>
                              )}
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeletePaymentMethod(method.id)}
                            data-testid={`delete-payment-method-${method.id}`}
                            className="text-slate-500 hover:text-red-600 hover:bg-red-50"
                          >
                            <Trash2 className="h-4 w-4 mr-1" />
                            {t('paymentTrust.removeCardBtn', 'Remove Card')}
                          </Button>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-3 pl-12">
                          {t('paymentTrust.savedCardExplain', 'This card is used for bid security verification only. You will be notified before any charge.')}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : null}

                {!showAddCard && (
                  <Button
                    onClick={() => setShowAddCard(true)}
                    className="w-full"
                    variant="outline"
                    data-testid="add-payment-method-btn"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    {t('profile.addPaymentMethod', 'Add Payment Method')}
                  </Button>
                )}

                {showAddCard && (
                  <Card className="border-2 border-primary">
                    <CardContent className="pt-6">
                      <p className="text-xs font-medium mb-2" style={{ color: '#475569' }}>
                        {t('paymentTrust.addFormLabel', 'Enter your card details — you will not be charged now.')}
                      </p>
                      <Elements stripe={stripePromise}>
                        <AddCardForm 
                          onSuccess={async () => {
                            setShowAddCard(false);
                            fetchPaymentMethods();
                            // Refresh user to update has_payment_method flag
                            if (refreshUser) {
                              await refreshUser();
                            }
                          }}
                          onCancel={() => setShowAddCard(false)}
                        />
                      </Elements>
                      <p className="text-[11px] mt-3 leading-relaxed" style={{ color: '#94a3b8' }}>
                        {t('paymentTrust.addFormDisclaimer', 'By saving, you agree to our Terms of Service. Your card will only be charged when you win and confirm a purchase.')}
                      </p>
                    </CardContent>
                  </Card>
                )}
              </CardContent>
            </div>
          </TabsContent>

          <TabsContent value="notifications">
            <div className="rounded-2xl bg-white/70 dark:bg-slate-800/50 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-slate-900 dark:text-white"><Bell className="h-5 w-5 text-blue-500" />{t('profileSettings.notifPrefs')}</CardTitle>
                <CardDescription className="text-slate-600 dark:text-slate-400">{t('profileSettings.notifPrefsDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{t('profileSettings.emailSummaries')}</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">{t('profileSettings.emailSummariesDesc')}</p>
                    </div>
                    <Switch
                      checked={notificationSettings.email_summaries}
                      onCheckedChange={handleToggleNotification('email_summaries')}
                      disabled={notifSettingsSaving}
                      data-testid="notif-toggle-email-summaries"
                      className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600"
                    />
                  </div>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{t('profileSettings.bidNotifs')}</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">{t('profileSettings.bidNotifsDesc')}</p>
                    </div>
                    <Switch
                      checked={notificationSettings.bid_alerts}
                      onCheckedChange={handleToggleNotification('bid_alerts')}
                      disabled={notifSettingsSaving}
                      data-testid="notif-toggle-bid-alerts"
                      className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600"
                    />
                  </div>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{t('profileSettings.messageNotifs')}</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">{t('profileSettings.messageNotifsDesc')}</p>
                    </div>
                    <Switch
                      checked={notificationSettings.message_alerts}
                      onCheckedChange={handleToggleNotification('message_alerts')}
                      disabled={notifSettingsSaving}
                      data-testid="notif-toggle-message-alerts"
                      className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600"
                    />
                  </div>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{t('profileSettings.auctionWins')}</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">{t('profileSettings.auctionWinsDesc')}</p>
                    </div>
                    <Switch
                      checked={notificationSettings.auction_win_alerts}
                      onCheckedChange={handleToggleNotification('auction_win_alerts')}
                      disabled={notifSettingsSaving}
                      data-testid="notif-toggle-auction-win-alerts"
                      className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600"
                    />
                  </div>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 px-1">
                    {notifSettingsSaving ? 'Saving…' : 'Changes save automatically.'}
                  </p>
                </div>

                {/* Push Notifications */}
                <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">{t('profileSettings.pushNotifs')}</h3>
                  <PushNotificationToggle variant="settings" />
                  <p className="text-xs text-slate-500 dark:text-slate-500 mt-2 pl-1">
                    {t('profileSettings.pushNotifsDesc')}
                  </p>
                </div>

                {/* Personalized Recommendations */}
                <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Privacy &amp; AI</h3>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700" data-testid="recommendations-toggle-row">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">Personalized Recommendations</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">{t('profileSettings.aiSuggestionsDesc')}</p>
                    </div>
                    <Switch
                      checked={recommendationsEnabled}
                      onCheckedChange={handleToggleRecommendations}
                      className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600"
                      data-testid="recommendations-toggle"
                    />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-500 mt-2 pl-1">
                    Disabling this will not affect core bidding or platform functionality. See our <a href="/legal#privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">Privacy Policy (Section 6)</a> for details.
                  </p>
                </div>
              </CardContent>
            </div>
          </TabsContent>

          {/* Subscription Tab */}
          <TabsContent value="subscription">
            <div className="rounded-2xl bg-white/70 dark:bg-slate-800/50 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Crown className="h-5 w-5 text-yellow-500" />
                  Subscription Management
                </CardTitle>
                <CardDescription>
                  {t('profileSettings.upgradeDesc')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                {/* Current Subscription Status */}
                <div className="p-6 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-xl border border-purple-200 dark:border-purple-800">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <p className="text-sm text-muted-foreground mb-2">Current Plan</p>
                      <div className="flex items-center gap-3">
                        <SubscriptionBadge tier={user?.subscription_tier || 'free'} size="large" />
                        <span className="text-2xl font-bold capitalize">{user?.subscription_tier || 'Free'} Tier</span>
                      </div>
                    </div>
                    {user?.subscription_status && (
                      <div className="text-right">
                        <p className="text-sm text-muted-foreground mb-1">Status</p>
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                          user.subscription_status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                        }`}>
                          {user.subscription_status === 'active' ? '✓ Active' : user.subscription_status}
                        </span>
                      </div>
                    )}
                  </div>
                  {user?.subscription_end_date && (
                    <p className="text-sm text-muted-foreground">
                      {user.subscription_status === 'active' 
                        ? `Renews on ${new Date(user.subscription_end_date).toLocaleDateString()}`
                        : `Expired on ${new Date(user.subscription_end_date).toLocaleDateString()}`
                      }
                    </p>
                  )}
                </div>

                {/* Subscription Management Panel */}
                <SubscriptionManagement />

                {/* iter254 Mission 1 — B2B Partner Program coupon
                    activation. The component self-gates on B2B role. */}
                <B2BCouponActivationCard />

                {/* Show PartnerLicenseCard for partners, UserTierGrid for regular users */}
                {user?.is_partner ? (
                  <PartnerLicenseCard user={user} />
                ) : (
                  <UserTierGrid currentTier={user?.subscription_tier || 'free'} />
                )}

                {/* Personalized Savings Calculator */}
                <PersonalizedSavingsCalculator currentTier={user?.subscription_tier || 'free'} />
              </CardContent>
            </div>
          </TabsContent>

          {/* Security / Change Password Tab */}
          <TabsContent value="security">
            <ChangePasswordForm />
          </TabsContent>
          {/* Email Change Modal */}
          {showEmailChange && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" data-testid="email-change-modal">
              <Card className="w-full max-w-md">
                <CardHeader>
                  <CardTitle>{t('profile.changeEmail', 'Change Email')}</CardTitle>
                  <CardDescription>
                    {t('profile.emailChangeNotice', 'A confirmation link will be sent to your new email. Your email will only change after you click the link.')}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {!emailChangeRequested ? (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="new-email-input">{t('profile.newEmail', 'New email address')}</Label>
                        <Input
                          id="new-email-input"
                          type="email"
                          value={newEmail}
                          onChange={(e) => setNewEmail(e.target.value)}
                          placeholder="you@example.com"
                          data-testid="new-email-input"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="email-change-pwd">{t('profile.confirmPassword', 'Confirm with current password')}</Label>
                        <Input
                          id="email-change-pwd"
                          type="password"
                          value={emailChangePassword}
                          onChange={(e) => setEmailChangePassword(e.target.value)}
                          placeholder="••••••••"
                          data-testid="email-change-password-input"
                        />
                      </div>
                      <div className="flex flex-col sm:flex-row gap-2 pt-2">
                        <Button
                          onClick={async () => {
                            if (!newEmail || !emailChangePassword) {
                              toast.error(t('profile.fillBothFields', 'Please fill in both fields.'));
                              return;
                            }
                            setEmailChangeLoading(true);
                            try {
                              const r = await axios.post(`${API}/auth/email-change/request`, {
                                new_email: newEmail,
                                current_password: emailChangePassword,
                              });
                              toast.success(r.data?.message || 'Verification link sent.');
                              setEmailChangeRequested(true);
                            } catch (err) {
                              toast.error(err?.response?.data?.detail || t('common.error'));
                            } finally {
                              setEmailChangeLoading(false);
                            }
                          }}
                          disabled={emailChangeLoading}
                          className="flex-1"
                          data-testid="submit-email-change-btn"
                        >
                          {emailChangeLoading ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />{t('common.loading')}</> : t('profile.sendVerification', 'Send verification link')}
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => { setShowEmailChange(false); setNewEmail(''); setEmailChangePassword(''); }}
                          data-testid="cancel-email-change-btn"
                        >
                          {t('common.cancel', 'Cancel')}
                        </Button>
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-6 space-y-4">
                      <div className="text-emerald-600 mx-auto">
                        <Check className="h-12 w-12 mx-auto" />
                      </div>
                      <p className="text-sm">
                        {t('profile.emailLinkSent', 'Verification link sent to')} <strong>{newEmail}</strong>.
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t('profile.emailCheckInbox', 'Check your inbox and click the link within 24 hours to confirm. Your current email remains active until then.')}
                      </p>
                      <Button
                        onClick={() => { setShowEmailChange(false); setNewEmail(''); setEmailChangePassword(''); setEmailChangeRequested(false); }}
                        className="w-full"
                        data-testid="close-email-change-confirmation-btn"
                      >
                        {t('common.close', 'Close')}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </Tabs>
      </div>
    </div>
  );
};

const ChangePasswordForm = () => {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [loading, setLoading] = useState(false);

  const passwordChecks = [
    { label: 'At least 8 characters', met: newPassword.length >= 8 },
    { label: 'Contains an uppercase letter', met: /[A-Z]/.test(newPassword) },
    { label: 'Contains a number', met: /\d/.test(newPassword) },
    { label: 'Passwords match', met: newPassword && confirmPassword && newPassword === confirmPassword },
  ];
  const allMet = passwordChecks.every(c => c.met);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!allMet) {
      toast.error('Please meet all password requirements');
      return;
    }
    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/change-password`, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      if (res.data.success) {
        toast.success(res.data.message || 'Password updated successfully');
        setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Failed to change password';
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl bg-white/70 dark:bg-slate-800/50 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Lock className="h-5 w-5 text-blue-600" />
          {t('profileSettings.changePassword')}
        </CardTitle>
        <CardDescription>{t('profileSettings.changePasswordDesc')}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-5 max-w-md">
          {/* Current Password */}
          <div className="space-y-2">
            <Label htmlFor="current-password">{t('profileSettings.currentPassword')}</Label>
            <div className="relative">
              <Input
                id="current-password"
                data-testid="current-password-input"
                type={showCurrent ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder={t('profileSettings.enterCurrentPassword')}
                required
                className="pr-10"
              />
              <button type="button" onClick={() => setShowCurrent(!showCurrent)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* New Password */}
          <div className="space-y-2">
            <Label htmlFor="new-password">{t('profileSettings.newPassword')}</Label>
            <div className="relative">
              <Input
                id="new-password"
                data-testid="new-password-input"
                type={showNew ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder={t('profileSettings.enterNewPassword')}
                required
                className="pr-10"
              />
              <button type="button" onClick={() => setShowNew(!showNew)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Confirm New Password */}
          <div className="space-y-2">
            <Label htmlFor="confirm-password">{t('profileSettings.confirmNewPassword')}</Label>
            <Input
              id="confirm-password"
              data-testid="confirm-password-input"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder={t('profileSettings.confirmNewPasswordPh')}
              required
            />
          </div>

          {/* Strength Checklist */}
          {newPassword && (
            <div className="space-y-1.5 p-3 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200/60 dark:border-slate-700/40">
              {passwordChecks.map((c, i) => (
                <div key={i} className={`flex items-center gap-2 text-xs ${c.met ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}>
                  {c.met ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                  {c.label}
                </div>
              ))}
            </div>
          )}

          <Button
            type="submit"
            data-testid="change-password-submit"
            disabled={loading || !allMet || !currentPassword}
            className="w-full sm:w-auto"
          >
            {loading ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Updating...</> : 'Update Password'}
          </Button>
        </form>
      </CardContent>
    </div>
  );
};

const AddCardForm = ({ onSuccess, onCancel }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const { t } = useTranslation();

  // iter283-payments-audit Mission 1A — Switched from
  // `stripe.createPaymentMethod()` to `stripe.confirmCardSetup()`
  // with a SetupIntent + `usage="off_session"`. This:
  //   • Verifies the card is usable for off-session charges (the
  //     way our deposit/auto-capture flows actually use it).
  //   • Completes 3DS / SCA in-flow so we don't fail later when
  //     a Quebec/EU bank requires 3DS at deposit-hold time.
  //   • Attaches the PaymentMethod to the Customer automatically
  //     — no separate PaymentMethod.attach call needed.
  // Raw PAN never leaves the browser (still goes through Stripe
  // Elements `CardElement` as before).
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setLoading(true);
    try {
      // 1) Backend creates a SetupIntent + ensures the Customer exists.
      const setupRes = await axios.post(`${API}/payments/setup-intent`);
      const clientSecret = setupRes.data?.client_secret;
      if (!clientSecret) {
        toast.error(t('paymentTrust.cardAddFailed',
          'Failed to add payment method'));
        return;
      }

      // 2) Stripe confirms the card off-session (handles 3DS).
      const { error, setupIntent } = await stripe.confirmCardSetup(
        clientSecret,
        {
          payment_method: { card: elements.getElement(CardElement) },
        },
      );

      if (error) {
        toast.error(error.message);
        return;
      }

      const paymentMethodId =
        setupIntent?.payment_method ||
        (typeof setupIntent?.payment_method === 'object'
          ? setupIntent.payment_method.id
          : null);

      if (!paymentMethodId) {
        toast.error(t('paymentTrust.cardAddFailed',
          'Failed to add payment method'));
        return;
      }

      // 3) Backend persists PM metadata + flips trust_status.
      await axios.post(`${API}/payments/payment-methods`, {
        payment_method_id: paymentMethodId,
      });
      toast.success(t('paymentTrust.cardAddedSuccess',
        'Payment method added successfully!'));
      onSuccess();
    } catch (error) {
      const detail = error?.response?.data?.detail || error?.message || 'Unknown error';
      console.error('Add payment method failed:', detail, error);
      toast.error(`${t('paymentTrust.cardAddFailed', 'Failed to add payment method')}: ${detail}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="p-4 border rounded-md">
        <CardElement
          options={{
            style: {
              base: {
                fontSize: '16px',
                color: '#424770',
                '::placeholder': {
                  color: '#aab7c4',
                },
              },
              invalid: {
                color: '#9e2146',
              },
            },
          }}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={!stripe || loading} className="flex-1" data-testid="save-card-securely-btn">
          {loading
            ? t('paymentTrust.savingCard', 'Saving…')
            : <>{t('paymentTrust.saveCardBtn', 'Save Card Securely')} <span aria-hidden>→</span></>}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('common.cancel', 'Cancel')}
        </Button>
      </div>
    </form>
  );
};

export default ProfileSettingsPage;
