import API_BASE from '../../config';
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
  Shield, ShieldCheck, DollarSign, Loader2, Search, Eye, AlertTriangle, Mail, Banknote
} from 'lucide-react';
import ManualSettleSubscriptionModal from '../../components/ManualSettleSubscriptionModal';

const API = API_BASE;

// iter211 — robust document opener that handles the structured 404 (file
// missing on disk) and renders a CTA modal instead of dumping JSON in a tab.
const useDocumentOpener = (token, onMissing) => {
  return async (rawPath) => {
    try {
      const abs = rawPath.startsWith('http') ? rawPath : `${process.env.REACT_APP_BACKEND_URL}${rawPath}`;
      const res = await fetch(abs, { headers: { Authorization: `Bearer ${token || ''}` } });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank', 'noopener');
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
        return;
      }
      // Structured 404 from iter211?
      if (res.status === 404) {
        const data = await res.json().catch(() => ({}));
        const detail = data?.detail || {};
        if (detail.error_code === 'file_missing_on_disk') {
          onMissing(detail);
          return;
        }
      }
      toast.error(`Failed to open document (HTTP ${res.status})`);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[partner-doc-open]', err);
      toast.error('Could not load document — network error.');
    }
  };
};

const PartnerManager = () => {
  const { token } = useAuth();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Review dialog
  const [reviewDialog, setReviewDialog] = useState(false);
  const [selectedApp, setSelectedApp] = useState(null);

  // iter211 — Missing-document modal (raised by useDocumentOpener)
  const [missingDocModal, setMissingDocModal] = useState(null);
  const [requestingResubmit, setRequestingResubmit] = useState(false);

  // iter211 Task 1 — Manual subscription settle modal
  const [manualSettleOpen, setManualSettleOpen] = useState(false);

  const openDocument = useDocumentOpener(token, setMissingDocModal);

  const handleRequestResubmission = async () => {
    if (!missingDocModal?.owner_user_id) {
      toast.error('Cannot identify the partner for this document.');
      return;
    }
    setRequestingResubmit(true);
    try {
      const r = await axios.post(`${API}/admin/partners/${missingDocModal.owner_user_id}/request-resubmission`);
      toast.success(`Resubmission email sent to ${r.data?.email || 'partner'}.`);
      setMissingDocModal(null);
      // Refresh the list so the new "rejected" status appears
      window.location.reload();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[request-resubmission]', err);
      toast.error('Failed to send resubmission request.');
    } finally {
      setRequestingResubmit(false);
    }
  };
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
                        {app.partner_neq && <span>Business Reg.: {app.partner_neq}</span>}
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
                  <Label className="text-xs text-slate-500">Business Registration #</Label>
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

              {/* Documents — iter211: structured-404 handling via openDocument() */}
              <div className="space-y-2">
                <Label className="text-xs text-slate-500">Submitted Documents</Label>
                {selectedApp.partner_neq_document && (
                  <button
                    type="button"
                    onClick={() => openDocument(selectedApp.partner_neq_document)}
                    data-testid="partner-doc-neq-link"
                    className="flex items-center gap-2 text-sm text-blue-600 hover:underline bg-transparent border-0 p-0 cursor-pointer"
                  >
                    <FileText className="w-4 h-4" /> Business Registration Document <ExternalLink className="w-3 h-3" />
                  </button>
                )}
                {(selectedApp.partner_certifications || []).map((raw, i) => (
                  <button
                    type="button"
                    key={i}
                    onClick={() => openDocument(raw)}
                    data-testid={`partner-doc-cert-link-${i}`}
                    className="flex items-center gap-2 text-sm text-blue-600 hover:underline bg-transparent border-0 p-0 cursor-pointer"
                  >
                    <Shield className="w-4 h-4" /> Certification {i + 1} <ExternalLink className="w-3 h-3" />
                  </button>
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

              {/* Verified Auction Firm Toggle */}
              {selectedApp.partner_verification_status === 'verified' && (
                <div className="flex items-center justify-between rounded-md p-3 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    <div>
                      <p className="text-sm font-medium">Verified Auction Firm</p>
                      <p className="text-[10px] text-slate-500">Display trust badge on listings & profile</p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant={selectedApp.is_verified_firm ? 'default' : 'outline'}
                    className={selectedApp.is_verified_firm ? 'bg-emerald-600 hover:bg-emerald-700' : ''}
                    data-testid="toggle-verified-firm-btn"
                    onClick={async () => {
                      try {
                        const newVal = !selectedApp.is_verified_firm;
                        await axios.post(`${API}/admin/partners/${selectedApp.id}/verified-firm`,
                          { is_verified_firm: newVal },
                          { headers: { Authorization: `Bearer ${token}` } }
                        );
                        setSelectedApp(prev => ({ ...prev, is_verified_firm: newVal }));
                        setApplications(prev => prev.map(a => a.id === selectedApp.id ? { ...a, is_verified_firm: newVal } : a));
                        toast.success(newVal ? 'Verified Firm badge granted' : 'Verified Firm badge removed');
                      } catch (err) {
                        toast.error('Failed to update verified status');
                      }
                    }}
                  >
                    {selectedApp.is_verified_firm ? 'Badge Active' : 'Grant Badge'}
                  </Button>
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
            {selectedApp?.partner_verification_status === 'verified' && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setManualSettleOpen(true)}
                data-testid="partner-manual-settle-btn"
                className="border-emerald-300 text-emerald-700 hover:bg-emerald-50"
              >
                <Banknote className="w-3 h-3 mr-1" />
                Manual Settle
              </Button>
            )}
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

      {/* iter211 — Missing document modal (raised when the serve endpoint
          returns the structured `file_missing_on_disk` 404). */}
      <Dialog open={!!missingDocModal} onOpenChange={(o) => !o && setMissingDocModal(null)}>
        <DialogContent className="max-w-lg" data-testid="missing-doc-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-rose-700">
              <AlertTriangle className="w-5 h-5" />
              Document not available
            </DialogTitle>
            <DialogDescription>
              The document file is no longer on the server. This usually happens after a system redeployment wiped the temporary file storage.
            </DialogDescription>
          </DialogHeader>
          {missingDocModal && (
            <div className="space-y-3 text-sm">
              <p className="text-slate-700">{missingDocModal.message_en}</p>
              <div className="rounded-md bg-slate-50 border border-slate-200 p-3 text-xs space-y-1">
                <div><span className="text-slate-500">Filename:</span> <code className="text-slate-700">{missingDocModal.filename}</code></div>
                {missingDocModal.owner_email && (
                  <div><span className="text-slate-500">Partner:</span> <strong>{missingDocModal.owner_email}</strong></div>
                )}
                {missingDocModal.owner_status && (
                  <div><span className="text-slate-500">Current status:</span> <Badge className="text-[10px]">{missingDocModal.owner_status}</Badge></div>
                )}
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setMissingDocModal(null)}>Cancel</Button>
            <Button
              size="sm"
              onClick={handleRequestResubmission}
              disabled={requestingResubmit || !missingDocModal?.owner_user_id}
              data-testid="request-resubmission-btn"
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {requestingResubmit ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Mail className="w-4 h-4 mr-2" />}
              Email partner to resubmit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* iter211 Task 1 — Manual subscription settle */}
      <ManualSettleSubscriptionModal
        open={manualSettleOpen}
        onOpenChange={setManualSettleOpen}
        targetUserId={selectedApp?.id}
        targetUserEmail={selectedApp?.email}
        accountKind="partner"
        defaultAmount={100}
        onSettled={() => { setManualSettleOpen(false); fetchApplications?.(); }}
      />
    </div>
  );
};

export default PartnerManager;
