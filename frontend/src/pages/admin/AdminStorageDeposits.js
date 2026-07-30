import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Loader2, ShieldCheck, DollarSign, RefreshCw, AlertTriangle, Ban, CheckCircle } from 'lucide-react';
import { extractErrorMessage } from '../../utils/errorHandler';

const API = API_BASE;

const STATUS_STYLES = {
  held: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  authorized: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  applied: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  refunded: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200',
  forfeited: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200',
};

const AdminStorageDeposits = () => {
  const { token } = useAuth();
  const [data, setData] = useState({ stats: null, deposits: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [confirming, setConfirming] = useState(null); // { action, row }
  const [reason, setReason] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/storage-deposits`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data || { stats: null, deposits: [] });
    } catch (e) {
      toast.error('Failed to load deposits · Échec du chargement');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const doRelease = async (row) => {
    setBusyId(row.auction_id + ':' + row.buyer_id);
    try {
      await axios.post(
        `${API}/admin/storage-auctions/${row.auction_id}/release-deposits`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Deposits released · Dépôts libérés');
      setConfirming(null);
      fetchData();
    } catch (e) {
      toast.error(extractErrorMessage(e) || 'Release failed · Échec');
    } finally {
      setBusyId(null);
    }
  };

  const doForfeit = async (row) => {
    if (!reason.trim()) {
      toast.error('Reason required · Motif requis');
      return;
    }
    setBusyId(row.auction_id + ':' + row.buyer_id);
    try {
      await axios.post(
        `${API}/admin/storage-auctions/${row.auction_id}/forfeit-deposit`,
        { buyer_id: row.buyer_id, reason },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Deposit forfeited · Dépôt confisqué');
      setConfirming(null);
      setReason('');
      fetchData();
    } catch (e) {
      toast.error(extractErrorMessage(e) || 'Forfeit failed · Échec');
    } finally {
      setBusyId(null);
    }
  };

  const filteredRows = data.deposits.filter((r) => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      (r.bidder_name || '').toLowerCase().includes(q) ||
      (r.bidder_email || '').toLowerCase().includes(q) ||
      (r.facility_name || '').toLowerCase().includes(q) ||
      (r.auction_unit_number || '').toLowerCase().includes(q) ||
      (r.auction_id || '').toLowerCase().includes(q) ||
      (r.status || '').toLowerCase().includes(q)
    );
  });

  const stats = data.stats || { active_holds: 0, applied: 0, refunded: 0, forfeited: 0 };

  return (
    <div className="space-y-6" data-testid="admin-storage-deposits">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <DollarSign className="h-6 w-6 text-emerald-500" />
            Storage Deposits
          </h2>
          <p className="text-sm text-muted-foreground italic mt-0.5">Dépôts d'enchères d'entreposage</p>
        </div>
        <Button variant="outline" onClick={fetchData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
          Refresh · Actualiser
        </Button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="border-amber-200 dark:border-amber-900/40" data-testid="stat-active-holds">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium">
              <div className="flex items-center gap-1.5 text-amber-700 dark:text-amber-300">
                <ShieldCheck className="h-3.5 w-3.5" />
                Active Holds
              </div>
              <div className="text-[10px] italic opacity-75 mt-0.5">Retenues actives</div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-black text-amber-700 dark:text-amber-300">{stats.active_holds}</p>
          </CardContent>
        </Card>

        <Card className="border-emerald-200 dark:border-emerald-900/40" data-testid="stat-applied">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium">
              <div className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-300">
                <CheckCircle className="h-3.5 w-3.5" />
                Applied to Fees
              </div>
              <div className="text-[10px] italic opacity-75 mt-0.5">Appliqués aux frais</div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-black text-emerald-700 dark:text-emerald-300">{stats.applied}</p>
          </CardContent>
        </Card>

        <Card className="border-blue-200 dark:border-blue-900/40" data-testid="stat-refunded">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium">
              <div className="flex items-center gap-1.5 text-blue-700 dark:text-blue-300">
                <RefreshCw className="h-3.5 w-3.5" />
                Refunded
              </div>
              <div className="text-[10px] italic opacity-75 mt-0.5">Remboursés</div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-black text-blue-700 dark:text-blue-300">{stats.refunded}</p>
          </CardContent>
        </Card>

        <Card className="border-red-200 dark:border-red-900/40" data-testid="stat-forfeited">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium">
              <div className="flex items-center gap-1.5 text-red-700 dark:text-red-300">
                <AlertTriangle className="h-3.5 w-3.5" />
                Forfeited
              </div>
              <div className="text-[10px] italic opacity-75 mt-0.5">Confisqués</div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-black text-red-700 dark:text-red-300">{stats.forfeited}</p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <Input
            placeholder="Search bidder / facility / unit / status · Rechercher"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            data-testid="deposits-search"
          />
        </CardContent>
      </Card>

      {/* Deposits table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            All Deposit Holds
            <span className="text-sm font-normal italic text-muted-foreground ml-2">· Toutes les retenues</span>
            <Badge variant="outline" className="ml-3">{filteredRows.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : filteredRows.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No deposits found · Aucun dépôt trouvé
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="deposits-table">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="pb-2 pr-3">Bidder<div className="text-[10px] italic font-normal">Enchérisseur</div></th>
                    <th className="pb-2 pr-3">Unit #<div className="text-[10px] italic font-normal">Unité</div></th>
                    <th className="pb-2 pr-3">Facility<div className="text-[10px] italic font-normal">Facilité</div></th>
                    <th className="pb-2 pr-3 text-right">Amount<div className="text-[10px] italic font-normal">Montant</div></th>
                    <th className="pb-2 pr-3">Placed At<div className="text-[10px] italic font-normal">Placé le</div></th>
                    <th className="pb-2 pr-3">Status<div className="text-[10px] italic font-normal">Statut</div></th>
                    <th className="pb-2 pr-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((r) => (
                    <tr key={r.auction_id + ':' + r.buyer_id} className="border-b hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="py-3 pr-3">
                        <div className="font-medium">{r.bidder_name}</div>
                        <div className="text-xs text-muted-foreground">{r.bidder_email}</div>
                      </td>
                      <td className="py-3 pr-3 font-mono text-xs">{r.auction_unit_number}</td>
                      <td className="py-3 pr-3">{r.facility_name}</td>
                      <td className="py-3 pr-3 text-right font-semibold">${Number(r.amount).toFixed(2)} CAD</td>
                      <td className="py-3 pr-3 text-xs text-muted-foreground">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="py-3 pr-3">
                        <Badge className={STATUS_STYLES[r.status] || 'bg-slate-100 text-slate-700'}>
                          {r.status}
                        </Badge>
                      </td>
                      <td className="py-3 pr-3 text-right space-x-1">
                        {(r.status === 'held' || r.status === 'authorized') && (
                          <>
                            <Button
                              size="sm"
                              className="bg-emerald-600 hover:bg-emerald-700 text-white"
                              disabled={busyId === (r.auction_id + ':' + r.buyer_id)}
                              onClick={() => setConfirming({ action: 'release', row: r })}
                              data-testid={`release-${r.auction_id}`}
                            >
                              Release
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={busyId === (r.auction_id + ':' + r.buyer_id)}
                              onClick={() => { setReason(''); setConfirming({ action: 'forfeit', row: r }); }}
                              data-testid={`forfeit-${r.auction_id}`}
                            >
                              <Ban className="h-3.5 w-3.5 mr-1" />
                              Forfeit
                            </Button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confirmation modal */}
      {confirming && (
        <div
          className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
          onClick={() => !busyId && setConfirming(null)}
          data-testid="deposit-confirm-modal"
        >
          <Card className="max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <CardHeader>
              <CardTitle className={confirming.action === 'forfeit' ? 'text-red-600' : 'text-emerald-600'}>
                {confirming.action === 'forfeit'
                  ? 'Confirm Forfeit · Confirmer la confiscation'
                  : 'Confirm Release · Confirmer la libération'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                {confirming.action === 'forfeit'
                  ? `This will CAPTURE $${Number(confirming.row.amount).toFixed(2)} from ${confirming.row.bidder_name}'s card as a penalty.`
                  : `This will release ALL held deposits for auction ${confirming.row.auction_unit_number}. Winner → applied; losers → refunded.`}
              </p>
              <p className="italic text-muted-foreground">
                {confirming.action === 'forfeit'
                  ? `Ceci va CAPTURER ${Number(confirming.row.amount).toFixed(2)} $ sur la carte de ${confirming.row.bidder_name} comme pénalité.`
                  : `Ceci libèrera TOUS les dépôts en attente pour l'enchère ${confirming.row.auction_unit_number}.`}
              </p>
              {confirming.action === 'forfeit' && (
                <div>
                  <label className="text-xs font-semibold">Reason · Motif</label>
                  <Input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. Missed payment deadline · p.ex. Délai dépassé"
                    data-testid="forfeit-reason"
                  />
                </div>
              )}
              <div className="flex justify-end gap-2 pt-3">
                <Button variant="outline" onClick={() => setConfirming(null)} disabled={!!busyId}>
                  Cancel · Annuler
                </Button>
                <Button
                  className={confirming.action === 'forfeit'
                    ? 'bg-red-600 hover:bg-red-700 text-white'
                    : 'bg-emerald-600 hover:bg-emerald-700 text-white'}
                  disabled={!!busyId}
                  onClick={() => confirming.action === 'forfeit' ? doForfeit(confirming.row) : doRelease(confirming.row)}
                  data-testid="confirm-action-btn"
                >
                  {busyId ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                  {confirming.action === 'forfeit' ? 'Forfeit · Confisquer' : 'Release · Libérer'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default AdminStorageDeposits;
