import API_BASE from '../../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import {
  Trash2, AlertTriangle, Shield, Search, RefreshCw,
  Users, Package, MessageSquare, CreditCard, Bell, Heart, Lock
} from 'lucide-react';

const API = API_BASE;

const PlatformCleanupManager = () => {
  const { token } = useAuth();
  const headers = { Authorization: `Bearer ${token}` };
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);
  const [result, setResult] = useState(null);
  const [confirmStep, setConfirmStep] = useState(false);

  useEffect(() => {
    fetchPreview();
  }, []);

  const fetchPreview = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/platform-cleanup/preview`, { headers });
      setPreview(res.data);
      setResult(null);
      setConfirmStep(false);
    } catch (error) {
      toast.error('Failed to load cleanup preview');
    } finally {
      setLoading(false);
    }
  };

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      const res = await axios.post(`${API}/admin/platform-cleanup`, {}, { headers });
      setResult(res.data);
      setConfirmStep(false);
      toast.success(res.data.message || 'Platform cleanup complete');
      fetchPreview();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Cleanup failed');
    } finally {
      setCleaning(false);
    }
  };

  const previewItems = preview ? [
    { label: 'Test Users', count: preview.test_users, icon: Users, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/30' },
    { label: 'Listings', count: preview.test_listings, icon: Package, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/30' },
    { label: 'Multi-Item Listings', count: preview.test_multi_listings, icon: Package, color: 'text-purple-600', bg: 'bg-purple-50 dark:bg-purple-950/30' },
    { label: 'Bids', count: preview.test_bids, icon: Package, color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/30' },
    { label: 'Messages', count: preview.test_messages, icon: MessageSquare, color: 'text-cyan-600', bg: 'bg-cyan-50 dark:bg-cyan-950/30' },
    { label: 'Notifications', count: preview.test_notifications, icon: Bell, color: 'text-orange-600', bg: 'bg-orange-50 dark:bg-orange-950/30' },
    { label: 'Payment Methods', count: preview.test_payment_methods, icon: CreditCard, color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/30' },
    { label: 'Escrow Entries', count: preview.test_escrows, icon: Lock, color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/30' },
    { label: 'Community Questions', count: preview.test_community_questions, icon: MessageSquare, color: 'text-indigo-600', bg: 'bg-indigo-50 dark:bg-indigo-950/30' },
    { label: 'Community Replies', count: preview.test_community_replies, icon: MessageSquare, color: 'text-pink-600', bg: 'bg-pink-50 dark:bg-pink-950/30' },
    { label: 'Watchlist', count: preview.test_watchlist, icon: Heart, color: 'text-rose-600', bg: 'bg-rose-50 dark:bg-rose-950/30' },
  ] : [];

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="platform-cleanup-manager">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Trash2 className="h-5 w-5 sm:h-6 sm:w-6 text-red-500" />
            Platform Cleanup
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Remove test, demo, and fake data from the platform. Admin and real accounts are protected.
          </p>
        </div>
        <Button variant="outline" onClick={fetchPreview} data-testid="refresh-cleanup-preview">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Safety Notice */}
      <Card className="border-green-200 dark:border-green-800">
        <CardContent className="p-4 flex items-start gap-3">
          <Shield className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm">
            <p className="font-medium text-green-700 dark:text-green-400">Safety Protections Active</p>
            <ul className="text-muted-foreground mt-1 space-y-0.5 text-xs">
              <li>Admin accounts are never deleted</li>
              <li>Only users with test/demo/qa/fake/spam/example.com/mailinator emails are targeted</li>
              <li>All related data (listings, bids, messages, etc.) is cascade-deleted</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Preview Grid */}
      {preview && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {previewItems.map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.label} className={item.count > 0 ? 'border-red-200 dark:border-red-800' : ''}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`w-8 h-8 ${item.bg} rounded-full flex items-center justify-center`}>
                      <Icon className={`h-4 w-4 ${item.color}`} />
                    </div>
                    <span className="text-2xl font-bold">{item.count}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{item.label}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Total + Action */}
      {preview && (
        <Card className={preview.total_records > 0 ? 'border-red-300 dark:border-red-700' : 'border-green-300 dark:border-green-700'}>
          <CardContent className="p-6">
            {preview.total_records === 0 ? (
              <div className="text-center py-4">
                <Shield className="h-12 w-12 text-green-500 mx-auto mb-3" />
                <h3 className="text-lg font-bold text-green-700 dark:text-green-400">Platform is Clean</h3>
                <p className="text-sm text-muted-foreground">No test or demo data found. Nothing to clean up.</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-red-600">
                      {preview.total_records} test records found
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Across {previewItems.filter(i => i.count > 0).length} collections
                    </p>
                  </div>
                  <Badge variant="destructive" className="text-lg px-4 py-1">
                    {preview.test_users} users
                  </Badge>
                </div>

                {!confirmStep ? (
                  <Button
                    variant="destructive"
                    className="w-full"
                    onClick={() => setConfirmStep(true)}
                    data-testid="cleanup-start-btn"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Clean Up Test Data
                  </Button>
                ) : (
                  <div className="space-y-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                    <p className="text-sm font-medium text-red-700 dark:text-red-300 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4" />
                      Are you absolutely sure? This action is irreversible.
                    </p>
                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" onClick={() => setConfirmStep(false)} data-testid="cleanup-cancel-btn">
                        Cancel
                      </Button>
                      <Button
                        variant="destructive"
                        className="flex-1"
                        onClick={handleCleanup}
                        disabled={cleaning}
                        data-testid="cleanup-confirm-btn"
                      >
                        {cleaning ? (
                          <><div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2" />Cleaning...</>
                        ) : (
                          <><Trash2 className="h-4 w-4 mr-2" />Confirm Cleanup</>
                        )}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Result Summary */}
      {result && result.deleted && Object.keys(result.deleted).length > 0 && (
        <Card className="border-green-300 dark:border-green-700">
          <CardHeader>
            <CardTitle className="text-green-600 flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Cleanup Complete
            </CardTitle>
            <CardDescription>{result.message}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(result.deleted).map(([col, count]) => (
                <div key={col} className="flex items-center justify-between p-2 bg-green-50 dark:bg-green-950/30 rounded-lg">
                  <span className="text-xs text-muted-foreground capitalize">{col.replace(/_/g, ' ')}</span>
                  <Badge variant="outline" className="text-green-600">{count}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default PlatformCleanupManager;
