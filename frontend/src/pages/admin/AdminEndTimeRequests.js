/**
 * iter483 — Admin End-Time Change Requests Queue
 * ==============================================
 *
 * Lists pending / approved / denied requests and lets admins
 * approve or deny each with an optional note.
 *
 * Backend contract:
 *   GET   /api/admin/end-time-requests?status=pending
 *   POST  /api/admin/end-time-requests/{id}/approve  {admin_note?}
 *   POST  /api/admin/end-time-requests/{id}/deny     {admin_note?}
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import { Loader2, Check, X, Clock, RefreshCw } from 'lucide-react';
import API_BASE from '../../config';

const API = API_BASE;

const STATUS_TABS = ['pending', 'approved', 'denied'];

export default function AdminEndTimeRequests() {
  const { token } = useAuth();
  const headers = { Authorization: `Bearer ${token}` };

  const [status, setStatus] = useState('pending');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [noteFor, setNoteFor] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(
        `${API}/admin/end-time-requests?status=${status}`,
        { headers });
      setRows(r.data?.rows || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load requests');
    } finally {
      setLoading(false);
    }
  }, [status, token]);

  useEffect(() => { load(); }, [load]);

  const act = async (id, action) => {
    setBusyId(id);
    try {
      await axios.post(
        `${API}/admin/end-time-requests/${id}/${action}`,
        { admin_note: noteFor[id] || '' },
        { headers });
      toast.success(action === 'approve' ? 'Request approved' : 'Request denied');
      setNoteFor({ ...noteFor, [id]: '' });
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Action failed');
    } finally {
      setBusyId(null);
    }
  };

  const badge = (st) => ({
    pending:  <Badge className="bg-amber-100 text-amber-800 border-amber-300"><Clock className="h-3 w-3 mr-1 inline" />Pending</Badge>,
    approved: <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300"><Check className="h-3 w-3 mr-1 inline" />Approved</Badge>,
    denied:   <Badge className="bg-rose-100 text-rose-800 border-rose-300"><X className="h-3 w-3 mr-1 inline" />Denied</Badge>,
  }[st] || <Badge>{st}</Badge>);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>End Time Change Requests</CardTitle>
          <p className="text-sm text-slate-500 mt-1">Seller-submitted requests to extend or shorten an active auction.</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} data-testid="refresh-end-time-requests">
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status tabs */}
        <div className="flex gap-2">
          {STATUS_TABS.map(s => (
            <Button
              key={s}
              variant={status === s ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatus(s)}
              data-testid={`end-time-filter-${s}`}
              className={status === s ? 'bg-blue-600 text-white' : ''}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </Button>
          ))}
        </div>

        {loading ? (
          <div className="py-8 flex justify-center text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />Loading…
          </div>
        ) : rows.length === 0 ? (
          <p className="text-center text-slate-500 py-8 italic">
            No {status} requests.
          </p>
        ) : (
          <div className="space-y-3">
            {rows.map(r => (
              <div key={r.id} className="border rounded-lg p-4 bg-slate-50 dark:bg-slate-800" data-testid={`end-time-request-row-${r.id}`}>
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h4 className="font-semibold">{r.auction_title || r.auction_id}</h4>
                    <p className="text-xs text-slate-500 mt-1">
                      Seller: {r.seller_email || r.seller_id} &nbsp;·&nbsp;
                      Submitted: <span className="font-mono">{r.submitted_at}</span>
                    </p>
                  </div>
                  {badge(r.status)}
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                  <div>
                    <div className="text-xs text-slate-500 uppercase">Current end</div>
                    <div className="font-mono">{r.current_end_time || '—'}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500 uppercase">Requested end</div>
                    <div className="font-mono text-blue-700">{r.requested_end_time}</div>
                  </div>
                </div>
                <div className="text-sm mb-3">
                  <div className="text-xs text-slate-500 uppercase mb-1">Reason</div>
                  <div className="whitespace-pre-wrap">{r.reason}</div>
                </div>
                {r.admin_note && (
                  <div className="text-sm mb-3">
                    <div className="text-xs text-slate-500 uppercase mb-1">Admin note</div>
                    <div className="whitespace-pre-wrap italic">{r.admin_note}</div>
                  </div>
                )}
                {r.status === 'pending' && (
                  <div className="space-y-2">
                    <Textarea
                      placeholder="Optional admin note (visible to seller in the confirmation email)"
                      value={noteFor[r.id] || ''}
                      onChange={(e) => setNoteFor({ ...noteFor, [r.id]: e.target.value })}
                      rows={2}
                      data-testid={`admin-note-${r.id}`}
                    />
                    <div className="flex gap-2">
                      <Button
                        onClick={() => act(r.id, 'approve')}
                        disabled={busyId === r.id}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                        data-testid={`approve-btn-${r.id}`}
                      >
                        {busyId === r.id ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Check className="h-4 w-4 mr-2" />}
                        Approve
                      </Button>
                      <Button
                        onClick={() => act(r.id, 'deny')}
                        disabled={busyId === r.id}
                        variant="destructive"
                        data-testid={`deny-btn-${r.id}`}
                      >
                        <X className="h-4 w-4 mr-2" /> Deny
                      </Button>
                    </div>
                  </div>
                )}
                {r.reviewed_at && (
                  <p className="text-xs text-slate-500 mt-2">
                    Reviewed by {r.reviewed_by} on <span className="font-mono">{r.reviewed_at}</span>
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
