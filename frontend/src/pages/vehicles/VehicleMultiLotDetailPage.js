import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import {
  Layers, Car, Gavel, Loader2, Clock, BellRing, Trophy,
  Lock, Unlock, ChevronDown, ChevronUp, History, ShieldAlert, Shield,
} from 'lucide-react';
import { toast } from 'sonner';
import UpcomingCountdownBadge from '../../components/UpcomingCountdownBadge';
import { getTimingModeShortLabel } from '../../lib/vehicleMultiLotTimingModes';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * VehicleMultiLotDetailPage — iter293 Directive 2 / iter295 P0+P1 addendum
 *
 * Adds (iter295):
 *   • 403 broker_required handling (province-gated buyer restriction)
 *   • 402 deposit_required → per-lot deposit modal
 *   • Per-lot Bid History (collapsible "Last 10 bids" panel)
 *   • Lot Queue deposit-lock icon
 */
const fmtCurrency = (n) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(n || 0);

const StatusBadge = ({ status }) => {
  const styles = {
    draft:     'bg-gray-100 text-gray-700 border-gray-300',
    upcoming:  'bg-blue-100 text-blue-700 border-blue-300',
    live:      'bg-green-100 text-green-700 border-green-300',
    ended:     'bg-orange-100 text-orange-700 border-orange-300',
    sold:      'bg-purple-100 text-purple-700 border-purple-300',
    cancelled: 'bg-red-100 text-red-700 border-red-300',
  };
  return (
    <Badge className={`${styles[status] || styles.upcoming} border`} data-testid={`status-badge-${status}`}>
      {status.toUpperCase()}
    </Badge>
  );
};

// ── iter295 P1 — Bid History (collapsible per lot) ─────────────────────
const BidHistoryPanel = ({ eventId, lot }) => {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/vehicle-multi-lot-auctions/${eventId}/lots/${lot.id}/bid-history`);
      setRows(r.data?.data || []);
    } catch (e) {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [eventId, lot.id]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !rows) loadHistory();
  };

  return (
    <div className="mt-2 border-t pt-2" data-testid={`bid-history-panel-${lot.lot_number}`}>
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center justify-between text-xs font-medium text-slate-600 hover:text-slate-900"
        data-testid={`bid-history-toggle-${lot.lot_number}`}
      >
        <span className="inline-flex items-center gap-1">
          <History className="h-3.5 w-3.5" />
          Bid History
          {typeof lot.bid_count === 'number' && lot.bid_count > 0 && (
            <span className="ml-1 px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 text-[10px] font-semibold">
              {lot.bid_count}
            </span>
          )}
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
      {open && (
        <div className="mt-2" data-testid={`bid-history-rows-${lot.lot_number}`}>
          {loading && (
            <div className="text-xs text-slate-500 flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" /> Loading…
            </div>
          )}
          {!loading && rows && rows.length === 0 && (
            <div className="text-xs text-slate-500 italic">No bids yet on this lot.</div>
          )}
          {!loading && rows && rows.length > 0 && (
            <ul className="space-y-1">
              {rows.map((b) => (
                <li
                  key={b.bid_id}
                  className="flex items-center justify-between text-xs bg-slate-50 rounded px-2 py-1"
                  data-testid={`bid-history-row-${lot.lot_number}-${b.bid_id}`}
                >
                  <span className="text-slate-700">{b.alias}</span>
                  <span className="font-semibold text-emerald-700">{fmtCurrency(b.amount)}</span>
                  <span className="text-slate-500">
                    {b.created_at ? new Date(b.created_at).toLocaleTimeString() : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

const VehicleMultiLotDetailPage = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bidAmount, setBidAmount] = useState('');
  const [placing, setPlacing] = useState(false);
  const [activeLotOverride, setActiveLotOverride] = useState(null);
  const [notifying, setNotifying] = useState(false);

  // iter295 — deposit modal state
  const [depositModal, setDepositModal] = useState(null); // { lotId, amount, lotNumber, lotTitle }
  const [payingDeposit, setPayingDeposit] = useState(false);
  // iter295 — deposit-lock map: { [lot_id]: true/false }
  const [depositMap, setDepositMap] = useState({});

  const refresh = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/vehicle-multi-lot-auctions/${eventId}`);
      setEvent(r.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    let cancelled = false;
    let timer;
    const runner = async () => {
      if (cancelled) return;
      try {
        const r = await axios.get(`${API}/vehicle-multi-lot-auctions/${eventId}`);
        if (cancelled) return;
        setEvent(r.data);
      } catch (e) {
        console.error(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    runner();
    timer = setInterval(runner, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [eventId]);

  // iter295 — Pre-load per-lot deposit lock state for the logged-in buyer.
  // Best-effort: anonymous users skip silently. The fetch happens inside
  // a top-level useEffect (not exported) so React Compiler's
  // set-state-in-effect rule sees the state update as initialization.
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token || !event?.lots?.length) return;
    let cancelled = false;
    (async () => {
      try {
        const results = await Promise.all(
          event.lots.map((lt) =>
            axios.get(
              `${API}/vehicle-multi-lot-auctions/${event.id}/lots/${lt.id}/my-deposit`,
              { headers: { Authorization: `Bearer ${token}` } },
            ).then((r) => [lt.id, !!r.data?.has_deposit]).catch(() => [lt.id, false]),
          ),
        );
        if (cancelled) return;
        const map = {};
        results.forEach(([id, has]) => { map[id] = has; });
        setDepositMap(map);
      } catch {
        /* silent */
      }
    })();
    return () => { cancelled = true; };
  }, [event]);

  let activeLotId = null;
  if (activeLotOverride) {
    activeLotId = activeLotOverride;
  } else if (event?.lots?.length) {
    const live = event.lots.find((l) => l.status === 'live');
    const upcoming = event.lots.find((l) => l.status === 'upcoming');
    activeLotId = live?.id || upcoming?.id || event.lots[0].id;
  }

  const activeLot = event?.lots?.find((l) => l.id === activeLotId) || null;

  const payDeposit = async () => {
    if (!depositModal) return;
    setPayingDeposit(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API}/vehicle-multi-lot-auctions/${event.id}/lots/${depositModal.lotId}/deposit`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Deposit paid — you can now bid on this lot.');
      setDepositMap((m) => ({ ...m, [depositModal.lotId]: true }));
      setDepositModal(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Deposit payment failed');
    } finally {
      setPayingDeposit(false);
    }
  };

  const handleBid = async () => {
    if (!activeLot) return;
    const amt = Number(bidAmount);
    if (!amt || amt <= 0) { toast.error('Enter a bid amount'); return; }
    setPlacing(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API}/vehicle-multi-lot-auctions/${event.id}/lots/${activeLot.id}/bid`,
        { event_id: event.id, lot_id: activeLot.id, amount: amt },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Bid placed!');
      setBidAmount('');
      refresh();
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;

      // iter295 P1 — 402 deposit_required → open per-lot deposit modal
      if (status === 402 && detail?.code === 'deposit_required') {
        setDepositModal({
          lotId:     detail.lot_id || activeLot.id,
          amount:    Number(detail.deposit_amount) || 200,
          lotNumber: detail.lot_number || activeLot.lot_number,
          lotTitle:  detail.lot_title || activeLot.title,
        });
        toast.message(detail.message_en || 'Refundable deposit required.');
      }
      // iter295 P0 — 403 broker_required → province-gate toast + nav to broker directory
      else if (status === 403 && detail?.code === 'broker_required') {
        toast.error(
          detail.message_en || 'A licensed broker is required to bid in your province.',
          {
            action: {
              label: 'Find a broker',
              onClick: () => navigate(detail.action_url || '/brokers'),
            },
          },
        );
      }
      else {
        toast.error(typeof detail === 'string' ? detail : (detail?.message_en || 'Bid failed'));
      }
    } finally {
      setPlacing(false);
    }
  };

  const handleNotify = async () => {
    setNotifying(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API}/upcoming-notify/subscribe`, {
        listing_id: event.id,
        listing_type: 'vehicle_multi_lot',
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success('We\u2019ll email you when bidding opens!');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Subscription failed — login required');
    } finally {
      setNotifying(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center"><Loader2 className="h-8 w-8 animate-spin mx-auto" /></div>;
  }
  if (!event) {
    return <div className="p-8 text-center text-gray-600">Event not found.</div>;
  }

  const lots = event.lots || [];
  const minBid = activeLot
    ? (Number(activeLot.current_bid) > 0
      ? Number(activeLot.current_bid) + Number(activeLot.bid_increment || 100)
      : Number(activeLot.starting_price))
    : 0;

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6" data-testid="multi-lot-detail-page">
      {/* Header */}
      <Card className="p-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <Layers className="h-5 w-5 text-blue-600" />
              <h1 className="text-2xl sm:text-3xl font-bold">{event.title}</h1>
              <StatusBadge status={event.status} />
              <Badge variant="outline" className="border-blue-300 text-blue-700">
                {getTimingModeShortLabel(event.timing_mode)}
              </Badge>
            </div>
            <p className="text-sm text-gray-600">
              {lots.length} lot{lots.length === 1 ? '' : 's'} · Event starts {new Date(event.start_time).toLocaleString()}
            </p>
            {event.description && <p className="mt-2 text-gray-700">{event.description}</p>}
          </div>
          {event.status === 'upcoming' && (
            <div className="flex flex-col items-end gap-2">
              <UpcomingCountdownBadge startTime={event.start_time} onLive={refresh} />
              <Button onClick={handleNotify} disabled={notifying} variant="outline" size="sm" data-testid="notify-btn">
                {notifying ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <BellRing className="h-4 w-4 mr-1" />}
                Notify me when live
              </Button>
            </div>
          )}
        </div>
      </Card>

      {/* Active Lot */}
      {activeLot && (
        <Card className="p-6 border-blue-200 bg-gradient-to-r from-white to-blue-50" data-testid="active-lot-card">
          <div className="flex flex-col lg:flex-row gap-4 justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <Car className="h-5 w-5 text-blue-600" />
                <h2 className="text-xl font-semibold">Lot #{activeLot.lot_number} — {activeLot.title}</h2>
                <StatusBadge status={activeLot.status} />
                {activeLot.reserve_price > 0 && (
                  Number(activeLot.current_bid) >= Number(activeLot.reserve_price) ? (
                    <Badge data-testid="reserve-met-badge"
                      className="bg-green-100 text-green-800 border border-green-300">
                      ✓ Reserve Met
                    </Badge>
                  ) : (
                    <Badge data-testid="reserve-not-met-badge"
                      className="bg-slate-100 text-slate-600 border border-slate-300">
                      Reserve Not Met
                    </Badge>
                  )
                )}
                {/* iter295 — deposit lock icon on active lot */}
                {activeLot.status === 'live' && (
                  depositMap[activeLot.id]
                    ? <Badge className="bg-emerald-50 text-emerald-800 border border-emerald-200 inline-flex items-center gap-1"
                        data-testid="active-lot-deposit-unlocked">
                        <Unlock className="h-3 w-3" /> Bid-Enabled
                      </Badge>
                    : <Badge className="bg-amber-50 text-amber-800 border border-amber-200 inline-flex items-center gap-1"
                        data-testid="active-lot-deposit-locked">
                        <Lock className="h-3 w-3" /> Deposit Required
                      </Badge>
                )}
              </div>
              <p className="text-sm text-gray-700">
                {activeLot.year} {activeLot.make} {activeLot.model} · {activeLot.mileage?.toLocaleString()} km · {activeLot.location_city}, {activeLot.location_province}
              </p>
              <div className="grid grid-cols-2 gap-2 mt-3 text-sm">
                <div><span className="text-gray-500">Starting:</span> <span className="font-medium">{fmtCurrency(activeLot.starting_price)}</span></div>
                <div><span className="text-gray-500">Current Bid:</span> <span className="font-bold text-green-700">{fmtCurrency(activeLot.current_bid)}</span></div>
                <div><span className="text-gray-500">Bids:</span> <span className="font-medium">{activeLot.bid_count || 0}</span></div>
                <div><span className="text-gray-500">VIN:</span> <span className="font-mono text-xs">{activeLot.vin}</span></div>
              </div>
              {activeLot.description && <p className="mt-2 text-sm text-gray-600">{activeLot.description}</p>}

              {/* iter295 P1 — Active-lot bid history */}
              <BidHistoryPanel eventId={event.id} lot={activeLot} />
            </div>

            {/* Bid panel */}
            <div className="lg:w-80 space-y-3">
              {activeLot.status === 'upcoming' && (
                <UpcomingCountdownBadge startTime={activeLot.start_time} onLive={refresh} />
              )}
              {activeLot.status === 'live' && activeLot.end_time && (
                <div className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                  <Clock className="h-4 w-4" />
                  Ends {new Date(activeLot.end_time).toLocaleTimeString()}
                </div>
              )}
              {activeLot.status === 'live' && (
                <div className="space-y-2">
                  <Input
                    type="number"
                    placeholder={`Min ${fmtCurrency(minBid)}`}
                    value={bidAmount}
                    onChange={(e) => setBidAmount(e.target.value)}
                    data-testid="bid-amount-input"
                  />
                  <Button onClick={handleBid} disabled={placing} className="w-full bg-green-600 hover:bg-green-700" data-testid="place-bid-btn">
                    {placing ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Gavel className="h-4 w-4 mr-1" />}
                    Place Bid
                  </Button>
                  <p className="text-xs text-gray-500 text-center">2-min soft-close active — late bids extend the lot.</p>
                </div>
              )}
              {(activeLot.status === 'ended' || activeLot.status === 'sold') && (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg text-center">
                  <Trophy className="h-5 w-5 mx-auto text-purple-600 mb-1" />
                  <p className="text-sm font-semibold text-purple-800">
                    Lot {activeLot.status === 'sold' ? 'SOLD' : 'CLOSED'} at {fmtCurrency(activeLot.current_bid)}
                  </p>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Lot queue */}
      <Card className="p-4 sm:p-6">
        <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Layers className="h-5 w-5" /> Lot Queue ({lots.length})
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="lot-queue-table">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="p-2">#</th>
                <th className="p-2">Vehicle</th>
                <th className="p-2">Status</th>
                <th className="p-2">Current Bid</th>
                <th className="p-2">Bids</th>
                <th className="p-2">Access</th>
                <th className="p-2"></th>
              </tr>
            </thead>
            <tbody>
              {lots.map((lot) => (
                <React.Fragment key={lot.id}>
                  <tr
                    className={`border-t ${lot.id === activeLotId ? 'bg-blue-50' : ''}`}
                    data-testid={`lot-row-${lot.lot_number}`}
                  >
                    <td className="p-2 font-medium">{lot.lot_number}</td>
                    <td className="p-2">{lot.year} {lot.make} {lot.model}</td>
                    <td className="p-2"><StatusBadge status={lot.status} /></td>
                    <td className="p-2">{fmtCurrency(lot.current_bid)}</td>
                    <td className="p-2">{lot.bid_count || 0}</td>
                    <td className="p-2">
                      {depositMap[lot.id] ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700" data-testid={`lot-deposit-ok-${lot.lot_number}`}>
                          <Unlock className="h-3.5 w-3.5" /> Bid-ready
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-amber-700" data-testid={`lot-deposit-locked-${lot.lot_number}`}>
                          <Lock className="h-3.5 w-3.5" /> Deposit
                        </span>
                      )}
                    </td>
                    <td className="p-2">
                      <Button size="sm" variant="ghost" onClick={() => setActiveLotOverride(lot.id)} data-testid={`view-lot-${lot.lot_number}`}>
                        View
                      </Button>
                    </td>
                  </tr>
                  {/* iter295 — Bid history sub-row */}
                  <tr className="border-t bg-slate-50/60">
                    <td colSpan={7} className="px-4 py-1">
                      <BidHistoryPanel eventId={event.id} lot={lot} />
                    </td>
                  </tr>
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* iter295 P1 — Per-lot deposit modal (triggered by 402) */}
      {depositModal && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          data-testid="lot-deposit-modal"
          onClick={() => !payingDeposit && setDepositModal(null)}
        >
          <div
            className="bg-white rounded-lg p-6 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3">
              <ShieldAlert className="h-5 w-5 text-amber-600" />
              <h3 className="text-lg font-semibold">Refundable Deposit Required</h3>
            </div>
            <p className="text-sm text-slate-600 mb-3">
              To bid on <strong>Lot #{depositModal.lotNumber} — {depositModal.lotTitle}</strong>,
              a refundable deposit of <strong>{fmtCurrency(depositModal.amount)}</strong> is required.
              It is fully refunded if you do not win this lot.
            </p>
            <div className="bg-blue-50 border border-blue-100 rounded p-3 text-xs text-blue-900 mb-4 inline-flex items-start gap-2">
              <Shield className="h-4 w-4 mt-0.5 shrink-0" />
              <span>The deposit applies only to this lot — bidding on another lot requires a separate deposit.</span>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setDepositModal(null)}
                disabled={payingDeposit}
                data-testid="lot-deposit-cancel-btn"
              >
                Cancel
              </Button>
              <Button
                onClick={payDeposit}
                disabled={payingDeposit}
                className="bg-blue-600 hover:bg-blue-700"
                data-testid="lot-deposit-confirm-btn"
              >
                {payingDeposit
                  ? <Loader2 className="h-4 w-4 animate-spin mr-1" />
                  : <Shield className="h-4 w-4 mr-1" />}
                Pay {fmtCurrency(depositModal.amount)} deposit
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VehicleMultiLotDetailPage;
