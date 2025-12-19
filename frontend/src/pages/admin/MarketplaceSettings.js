import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Switch } from '../../components/ui/switch';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { 
  Settings, Save, RotateCcw, AlertTriangle, Check, Users, Package, 
  DollarSign, Clock, ShoppingCart, Shield, Loader2, Info
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// System defaults (must match backend)
const SYSTEM_DEFAULTS = {
  allow_all_users_multi_lot: true,
  require_approval_new_sellers: false,
  max_active_auctions_per_user: 20,
  max_lots_per_auction: 50,
  minimum_bid_increment: 1.0,
  enable_anti_sniping: true,
  anti_sniping_window_minutes: 2,
  enable_buy_now: true
};

const MarketplaceSettings = () => {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [originalSettings, setOriginalSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);

  // Fetch settings on mount
  const fetchSettings = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/admin/marketplace-settings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSettings(response.data);
      setOriginalSettings(response.data);
    } catch (error) {
      toast.error('Failed to load marketplace settings');
      console.error('Error fetching settings:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // Check if settings have changed (dirty state)
  const isDirty = useCallback(() => {
    if (!settings || !originalSettings) return false;
    const compareKeys = Object.keys(SYSTEM_DEFAULTS);
    return compareKeys.some(key => settings[key] !== originalSettings[key]);
  }, [settings, originalSettings]);

  // Handle toggle changes
  const handleToggle = (key) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // Handle numeric input changes with validation
  const handleNumericChange = (key, value, min, max, isFloat = false) => {
    // Allow empty string for typing
    if (value === '') {
      setSettings(prev => ({ ...prev, [key]: '' }));
      return;
    }

    const numValue = isFloat ? parseFloat(value) : parseInt(value, 10);
    
    // Validate: reject negative, NaN, or out-of-range values
    if (isNaN(numValue) || numValue < 0) return;
    
    // Clamp to valid range
    const clampedValue = Math.max(min, Math.min(max || Infinity, numValue));
    setSettings(prev => ({ ...prev, [key]: clampedValue }));
  };

  // Save settings
  const handleSave = async () => {
    setSaving(true);
    try {
      // Build update payload with only changed fields
      const updatePayload = {};
      Object.keys(SYSTEM_DEFAULTS).forEach(key => {
        if (settings[key] !== originalSettings[key]) {
          updatePayload[key] = settings[key];
        }
      });

      const response = await axios.put(`${API}/admin/marketplace-settings`, updatePayload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setSettings(response.data);
      setOriginalSettings(response.data);
      toast.success('Settings saved successfully!', {
        description: 'Changes are now live across the platform.'
      });
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to save settings';
      toast.error('Save failed', { description: errorMsg });
    } finally {
      setSaving(false);
    }
  };

  // Restore defaults
  const handleRestoreDefaults = async () => {
    setResetting(true);
    try {
      const response = await axios.post(`${API}/admin/marketplace-settings/restore-defaults`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setSettings(response.data);
      setOriginalSettings(response.data);
      setShowResetModal(false);
      toast.success('Settings restored to factory defaults!', {
        description: 'All marketplace rules have been reset.'
      });
    } catch (error) {
      toast.error('Failed to restore defaults');
    } finally {
      setResetting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        Failed to load settings. Please refresh the page.
      </div>
    );
  }

  const hasChanges = isDirty();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Settings className="h-6 w-6 text-primary" />
            Marketplace Settings
          </h2>
          <p className="text-muted-foreground">
            Configure global auction and marketplace behavior
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => setShowResetModal(true)}
            className="flex items-center gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            Restore Defaults
          </Button>
          <Button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            className={`flex items-center gap-2 ${hasChanges ? 'bg-primary hover:bg-primary/90' : 'bg-gray-300'}`}
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : hasChanges ? (
              <Save className="h-4 w-4" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            {saving ? 'Saving...' : hasChanges ? 'Save Settings' : 'No Changes to Save'}
          </Button>
        </div>
      </div>

      {/* Dirty State Indicator */}
      {hasChanges && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-600" />
          <span className="text-amber-800 font-medium">You have unsaved changes</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* User & Seller Rules */}
        <Card className="border-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Users className="h-5 w-5 text-blue-600" />
              User & Seller Rules
            </CardTitle>
            <CardDescription>Control who can create auctions</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Allow All Users Multi-Lot */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex-1">
                <p className="font-medium">Allow All Users Multi-Lot</p>
                <p className="text-sm text-muted-foreground">
                  {settings.allow_all_users_multi_lot 
                    ? 'All users can create multi-lot auctions' 
                    : 'Only business accounts can create multi-lot auctions'}
                </p>
              </div>
              <Switch
                checked={settings.allow_all_users_multi_lot}
                onCheckedChange={() => handleToggle('allow_all_users_multi_lot')}
              />
            </div>

            {/* Require Seller Approval */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex-1">
                <p className="font-medium">Require Seller Approval</p>
                <p className="text-sm text-muted-foreground">
                  {settings.require_approval_new_sellers 
                    ? 'New sellers need admin approval' 
                    : 'New sellers can list immediately'}
                </p>
              </div>
              <Switch
                checked={settings.require_approval_new_sellers}
                onCheckedChange={() => handleToggle('require_approval_new_sellers')}
              />
            </div>
          </CardContent>
        </Card>

        {/* Auction Limits */}
        <Card className="border-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Package className="h-5 w-5 text-green-600" />
              Auction Limits
            </CardTitle>
            <CardDescription>Set maximum quantities per user</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Max Active Auctions */}
            <div className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="font-medium">Max Active Auctions per User</p>
                <Badge variant="outline">{settings.max_active_auctions_per_user}</Badge>
              </div>
              <Input
                type="number"
                min={1}
                max={100}
                value={settings.max_active_auctions_per_user}
                onChange={(e) => handleNumericChange('max_active_auctions_per_user', e.target.value, 1, 100)}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground mt-1">Range: 1-100</p>
            </div>

            {/* Max Lots per Auction */}
            <div className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="font-medium">Max Lots per Auction</p>
                <Badge variant="outline">{settings.max_lots_per_auction}</Badge>
              </div>
              <Input
                type="number"
                min={1}
                max={500}
                value={settings.max_lots_per_auction}
                onChange={(e) => handleNumericChange('max_lots_per_auction', e.target.value, 1, 500)}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground mt-1">Range: 1-500</p>
            </div>
          </CardContent>
        </Card>

        {/* Bidding Rules */}
        <Card className="border-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <DollarSign className="h-5 w-5 text-amber-600" />
              Bidding Rules
            </CardTitle>
            <CardDescription>Configure bid increments and pricing</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Minimum Bid Increment */}
            <div className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <p className="font-medium">Minimum Bid Increment</p>
                <Badge variant="outline">${settings.minimum_bid_increment?.toFixed(2)}</Badge>
              </div>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">$</span>
                <Input
                  type="number"
                  min={1}
                  step={0.01}
                  value={settings.minimum_bid_increment}
                  onChange={(e) => handleNumericChange('minimum_bid_increment', e.target.value, 1.0, null, true)}
                  className="pl-7"
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">Minimum: $1.00</p>
            </div>
          </CardContent>
        </Card>

        {/* Anti-Sniping */}
        <Card className="border-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Clock className="h-5 w-5 text-purple-600" />
              Anti-Sniping Protection
            </CardTitle>
            <CardDescription>Extend auctions for last-minute bids</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Enable Anti-Sniping */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex-1">
                <p className="font-medium">Enable Anti-Sniping</p>
                <p className="text-sm text-muted-foreground">
                  {settings.enable_anti_sniping 
                    ? 'Auctions auto-extend on late bids' 
                    : 'Auctions end at scheduled time'}
                </p>
              </div>
              <Switch
                checked={settings.enable_anti_sniping}
                onCheckedChange={() => handleToggle('enable_anti_sniping')}
              />
            </div>

            {/* Anti-Sniping Window */}
            {settings.enable_anti_sniping && (
              <div className="p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium">Extension Window</p>
                  <Badge variant="outline">{settings.anti_sniping_window_minutes} min</Badge>
                </div>
                <Input
                  type="number"
                  min={1}
                  max={60}
                  value={settings.anti_sniping_window_minutes}
                  onChange={(e) => handleNumericChange('anti_sniping_window_minutes', e.target.value, 1, 60)}
                  className="w-full"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Bids within this window extend the auction. Range: 1-60 minutes
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Buy Now (Full Width) */}
        <Card className="border-2 lg:col-span-2 border-red-200">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShoppingCart className="h-5 w-5 text-red-600" />
              Buy Now Feature
              {!settings.enable_buy_now && (
                <Badge className="bg-red-100 text-red-700 border-red-300">DISABLED</Badge>
              )}
            </CardTitle>
            <CardDescription>Global kill-switch for instant purchase feature</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between p-4 bg-red-50 rounded-lg border border-red-200">
              <div className="flex-1">
                <p className="font-medium text-red-900">Enable Buy Now</p>
                <p className="text-sm text-red-700">
                  {settings.enable_buy_now 
                    ? 'Buy Now buttons are visible on all eligible listings' 
                    : 'Buy Now buttons are HIDDEN platform-wide'}
                </p>
              </div>
              <Switch
                checked={settings.enable_buy_now}
                onCheckedChange={() => handleToggle('enable_buy_now')}
              />
            </div>
            {!settings.enable_buy_now && (
              <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                <p className="text-sm text-amber-800">
                  <strong>Warning:</strong> Buy Now is currently disabled. Users will only be able to place bids, not instant purchases.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Configuration Summary */}
      <Card className="border-2 border-primary/20 bg-primary/5">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Info className="h-5 w-5 text-primary" />
            Current Configuration Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-white rounded-lg shadow-sm">
              <p className="text-xs text-muted-foreground uppercase">Multi-Lot Access</p>
              <p className="font-bold text-lg">
                {settings.allow_all_users_multi_lot ? 'All Users' : 'Business Only'}
              </p>
            </div>
            <div className="text-center p-3 bg-white rounded-lg shadow-sm">
              <p className="text-xs text-muted-foreground uppercase">New Seller Approval</p>
              <p className="font-bold text-lg">
                {settings.require_approval_new_sellers ? 'Required' : 'Not Required'}
              </p>
            </div>
            <div className="text-center p-3 bg-white rounded-lg shadow-sm">
              <p className="text-xs text-muted-foreground uppercase">Max Auctions/User</p>
              <p className="font-bold text-lg">{settings.max_active_auctions_per_user}</p>
            </div>
            <div className="text-center p-3 bg-white rounded-lg shadow-sm">
              <p className="text-xs text-muted-foreground uppercase">Max Lots/Auction</p>
              <p className="font-bold text-lg">{settings.max_lots_per_auction}</p>
            </div>
            <div className="text-center p-3 bg-white rounded-lg shadow-sm">
              <p className="text-xs text-muted-foreground uppercase">Min Bid Increment</p>
              <p className="font-bold text-lg">${settings.minimum_bid_increment?.toFixed(2)}</p>
            </div>
            <div className="text-center p-3 bg-white rounded-lg shadow-sm">
              <p className="text-xs text-muted-foreground uppercase">Anti-Sniping</p>
              <p className="font-bold text-lg">
                {settings.enable_anti_sniping ? `${settings.anti_sniping_window_minutes} min` : 'OFF'}
              </p>
            </div>
            <div className="text-center p-3 bg-white rounded-lg shadow-sm">
              <p className="text-xs text-muted-foreground uppercase">Buy Now</p>
              <p className={`font-bold text-lg ${settings.enable_buy_now ? 'text-green-600' : 'text-red-600'}`}>
                {settings.enable_buy_now ? 'Enabled' : 'DISABLED'}
              </p>
            </div>
            <div className="text-center p-3 bg-white rounded-lg shadow-sm">
              <p className="text-xs text-muted-foreground uppercase">Last Updated</p>
              <p className="font-medium text-sm">
                {settings.updated_at 
                  ? new Date(settings.updated_at).toLocaleDateString()
                  : 'Never'}
              </p>
            </div>
          </div>
          {settings.updated_by && (
            <p className="text-xs text-muted-foreground mt-3 text-center">
              Last modified by: {settings.updated_by}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Reset Confirmation Modal */}
      {showResetModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4 border-2 border-red-300">
            <CardHeader className="bg-red-50 border-b border-red-200">
              <CardTitle className="flex items-center gap-2 text-red-700">
                <AlertTriangle className="h-6 w-6" />
                Restore Factory Defaults?
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <p className="text-gray-700">
                <strong>Are you sure?</strong> This will instantly reset all marketplace rules to factory settings:
              </p>
              <ul className="text-sm space-y-1 bg-gray-50 p-3 rounded-lg">
                <li>• Max Active Auctions: <strong>20</strong></li>
                <li>• Max Lots per Auction: <strong>50</strong></li>
                <li>• Minimum Bid Increment: <strong>$1.00</strong></li>
                <li>• Anti-Sniping Window: <strong>2 minutes</strong></li>
                <li>• All toggles reset to default states</li>
              </ul>
              <p className="text-sm text-red-600 font-medium">
                This action cannot be undone.
              </p>
              <div className="flex gap-3 pt-2">
                <Button
                  variant="outline"
                  onClick={() => setShowResetModal(false)}
                  className="flex-1"
                  disabled={resetting}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleRestoreDefaults}
                  className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                  disabled={resetting}
                >
                  {resetting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Resetting...
                    </>
                  ) : (
                    <>
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Yes, Reset All
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default MarketplaceSettings;
