import API_BASE from '../../config';
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import {
  ShieldAlert, AlertTriangle, CheckCircle, Clock, Search,
  Eye, RefreshCw, Loader2, XCircle, UserX, Sparkles,
  ArrowUpRight, Shield, Filter, ChevronDown, ChevronUp,
  Ban, MapPin, Calendar, Activity, TrendingDown
} from 'lucide-react';
import { toast } from 'sonner';

const API = API_BASE;

const SEVERITY_MAP = {
  critical: { bg: 'bg-red-600', text: 'text-red-700', ring: 'ring-red-200' },
  high:     { bg: 'bg-orange-500', text: 'text-orange-700', ring: 'ring-orange-200' },
  medium:   { bg: 'bg-amber-500', text: 'text-amber-700', ring: 'ring-amber-200' },
  low:      { bg: 'bg-blue-500', text: 'text-blue-600', ring: 'ring-blue-200' },
};

const STATUS_MAP = {
  pending_review:      { label: 'Pending Review', color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/30', icon: Clock },
  under_investigation: { label: 'Investigating', color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/30', icon: Search },
  cleared:             { label: 'Cleared', color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/30', icon: CheckCircle },
  confirmed_fraud:     { label: 'Confirmed Fraud', color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/30', icon: XCircle },
};

const RiskMonitoringDashboard = () => {
  const [flags, setFlags] = useState([]);
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [threshold, setThreshold] = useState(80);
  const [viewMode, setViewMode] = useState('flags');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFlag, setExpandedFlag] = useState(null);
  const [clearDialog, setClearDialog] = useState({ open: false, flagId: null, flagTitle: '' });
  const [clearNotes, setClearNotes] = useState('');
  const [clearing, setClearing] = useState(false);
  const [behaviorData, setBehaviorData] = useState({});
  const [loadingBehavior, setLoadingBehavior] = useState(null);

  const getAuthHeader = () => {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(
        `${API}/admin/risk-monitoring?min_risk=${threshold}`,
        { headers: getAuthHeader() }
      );
      if (response.data.success) {
        setFlags(response.data.flags || []);
        setUsers(response.data.users || []);
        setStats(response.data.stats || {});
      }
    } catch (error) {
      console.error('Risk monitoring fetch error:', error);
      toast.error('Failed to load risk monitoring data');
    } finally {
      setLoading(false);
    }
  }, [threshold]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleClearFlag = async () => {
    if (!clearDialog.flagId) return;
    setClearing(true);
    try {
      const response = await axios.post(
        `${API}/admin/risk-monitoring/clear/${clearDialog.flagId}`,
        { notes: clearNotes || 'Cleared via Risk Monitoring — false positive' },
        { headers: getAuthHeader() }
      );
      if (response.data.success) {
        setFlags(prev => prev.filter(f => f.id !== clearDialog.flagId));
        setStats(prev => prev ? { ...prev, pending_review: Math.max(0, prev.pending_review - 1) } : prev);
        toast.success('Flag cleared successfully');
      }
    } catch (error) {
      toast.error('Failed to clear flag');
    } finally {
      setClearing(false);
      setClearDialog({ open: false, flagId: null, flagTitle: '' });
      setClearNotes('');
    }
  };

  const handleStatusUpdate = async (flagId, newStatus) => {
    try {
      const response = await axios.put(
        `${API}/admin/ai-guard/flags/${flagId}/status`,
        { status: newStatus },
        { headers: getAuthHeader() }
      );
      if (response.data.success) {
        setFlags(prev => prev.map(f => f.id === flagId ? { ...f, status: newStatus } : f));
        toast.success(`Status updated to ${STATUS_MAP[newStatus]?.label || newStatus}`);
      }
    } catch (error) {
      toast.error('Failed to update status');
    }
  };

  const fetchBehavior = async (userId) => {
    if (behaviorData[userId]) {
      setExpandedFlag(expandedFlag === userId ? null : userId);
      return;
    }
    setLoadingBehavior(userId);
    try {
      const response = await axios.get(
        `${API}/admin/trust-safety/behavioral-analysis?user_id=${userId}`,
        { headers: getAuthHeader() }
      );
      setBehaviorData(prev => ({ ...prev, [userId]: response.data }));
      setExpandedFlag(userId);
    } catch (error) {
      toast.error('Failed to load behavioral analysis');
    } finally {
      setLoadingBehavior(null);
    }
  };

  const riskColor = (score) => {
    if (score >= 95) return 'text-red-600 font-black';
    if (score >= 90) return 'text-red-500 font-bold';
    if (score >= 85) return 'text-orange-500 font-bold';
    return 'text-amber-500 font-semibold';
  };

  const confidencePercent = (c) => Math.round((c || 0) * 100);

  const filteredFlags = flags.filter(f => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (f.auction_title || '').toLowerCase().includes(q)
      || (f.seller_name || '').toLowerCase().includes(q)
      || (f.auction_id || '').toLowerCase().includes(q)
      || (f.flag_type || '').toLowerCase().includes(q);
  });

  const filteredUsers = users.filter(u => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (u.name || '').toLowerCase().includes(q)
      || (u.email || '').toLowerCase().includes(q);
  });

  return (
    <div className="space-y-6" data-testid="risk-monitoring-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-red-500 to-orange-600 rounded-xl flex items-center justify-center shadow-lg shadow-red-200 dark:shadow-red-900/30">
            <ShieldAlert className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Risk Monitoring</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              High-confidence flags requiring manual review
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={String(threshold)} onValueChange={(v) => setThreshold(Number(v))}>
            <SelectTrigger className="w-[160px]" data-testid="risk-threshold-select">
              <Filter className="h-4 w-4 mr-2 text-slate-400" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="80">Risk &ge; 80%</SelectItem>
              <SelectItem value="85">Risk &ge; 85%</SelectItem>
              <SelectItem value="90">Risk &ge; 90%</SelectItem>
              <SelectItem value="95">Risk &ge; 95%</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={fetchData} disabled={loading} className="gap-2" data-testid="risk-refresh-btn">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats Row */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Card className="border-0 bg-slate-50 dark:bg-slate-800/50">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-slate-200 dark:bg-slate-700 flex items-center justify-center">
                <Shield className="h-5 w-5 text-slate-600 dark:text-slate-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 dark:text-white" data-testid="stat-total-flags">{stats.total_flags_system}</p>
                <p className="text-xs text-slate-500">Total Flags</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 bg-red-50 dark:bg-red-950/20">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-red-200 dark:bg-red-800 flex items-center justify-center">
                <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600 dark:text-red-400" data-testid="stat-high-risk">{stats.high_risk_flags}</p>
                <p className="text-xs text-red-500">High Risk (&ge;{threshold}%)</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 bg-amber-50 dark:bg-amber-950/20">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-200 dark:bg-amber-800 flex items-center justify-center">
                <Clock className="h-5 w-5 text-amber-600 dark:text-amber-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-600 dark:text-amber-400" data-testid="stat-pending">{stats.pending_review}</p>
                <p className="text-xs text-amber-500">Pending Review</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 bg-emerald-50 dark:bg-emerald-950/20">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-200 dark:bg-emerald-800 flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400" data-testid="stat-cleared-today">{stats.cleared_today}</p>
                <p className="text-xs text-emerald-500">Cleared Today</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 bg-purple-50 dark:bg-purple-950/20">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-200 dark:bg-purple-800 flex items-center justify-center">
                <UserX className="h-5 w-5 text-purple-600 dark:text-purple-300" />
              </div>
              <div>
                <p className="text-2xl font-bold text-purple-600 dark:text-purple-400" data-testid="stat-high-risk-users">{stats.high_risk_users}</p>
                <p className="text-xs text-purple-500">High-Risk Users</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* View Toggle + Search */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex bg-slate-100 dark:bg-slate-800 rounded-lg p-1 gap-1">
              <button
                onClick={() => setViewMode('flags')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${viewMode === 'flags' ? 'bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white' : 'text-slate-500 hover:text-slate-700'}`}
                data-testid="view-flags-tab"
              >
                Fraud Flags ({filteredFlags.length})
              </button>
              <button
                onClick={() => setViewMode('users')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${viewMode === 'users' ? 'bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white' : 'text-slate-500 hover:text-slate-700'}`}
                data-testid="view-users-tab"
              >
                Risky Users ({filteredUsers.length})
              </button>
            </div>
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder={viewMode === 'flags' ? 'Search by auction, seller, or flag type...' : 'Search by name or email...'}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
                data-testid="risk-search-input"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      ) : viewMode === 'flags' ? (
        /* ─── FLAGS VIEW ─── */
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              High-Risk Flags
            </CardTitle>
            <CardDescription>
              {filteredFlags.length === 0
                ? 'No flags above the selected risk threshold'
                : `${filteredFlags.length} flag${filteredFlags.length !== 1 ? 's' : ''} with confidence >= ${threshold}%`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {filteredFlags.length === 0 ? (
              <div className="text-center py-16" data-testid="no-flags-message">
                <CheckCircle className="h-14 w-14 text-emerald-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">All Clear</h3>
                <p className="text-slate-500 text-sm">No flags at or above {threshold}% risk confidence.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredFlags.map((flag) => {
                  const severity = SEVERITY_MAP[flag.severity] || SEVERITY_MAP.medium;
                  const status = STATUS_MAP[flag.status] || STATUS_MAP.pending_review;
                  const StatusIcon = status.icon;
                  const conf = confidencePercent(flag.confidence);

                  return (
                    <div
                      key={flag.id}
                      className={`rounded-xl border transition-all ${status.bg} ${flag.status === 'pending_review' ? 'border-amber-200 dark:border-amber-800' : 'border-slate-200 dark:border-slate-700'}`}
                      data-testid={`risk-flag-${flag.id}`}
                    >
                      <div className="p-4">
                        <div className="flex flex-col lg:flex-row lg:items-start gap-4">
                          {/* Risk Score Circle */}
                          <div className="flex-shrink-0 w-16 h-16 rounded-full border-4 border-slate-200 dark:border-slate-600 flex flex-col items-center justify-center bg-white dark:bg-slate-800">
                            <span className={`text-lg leading-none ${riskColor(conf)}`}>{conf}</span>
                            <span className="text-[10px] text-slate-400 uppercase tracking-wide">risk</span>
                          </div>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap mb-1">
                              <h4 className="font-semibold text-slate-900 dark:text-white truncate">
                                {flag.auction_title || 'Unnamed Auction'}
                              </h4>
                              <Badge className={`${severity.bg} text-white text-xs`}>
                                {(flag.flag_type || '').replace(/_/g, ' ')}
                              </Badge>
                              <Badge variant="outline" className={`${status.color} text-xs gap-1`}>
                                <StatusIcon className="h-3 w-3" />
                                {status.label}
                              </Badge>
                            </div>
                            <p className="text-sm text-slate-500 dark:text-slate-400 mb-1">
                              Seller: <span className="font-medium">{flag.seller_name || 'Unknown'}</span>
                              {flag.auction_id && <span className="ml-2 text-xs text-slate-400">ID: {flag.auction_id}</span>}
                            </p>
                            <p className="text-sm text-slate-600 dark:text-slate-300">{flag.reason}</p>
                            {flag.ai_summary && (
                              <div className="mt-2 p-2.5 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                                <div className="flex items-center gap-1.5 mb-1">
                                  <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                                  <span className="text-xs font-medium text-purple-600 dark:text-purple-300">AI Analysis</span>
                                </div>
                                <p className="text-xs text-purple-700 dark:text-purple-200">{flag.ai_summary}</p>
                              </div>
                            )}
                          </div>

                          {/* Timestamp */}
                          <div className="text-right flex-shrink-0">
                            <p className="text-xs text-slate-400">
                              {flag.detected_at ? new Date(flag.detected_at).toLocaleDateString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                            </p>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-200/60 dark:border-slate-700/60 flex-wrap">
                          {flag.auction_id && (
                            <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => window.open(`/vehicle/${flag.auction_id}`, '_blank')} data-testid={`view-auction-${flag.id}`}>
                              <Eye className="h-3.5 w-3.5" /> View Auction
                            </Button>
                          )}

                          {flag.status === 'pending_review' && (
                            <>
                              <Button
                                size="sm"
                                className="gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                                onClick={() => { setClearDialog({ open: true, flagId: flag.id, flagTitle: flag.auction_title || flag.flag_type }); }}
                                data-testid={`clear-flag-${flag.id}`}
                              >
                                <CheckCircle className="h-3.5 w-3.5" /> Clear (False Positive)
                              </Button>
                              <Button variant="outline" size="sm" className="gap-1.5 text-xs text-blue-600" onClick={() => handleStatusUpdate(flag.id, 'under_investigation')} data-testid={`investigate-flag-${flag.id}`}>
                                <Search className="h-3.5 w-3.5" /> Investigate
                              </Button>
                            </>
                          )}

                          {flag.status === 'under_investigation' && (
                            <>
                              <Button
                                size="sm"
                                className="gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                                onClick={() => { setClearDialog({ open: true, flagId: flag.id, flagTitle: flag.auction_title || flag.flag_type }); }}
                                data-testid={`clear-investigated-${flag.id}`}
                              >
                                <CheckCircle className="h-3.5 w-3.5" /> Clear
                              </Button>
                              <Button variant="outline" size="sm" className="gap-1.5 text-xs text-red-600" onClick={() => handleStatusUpdate(flag.id, 'confirmed_fraud')} data-testid={`confirm-fraud-${flag.id}`}>
                                <XCircle className="h-3.5 w-3.5" /> Confirm Fraud
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        /* ─── USERS VIEW ─── */
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <UserX className="h-5 w-5 text-purple-500" />
              High-Risk Users
            </CardTitle>
            <CardDescription>
              {filteredUsers.length === 0
                ? 'No users above the selected risk threshold'
                : `${filteredUsers.length} user${filteredUsers.length !== 1 ? 's' : ''} with risk score >= ${threshold}`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {filteredUsers.length === 0 ? (
              <div className="text-center py-16" data-testid="no-users-message">
                <CheckCircle className="h-14 w-14 text-emerald-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">No High-Risk Users</h3>
                <p className="text-slate-500 text-sm">All users are below the {threshold}% risk threshold.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredUsers.map((user) => {
                  const behavior = behaviorData[user.user_id];
                  const isExpanded = expandedFlag === user.user_id;

                  return (
                    <div
                      key={user.user_id}
                      className="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden transition-all"
                      data-testid={`risk-user-${user.user_id}`}
                    >
                      <div className="p-4 flex flex-col sm:flex-row sm:items-center gap-4">
                        {/* Risk Score */}
                        <div className="flex-shrink-0 w-14 h-14 rounded-full border-4 border-red-200 dark:border-red-800 flex flex-col items-center justify-center bg-red-50 dark:bg-red-950/30">
                          <span className={`text-lg leading-none ${riskColor(user.risk_score)}`}>{user.risk_score}</span>
                          <span className="text-[9px] text-red-400 uppercase">risk</span>
                        </div>

                        {/* User Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="font-semibold text-slate-900 dark:text-white">{user.name}</h4>
                            {!user.is_verified && (
                              <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">Unverified</Badge>
                            )}
                            {user.province && (
                              <span className="flex items-center gap-1 text-xs text-slate-400">
                                <MapPin className="h-3 w-3" />{user.province}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-slate-500">{user.email}</p>
                          <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                            <span className="flex items-center gap-1"><Shield className="h-3 w-3" /> Trust: {user.trust_score}/100</span>
                            {user.created_at && (
                              <span className="flex items-center gap-1">
                                <Calendar className="h-3 w-3" />
                                Joined {new Date(user.created_at).toLocaleDateString('en-CA', { month: 'short', year: 'numeric' })}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-1.5 text-xs"
                            onClick={() => fetchBehavior(user.user_id)}
                            disabled={loadingBehavior === user.user_id}
                            data-testid={`analyze-user-${user.user_id}`}
                          >
                            {loadingBehavior === user.user_id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Activity className="h-3.5 w-3.5" />
                            )}
                            {isExpanded ? 'Hide' : 'Analyze'}
                            {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                          </Button>
                        </div>
                      </div>

                      {/* Expanded Behavioral Analysis */}
                      {isExpanded && behavior && (
                        <div className="px-4 pb-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30" data-testid={`behavior-panel-${user.user_id}`}>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3">
                            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                              <p className="text-xs text-slate-500 mb-1">Behavior Score</p>
                              <p className={`text-xl font-bold ${behavior.behavior_score < 40 ? 'text-red-600' : behavior.behavior_score < 70 ? 'text-amber-500' : 'text-emerald-600'}`}>
                                {behavior.behavior_score}
                              </p>
                            </div>
                            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                              <p className="text-xs text-slate-500 mb-1">Total Bids</p>
                              <p className="text-xl font-bold text-slate-900 dark:text-white">{behavior.statistics?.total_bids || 0}</p>
                            </div>
                            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                              <p className="text-xs text-slate-500 mb-1">Avg Bid</p>
                              <p className="text-xl font-bold text-slate-900 dark:text-white">${Math.round(behavior.statistics?.average_bid || 0)}</p>
                            </div>
                            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                              <p className="text-xs text-slate-500 mb-1">Flagged Msgs</p>
                              <p className={`text-xl font-bold ${(behavior.statistics?.flagged_messages || 0) > 0 ? 'text-red-600' : 'text-slate-900 dark:text-white'}`}>
                                {behavior.statistics?.flagged_messages || 0}
                              </p>
                            </div>
                          </div>
                          {behavior.risk_indicators?.filter(Boolean).length > 0 && (
                            <div className="mt-3 p-3 bg-red-50 dark:bg-red-950/20 rounded-lg border border-red-200 dark:border-red-800">
                              <p className="text-xs font-semibold text-red-700 dark:text-red-300 mb-1 flex items-center gap-1"><TrendingDown className="h-3 w-3" /> Risk Indicators</p>
                              <ul className="space-y-1">
                                {behavior.risk_indicators.filter(Boolean).map((ind, i) => (
                                  <li key={i} className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1.5">
                                    <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                                    {ind}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {behavior.recommended_actions?.filter(Boolean).length > 0 && (
                            <div className="mt-2 p-3 bg-amber-50 dark:bg-amber-950/20 rounded-lg border border-amber-200 dark:border-amber-800">
                              <p className="text-xs font-semibold text-amber-700 dark:text-amber-300 mb-1">Recommended Actions</p>
                              <div className="flex flex-wrap gap-2">
                                {behavior.recommended_actions.filter(Boolean).map((action, i) => (
                                  <Badge key={i} variant="outline" className="text-xs text-amber-600 border-amber-300">{action}</Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Quebec Buyer Notice */}
      <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center flex-shrink-0">
              <MapPin className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h4 className="font-semibold text-blue-900 dark:text-blue-100 mb-1">False Positive Prevention</h4>
              <p className="text-sm text-blue-700 dark:text-blue-300">
                Legitimate Quebec buyers may appear as high-risk due to new account age combined with high-value bids.
                Use the &quot;Clear (False Positive)&quot; action with notes to whitelist these users.
                The behavioral analysis panel helps distinguish genuine bidders from suspicious accounts.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Clear Dialog */}
      <Dialog open={clearDialog.open} onOpenChange={(open) => { if (!open) setClearDialog({ open: false, flagId: null, flagTitle: '' }); }}>
        <DialogContent data-testid="clear-flag-dialog">
          <DialogHeader>
            <DialogTitle>Clear Flag — False Positive</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-500 mb-2">
            Clearing: <span className="font-medium text-slate-700 dark:text-slate-300">{clearDialog.flagTitle}</span>
          </p>
          <Input
            placeholder="Add notes (e.g., 'Verified Quebec buyer, legitimate high-value bid')"
            value={clearNotes}
            onChange={(e) => setClearNotes(e.target.value)}
            data-testid="clear-notes-input"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setClearDialog({ open: false, flagId: null, flagTitle: '' })} data-testid="clear-cancel-btn">
              Cancel
            </Button>
            <Button
              onClick={handleClearFlag}
              disabled={clearing}
              className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2"
              data-testid="clear-confirm-btn"
            >
              {clearing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
              Confirm Clear
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default RiskMonitoringDashboard;
