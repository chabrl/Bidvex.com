import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../components/ui/dialog';
import { Textarea } from '../../components/ui/textarea';
import {
  AlertTriangle, CheckCircle2, Undo2, ArrowUpCircle, StickyNote, Loader2, RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { extractErrorMessage } from '../../utils/errorHandler';

const API = API_BASE;

const REASON_LABELS = {
  item_not_as_described: 'Item not as described',
  no_contact_from_seller: 'No contact from seller',
  payment_issue: 'Payment issue',
  other: 'Other',
};

const STATUS_STYLES = {
  open: 'bg-red-100 text-red-700 border-red-200',
  escalated: 'bg-purple-100 text-purple-700 border-purple-200',
  resolved: 'bg-emerald-100 text-emerald-700 border-emerald-200',
};

/**
 * iter300 P1 — General dispute queue (marketplace / lots / storage).
 * Actions: Resolve—Release to Seller, Resolve—Refund to Buyer, Escalate,
 * and internal admin-only notes.
 */
const GeneralDisputeQueue = () => {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [statusFilter, setStatusFilter] = useState('open');
  const [refreshing, setRefreshing] = useState(false);
  // action dialog: {dispute, mode: 'release_to_seller'|'refund_buyer'|'escalate'|'note'}
  const [action, setAction] = useState(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [expandedNotes, setExpandedNotes] = useState({});

  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true);
    try {
      const res = await axios.get(`${API}/admin/disputes/queue?status=${statusFilter}`,
        { headers: { Authorization: `Bearer ${token}` } });
      setData(res.data);
    } catch {
      toast.error('Failed to load disputes');
    } finally {
      setRefreshing(false);
    }
  }, [token, statusFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const runAction = async () => {
    if (!action) return;
    const { dispute, mode } = action;
    if (note.trim().length < 5 && mode !== 'note') {
      toast.error('Please provide a note (min 5 characters)');
      return;
    }
    if (mode === 'note' && note.trim().length < 3) {
      toast.error('Note too short');
      return;
    }
    setBusy(true);
    try {
      if (mode === 'release_to_seller' || mode === 'refund_buyer') {
        await axios.post(`${API}/admin/disputes/${dispute.id}/resolve`,
          { action: mode, note: note.trim() }, { headers });
        toast.success(mode === 'refund_buyer'
          ? 'Dispute resolved — buyer refunded. Both parties notified.'
          : 'Dispute resolved — payout released to seller. Both parties notified.');
      } else if (mode === 'escalate') {
        await axios.post(`${API}/admin/disputes/${dispute.id}/escalate`,
          { note: note.trim() }, { headers });
        toast.success('Dispute escalated for senior/legal review');
      } else {
        await axios.post(`${API}/admin/disputes/${dispute.id}/note`,
          { note: note.trim() }, { headers });
        toast.success('Internal note added');
      }
      setAction(null);
      setNote('');
      fetchData(true);
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  const DIALOG_COPY = {
    release_to_seller: {
      title: 'Resolve — Release to Seller',
      desc: 'Marks the dispute resolved and approves the seller payout. Both parties receive the outcome by email + notification.',
    },
    refund_buyer: {
      title: 'Resolve — Refund to Buyer',
      desc: 'Triggers a Stripe refund of the buyer charge (when one exists), cancels the seller payout and notifies both parties.',
    },
    escalate: {
      title: 'Escalate Dispute',
      desc: 'Flags this dispute for legal/senior review. Add an internal note explaining why.',
    },
    note: {
      title: 'Add Internal Note',
      desc: 'Visible to admins only — never shown to the buyer or seller.',
    },
  };

  return (
    <Card data-testid="general-dispute-queue">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-600" />
            General Disputes (Marketplace · Lots · Storage)
            {data?.open_count > 0 && (
              <Badge className="bg-red-600 text-white" data-testid="dispute-open-count">{data.open_count} open</Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-2">
            {['open', 'resolved', 'all'].map((s) => (
              <Button key={s} size="sm" variant={statusFilter === s ? 'default' : 'outline'}
                onClick={() => setStatusFilter(s)} data-testid={`dispute-filter-${s}`}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </Button>
            ))}
            <Button size="sm" variant="ghost" onClick={() => fetchData(true)} disabled={refreshing}>
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {!data ? (
          <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
        ) : data.disputes.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8" data-testid="dispute-queue-empty">
            No {statusFilter === 'all' ? '' : statusFilter} disputes. 🎉
          </p>
        ) : (
          <div className="space-y-3">
            {data.disputes.map((d) => (
              <div key={d.id} className="border rounded-lg p-4" data-testid={`dispute-row-${d.id}`}>
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="font-semibold truncate" title={d.listing_title}>{d.listing_title}</h4>
                      <Badge variant="outline" className={STATUS_STYLES[d.status] || ''}>{d.status}</Badge>
                      <Badge variant="secondary" className="text-[10px]">{d.section}</Badge>
                      {d.outcome && (
                        <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px]">
                          {d.outcome === 'refund_buyer' ? 'Refunded to buyer' : 'Released to seller'}
                        </Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-muted-foreground">
                      <span><strong>Buyer:</strong> {d.buyer_name}</span>
                      <span><strong>Seller:</strong> {d.seller_name}</span>
                      <span><strong>Hammer:</strong> ${Number(d.hammer_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                      <span><strong>Reason:</strong> {REASON_LABELS[d.reason_category] || d.reason_category}</span>
                      <span><strong>Filed:</strong> {d.created_at ? new Date(d.created_at).toLocaleString() : '—'} by {d.filed_by_role}</span>
                    </div>
                    {d.details && (
                      <p className="text-sm mt-2 text-slate-700 bg-slate-50 rounded p-2 border border-slate-100">{d.details}</p>
                    )}
                    {(d.internal_notes || []).length > 0 && (
                      <div className="mt-2">
                        <button
                          className="text-xs text-blue-700 underline"
                          onClick={() => setExpandedNotes((p) => ({ ...p, [d.id]: !p[d.id] }))}
                          data-testid={`toggle-notes-${d.id}`}
                        >
                          {expandedNotes[d.id] ? 'Hide' : 'Show'} {d.internal_notes.length} internal note(s)
                        </button>
                        {expandedNotes[d.id] && (
                          <div className="mt-1.5 space-y-1.5">
                            {d.internal_notes.map((n, i) => (
                              <div key={i} className="text-xs bg-amber-50 border border-amber-100 rounded p-2">
                                <span className="font-medium">{n.by_email}</span>
                                <span className="text-muted-foreground"> · {n.at ? new Date(n.at).toLocaleString() : ''}{n.kind === 'escalation' ? ' · ESCALATION' : ''}</span>
                                <p className="mt-0.5">{n.text}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                    {d.resolution_note && (
                      <p className="text-xs mt-2 text-emerald-800 bg-emerald-50 rounded p-2 border border-emerald-100">
                        <strong>Resolution:</strong> {d.resolution_note}
                      </p>
                    )}
                  </div>

                  {['open', 'escalated'].includes(d.status) && (
                    <div className="flex flex-wrap lg:flex-col gap-2 shrink-0">
                      <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700"
                        onClick={() => { setAction({ dispute: d, mode: 'release_to_seller' }); setNote(''); }}
                        data-testid={`release-btn-${d.id}`}>
                        <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" /> Release to Seller
                      </Button>
                      <Button size="sm" variant="destructive"
                        onClick={() => { setAction({ dispute: d, mode: 'refund_buyer' }); setNote(''); }}
                        data-testid={`refund-btn-${d.id}`}>
                        <Undo2 className="h-3.5 w-3.5 mr-1.5" /> Refund Buyer
                      </Button>
                      {d.status !== 'escalated' && (
                        <Button size="sm" variant="outline" className="border-purple-300 text-purple-700"
                          onClick={() => { setAction({ dispute: d, mode: 'escalate' }); setNote(''); }}
                          data-testid={`escalate-btn-${d.id}`}>
                          <ArrowUpCircle className="h-3.5 w-3.5 mr-1.5" /> Escalate
                        </Button>
                      )}
                      <Button size="sm" variant="ghost"
                        onClick={() => { setAction({ dispute: d, mode: 'note' }); setNote(''); }}
                        data-testid={`note-btn-${d.id}`}>
                        <StickyNote className="h-3.5 w-3.5 mr-1.5" /> Add Note
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <Dialog open={!!action} onOpenChange={(o) => { if (!o) setAction(null); }}>
        <DialogContent data-testid="dispute-action-dialog">
          <DialogHeader>
            <DialogTitle>{action ? DIALOG_COPY[action.mode].title : ''}</DialogTitle>
            <DialogDescription>
              {action ? DIALOG_COPY[action.mode].desc : ''}
              {action && <span className="block mt-1 font-medium text-slate-700">“{action.dispute.listing_title}”</span>}
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={4}
            placeholder={action?.mode === 'note' ? 'Internal note (admins only)…' : 'Resolution / escalation note (required, included in party emails for resolutions)…'}
            data-testid="dispute-action-note"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAction(null)}>Cancel</Button>
            <Button onClick={runAction} disabled={busy} data-testid="dispute-action-confirm">
              {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
};

export default GeneralDisputeQueue;
