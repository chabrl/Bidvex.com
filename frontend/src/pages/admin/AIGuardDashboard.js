/**
 * AI Guard Dashboard - Fraud Detection Status
 * Shows flagged auctions and AI-detected suspicious activity
 */

import React, { useState, useEffect } from 'react';
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
  Eye, Ban, RefreshCw, Filter, ChevronRight, Bot,
  TrendingUp, Users, Package, XCircle
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Mock data for demonstration (replace with real API calls)
const MOCK_FLAGGED_AUCTIONS = [
  {
    id: 'flag-001',
    auction_id: 'AUC-2024-0892',
    auction_title: '2022 BMW M3 Competition',
    seller_name: 'AutoDealer Pro',
    seller_id: 'seller-123',
    flag_type: 'price_anomaly',
    confidence: 0.89,
    reason: 'Starting price 40% below market average for similar vehicles',
    detected_at: '2026-02-26T10:30:00Z',
    status: 'pending_review',
  },
  {
    id: 'flag-002',
    auction_id: 'AUC-2024-0876',
    auction_title: '2021 Tesla Model S Plaid',
    seller_name: 'QuickFlip Motors',
    seller_id: 'seller-456',
    flag_type: 'bid_manipulation',
    confidence: 0.95,
    reason: 'Multiple bids from accounts with similar IP addresses and registration dates',
    detected_at: '2026-02-26T09:15:00Z',
    status: 'under_investigation',
  },
  {
    id: 'flag-003',
    auction_id: 'AUC-2024-0845',
    auction_title: 'Vintage 1967 Ford Mustang',
    seller_name: 'Classic Car Haven',
    seller_id: 'seller-789',
    flag_type: 'image_mismatch',
    confidence: 0.72,
    reason: 'Vehicle images appear to be from different sources with inconsistent backgrounds',
    detected_at: '2026-02-25T16:45:00Z',
    status: 'cleared',
  },
];

// Flag type configurations
const FLAG_TYPES = {
  price_anomaly: { label: 'Price Anomaly', color: 'bg-amber-500', icon: TrendingUp },
  bid_manipulation: { label: 'Bid Manipulation', color: 'bg-red-500', icon: Users },
  image_mismatch: { label: 'Image Mismatch', color: 'bg-purple-500', icon: Package },
  duplicate_listing: { label: 'Duplicate Listing', color: 'bg-blue-500', icon: Package },
  suspicious_activity: { label: 'Suspicious Activity', color: 'bg-orange-500', icon: AlertTriangle },
};

// Status configurations
const STATUS_CONFIGS = {
  pending_review: { label: 'Pending Review', color: 'bg-yellow-500', textColor: 'text-yellow-700' },
  under_investigation: { label: 'Under Investigation', color: 'bg-blue-500', textColor: 'text-blue-700' },
  cleared: { label: 'Cleared', color: 'bg-green-500', textColor: 'text-green-700' },
  confirmed_fraud: { label: 'Confirmed Fraud', color: 'bg-red-500', textColor: 'text-red-700' },
};

const AIGuardDashboard = () => {
  const [flaggedAuctions, setFlaggedAuctions] = useState(MOCK_FLAGGED_AUCTIONS);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Stats calculation
  const stats = {
    total: flaggedAuctions.length,
    pending: flaggedAuctions.filter(f => f.status === 'pending_review').length,
    investigating: flaggedAuctions.filter(f => f.status === 'under_investigation').length,
    cleared: flaggedAuctions.filter(f => f.status === 'cleared').length,
    confirmed: flaggedAuctions.filter(f => f.status === 'confirmed_fraud').length,
  };

  // Filter auctions
  const filteredAuctions = flaggedAuctions.filter(auction => {
    const matchesStatus = filterStatus === 'all' || auction.status === filterStatus;
    const matchesType = filterType === 'all' || auction.flag_type === filterType;
    const matchesSearch = searchQuery === '' || 
      auction.auction_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      auction.seller_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      auction.auction_id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesType && matchesSearch;
  });

  const handleStatusUpdate = async (flagId, newStatus) => {
    // In production, this would call the API
    setFlaggedAuctions(prev => 
      prev.map(f => f.id === flagId ? { ...f, status: newStatus } : f)
    );
    toast.success(`Status updated to ${STATUS_CONFIGS[newStatus]?.label || newStatus}`);
  };

  const formatConfidence = (confidence) => {
    const percent = Math.round(confidence * 100);
    if (percent >= 90) return { text: `${percent}%`, color: 'text-red-500' };
    if (percent >= 75) return { text: `${percent}%`, color: 'text-amber-500' };
    return { text: `${percent}%`, color: 'text-blue-500' };
  };

  const formatDate = (dateStr) => {
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
        <Button 
          variant="outline" 
          onClick={() => toast.info('Refreshing flagged auctions...')}
          className="gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
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
                <p className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">{stats.pending}</p>
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
                <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">{stats.investigating}</p>
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
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">{stats.confirmed}</p>
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
            <Select value={filterStatus} onValueChange={setFilterStatus}>
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
            <Select value={filterType} onValueChange={setFilterType}>
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
            {filteredAuctions.length} auction{filteredAuctions.length !== 1 ? 's' : ''} flagged for review
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filteredAuctions.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle className="h-12 w-12 text-green-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-2">
                All Clear!
              </h3>
              <p className="text-slate-500 dark:text-slate-400">
                No flagged auctions match your current filters.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredAuctions.map((auction) => {
                const flagConfig = FLAG_TYPES[auction.flag_type] || FLAG_TYPES.suspicious_activity;
                const statusConfig = STATUS_CONFIGS[auction.status] || STATUS_CONFIGS.pending_review;
                const confidence = formatConfidence(auction.confidence);
                const FlagIcon = flagConfig.icon;

                return (
                  <div
                    key={auction.id}
                    className="p-4 border border-slate-200 dark:border-slate-700 rounded-xl hover:border-slate-300 dark:hover:border-slate-600 transition-colors"
                    data-testid={`flagged-auction-${auction.id}`}
                  >
                    <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                      {/* Flag Type Icon */}
                      <div className={`w-12 h-12 ${flagConfig.color} rounded-xl flex items-center justify-center flex-shrink-0`}>
                        <FlagIcon className="h-6 w-6 text-white" />
                      </div>

                      {/* Main Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-slate-900 dark:text-white truncate">
                            {auction.auction_title}
                          </h4>
                          <Badge variant="outline" className="text-xs">
                            {auction.auction_id}
                          </Badge>
                        </div>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
                          Seller: <span className="font-medium">{auction.seller_name}</span>
                        </p>
                        <p className="text-sm text-slate-600 dark:text-slate-300">
                          {auction.reason}
                        </p>
                      </div>

                      {/* Meta Info */}
                      <div className="flex flex-col gap-2 lg:items-end flex-shrink-0">
                        <div className="flex items-center gap-2">
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
                          <span className="text-slate-400 dark:text-slate-500">
                            {formatDate(auction.detected_at)}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1"
                          onClick={() => toast.info(`Viewing auction ${auction.auction_id}`)}
                        >
                          <Eye className="h-4 w-4" />
                          View
                        </Button>
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
                              <Ban className="h-4 w-4" />
                              Confirm Fraud
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
                AI Guard uses machine learning to automatically detect potential fraud, bid manipulation, 
                and suspicious activity across all auctions. Flags are generated based on pattern analysis, 
                price anomalies, and behavioral signals. All flags require human review before action is taken.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AIGuardDashboard;
