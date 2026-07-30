/**
 * iter420 — Admin Vehicle Dealer Management page.
 *
 * Three capabilities:
 *   1. Dealer list — filterable by status/kind/search, quick actions.
 *   2. Dealer profile — registration + license + docs + status.
 *   3. Activity history — auctions, sold lots, buyer interactions.
 *
 * Reuses the existing admin Card/Button/Badge/Input primitives and the
 * `require_admin` middleware on the backend. No changes to the dealer
 * verification pipeline itself.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import API_BASE from '../../config';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import {
  Building2, Handshake, Search, RefreshCw, ChevronLeft, ShieldCheck,
  ShieldOff, ShieldAlert, Clock, XCircle, CheckCircle, Ban, Play,
  ExternalLink, FileText, Gavel, Car, Users, DollarSign, Package,
  Mail, Phone, MapPin, Calendar,
} from 'lucide-react';

const STATUS_FILTERS = [
  { id: 'all',       label: 'All',       icon: Users,        color: 'bg-slate-100 text-slate-700' },
  { id: 'pending',   label: 'Pending',   icon: Clock,        color: 'bg-amber-100 text-amber-800' },
  { id: 'approved',  label: 'Approved',  icon: ShieldCheck,  color: 'bg-emerald-100 text-emerald-800' },
  { id: 'suspended', label: 'Suspended', icon: ShieldOff,    color: 'bg-orange-100 text-orange-800' },
  { id: 'rejected',  label: 'Rejected',  icon: XCircle,      color: 'bg-rose-100 text-rose-800' },
];

const KIND_FILTERS = [
  { id: 'all',    label: 'All' },
  { id: 'dealer', label: 'Dealers' },
  { id: 'broker', label: 'Brokers' },
];

const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');
const _authHeaders = () => ({ Authorization: `Bearer ${_token()}` });

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' }); }
  catch { return iso; }
};

const fmtCurrency = (n) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n) || 0);

// ── Status badge (shared) ─────────────────────────────────────────────
const StatusBadge = ({ status }) => {
  const key = (status || 'pending').toLowerCase();
  const map = {
    approved:   'bg-emerald-100 text-emerald-800 border-emerald-300',
    pending:    'bg-amber-100 text-amber-800 border-amber-300',
    pending_review: 'bg-amber-100 text-amber-800 border-amber-300',
    under_review: 'bg-blue-100 text-blue-800 border-blue-300',
    rejected:   'bg-rose-100 text-rose-800 border-rose-300',
    suspended:  'bg-orange-100 text-orange-800 border-orange-300',
  };
  return (
    <Badge className={`${map[key] || map.pending} border`} data-testid={`dealer-status-${key}`}>
      {key.replace(/_/g, ' ').toUpperCase()}
    </Badge>
  );
};

// ── Dealer detail panel ───────────────────────────────────────────────
const DealerDetailPanel = ({ userId, onBack, onActionCompleted }) => {
  const [profile, setProfile] = useState(null);
  const [activity, setActivity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, aRes] = await Promise.all([
        axios.get(`${API_BASE}/admin/vehicle-dealers/${userId}`, { headers: _authHeaders() }),
        axios.get(`${API_BASE}/admin/vehicle-dealers/${userId}/activity`, { headers: _authHeaders() }),
      ]);
      setProfile(pRes.data);
      setActivity(aRes.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load dealer profile');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  const runAction = async (verb, body = {}) => {
    setActionBusy(verb);
    try {
      await axios.post(
        `${API_BASE}/admin/vehicle-dealers/${userId}/${verb}`,
        body,
        { headers: _authHeaders() },
      );
      toast.success(`Dealer ${verb}d`);
      await load();
      onActionCompleted?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || `Failed to ${verb}`);
    } finally {
      setActionBusy('');
    }
  };

  const handleSuspend = () => {
    const reason = window.prompt('Reason for suspension (optional):') || '';
    runAction('suspend', { reason });
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-slate-500">
          <RefreshCw className="h-6 w-6 mx-auto animate-spin mb-2" />
          Loading dealer profile…
        </CardContent>
      </Card>
    );
  }
  if (!profile) return null;

  const { identity, status, dealer_registration, broker_registration, documents } = profile;
  const kind = profile.kind;
  const suspended = status?.suspended;

  return (
    <div className="space-y-4" data-testid="dealer-detail-panel">
      {/* Header + actions */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack} data-testid="dealer-detail-back-btn">
          <ChevronLeft className="h-4 w-4 mr-1" /> Back to list
        </Button>
        <div className="flex items-center gap-2">
          {status?.verification_status !== 'approved' && !suspended && (
            <Button
              onClick={() => runAction('approve')}
              disabled={!!actionBusy}
              className="bg-emerald-600 hover:bg-emerald-700"
              data-testid="dealer-approve-btn"
            >
              <CheckCircle className="h-4 w-4 mr-1" /> Approve
            </Button>
          )}
          {!suspended && (
            <Button
              onClick={handleSuspend}
              disabled={!!actionBusy}
              variant="outline"
              className="border-orange-300 text-orange-700 hover:bg-orange-50"
              data-testid="dealer-suspend-btn"
            >
              <Ban className="h-4 w-4 mr-1" /> Suspend
            </Button>
          )}
          {suspended && (
            <Button
              onClick={() => runAction('reinstate')}
              disabled={!!actionBusy}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="dealer-reinstate-btn"
            >
              <Play className="h-4 w-4 mr-1" /> Reinstate
            </Button>
          )}
        </div>
      </div>

      {/* Identity + status */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            {kind === 'broker' ? <Handshake className="h-5 w-5 text-purple-600" /> : <Building2 className="h-5 w-5 text-emerald-600" />}
            <span data-testid="dealer-detail-name">{identity.name || identity.email}</span>
            <StatusBadge status={status.verification_status} />
            <Badge variant="outline" className="capitalize">{kind}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-y-2 gap-x-6 text-sm">
          <div className="flex items-center gap-2 text-slate-700">
            <Mail className="h-4 w-4 text-slate-400" />
            <span data-testid="dealer-detail-email">{identity.email}</span>
            {identity.email_verified && <Badge className="bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px]">verified</Badge>}
          </div>
          <div className="flex items-center gap-2 text-slate-700">
            <Phone className="h-4 w-4 text-slate-400" />
            <span>{identity.phone || '—'}</span>
            {identity.phone_verified && <Badge className="bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px]">verified</Badge>}
          </div>
          <div className="flex items-center gap-2 text-slate-700">
            <MapPin className="h-4 w-4 text-slate-400" />
            {identity.province || '—'}{identity.address ? ` · ${identity.address}` : ''}
          </div>
          <div className="flex items-center gap-2 text-slate-700">
            <Calendar className="h-4 w-4 text-slate-400" />
            Registered {fmtDate(identity.created_at)}
          </div>
          <div className="flex items-center gap-2 text-slate-700 md:col-span-2">
            <Clock className="h-4 w-4 text-slate-400" />
            Last login {fmtDate(identity.last_login_at)}
          </div>
          {suspended && (
            <div className="md:col-span-2 mt-1 p-2 rounded bg-orange-50 border border-orange-200 text-sm text-orange-800">
              <ShieldAlert className="h-4 w-4 inline mr-1" />
              <strong>Suspended</strong> on {fmtDate(status.suspended_at)}
              {status.suspended_reason ? ` — ${status.suspended_reason}` : ''}
            </div>
          )}
        </CardContent>
      </Card>

      {/* License / registration */}
      {dealer_registration && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">Dealer Registration</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-y-2 gap-x-6 text-sm" data-testid="dealer-registration-section">
            <div><span className="text-slate-500">Business:</span> <span className="font-medium">{dealer_registration.business_name || '—'}</span></div>
            <div><span className="text-slate-500">Seller type:</span> <span className="font-medium capitalize">{dealer_registration.seller_type || '—'}</span></div>
            <div><span className="text-slate-500">License #:</span> <span className="font-mono">{dealer_registration.license_number || '—'}</span></div>
            <div><span className="text-slate-500">License province:</span> <span className="font-medium">{dealer_registration.license_province || '—'}</span></div>
            <div><span className="text-slate-500">License expiry:</span> <span className="font-medium">{fmtDate(dealer_registration.license_expiry)}</span></div>
            <div><span className="text-slate-500">Tax ID:</span> <span className="font-mono">{dealer_registration.tax_id || '—'}</span></div>
            <div><span className="text-slate-500">Business phone:</span> <span>{dealer_registration.business_phone || '—'}</span></div>
            <div><span className="text-slate-500">Business address:</span> <span>{dealer_registration.business_address || '—'}</span></div>
            {dealer_registration.website && (
              <div className="md:col-span-2">
                <span className="text-slate-500">Website:</span>{' '}
                <a href={dealer_registration.website} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline inline-flex items-center gap-1">
                  {dealer_registration.website} <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
            {dealer_registration.rejection_reason && (
              <div className="md:col-span-2 text-rose-700 bg-rose-50 border border-rose-200 rounded p-2">
                <strong>Rejection reason:</strong> {dealer_registration.rejection_reason}
              </div>
            )}
          </CardContent>
        </Card>
      )}
      {broker_registration && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">Broker Registration</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-y-2 gap-x-6 text-sm" data-testid="broker-registration-section">
            <div><span className="text-slate-500">Legal name:</span> <span className="font-medium">{broker_registration.legal_business_name || '—'}</span></div>
            <div><span className="text-slate-500">Operating province:</span> <span className="font-medium">{broker_registration.operating_province || '—'}</span></div>
            <div><span className="text-slate-500">Regulatory body:</span> <span className="font-medium">{broker_registration.regulatory_body || '—'}</span></div>
            <div><span className="text-slate-500">Permit type:</span> <span className="font-medium capitalize">{broker_registration.permit_type || '—'}</span></div>
            <div><span className="text-slate-500">Broker license #:</span> <span className="font-mono">{broker_registration.broker_license_number || '—'}</span></div>
            <div><span className="text-slate-500">Corp registration #:</span> <span className="font-mono">{broker_registration.corporate_registration_number || '—'}</span></div>
            <div><span className="text-slate-500">Default deposit:</span> <span className="font-medium">{fmtCurrency(broker_registration.default_deposit_amount_cad)}</span></div>
            <div><span className="text-slate-500">Verified:</span> <span>{fmtDate(broker_registration.verified_at)}</span></div>
          </CardContent>
        </Card>
      )}

      {/* Documents */}
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">Verification Documents ({documents?.length || 0})</CardTitle></CardHeader>
        <CardContent data-testid="dealer-documents-section">
          {(!documents || documents.length === 0) ? (
            <p className="text-sm text-slate-500 italic">No verification documents on file.</p>
          ) : (
            <ul className="space-y-2">
              {documents.map((d, i) => (
                <li key={d.id || `${d.document_type}-${i}`}
                    className="flex items-center justify-between border border-slate-200 rounded p-2"
                    data-testid={`dealer-document-${i}`}>
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-slate-500" />
                    <div>
                      <div className="text-sm font-medium capitalize">{(d.document_type || 'document').replace(/_/g, ' ')}</div>
                      <div className="text-xs text-slate-500">
                        {d.file_name || d.file_url || 'no file'}
                        {d.uploaded_at ? ` · uploaded ${fmtDate(d.uploaded_at)}` : ''}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={d.status} />
                    {d.file_url && (
                      <a href={d.file_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-xs inline-flex items-center gap-1">
                        Open <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Activity history */}
      {activity && (
        <>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">Activity Summary</CardTitle></CardHeader>
            <CardContent data-testid="dealer-activity-summary">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div className="p-3 rounded bg-slate-50">
                  <div className="text-[10px] uppercase text-slate-500 mb-1"><Gavel className="h-3 w-3 inline mr-1" /> Auctions</div>
                  <div className="text-lg font-bold">{activity.summary.auctions_created}</div>
                  <div className="text-[11px] text-slate-500">
                    {activity.summary.single_vehicle_listings} single · {activity.summary.multi_lot_events} multi-lot
                  </div>
                </div>
                <div className="p-3 rounded bg-slate-50">
                  <div className="text-[10px] uppercase text-slate-500 mb-1"><Package className="h-3 w-3 inline mr-1" /> Vehicles Sold</div>
                  <div className="text-lg font-bold">{activity.summary.vehicles_sold}</div>
                </div>
                <div className="p-3 rounded bg-slate-50">
                  <div className="text-[10px] uppercase text-slate-500 mb-1"><DollarSign className="h-3 w-3 inline mr-1" /> Gross Hammer</div>
                  <div className="text-lg font-bold">{fmtCurrency(activity.summary.gross_hammer_cad)}</div>
                </div>
                <div className="p-3 rounded bg-slate-50">
                  <div className="text-[10px] uppercase text-slate-500 mb-1"><Users className="h-3 w-3 inline mr-1" /> Buyer Reach</div>
                  <div className="text-lg font-bold">{activity.summary.unique_buyers}</div>
                  <div className="text-[11px] text-slate-500">{activity.summary.total_bids_received} bids received</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Single vehicle listings */}
          {activity.single_listings?.length > 0 && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><Car className="h-4 w-4" /> Single-Vehicle Listings</CardTitle></CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="dealer-single-listings-table">
                    <thead className="bg-slate-50 text-left">
                      <tr>
                        <th className="p-2">Title</th>
                        <th className="p-2">Status</th>
                        <th className="p-2 text-right">Current bid</th>
                        <th className="p-2 text-right">Final price</th>
                        <th className="p-2 text-right">Bids</th>
                        <th className="p-2">Buyer</th>
                        <th className="p-2">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activity.single_listings.map((v) => (
                        <tr key={v.listing_id} className="border-t"
                            data-testid={`dealer-listing-row-${v.listing_id}`}>
                          <td className="p-2 max-w-[240px] truncate">{v.title || v.listing_id}</td>
                          <td className="p-2"><StatusBadge status={v.status} /></td>
                          <td className="p-2 text-right">{fmtCurrency(v.current_bid)}</td>
                          <td className="p-2 text-right">{v.final_price ? fmtCurrency(v.final_price) : '—'}</td>
                          <td className="p-2 text-right">{v.bid_count}</td>
                          <td className="p-2 font-mono text-xs">{v.buyer_id ? v.buyer_id.slice(0, 8) + '…' : '—'}</td>
                          <td className="p-2">{fmtDate(v.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Multi-lot events */}
          {activity.multi_lot_events?.length > 0 && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><Package className="h-4 w-4" /> Multi-Lot Events</CardTitle></CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="dealer-multi-lot-table">
                    <thead className="bg-slate-50 text-left">
                      <tr>
                        <th className="p-2">Title</th>
                        <th className="p-2">Status</th>
                        <th className="p-2 text-right">Lots</th>
                        <th className="p-2 text-right">Sold lots</th>
                        <th className="p-2 text-right">Gross hammer</th>
                        <th className="p-2">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activity.multi_lot_events.map((e) => (
                        <tr key={e.event_id} className="border-t"
                            data-testid={`dealer-event-row-${e.event_id}`}>
                          <td className="p-2 max-w-[240px] truncate">{e.title || e.event_id}</td>
                          <td className="p-2"><StatusBadge status={e.status} /></td>
                          <td className="p-2 text-right">{e.lot_count}</td>
                          <td className="p-2 text-right">{e.sold_lot_count}</td>
                          <td className="p-2 text-right">{fmtCurrency(e.gross_hammer)}</td>
                          <td className="p-2">{fmtDate(e.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Recent buyer bids */}
          {activity.recent_bids?.length > 0 && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><Users className="h-4 w-4" /> Recent Buyer Interactions</CardTitle></CardHeader>
              <CardContent>
                <ul className="divide-y" data-testid="dealer-recent-bids-list">
                  {activity.recent_bids.map((b, idx) => (
                    <li key={`${b.vehicle_id}-${b.created_at}-${idx}`} className="py-2 flex items-center justify-between text-sm">
                      <div>
                        <span className="font-mono text-xs">{(b.bidder_id || '—').slice(0, 8)}…</span>
                        <span className="text-slate-500 mx-2">on</span>
                        <span className="font-mono text-xs">{(b.vehicle_id || '').slice(0, 8)}…</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge status={b.status} />
                        <span className="font-semibold text-emerald-700">{fmtCurrency(b.amount)}</span>
                        <span className="text-xs text-slate-500">{fmtDate(b.created_at)}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

// ── Main page ────────────────────────────────────────────────────────
export default function AdminVehicleDealersPage() {
  const [status, setStatus] = useState('all');
  const [kind, setKind] = useState('all');
  const [search, setSearch] = useState('');
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status !== 'all') params.set('status', status);
      if (kind !== 'all') params.set('kind', kind);
      if (search.trim()) params.set('search', search.trim());
      const r = await axios.get(
        `${API_BASE}/admin/vehicle-dealers?${params.toString()}`,
        { headers: _authHeaders() },
      );
      setRows(r.data?.data || []);
      setTotal(r.data?.total || 0);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load dealers');
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [status, kind, search]);

  useEffect(() => { load(); }, [load]);

  const runQuickAction = async (userId, verb, e) => {
    e?.stopPropagation();
    let body = {};
    if (verb === 'suspend') {
      const reason = window.prompt('Reason for suspension (optional):') || '';
      body = { reason };
    }
    try {
      await axios.post(
        `${API_BASE}/admin/vehicle-dealers/${userId}/${verb}`,
        body,
        { headers: _authHeaders() },
      );
      toast.success(`Dealer ${verb}d`);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || `Failed to ${verb}`);
    }
  };

  const statusCounts = useMemo(() => {
    const counts = { all: 0, pending: 0, approved: 0, suspended: 0, rejected: 0 };
    // Only accurate when the "all" filter is active — otherwise counts show the filtered subset.
    rows.forEach((r) => {
      counts.all += 1;
      const k = r.verification_status;
      if (k in counts) counts[k] += 1;
    });
    return counts;
  }, [rows]);

  if (selectedUserId) {
    return (
      <DealerDetailPanel
        userId={selectedUserId}
        onBack={() => setSelectedUserId(null)}
        onActionCompleted={load}
      />
    );
  }

  return (
    <div className="space-y-4" data-testid="admin-vehicle-dealers-page">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-emerald-600" />
            Vehicle Dealer & Broker Management
            <Badge variant="outline" className="ml-2">{total}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-wrap gap-2 mb-4">
            {STATUS_FILTERS.map((f) => {
              const Icon = f.icon;
              const active = status === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setStatus(f.id)}
                  className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium border transition ${
                    active ? 'bg-slate-900 text-white border-slate-900' : `${f.color} border-transparent hover:brightness-95`
                  }`}
                  data-testid={`filter-status-${f.id}`}
                >
                  <Icon className="h-3.5 w-3.5" /> {f.label}
                  {status === 'all' && (
                    <span className="ml-1 text-[11px] opacity-70">{statusCounts[f.id] || 0}</span>
                  )}
                </button>
              );
            })}
            <div className="mx-2 border-l h-6 self-center" />
            {KIND_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setKind(f.id)}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium border transition ${
                  kind === f.id ? 'bg-blue-600 text-white border-blue-600' : 'bg-slate-100 text-slate-700 border-transparent hover:bg-slate-200'
                }`}
                data-testid={`filter-kind-${f.id}`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="flex items-center gap-2 mb-4">
            <div className="relative flex-1 max-w-md">
              <Search className="h-4 w-4 text-slate-400 absolute left-2 top-1/2 -translate-y-1/2" />
              <Input
                type="search"
                placeholder="Search by name, email, business, license…"
                className="pl-8"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                data-testid="dealer-search-input"
              />
            </div>
            <Button variant="outline" size="sm" onClick={load} data-testid="dealer-refresh-btn">
              <RefreshCw className="h-4 w-4 mr-1" /> Refresh
            </Button>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="dealer-list-table">
              <thead className="bg-slate-50 text-left border-b">
                <tr>
                  <th className="p-2">Name / Business</th>
                  <th className="p-2">Email</th>
                  <th className="p-2">Kind</th>
                  <th className="p-2">Status</th>
                  <th className="p-2">License</th>
                  <th className="p-2">Registered</th>
                  <th className="p-2 text-right">Quick actions</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr><td colSpan={7} className="p-8 text-center text-slate-500">
                    <RefreshCw className="h-5 w-5 mx-auto animate-spin mb-1" /> Loading…
                  </td></tr>
                )}
                {!loading && rows.length === 0 && (
                  <tr><td colSpan={7} className="p-8 text-center text-slate-500 italic">
                    No dealers or brokers match these filters.
                  </td></tr>
                )}
                {!loading && rows.map((r) => (
                  <tr
                    key={r.user_id}
                    className="border-b hover:bg-blue-50/40 cursor-pointer transition"
                    onClick={() => setSelectedUserId(r.user_id)}
                    data-testid={`dealer-row-${r.user_id}`}
                  >
                    <td className="p-2">
                      <div className="font-medium">{r.name || '—'}</div>
                      <div className="text-xs text-slate-500">{r.business_name || '—'}</div>
                    </td>
                    <td className="p-2 text-slate-700">{r.email}</td>
                    <td className="p-2">
                      <Badge variant="outline" className="capitalize inline-flex items-center gap-1">
                        {r.kind === 'broker' ? <Handshake className="h-3 w-3" /> : <Building2 className="h-3 w-3" />}
                        {r.kind}
                      </Badge>
                    </td>
                    <td className="p-2"><StatusBadge status={r.verification_status} /></td>
                    <td className="p-2">
                      <div className="font-mono text-xs">{r.license_number || '—'}</div>
                      <div className="text-[10px] text-slate-500">{r.license_province || ''}</div>
                    </td>
                    <td className="p-2 text-slate-600">{fmtDate(r.registered_at)}</td>
                    <td className="p-2 text-right">
                      <div className="inline-flex items-center gap-1">
                        {r.verification_status !== 'approved' && !r.suspended && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-emerald-300 text-emerald-700 hover:bg-emerald-50 h-7 px-2"
                            onClick={(e) => runQuickAction(r.user_id, 'approve', e)}
                            data-testid={`quick-approve-${r.user_id}`}
                          >
                            <CheckCircle className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        {!r.suspended && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-orange-300 text-orange-700 hover:bg-orange-50 h-7 px-2"
                            onClick={(e) => runQuickAction(r.user_id, 'suspend', e)}
                            data-testid={`quick-suspend-${r.user_id}`}
                          >
                            <Ban className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        {r.suspended && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-blue-300 text-blue-700 hover:bg-blue-50 h-7 px-2"
                            onClick={(e) => runQuickAction(r.user_id, 'reinstate', e)}
                            data-testid={`quick-reinstate-${r.user_id}`}
                          >
                            <Play className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
