/**
 * iter201 — Phase 3 / 3B sub-tab 4 — Admin Compliance Alerts.
 *
 * Aggregates 5 alert types from /api/admin/compliance-alerts:
 *   ⛔ Pending Review Queue (iter206 — auto-paused vehicle listings, with Approve/Reject toolbar)
 *   🔴 Expired licences (within 30 days or already expired)
 *   🟠 High fraud-score listings
 *   🟡 Unreviewed manual_review listings (>24h)
 *   🔵 Territory bids (advisory only)
 */
import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  AlertTriangle, ShieldAlert, Clock, MapPin, Loader2, RefreshCw,
  PauseCircle, Check, X, PlayCircle, Hammer, Car, BadgeCheck, User as UserIcon,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';

const API = API_BASE;

const Section = ({ icon: Icon, title, count, color, children, testId }) => (
  <div className="rounded-lg border" data-testid={testId}>
    <div className={`flex items-center justify-between px-3 py-2 ${color} rounded-t-lg`}>
      <div className="flex items-center gap-2 font-semibold text-sm">
        <Icon className="h-4 w-4" /> {title}
      </div>
      <Badge variant="secondary">{count}</Badge>
    </div>
    <div className="p-3 space-y-2">{children}</div>
  </div>
);

// iter206 — Pending Review queue card with Approve / Reject toolbar
const PendingReviewCard = ({ entry, onAction }) => {
  const [busy, setBusy] = useState(false);
  const [showNote, setShowNote] = useState(null); // 'approve' | 'reject' | null
  const [note, setNote] = useState('');

  const submit = async (decision) => {
    setBusy(true);
    try {
      const token = localStorage.getItem('token');
      const url = `${API}/admin/compliance/listings/${entry.listing_id}/${decision}`;
      const res = await axios.post(url, { note: note || null }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(
        decision === 'approve'
          ? `Approved — listing back to ${res.data.restored_status}`
          : 'Rejected — seller notified'
      );
      onAction?.();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Action failed');
    } finally {
      setBusy(false);
      setShowNote(null);
      setNote('');
    }
  };

  const formatPausedAgo = (iso) => {
    if (!iso) return '—';
    const min = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
    if (min < 60) return `${min} min ago`;
    if (min < 1440) return `${Math.floor(min / 60)} h ago`;
    return `${Math.floor(min / 1440)} d ago`;
  };

  return (
    <div
      className="rounded-lg border border-rose-200 bg-rose-50/40 p-3 hover:bg-rose-50 transition-colors"
      data-testid={`pending-review-${entry.listing_id}`}
    >
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Photo thumbnail */}
        <div className="flex-shrink-0 w-full sm:w-24 h-20 rounded bg-slate-100 overflow-hidden flex items-center justify-center">
          {entry.first_image ? (
            <img src={entry.first_image} alt={entry.title}
                 width="96" height="80" loading="lazy"
                 className="w-full h-full object-cover" />
          ) : (
            <Car className="h-7 w-7 text-slate-300" />
          )}
        </div>

        {/* Body */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 mb-1">
            <div className="min-w-0">
              <h4 className="font-bold text-sm text-slate-900 truncate" title={entry.title}>
                {entry.title || '(untitled)'}
              </h4>
              <p className="text-[11px] text-slate-500">
                {entry.category || '—'}
                {entry.city ? ` · ${entry.city}` : ''}
                {entry.province ? `, ${entry.province}` : ''}
                {entry.starting_price ? ` · $${entry.starting_price}` : ''}
              </p>
            </div>
            <Badge variant="secondary" className="text-[10px] flex-shrink-0">
              {entry.collection === 'multi_item_listings' ? 'Multi-lot' : 'Single'}
            </Badge>
          </div>

          {/* Seller */}
          <div className="flex items-center flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600 mb-2">
            <span className="inline-flex items-center gap-1">
              {entry.seller_dealer_verified
                ? <BadgeCheck className="h-3.5 w-3.5 text-blue-600" />
                : <UserIcon className="h-3.5 w-3.5" />}
              <span className="font-semibold">{entry.seller_email || entry.seller_id}</span>
            </span>
            <span className="text-slate-500">
              {entry.seller_type || 'individual'}
              {entry.seller_dealer_verified ? ' · dealer verified' : ''}
            </span>
          </div>

          {/* Detection signals */}
          <div className="flex items-center flex-wrap gap-1.5 mb-2">
            {(entry.compliance_signals || []).map((s) => (
              <span
                key={s}
                className="inline-block text-[10px] font-mono bg-rose-100 text-rose-800 rounded px-1.5 py-0.5"
              >
                {s}
              </span>
            ))}
            <span className="text-[10px] text-slate-400 ml-auto">
              <PauseCircle className="inline h-3 w-3 mr-0.5" />
              Paused {formatPausedAgo(entry.paused_at)} by{' '}
              <span className="font-mono">{entry.paused_by}</span>
            </span>
          </div>

          {/* Note input (shown only when approving/rejecting) */}
          {showNote && (
            <div className="mb-2">
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={showNote === 'approve'
                  ? 'Optional note: why this listing is OK to publish (audit trail)'
                  : 'Optional note: reason for rejection (sent to seller)'}
                rows={2}
                className="w-full text-xs border rounded p-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                data-testid={`pending-review-note-${entry.listing_id}`}
              />
            </div>
          )}

          {/* Toolbar */}
          <div className="flex items-center gap-2">
            {!showNote ? (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-emerald-500 text-emerald-700 hover:bg-emerald-50"
                  onClick={() => setShowNote('approve')}
                  disabled={busy}
                  data-testid={`pending-review-approve-${entry.listing_id}`}
                >
                  <Check className="h-3.5 w-3.5 mr-1" /> Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-rose-500 text-rose-700 hover:bg-rose-50"
                  onClick={() => setShowNote('reject')}
                  disabled={busy}
                  data-testid={`pending-review-reject-${entry.listing_id}`}
                >
                  <X className="h-3.5 w-3.5 mr-1" /> Reject
                </Button>
                <a
                  href={`/listing/${entry.listing_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-slate-600 hover:text-cyan-700 hover:underline ml-auto"
                  data-testid={`pending-review-view-${entry.listing_id}`}
                >
                  View listing →
                </a>
              </>
            ) : (
              <>
                <Button
                  size="sm"
                  className={showNote === 'approve' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'}
                  onClick={() => submit(showNote)}
                  disabled={busy}
                  data-testid={`pending-review-confirm-${showNote}-${entry.listing_id}`}
                >
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : (
                    showNote === 'approve' ? <PlayCircle className="h-3.5 w-3.5 mr-1" /> : <Hammer className="h-3.5 w-3.5 mr-1" />
                  )}
                  Confirm {showNote === 'approve' ? 'approval' : 'rejection'}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => { setShowNote(null); setNote(''); }}
                  disabled={busy}
                >
                  Cancel
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const AdminComplianceAlerts = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cleanupRunning, setCleanupRunning] = useState(false);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API}/admin/compliance-alerts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, []);

  // iter206 — One-click cleanup runner
  const runCleanup = async () => {
    setCleanupRunning(true);
    try {
      const token = localStorage.getItem('token');
      const r = await axios.post(`${API}/admin/compliance/run-cleanup`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(`Watchdog ran — examined ${r.data.total_examined}, paused ${r.data.total_paused}`);
      await fetchAlerts();
    } catch (e) {
      toast.error('Cleanup run failed');
    } finally {
      setCleanupRunning(false);
    }
  };

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  if (loading || !data) {
    return <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>;
  }

  const queue = data.pending_review_queue || [];

  return (
    <Card data-testid="admin-compliance-alerts">
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle>Compliance Alerts</CardTitle>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={runCleanup}
              disabled={cleanupRunning}
              data-testid="admin-run-cleanup-btn"
            >
              {cleanupRunning
                ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                : <Hammer className="h-3.5 w-3.5 mr-1" />}
              Run Cleanup
            </Button>
            <Button variant="outline" size="sm" onClick={fetchAlerts}>
              <RefreshCw className="h-3.5 w-3.5 mr-1" /> Refresh
            </Button>
          </div>
        </div>
        <p className="text-xs text-slate-500">Last refreshed: {new Date(data.checked_at).toLocaleString()}</p>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* iter206 — Pending Review Moderation Queue (TOP — most urgent) */}
        <Section
          icon={PauseCircle}
          title="Pending Review — Auto-Paused Vehicle Listings"
          count={queue.length}
          color={queue.length > 0 ? "bg-rose-50 text-rose-800" : "bg-emerald-50 text-emerald-800"}
          testId="alerts-pending-review"
        >
          {queue.length === 0 ? (
            <p className="text-xs text-slate-500">
              No listings pending review. Press <strong>Run Cleanup</strong> above to scan for
              suspicious active listings on demand.
            </p>
          ) : (
            <div className="space-y-2.5" data-testid="pending-review-queue">
              {queue.map((entry) => (
                <PendingReviewCard
                  key={`${entry.collection}:${entry.listing_id}`}
                  entry={entry}
                  onAction={fetchAlerts}
                />
              ))}
            </div>
          )}
        </Section>

        <Section
          icon={ShieldAlert}
          title="Expired / Expiring Licences"
          count={data.expired?.length || 0}
          color="bg-red-50 text-red-800"
          testId="alerts-expired"
        >
          {(data.expired?.length || 0) === 0 ? (
            <p className="text-xs text-slate-500">No licences expiring in the next 30 days.</p>
          ) : data.expired.map((u) => (
            <div key={u.user_id} className="flex items-center justify-between text-sm border-b pb-1.5 last:border-b-0">
              <div>
                <span className="font-medium">{u.name || u.email}</span>{' '}
                <span className="text-slate-500 text-xs">· {u.province || '?'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs ${u.expired ? 'text-red-700 font-bold' : 'text-amber-600'}`}>
                  {u.expired ? '⛔ Expired' : '⚠ Expiring'} {new Date(u.expiry_date).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </Section>

        <Section
          icon={AlertTriangle}
          title="High Fraud Score Listings"
          count={data.high_fraud_score?.length || 0}
          color="bg-orange-50 text-orange-800"
          testId="alerts-fraud"
        >
          {(data.high_fraud_score?.length || 0) === 0 ? (
            <p className="text-xs text-slate-500">No listings flagged.</p>
          ) : data.high_fraud_score.map((v) => (
            <div key={v.vehicle_id} className="text-sm border-b pb-1.5 last:border-b-0">
              <span className="font-medium">{v.title}</span>
              <span className="text-orange-700 ml-2 text-xs font-mono">score {Number(v.fraud_score).toFixed(2)}</span>
              {v.flags?.length > 0 && (
                <p className="text-[11px] text-slate-500 mt-0.5">{v.flags.join(' · ')}</p>
              )}
            </div>
          ))}
        </Section>

        <Section
          icon={Clock}
          title="Unreviewed Manual-Review Listings (>24h)"
          count={data.unreviewed_manual_review?.length || 0}
          color="bg-yellow-50 text-yellow-800"
          testId="alerts-unreviewed"
        >
          {(data.unreviewed_manual_review?.length || 0) === 0 ? (
            <p className="text-xs text-slate-500">All manual-review listings are current.</p>
          ) : data.unreviewed_manual_review.map((v) => (
            <div key={v.vehicle_id} className="text-sm border-b pb-1.5 last:border-b-0">
              <span className="font-medium">{v.title}</span>
              <span className="text-slate-500 ml-2 text-xs">submitted {new Date(v.created_at).toLocaleString()}</span>
            </div>
          ))}
        </Section>

        <Section
          icon={MapPin}
          title="Territory Bids (last 7 days)"
          count={data.territory_bids?.length || 0}
          color="bg-blue-50 text-blue-800"
          testId="alerts-territory"
        >
          {(data.territory_bids?.length || 0) === 0 ? (
            <p className="text-xs text-slate-500">No territorial bids logged.</p>
          ) : data.territory_bids.map((b, i) => (
            <div key={i} className="text-sm border-b pb-1.5 last:border-b-0">
              <span className="font-medium">{b.province}</span>
              <span className="text-slate-500 ml-2 text-xs">Vehicle {b.vehicle_id}</span>
              <span className="text-slate-500 ml-2 text-xs">${b.amount}</span>
              <span className="text-slate-500 ml-2 text-xs">{new Date(b.timestamp).toLocaleString()}</span>
            </div>
          ))}
        </Section>

      </CardContent>
    </Card>
  );
};

export default AdminComplianceAlerts;
