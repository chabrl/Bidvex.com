import API_BASE from '../../config';
/**
 * PricingManager - Admin panel for managing subscription plan pricing
 * Features: Edit prices, view changelog, Stripe sync
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { 
  Crown, Star, User as UserIcon, DollarSign, Save, History,
  RefreshCw, Settings, Edit3, TrendingUp, Check, AlertCircle
} from 'lucide-react';
import { formatCurrency } from '../../utils/currencyFormatter';
import { useTranslation } from 'react-i18next';

const API = `${API_BASE}/api`;

// Plan icons and colors
const PLAN_CONFIG = {
  free: { icon: UserIcon, color: 'gray', bgColor: 'bg-slate-100 dark:bg-slate-800' },
  premium: { icon: Star, color: 'purple', bgColor: 'bg-purple-100 dark:bg-purple-900/30' },
  vip: { icon: Crown, color: 'amber', bgColor: 'bg-amber-100 dark:bg-amber-900/30' }
};

const PricingManager = () => {
  const { t } = useTranslation();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [changelog, setChangelog] = useState([]);
  const [activeTab, setActiveTab] = useState('plans');
  
  // Edit state
  const [editingPlan, setEditingPlan] = useState(null);
  const [editData, setEditData] = useState({});
  const [editReason, setEditReason] = useState('');
  const [saving, setSaving] = useState(false);

  const getAuthHeader = () => {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchPlans = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/admin/subscription-plans`, {
        headers: getAuthHeader()
      });
      if (response.data.success) {
        setPlans(response.data.plans || []);
      }
    } catch (error) {
      console.error('Error fetching plans:', error);
      toast.error('Failed to load subscription plans');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchChangelog = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/subscription-plans/changelog?limit=50`, {
        headers: getAuthHeader()
      });
      if (response.data.success) {
        setChangelog(response.data.changelog || []);
      }
    } catch (error) {
      console.error('Error fetching changelog:', error);
    }
  }, []);

  useEffect(() => {
    fetchPlans();
    fetchChangelog();
  }, [fetchPlans, fetchChangelog]);

  const handleEditPlan = (plan) => {
    setEditingPlan(plan);
    setEditData({
      price_monthly: plan.price_monthly || 0,
      price_yearly: plan.price_yearly || 0,
      original_price_monthly: plan.original_price_monthly || 0,
      original_price_yearly: plan.original_price_yearly || 0,
      buyer_premium_discount: plan.buyer_premium_discount || 0,
      seller_commission_discount: plan.seller_commission_discount || 0,
      monthly_listing_limit: plan.monthly_listing_limit || 0,
      is_active: plan.is_active !== false
    });
    setEditReason('');
  };

  const handleSavePlan = async () => {
    if (!editReason.trim()) {
      toast.error('Please provide a reason for the change');
      return;
    }

    setSaving(true);
    try {
      const response = await axios.put(
        `${API}/admin/subscription-plans/${editingPlan.plan_id}`,
        { ...editData, reason: editReason },
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        toast.success(`${editingPlan.name} plan updated successfully`);
        setEditingPlan(null);
        fetchPlans();
        fetchChangelog();
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to update plan';
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-CA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
          <p className="mt-4 text-muted-foreground">Loading pricing data...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6" data-testid="pricing-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center shadow-lg">
            <DollarSign className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Pricing Engine</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Manage subscription plan pricing and discounts
            </p>
          </div>
        </div>
        <Button variant="outline" onClick={() => { fetchPlans(); fetchChangelog(); }} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2 max-w-md">
          <TabsTrigger value="plans" className="gap-2">
            <Settings className="h-4 w-4" />
            Plans & Pricing
          </TabsTrigger>
          <TabsTrigger value="changelog" className="gap-2">
            <History className="h-4 w-4" />
            Change Log
          </TabsTrigger>
        </TabsList>

        {/* Plans Tab */}
        <TabsContent value="plans" className="space-y-4 mt-4">
          <div className="grid md:grid-cols-3 gap-4">
            {plans.map((plan) => {
              const config = PLAN_CONFIG[plan.plan_id] || PLAN_CONFIG.free;
              const PlanIcon = config.icon;

              return (
                <Card 
                  key={plan.plan_id} 
                  className={`${config.bgColor} border-0 relative overflow-hidden`}
                >
                  {!plan.is_active && (
                    <div className="absolute top-2 right-2">
                      <Badge variant="secondary">{t("common.inactive")}</Badge>
                    </div>
                  )}
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        plan.plan_id === 'vip' ? 'bg-amber-500' :
                        plan.plan_id === 'premium' ? 'bg-purple-500' : 'bg-slate-500'
                      }`}>
                        <PlanIcon className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{plan.name}</CardTitle>
                        <CardDescription className="text-xs">
                          {plan.plan_id === 'free' ? 'Base tier' : 'Paid subscription'}
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Pricing */}
                    <div className="space-y-2">
                      <div className="flex justify-between items-baseline">
                        <span className="text-sm text-muted-foreground">Monthly</span>
                        <div className="text-right">
                          {plan.original_price_monthly > plan.price_monthly && (
                            <span className="text-xs text-slate-400 line-through mr-2">
                              {formatCurrency(plan.original_price_monthly)}
                            </span>
                          )}
                          <span className="text-xl font-bold">{formatCurrency(plan.price_monthly)}</span>
                        </div>
                      </div>
                      <div className="flex justify-between items-baseline">
                        <span className="text-sm text-muted-foreground">Yearly</span>
                        <div className="text-right">
                          {plan.original_price_yearly > plan.price_yearly && (
                            <span className="text-xs text-slate-400 line-through mr-2">
                              {formatCurrency(plan.original_price_yearly)}
                            </span>
                          )}
                          <span className="text-xl font-bold">{formatCurrency(plan.price_yearly)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Discounts */}
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Buyer Discount</span>
                        <span className="font-medium">{plan.buyer_premium_discount || 0}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Seller Discount</span>
                        <span className="font-medium">{plan.seller_commission_discount || 0}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Listing Limit</span>
                        <span className="font-medium">
                          {plan.monthly_listing_limit === -1 ? 'Unlimited' : plan.monthly_listing_limit}
                        </span>
                      </div>
                    </div>

                    {/* Stripe Sync Status */}
                    <div className="pt-2 border-t">
                      <div className="flex items-center gap-2 text-xs">
                        {plan.stripe_product_id ? (
                          <>
                            <Check className="h-3 w-3 text-green-500" />
                            <span className="text-green-600 dark:text-green-400">Synced with Stripe</span>
                          </>
                        ) : (
                          <>
                            <AlertCircle className="h-3 w-3 text-amber-500" />
                            <span className="text-amber-600 dark:text-amber-400">Not synced to Stripe</span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Edit Button */}
                    <Button 
                      onClick={() => handleEditPlan(plan)}
                      className="w-full gap-2"
                      variant={plan.plan_id === 'free' ? 'outline' : 'default'}
                    >
                      <Edit3 className="h-4 w-4" />
                      Edit Pricing
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Revenue Estimation */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-green-500" />
                Pricing Overview
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid sm:grid-cols-3 gap-4 text-sm">
                {plans.filter(p => p.plan_id !== 'free').map(plan => (
                  <div key={plan.plan_id} className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <p className="text-muted-foreground mb-1">{plan.name} Annual</p>
                    <p className="text-lg font-bold">{formatCurrency(plan.price_yearly)}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatCurrency(plan.price_yearly / 12)}/mo equivalent
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Changelog Tab */}
        <TabsContent value="changelog" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Pricing Change History
              </CardTitle>
              <CardDescription>
                Track all pricing modifications with admin attribution
              </CardDescription>
            </CardHeader>
            <CardContent>
              {changelog.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No pricing changes recorded yet
                </div>
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto">
                  {changelog.map((entry, idx) => (
                    <div 
                      key={entry.id || idx}
                      className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                    >
                      <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="capitalize">
                            {entry.plan_id}
                          </Badge>
                          <span className="font-medium text-sm">{entry.field_changed}</span>
                        </div>
                        <p className="text-sm mt-1">
                          <span className="text-red-500 line-through">{String(entry.old_value)}</span>
                          <span className="mx-2">→</span>
                          <span className="text-green-500 font-medium">{String(entry.new_value)}</span>
                        </p>
                        {entry.reason && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Reason: "{entry.reason}"
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1">
                          {formatDate(entry.changed_at)} • {entry.changed_by}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Plan Dialog */}
      <Dialog open={!!editingPlan} onOpenChange={() => setEditingPlan(null)}>
        <DialogContent className="w-[95vw] max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit3 className="h-5 w-5" />
              Edit {editingPlan?.name} Plan
            </DialogTitle>
            <DialogDescription>
              Update pricing and discounts. Changes will sync to Stripe.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Current Pricing */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Monthly Price (CAD)</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={editData.price_monthly}
                  onChange={(e) => setEditData(d => ({ ...d, price_monthly: parseFloat(e.target.value) || 0 }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Yearly Price (CAD)</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={editData.price_yearly}
                  onChange={(e) => setEditData(d => ({ ...d, price_yearly: parseFloat(e.target.value) || 0 }))}
                />
              </div>
            </div>

            {/* Original Prices (for promotional strikethrough display) */}
            <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
              <p className="text-xs text-amber-700 dark:text-amber-400 font-medium mb-2">
                Original Prices (displayed as strikethrough on pricing page)
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs">Original Monthly</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={editData.original_price_monthly}
                    onChange={(e) => setEditData(d => ({ ...d, original_price_monthly: parseFloat(e.target.value) || 0 }))}
                    placeholder="Leave 0 to hide"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Original Yearly</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={editData.original_price_yearly}
                    onChange={(e) => setEditData(d => ({ ...d, original_price_yearly: parseFloat(e.target.value) || 0 }))}
                    placeholder="Leave 0 to hide"
                  />
                </div>
              </div>
            </div>

            {/* Discounts */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Buyer Premium Discount (%)</Label>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={editData.buyer_premium_discount}
                  onChange={(e) => setEditData(d => ({ ...d, buyer_premium_discount: parseFloat(e.target.value) || 0 }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Seller Commission Discount (%)</Label>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={editData.seller_commission_discount}
                  onChange={(e) => setEditData(d => ({ ...d, seller_commission_discount: parseFloat(e.target.value) || 0 }))}
                />
              </div>
            </div>

            {/* Listing Limit */}
            <div className="space-y-2">
              <Label>Monthly Listing Limit (-1 for unlimited)</Label>
              <Input
                type="number"
                min="-1"
                value={editData.monthly_listing_limit}
                onChange={(e) => setEditData(d => ({ ...d, monthly_listing_limit: parseInt(e.target.value) || 0 }))}
              />
            </div>

            {/* Active Toggle */}
            <div className="flex items-center justify-between">
              <Label>{t("admin.planActive")}</Label>
              <Switch
                checked={editData.is_active}
                onCheckedChange={(checked) => setEditData(d => ({ ...d, is_active: checked }))}
              />
            </div>

            {/* Reason */}
            <div className="space-y-2">
              <Label>Reason for Change (Required) *</Label>
              <Textarea
                value={editReason}
                onChange={(e) => setEditReason(e.target.value)}
                placeholder="e.g., Annual pricing adjustment, promotional discount..."
                rows={2}
              />
            </div>
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setEditingPlan(null)} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button onClick={handleSavePlan} disabled={saving} className="w-full sm:w-auto gap-2">
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PricingManager;
