import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import API_BASE from '../../config';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Lock, CheckCircle2, Clock, AlertTriangle, Search, RefreshCw, Shield, Key } from 'lucide-react';

const API = API_BASE;

const STATUS_COLORS = {
  held: 'bg-amber-100 text-amber-800',
  released: 'bg-green-100 text-green-800',
  auto_released: 'bg-blue-100 text-blue-800',
  disputed: 'bg-red-100 text-red-800',
  refunded: 'bg-slate-100 text-slate-800',
};

export default function AdminEscrowManager() {
  const { token } = useAuth();
  const [escrows, setEscrows] = useState([]);
  const [penalties, setPenalties] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('escrows');
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [escrowRes, penaltyRes, disputeRes] = await Promise.all([
        axios.get(`${API}/escrow/admin/escrow/transactions`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/escrow/admin/escrow/penalties`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/escrow/admin/escrow/disputes`, { headers }).catch(() => ({ data: [] })),
      ]);
      setEscrows(Array.isArray(escrowRes.data) ? escrowRes.data : []);
      setPenalties(Array.isArray(penaltyRes.data) ? penaltyRes.data : []);
      setDisputes(Array.isArray(disputeRes.data) ? disputeRes.data : []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAll(); }, []);

  const filteredEscrows = escrows.filter(e => {
    if (statusFilter !== 'all' && e.escrow_status !== statusFilter) return false;
    if (searchQuery && !JSON.stringify(e).toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6" data-testid="admin-escrow-manager">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold">{escrows.length}</p><p className="text-xs text-muted-foreground">Total Escrows</p></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-amber-600">{escrows.filter(e => e.escrow_status === 'held').length}</p><p className="text-xs text-muted-foreground">Held</p></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-green-600">{escrows.filter(e => e.escrow_status === 'released').length}</p><p className="text-xs text-muted-foreground">Released</p></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-red-600">{disputes.length}</p><p className="text-xs text-muted-foreground">Disputes</p></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><p className="text-2xl font-bold text-purple-600">{penalties.length}</p><p className="text-xs text-muted-foreground">Penalties</p></CardContent></Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        {['escrows', 'disputes', 'penalties'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${tab === t ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
            data-testid={`admin-tab-${t}`}>
            {t === 'escrows' ? 'Escrow Transactions' : t === 'disputes' ? 'Disputes' : 'Penalty Log'}
          </button>
        ))}
        <Button variant="outline" size="sm" className="ml-auto" onClick={fetchAll} data-testid="refresh-btn">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Escrow Transactions Tab */}
      {tab === 'escrows' && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search by ID, buyer, seller..." className="pl-9" data-testid="escrow-search" />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="held">Held</SelectItem>
                <SelectItem value="released">Released</SelectItem>
                <SelectItem value="auto_released">Auto-Released</SelectItem>
                <SelectItem value="disputed">Disputed</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {loading ? <p className="text-center py-8 text-muted-foreground">Loading...</p> :
          filteredEscrows.length === 0 ? (
            <Card><CardContent className="py-12 text-center"><Shield className="h-10 w-10 text-slate-300 mx-auto mb-3" /><p className="text-muted-foreground">No escrow transactions found.</p></CardContent></Card>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="escrow-table">
                <thead><tr className="border-b bg-muted/50">
                  <th className="p-3 text-left">Auction</th>
                  <th className="p-3 text-left">Buyer</th>
                  <th className="p-3 text-left">Seller</th>
                  <th className="p-3 text-left">Amount</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Code</th>
                  <th className="p-3 text-left">Created</th>
                  <th className="p-3 text-left">Released</th>
                </tr></thead>
                <tbody>
                  {filteredEscrows.map(e => (
                    <tr key={e.auction_id} className="border-b hover:bg-muted/30" data-testid={`escrow-row-${e.auction_id}`}>
                      <td className="p-3 font-mono text-xs">{e.auction_id?.slice(0, 8)}...</td>
                      <td className="p-3 font-mono text-xs">{e.buyer_id?.slice(0, 8)}...</td>
                      <td className="p-3 font-mono text-xs">{e.seller_id?.slice(0, 8)}...</td>
                      <td className="p-3 font-semibold">${((e.total_charged_cents || 0) / 100).toFixed(2)}</td>
                      <td className="p-3"><Badge className={STATUS_COLORS[e.escrow_status] || ''}>{e.escrow_status}</Badge></td>
                      <td className="p-3 font-mono">{e.pickup_code || '—'}</td>
                      <td className="p-3 text-xs">{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
                      <td className="p-3 text-xs">{e.funds_released_at ? new Date(e.funds_released_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Disputes Tab */}
      {tab === 'disputes' && (
        <div>
          {disputes.length === 0 ? (
            <Card><CardContent className="py-12 text-center"><AlertTriangle className="h-10 w-10 text-slate-300 mx-auto mb-3" /><p className="text-muted-foreground">No disputes found.</p></CardContent></Card>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="dispute-table">
                <thead><tr className="border-b bg-muted/50">
                  <th className="p-3 text-left">Auction ID</th>
                  <th className="p-3 text-left">Initiated By</th>
                  <th className="p-3 text-left">Reason</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Created</th>
                </tr></thead>
                <tbody>
                  {disputes.map((d, i) => (
                    <tr key={i} className="border-b hover:bg-muted/30">
                      <td className="p-3 font-mono text-xs">{d.auction_id?.slice(0, 8)}...</td>
                      <td className="p-3 font-mono text-xs">{d.initiated_by?.slice(0, 8)}...</td>
                      <td className="p-3">{d.reason}</td>
                      <td className="p-3"><Badge className="bg-red-100 text-red-800">{d.status}</Badge></td>
                      <td className="p-3 text-xs">{d.created_at ? new Date(d.created_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Penalties Tab */}
      {tab === 'penalties' && (
        <div>
          {penalties.length === 0 ? (
            <Card><CardContent className="py-12 text-center"><Lock className="h-10 w-10 text-slate-300 mx-auto mb-3" /><p className="text-muted-foreground">No penalties issued.</p></CardContent></Card>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="penalty-table">
                <thead><tr className="border-b bg-muted/50">
                  <th className="p-3 text-left">Seller ID</th>
                  <th className="p-3 text-left">Listing</th>
                  <th className="p-3 text-left">Amount</th>
                  <th className="p-3 text-left">Reason</th>
                  <th className="p-3 text-left">Stripe PI</th>
                  <th className="p-3 text-left">Status</th>
                  <th className="p-3 text-left">Date</th>
                </tr></thead>
                <tbody>
                  {penalties.map((p, i) => (
                    <tr key={i} className="border-b hover:bg-muted/30">
                      <td className="p-3 font-mono text-xs">{p.seller_id?.slice(0, 8)}...</td>
                      <td className="p-3 font-mono text-xs">{p.listing_id?.slice(0, 8)}...</td>
                      <td className="p-3 font-semibold text-red-600">${((p.amount_cents || 0) / 100).toFixed(2)}</td>
                      <td className="p-3">{p.reason}</td>
                      <td className="p-3 font-mono text-xs">{p.stripe_payment_intent?.slice(0, 12) || '—'}</td>
                      <td className="p-3"><Badge className={p.status === 'succeeded' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>{p.status}</Badge></td>
                      <td className="p-3 text-xs">{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
