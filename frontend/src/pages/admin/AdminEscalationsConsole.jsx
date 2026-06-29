/**
 * iter320 — Admin Escalations Console.
 *
 * Lists every Live Support escalation ticket created via the AI Core
 * widget (`POST /api/support/escalate`). Admins can:
 *   • Filter by status / search by user / problem.
 *   • Drill into a ticket to see the full Context Packet (problem +
 *     details + conversation transcript with role-coded bubbles).
 *   • Change ticket status: open → acknowledged → resolved (or
 *     dismissed).
 *   • Save admin notes.
 *
 * Surfaced inside the existing Admin Dashboard under the Team tab
 * (alongside Team Members and Careers).
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  LifeBuoy, Search, Loader2, Save, Filter, Clock, User as UserIcon,
  MessageSquare, AlertTriangle, CheckCircle2, Send,
} from 'lucide-react';

import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';

const STATUS_COLORS = {
  open:         'bg-rose-100 text-rose-800',
  acknowledged: 'bg-amber-100 text-amber-800',
  resolved:     'bg-emerald-100 text-emerald-800',
  dismissed:    'bg-slate-200 text-slate-700',
};

const ROLE_BG = {
  user:      'bg-sky-50 border-sky-200',
  assistant: 'bg-slate-50 border-slate-200',
  system:    'bg-amber-50 border-amber-200',
  admin:     'bg-rose-50 border-rose-300',
};
const ROLE_LABEL = {
  user:      'USER',
  assistant: 'AI',
  system:    'SYSTEM',
  admin:     '🛡 ADMIN',
};

function authHeaders(token) {
  return { Authorization: `Bearer ${token}` };
}


export default function AdminEscalationsConsole() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ status: '', search: '' });
  const [selectedId, setSelectedId] = useState(null);
  const [pendingCount, setPendingCount] = useState(0);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.status) params.status = filters.status;
      if (filters.search) params.search = filters.search;
      const r = await axios.get(`${API_BASE}/admin/support/escalations`, {
        headers: authHeaders(token), params,
      });
      setItems(r.data?.items || []);
    } catch {
      toast.error('Failed to load escalations');
    } finally {
      setLoading(false);
    }
  }, [token, filters]);

  const fetchPendingCount = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/admin/support/escalations/pending/count`, {
        headers: authHeaders(token),
      });
      setPendingCount(r.data?.open_count || 0);
    } catch { /* noop */ }
  }, [token]);

  useEffect(() => { fetchList(); }, [fetchList]);
  useEffect(() => { fetchPendingCount(); }, [fetchPendingCount]);

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4" data-testid="admin-escalations-console">
      <header className="mb-4 flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <LifeBuoy className="h-6 w-6 text-rose-600" />
            Live Support Escalations
            {pendingCount > 0 && (
              <Badge className="bg-rose-600 text-white" data-testid="pending-count-badge">
                {pendingCount} open
              </Badge>
            )}
          </h1>
          <p className="text-sm text-slate-500">
            Tickets created when users escalate from the AI Core widget.
            The full conversation Context Packet is preserved.
          </p>
        </div>
      </header>

      <Card>
        <CardContent className="p-4 flex flex-wrap items-center gap-3">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm bg-white"
            data-testid="filter-status"
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
            <option value="dismissed">Dismissed</option>
          </select>
          <div className="relative ml-auto">
            <Search className="absolute left-2 top-2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search user / problem / details…"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="pl-8 h-8 w-72"
              data-testid="filter-search"
            />
          </div>
        </CardContent>
      </Card>

      <div className="mt-4">
        {loading && (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-rose-600" />
          </div>
        )}

        {!loading && items.length === 0 && (
          <Card>
            <CardContent className="p-8 text-center text-slate-500" data-testid="escalations-empty">
              No escalation tickets match the current filters.
            </CardContent>
          </Card>
        )}

        {!loading && items.length > 0 && (
          <Card>
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-sm" data-testid="escalations-table">
                <thead className="bg-slate-50 border-b text-left">
                  <tr>
                    <th className="px-4 py-2">User</th>
                    <th className="px-4 py-2">Problem</th>
                    <th className="px-4 py-2">Lang</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Created</th>
                    <th className="px-4 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((e) => (
                    <tr key={e.id} className="border-b hover:bg-slate-50" data-testid={`escalation-row-${e.id}`}>
                      <td className="px-4 py-2 font-medium truncate max-w-xs">{e.user_email || e.user_id}</td>
                      <td className="px-4 py-2 text-slate-600 truncate max-w-md">{e.problem}</td>
                      <td className="px-4 py-2 text-xs uppercase">{e.language}</td>
                      <td className="px-4 py-2">
                        <Badge className={STATUS_COLORS[e.status] || ''}>{e.status}</Badge>
                      </td>
                      <td className="px-4 py-2 text-xs text-slate-500">
                        {e.created_at ? new Date(e.created_at).toLocaleString('en-CA') : ''}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Button
                          size="sm" variant="outline"
                          onClick={() => setSelectedId(e.id)}
                          data-testid={`view-escalation-${e.id}`}
                        >
                          View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}
      </div>

      {selectedId && (
        <EscalationDetailDialog
          token={token}
          ticketId={selectedId}
          open
          onClose={() => setSelectedId(null)}
          onUpdated={() => { fetchList(); fetchPendingCount(); }}
        />
      )}
    </div>
  );
}


function EscalationDetailDialog({ token, ticketId, open, onClose, onUpdated }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  // iter322 — Inline admin reply composer state.
  const [replyDraft, setReplyDraft] = useState('');
  const [sendingReply, setSendingReply] = useState(false);

  // Refetch the ticket (called after each admin reply / user reply / status change).
  const refetch = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/admin/support/escalations/${ticketId}`, {
        headers: authHeaders(token),
      });
      setData(r.data);
      setStatus(r.data?.status || 'open');
      if (!notes) setNotes(r.data?.admin_notes || '');
    } catch { /* noop */ }
  }, [ticketId, token, notes]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/admin/support/escalations/${ticketId}`, {
          headers: authHeaders(token),
        });
        if (!cancelled) {
          setData(r.data);
          setStatus(r.data?.status || 'open');
          setNotes(r.data?.admin_notes || '');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [ticketId, token]);

  // iter322 — Subscribe to ticket_updated SSE so concurrent admins see
  // the same conversation in real time. Uses the existing admin
  // realtime/stream endpoint already mounted by EscalationAlertProvider
  // — we just listen via window-events so we don't double-open the SSE
  // connection.
  useEffect(() => {
    const handler = (ev) => {
      try {
        const d = ev.detail || {};
        if (d.id === ticketId) refetch();
      } catch { /* noop */ }
    };
    window.addEventListener('bidvex:ticket-updated', handler);
    return () => window.removeEventListener('bidvex:ticket-updated', handler);
  }, [ticketId, refetch]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.patch(
        `${API_BASE}/admin/support/escalations/${ticketId}/status`,
        { status, admin_notes: notes },
        { headers: authHeaders(token) },
      );
      toast.success('Saved');
      onUpdated?.();
      onClose();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail?.message_en || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  // iter322 — Live help-desk: admin posts a reply, the user receives it
  // instantly via SSE + email. The transcript card refreshes from the
  // server response so the new admin bubble lands without a full page reload.
  const handleSendReply = async () => {
    const msg = replyDraft.trim();
    if (!msg || sendingReply) return;
    setSendingReply(true);
    try {
      const r = await axios.post(
        `${API_BASE}/admin/support/escalations/${ticketId}/reply`,
        { message: msg },
        { headers: authHeaders(token) },
      );
      setReplyDraft('');
      if (r.data?.ticket) {
        setData(r.data.ticket);
        setStatus(r.data.ticket.status || status);
      } else {
        await refetch();
      }
      toast.success('Reply sent — user notified');
      onUpdated?.();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg = (typeof detail === 'object' ? detail?.message_en : detail) || 'Reply failed';
      toast.error(msg);
    } finally {
      setSendingReply(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-4xl max-h-[92vh] overflow-y-auto" data-testid="escalation-detail-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <LifeBuoy className="h-5 w-5 text-rose-600" />
            Ticket #{ticketId.slice(0, 8)}
          </DialogTitle>
        </DialogHeader>

        {loading && <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-rose-600" /></div>}

        {data && (
          <div className="space-y-4 text-sm">
            {/* Header */}
            <Card>
              <CardContent className="p-4 grid grid-cols-2 gap-3 text-xs">
                <div className="flex items-center gap-2">
                  <UserIcon className="h-4 w-4 text-slate-400" />
                  <span className="text-slate-500">User:</span>
                  <strong>{data.user_email || data.user_id}</strong>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-slate-400" />
                  <span className="text-slate-500">Created:</span>
                  {data.created_at}
                </div>
                <div>
                  <span className="text-slate-500">Language:</span> {data.language?.toUpperCase()}
                </div>
                <div>
                  <span className="text-slate-500">Page:</span> {data.page_url || '—'}
                </div>
                <div>
                  <span className="text-slate-500">Session:</span> {data.session_id || '—'}
                </div>
                <div>
                  <span className="text-slate-500">IP:</span> {data.ip_address || '—'}
                </div>
              </CardContent>
            </Card>

            {/* Problem (Q1) */}
            <Card className="border-l-4 border-rose-500" data-testid="problem-card">
              <CardContent className="p-4">
                <h3 className="text-sm font-bold text-rose-700 flex items-center gap-1 mb-1">
                  <AlertTriangle className="h-4 w-4" /> Problem (Q1)
                </h3>
                <p className="text-sm text-rose-900 whitespace-pre-wrap">{data.problem}</p>
              </CardContent>
            </Card>

            {/* Details (Q2) */}
            <Card className="border-l-4 border-sky-500" data-testid="details-card">
              <CardContent className="p-4">
                <h3 className="text-sm font-bold text-sky-700 mb-1">Details (Q2)</h3>
                <p className="text-sm text-sky-900 whitespace-pre-wrap">
                  {data.details || <span className="italic text-slate-400">(none provided)</span>}
                </p>
              </CardContent>
            </Card>

            {/* Transcript */}
            <Card data-testid="transcript-card">
              <CardContent className="p-4">
                <h3 className="text-sm font-bold flex items-center gap-1 mb-2">
                  <MessageSquare className="h-4 w-4" /> Conversation Transcript
                </h3>
                {(data.transcript || []).length === 0 && (
                  <p className="text-xs text-slate-400 italic">No transcript captured.</p>
                )}
                <ul className="space-y-2">
                  {(data.transcript || []).map((m, i) => (
                    <li
                      key={i}
                      className={`rounded border px-3 py-2 text-xs ${ROLE_BG[m.role] || 'bg-slate-50 border-slate-200'}`}
                      data-testid={`transcript-msg-${i}`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-[10px] uppercase">
                          {ROLE_LABEL[m.role] || m.role || 'msg'}
                        </Badge>
                        {m.ts && <span className="text-[10px] text-slate-400">{m.ts}</span>}
                      </div>
                      <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{m.content}</p>
                    </li>
                  ))}
                </ul>
                {/* iter322 — Inline admin reply composer (live help-desk) */}
                <div className="mt-4 pt-4 border-t border-slate-200 space-y-2" data-testid="admin-reply-composer">
                  <Label className="text-xs font-semibold flex items-center gap-2 text-rose-700">
                    <MessageSquare className="h-3.5 w-3.5" /> Reply to user (sends in-app + email)
                  </Label>
                  <Textarea
                    rows={3}
                    value={replyDraft}
                    onChange={(e) => setReplyDraft(e.target.value)}
                    placeholder="Type your reply — the user receives it instantly in their chat widget…"
                    maxLength={2500}
                    className="text-sm"
                    data-testid="admin-reply-textarea"
                  />
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] text-slate-400">
                      Reply-To: <strong>support@bidvex.com</strong> · {replyDraft.length}/2500
                    </span>
                    <Button
                      onClick={handleSendReply}
                      disabled={sendingReply || !replyDraft.trim() || data.status === 'dismissed'}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      data-testid="admin-reply-send-btn"
                    >
                      {sendingReply ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}
                      Send reply
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Status + Notes */}
            <Card>
              <CardContent className="p-4 space-y-3">
                <div>
                  <Label>Status</Label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm bg-white"
                    data-testid="escalation-status-select"
                  >
                    <option value="open">Open</option>
                    <option value="acknowledged">Acknowledged</option>
                    <option value="resolved">Resolved</option>
                    <option value="dismissed">Dismissed</option>
                  </select>
                </div>
                <div>
                  <Label>Admin Notes</Label>
                  <Textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={3}
                    data-testid="escalation-notes-textarea"
                  />
                </div>
                <div className="flex items-center justify-end gap-2">
                  <Button variant="outline" onClick={onClose}>Cancel</Button>
                  <Button
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-rose-600 hover:bg-rose-700 text-white"
                    data-testid="save-escalation-btn"
                  >
                    {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                    Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
