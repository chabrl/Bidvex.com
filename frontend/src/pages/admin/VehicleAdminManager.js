import API_BASE from '../../config';
/**
 * Vehicle Admin Manager
 * Admin panel for managing vehicle auction sellers and listings
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import {
  Car, User, Building2, Gavel, CheckCircle, XCircle, Clock,
  Eye, FileText, Shield, AlertTriangle, Search, RefreshCw,
  ChevronDown, ChevronUp, ExternalLink, Calendar, MapPin,
  DollarSign, Settings2, Percent, Timer, Scale, Award, Mail
} from 'lucide-react';
import { formatCurrency } from '../../utils/currencyFormatter';
import { useTranslation } from 'react-i18next';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';

const API = API_BASE;

const formatDate = (date) => {
  if (!date) return 'N/A';
  return new Date(date).toLocaleDateString('en-CA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

// Seller Card Component
const SellerCard = ({ seller, onApprove, onReject, onViewDetails, onToggleOpc, actionBusy }) => {
  const [expanded, setExpanded] = useState(false);
  const [opcNumber, setOpcNumber] = useState(seller.opc_permit_number || '');
  const opcVerified = !!seller.opc_permit_verified;
  
  const getSellerTypeIcon = (type) => {
    switch (type) {
      case 'dealer': return <Building2 className="h-5 w-5 text-green-600" />;
      case 'auctioneer': return <Gavel className="h-5 w-5 text-purple-600" />;
      default: return <User className="h-5 w-5 text-blue-600" />;
    }
  };
  
  const getStatusBadge = (status) => {
    const configs = {
      pending: { color: 'bg-yellow-500', label: 'Pending' },
      under_review: { color: 'bg-blue-500', label: 'Under Review' },
      approved: { color: 'bg-green-500', label: 'Approved' },
      rejected: { color: 'bg-red-500', label: 'Rejected' },
      suspended: { color: 'bg-orange-500', label: 'Suspended' },
    };
    const config = configs[status] || configs.pending;
    return <Badge className={config.color}>{config.label}</Badge>;
  };
  
  return (
    <Card className="mb-4">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center">
              {getSellerTypeIcon(seller.seller_type)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-lg">
                  {seller.business_name || seller.user?.full_name || 'Private Seller'}
                </h3>
                {getStatusBadge(seller.verification_status)}
              </div>
              <p className="text-sm text-slate-500">
                {seller.user?.email} • Registered {formatDate(seller.created_at)}
              </p>
              <div className="flex items-center gap-4 mt-2">
                <Badge variant="outline" className="capitalize">
                  {seller.seller_type}
                </Badge>
                <span className="text-sm text-slate-500">
                  Limit: {seller.monthly_listing_count}/{seller.monthly_listing_limit} this month
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        
        {expanded && (
          <div className="mt-4 pt-4 border-t space-y-4">
            {/* Business Details */}
            {seller.seller_type !== 'private' && (
              <div className="grid grid-cols-2 gap-4 text-sm">
                {seller.business_address && (
                  <div>
                    <p className="text-slate-500">Address</p>
                    <p className="font-medium">{seller.business_address}</p>
                  </div>
                )}
                {seller.business_phone && (
                  <div>
                    <p className="text-slate-500">Phone</p>
                    <p className="font-medium">{seller.business_phone}</p>
                  </div>
                )}
                {seller.license_number && (
                  <div>
                    <p className="text-slate-500">License #</p>
                    <p className="font-medium">{seller.license_number} ({seller.license_province})</p>
                  </div>
                )}
                {seller.tax_id && (
                  <div>
                    <p className="text-slate-500">Tax ID</p>
                    <p className="font-medium">{seller.tax_id}</p>
                  </div>
                )}
              </div>
            )}
            
            {/* Documents */}
            {seller.documents?.length > 0 && (
              <div>
                <p className="text-sm text-slate-500 mb-2">Uploaded Documents</p>
                <div className="flex flex-wrap gap-2">
                  {seller.documents.map((doc, idx) => (
                    <Badge key={idx} variant="outline" className="gap-1">
                      <FileText className="h-3 w-3" />
                      {doc.document_type.replace('_', ' ')}
                      {doc.verified && <CheckCircle className="h-3 w-3 text-green-500" />}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            
            {/* Description */}
            {seller.description && (
              <div>
                <p className="text-sm text-slate-500 mb-1">Description</p>
                <p className="text-sm">{seller.description}</p>
              </div>
            )}
            
            {/* Stats */}
            <div className="grid grid-cols-4 gap-4 text-center bg-slate-50 rounded-lg p-3">
              <div>
                <p className="text-xl font-bold">{seller.total_listings}</p>
                <p className="text-xs text-slate-500">Total Listings</p>
              </div>
              <div>
                <p className="text-xl font-bold">{seller.total_sold}</p>
                <p className="text-xs text-slate-500">Sold</p>
              </div>
              <div>
                <p className="text-xl font-bold">{formatCurrency(seller.total_revenue || 0)}</p>
                <p className="text-xs text-slate-500">Revenue</p>
              </div>
              <div>
                <p className="text-xl font-bold">{seller.average_rating?.toFixed(1) || 'N/A'}</p>
                <p className="text-xs text-slate-500">Rating</p>
              </div>
            </div>
            
            {/* OPC Permit Verification (vehicle sellers) */}
            <div className={`rounded-lg p-3 border ${opcVerified ? 'bg-green-50 border-green-200' : 'bg-amber-50 border-amber-200'}`} data-testid={`opc-panel-${seller.id}`}>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <p className="text-sm font-semibold flex items-center gap-2">
                    OPC Permit Verification
                    {opcVerified ? (
                      <Badge className="bg-green-600 text-white text-[10px]">VERIFIED</Badge>
                    ) : (
                      <Badge className="bg-amber-500 text-white text-[10px]">UNVERIFIED</Badge>
                    )}
                  </p>
                  <p className="text-[11px] text-slate-500">
                    Quebec Consumer Protection permit (dealers must register). / Permis OPC requis pour les concessionnaires du Québec.
                  </p>
                </div>
              </div>
              <div className="flex gap-2 mt-2 items-center">
                <Input
                  placeholder="OPC permit number"
                  value={opcNumber}
                  onChange={(e) => setOpcNumber(e.target.value)}
                  className="h-8 text-sm max-w-xs"
                  data-testid={`opc-number-input-${seller.id}`}
                />
                <Button
                  size="sm"
                  variant={opcVerified ? 'outline' : 'default'}
                  className={opcVerified ? '' : 'bg-green-600 hover:bg-green-700 text-white'}
                  disabled={actionBusy === `opc-${seller.id}`}
                  onClick={() => onToggleOpc(seller, !opcVerified, opcNumber)}
                  data-testid={`opc-toggle-btn-${seller.id}`}
                >
                  {actionBusy === `opc-${seller.id}` ? 'Saving…' : (opcVerified ? 'Un-verify' : 'Mark Verified')}
                </Button>
              </div>
            </div>

            {/* Actions */}
            {(seller.verification_status === 'pending' || seller.verification_status === 'under_review') && (
              <div className="flex gap-2 pt-2">
                <Button 
                  onClick={() => onApprove(seller)}
                  className="gap-2 bg-green-600 hover:bg-green-700"
                  disabled={actionBusy === `seller-${seller.id}`}
                  data-testid={`approve-seller-btn-${seller.id}`}
                >
                  <CheckCircle className="h-4 w-4" /> {actionBusy === `seller-${seller.id}` ? 'Approving…' : 'Approve Seller'}
                </Button>
                <Button 
                  variant="destructive"
                  onClick={() => onReject(seller)}
                  className="gap-2"
                  disabled={!!actionBusy}
                  data-testid={`reject-seller-btn-${seller.id}`}
                >
                  <XCircle className="h-4 w-4" /> Reject
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Vehicle Listing Card Component
const VehicleListingCard = ({ vehicle, onApprove, onReject, onView, actionBusy }) => {
  const [expanded, setExpanded] = useState(false);
  
  const getStatusBadge = (status) => {
    const configs = {
      draft: { color: 'bg-slate-500', label: 'Draft' },
      pending_approval: { color: 'bg-yellow-500', label: 'Pending Approval' },
      approved: { color: 'bg-blue-500', label: 'Approved' },
      active: { color: 'bg-green-500', label: 'Active' },
      ended: { color: 'bg-slate-500', label: 'Ended' },
      sold: { color: 'bg-purple-500', label: 'Sold' },
      rejected: { color: 'bg-red-500', label: 'Rejected' },
      cancelled: { color: 'bg-red-500', label: 'Cancelled' },
    };
    const config = configs[status] || configs.draft;
    return <Badge className={config.color}>{config.label}</Badge>;
  };
  
  const mainImage = vehicle.media?.find(m => m.category === 'front')?.url || 
                    vehicle.media?.[0]?.url;
  
  return (
    <Card className="mb-4 overflow-hidden">
      <div className="flex">
        {/* Thumbnail */}
        <div className="w-48 h-32 bg-slate-100 flex-shrink-0">
          {mainImage ? (
            <img src={mainImage} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Car className="h-12 w-12 text-slate-300" />
            </div>
          )}
        </div>
        
        {/* Content */}
        <CardContent className="flex-1 p-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">
                  {vehicle.year} {vehicle.make} {vehicle.model} {vehicle.trim || ''}
                </h3>
                {getStatusBadge(vehicle.status)}
              </div>
              <p className="text-sm text-slate-500 mt-1">
                VIN: {vehicle.vin} • Submitted {formatDate(vehicle.created_at)}
              </p>
              <div className="flex items-center gap-4 mt-2 text-sm">
                <span className="flex items-center gap-1">
                  <MapPin className="h-4 w-4 text-slate-400" />
                  {vehicle.location_city}, {vehicle.location_province}
                </span>
                <span>Starting: {formatCurrency(vehicle.starting_price)}</span>
                {vehicle.reserve_price && (
                  <span className="text-slate-500">Reserve: {formatCurrency(vehicle.reserve_price)}</span>
                )}
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => onView(vehicle)}>
                <Eye className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
                {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          
          {expanded && (
            <div className="mt-4 pt-4 border-t space-y-4">
              {/* Specs */}
              <div className="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-slate-500">Mileage</p>
                  <p className="font-medium">{vehicle.mileage?.toLocaleString()} km</p>
                </div>
                <div>
                  <p className="text-slate-500">Title Status</p>
                  <Badge className={vehicle.title_status === 'clean' ? 'bg-green-500' : 'bg-yellow-500'}>
                    {vehicle.title_status}
                  </Badge>
                </div>
                <div>
                  <p className="text-slate-500">Auction Type</p>
                  <p className="font-medium capitalize">{vehicle.auction_type}</p>
                </div>
                <div>
                  <p className="text-slate-500">Photos</p>
                  <p className="font-medium">{vehicle.media?.length || 0} uploaded</p>
                </div>
              </div>
              
              {/* Condition Summary */}
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-sm text-slate-500 mb-2">Condition Summary</p>
                <div className="flex flex-wrap gap-2">
                  {vehicle.condition_report?.is_running ? (
                    <Badge className="bg-green-100 text-green-700">Running</Badge>
                  ) : (
                    <Badge className="bg-red-100 text-red-700">Non-Running</Badge>
                  )}
                  {vehicle.condition_report?.has_accident_history && (
                    <Badge className="bg-yellow-100 text-yellow-700">Accident History</Badge>
                  )}
                  {vehicle.condition_report?.has_flood_damage && (
                    <Badge className="bg-red-100 text-red-700">Flood Damage</Badge>
                  )}
                  {vehicle.condition_report?.has_fire_damage && (
                    <Badge className="bg-red-100 text-red-700">Fire Damage</Badge>
                  )}
                </div>
              </div>
              
              {/* Seller Info */}
              <div className="flex items-center gap-2 text-sm">
                <span className="text-slate-500">Seller:</span>
                <Badge variant="outline" className="capitalize">
                  {vehicle.seller?.seller_type || 'Unknown'}
                </Badge>
                <span>{vehicle.seller?.business_name || 'Private Seller'}</span>
              </div>
              
              {/* Actions */}
              {vehicle.status === 'pending_approval' && (
                <div className="flex gap-2 pt-2">
                  <Button 
                    onClick={() => onApprove(vehicle)}
                    className="gap-2 bg-green-600 hover:bg-green-700"
                    disabled={actionBusy === `vehicle-${vehicle.id}`}
                    data-testid={`approve-vehicle-btn-${vehicle.id}`}
                  >
                    <CheckCircle className="h-4 w-4" /> {actionBusy === `vehicle-${vehicle.id}` ? 'Approving…' : 'Approve Listing'}
                  </Button>
                  <Button 
                    variant="destructive"
                    onClick={() => onReject(vehicle)}
                    className="gap-2"
                    disabled={!!actionBusy}
                    data-testid={`reject-vehicle-btn-${vehicle.id}`}
                  >
                    <XCircle className="h-4 w-4" /> Reject
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </div>
    </Card>
  );
};

// Main Component
const VehicleAdminManager = () => {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('system-settings');
  const [loading, setLoading] = useState(true);
  const [pendingSellers, setPendingSellers] = useState([]);
  const [pendingVehicles, setPendingVehicles] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  // System settings state
  const [systemSettings, setSystemSettings] = useState({
    vehicle_auctions_enabled: false,
    vehicle_listing_enabled: false,
    vehicle_bidding_enabled: false,
  });
  const [settingsLoading, setSettingsLoading] = useState(false);
  
  // Dialog states
  const [rejectDialog, setRejectDialog] = useState({ open: false, item: null, type: null });
  const [rejectReason, setRejectReason] = useState('');
  const [actionBusy, setActionBusy] = useState(null); // id-string for the row currently processing
  
  // Stats
  const [stats, setStats] = useState({
    pendingSellers: 0,
    pendingVehicles: 0,
    activeSellers: 0,
    activeVehicles: 0,
  });

  // Fetch system settings
  const fetchSystemSettings = useCallback(async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/vehicle-admin/system/settings`, { headers });
      setSystemSettings(response.data);
    } catch (error) {
      console.error('Failed to fetch system settings:', error);
    }
  }, [token]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      
      // Fetch system settings
      await fetchSystemSettings();
      
      // Fetch pending sellers
      const sellersResp = await axios.get(`${API}/vehicle-admin/pending-sellers`, { headers });
      setPendingSellers(sellersResp.data.sellers || []);
      
      // Fetch pending vehicles
      const vehiclesResp = await axios.get(`${API}/vehicle-admin/pending-vehicles`, { headers });
      setPendingVehicles(vehiclesResp.data.vehicles || []);
      
      // Fetch audit logs
      const logsResp = await axios.get(`${API}/vehicle-admin/audit-logs?limit=50`, { headers });
      setAuditLogs(logsResp.data.logs || []);
      
      // Update stats
      setStats({
        pendingSellers: sellersResp.data.sellers?.length || 0,
        pendingVehicles: vehiclesResp.data.vehicles?.length || 0,
      });
      
    } catch (error) {
      console.error('Failed to fetch vehicle admin data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [token, fetchSystemSettings]);

  // Toggle vehicle auctions
  const toggleVehicleAuctions = async (enabled) => {
    setSettingsLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(`${API}/vehicle-admin/system/toggle-auctions?enabled=${enabled}`, {}, { headers });
      setSystemSettings(prev => ({
        ...prev,
        vehicle_auctions_enabled: enabled,
        vehicle_bidding_enabled: enabled,
      }));
      toast.success(`Vehicle auctions ${enabled ? 'enabled' : 'disabled'}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update settings');
    } finally {
      setSettingsLoading(false);
    }
  };

  // Toggle vehicle listing
  const toggleVehicleListing = async (enabled) => {
    setSettingsLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(`${API}/vehicle-admin/system/toggle-listing?enabled=${enabled}`, {}, { headers });
      setSystemSettings(prev => ({
        ...prev,
        vehicle_listing_enabled: enabled,
      }));
      toast.success(`Vehicle listing ${enabled ? 'enabled' : 'disabled'}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update settings');
    } finally {
      setSettingsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleApproveSeller = async (seller) => {
    if (actionBusy) return;
    setActionBusy(`seller-${seller.id}`);
    try {
      await axios.post(`${API}/vehicle-admin/sellers/${seller.id}/approve`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Seller "${seller.business_name || 'Private Seller'}" approved`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to approve seller');
    } finally {
      setActionBusy(null);
    }
  };

  const handleToggleOpc = async (seller, enable, permitNumber) => {
    if (actionBusy) return;
    const userId = seller.user_id || seller.user?.id;
    if (!userId) {
      toast.error('Seller user ID missing');
      return;
    }
    if (enable && !permitNumber?.trim()) {
      toast.error('Enter the OPC permit number before marking verified / Saisissez le numéro de permis OPC');
      return;
    }
    setActionBusy(`opc-${seller.id}`);
    try {
      await axios.put(`${API}/admin/users/${userId}/opc-verify`, {
        opc_permit_verified: enable,
        opc_permit_number: permitNumber || null,
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(enable ? 'OPC permit marked verified' : 'OPC verification removed');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update OPC permit');
    } finally {
      setActionBusy(null);
    }
  };

  const handleRejectSeller = async () => {
    if (!rejectDialog.item || !rejectReason.trim()) {
      toast.error('Please provide a rejection reason');
      return;
    }
    if (actionBusy) return;
    setActionBusy(`reject-seller-${rejectDialog.item.id}`);
    try {
      await axios.post(`${API}/vehicle-admin/sellers/${rejectDialog.item.id}/reject?reason=${encodeURIComponent(rejectReason)}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Seller rejected');
      setRejectDialog({ open: false, item: null, type: null });
      setRejectReason('');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to reject seller');
    } finally {
      setActionBusy(null);
    }
  };

  const handleApproveVehicle = async (vehicle) => {
    if (actionBusy) return;
    setActionBusy(`vehicle-${vehicle.id}`);
    try {
      await axios.post(`${API}/vehicle-admin/vehicles/${vehicle.id}/approve`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Vehicle "${vehicle.year} ${vehicle.make} ${vehicle.model}" approved`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to approve vehicle');
    } finally {
      setActionBusy(null);
    }
  };

  const handleRejectVehicle = async () => {
    if (!rejectDialog.item || !rejectReason.trim()) {
      toast.error('Please provide a rejection reason');
      return;
    }
    if (actionBusy) return;
    setActionBusy(`reject-vehicle-${rejectDialog.item.id}`);
    try {
      await axios.post(`${API}/vehicle-admin/vehicles/${rejectDialog.item.id}/reject?reason=${encodeURIComponent(rejectReason)}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Vehicle listing rejected');
      setRejectDialog({ open: false, item: null, type: null });
      setRejectReason('');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to reject vehicle');
    } finally {
      setActionBusy(null);
    }
  };

  const openRejectDialog = (item, type) => {
    setRejectDialog({ open: true, item, type });
    setRejectReason('');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="vehicle-admin-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Car className="h-6 w-6" />
            Vehicle Auction Administration
          </h2>
          <p className="text-slate-500 mt-1">
            Manage vehicle sellers and listings
          </p>
        </div>
        <Button onClick={fetchData} variant="outline" className="gap-2">
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
                <Clock className="h-5 w-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats.pendingSellers}</p>
                <p className="text-sm text-slate-500">Pending Sellers</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <Car className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats.pendingVehicles}</p>
                <p className="text-sm text-slate-500">Pending Vehicles</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{pendingSellers.filter(s => s.verification_status === 'approved').length}</p>
                <p className="text-sm text-slate-500">Approved Sellers</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                <Shield className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{auditLogs.length}</p>
                <p className="text-sm text-slate-500">Audit Entries</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex flex-wrap bg-transparent">
          <TabsTrigger value="system-settings" className="gap-2 bg-transparent">
            <Shield className="h-4 w-4" />
            System Settings
          </TabsTrigger>
          <TabsTrigger value="fee-config" className="gap-2 bg-transparent">
            <DollarSign className="h-4 w-4" />
            Fee Config
          </TabsTrigger>
          <TabsTrigger value="pending-sellers" className="gap-2 bg-transparent">
            <User className="h-4 w-4" />
            Pending Sellers
            {stats.pendingSellers > 0 && (
              <Badge className="ml-1 bg-yellow-500">{stats.pendingSellers}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="pending-vehicles" className="gap-2 bg-transparent">
            <Car className="h-4 w-4" />
            Pending Vehicles
            {stats.pendingVehicles > 0 && (
              <Badge className="ml-1 bg-yellow-500">{stats.pendingVehicles}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="auction-rules" className="gap-2 bg-transparent">
            <Settings2 className="h-4 w-4" />
            Auction Rules
          </TabsTrigger>
          <TabsTrigger value="invoices" className="gap-2 bg-transparent" data-testid="admin-tab-invoices">
            <FileText className="h-4 w-4" />
            Invoices
          </TabsTrigger>
          <TabsTrigger value="audit-logs" className="gap-2 bg-transparent">
            <FileText className="h-4 w-4" />
            Audit Logs
          </TabsTrigger>
        </TabsList>

        {/* System Settings Tab */}
        <TabsContent value="system-settings" className="mt-6">
          <div className="grid gap-6">
            {/* System Status Overview */}
            <Card className={`border-2 ${systemSettings.vehicle_auctions_enabled ? 'border-green-500 bg-green-50 dark:bg-green-950/20' : 'border-amber-500 bg-amber-50 dark:bg-amber-950/20'}`}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {systemSettings.vehicle_auctions_enabled ? (
                    <CheckCircle className="h-6 w-6 text-green-600" />
                  ) : (
                    <AlertTriangle className="h-6 w-6 text-amber-600" />
                  )}
                  Vehicle Auction System Status
                </CardTitle>
                <CardDescription>
                  {systemSettings.vehicle_auctions_enabled 
                    ? 'Vehicle auctions are LIVE. Users can browse, bid, and interact with auctions.'
                    : 'Vehicle auctions are in DISCOVERY MODE. Users can browse but cannot list or bid.'}
                </CardDescription>
              </CardHeader>
            </Card>

            {/* Auction Controls */}
            <Card>
              <CardHeader>
                <CardTitle>{t("admin.enableVehicleAuctions")}</CardTitle>
                <CardDescription>
                  Master switch to enable/disable all vehicle auction functionality.
                  When OFF, the platform operates in discovery-only mode.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${systemSettings.vehicle_auctions_enabled ? 'bg-green-100' : 'bg-slate-200'}`}>
                      <Gavel className={`h-6 w-6 ${systemSettings.vehicle_auctions_enabled ? 'text-green-600' : 'text-slate-400'}`} />
                    </div>
                    <div>
                      <p className="font-semibold">Vehicle Auctions</p>
                      <p className="text-sm text-slate-500">
                        {systemSettings.vehicle_auctions_enabled ? 'Auctions are LIVE' : 'Auctions are PAUSED'}
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={() => toggleVehicleAuctions(!systemSettings.vehicle_auctions_enabled)}
                    disabled={settingsLoading}
                    className={systemSettings.vehicle_auctions_enabled 
                      ? 'bg-red-600 hover:bg-red-700' 
                      : 'bg-green-600 hover:bg-green-700'}
                  >
                    {settingsLoading ? (
                      <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                    ) : null}
                    {systemSettings.vehicle_auctions_enabled ? 'Disable Auctions' : 'Enable Auctions'}
                  </Button>
                </div>

                {/* Bidding Status */}
                <div className="flex items-center justify-between p-4 mt-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${systemSettings.vehicle_bidding_enabled ? 'bg-blue-100' : 'bg-slate-200'}`}>
                      <Car className={`h-6 w-6 ${systemSettings.vehicle_bidding_enabled ? 'text-blue-600' : 'text-slate-400'}`} />
                    </div>
                    <div>
                      <p className="font-semibold">Vehicle Bidding</p>
                      <p className="text-sm text-slate-500">
                        {systemSettings.vehicle_bidding_enabled ? 'Users CAN place bids' : 'Bidding is BLOCKED'}
                      </p>
                    </div>
                  </div>
                  <Badge className={systemSettings.vehicle_bidding_enabled ? 'bg-green-500' : 'bg-slate-400'}>
                    {systemSettings.vehicle_bidding_enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            {/* Listing Controls */}
            <Card>
              <CardHeader>
                <CardTitle>{t("admin.enableVehicleListing")}</CardTitle>
                <CardDescription>
                  Controls whether users can create new vehicle listings.
                  This is separate from auction viewing. Keep OFF until permits are approved.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${systemSettings.vehicle_listing_enabled ? 'bg-green-100' : 'bg-red-100'}`}>
                      <FileText className={`h-6 w-6 ${systemSettings.vehicle_listing_enabled ? 'text-green-600' : 'text-red-600'}`} />
                    </div>
                    <div>
                      <p className="font-semibold">Vehicle Listing Submission</p>
                      <p className="text-sm text-slate-500">
                        {systemSettings.vehicle_listing_enabled 
                          ? 'Users CAN submit vehicle listings' 
                          : 'All listing submissions BLOCKED'}
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={() => toggleVehicleListing(!systemSettings.vehicle_listing_enabled)}
                    disabled={settingsLoading}
                    className={systemSettings.vehicle_listing_enabled 
                      ? 'bg-red-600 hover:bg-red-700' 
                      : 'bg-green-600 hover:bg-green-700'}
                  >
                    {settingsLoading ? (
                      <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                    ) : null}
                    {systemSettings.vehicle_listing_enabled ? 'Disable Listing' : 'Enable Listing'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Warning Notice */}
            <Card className="border-amber-200 bg-amber-50 dark:bg-amber-950/20">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
                  <div>
                    <p className="font-semibold text-amber-800 dark:text-amber-200">Important: Permit Requirements</p>
                    <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                      Vehicle auctions require proper licensing and permits in Canada. 
                      Do not enable these features until all regulatory requirements are met.
                      Contact legal@bidvex.com for permit status.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Pending Sellers Tab */}
        <TabsContent value="pending-sellers" className="mt-6">
          {pendingSellers.length === 0 ? (
            <Card className="p-12 text-center">
              <CheckCircle className="h-16 w-16 text-green-300 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2">All Caught Up!</h3>
              <p className="text-slate-500">No pending seller applications.</p>
            </Card>
          ) : (
            <div>
              {pendingSellers.map((seller) => (
                <SellerCard
                  key={seller.id}
                  seller={seller}
                  onApprove={handleApproveSeller}
                  onReject={(s) => openRejectDialog(s, 'seller')}
                  onToggleOpc={handleToggleOpc}
                  actionBusy={actionBusy}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Pending Vehicles Tab */}
        <TabsContent value="pending-vehicles" className="mt-6">
          {pendingVehicles.length === 0 ? (
            <Card className="p-12 text-center">
              <CheckCircle className="h-16 w-16 text-green-300 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2">All Caught Up!</h3>
              <p className="text-slate-500">No pending vehicle listings.</p>
            </Card>
          ) : (
            <div>
              {pendingVehicles.map((vehicle) => (
                <VehicleListingCard
                  key={vehicle.id}
                  vehicle={vehicle}
                  onApprove={handleApproveVehicle}
                  onReject={(v) => openRejectDialog(v, 'vehicle')}
                  onView={(v) => window.open(`/vehicle-auctions/${v.id}`, '_blank')}
                  actionBusy={actionBusy}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Invoices Tab */}
        <TabsContent value="invoices" className="mt-6">
          <VehicleInvoicesTab token={token} />
        </TabsContent>

        {/* Audit Logs Tab */}
        <TabsContent value="audit-logs" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("admin.recentActions")}</CardTitle>
              <CardDescription>{t("admin.auditTrail")}</CardDescription>
            </CardHeader>
            <CardContent>
              {auditLogs.length === 0 ? (
                <p className="text-center text-slate-500 py-8">No audit logs available.</p>
              ) : (
                <div className="space-y-2">
                  {auditLogs.map((log) => (
                    <div 
                      key={log.id}
                      className="flex items-center justify-between p-3 bg-slate-50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <Badge variant="outline" className="capitalize">
                          {log.entity_type}
                        </Badge>
                        <span className="font-medium">{log.action}</span>
                        <span className="text-sm text-slate-500">
                          by {log.performed_by_role}
                        </span>
                      </div>
                      <span className="text-sm text-slate-400">
                        {formatDate(log.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Fee Configuration Tab */}
        <TabsContent value="fee-config" className="mt-6">
          <div className="grid gap-6">
            {/* Buyer Premium Configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5 text-blue-600" />
                  Buyer Premium Rates
                </CardTitle>
                <CardDescription>
                  Configure buyer premium percentages by subscription tier
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-slate-600">Standard</span>
                      <Badge variant="outline">{t("admin.freeTier")}</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        defaultValue="5"
                        className="w-24 text-center font-bold"
                        step="0.5"
                        min="0"
                        max="20"
                      />
                      <Percent className="h-4 w-4 text-slate-400" />
                    </div>
                  </div>
                  <div className="p-4 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-blue-700">Premium</span>
                      <Badge className="bg-blue-100 text-blue-700">Premium Tier</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        defaultValue="3.5"
                        className="w-24 text-center font-bold"
                        step="0.5"
                        min="0"
                        max="20"
                      />
                      <Percent className="h-4 w-4 text-blue-400" />
                    </div>
                  </div>
                  <div className="p-4 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-amber-700">VIP Elite</span>
                      <Badge className="bg-amber-100 text-amber-700">VIP Tier</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        defaultValue="3"
                        className="w-24 text-center font-bold"
                        step="0.5"
                        min="0"
                        max="20"
                      />
                      <Percent className="h-4 w-4 text-amber-400" />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Seller Commission Configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5 text-green-600" />
                  Seller Commission Rates
                </CardTitle>
                <CardDescription>
                  Configure seller commission percentages by subscription tier
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-slate-600">Standard</span>
                      <Badge variant="outline">{t("admin.freeTier")}</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        defaultValue="4"
                        className="w-24 text-center font-bold"
                        step="0.5"
                        min="0"
                        max="20"
                      />
                      <Percent className="h-4 w-4 text-slate-400" />
                    </div>
                  </div>
                  <div className="p-4 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-blue-700">Premium</span>
                      <Badge className="bg-blue-100 text-blue-700">Premium Tier</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        defaultValue="2.5"
                        className="w-24 text-center font-bold"
                        step="0.5"
                        min="0"
                        max="20"
                      />
                      <Percent className="h-4 w-4 text-blue-400" />
                    </div>
                  </div>
                  <div className="p-4 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-amber-700">VIP Elite</span>
                      <Badge className="bg-amber-100 text-amber-700">VIP Tier</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        defaultValue="2"
                        className="w-24 text-center font-bold"
                        step="0.5"
                        min="0"
                        max="20"
                      />
                      <Percent className="h-4 w-4 text-amber-400" />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Platform Fee */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Scale className="h-5 w-5 text-purple-600" />
                  Platform Fee
                </CardTitle>
                <CardDescription>
                  Base platform fee applied to all transactions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 p-4 bg-purple-50 dark:bg-purple-950/30 rounded-lg">
                  <div>
                    <p className="text-sm text-slate-500 mb-1">Platform Fee</p>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        defaultValue="2.5"
                        className="w-24 text-center font-bold"
                        step="0.5"
                        min="0"
                        max="10"
                      />
                      <Percent className="h-4 w-4 text-purple-400" />
                    </div>
                  </div>
                  <p className="text-sm text-slate-500 flex-1">
                    Applied to all transactions regardless of subscription tier
                  </p>
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end">
              <Button className="bg-blue-600 hover:bg-blue-700">
                Save Fee Configuration
              </Button>
            </div>
          </div>
        </TabsContent>
        
        {/* Auction Rules Tab */}
        <TabsContent value="auction-rules" className="mt-6">
          <div className="grid gap-6">
            {/* Anti-Sniping Configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Timer className="h-5 w-5 text-blue-600" />
                  Anti-Sniping Rules
                </CardTitle>
                <CardDescription>
                  Configure automatic auction extension for last-minute bids
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <label className="text-sm font-medium text-slate-600 block mb-2">
                      Trigger Window (minutes before end)
                    </label>
                    <Input
                      type="number"
                      defaultValue="2"
                      className="w-32"
                      min="1"
                      max="10"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Bids within this window trigger an extension
                    </p>
                  </div>
                  <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <label className="text-sm font-medium text-slate-600 block mb-2">
                      Extension Duration (minutes)
                    </label>
                    <Input
                      type="number"
                      defaultValue="2"
                      className="w-32"
                      min="1"
                      max="10"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      How long to extend the auction
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Bid Increment Rules */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings2 className="h-5 w-5 text-green-600" />
                  Bid Increment Schedule
                </CardTitle>
                <CardDescription>
                  Define minimum bid increments based on current price
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 font-medium">Price Range</th>
                        <th className="text-left py-2 font-medium">Minimum Increment</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      <tr>
                        <td className="py-2">$0 - $99</td>
                        <td className="py-2"><Input type="number" defaultValue="5" className="w-24" /></td>
                      </tr>
                      <tr>
                        <td className="py-2">$100 - $499</td>
                        <td className="py-2"><Input type="number" defaultValue="10" className="w-24" /></td>
                      </tr>
                      <tr>
                        <td className="py-2">$500 - $999</td>
                        <td className="py-2"><Input type="number" defaultValue="25" className="w-24" /></td>
                      </tr>
                      <tr>
                        <td className="py-2">$1,000 - $4,999</td>
                        <td className="py-2"><Input type="number" defaultValue="50" className="w-24" /></td>
                      </tr>
                      <tr>
                        <td className="py-2">$5,000 - $9,999</td>
                        <td className="py-2"><Input type="number" defaultValue="100" className="w-24" /></td>
                      </tr>
                      <tr>
                        <td className="py-2">$10,000 - $49,999</td>
                        <td className="py-2"><Input type="number" defaultValue="250" className="w-24" /></td>
                      </tr>
                      <tr>
                        <td className="py-2">$50,000 - $99,999</td>
                        <td className="py-2"><Input type="number" defaultValue="500" className="w-24" /></td>
                      </tr>
                      <tr>
                        <td className="py-2">$100,000+</td>
                        <td className="py-2"><Input type="number" defaultValue="1000" className="w-24" /></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Reserve Price Settings */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Award className="h-5 w-5 text-amber-600" />
                  Reserve Price Settings
                </CardTitle>
                <CardDescription>
                  Configure reserve price options for sellers
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <div>
                      <p className="font-medium">Allow Reserve Prices</p>
                      <p className="text-sm text-slate-500">Sellers can set a minimum price</p>
                    </div>
                    <Button variant="outline" className="bg-green-100 text-green-700 border-green-300">
                      Enabled
                    </Button>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <div>
                      <p className="font-medium">Show Reserve Met/Not Met</p>
                      <p className="text-sm text-slate-500">Display reserve status to bidders</p>
                    </div>
                    <Button variant="outline" className="bg-green-100 text-green-700 border-green-300">
                      Enabled
                    </Button>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <div>
                      <p className="font-medium">Allow No-Reserve Auctions</p>
                      <p className="text-sm text-slate-500">Sellers can list without a minimum</p>
                    </div>
                    <Button variant="outline" className="bg-green-100 text-green-700 border-green-300">
                      Enabled
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end">
              <Button className="bg-blue-600 hover:bg-blue-700">
                Save Auction Rules
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Rejection Dialog */}
      <Dialog open={rejectDialog.open} onOpenChange={(open) => !open && setRejectDialog({ open: false, item: null, type: null })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              Reject {rejectDialog.type === 'seller' ? 'Seller Application' : 'Vehicle Listing'}
            </DialogTitle>
            <DialogDescription>
              Please provide a reason for rejection. This will be visible to the {rejectDialog.type}.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 my-4">
            <Textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter rejection reason..."
              rows={4}
            />
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectDialog({ open: false, item: null, type: null })}>
              Cancel
            </Button>
            <Button 
              variant="destructive"
              onClick={rejectDialog.type === 'seller' ? handleRejectSeller : handleRejectVehicle}
              disabled={!rejectReason.trim() || !!actionBusy}
              data-testid="confirm-reject-btn"
            >
              {actionBusy ? 'Rejecting…' : 'Reject'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// ═════════════════════════ Vehicle Invoices Tab ═══════════════════════════
const VehicleInvoicesTab = ({ token }) => {
  const [invoices, setInvoices] = React.useState([]);
  const [stats, setStats] = React.useState({ pending: 0, overdue: 0, paid: 0 });
  const [loading, setLoading] = React.useState(true);
  const [statusFilter, setStatusFilter] = React.useState('all');
  const [typeFilter, setTypeFilter] = React.useState('all');
  const [search, setSearch] = React.useState('');
  const [confirm, setConfirm] = React.useState(null);
  const [busyId, setBusyId] = React.useState(null);

  const headers = React.useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchData = React.useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 200 };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (typeFilter !== 'all') params.invoice_type = typeFilter;
      const res = await axios.get(`${API}/vehicle-admin/invoices`, { params, headers });
      setInvoices(res.data?.invoices || []);
      setStats(res.data?.stats || { pending: 0, overdue: 0, paid: 0 });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to load invoices');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, typeFilter, headers]);

  React.useEffect(() => { fetchData(); }, [fetchData]);

  const markPaid = async (inv) => {
    setBusyId(inv.id);
    try {
      await axios.post(`${API}/admin/vehicle-invoices/${inv.id}/mark-paid`, null, {
        headers, params: { note: 'admin_manual_payment' },
      });
      toast.success(`Invoice ${inv.id} marked paid`);
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to mark paid');
    } finally { setBusyId(null); }
  };

  const sendReminder = async (inv) => {
    setBusyId(inv.id);
    try {
      await axios.post(`${API}/admin/vehicle-invoices/${inv.id}/send-reminder`, null, { headers });
      toast.success(`Reminder sent to ${inv.buyer_email || 'buyer'}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to send reminder');
    } finally { setBusyId(null); }
  };

  const filtered = invoices.filter(i =>
    !search || JSON.stringify(i).toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4" data-testid="vehicle-invoices-tab">
      <div className="grid grid-cols-3 gap-3">
        <Card><CardContent className="p-4 text-center">
          <p className="text-2xl font-bold text-amber-600">{stats.pending}</p>
          <p className="text-xs text-muted-foreground">Pending</p>
        </CardContent></Card>
        <Card><CardContent className="p-4 text-center">
          <p className="text-2xl font-bold text-red-600">{stats.overdue}</p>
          <p className="text-xs text-muted-foreground">Overdue</p>
        </CardContent></Card>
        <Card><CardContent className="p-4 text-center">
          <p className="text-2xl font-bold text-green-600">{stats.paid}</p>
          <p className="text-xs text-muted-foreground">Paid</p>
        </CardContent></Card>
      </div>

      <div className="flex gap-3 flex-wrap">
        <Input placeholder="Search invoices, buyer, vehicle..." value={search}
          onChange={(e) => setSearch(e.target.value)} className="flex-1 min-w-64"
          data-testid="invoice-search" />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 px-3 border rounded-md bg-background" data-testid="invoice-status-filter">
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="overdue">Overdue</option>
          <option value="paid">Paid</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
          className="h-10 px-3 border rounded-md bg-background" data-testid="invoice-type-filter">
          <option value="all">All Types</option>
          <option value="buyer_fee">Buyer Fee</option>
          <option value="seller_commission">Seller Commission</option>
        </select>
        <Button variant="outline" onClick={fetchData} disabled={loading} data-testid="invoice-refresh">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {loading ? (
        <div className="py-8 text-center text-muted-foreground">Loading invoices...</div>
      ) : filtered.length === 0 ? (
        <Card><CardContent className="py-12 text-center">
          <FileText className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="text-muted-foreground">No invoices match your filters.</p>
          <p className="text-xs text-muted-foreground/70">Aucune facture ne correspond.</p>
        </CardContent></Card>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="invoices-table">
            <thead><tr className="border-b bg-muted/50">
              <th className="p-3 text-left">Invoice ID</th>
              <th className="p-3 text-left">Type</th>
              <th className="p-3 text-left">Vehicle</th>
              <th className="p-3 text-left">Party</th>
              <th className="p-3 text-left">Amount</th>
              <th className="p-3 text-left">Status</th>
              <th className="p-3 text-left">Due</th>
              <th className="p-3 text-left">Actions</th>
            </tr></thead>
            <tbody>
              {filtered.slice(0, 100).map(inv => {
                const statusColor = {
                  pending: 'bg-amber-100 text-amber-800',
                  overdue: 'bg-red-100 text-red-800',
                  paid: 'bg-green-100 text-green-800',
                  cancelled: 'bg-slate-100 text-slate-600',
                }[inv.payment_status] || 'bg-slate-100';
                const isPaid = inv.payment_status === 'paid';
                return (
                  <tr key={inv.id} className="border-b hover:bg-muted/30" data-testid={`invoice-row-${inv.id}`}>
                    <td className="p-3 font-mono text-xs">{inv.id?.slice(0, 12)}…</td>
                    <td className="p-3 text-xs capitalize">{(inv.invoice_type || '').replace('_', ' ')}</td>
                    <td className="p-3 text-xs">{inv.vehicle_title || inv.vehicle_id?.slice(0, 8) || '—'}</td>
                    <td className="p-3 text-xs">
                      {inv.invoice_type === 'buyer_fee' ? inv.buyer_email : inv.seller_email}
                    </td>
                    <td className="p-3 font-semibold">${(inv.total_amount ?? 0).toFixed(2)}</td>
                    <td className="p-3"><Badge className={statusColor}>{inv.payment_status}</Badge></td>
                    <td className="p-3 text-xs">
                      {inv.due_date ? new Date(inv.due_date).toLocaleDateString() : '—'}
                    </td>
                    <td className="p-3">
                      <div className="flex gap-1 flex-wrap">
                        <Button size="sm" variant="outline" disabled={isPaid || busyId === inv.id}
                          onClick={() => setConfirm({
                            title: 'Mark this invoice as paid?',
                            description: `This is an admin override — useful if the buyer paid offline (e-transfer, cash). It will NOT charge the card. Invoice ${inv.id} ($${(inv.total_amount ?? 0).toFixed(2)}).`,
                            confirmText: 'Mark Paid',
                            successMessage: 'Invoice marked paid',
                            onConfirm: () => markPaid(inv),
                          })}
                          data-testid={`invoice-mark-paid-${inv.id}`}>
                          <DollarSign className="h-3.5 w-3.5 mr-1" /> Mark Paid
                        </Button>
                        <Button size="sm" variant="outline" disabled={isPaid || busyId === inv.id}
                          onClick={() => sendReminder(inv)}
                          data-testid={`invoice-send-reminder-${inv.id}`}>
                          <Mail className="h-3.5 w-3.5 mr-1" /> Remind
                        </Button>
                        <Button size="sm" variant="outline"
                          onClick={() => window.open(`${API}/vehicle-invoices/${inv.id}/pdf`, '_blank')}
                          data-testid={`invoice-view-pdf-${inv.id}`}>
                          <FileText className="h-3.5 w-3.5 mr-1" /> PDF
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />
    </div>
  );
};

export default VehicleAdminManager;
