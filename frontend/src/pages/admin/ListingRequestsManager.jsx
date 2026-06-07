/**
 * iter288 — Admin: Listing Change-Request Inbox.
 *
 * Triage queue for user-submitted edit / delete requests across every
 * directory (vehicle, storage, lot, marketplace).
 *
 *  - Feeds from `GET /api/admin/listing-requests?status=pending`
 *  - "Approve" → `POST /api/admin/listing-requests/{id}/approve`
 *    Executes the underlying action (soft-cancel for delete, merge
 *    for edit) and stamps `status='approved'`.
 *  - "Reject"  → `POST /api/admin/listing-requests/{id}/reject`
 *
 *  Filter chips: pending / approved / rejected / all
 *  Pending count surfaces as a badge on the parent AdminDashboard tab.
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import API_BASE from '../../config';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { CheckCircle2, XCircle, RefreshCw, Inbox, Loader2 } from 'lucide-react';

const STATUSES = ['pending', 'approved', 'rejected', 'all'];

export default function ListingRequestsManager() {
  const [statusFilter, setStatusFilter] = useState('pending');
  const [requests, setRequests] = useState([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState(null);

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    try {
      const url = statusFilter === 'all'
        ? `${API_BASE}/admin/listing-requests?status=`  // status= → no filter
        : `${API_BASE}/admin/listing-requests?status=${statusFilter}`;
      const { data } = await axios.get(url, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      setRequests(data?.requests || []);
      setPendingCount(data?.pending_count || 0);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load listing requests');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { fetchRequests(); }, [fetchRequests]);

  const handleAction = async (req, action) => {
    setActingId(req.id);
    try {
      await axios.post(
        `${API_BASE}/admin/listing-requests/${req.id}/${action}`,
        {},
        { headers: { Authorization: `Bearer ${_token()}` } },
      );
      toast.success(action === 'approve' ? 'Request approved' : 'Request rejected');
      fetchRequests();
    } catch (err) {
      toast.error(err?.response?.data?.detail || `Failed to ${action} request`);
    } finally {
      setActingId(null);
    }
  };

  return (
    <Card data-testid="admin-listing-requests-panel">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Inbox className="h-5 w-5" />
          Pending Modification Requests
          {pendingCount > 0 && (
            <Badge variant="destructive" data-testid="admin-listing-requests-pending-badge">
              {pendingCount}
            </Badge>
          )}
        </CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchRequests}
          disabled={loading}
          data-testid="admin-listing-requests-refresh"
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Filter chips */}
        <div className="flex flex-wrap gap-2">
          {STATUSES.map((s) => (
            <Button
              key={s}
              variant={statusFilter === s ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter(s)}
              data-testid={`admin-listing-requests-filter-${s}`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </Button>
          ))}
        </div>

        {loading && requests.length === 0 ? (
          <div className="py-10 text-center text-sm text-slate-500">
            <Loader2 className="inline h-4 w-4 mr-1 animate-spin" />
            Loading…
          </div>
        ) : requests.length === 0 ? (
          <div className="py-10 text-center text-sm text-slate-500">
            No {statusFilter !== 'all' ? statusFilter : ''} requests in the queue.
          </div>
        ) : (
          <div className="space-y-2">
            {requests.map((req) => (
              <div
                key={req.id}
                data-testid={`admin-listing-request-row-${req.id}`}
                className="flex flex-col md:flex-row md:items-center justify-between gap-3 rounded-lg border border-slate-200 dark:border-slate-700 p-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <Badge variant={req.request_type === 'delete' ? 'destructive' : 'secondary'}>
                      {req.request_type.toUpperCase()}
                    </Badge>
                    <Badge variant="outline">{req.listing_type}</Badge>
                    <Badge variant={
                      req.status === 'pending'  ? 'default'     :
                      req.status === 'approved' ? 'secondary'   : 'outline'
                    }>
                      {req.status}
                    </Badge>
                    <code className="text-xs text-slate-500 truncate">{req.listing_id}</code>
                  </div>
                  <p className="text-sm text-slate-700 break-words">
                    <span className="font-semibold">Reason: </span>{req.reason}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Submitted by {req.user_email || req.user_id} ·{' '}
                    {new Date(req.created_at).toLocaleString()}
                  </p>
                  {req.resolved_at && (
                    <p className="text-xs text-slate-500">
                      Resolved by {req.resolved_by || '—'} on{' '}
                      {new Date(req.resolved_at).toLocaleString()}
                    </p>
                  )}
                </div>
                {req.status === 'pending' && (
                  <div className="flex gap-2 flex-shrink-0">
                    <Button
                      size="sm"
                      onClick={() => handleAction(req, 'approve')}
                      disabled={actingId === req.id}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      data-testid={`admin-listing-request-approve-${req.id}`}
                    >
                      <CheckCircle2 className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleAction(req, 'reject')}
                      disabled={actingId === req.id}
                      className="border-rose-200 text-rose-700 hover:bg-rose-50"
                      data-testid={`admin-listing-request-reject-${req.id}`}
                    >
                      <XCircle className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
