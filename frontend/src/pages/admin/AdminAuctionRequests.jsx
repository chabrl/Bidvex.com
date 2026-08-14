/**
 * iter483.3 — Admin unified Auction Requests queue
 * =================================================
 *
 * Replaces AdminEndTimeRequests.  Shows every request type
 * (end_time · reserve_price · edit) in a single table with
 * type/status/date filters.  Approve/Deny actions call the
 * unified endpoint at /api/admin/auction-requests.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import {
  Card, CardContent, CardHeader, CardTitle,
} from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import {
  Loader2, Check, X, Clock, RefreshCw, DollarSign,
  FileText, MessageSquare,
} from 'lucide-react';
import API_BASE from '../../config';

const API = API_BASE;

const STATUSES = ['pending', 'approved', 'denied'];
const TYPES = ['all', 'end_time', 'reserve_price', 'edit'];

const typeIcon = (t) => {
  if (t === 'end_time') return Clock;
  if (t === 'reserve_price') return DollarSign;
  if (t === 'edit') return FileText;
  return MessageSquare;
};

export default function AdminAuctionRequests() {
  const { token } = useAuth();
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const [status, setStatus] = useState('pending');
  const [type,   setType]   = useState('all');
  const [q, setQ] = useState('');           // auction_id / seller_id search
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [noteFor, setNoteFor] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (type && type !== 'all') params.set('request_type', type);
      if (q.trim()) {
        // Backend supports auction_id + seller_id — try auction_id first,
        // fallback to seller_id.  We send both if the user pastes a UUID
        // that could match either.
        params.set('auction_id', q.trim());
      }
      const r = await axios.get(
        `${API}/admin/auction-requests?${params}`, { headers });
      let all = r.data?.rows || [];
      // If user typed something and auction_id search returned empty,
      // try again with seller_id.
      if (q.trim() && all.length === 0) {
        const params2 = new URLSearchParams();
        if (status) params2.set('status', status);
        if (type && type !== 'all') params2.set('request_type', type);
        params2.set('seller_id', q.trim());
        const r2 = await axios.get(
          `${API}/admin/auction-requests?${params2}`, { headers });
        all = r2.data?.rows || [];
      }
      setRows(all);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load requests');
    } finally {
      setLoading(false);
    }
  }, [status, type, q, headers]);

  useEffect(() => { load(); }, [load]);

  const act = async (id, action) => {
    setBusyId(id);
    try {
      await axios.post(
        `${API}/admin/auction-requests/${id}/${action}`,
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

  const statusBadge = (s) => ({
    pending:  <Badge className="bg-amber-100 text-amber-800 border-amber-300"><Clock className="h-3 w-3 mr-1 inline" />Pending</Badge>,
    approved: <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300"><Check className="h-3 w-3 mr-1 inline" />Approved</Badge>,
    denied:   <Badge className="bg-rose-100 text-rose-800 border-rose-300"><X className="h-3 w-3 mr-1 inline" />Denied</Badge>,
  }[s] || <Badge>{s}</Badge>);

  const typeBadge = (t) => {
    const Icon = typeIcon(t);
    return (
      <Badge variant="outline" className="inline-flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {t}
      </Badge>
    );
  };

  return (
    <Card data-testid="admin-auction-requests">
      <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 space-y-0">
        <div>
          <CardTitle>Auction Requests</CardTitle>
          <p className="text-sm text-slate-500 mt-1">
            Unified queue: end-time changes, reserve-price requests, and edit requests on bid-locked auctions.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load}
                data-testid="refresh-requests-btn">
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filters */}
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="flex gap-2">
            {STATUSES.map(s => (
              <Button key={s} size="sm"
                      variant={status === s ? 'default' : 'outline'}
                      onClick={() => setStatus(s)}
                      data-testid={`request-status-filter-${s}`}
                      className={status === s ? 'bg-blue-600 text-white' : ''}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </Button>
            ))}
          </div>
          <div className="flex gap-2">
            {TYPES.map(t => (
              <Button key={t} size="sm"
                      variant={type === t ? 'default' : 'outline'}
                      onClick={() => setType(t)}
                      data-testid={`request-type-filter-${t}`}
                      className={type === t ? 'bg-purple-600 text-white' : ''}>
                {t === 'all' ? 'All types' : t}
              </Button>
            ))}
          </div>
          <Input
            placeholder="Search by auction id or seller id"
            value={q} onChange={(e) => setQ(e.target.value)}
            data-testid="request-search-input"
            className="max-w-sm"
          />
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
              <div key={r.id}
                   className="border rounded-lg p-4 bg-slate-50 dark:bg-slate-800"
                   data-testid={`request-row-${r.id}`}>
                <div className="flex items-start justify-between gap-3 mb-2 flex-wrap">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      {typeBadge(r.request_type)}
                      {statusBadge(r.status)}
                      <span className="text-xs text-slate-500 font-mono">{r.submitted_at?.slice(0, 19).replace('T', ' ')}</span>
                    </div>
                    <h4 className="font-semibold mt-1 truncate">{r.auction_title || r.auction_id}</h4>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">
                      Seller: {r.seller_email || r.seller_id} · Target: <span className="font-mono">{r.target}</span>
                    </p>
                  </div>
                </div>
                {/* Payload summary */}
                <div className="text-sm bg-white dark:bg-slate-900 border rounded p-2 mb-2 font-mono text-xs overflow-x-auto">
                  {r.request_type === 'end_time' && (
                    <>
                      <div><span className="text-slate-500">Requested end:</span> {r.payload?.requested_end_time || '—'}</div>
                      {r.payload?.current_end_time && (
                        <div><span className="text-slate-500">Current end:</span> {r.payload.current_end_time}</div>
                      )}
                    </>
                  )}
                  {r.request_type === 'reserve_price' && (
                    <div><span className="text-slate-500">Reserve $</span> {r.payload?.requested_reserve_price ?? '—'}</div>
                  )}
                  {r.request_type === 'edit' && (
                    <>
                      <div><span className="text-slate-500">Field:</span> {r.payload?.field_name || '—'}</div>
                      <div><span className="text-slate-500">New value:</span> {typeof r.payload?.requested_new_value === 'object' ? JSON.stringify(r.payload?.requested_new_value) : r.payload?.requested_new_value}</div>
                    </>
                  )}
                </div>
                <div className="text-sm mb-2">
                  <div className="text-xs text-slate-500 uppercase mb-1">Reason</div>
                  <div className="whitespace-pre-wrap">{r.reason}</div>
                </div>
                {r.admin_note && (
                  <div className="text-sm mb-2">
                    <div className="text-xs text-slate-500 uppercase mb-1">Admin note</div>
                    <div className="whitespace-pre-wrap italic">{r.admin_note}</div>
                  </div>
                )}
                {r.status === 'pending' && (
                  <div className="space-y-2">
                    <Textarea
                      placeholder="Optional admin note (bilingual — visible to seller in confirmation email)"
                      rows={2}
                      value={noteFor[r.id] || ''}
                      onChange={(e) => setNoteFor({ ...noteFor, [r.id]: e.target.value })}
                      data-testid={`admin-note-${r.id}`}
                    />
                    <div className="flex flex-col sm:flex-row gap-2">
                      <Button onClick={() => act(r.id, 'approve')}
                              disabled={busyId === r.id}
                              className="bg-emerald-600 hover:bg-emerald-700 text-white w-full sm:w-auto"
                              data-testid={`approve-request-btn-${r.id}`}>
                        {busyId === r.id ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Check className="h-4 w-4 mr-2" />}
                        Approve
                      </Button>
                      <Button onClick={() => act(r.id, 'deny')}
                              disabled={busyId === r.id}
                              variant="destructive"
                              className="w-full sm:w-auto"
                              data-testid={`deny-request-btn-${r.id}`}>
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
