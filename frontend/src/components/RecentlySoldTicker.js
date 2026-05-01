/**
 * RecentlySoldTicker — iter175
 * =============================
 * Rolling marquee on the homepage showing recent auction wins across all
 * three surfaces (marketplace · storage · vehicle).
 *
 * Visibility threshold: only renders when the platform has >= 10 completed
 * auctions in TOTAL — backend returns `visible: false` otherwise so the
 * homepage doesn't show an empty/anaemic strip pre-launch.
 *
 * Format per item:  $1,234 · Toronto, ON · 10x10 storage unit
 * Bilingual: every item shows EN label, FR label is in tooltip via title attr.
 */
import API_BASE from '../config';
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Sparkles, MapPin, Package, Car, ShoppingBag } from 'lucide-react';

const API = API_BASE;

const KIND_META = {
  marketplace: { Icon: ShoppingBag, color: 'text-blue-300' },
  storage:     { Icon: Package,     color: 'text-amber-300' },
  vehicle:     { Icon: Car,         color: 'text-emerald-300' },
};

const formatCAD = (n) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(n || 0);

const RecentlySoldTicker = () => {
  const [data, setData] = useState({ visible: false, items: [] });

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await axios.get(`${API}/carousel/recently-sold-ticker?limit=30`);
        if (!cancelled) setData(r.data || { visible: false, items: [] });
      } catch {
        if (!cancelled) setData({ visible: false, items: [] });
      }
    };
    load();
    const t = setInterval(load, 60_000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  if (!data?.visible || !Array.isArray(data.items) || data.items.length === 0) {
    return null;
  }

  // Duplicate items twice so the marquee animation loops seamlessly
  const loop = [...data.items, ...data.items];

  return (
    <section
      data-testid="recently-sold-ticker"
      className="bg-gradient-to-r from-slate-900 via-blue-950 to-slate-900 text-white border-y border-blue-900/40 relative overflow-hidden"
    >
      <div className="flex items-center gap-3 py-2 px-4 max-w-[1600px] mx-auto">
        <div className="flex items-center gap-2 shrink-0 pr-3 border-r border-blue-800/60">
          <Sparkles className="h-4 w-4 text-yellow-400 animate-pulse" />
          <span className="text-[11px] uppercase tracking-widest font-bold text-yellow-200 leading-tight">
            Recently Sold
            <br />
            <span className="text-blue-200/80 font-normal normal-case tracking-normal italic">Vendus récemment</span>
          </span>
        </div>

        <div className="flex-1 overflow-hidden relative">
          {/* edge fade */}
          <div className="pointer-events-none absolute inset-y-0 left-0 w-12 bg-gradient-to-r from-slate-900 to-transparent z-10" />
          <div className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-slate-900 to-transparent z-10" />
          <div
            className="flex gap-6 whitespace-nowrap"
            style={{
              animation: 'recently-sold-marquee 60s linear infinite',
            }}
          >
            {loop.map((it, i) => {
              const meta = KIND_META[it.kind] || KIND_META.marketplace;
              const Icon = meta.Icon;
              const cityProv = [it.city, it.province].filter(Boolean).join(', ');
              return (
                <div
                  key={`${it.kind}-${i}`}
                  className="flex items-center gap-2 text-sm shrink-0"
                  title={`${formatCAD(it.price)} · ${cityProv} · ${it.label_fr}`}
                  data-testid={`ticker-item-${i}`}
                >
                  <Icon className={`h-3.5 w-3.5 ${meta.color}`} />
                  <span className="font-bold text-yellow-300">{formatCAD(it.price)}</span>
                  {cityProv && (
                    <span className="text-blue-200 inline-flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {cityProv}
                    </span>
                  )}
                  <span className="text-blue-100/90 truncate max-w-[280px]">{it.label_en}</span>
                  <span className="text-blue-300/40">•</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes recently-sold-marquee {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </section>
  );
};

export default RecentlySoldTicker;
