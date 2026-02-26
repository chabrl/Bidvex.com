/**
 * AI Guard Dashboard - Fraud Detection Status
 * Shows flagged auctions and AI-detected suspicious activity
 * Connected to real backend fraud detection service
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { 
  Shield, AlertTriangle, CheckCircle, Clock, Search, 
  Eye, Ban, RefreshCw, Bot, TrendingUp, Users, Package, 
  XCircle, Zap, Loader2, Play, Pause, Sparkles
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Flag type configurations
const FLAG_TYPES = {
  bid_shilling: { label: 'Bid Shilling', color: 'bg-red-500', icon: Users },
  price_anomaly: { label: 'Price Anomaly', color: 'bg-amber-500', icon: TrendingUp },
  account_risk: { label: 'Account Risk', color: 'bg-orange-500', icon: AlertTriangle },
  rapid_bidding: { label: 'Rapid Bidding', color: 'bg-purple-500', icon: Zap },
  ip_clustering: { label: 'IP Clustering', color: 'bg-red-600', icon: Package },
  new_account_high_bid: { label: 'New Account', color: 'bg-blue-500', icon: Users },
};

// Status configurations
const STATUS_CONFIGS = {
  pending_review: { label: 'Pending Review', color: 'bg-yellow-500', textColor: 'text-yellow-700' },
  under_investigation: { label: 'Under Investigation', color: 'bg-blue-500', textColor: 'text-blue-700' },
  cleared: { label: 'Cleared', color: 'bg-green-500', textColor: 'text-green-700' },
  confirmed_fraud: { label: 'Confirmed Fraud', color: 'bg-red-500', textColor: 'text-red-700' },
};

const AIGuardDashboard = () => {
  const [flaggedAuctions, setFlaggedAuctions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState({
    total: 0,
    pending_review: 0,
    under_investigation: 0,
    cleared: 0,
    confirmed_fraud: 0
  });

  // Get auth token
  const getAuthHeader = () => {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  // Fetch flagged auctions from backend
  const fetchFlags = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterStatus !== 'all') params.append('status', filterStatus);
      if (filterType !== 'all') params.append('flag_type', filterType);
      params.append('limit', '100');

      const response = await axios.get(
        `${API}/admin/ai-guard/flags?${params.toString()}`,
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        setFlaggedAuctions(response.data.flags || []);
      }
    } catch (error) {
      console.error('Error fetching flags:', error);
      toast.error('Failed to load fraud flags');
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterType]);

  // Fetch stats from backend
  const fetchStats = useCallback(async () => {
    try {
      const response = await axios.get(
        `${API}/admin/ai-guard/stats`,
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        setStats(response.data.stats);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  }, []);

  // Run fraud scan
  const runScan = async () => {
    setScanning(true);
    toast.info('Starting fraud detection scan...');
    
    try {
      const response = await axios.post(
        `${API}/admin/ai-guard/scan`,
        { hours_back: 168 }, // Last 7 days
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        toast.success(`Scan complete! Found ${response.data.flags_detected} potential issues.`);
        // Refresh data
        await fetchFlags();
        await fetchStats();
      }
    } catch (error) {
      console.error('Scan error:', error);
      toast.error('Fraud scan failed. Check console for details.');
    } finally {
      setScanning(false);
    }
  };

  // Update flag status
  const handleStatusUpdate = async (flagId, newStatus, notes = null) => {
    try {
      const response = await axios.put(
        `${API}/admin/ai-guard/flags/${flagId}/status`,
        { status: newStatus, notes },
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        // Update local state
        setFlaggedAuctions(prev => 
          prev.map(f => f.id === flagId ? { ...f, status: newStatus } : f)
        );
        toast.success(`Status updated to ${STATUS_CONFIGS[newStatus]?.label || newStatus}`);
        await fetchStats();
      }
    } catch (error) {
      console.error('Status update error:', error);
      toast.error('Failed to update status');
    }
  };

  // Suspend auction
  const handleSuspendAuction = async (auctionId, reason) => {
    try {
      const response = await axios.post(
        `${API}/admin/ai-guard/suspend/${auctionId}`,
        { reason },
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        toast.success('Auction suspended successfully');
      }
    } catch (error) {
      console.error('Suspend error:', error);
      toast.error('Failed to suspend auction');
    }
  };

  // Generate AI summary for a flag
  const handleGenerateSummary = async (flagId) => {
    toast.info('Generating AI analysis...');
    try {
      const response = await axios.post(
        `${API}/admin/ai-guard/summary/${flagId}`,
        {},
        { headers: getAuthHeader() }
      );

      if (response.data.success) {
        // Update local state with summary
        setFlaggedAuctions(prev => 
          prev.map(f => f.id === flagId ? { ...f, ai_summary: response.data.summary } : f)
        );
        toast.success('AI analysis generated');
      }
    } catch (error) {
      console.error('Summary generation error:', error);
      toast.error('Failed to generate AI summary');
    }
  };

  // Initial load
  useEffect(() => {
    fetchFlags();
    fetchStats();
  }, [fetchFlags, fetchStats]);

  // Filter auctions locally by search
  const filteredAuctions = flaggedAuctions.filter(auction => {
    const matchesSearch = searchQuery === '' || 
      (auction.auction_title?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
      (auction.seller_name?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
      (auction.auction_id?.toLowerCase() || '').includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const formatConfidence = (confidence) => {
    const percent = Math.round((confidence || 0) * 100);
    if (percent >= 90) return { text: `${percent}%`, color: 'text-red-500' };
    if (percent >= 75) return { text: `${percent}%`, color: 'text-amber-500' };
    return { text: `${percent}%`, color: 'text-blue-500' };
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-CA', { 
      month: 'short', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div className="space-y-6" data-testid="ai-guard-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
            <Bot className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">AI Guard</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Automated fraud detection and auction monitoring
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            onClick={() => { fetchFlags(); fetchStats(); }}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button 
            onClick={runScan}
            disabled={scanning}
            className="gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700"
          >
            {scanning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Scanning...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Run Scan
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900 border-0">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-slate-200 dark:bg-slate-700 rounded-lg flex items-center justify-center">
                <Shield className="h-5 w-5 text-slate-600 dark:text-slate-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 dark:text-white">{stats.total}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Total Flags</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-yellow-50 to-amber-50 dark:from-yellow-900/20 dark:to-amber-900/20 border-0">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-yellow-200 dark:bg-yellow-800 rounded-lg flex items-center justify-center">
                <Clock className="h-5 w-5 text-yellow-700 dark:text-yellow-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">{stats.pending_review}</p>
                <p className="text-xs text-yellow-600 dark:text-yellow-400">Pending</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border-0">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-200 dark:bg-blue-800 rounded-lg flex items-center justify-center">
                <Search className="h-5 w-5 text-blue-700 dark:text-blue-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">{stats.under_investigation}</p>
                <p className="text-xs text-blue-600 dark:text-blue-400">Investigating</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-0">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-200 dark:bg-green-800 rounded-lg flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-green-700 dark:text-green-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-700 dark:text-green-300">{stats.cleared}</p>
                <p className="text-xs text-green-600 dark:text-green-400">Cleared</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-red-50 to-rose-50 dark:from-red-900/20 dark:to-rose-900/20 border-0">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-red-200 dark:bg-red-800 rounded-lg flex items-center justify-center">
                <XCircle className="h-5 w-5 text-red-700 dark:text-red-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">{stats.confirmed_fraud}</p>
                <p className="text-xs text-red-600 dark:text-red-400">Confirmed</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search by auction ID, title, or seller..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
                data-testid="ai-guard-search"
              />
            </div>
            <Select value={filterStatus} onValueChange={(v) => { setFilterStatus(v); }}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="pending_review">Pending Review</SelectItem>
                <SelectItem value="under_investigation">Under Investigation</SelectItem>
                <SelectItem value="cleared">Cleared</SelectItem>
                <SelectItem value="confirmed_fraud">Confirmed Fraud</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterType} onValueChange={(v) => { setFilterType(v); }}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {Object.entries(FLAG_TYPES).map(([key, config]) => (
                  <SelectItem key={key} value={key}>{config.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Flagged Auctions List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Flagged Auctions
          </CardTitle>
          <CardDescription>
            {loading ? 'Loading...' : `${filteredAuctions.length} auction${filteredAuctions.length !== 1 ? 's' : ''} flagged for review`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
          ) : filteredAuctions.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle className="h-12 w-12 text-green-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-2">
                All Clear!
              </h3>
              <p className="text-slate-500 dark:text-slate-400 mb-4">
                No flagged auctions match your current filters.
              </p>
              <Button variant="outline" onClick={runScan} disabled={scanning}>
                {scanning ? 'Scanning...' : 'Run a New Scan'}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredAuctions.map((auction) => {
                const flagConfig = FLAG_TYPES[auction.flag_type] || { label: auction.flag_type, color: 'bg-gray-500', icon: AlertTriangle };
                const statusConfig = STATUS_CONFIGS[auction.status] || STATUS_CONFIGS.pending_review;
                const confidence = formatConfidence(auction.confidence);
                const FlagIcon = flagConfig.icon;

                return (
                  <div
                    key={auction.id}
                    className="p-4 border border-slate-200 dark:border-slate-700 rounded-xl hover:border-slate-300 dark:hover:border-slate-600 transition-colors"
                    data-testid={`flagged-auction-${auction.id}`}
                  >
                    <div className="flex flex-col lg:flex-row lg:items-start gap-4">
                      {/* Flag Type Icon */}
                      <div className={`w-12 h-12 ${flagConfig.color} rounded-xl flex items-center justify-center flex-shrink-0`}>
                        <FlagIcon className="h-6 w-6 text-white" />
                      </div>

                      {/* Main Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <h4 className="font-semibold text-slate-900 dark:text-white">
                            {auction.auction_title || 'Unknown Auction'}
                          </h4>
                          {auction.auction_id && (
                            <Badge variant="outline" className="text-xs">
                              {auction.auction_id}
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
                          Seller: <span className="font-medium">{auction.seller_name || 'Unknown'}</span>
                        </p>
                        <p className="text-sm text-slate-600 dark:text-slate-300 mb-2">
                          {auction.reason}
                        </p>
                        
                        {/* AI Summary */}
                        {auction.ai_summary && (
                          <div className="mt-2 p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                            <div className="flex items-center gap-2 mb-1">
                              <Sparkles className="h-4 w-4 text-purple-500" />
                              <span className="text-xs font-medium text-purple-700 dark:text-purple-300">AI Analysis</span>
                            </div>
                            <p className="text-sm text-purple-800 dark:text-purple-200">
                              {auction.ai_summary}
                            </p>
                          </div>
                        )}
                      </div>

                      {/* Meta Info */}
                      <div className="flex flex-col gap-2 lg:items-end flex-shrink-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge className={`${flagConfig.color} text-white`}>
                            {flagConfig.label}
                          </Badge>
                          <Badge variant="outline" className={statusConfig.textColor}>
                            {statusConfig.label}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">
                            Confidence: <span className={`font-semibold ${confidence.color}`}>{confidence.text}</span>
                          </span>
                        </div>
                        <span className="text-xs text-slate-400 dark:text-slate-500">
                          {formatDate(auction.detected_at)}
                        </span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 flex-wrap">
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1"
                        onClick={() => window.open(`/vehicle/${auction.auction_id}`, '_blank')}
                      >
                        <Eye className="h-4 w-4" />
                        View Auction
                      </Button>
                      
                      {!auction.ai_summary && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1 text-purple-600 hover:text-purple-700 hover:bg-purple-50"
                          onClick={() => handleGenerateSummary(auction.id)}
                        >
                          <Sparkles className="h-4 w-4" />
                          AI Analyze
                        </Button>
                      )}
                      
                      {auction.status === 'pending_review' && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-1 text-green-600 hover:text-green-700 hover:bg-green-50"
                            onClick={() => handleStatusUpdate(auction.id, 'cleared')}
                          >
                            <CheckCircle className="h-4 w-4" />
                            Clear
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-1 text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                            onClick={() => handleStatusUpdate(auction.id, 'under_investigation')}
                          >
                            <Search className="h-4 w-4" />
                            Investigate
                          </Button>
                        </>
                      )}
                      
                      {auction.status === 'under_investigation' && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-1 text-green-600 hover:text-green-700 hover:bg-green-50"
                            onClick={() => handleStatusUpdate(auction.id, 'cleared')}
                          >
                            <CheckCircle className="h-4 w-4" />
                            Clear
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-1 text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleStatusUpdate(auction.id, 'confirmed_fraud')}
                          >
                            <XCircle className="h-4 w-4" />
                            Confirm Fraud
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-1 text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleSuspendAuction(auction.auction_id, 'Suspended due to fraud investigation')}
                          >
                            <Ban className="h-4 w-4" />
                            Suspend Auction
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center flex-shrink-0">
              <Bot className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h4 className="font-semibold text-blue-900 dark:text-blue-100 mb-1">
                About AI Guard
              </h4>
              <p className="text-sm text-blue-700 dark:text-blue-300">
                AI Guard uses pattern analysis and machine learning to detect potential fraud, 
                bid manipulation, and suspicious activity across all auctions. Click "Run Scan" 
                to analyze recent auction activity. Use "AI Analyze" on individual flags to get 
                GPT-4 powered fraud assessments with risk analysis and recommended actions.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AIGuardDashboard;
