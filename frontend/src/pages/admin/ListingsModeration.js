import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import {
  ShieldCheck, CheckCircle2, XCircle, RefreshCw, Package,
  ExternalLink, Loader2, Layers, AlertTriangle,
} from 'lucide-react';

const API = API_BASE;

const COMMON_REJECT_REASONS = [
  'Photos are blurry or low quality — please re-upload clearer images.',
  'Description is missing essential details (condition, dimensions, etc.).',
  'Starting price appears unreasonable for this item.',
  'Listing violates BidVex policies (prohibited item / misleading info).',
  'Title is misleading or contains spam keywords.',
];

const ListingsModeration = () => {
  const { token } = useAuth();
  const [data, setData] = useState({ total: 0, single_count: 0, multi_count: 0, listings: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState({});
  const [rejectDialog, setRejectDialog] = useState({ open: false, listing: null });
  const [rejectReason, setRejectReason] = useState('');
  const [submittingReject, setSubmittingReject] = useState(false);

  const fetchPending = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await axios.get(`${API}/admin/listings/pending`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch (err) {
      console.error(err);
      toast.error('Failed to load pending listings');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => { fetchPending(); }, [fetchPending]);

  const handleApprove = async (listing) => {
    setActionLoading(prev => ({ ...prev, [listing.id]: 'approve' }));
    try {
      await axios.post(
        `${API}/admin/listings/${listing.id}/approve`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(`"${listing.title}" approved — seller has been notified.`);
      setData(prev => ({
        ...prev,
        total: prev.total - 1,
        single_count: prev.single_count - (listing._listing_type === 'single' ? 1 : 0),
        multi_count: prev.multi_count - (listing._listing_type === 'multi' ? 1 : 0),
        listings: prev.listings.filter(l => l.id !== listing.id),
      }));
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Approval failed';
      toast.error(msg);
    } finally {
      setActionLoading(prev => {
        const { [listing.id]: _removed, ...rest } = prev;
        return rest;
      });
    }
  };

  const openRejectDialog = (listing) => {
    setRejectDialog({ open: true, listing });
    setRejectReason('');
  };

  const handleReject = async () => {
    const listing = rejectDialog.listing;
    const reason = rejectReason.trim();
    if (reason.length < 5) {
      toast.error('Please provide a reason of at least 5 characters so the seller knows what to fix.');
      return;
    }
    setSubmittingReject(true);
    try {
      await axios.post(
        `${API}/admin/listings/${listing.id}/reject`,
        { reason },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(`"${listing.title}" rejected — seller will receive an email with the reason.`);
      setData(prev => ({
        ...prev,
        total: prev.total - 1,
        single_count: prev.single_count - (listing._listing_type === 'single' ? 1 : 0),
        multi_count: prev.multi_count - (listing._listing_type === 'multi' ? 1 : 0),
        listings: prev.listings.filter(l => l.id !== listing.id),
      }));
      setRejectDialog({ open: false, listing: null });
      setRejectReason('');
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Rejection failed';
      toast.error(msg);
    } finally {
      setSubmittingReject(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="listings-moderation-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-blue-600" />
            Listings Moderation
          </h2>
          <p className="text-muted-foreground text-sm mt-1">
            Review listings from new sellers before they go live to the public.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchPending(true)}
          disabled={refreshing}
          data-testid="refresh-pending-btn"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">Total Pending</p>
                <p className="text-3xl font-bold mt-1" data-testid="pending-total-count">{data.total}</p>
              </div>
              <Package className="h-8 w-8 text-blue-600 opacity-70" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">Single-Item</p>
                <p className="text-3xl font-bold mt-1" data-testid="pending-single-count">{data.single_count}</p>
              </div>
              <Package className="h-8 w-8 text-emerald-600 opacity-70" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">Multi-Item Lots</p>
                <p className="text-3xl font-bold mt-1" data-testid="pending-multi-count">{data.multi_count}</p>
              </div>
              <Layers className="h-8 w-8 text-amber-600 opacity-70" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pending list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pending Listings ({data.total})</CardTitle>
        </CardHeader>
        <CardContent>
          {data.listings.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground" data-testid="no-pending-empty-state">
              <CheckCircle2 className="h-12 w-12 mx-auto mb-3 text-emerald-500 opacity-60" />
              <p className="font-medium">All clear — no listings awaiting moderation.</p>
              <p className="text-sm mt-1">New listings from first-time sellers will appear here when the
                <span className="font-mono mx-1 px-1.5 py-0.5 bg-muted rounded">require_approval_new_sellers</span>
                setting is enabled.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.listings.map((listing) => {
                const action = actionLoading[listing.id];
                const isApproving = action === 'approve';
                const isRejecting = action === 'reject';
                const thumb = (listing.images || [])[0];
                const priceDisplay = listing.starting_price
                  ? `$${Number(listing.starting_price).toLocaleString()} ${listing.currency || 'CAD'}`
                  : '—';

                return (
                  <div
                    key={listing.id}
                    className="flex flex-col md:flex-row gap-4 p-4 border rounded-lg bg-card hover:bg-accent/30 transition-colors"
                    data-testid={`pending-listing-${listing.id}`}
                  >
                    {/* Thumb */}
                    {thumb && (
                      <img
                        src={thumb}
                        alt={listing.title}
                        className="w-full md:w-28 h-28 object-cover rounded-md border"
                      />
                    )}
                    {/* Body */}
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <Badge
                          variant={listing._listing_type === 'multi' ? 'default' : 'secondary'}
                          className="text-[10px]"
                        >
                          {listing._listing_type === 'multi'
                            ? `Multi-Lot (${(listing.lots || []).length} items)`
                            : 'Single-Item'}
                        </Badge>
                        {listing.category && (
                          <Badge variant="outline" className="text-[10px]">
                            {listing.category}
                          </Badge>
                        )}
                      </div>
                      <h3 className="font-semibold text-base truncate" title={listing.title}>
                        {listing.title || 'Untitled'}
                      </h3>
                      <p className="text-sm text-muted-foreground line-clamp-2 mt-0.5">
                        {listing.description || '(no description)'}
                      </p>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                        <span><strong>Seller:</strong> {listing._seller_name || '—'} &lt;{listing._seller_email || '—'}&gt;</span>
                        <span><strong>Start price:</strong> {priceDisplay}</span>
                        {listing.location && <span><strong>Location:</strong> {listing.location}</span>}
                        <span><strong>Created:</strong> {listing.created_at ? new Date(listing.created_at).toLocaleString() : '—'}</span>
                      </div>
                    </div>
                    {/* Actions */}
                    <div className="flex md:flex-col gap-2 md:w-40 shrink-0">
                      <Button
                        size="sm"
                        className="bg-emerald-600 hover:bg-emerald-700 text-white flex-1"
                        onClick={() => handleApprove(listing)}
                        disabled={isApproving || isRejecting}
                        data-testid={`approve-btn-${listing.id}`}
                      >
                        {isApproving
                          ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                          : <CheckCircle2 className="h-4 w-4 mr-1" />}
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        className="flex-1"
                        onClick={() => openRejectDialog(listing)}
                        disabled={isApproving || isRejecting}
                        data-testid={`reject-btn-${listing.id}`}
                      >
                        <XCircle className="h-4 w-4 mr-1" />
                        Reject
                      </Button>
                      {listing._listing_type === 'single' && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="flex-1"
                          onClick={() => window.open(`/listing/${listing.id}`, '_blank')}
                          data-testid={`preview-btn-${listing.id}`}
                        >
                          <ExternalLink className="h-4 w-4 mr-1" />
                          Preview
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Reject Dialog */}
      <Dialog open={rejectDialog.open} onOpenChange={(open) => !submittingReject && setRejectDialog({ open, listing: rejectDialog.listing })}>
        <DialogContent className="max-w-lg" data-testid="reject-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              Reject this listing?
            </DialogTitle>
            <DialogDescription>
              The seller will receive an email containing the exact reason you provide below, so make it
              clear and actionable.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm font-medium">
              Listing: <span className="font-normal">{rejectDialog.listing?.title}</span>
            </p>
            {/* Quick-pick reasons */}
            <div>
              <p className="text-xs text-muted-foreground mb-1.5">Quick reasons:</p>
              <div className="flex flex-wrap gap-1.5">
                {COMMON_REJECT_REASONS.map((reason, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setRejectReason(reason)}
                    className="text-[11px] px-2 py-1 border border-border rounded-md hover:bg-accent text-left"
                    data-testid={`quick-reason-${idx}`}
                  >
                    {reason.length > 50 ? `${reason.slice(0, 50)}…` : reason}
                  </button>
                ))}
              </div>
            </div>
            <Textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Explain to the seller exactly what they need to fix or change…"
              rows={4}
              className="resize-none"
              data-testid="reject-reason-textarea"
            />
            <p className="text-[11px] text-muted-foreground">
              {rejectReason.length} characters · minimum 5
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRejectDialog({ open: false, listing: null })}
              disabled={submittingReject}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={submittingReject || rejectReason.trim().length < 5}
              data-testid="confirm-reject-btn"
            >
              {submittingReject
                ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                : <XCircle className="h-4 w-4 mr-1" />}
              Reject &amp; Email Seller
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ListingsModeration;
