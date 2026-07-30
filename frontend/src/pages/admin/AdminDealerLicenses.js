import { extractErrorMessage } from '../../utils/errorHandler';
/**
 * AdminDealerLicenses — iter195 (P0)
 * ===================================
 * Browser UI for admins to review pending dealer-license submissions.
 * Mounts at: AdminDashboard → Vehicles → Dealer Licenses
 *
 * Backend endpoints:
 *   GET  /api/admin/dealer-licenses?status=pending|approved|rejected|expired
 *   POST /api/admin/dealer-licenses/{id}/decision  { decision, rejection_reason? }
 */
import API_BASE from '../../config';
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription,
} from '../../components/ui/dialog';
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from '../../components/ui/tabs';
import {
  ShieldCheck, CheckCircle2, XCircle, FileText, Loader2, RefreshCw, ExternalLink, Clock, AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';

const API = API_BASE;

const STATUS_LABEL = {
  pending: { en: 'Pending', cls: 'bg-amber-100 text-amber-800 border-amber-300' },
  approved: { en: 'Approved', cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  rejected: { en: 'Rejected', cls: 'bg-red-100 text-red-800 border-red-300' },
  expired: { en: 'Expired', cls: 'bg-slate-200 text-slate-700 border-slate-300' },
};

function fmtDate(d) {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: '2-digit' });
  } catch (_) { return String(d); }
}

const RejectDialog = ({ open, onClose, onConfirm, processing }) => {
  const [reason, setReason] = useState('');
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) { setReason(''); onClose(); } }}>
      <DialogContent data-testid="admin-license-reject-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-600" />
            Reject Dealer License
          </DialogTitle>
          <DialogDescription>
            Provide an optional reason. The buyer will receive an email with this reason and a link to resubmit.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="reject-reason">Rejection Reason (optional)</Label>
          <Textarea
            id="reject-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Document is illegible, license has expired, jurisdiction does not match…"
            rows={3}
            data-testid="admin-license-reject-reason-input"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => { setReason(''); onClose(); }} disabled={processing} data-testid="admin-license-reject-cancel-btn">
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => onConfirm(reason)}
            disabled={processing}
            data-testid="admin-license-reject-confirm-btn"
          >
            {processing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <XCircle className="h-4 w-4 mr-2" />}
            Confirm Reject
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};


const AdminDealerLicenses = () => {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState('pending');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [rejectTarget, setRejectTarget] = useState(null);
  const [processingId, setProcessingId] = useState(null);

  const fetchList = useCallback(async (status) => {
    setLoading(true);
    try {
      const url = status === 'all'
        ? `${API}/admin/dealer-licenses`
        : `${API}/admin/dealer-licenses?status=${status}`;
      const res = await axios.get(url, { headers: { Authorization: `Bearer ${token}` } });
      setItems(res.data?.items || []);
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Failed to load licenses');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchList(activeTab);
  }, [activeTab, fetchList]);

  const handleApprove = async (id) => {
    setProcessingId(id);
    try {
      await axios.post(
        `${API}/admin/dealer-licenses/${id}/decision`,
        { decision: 'approve' },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('License approved — buyer notified by email');
      fetchList(activeTab);
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Approve failed');
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (reason) => {
    if (!rejectTarget) return;
    setProcessingId(rejectTarget.id);
    try {
      await axios.post(
        `${API}/admin/dealer-licenses/${rejectTarget.id}/decision`,
        { decision: 'reject', rejection_reason: reason || null },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('License rejected — buyer notified by email');
      setRejectTarget(null);
      fetchList(activeTab);
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Reject failed');
    } finally {
      setProcessingId(null);
    }
  };

  const filtered = items.filter((it) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (it.license_number || '').toLowerCase().includes(q) ||
      (it.jurisdiction || '').toLowerCase().includes(q) ||
      (it.user_id || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6" data-testid="admin-dealer-licenses-page">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-blue-600" />
              Dealer License Management
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchList(activeTab)}
              disabled={loading}
              data-testid="admin-license-refresh-btn"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Review pending license submissions and approve / reject access for licensed-only vehicle auctions.
            Buyers receive a transactional email on every status change.
          </p>
        </CardHeader>

        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid grid-cols-5 w-full max-w-2xl mb-4">
              <TabsTrigger value="pending" data-testid="admin-license-tab-pending">
                <Clock className="h-3.5 w-3.5 mr-1" /> Pending
              </TabsTrigger>
              <TabsTrigger value="approved" data-testid="admin-license-tab-approved">
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Approved
              </TabsTrigger>
              <TabsTrigger value="rejected" data-testid="admin-license-tab-rejected">
                <XCircle className="h-3.5 w-3.5 mr-1" /> Rejected
              </TabsTrigger>
              <TabsTrigger value="expired" data-testid="admin-license-tab-expired">
                <AlertTriangle className="h-3.5 w-3.5 mr-1" /> Expired
              </TabsTrigger>
              <TabsTrigger value="all" data-testid="admin-license-tab-all">
                All
              </TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab}>
              <div className="mb-3 flex items-center gap-3">
                <Input
                  placeholder="Search by license #, jurisdiction, or user id…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="max-w-sm"
                  data-testid="admin-license-search-input"
                />
                <span className="text-sm text-muted-foreground">
                  Showing <strong>{filtered.length}</strong> of {items.length}
                </span>
              </div>

              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : filtered.length === 0 ? (
                <p className="text-center text-muted-foreground py-10">No licenses in this tab.</p>
              ) : (
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full text-sm" data-testid="admin-license-table">
                    <thead className="bg-slate-50 dark:bg-slate-800/40">
                      <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                        <th className="px-3 py-2">License #</th>
                        <th className="px-3 py-2">Jurisdiction</th>
                        <th className="px-3 py-2">Expiry</th>
                        <th className="px-3 py-2">Submitted</th>
                        <th className="px-3 py-2">User ID</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((it) => {
                        const meta = STATUS_LABEL[it.status] || STATUS_LABEL.pending;
                        const isProcessing = processingId === it.id;
                        return (
                          <tr
                            key={it.id}
                            className="border-t hover:bg-slate-50 dark:hover:bg-slate-800/40"
                            data-testid={`admin-license-row-${it.id}`}
                          >
                            <td className="px-3 py-2 font-mono text-xs">{it.license_number}</td>
                            <td className="px-3 py-2 uppercase">{it.jurisdiction}</td>
                            <td className="px-3 py-2">{fmtDate(it.expiry_date)}</td>
                            <td className="px-3 py-2 text-xs text-muted-foreground">{fmtDate(it.submitted_at)}</td>
                            <td className="px-3 py-2 font-mono text-[10px] text-slate-500" title={it.user_id}>
                              {it.user_id?.slice(0, 8)}…
                            </td>
                            <td className="px-3 py-2">
                              <Badge className={meta.cls}>{meta.en}</Badge>
                              {it.rejection_reason && (
                                <p className="text-[10px] text-red-600 mt-1">Reason: {it.rejection_reason}</p>
                              )}
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex flex-wrap gap-1.5">
                                {it.document_url && (() => {
                                  // iter208 — relative path + absolute fallback + ?token= for browser nav
                                  // Prefix with bare REACT_APP_BACKEND_URL (NOT API_BASE which adds /api)
                                  const raw = it.document_url;
                                  const abs = raw.startsWith('http') ? raw : `${process.env.REACT_APP_BACKEND_URL}${raw}`;
                                  const href = `${abs}${abs.includes('?') ? '&' : '?'}token=${encodeURIComponent(token || '')}`;
                                  return (
                                    <a
                                      href={href}
                                      target="_blank"
                                      rel="noreferrer"
                                      data-testid={`admin-license-view-doc-${it.id}`}
                                    >
                                      <Button size="sm" variant="outline">
                                        <FileText className="h-3.5 w-3.5 mr-1" /> View
                                        <ExternalLink className="h-3 w-3 ml-1 opacity-60" />
                                      </Button>
                                    </a>
                                  );
                                })()}
                                {it.status === 'pending' && (
                                  <>
                                    <Button
                                      size="sm"
                                      onClick={() => handleApprove(it.id)}
                                      disabled={isProcessing}
                                      className="bg-emerald-600 hover:bg-emerald-700 text-white"
                                      data-testid={`admin-license-approve-btn-${it.id}`}
                                    >
                                      {isProcessing
                                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        : <><CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Approve</>}
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="destructive"
                                      onClick={() => setRejectTarget(it)}
                                      disabled={isProcessing}
                                      data-testid={`admin-license-reject-btn-${it.id}`}
                                    >
                                      <XCircle className="h-3.5 w-3.5 mr-1" /> Reject
                                    </Button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <RejectDialog
        open={!!rejectTarget}
        onClose={() => setRejectTarget(null)}
        onConfirm={handleReject}
        processing={processingId === rejectTarget?.id}
      />
    </div>
  );
};

export default AdminDealerLicenses;
