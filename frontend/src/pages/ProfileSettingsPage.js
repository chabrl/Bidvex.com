import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { User, CreditCard, Bell, MapPin, Loader2, Plus, Trash2, Globe, DollarSign, Crown, Star, Check, X, Zap, Bot } from 'lucide-react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import AvatarUpload from '../components/AvatarUpload';
import SubscriptionBadge from '../components/SubscriptionBadge';
import { useTranslation } from 'react-i18next';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const stripePromise = loadStripe('pk_test_51QEYhKP5VxaDuxPQiPLqHBcPrU7VrDu0YnPRCd5RPBSH9QdPQmOTmDo5r9mglvLbJ0P3WfCqxZ5c6Wb8fh0xdvl800nZdMLCqZ');

const ProfileSettingsPage = () => {
  const { user, updateUserPreferences } = useAuth();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
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
    <div className="min-h-screen py-8 px-4" data-testid="profile-settings-page">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">{t('profile.accountSettings')}</h1>

        <Tabs defaultValue="profile" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="profile" data-testid="profile-tab">
              <User className="mr-2 h-4 w-4" />
              {t('profile.profileTab')}
            </TabsTrigger>
            <TabsTrigger value="payment" data-testid="payment-tab">
              <CreditCard className="mr-2 h-4 w-4" />
              {t('profile.paymentTab')}
            </TabsTrigger>
            <TabsTrigger value="subscription" data-testid="subscription-tab">
              <Crown className="mr-2 h-4 w-4" />
              Subscription
            </TabsTrigger>
            <TabsTrigger value="notifications" data-testid="notifications-tab">
              <Bell className="mr-2 h-4 w-4" />
              {t('profile.notificationsTab')}
            </TabsTrigger>
          </TabsList>

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
                          onSuccess={() => {
                            setShowAddCard(false);
                            fetchPaymentMethods();
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
                <CardTitle>Notification Preferences</CardTitle>
                <CardDescription>Choose how you want to be notified</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Email Notifications</p>
                      <p className="text-sm text-muted-foreground">Receive updates via email</p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Bid Notifications</p>
                      <p className="text-sm text-muted-foreground">Get notified when someone bids on your items</p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Message Notifications</p>
                      <p className="text-sm text-muted-foreground">Get notified of new messages</p>
                    </div>
                    <Switch defaultChecked />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">Auction Wins</p>
                      <p className="text-sm text-muted-foreground">Get notified when you win an auction</p>
                    </div>
                    <Switch defaultChecked />
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
                  Manage your subscription tier and features
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Current Subscription Status */}
                <div className="p-6 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
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

                {/* Feature Comparison Table */}
                <div>
                  <h3 className="text-lg font-semibold mb-4">Compare Plans</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left p-4 font-semibold">Feature</th>
                          <th className="text-center p-4 font-semibold bg-gray-50 dark:bg-gray-900">
                            <div className="flex flex-col items-center gap-2">
                              <SubscriptionBadge tier="free" size="small" />
                              <span className="text-lg font-bold">$0</span>
                              <span className="text-xs text-muted-foreground">/month</span>
                            </div>
                          </th>
                          <th className="text-center p-4 font-semibold bg-purple-50 dark:bg-purple-900/20">
                            <div className="flex flex-col items-center gap-2">
                              <SubscriptionBadge tier="premium" size="small" />
                              <span className="text-lg font-bold">$9.99</span>
                              <span className="text-xs text-muted-foreground">/month</span>
                            </div>
                          </th>
                          <th className="text-center p-4 font-semibold bg-gradient-to-r from-yellow-50 to-orange-50 dark:from-yellow-900/20 dark:to-orange-900/20">
                            <div className="flex flex-col items-center gap-2">
                              <SubscriptionBadge tier="vip" size="small" />
                              <span className="text-lg font-bold">$29.99</span>
                              <span className="text-xs text-muted-foreground">/month</span>
                            </div>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b hover:bg-gray-50 dark:hover:bg-gray-900/50">
                          <td className="p-4">Standard Bidding</td>
                          <td className="text-center p-4"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                          <td className="text-center p-4 bg-purple-50/50 dark:bg-purple-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                          <td className="text-center p-4 bg-yellow-50/50 dark:bg-yellow-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                        </tr>
                        <tr className="border-b hover:bg-gray-50 dark:hover:bg-gray-900/50">
                          <td className="p-4">Wishlist System</td>
                          <td className="text-center p-4"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                          <td className="text-center p-4 bg-purple-50/50 dark:bg-purple-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                          <td className="text-center p-4 bg-yellow-50/50 dark:bg-yellow-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                        </tr>
                        <tr className="border-b hover:bg-gray-50 dark:hover:bg-gray-900/50">
                          <td className="p-4 flex items-center gap-2">
                            <Zap className="h-4 w-4 text-purple-600" />
                            Monster Bids per Auction
                          </td>
                          <td className="text-center p-4">
                            <span className="font-semibold">1</span>
                          </td>
                          <td className="text-center p-4 bg-purple-50/50 dark:bg-purple-900/10">
                            <span className="font-semibold">Unlimited</span>
                          </td>
                          <td className="text-center p-4 bg-yellow-50/50 dark:bg-yellow-900/10">
                            <span className="font-semibold">Unlimited</span>
                          </td>
                        </tr>
                        <tr className="border-b hover:bg-gray-50 dark:hover:bg-gray-900/50">
                          <td className="p-4 flex items-center gap-2">
                            <Bot className="h-4 w-4 text-green-600" />
                            Auto-Bid Bot
                          </td>
                          <td className="text-center p-4"><X className="h-5 w-5 text-red-400 mx-auto" /></td>
                          <td className="text-center p-4 bg-purple-50/50 dark:bg-purple-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                          <td className="text-center p-4 bg-yellow-50/50 dark:bg-yellow-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                        </tr>
                        <tr className="border-b hover:bg-gray-50 dark:hover:bg-gray-900/50">
                          <td className="p-4">Priority Notifications</td>
                          <td className="text-center p-4"><X className="h-5 w-5 text-red-400 mx-auto" /></td>
                          <td className="text-center p-4 bg-purple-50/50 dark:bg-purple-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                          <td className="text-center p-4 bg-yellow-50/50 dark:bg-yellow-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                        </tr>
                        <tr className="border-b hover:bg-gray-50 dark:hover:bg-gray-900/50">
                          <td className="p-4">Early Access to Exclusive Lots</td>
                          <td className="text-center p-4"><X className="h-5 w-5 text-red-400 mx-auto" /></td>
                          <td className="text-center p-4 bg-purple-50/50 dark:bg-purple-900/10"><X className="h-5 w-5 text-red-400 mx-auto" /></td>
                          <td className="text-center p-4 bg-yellow-50/50 dark:bg-yellow-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                        </tr>
                        <tr className="hover:bg-gray-50 dark:hover:bg-gray-900/50">
                          <td className="p-4">Dedicated Support</td>
                          <td className="text-center p-4"><X className="h-5 w-5 text-red-400 mx-auto" /></td>
                          <td className="text-center p-4 bg-purple-50/50 dark:bg-purple-900/10"><X className="h-5 w-5 text-red-400 mx-auto" /></td>
                          <td className="text-center p-4 bg-yellow-50/50 dark:bg-yellow-900/10"><Check className="h-5 w-5 text-green-600 mx-auto" /></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Upgrade Buttons */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {user?.subscription_tier === 'free' && (
                    <>
                      <Button
                        className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white border-0 h-auto py-6"
                        onClick={() => toast.info('Stripe integration coming soon!')}
                      >
                        <div className="flex flex-col items-center gap-2">
                          <Star className="h-6 w-6" />
                          <div>
                            <p className="font-bold text-lg">Upgrade to Premium</p>
                            <p className="text-sm opacity-90">$9.99/month</p>
                          </div>
                        </div>
                      </Button>
                      <Button
                        className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 text-white border-0 h-auto py-6"
                        onClick={() => toast.info('Stripe integration coming soon!')}
                      >
                        <div className="flex flex-col items-center gap-2">
                          <Crown className="h-6 w-6" />
                          <div>
                            <p className="font-bold text-lg">Upgrade to VIP</p>
                            <p className="text-sm opacity-90">$29.99/month</p>
                          </div>
                        </div>
                      </Button>
                    </>
                  )}
                  {user?.subscription_tier === 'premium' && (
                    <Button
                      className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 text-white border-0 h-auto py-6"
                      onClick={() => toast.info('Stripe integration coming soon!')}
                    >
                      <div className="flex flex-col items-center gap-2">
                        <Crown className="h-6 w-6" />
                        <div>
                          <p className="font-bold text-lg">Upgrade to VIP</p>
                          <p className="text-sm opacity-90">$29.99/month</p>
                        </div>
                      </div>
                    </Button>
                  )}
                  {user?.subscription_tier === 'vip' && (
                    <div className="col-span-2 text-center p-6 bg-gradient-to-r from-yellow-50 to-orange-50 dark:from-yellow-900/20 dark:to-orange-900/20 rounded-lg border border-yellow-200">
                      <Crown className="h-12 w-12 text-yellow-500 mx-auto mb-3" />
                      <p className="text-lg font-semibold">You're on the VIP Plan!</p>
                      <p className="text-sm text-muted-foreground mt-2">
                        Enjoy all premium features and exclusive access.
                      </p>
                    </div>
                  )}
                </div>

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
