import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Switch } from '../../components/ui/switch';
import { Label } from '../../components/ui/label';
import { Separator } from '../../components/ui/separator';
import { toast } from 'sonner';
import { 
  Settings, Users, Shield, Save, Info, CheckCircle, 
  AlertCircle, Package, Gavel, Clock, UserCheck,
  ToggleLeft, Hash, Layers
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AuctionControl = () => {
  // Settings State
  const [settings, setSettings] = useState({
    allowAllUsersMultiLot: true,
    requireApprovalNewSellers: false,
    maxActiveAuctionsPerUser: 20,
    maxLotsPerAuction: 50,
    enableAntiSniping: true,
    antiSnipingWindowMinutes: 2,
    enableBuyNow: true,
    minimumBidIncrement: 1,
  });
  
  const [originalSettings, setOriginalSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/admin/marketplace-settings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Map backend field names to frontend state
      const data = response.data;
      const mappedSettings = {
        allowAllUsersMultiLot: data.allow_all_users_multi_lot ?? true,
        requireApprovalNewSellers: data.require_approval_new_sellers ?? false,
        maxActiveAuctionsPerUser: data.max_active_auctions_per_user ?? 20,
        maxLotsPerAuction: data.max_lots_per_auction ?? 50,
        minimumBidIncrement: data.minimum_bid_increment ?? 1,
        enableAntiSniping: data.enable_anti_sniping ?? true,
        antiSnipingWindowMinutes: data.anti_sniping_window_minutes ?? 2,
        enableBuyNow: data.enable_buy_now ?? true,
      };
      
      setSettings(mappedSettings);
      setOriginalSettings({ ...mappedSettings });
    } catch (error) {
      console.error('Failed to load settings:', error);
      // Use defaults if API fails
      setOriginalSettings({ ...settings });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      
      // Map frontend state to backend field names
      const payload = {
        allow_all_users_multi_lot: settings.allowAllUsersMultiLot,
        require_approval_new_sellers: settings.requireApprovalNewSellers,
        max_active_auctions_per_user: settings.maxActiveAuctionsPerUser,
        max_lots_per_auction: settings.maxLotsPerAuction,
        minimum_bid_increment: settings.minimumBidIncrement,
        enable_anti_sniping: settings.enableAntiSniping,
        anti_sniping_window_minutes: settings.antiSnipingWindowMinutes,
        enable_buy_now: settings.enableBuyNow,
      };
      
      await axios.put(`${API}/admin/marketplace-settings`, payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setOriginalSettings({ ...settings });
      toast.success('Settings saved successfully', {
        description: 'Changes are now live on the marketplace.',
        icon: <CheckCircle className="h-4 w-4 text-green-500" />
      });
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast.error('Failed to save settings', {
        description: error.response?.data?.detail || 'Please try again.'
      });
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = JSON.stringify(settings) !== JSON.stringify(originalSettings);

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header Section */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Settings className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Marketplace Settings</h1>
            <p className="text-muted-foreground">Configure multi-lot auction access and quotas</p>
          </div>
        </div>
      </div>

      {/* Info Alert */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-start gap-3">
        <Info className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm text-blue-800 font-medium">Important</p>
          <p className="text-sm text-blue-700">
            These settings control who can create multi-lot auctions and enforce quotas to prevent abuse. 
            Changes take effect immediately.
          </p>
        </div>
      </div>

      {/* Card 1: Multi-Lot Auction Access */}
      <Card className="shadow-sm border-0 bg-white rounded-xl overflow-hidden">
        <CardHeader className="bg-gray-50/50 border-b pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 rounded-lg">
              <Users className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <CardTitle className="text-lg font-semibold">Multi-Lot Auction Access</CardTitle>
              <CardDescription>Control who can create multi-item auctions</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          {/* Toggle 1 */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
            <div className="flex items-center gap-4">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <Package className="h-5 w-5 text-gray-600" />
              </div>
              <div>
                <Label className="text-base font-medium cursor-pointer">
                  Allow All Users to Create Multi-Lot Auctions
                </Label>
                <p className="text-sm text-muted-foreground mt-0.5">
                  When disabled, only business accounts can create them
                </p>
              </div>
            </div>
            <Switch
              checked={settings.allowAllUsersMultiLot}
              onCheckedChange={(checked) => updateSetting('allowAllUsersMultiLot', checked)}
              className="data-[state=checked]:bg-indigo-600"
            />
          </div>

          {/* Toggle 2 */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
            <div className="flex items-center gap-4">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <UserCheck className="h-5 w-5 text-gray-600" />
              </div>
              <div>
                <Label className="text-base font-medium cursor-pointer">
                  Require Approval for New Sellers
                </Label>
                <p className="text-sm text-muted-foreground mt-0.5">
                  First-time sellers need admin approval before listings go live
                </p>
              </div>
            </div>
            <Switch
              checked={settings.requireApprovalNewSellers}
              onCheckedChange={(checked) => updateSetting('requireApprovalNewSellers', checked)}
              className="data-[state=checked]:bg-indigo-600"
            />
          </div>
        </CardContent>
      </Card>

      {/* Card 2: Quotas & Abuse Protection */}
      <Card className="shadow-sm border-0 bg-white rounded-xl overflow-hidden">
        <CardHeader className="bg-gray-50/50 border-b pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-100 rounded-lg">
              <Shield className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <CardTitle className="text-lg font-semibold">Quotas & Abuse Protection</CardTitle>
              <CardDescription>Set limits to maintain marketplace quality</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          {/* Input 1: Max Active Auctions */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <Gavel className="h-5 w-5 text-gray-600" />
              </div>
              <Label className="text-base font-medium">Maximum Active Auctions Per User</Label>
            </div>
            <div className="ml-12">
              <Input
                type="number"
                min="1"
                max="100"
                value={settings.maxActiveAuctionsPerUser}
                onChange={(e) => updateSetting('maxActiveAuctionsPerUser', parseInt(e.target.value) || 1)}
                className="w-32 h-11 text-lg font-medium"
              />
              <p className="text-xs text-muted-foreground mt-2">
                Limits how many concurrent auctions a single user can run. Recommended: 10-30
              </p>
            </div>
          </div>

          <Separator />

          {/* Input 2: Max Lots Per Auction */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <Layers className="h-5 w-5 text-gray-600" />
              </div>
              <Label className="text-base font-medium">Maximum Lots Per Auction</Label>
            </div>
            <div className="ml-12">
              <Input
                type="number"
                min="1"
                max="200"
                value={settings.maxLotsPerAuction}
                onChange={(e) => updateSetting('maxLotsPerAuction', parseInt(e.target.value) || 1)}
                className="w-32 h-11 text-lg font-medium"
              />
              <p className="text-xs text-muted-foreground mt-2">
                Maximum number of individual items allowed in a multi-lot auction. Recommended: 25-100
              </p>
            </div>
          </div>

          <Separator />

          {/* Input 3: Minimum Bid Increment */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <Hash className="h-5 w-5 text-gray-600" />
              </div>
              <Label className="text-base font-medium">Minimum Bid Increment ($)</Label>
            </div>
            <div className="ml-12">
              <Input
                type="number"
                min="0.01"
                step="0.01"
                value={settings.minimumBidIncrement}
                onChange={(e) => updateSetting('minimumBidIncrement', parseFloat(e.target.value) || 0.01)}
                className="w-32 h-11 text-lg font-medium"
              />
              <p className="text-xs text-muted-foreground mt-2">
                Minimum amount a new bid must exceed the current price. Recommended: $1-$5
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Card 3: Bidding Features */}
      <Card className="shadow-sm border-0 bg-white rounded-xl overflow-hidden">
        <CardHeader className="bg-gray-50/50 border-b pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 rounded-lg">
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <CardTitle className="text-lg font-semibold">Bidding Features</CardTitle>
              <CardDescription>Configure auction bidding behavior</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          {/* Anti-Sniping Toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
            <div className="flex items-center gap-4">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <Clock className="h-5 w-5 text-gray-600" />
              </div>
              <div>
                <Label className="text-base font-medium cursor-pointer">
                  Enable Anti-Sniping Protection
                </Label>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Automatically extends auctions when bids are placed in the final minutes
                </p>
              </div>
            </div>
            <Switch
              checked={settings.enableAntiSniping}
              onCheckedChange={(checked) => updateSetting('enableAntiSniping', checked)}
              className="data-[state=checked]:bg-amber-600"
            />
          </div>

          {settings.enableAntiSniping && (
            <div className="ml-12 p-4 bg-amber-50 rounded-xl border border-amber-200">
              <Label className="text-sm font-medium text-amber-800">Anti-Sniping Window (minutes)</Label>
              <Input
                type="number"
                min="1"
                max="10"
                value={settings.antiSnipingWindowMinutes}
                onChange={(e) => updateSetting('antiSnipingWindowMinutes', parseInt(e.target.value) || 2)}
                className="w-24 h-10 mt-2"
              />
              <p className="text-xs text-amber-700 mt-2">
                If a bid is placed within the final {settings.antiSnipingWindowMinutes} minutes, extend by {settings.antiSnipingWindowMinutes} minutes
              </p>
            </div>
          )}

          {/* Buy Now Toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
            <div className="flex items-center gap-4">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <Gavel className="h-5 w-5 text-gray-600" />
              </div>
              <div>
                <Label className="text-base font-medium cursor-pointer">
                  Enable "Buy Now" Feature
                </Label>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Allow sellers to set instant purchase prices on auction items
                </p>
              </div>
            </div>
            <Switch
              checked={settings.enableBuyNow}
              onCheckedChange={(checked) => updateSetting('enableBuyNow', checked)}
              className="data-[state=checked]:bg-amber-600"
            />
          </div>
        </CardContent>
      </Card>

      {/* Current Configuration Summary */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-5">
        <h3 className="font-semibold text-blue-900 mb-3 flex items-center gap-2">
          <CheckCircle className="h-5 w-5 text-blue-600" />
          Current Configuration Summary
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <ConfigSummaryItem 
            label="Multi-Lot Access" 
            value={settings.allowAllUsersMultiLot ? 'All Users' : 'Business Only'}
            active={settings.allowAllUsersMultiLot}
          />
          <ConfigSummaryItem 
            label="Seller Approval" 
            value={settings.requireApprovalNewSellers ? 'Required' : 'Not Required'}
            active={settings.requireApprovalNewSellers}
          />
          <ConfigSummaryItem 
            label="Active Auction Limit" 
            value={settings.maxActiveAuctionsPerUser.toString()}
            active={true}
          />
          <ConfigSummaryItem 
            label="Lots Per Auction" 
            value={settings.maxLotsPerAuction.toString()}
            active={true}
          />
        </div>
      </div>

      {/* Save Button */}
      <div className="sticky bottom-4 pt-4">
        <Button 
          onClick={handleSave}
          disabled={!hasChanges || saving}
          className={`w-full h-14 text-lg font-semibold rounded-xl shadow-lg transition-all ${
            hasChanges 
              ? 'bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white' 
              : 'bg-gray-200 text-gray-500 cursor-not-allowed'
          }`}
        >
          {saving ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent mr-2" />
              Saving...
            </>
          ) : (
            <>
              <Save className="h-5 w-5 mr-2" />
              {hasChanges ? 'Save Settings' : 'No Changes to Save'}
            </>
          )}
        </Button>
        {hasChanges && (
          <p className="text-center text-sm text-amber-600 mt-2 flex items-center justify-center gap-1">
            <AlertCircle className="h-4 w-4" />
            You have unsaved changes
          </p>
        )}
      </div>
    </div>
  );
};

// Config Summary Item Component
const ConfigSummaryItem = ({ label, value, active }) => (
  <div className="bg-white rounded-lg p-3 shadow-sm">
    <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
    <p className={`font-semibold mt-1 ${active ? 'text-blue-700' : 'text-gray-600'}`}>
      {value}
    </p>
  </div>
);

export default AuctionControl;
