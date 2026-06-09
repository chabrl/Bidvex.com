import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Layers, Car, Gavel, Loader2, Clock, CheckCircle, BellRing, Trophy } from 'lucide-react';
import { toast } from 'sonner';
import UpcomingCountdownBadge from '../../components/UpcomingCountdownBadge';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * VehicleMultiLotDetailPage — iter293 Directive 2
 *
 * Shows:
 *   • Event header (title, dealer, timing mode, status)
 *   • Active lot card with bid panel (current bid, increment, countdown)
 *   • Lot queue table (status per lot, winner per lot)
 *
 * Polls /api/vehicle-multi-lot-auctions/{id} every 5s so lot transitions
 * driven by the backend scheduler appear without a manual refresh.
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

const VehicleMultiLotDetailPage = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bidAmount, setBidAmount] = useState('');
  const [placing, setPlacing] = useState(false);
  const [activeLotId, setActiveLotId] = useState(null);
  const [notifying, setNotifying] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/vehicle-multi-lot-auctions/${eventId}`);
      setEvent(r.data);
      if (!activeLotId && r.data?.lots?.length) {
        // Pick the LIVE lot, fall back to the first UPCOMING.
        const live = r.data.lots.find(l => l.status === 'live');
        const upcoming = r.data.lots.find(l => l.status === 'upcoming');
        setActiveLotId(live?.id || upcoming?.id || r.data.lots[0].id);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [eventId, activeLotId]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  const activeLot = event?.lots?.find(l => l.id === activeLotId) || null;

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
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : detail?.message_en || 'Bid failed');
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
                {event.timing_mode === 'sequential' ? 'Copart Sequential' : 'Staggered'}
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
              <div className="flex items-center gap-2 mb-1">
                <Car className="h-5 w-5 text-blue-600" />
                <h2 className="text-xl font-semibold">Lot #{activeLot.lot_number} — {activeLot.title}</h2>
                <StatusBadge status={activeLot.status} />
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
                    onChange={e => setBidAmount(e.target.value)}
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
                <th className="p-2"></th>
              </tr>
            </thead>
            <tbody>
              {lots.map(lot => (
                <tr
                  key={lot.id}
                  className={`border-t ${lot.id === activeLotId ? 'bg-blue-50' : ''}`}
                  data-testid={`lot-row-${lot.lot_number}`}
                >
                  <td className="p-2 font-medium">{lot.lot_number}</td>
                  <td className="p-2">{lot.year} {lot.make} {lot.model}</td>
                  <td className="p-2"><StatusBadge status={lot.status} /></td>
                  <td className="p-2">{fmtCurrency(lot.current_bid)}</td>
                  <td className="p-2">{lot.bid_count || 0}</td>
                  <td className="p-2">
                    <Button size="sm" variant="ghost" onClick={() => setActiveLotId(lot.id)} data-testid={`view-lot-${lot.lot_number}`}>
                      View
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default VehicleMultiLotDetailPage;
