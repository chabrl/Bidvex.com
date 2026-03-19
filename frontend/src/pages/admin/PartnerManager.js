import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import {
  Building2, CheckCircle, Clock, XCircle, FileText, ExternalLink,
  Shield, DollarSign, Loader2, Search, Eye
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PartnerManager = () => {
  const { token } = useAuth();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Review dialog
  const [reviewDialog, setReviewDialog] = useState(false);
  const [selectedApp, setSelectedApp] = useState(null);
  const [customRate, setCustomRate] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => { fetchApplications(); }, [filter]);

  const fetchApplications = async () => {
    setLoading(true);
    try {
      const params = filter !== 'all' ? `?status=${filter}` : '';
      const res = await axios.get(`${API}/admin/partners${params}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setApplications(res.data.applications || []);
    } catch (err) {
      toast.error('Failed to load partner applications.');
    } finally { setLoading(false); }
  };

  const handleVerify = async () => {
    if (!selectedApp) return;
    setActionLoading(true);
    try {
      const data = {};
      if (customRate) data.custom_premium_rate = parseFloat(customRate) / 100;
      const res = await axios.post(`${API}/admin/partners/${selectedApp.id}/verify`, data, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const checkoutUrl = res.data?.checkout_url;
      if (checkoutUrl) {
        toast.success(`Partner verified! Payment link sent to ${selectedApp.email}.`, { duration: 6000 });
      } else {
        toast.success(`Partner ${selectedApp.email} verified! (Stripe checkout could not be created — check Stripe config)`);
      }
      setReviewDialog(false);
      fetchApplications();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Verification failed.');
    } finally { setActionLoading(false); }
  };

  const handleReject = async () => {
    if (!selectedApp) return;
    setActionLoading(true);
    try {
      await axios.post(`${API}/admin/partners/${selectedApp.id}/reject`, {
        reason: rejectionReason || 'Application does not meet requirements.'
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success('Application rejected.');
      setReviewDialog(false);
      fetchApplications();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Rejection failed.');
    } finally { setActionLoading(false); }
  };

  const openReview = (app) => {
    setSelectedApp(app);
    setCustomRate(app.custom_premium_rate ? (app.custom_premium_rate * 100).toString() : '');
    setRejectionReason('');
    setReviewDialog(true);
  };

  const statusColors = {
    pending: 'bg-amber-100 text-amber-800 border-amber-200',
    verified: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    rejected: 'bg-red-100 text-red-800 border-red-200',
  };

  const feeStatusBadge = (app) => {
    if (app.partner_verification_status !== 'verified') return null;
    if (app.platform_fee_paid) {
      return <Badge className="text-[10px] px-1.5 py-0 bg-green-100 text-green-700 border-green-200">Fee Paid</Badge>;
    }
    return <Badge className="text-[10px] px-1.5 py-0 bg-orange-100 text-orange-700 border-orange-200">Fee Pending</Badge>;
  };

  const statusIcons = { pending: Clock, verified: CheckCircle, rejected: XCircle };

  const filtered = applications.filter(a =>
    (a.partner_company_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (a.email || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (a.name || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const stats = {
    pending: applications.filter(a => a.partner_verification_status === 'pending').length,
    verified: applications.filter(a => a.partner_verification_status === 'verified').length,
    rejected: applications.filter(a => a.partner_verification_status === 'rejected').length,
  };

  return (
    <div className="space-y-4" data-testid="partner-manager">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="bg-amber-50 border-amber-200">
          <CardContent className="p-3 text-center">
            <div className="text-2xl font-bold text-amber-700" data-testid="partner-pending-count">{stats.pending}</div>
            <div className="text-xs text-amber-600">Pending</div>
          </CardContent>
        </Card>
        <Card className="bg-emerald-50 border-emerald-200">
          <CardContent className="p-3 text-center">
            <div className="text-2xl font-bold text-emerald-700" data-testid="partner-verified-count">{stats.verified}</div>
            <div className="text-xs text-emerald-600">Verified</div>
          </CardContent>
        </Card>
        <Card className="bg-red-50 border-red-200">
          <CardContent className="p-3 text-center">
            <div className="text-2xl font-bold text-red-700" data-testid="partner-rejected-count">{stats.rejected}</div>
            <div className="text-xs text-red-600">Rejected</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            placeholder="Search by company, email, or name..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="pl-9 h-9 text-sm"
            data-testid="partner-search"
          />
        </div>
        {['all', 'pending', 'verified', 'rejected'].map(f => (
          <Button
            key={f}
            variant={filter === f ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(f)}
            className="text-xs capitalize"
            data-testid={`partner-filter-${f}`}
          >
            {f}
          </Button>
        ))}
      </div>

      {/* Applications List */}
      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-8 text-slate-500">
          <Building2 className="w-10 h-10 mx-auto mb-2 opacity-40" />
          <p className="text-sm">No partner applications found.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(app => {
            const StatusIcon = statusIcons[app.partner_verification_status] || Clock;
            return (
              <Card key={app.id} className="hover:shadow-md transition-shadow" data-testid={`partner-app-${app.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Building2 className="w-4 h-4 text-slate-500 flex-shrink-0" />
                        <span className="font-semibold text-sm truncate">{app.partner_company_name || 'No company name'}</span>
                        <Badge className={`text-[10px] px-1.5 py-0 ${statusColors[app.partner_verification_status] || 'bg-slate-100 text-slate-600'}`}>
                          <StatusIcon className="w-3 h-3 mr-1 inline" />
                          {app.partner_verification_status}
                        </Badge>
                        {feeStatusBadge(app)}
                      </div>
                      <div className="text-xs text-slate-500 mt-1 space-x-3">
                        <span>{app.name} ({app.email})</span>
                        {app.partner_neq && <span>NEQ: {app.partner_neq}</span>}
                        {app.custom_premium_rate != null && (
                          <span className="text-blue-600">BP: {(app.custom_premium_rate * 100).toFixed(1)}%</span>
                        )}
                      </div>
                      {app.partner_applied_at && (
                        <div className="text-[10px] text-slate-400 mt-1">
                          Applied: {new Date(app.partner_applied_at).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openReview(app)}
                      className="flex-shrink-0"
                      data-testid={`partner-review-${app.id}`}
                    >
                      <Eye className="w-3.5 h-3.5 mr-1" /> Review
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Review Dialog */}
      <Dialog open={reviewDialog} onOpenChange={setReviewDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Building2 className="w-5 h-5" /> Partner Application Review
            </DialogTitle>
            <DialogDescription>
              {selectedApp?.partner_company_name} — {selectedApp?.email}
            </DialogDescription>
          </DialogHeader>

          {selectedApp && (
            <div className="space-y-4">
              {/* Details */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <Label className="text-xs text-slate-500">Company</Label>
                  <p className="font-medium">{selectedApp.partner_company_name || '-'}</p>
                </div>
                <div>
                  <Label className="text-xs text-slate-500">NEQ Number</Label>
                  <p className="font-medium">{selectedApp.partner_neq || '-'}</p>
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Account Type</Label>
                  <p className="font-medium capitalize">{selectedApp.account_type}</p>
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Status</Label>
                  <Badge className={`text-xs ${statusColors[selectedApp.partner_verification_status]}`}>
                    {selectedApp.partner_verification_status}
                  </Badge>
                </div>
              </div>

              {/* Documents */}
              <div className="space-y-2">
                <Label className="text-xs text-slate-500">Submitted Documents</Label>
                {selectedApp.partner_neq_document && (
                  <a href={selectedApp.partner_neq_document} target="_blank" rel="noreferrer"
                    className="flex items-center gap-2 text-sm text-blue-600 hover:underline">
                    <FileText className="w-4 h-4" /> NEQ Proof <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                {(selectedApp.partner_certifications || []).map((url, i) => (
                  <a key={i} href={url} target="_blank" rel="noreferrer"
                    className="flex items-center gap-2 text-sm text-blue-600 hover:underline">
                    <Shield className="w-4 h-4" /> Certification {i + 1} <ExternalLink className="w-3 h-3" />
                  </a>
                ))}
                {!selectedApp.partner_neq_document && (!selectedApp.partner_certifications || selectedApp.partner_certifications.length === 0) && (
                  <p className="text-xs text-slate-400 italic">No documents uploaded.</p>
                )}
              </div>

              {/* Fee Status for verified partners */}
              {selectedApp.partner_verification_status === 'verified' && (
                <div className={`rounded-md p-3 text-sm ${selectedApp.platform_fee_paid ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-orange-50 border border-orange-200 text-orange-700'}`}>
                  {selectedApp.platform_fee_paid ? (
                    <span className="flex items-center gap-1.5"><CheckCircle className="w-4 h-4" /> Annual fee paid — account fully active</span>
                  ) : (
                    <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" /> Annual fee pending — listing capabilities locked until payment</span>
                  )}
                </div>
              )}

              {/* Custom Premium Rate */}
              {selectedApp.partner_verification_status === 'pending' && (
                <>
                  <div className="space-y-1.5">
                    <Label className="text-xs text-slate-500">Set Custom Buyer Premium Rate (optional)</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        step="0.1"
                        min="0"
                        max="100"
                        value={customRate}
                        onChange={e => setCustomRate(e.target.value)}
                        placeholder="e.g., 18"
                        className="w-24 h-8 text-sm"
                        data-testid="partner-custom-rate-input"
                      />
                      <span className="text-sm text-slate-500">%</span>
                    </div>
                    <p className="text-[10px] text-slate-400">Leave empty if partner will set per-listing rates later.</p>
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs text-slate-500">Rejection Reason (if rejecting)</Label>
                    <Input
                      value={rejectionReason}
                      onChange={e => setRejectionReason(e.target.value)}
                      placeholder="Reason for rejection..."
                      className="h-8 text-sm"
                      data-testid="partner-rejection-reason"
                    />
                  </div>
                </>
              )}
            </div>
          )}

          <DialogFooter className="gap-2">
            {selectedApp?.partner_verification_status === 'pending' && (
              <>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleReject}
                  disabled={actionLoading}
                  data-testid="partner-reject-btn"
                >
                  {actionLoading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <XCircle className="w-3 h-3 mr-1" />}
                  Reject
                </Button>
                <Button
                  size="sm"
                  onClick={handleVerify}
                  disabled={actionLoading}
                  className="bg-emerald-600 hover:bg-emerald-700"
                  data-testid="partner-verify-btn"
                >
                  {actionLoading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <CheckCircle className="w-3 h-3 mr-1" />}
                  Verify Partner
                </Button>
              </>
            )}
            <Button variant="outline" size="sm" onClick={() => setReviewDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PartnerManager;
