import API_BASE from '../../config';
/**
 * CouponManager - Admin panel for managing coupon codes
 * Features: CRUD operations, usage tracking, expiry management
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
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
import { Checkbox } from '../../components/ui/checkbox';
import { toast } from 'sonner';
import { 
  Ticket, Plus, Edit3, Trash2, RefreshCw, Copy, Check,
  Calendar, Users, DollarSign, Percent, Tag, AlertCircle,
  Search, Clock
} from 'lucide-react';
import { formatCurrency } from '../../utils/currencyFormatter';
import { useTranslation } from 'react-i18next';

const API = API_BASE;

const CouponManager = () => {
  const { t } = useTranslation();
  const [coupons, setCoupons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  
  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedCoupon, setSelectedCoupon] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    code: '',
    discount_type: 'percentage',
    value: 10,
    expiry_date: '',
    usage_limit: 0,
    min_purchase_amount: 0,
    applicable_plans: ['premium', 'vip']
  });
  const [saving, setSaving] = useState(false);
  const [copiedCode, setCopiedCode] = useState(null);

  const getAuthHeader = () => {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchCoupons = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(
        `${API}/admin/coupons?include_inactive=${showInactive}`,
        { headers: getAuthHeader() }
      );
      if (response.data.success) {
        setCoupons(response.data.coupons || []);
      }
    } catch (error) {
      console.error('Error fetching coupons:', error);
      toast.error('Failed to load coupons');
    } finally {
      setLoading(false);
    }
  }, [showInactive]);

  useEffect(() => {
    fetchCoupons();
  }, [fetchCoupons]);

  const resetForm = () => {
    setFormData({
      code: '',
      discount_type: 'percentage',
      value: 10,
      expiry_date: '',
      usage_limit: 0,
      min_purchase_amount: 0,
      applicable_plans: ['premium', 'vip']
    });
  };

  const handleCreateCoupon = async () => {
    if (!formData.code.trim()) {
      toast.error('Coupon code is required');
      return;
    }
    if (formData.value <= 0) {
      toast.error('Discount value must be positive');
      return;
    }

    setSaving(true);
    try {
      const response = await axios.post(
        `${API}/admin/coupons`,
        formData,
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        toast.success(`Coupon ${formData.code.toUpperCase()} created successfully`);
        setCreateDialogOpen(false);
        resetForm();
        fetchCoupons();
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to create coupon';
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleEditCoupon = async () => {
    if (!selectedCoupon) return;

    setSaving(true);
    try {
      const response = await axios.put(
        `${API}/admin/coupons/${selectedCoupon.id}`,
        formData,
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        toast.success('Coupon updated successfully');
        setEditDialogOpen(false);
        setSelectedCoupon(null);
        resetForm();
        fetchCoupons();
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to update coupon';
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCoupon = async () => {
    if (!selectedCoupon) return;

    setSaving(true);
    try {
      const response = await axios.delete(
        `${API}/admin/coupons/${selectedCoupon.id}`,
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        toast.success('Coupon deactivated successfully');
        setDeleteDialogOpen(false);
        setSelectedCoupon(null);
        fetchCoupons();
      }
    } catch (error) {
      toast.error('Failed to delete coupon');
    } finally {
      setSaving(false);
    }
  };

  const openEditDialog = (coupon) => {
    setSelectedCoupon(coupon);
    setFormData({
      code: coupon.code,
      discount_type: coupon.discount_type,
      value: coupon.value,
      expiry_date: coupon.expiry_date ? coupon.expiry_date.split('T')[0] : '',
      usage_limit: coupon.usage_limit || 0,
      min_purchase_amount: coupon.min_purchase_amount || 0,
      applicable_plans: coupon.applicable_plans || ['premium', 'vip']
    });
    setEditDialogOpen(true);
  };

  const copyToClipboard = (code) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
    toast.success('Coupon code copied!');
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'No expiry';
    return new Date(dateStr).toLocaleDateString('en-CA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const isExpired = (dateStr) => {
    if (!dateStr) return false;
    return new Date(dateStr) < new Date();
  };

  const filteredCoupons = coupons.filter(coupon =>
    coupon.code.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Form component for create/edit dialog
  const CouponForm = ({ isEdit = false }) => (
    <div className="space-y-4 py-4">
      {/* Code */}
      <div className="space-y-2">
        <Label>Coupon Code *</Label>
        <Input
          value={formData.code}
          onChange={(e) => setFormData(d => ({ ...d, code: e.target.value.toUpperCase() }))}
          placeholder="e.g., SAVE20"
          maxLength={20}
          disabled={isEdit}
        />
        <p className="text-xs text-muted-foreground">3-20 characters, will be uppercase</p>
      </div>

      {/* Discount Type & Value */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t("admin.discountType")}</Label>
          <Select 
            value={formData.discount_type} 
            onValueChange={(v) => setFormData(d => ({ ...d, discount_type: v }))}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="percentage">
                <span className="flex items-center gap-2">
                  <Percent className="h-4 w-4" /> Percentage
                </span>
              </SelectItem>
              <SelectItem value="fixed">
                <span className="flex items-center gap-2">
                  <DollarSign className="h-4 w-4" /> Fixed Amount
                </span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Value *</Label>
          <div className="relative">
            <Input
              type="number"
              min="0.01"
              max={formData.discount_type === 'percentage' ? 100 : 10000}
              step="0.01"
              value={formData.value}
              onChange={(e) => setFormData(d => ({ ...d, value: parseFloat(e.target.value) || 0 }))}
              className="pr-8"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              {formData.discount_type === 'percentage' ? '%' : '$'}
            </span>
          </div>
        </div>
      </div>

      {/* Expiry & Usage Limit */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Expiry Date (Optional)</Label>
          <Input
            type="date"
            value={formData.expiry_date}
            onChange={(e) => setFormData(d => ({ ...d, expiry_date: e.target.value }))}
            min={new Date().toISOString().split('T')[0]}
          />
        </div>
        <div className="space-y-2">
          <Label>Usage Limit (0 = unlimited)</Label>
          <Input
            type="number"
            min="0"
            value={formData.usage_limit}
            onChange={(e) => setFormData(d => ({ ...d, usage_limit: parseInt(e.target.value) || 0 }))}
          />
        </div>
      </div>

      {/* Minimum Purchase */}
      <div className="space-y-2">
        <Label>Minimum Purchase Amount (CAD)</Label>
        <Input
          type="number"
          min="0"
          step="0.01"
          value={formData.min_purchase_amount}
          onChange={(e) => setFormData(d => ({ ...d, min_purchase_amount: parseFloat(e.target.value) || 0 }))}
          placeholder="0 = no minimum"
        />
      </div>

      {/* Applicable Plans */}
      <div className="space-y-2">
        <Label>{t("admin.applicablePlans")}</Label>
        <div className="flex gap-4">
          {['premium', 'vip'].map(plan => (
            <label key={plan} className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={formData.applicable_plans.includes(plan)}
                onCheckedChange={(checked) => {
                  if (checked) {
                    setFormData(d => ({ ...d, applicable_plans: [...d.applicable_plans, plan] }));
                  } else {
                    setFormData(d => ({ 
                      ...d, 
                      applicable_plans: d.applicable_plans.filter(p => p !== plan) 
                    }));
                  }
                }}
              />
              <span className="capitalize">{plan}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
          <p className="mt-4 text-muted-foreground">Loading coupons...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6" data-testid="coupon-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-pink-500 to-rose-600 rounded-xl flex items-center justify-center shadow-lg">
            <Ticket className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Coupon Codes</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Create and manage promotional discount codes
            </p>
          </div>
        </div>
        <Button onClick={() => { resetForm(); setCreateDialogOpen(true); }} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Coupon
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                <Tag className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">{coupons.filter(c => c.is_active).length}</p>
                <p className="text-xs text-muted-foreground">Active Coupons</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
                <Users className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {coupons.reduce((sum, c) => sum + (c.usage_count || 0), 0)}
                </p>
                <p className="text-xs text-muted-foreground">Total Uses</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900/30 rounded-lg flex items-center justify-center">
                <Clock className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {coupons.filter(c => c.expiry_date && !isExpired(c.expiry_date)).length}
                </p>
                <p className="text-xs text-muted-foreground">With Expiry</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center">
                <Percent className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {coupons.filter(c => c.discount_type === 'percentage').length}
                </p>
                <p className="text-xs text-muted-foreground">Percentage Based</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
            <div className="relative flex-1 w-full sm:max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search coupons..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <Checkbox
                  checked={showInactive}
                  onCheckedChange={(checked) => setShowInactive(checked)}
                />
                Show inactive
              </label>
              <Button variant="outline" size="sm" onClick={fetchCoupons} className="gap-2">
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Coupons List */}
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.allCoupons")}</CardTitle>
          <CardDescription>
            {filteredCoupons.length} coupon{filteredCoupons.length !== 1 ? 's' : ''} found
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredCoupons.length === 0 ? (
            <div className="text-center py-12">
              <Ticket className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">No coupons found</h3>
              <p className="text-muted-foreground mb-4">Create your first coupon to get started</p>
              <Button onClick={() => { resetForm(); setCreateDialogOpen(true); }} className="gap-2">
                <Plus className="h-4 w-4" />
                Create Coupon
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredCoupons.map((coupon) => (
                <div
                  key={coupon.id}
                  className={`p-4 border rounded-xl transition-colors ${
                    !coupon.is_active ? 'opacity-50 bg-slate-50 dark:bg-slate-800/50' : 
                    'hover:border-primary/30'
                  }`}
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    {/* Code & Discount */}
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-gradient-to-br from-pink-500 to-rose-500 rounded-xl flex items-center justify-center">
                        {coupon.discount_type === 'percentage' ? (
                          <Percent className="h-6 w-6 text-white" />
                        ) : (
                          <DollarSign className="h-6 w-6 text-white" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <code className="text-lg font-bold font-mono">{coupon.code}</code>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() => copyToClipboard(coupon.code)}
                          >
                            {copiedCode === coupon.code ? (
                              <Check className="h-4 w-4 text-green-500" />
                            ) : (
                              <Copy className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {coupon.discount_type === 'percentage' 
                            ? `${coupon.value}% off` 
                            : `${formatCurrency(coupon.value)} off`}
                          {coupon.min_purchase_amount > 0 && ` (min ${formatCurrency(coupon.min_purchase_amount)})`}
                        </p>
                      </div>
                    </div>

                    {/* Meta Info */}
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Usage */}
                      <Badge variant="outline" className="gap-1">
                        <Users className="h-3 w-3" />
                        {coupon.usage_count || 0}
                        {coupon.usage_limit > 0 ? `/${coupon.usage_limit}` : ''} used
                      </Badge>

                      {/* Expiry */}
                      {coupon.expiry_date && (
                        <Badge 
                          variant={isExpired(coupon.expiry_date) ? "destructive" : "outline"}
                          className="gap-1"
                        >
                          <Calendar className="h-3 w-3" />
                          {isExpired(coupon.expiry_date) ? 'Expired' : formatDate(coupon.expiry_date)}
                        </Badge>
                      )}

                      {/* Plans */}
                      {coupon.applicable_plans?.map(plan => (
                        <Badge key={plan} variant="secondary" className="capitalize">
                          {plan}
                        </Badge>
                      ))}

                      {/* Status */}
                      {!coupon.is_active && (
                        <Badge variant="secondary">{t("common.inactive")}</Badge>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEditDialog(coupon)}
                        className="gap-1"
                      >
                        <Edit3 className="h-4 w-4" />
                        Edit
                      </Button>
                      {coupon.is_active && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => { setSelectedCoupon(coupon); setDeleteDialogOpen(true); }}
                          className="gap-1 text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="w-[95vw] max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              Create Coupon Code
            </DialogTitle>
            <DialogDescription>
              Create a new promotional discount code
            </DialogDescription>
          </DialogHeader>
          <CouponForm />
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button onClick={handleCreateCoupon} disabled={saving} className="w-full sm:w-auto gap-2">
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Create Coupon
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="w-[95vw] max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit3 className="h-5 w-5" />
              Edit Coupon: {selectedCoupon?.code}
            </DialogTitle>
          </DialogHeader>
          <CouponForm isEdit />
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setEditDialogOpen(false)} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button onClick={handleEditCoupon} disabled={saving} className="w-full sm:w-auto gap-2">
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="w-[95vw] max-w-[400px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertCircle className="h-5 w-5" />
              Deactivate Coupon
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to deactivate <strong>{selectedCoupon?.code}</strong>? 
              Users will no longer be able to use this coupon.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)} className="w-full sm:w-auto">
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleDeleteCoupon} 
              disabled={saving}
              className="w-full sm:w-auto gap-2"
            >
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Deactivate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CouponManager;
