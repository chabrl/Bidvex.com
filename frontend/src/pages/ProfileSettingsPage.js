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
import { User, CreditCard, Bell, MapPin, Loader2, Plus, Trash2, Globe, DollarSign, Crown, Star, Check, X, Bot, TrendingUp, Shield, Phone } from 'lucide-react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import AvatarUpload from '../components/AvatarUpload';
import SubscriptionBadge from '../components/SubscriptionBadge';
import TrustBadge from '../components/TrustBadge';
import TrendySubscriptionCards from '../components/TrendySubscriptionCards';
import PersonalizedSavingsCalculator from '../components/PersonalizedSavingsCalculator';
import { useTranslation } from 'react-i18next';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const stripePromise = loadStripe('pk_test_51QEYhKP5VxaDuxPQiPLqHBcPrU7VrDu0YnPRCd5RPBSH9QdPQmOTmDo5r9mglvLbJ0P3WfCqxZ5c6Wb8fh0xdvl800nZdMLCqZ');

const ProfileSettingsPage = () => {
  const { user, updateUserPreferences, refreshUser } = useAuth();
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const defaultTab = searchParams.get('tab') || 'profile';
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [profileData, setProfileData] = useState({
    name: '',
    phone: '',
    address: '',
    company_name: '',
    tax_number: '',
    preferred_language: 'en',
    preferred_currency: 'CAD',
  });
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [showAddCard, setShowAddCard] = useState(false);

  // Handler to switch to payment tab and open add card form
  const handleAddPaymentClick = () => {
    setActiveTab('payment');
    setShowAddCard(true);
  };

  useEffect(() => {
    if (user) {
      setProfileData({
        name: user.name || '',
        phone: user.phone || '',
        address: user.address || '',
        company_name: user.company_name || '',
        tax_number: user.tax_number || '',
        preferred_language: user.preferred_language || 'en',
        preferred_currency: user.preferred_currency || 'CAD',
      });
      fetchPaymentMethods();
    }
  }, [user]);

  const fetchPaymentMethods = async () => {
    try {
      const response = await axios.get(`${API}/payment-methods`);
      setPaymentMethods(response.data);
    } catch (error) {
      console.error('Failed to fetch payment methods:', error);
    }
  };

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await updateUserPreferences(profileData);
      toast.success(t('profile.changesSaved'));
    } catch (error) {
      toast.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const handleAvatarUpdate = async (avatarDataUrl) => {
    await axios.put(`${API}/profile`, { picture: avatarDataUrl });
  };

  const handleDeletePaymentMethod = async (methodId) => {
    if (window.confirm(t('payment.confirmDelete'))) {
      try {
        await axios.delete(`${API}/payment-methods/${methodId}`);
        toast.success(t('payment.cardDeleted'));
        fetchPaymentMethods();
      } catch (error) {
        toast.error(t('payment.cardDeleteFailed'));
      }
    }
  };

  return (
    <div className="min-h-screen py-8 px-4 bg-slate-50 dark:bg-slate-900" data-testid="profile-settings-page">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6" style={{ color: '#1a1a1a' }}>
          {t('profile.accountSettings')}
        </h1>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          {/* Professional Tab Navigation - Flat Design */}
          <TabsList className="flex w-full bg-transparent border-b-2 border-slate-200 dark:border-slate-700">
            <TabsTrigger 
              value="profile" 
              data-testid="profile-tab"
            >
              <User className="h-[18px] w-[18px]" />
              {t('profile.profileTab')}
            </TabsTrigger>
            <TabsTrigger 
              value="payment" 
              data-testid="payment-tab"
            >
              <CreditCard className="h-[18px] w-[18px]" />
              {t('profile.paymentTab')}
              {!user?.has_payment_method && (
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" title="Action required"></span>
              )}
            </TabsTrigger>
            <TabsTrigger 
              value="subscription" 
              data-testid="subscription-tab"
            >
              <Crown className="h-[18px] w-[18px]" />
              Subscription
            </TabsTrigger>
            <TabsTrigger 
              value="notifications" 
              data-testid="notifications-tab"
            >
              <Bell className="h-[18px] w-[18px]" />
              {t('profile.notificationsTab')}
            </TabsTrigger>
          </TabsList>

          {/* Trust Status Card */}
          <Card className="bg-gradient-to-r from-slate-50 to-cyan-50 dark:from-slate-900 dark:to-cyan-900/20 border-slate-200 dark:border-slate-700">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] flex items-center justify-center">
                    <Shield className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <p className="font-medium" style={{ color: '#1a1a1a' }}>
                      {t('profile.trustStatus') || 'Trust Status'}
                    </p>
                    <p className="text-sm" style={{ color: '#64748b' }}>
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
            </CardContent>
          </Card>

          <TabsContent value="profile">
            <Card className="glassmorphism">
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

                  <div className="space-y-2">
                    <Label htmlFor="address">{t('profile.address')}</Label>
                    <Input
                      id="address"
                      value={profileData.address}
                      onChange={(e) => setProfileData({ ...profileData, address: e.target.value })}
                      data-testid="address-input"
                    />
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
            </Card>
          </TabsContent>

          <TabsContent value="payment">
            <Card className="glassmorphism">
              <CardHeader>
                <CardTitle>Payment Methods</CardTitle>
                <CardDescription>Manage your payment methods for bidding</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {paymentMethods.length > 0 ? (
                  <div className="space-y-3">
                    {paymentMethods.map((method) => (
                      <div key={method.id} className="flex items-center justify-between p-4 border rounded-lg" data-testid={`payment-method-${method.id}`}>
                        <div className="flex items-center gap-4">
                          <CreditCard className="h-8 w-8 text-muted-foreground" />
                          <div>
                            <p className="font-medium capitalize">{method.card_brand} •••• {method.last4}</p>
                            <p className="text-sm text-muted-foreground">
                              Expires {method.exp_month}/{method.exp_year}
                              {method.is_verified && <span className="ml-2 text-green-600">✓ Verified</span>}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeletePaymentMethod(method.id)}
                          data-testid={`delete-payment-method-${method.id}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <CreditCard className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <p className="text-muted-foreground mb-4">No payment methods added</p>
                  </div>
                )}

                <Button
                  onClick={() => setShowAddCard(true)}
                  className="w-full"
                  variant="outline"
                  data-testid="add-payment-method-btn"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add Payment Method
                </Button>

                {showAddCard && (
                  <Card className="border-2 border-primary">
                    <CardContent className="pt-6">
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
                    </CardContent>
                  </Card>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="notifications">
            <Card className="glassmorphism">
              <CardHeader>
                <CardTitle className="text-slate-900 dark:text-white">Notification Preferences</CardTitle>
                <CardDescription className="text-slate-600 dark:text-slate-400">Choose how you want to be notified</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">Email Notifications</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">Receive updates via email</p>
                    </div>
                    <Switch defaultChecked className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600" />
                  </div>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">Bid Notifications</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">Get notified when someone bids on your items</p>
                    </div>
                    <Switch defaultChecked className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600" />
                  </div>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">Message Notifications</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">Get notified of new messages</p>
                    </div>
                    <Switch defaultChecked className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600" />
                  </div>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">Auction Wins</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">Get notified when you win an auction</p>
                    </div>
                    <Switch defaultChecked className="data-[state=checked]:bg-blue-600 data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Subscription Tab */}
          <TabsContent value="subscription">
            <Card className="glassmorphism">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Crown className="h-5 w-5 text-yellow-500" />
                  Subscription Management
                </CardTitle>
                <CardDescription>
                  Upgrade your plan to unlock premium features and lower fees
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

                {/* Trendy Subscription Cards */}
                <TrendySubscriptionCards currentTier={user?.subscription_tier || 'free'} />

                {/* Personalized Savings Calculator */}
                <PersonalizedSavingsCalculator currentTier={user?.subscription_tier || 'free'} />

                {/* Billing Info */}
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    💳 <strong>Payment Integration:</strong> Stripe checkout will be integrated in the next phase. 
                    For now, upgrades are managed by administrators.
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

const AddCardForm = ({ onSuccess, onCancel }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setLoading(true);
    try {
      const { error, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: elements.getElement(CardElement),
      });

      if (error) {
        toast.error(error.message);
      } else {
        await axios.post(`${API}/payment-methods`, {
          payment_method_id: paymentMethod.id,
        });
        toast.success('Payment method added successfully!');
        onSuccess();
      }
    } catch (error) {
      toast.error('Failed to add payment method');
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
        <Button type="submit" disabled={!stripe || loading} className="flex-1">
          {loading ? 'Adding...' : 'Add Card'}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
};

export default ProfileSettingsPage;
