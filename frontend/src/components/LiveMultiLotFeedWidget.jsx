import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Layers, ChevronRight, Clock, Radio } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * LiveMultiLotFeedWidget — iter294 P1
 *
 * Sidebar/banner widget that streams the currently-LIVE multi-lot
 * vehicle auction events on the public Vehicle Auctions homepage.
 *
 *  • Polls /api/vehicle-multi-lot-auctions every 10s — NO websocket.
 *  • Each entry: event title, active lot title + lot number, time
 *    remaining on the active lot, total lots remaining.
 *  • Click → /vehicle-multi-lot/{eventId}.
 *  • Falls back to UPCOMING events if no LIVE ones are running.
 *  • Renders `null` (nothing) when there are neither LIVE nor UPCOMING
 *    multi-lot events — keeps the homepage clean.
 */
const _fmtRemaining = (endTime) => {
  if (!endTime) return null;
  const secs = Math.max(0, (new Date(endTime).getTime() - Date.now()) / 1000);
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};

const LiveMultiLotFeedWidget = () => {
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [now, setNow] = useState(Date.now());

  const refresh = useCallback(async () => {
    try {
      // Pull LIVE events first; if none, fall back to UPCOMING (limit 5).
      const [liveRes, upRes] = await Promise.all([
        axios.get(`${API}/vehicle-multi-lot-auctions?status=live&limit=5`),
        axios.get(`${API}/vehicle-multi-lot-auctions?status=upcoming&limit=5`),
      ]);
      const live = liveRes.data?.data || [];
      const upcoming = upRes.data?.data || [];
      setEvents(live.length ? live : upcoming);
    } catch (_e) {
      setEvents([]);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10_000);
    return () => clearInterval(id);
  }, [refresh]);

  // 1s tick to refresh `time remaining` strings.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // iter294 P1 — Hide entirely when nothing is live AND nothing is upcoming.
  if (!events.length) return null;
  // Reference the 1s tick so the `time remaining` strings re-render
  // every second without spurious React warnings.
  void now;

  const isLive = events[0]?.status === 'live';

  return (
    <Card
      className="p-4 bg-gradient-to-br from-slate-50 to-white border border-slate-200"
      data-testid="live-multi-lot-feed-widget"
    >
      <div className="flex items-center gap-2 mb-3">
        {isLive ? (
          <>
            <Radio className="h-4 w-4 text-red-600 animate-pulse" />
            <h3 className="font-semibold text-sm">🔴 Live Auctions</h3>
          </>
        ) : (
          <>
            <Clock className="h-4 w-4 text-blue-600" />
            <h3 className="font-semibold text-sm">Upcoming Auctions</h3>
          </>
        )}
        <Badge variant="outline" className="ml-auto text-[10px]">
          {events.length}
        </Badge>
      </div>
      <ul className="space-y-2">
        {events.map(ev => {
          const lots = ev.lots || [];
          const activeIdx = ev.current_active_lot_index ?? 0;
          const activeLot = lots[activeIdx] || lots[0];
          const remainingLots = lots.filter(l => l.status === 'upcoming' || l.status === 'live').length;
          return (
            <li
              key={ev.id}
              onClick={() => navigate(`/vehicle-multi-lot/${ev.id}`)}
              onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/vehicle-multi-lot/${ev.id}`); }}
              role="button"
              tabIndex={0}
              className="group flex items-center gap-2 p-2 rounded-md cursor-pointer hover:bg-indigo-50 transition-colors"
              data-testid={`live-feed-entry-${ev.id}`}
            >
              <Layers className="h-4 w-4 text-indigo-600 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium truncate" title={ev.title}>{ev.title}</div>
                {isLive && activeLot ? (
                  <div className="text-xs text-slate-600 truncate">
                    Lot #{activeLot.lot_number || 1} · <span className="font-medium">{activeLot.title}</span>
                    {activeLot.end_time && (
                      <span className="text-rose-600 ml-1">· {_fmtRemaining(activeLot.end_time)}</span>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-slate-600 truncate">
                    Opens {new Date(ev.start_time).toLocaleString()} · {lots.length} lots
                  </div>
                )}
                <div className="text-[10px] text-slate-500">
                  {remainingLots} lot{remainingLots === 1 ? '' : 's'} remaining
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 transition-colors" />
            </li>
          );
        })}
      </ul>
    </Card>
  );
};

export default LiveMultiLotFeedWidget;
