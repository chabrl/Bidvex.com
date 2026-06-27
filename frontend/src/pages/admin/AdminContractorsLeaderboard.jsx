/**
 * iter316-D — Admin: Contractor Performance Leaderboard.
 * Sub-tab inside Admin → Dialer & Contractors.
 *
 * Sortable columns: earnings | call_volume | referred_count | conversion_rate.
 * Period filter: lifetime | month | week.
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
  Trophy, Loader2,
  Eye, AlertTriangle, CheckCircle2, Crown,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';

const money = (n) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n || 0));

const SORT_KEYS = [
  { key: 'earnings',         labelEn: 'Earnings',       labelFr: 'Revenus' },
  { key: 'call_volume',      labelEn: 'Call volume',    labelFr: 'Appels' },
  { key: 'referred_count',   labelEn: 'Referrals',      labelFr: 'Référés' },
  { key: 'conversion_rate',  labelEn: 'Conversion %',   labelFr: 'Conversion %' },
];

const PERIODS = [
  { key: 'lifetime', en: 'Lifetime',  fr: 'Total' },
  { key: 'month',    en: 'This Month', fr: 'Ce mois' },
  { key: 'week',     en: 'Last 7 days', fr: '7 derniers jours' },
];

export default function AdminContractorsLeaderboard() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const { token } = useAuth();
  const navigate = useNavigate();

  const [period, setPeriod] = useState('lifetime');
  const [sortKey, setSortKey] = useState('earnings');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(
        `${API_BASE}/twilio/admin/contractors/leaderboard?period=${period}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setRows(r.data?.items || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [token, period]);

  useEffect(() => { load(); }, [load]);

  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => (Number(b[sortKey] || 0) - Number(a[sortKey] || 0)));
  }, [rows, sortKey]);

  const topAccrued = sorted.length > 0 ? sorted[0] : null;

  return (
    <div className="container mx-auto max-w-7xl py-4 px-3" data-testid="admin-leaderboard-page">
      <header className="mb-4 flex items-start justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="admin-leaderboard-title">
            <Trophy className="h-7 w-7 text-amber-500" />
            {fr ? 'Classement des contractants' : 'Contractor Leaderboard'}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {fr
              ? 'Classez vos contractants par revenus, volume d\u2019appels, recommandations et taux de conversion.'
              : 'Rank your contractors by earnings, call volume, referrals, and conversion rate.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {PERIODS.map((p) => (
            <Button
              key={p.key}
              size="sm"
              variant={period === p.key ? 'default' : 'outline'}
              onClick={() => setPeriod(p.key)}
              data-testid={`period-${p.key}`}
            >
              {fr ? p.fr : p.en}
            </Button>
          ))}
        </div>
      </header>

      {/* MVP card */}
      {topAccrued && topAccrued.earnings > 0 && (
        <Card className="border-2 border-amber-300 bg-gradient-to-r from-amber-50 to-amber-100 mb-3" data-testid="leaderboard-top-performer">
          <CardContent className="p-3 flex items-center gap-3">
            <Crown className="h-8 w-8 text-amber-500" />
            <div className="flex-1">
              <p className="text-xs uppercase tracking-wide text-amber-800">
                {fr ? 'Meilleur contractant' : 'Top performer'}
              </p>
              <p className="text-lg font-bold">{topAccrued.name || topAccrued.email}</p>
              <p className="text-sm text-slate-700">
                {money(topAccrued.earnings)} · {topAccrued.call_volume} {fr ? 'appels' : 'calls'} · {topAccrued.referred_count} {fr ? 'références' : 'referrals'}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20" data-testid="leaderboard-loading">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-2" />
          <span>{fr ? 'Chargement…' : 'Loading…'}</span>
        </div>
      ) : sorted.length === 0 ? (
        <Card className="border-2 border-dashed">
          <CardContent className="p-8 text-center text-sm text-slate-500" data-testid="leaderboard-empty">
            {fr ? 'Aucun contractant à classer pour cette période.' : 'No contractors to rank for this period.'}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="leaderboard-table">
                <thead>
                  <tr className="text-xs text-slate-500 border-b bg-slate-50">
                    <th className="text-left py-2 px-3 w-12">#</th>
                    <th className="text-left py-2 px-3">{fr ? 'Contractant' : 'Contractor'}</th>
                    <th className="text-left py-2 px-3">{fr ? 'Stripe' : 'Stripe'}</th>
                    {SORT_KEYS.map((k) => (
                      <th
                        key={k.key}
                        className={`text-right py-2 px-3 cursor-pointer hover:bg-slate-100 ${sortKey === k.key ? 'text-indigo-700 font-bold' : ''}`}
                        onClick={() => setSortKey(k.key)}
                        data-testid={`sort-${k.key}`}
                      >
                        {fr ? k.labelFr : k.labelEn} {sortKey === k.key && '▼'}
                      </th>
                    ))}
                    <th className="text-right py-2 px-3">{fr ? 'Action' : 'Action'}</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((row, i) => (
                    <tr key={row.contractor_id} className="border-b hover:bg-slate-50" data-testid={`leaderboard-row-${row.contractor_id}`}>
                      <td className="py-2 px-3 font-bold text-slate-600">
                        {i === 0 ? <Crown className="inline h-4 w-4 text-amber-500" /> : `#${i + 1}`}
                      </td>
                      <td className="py-2 px-3">
                        <p className="font-medium">{row.name}</p>
                        <p className="text-xs text-slate-500">{row.email}</p>
                      </td>
                      <td className="py-2 px-3">
                        {row.stripe_ready ? (
                          <Badge className="bg-emerald-100 text-emerald-800"><CheckCircle2 className="h-3 w-3 mr-1" />{fr ? 'OK' : 'OK'}</Badge>
                        ) : (
                          <Badge className="bg-amber-100 text-amber-800"><AlertTriangle className="h-3 w-3 mr-1" />{fr ? 'Manquant' : 'Missing'}</Badge>
                        )}
                      </td>
                      <td className="py-2 px-3 text-right font-semibold">{money(row.earnings)}</td>
                      <td className="py-2 px-3 text-right">{row.call_volume}</td>
                      <td className="py-2 px-3 text-right">{row.referred_count}</td>
                      <td className="py-2 px-3 text-right">
                        {row.referred_count === 0 ? (
                          <span className="text-slate-400">—</span>
                        ) : (
                          <Badge className={row.conversion_rate >= 0.5 ? 'bg-emerald-100 text-emerald-800' : row.conversion_rate >= 0.2 ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'}>
                            {(row.conversion_rate * 100).toFixed(0)}%
                          </Badge>
                        )}
                      </td>
                      <td className="py-2 px-3 text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => navigate(`/admin/contractors/${row.contractor_id}`)}
                          data-testid={`leaderboard-view-${row.contractor_id}`}
                        >
                          <Eye className="h-3.5 w-3.5 mr-1" />
                          {fr ? 'Voir' : 'View'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
