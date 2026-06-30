/**
 * TopContractorLeaderboard — iter327
 *
 * Public, anonymized leaderboard widget for the /blogs SEO landing page.
 * Reads from GET /api/contractor/leaderboard/public — no auth required,
 * no names / photos / real extensions / dollar amounts exposed.
 *
 * Displays:
 *   • Rank (#1 — top, special highlight for ranks 1-3)
 *   • Masked partner ID (e.g. "Partner #12**")
 *   • Effective commission rate % (5% baseline + overlay, capped 20%)
 *   • Weeks in Top 5 streak
 *   • Trend (▲ / ▼ / —)
 *   • Cosmetic badge label (Rookie / Rising / Pro / Elite / Legendary)
 *
 * Purpose: SEO + social proof + competitive pressure for incoming contractors.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import API_BASE from '../config';
import { Trophy, TrendingUp, TrendingDown, Minus, Sparkles, Crown, Award } from 'lucide-react';

const API = API_BASE;

const BADGE_STYLES = {
  Legendary:  { className: 'bg-gradient-to-r from-amber-400 to-yellow-500 text-slate-900', Icon: Crown },
  Légendaire: { className: 'bg-gradient-to-r from-amber-400 to-yellow-500 text-slate-900', Icon: Crown },
  Elite:      { className: 'bg-gradient-to-r from-purple-500 to-indigo-600 text-white',    Icon: Award },
  Élite:      { className: 'bg-gradient-to-r from-purple-500 to-indigo-600 text-white',    Icon: Award },
  Pro:        { className: 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white',        Icon: Sparkles },
  Rising:     { className: 'bg-emerald-100 text-emerald-800',                              Icon: TrendingUp },
  Montant:    { className: 'bg-emerald-100 text-emerald-800',                              Icon: TrendingUp },
  Rookie:     { className: 'bg-slate-100 text-slate-600',                                  Icon: Minus },
  Recrue:     { className: 'bg-slate-100 text-slate-600',                                  Icon: Minus },
};

const RANK_COLORS = {
  1: 'bg-gradient-to-br from-amber-300 to-yellow-500 text-slate-900 ring-4 ring-amber-200/60',
  2: 'bg-gradient-to-br from-slate-300 to-slate-500 text-white ring-4 ring-slate-200/60',
  3: 'bg-gradient-to-br from-orange-300 to-amber-600 text-white ring-4 ring-orange-200/60',
};

function TrendIcon({ trend }) {
  if (trend === '▲') return <TrendingUp className="w-4 h-4 text-emerald-600" />;
  if (trend === '▼') return <TrendingDown className="w-4 h-4 text-rose-600" />;
  return <Minus className="w-4 h-4 text-slate-400" />;
}

export default function TopContractorLeaderboard() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const lang = fr ? 'fr' : 'en';
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/contractor/leaderboard/public?limit=10&lang=${lang}`);
        if (!cancelled) {
          setRows(res.data?.rows || []);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [fr]);

  if (loading) {
    return (
      <div className="mt-20" data-testid="top-contractor-leaderboard-loading">
        <div className="h-8 bg-slate-200 animate-pulse rounded w-1/3 mb-6" />
        <div className="grid gap-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-slate-100 animate-pulse rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error || rows.length === 0) {
    // Gracefully hide the widget if there's no data — don't pollute the SEO page.
    return null;
  }

  return (
    <section className="mt-20" data-testid="top-contractor-leaderboard">
      <header className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <Trophy className="w-7 h-7" style={{ color: '#0B2545' }} />
          <h2 className="text-3xl font-bold text-slate-900" data-testid="leaderboard-title">
            {fr ? 'Tableau Top Contractants' : 'Top Contractor Leaderboard'}
          </h2>
        </div>
        <p className="text-sm text-slate-600 max-w-2xl">
          {fr
            ? 'Classement public anonymisé des contractants les plus performants de BidVex. Chaque partenaire commence à 5 % de commission de base et gagne +1 % par semaine passée dans le Top 5, plafonné à 20 % effectif. Aucun nom, courriel, photo ni gain en dollars n\'est exposé.'
            : 'Public anonymized ranking of BidVex\'s top-performing partners. Every contractor starts at the 5% baseline commission and earns +1% per week they hold a Top 5 spot, capped at a 20% effective rate. No names, emails, photos, or dollar earnings are exposed.'}
        </p>
      </header>

      <div className="overflow-hidden rounded-2xl border border-slate-200 shadow-sm bg-white">
        {/* Table header */}
        <div
          className="hidden md:grid gap-4 px-6 py-3 text-[10px] uppercase tracking-[0.18em] font-semibold text-slate-500 border-b border-slate-200"
          style={{ gridTemplateColumns: '64px 1fr 110px 130px 120px 90px' }}
        >
          <span>{fr ? 'Rang' : 'Rank'}</span>
          <span>{fr ? 'Partenaire' : 'Partner'}</span>
          <span className="text-right">{fr ? 'Taux effectif' : 'Effective rate'}</span>
          <span className="text-right">{fr ? 'Semaines Top 5' : 'Weeks in Top 5'}</span>
          <span className="text-right">{fr ? 'Badge' : 'Badge'}</span>
          <span className="text-right">{fr ? 'Tendance' : 'Trend'}</span>
        </div>

        {/* Rows */}
        <ul className="divide-y divide-slate-100">
          {rows.map((row) => {
            const rankClass =
              RANK_COLORS[row.rank] || 'bg-slate-100 text-slate-700';
            const badge = BADGE_STYLES[row.badge_label] || BADGE_STYLES.Rookie;
            const BadgeIcon = badge.Icon;
            return (
              <li
                key={row.rank}
                data-testid={`leaderboard-row-${row.rank}`}
                className="px-6 py-4 hover:bg-slate-50 transition-colors"
              >
                {/* Desktop layout */}
                <div
                  className="hidden md:grid items-center gap-4"
                  style={{ gridTemplateColumns: '64px 1fr 110px 130px 120px 90px' }}
                >
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center font-extrabold text-lg ${rankClass}`}>
                    #{row.rank}
                  </div>
                  <div>
                    <div className="font-bold text-slate-900" data-testid={`leaderboard-masked-id-${row.rank}`}>
                      {row.masked_id}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {fr ? 'Poste ' : 'Ext. '}{row.extension_prefix}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-extrabold tabular-nums" style={{ color: '#0B2545' }}>
                      {row.effective_rate_pct.toFixed(0)}%
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-400">
                      {fr ? 'commission' : 'commission'}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-bold text-slate-700 tabular-nums">
                      {row.weeks_in_top_5}
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-400">
                      {fr ? 'semaines' : 'weeks'}
                    </div>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${badge.className}`}
                      data-testid={`leaderboard-badge-${row.rank}`}
                    >
                      <BadgeIcon className="w-3 h-3" />
                      {row.badge_label}
                    </span>
                  </div>
                  <div className="text-right flex items-center justify-end">
                    <TrendIcon trend={row.trend} />
                  </div>
                </div>

                {/* Mobile layout */}
                <div className="md:hidden flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold flex-shrink-0 ${rankClass}`}>
                      #{row.rank}
                    </div>
                    <div className="min-w-0">
                      <div className="font-bold text-slate-900 truncate">{row.masked_id}</div>
                      <div className="text-xs text-slate-500">
                        {row.weeks_in_top_5} {fr ? 'sem.' : 'wks'} • {row.badge_label}
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-xl font-extrabold tabular-nums" style={{ color: '#0B2545' }}>
                      {row.effective_rate_pct.toFixed(0)}%
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center justify-end gap-1">
                      <TrendIcon trend={row.trend} />
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Privacy disclosure */}
      <p className="mt-4 text-xs text-slate-500 italic" data-testid="leaderboard-privacy-note">
        {fr
          ? 'Tous les identifiants personnels sont masqués. Vous voulez voir votre nom ici ? '
          : 'All personal identifiers are masked. Want to see your name on this board? '}
        <a
          href="/contractor/onboarding"
          className="underline hover:text-cyan-700"
          data-testid="leaderboard-cta-link"
        >
          {fr ? 'Devenez contractant BidVex.' : 'Become a BidVex partner.'}
        </a>
      </p>
    </section>
  );
}
