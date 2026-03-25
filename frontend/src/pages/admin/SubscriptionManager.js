import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import { Switch } from '../../components/ui/switch';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter 
} from '../../components/ui/dialog';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { 
  Crown, Star, User as UserIcon, Search, TrendingUp, DollarSign, Calendar,
  CreditCard, Settings, History, AlertTriangle, Clock, CheckCircle, XCircle,
  Plus, Minus, RefreshCw, Shield, ArrowLeft, Eye, Edit3
} from 'lucide-react';

const API = `${API_BASE}/api`;

// Plan configurations (prices will be fetched from API)
const PLANS = {
  free: { name: 'Free', color: 'gray', icon: UserIcon, price: 0 },
  premium: { name: 'Premium', color: 'purple', icon: Star, price: 0 },
  vip: { name: 'VIP', color: 'amber', icon: Crown, price: 0 }
};

const SubscriptionManager = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterPlan, setFilterPlan] = useState('all');
  const [filterSource, setFilterSource] = useState('all');
  const [stats, setStats] = useState({
    total: 0, free: 0, premium: 0, vip: 0, 
    manual: 0, stripe: 0, revenue: 0
  });
  const [planPrices, setPlanPrices] = useState({ free: 0, premium: 99.99, vip: 299.99 }); // Dynamic from API

  // Selected user state
  const [selectedUser, setSelectedUser] = useState(null);
  const [userSubscription, setUserSubscription] = useState(null);
  const [subscriptionHistory, setSubscriptionHistory] = useState([]);
  const [loadingUser, setLoadingUser] = useState(false);

  // Override dialog state
  const [overrideDialogOpen, setOverrideDialogOpen] = useState(false);
  const [overrideData, setOverrideData] = useState({
    plan: 'premium',
    duration_type: 'days', // days or custom
    duration_days: 30,
    end_date: '',
    reason: ''
  });
  const [overriding, setOverriding] = useState(false);

  // Extend dialog state
  const [extendDialogOpen, setExtendDialogOpen] = useState(false);
  const [extendData, setExtendData] = useState({
    additional_days: 30,
    reason: ''
  });
  const [extending, setExtending] = useState(false);

  // Revoke dialog state
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
  const [revokeReason, setRevokeReason] = useState('');
  const [revoking, setRevoking] = useState(false);

  useEffect(() => {
    fetchUsers();
    fetchPlanPrices();
  }, []);

  const fetchPlanPrices = async () => {
    try {
      const response = await axios.get(`${API}/subscription-plans`);
      if (response.data.success) {
        const plans = response.data.plans || [];
        const prices = { free: 0, premium: 99.99, vip: 299.99 };
        plans.forEach(p => {
          if (prices.hasOwnProperty(p.plan_id)) {
            prices[p.plan_id] = p.price_yearly || 0;
          }
        });
        setPlanPrices(prices);
      }
    } catch (error) {
      console.log('Using default prices');
    }
  };

  const fetchUsers = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/admin/users`, { headers });
      const allUsers = response.data || [];
      setUsers(allUsers);
      calculateStats(allUsers);
    } catch (error) {
      console.error('Failed to fetch users:', error);
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (userList) => {
    const free = userList.filter(u => (u.subscription_tier || 'free') === 'free').length;
    const premium = userList.filter(u => u.subscription_tier === 'premium').length;
    const vip = userList.filter(u => u.subscription_tier === 'vip').length;
    const manual = userList.filter(u => u.subscription_source === 'manual').length;
    const stripe = userList.filter(u => u.subscription_source === 'stripe' || u.stripe_subscription_id).length;
    // Use dynamic prices
    const revenue = (premium * planPrices.premium) + (vip * planPrices.vip);

    setStats({ total: userList.length, free, premium, vip, manual, stripe, revenue });
  };

  const fetchUserSubscription = async (userId) => {
    setLoadingUser(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [subRes, historyRes] = await Promise.all([
        axios.get(`${API}/admin/users/${userId}/subscription`, { headers }),
        axios.get(`${API}/admin/users/${userId}/subscription/history`, { headers })
      ]);
      setUserSubscription(subRes.data);
      setSubscriptionHistory(historyRes.data.history || []);
    } catch (error) {
      console.error('Failed to fetch user subscription:', error);
      toast.error('Failed to load subscription details');
    } finally {
      setLoadingUser(false);
    }
  };

  const selectUser = async (user) => {
    setSelectedUser(user);
    await fetchUserSubscription(user.id);
  };

  const handleOverride = async () => {
    if (!overrideData.reason.trim()) {
      toast.error('Please provide a reason for the override');
      return;
    }

    setOverriding(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const payload = {
        plan: overrideData.plan,
        reason: overrideData.reason
      };

      if (overrideData.duration_type === 'days') {
        payload.duration_days = parseInt(overrideData.duration_days);
      } else {
        payload.end_date = overrideData.end_date;
      }

      await axios.post(
        `${API}/admin/users/${selectedUser.id}/subscription/override`,
        payload,
        { headers }
      );

      toast.success(`Subscription updated to ${overrideData.plan.toUpperCase()}`);
      setOverrideDialogOpen(false);
      setOverrideData({ plan: 'premium', duration_type: 'days', duration_days: 30, end_date: '', reason: '' });
      await fetchUserSubscription(selectedUser.id);
      fetchUsers();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to override subscription';
      toast.error(message);
    } finally {
      setOverriding(false);
    }
  };

  const handleExtend = async () => {
    if (!extendData.reason.trim()) {
      toast.error('Please provide a reason for the extension');
      return;
    }

    setExtending(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(
        `${API}/admin/users/${selectedUser.id}/subscription/extend`,
        { additional_days: parseInt(extendData.additional_days), reason: extendData.reason },
        { headers }
      );

      toast.success(`Subscription extended by ${extendData.additional_days} days`);
      setExtendDialogOpen(false);
      setExtendData({ additional_days: 30, reason: '' });
      await fetchUserSubscription(selectedUser.id);
      fetchUsers();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to extend subscription';
      toast.error(message);
    } finally {
      setExtending(false);
    }
  };

  const handleRevoke = async () => {
    if (!revokeReason.trim()) {
      toast.error('Please provide a reason for revocation');
      return;
    }

    setRevoking(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(
        `${API}/admin/users/${selectedUser.id}/subscription/revoke`,
        { reason: revokeReason },
        { headers }
      );

      toast.success('Subscription revoked - user downgraded to Free');
      setRevokeDialogOpen(false);
      setRevokeReason('');
      await fetchUserSubscription(selectedUser.id);
      fetchUsers();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to revoke subscription';
      toast.error(message);
    } finally {
      setRevoking(false);
    }
  };

  // Filter users
  const filteredUsers = users.filter(user => {
    const matchesSearch = 
      user.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.email?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesPlan = filterPlan === 'all' || (user.subscription_tier || 'free') === filterPlan;
    
    const userSource = user.subscription_source || (user.stripe_subscription_id ? 'stripe' : 'manual');
    const matchesSource = filterSource === 'all' || userSource === filterSource;
    
    return matchesSearch && matchesPlan && matchesSource;
  });

  // Format date for display
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-CA', {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  };

  // User Detail Panel
  const UserDetailPanel = () => {
    if (!selectedUser) return null;
    
    const sub = userSubscription?.subscription || {};
    const stripe = userSubscription?.stripe || {};
    const override = userSubscription?.override_info || {};
    const benefits = userSubscription?.plan_benefits || {};

    return (
      <div className="space-y-4">
        {/* Back button */}
        <Button variant="ghost" onClick={() => setSelectedUser(null)} className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to List
        </Button>

        {/* User Header */}
        <Card>
          <CardContent className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold">{userSubscription?.name || selectedUser.name}</h2>
                <p className="text-muted-foreground">{userSubscription?.email || selectedUser.email}</p>
              </div>
              <div className="flex items-center gap-2">
                {sub.source === 'stripe' && (
                  <Badge className="bg-blue-500 text-white gap-1">
                    <CreditCard className="h-3 w-3" /> Stripe
                  </Badge>
                )}
                {sub.source === 'manual' && (
                  <Badge className="bg-amber-500 text-white gap-1">
                    <Settings className="h-3 w-3" /> Manual
                  </Badge>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Current Subscription */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Crown className="h-5 w-5 text-amber-500" />
              Current Subscription
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadingUser ? (
              <div className="flex justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <>
                {/* Plan Info */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Plan</p>
                    <p className="font-bold text-lg capitalize">{sub.plan || 'Free'}</p>
                  </div>
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Status</p>
                    <Badge className={
                      sub.status === 'active' ? 'bg-green-500' :
                      sub.status === 'expired' ? 'bg-red-500' : 'bg-gray-500'
                    }>
                      {sub.status || 'Active'}
                    </Badge>
                  </div>
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Days Left</p>
                    <p className="font-bold text-lg">
                      {sub.days_remaining !== null ? sub.days_remaining : '∞'}
                    </p>
                  </div>
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">End Date</p>
                    <p className="font-medium text-sm">{formatDate(sub.end_date)}</p>
                  </div>
                </div>

                {/* Stripe Warning */}
                {stripe.has_subscription && stripe.status === 'active' && (
                  <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800">
                    <CreditCard className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-blue-700 dark:text-blue-300">Active Stripe Subscription</p>
                      <p className="text-sm text-blue-600 dark:text-blue-400">
                        This user has an active Stripe subscription. Manual override is blocked to prevent billing conflicts.
                        The user must cancel their Stripe subscription first.
                      </p>
                    </div>
                  </div>
                )}

                {/* Override Info */}
                {override.override_by && (
                  <div className="p-4 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200 dark:border-amber-800">
                    <p className="text-sm text-amber-700 dark:text-amber-300">
                      <strong>Last Override:</strong> {formatDate(override.override_at)}
                    </p>
                    <p className="text-sm text-amber-600 dark:text-amber-400 mt-1">
                      Reason: {override.override_reason || 'N/A'}
                    </p>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex flex-wrap gap-2 pt-4 border-t">
                  <Button
                    onClick={() => setOverrideDialogOpen(true)}
                    disabled={stripe.has_subscription && stripe.status === 'active'}
                    className="gap-2"
                  >
                    <Edit3 className="h-4 w-4" />
                    Override Plan
                  </Button>
                  {sub.plan !== 'free' && sub.source === 'manual' && (
                    <>
                      <Button
                        variant="outline"
                        onClick={() => setExtendDialogOpen(true)}
                        className="gap-2"
                      >
                        <Plus className="h-4 w-4" />
                        Extend
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => setRevokeDialogOpen(true)}
                        className="gap-2"
                      >
                        <XCircle className="h-4 w-4" />
                        Revoke
                      </Button>
                    </>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Plan Benefits */}
        {benefits.name && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Plan Benefits</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Monthly Listing Limit</p>
                  <p className="font-medium">{benefits.monthly_listing_limit}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Buyer Premium Discount</p>
                  <p className="font-medium">{(benefits.buyer_premium_discount * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Seller Commission Discount</p>
                  <p className="font-medium">{(benefits.seller_commission_discount * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Features</p>
                  <p className="font-medium">{benefits.features?.length || 0} included</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Audit History */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <History className="h-4 w-4" />
              Subscription History
            </CardTitle>
          </CardHeader>
          <CardContent>
            {subscriptionHistory.length === 0 ? (
              <p className="text-muted-foreground text-sm">No subscription changes recorded.</p>
            ) : (
              <div className="space-y-3 max-h-64 overflow-y-auto">
                {subscriptionHistory.map((entry, idx) => (
                  <div key={entry.id || idx} className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg text-sm">
                    <div className={`w-2 h-2 rounded-full mt-1.5 ${
                      entry.action.includes('override') ? 'bg-amber-500' :
                      entry.action.includes('extend') ? 'bg-green-500' :
                      entry.action.includes('revok') ? 'bg-red-500' :
                      'bg-blue-500'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium capitalize">{entry.action.replace(/_/g, ' ')}</p>
                      <p className="text-xs text-muted-foreground">{formatDate(entry.timestamp)}</p>
                      {entry.reason && (
                        <p className="text-xs text-muted-foreground mt-1">"{entry.reason}"</p>
                      )}
                      {entry.admin_email && (
                        <p className="text-xs text-muted-foreground">By: {entry.admin_email}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading subscription data...</p>
        </CardContent>
      </Card>
    );
  }

  // Show user detail if selected
  if (selectedUser) {
    return (
      <div className="space-y-6">
        <UserDetailPanel />

        {/* Override Dialog */}
        <Dialog open={overrideDialogOpen} onOpenChange={setOverrideDialogOpen}>
          <DialogContent className="w-[95vw] max-w-[500px]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Edit3 className="h-5 w-5" />
                Override Subscription
              </DialogTitle>
              <DialogDescription>
                Manually assign a subscription plan. This will not trigger Stripe billing.
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              {/* Plan Selection */}
              <div className="space-y-2">
                <Label>{t("admin.selectPlan")}</Label>
                <Select value={overrideData.plan} onValueChange={(v) => setOverrideData(p => ({...p, plan: v}))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="free">
                      <span className="flex items-center gap-2"><UserIcon className="h-4 w-4" /> Free</span>
                    </SelectItem>
                    <SelectItem value="premium">
                      <span className="flex items-center gap-2"><Star className="h-4 w-4 text-purple-500" /> Premium</span>
                    </SelectItem>
                    <SelectItem value="vip">
                      <span className="flex items-center gap-2"><Crown className="h-4 w-4 text-amber-500" /> VIP</span>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Duration */}
              {overrideData.plan !== 'free' && (
                <>
                  <div className="space-y-2">
                    <Label>{t("admin.durationType")}</Label>
                    <div className="flex gap-2">
                      <Button 
                        type="button"
                        variant={overrideData.duration_type === 'days' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setOverrideData(p => ({...p, duration_type: 'days'}))}
                      >
                        Days from now
                      </Button>
                      <Button 
                        type="button"
                        variant={overrideData.duration_type === 'custom' ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setOverrideData(p => ({...p, duration_type: 'custom'}))}
                      >
                        Custom end date
                      </Button>
                    </div>
                  </div>

                  {overrideData.duration_type === 'days' ? (
                    <div className="space-y-2">
                      <Label>{t("admin.numberOfDays")}</Label>
                      <div className="flex gap-2">
                        {[30, 90, 180, 365].map(d => (
                          <Button
                            key={d}
                            type="button"
                            variant={overrideData.duration_days === d ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setOverrideData(p => ({...p, duration_days: d}))}
                          >
                            {d}d
                          </Button>
                        ))}
                      </div>
                      <Input
                        type="number"
                        value={overrideData.duration_days}
                        onChange={(e) => setOverrideData(p => ({...p, duration_days: e.target.value}))}
                        min={1}
                        placeholder="Custom days"
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label>{t("admin.endDate")}</Label>
                      <Input
                        type="date"
                        value={overrideData.end_date}
                        onChange={(e) => setOverrideData(p => ({...p, end_date: e.target.value}))}
                        min={new Date().toISOString().split('T')[0]}
                      />
                    </div>
                  )}
                </>
              )}

              {/* Reason */}
              <div className="space-y-2">
                <Label>Reason (Required) *</Label>
                <Textarea
                  value={overrideData.reason}
                  onChange={(e) => setOverrideData(p => ({...p, reason: e.target.value}))}
                  placeholder="e.g., VIP customer compensation, promotional upgrade, etc."
                  rows={3}
                />
              </div>
            </div>

            <DialogFooter className="flex-col sm:flex-row gap-2">
              <Button variant="outline" onClick={() => setOverrideDialogOpen(false)} className="w-full sm:w-auto">
                Cancel
              </Button>
              <Button onClick={handleOverride} disabled={overriding} className="w-full sm:w-auto gap-2">
                {overriding ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
                Apply Override
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Extend Dialog */}
        <Dialog open={extendDialogOpen} onOpenChange={setExtendDialogOpen}>
          <DialogContent className="w-[95vw] max-w-[400px]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5" />
                Extend Subscription
              </DialogTitle>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>{t("admin.additionalDays")}</Label>
                <div className="flex gap-2 flex-wrap">
                  {[7, 14, 30, 60, 90].map(d => (
                    <Button
                      key={d}
                      type="button"
                      variant={extendData.additional_days === d ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setExtendData(p => ({...p, additional_days: d}))}
                    >
                      +{d}d
                    </Button>
                  ))}
                </div>
                <Input
                  type="number"
                  value={extendData.additional_days}
                  onChange={(e) => setExtendData(p => ({...p, additional_days: e.target.value}))}
                  min={1}
                />
              </div>
              <div className="space-y-2">
                <Label>Reason (Required) *</Label>
                <Textarea
                  value={extendData.reason}
                  onChange={(e) => setExtendData(p => ({...p, reason: e.target.value}))}
                  placeholder="e.g., Service credit, goodwill extension"
                  rows={2}
                />
              </div>
            </div>

            <DialogFooter className="flex-col sm:flex-row gap-2">
              <Button variant="outline" onClick={() => setExtendDialogOpen(false)} className="w-full sm:w-auto">
                Cancel
              </Button>
              <Button onClick={handleExtend} disabled={extending} className="w-full sm:w-auto gap-2">
                {extending ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
                Extend
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Revoke Dialog */}
        <Dialog open={revokeDialogOpen} onOpenChange={setRevokeDialogOpen}>
          <DialogContent className="w-[95vw] max-w-[400px]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-600">
                <XCircle className="h-5 w-5" />
                Revoke Subscription
              </DialogTitle>
              <DialogDescription>
                This will immediately downgrade the user to the Free plan.
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div className="p-4 bg-red-50 dark:bg-red-950/30 rounded-lg border border-red-200 dark:border-red-800">
                <p className="text-sm text-red-700 dark:text-red-300">
                  <strong>Warning:</strong> This action is immediate and will remove all paid plan benefits.
                </p>
              </div>
              <div className="space-y-2">
                <Label>Reason (Required) *</Label>
                <Textarea
                  value={revokeReason}
                  onChange={(e) => setRevokeReason(e.target.value)}
                  placeholder="e.g., Violation of terms, user request, refund issued"
                  rows={3}
                />
              </div>
            </div>

            <DialogFooter className="flex-col sm:flex-row gap-2">
              <Button variant="outline" onClick={() => setRevokeDialogOpen(false)} className="w-full sm:w-auto">
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleRevoke} disabled={revoking} className="w-full sm:w-auto gap-2">
                {revoking ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
                Revoke Subscription
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  // Main list view
  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center">
                <UserIcon className="h-5 w-5 text-slate-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats.total}</p>
                <p className="text-xs text-muted-foreground">Total Users</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
                <UserIcon className="h-5 w-5 text-gray-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats.free}</p>
                <p className="text-xs text-muted-foreground">Free</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-purple-50 dark:bg-purple-950/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center">
                <Star className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-purple-700 dark:text-purple-300">{stats.premium}</p>
                <p className="text-xs text-purple-600 dark:text-purple-400">Premium</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-amber-50 dark:bg-amber-950/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center">
                <Crown className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">{stats.vip}</p>
                <p className="text-xs text-amber-600 dark:text-amber-400">VIP</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-green-50 dark:bg-green-950/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
                <DollarSign className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-xl font-bold text-green-700 dark:text-green-300">${stats.revenue.toFixed(0)}</p>
                <p className="text-xs text-green-600 dark:text-green-400">Est. ARR</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Crown className="h-5 w-5 text-amber-500" />
            Subscription Management
          </CardTitle>
          <CardDescription>
            View and manage user subscriptions. Manual overrides do not affect Stripe billing.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Search and Filters */}
          <div className="flex flex-col sm:flex-row gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name or email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={filterPlan} onValueChange={setFilterPlan}>
              <SelectTrigger className="w-full sm:w-32">
                <SelectValue placeholder="Plan" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("admin.allPlans")}</SelectItem>
                <SelectItem value="free">Free</SelectItem>
                <SelectItem value="premium">Premium</SelectItem>
                <SelectItem value="vip">VIP</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterSource} onValueChange={setFilterSource}>
              <SelectTrigger className="w-full sm:w-32">
                <SelectValue placeholder="Source" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("admin.allSources")}</SelectItem>
                <SelectItem value="manual">Manual</SelectItem>
                <SelectItem value="stripe">Stripe</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* User List */}
          <div className="space-y-2">
            {filteredUsers.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No users found matching your filters
              </div>
            ) : (
              filteredUsers.slice(0, 50).map(user => {
                const plan = user.subscription_tier || 'free';
                const source = user.subscription_source || (user.stripe_subscription_id ? 'stripe' : 'manual');
                const PlanIcon = PLANS[plan]?.icon || UserIcon;
                
                return (
                  <div 
                    key={user.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                    onClick={() => selectUser(user)}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                        plan === 'vip' ? 'bg-amber-100 dark:bg-amber-900' :
                        plan === 'premium' ? 'bg-purple-100 dark:bg-purple-900' :
                        'bg-slate-100 dark:bg-slate-800'
                      }`}>
                        <PlanIcon className={`h-5 w-5 ${
                          plan === 'vip' ? 'text-amber-600' :
                          plan === 'premium' ? 'text-purple-600' :
                          'text-slate-500'
                        }`} />
                      </div>
                      <div>
                        <p className="font-medium">{user.name || 'No name'}</p>
                        <p className="text-sm text-muted-foreground">{user.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-13 sm:ml-0">
                      <Badge variant="outline" className="capitalize">{plan}</Badge>
                      <Badge className={source === 'stripe' ? 'bg-blue-500' : 'bg-amber-500'}>
                        {source}
                      </Badge>
                      <Button variant="ghost" size="sm">
                        <Eye className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                );
              })
            )}
            {filteredUsers.length > 50 && (
              <p className="text-center text-sm text-muted-foreground py-2">
                Showing 50 of {filteredUsers.length} users. Use search to find specific users.
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SubscriptionManager;
