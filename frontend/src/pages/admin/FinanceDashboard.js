import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import {
  DollarSign, TrendingUp, Users, Building2, Gavel, CreditCard,
  Search, FileText, ExternalLink, Shield, Loader2, ToggleLeft,
  ToggleRight, Trash2, Eye, ChevronLeft, ChevronRight, Clock,
  ArrowUpDown, Percent, Landmark, Download
} from 'lucide-react';

const API = API_BASE;

const fmt = (v) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(v || 0);

const FinanceDashboard = () => {
  const { token } = useAuth();
  const [revenue, setRevenue] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [txPage, setTxPage] = useState(1);
  const [txTotal, setTxTotal] = useState(0);
  const [txPages, setTxPages] = useState(0);
  const [txSearch, setTxSearch] = useState('');
  const [partnerOnly, setPartnerOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [txLoading, setTxLoading] = useState(false);

  // Partner management
  const [partners, setPartners] = useState([]);
  const [partnerFilter, setPartnerFilter] = useState('all');
  const [reviewDialog, setReviewDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const [activeTab, setActiveTab] = useState('overview');

  const headers = { Authorization: `Bearer ${token}` };

  const fetchRevenue = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/finance/revenue-summary`, { headers });
      setRevenue(res.data);
    } catch { toast.error('Failed to load revenue data.'); }
    finally { setLoading(false); }
  }, [token]);

  const fetchTransactions = useCallback(async () => {
    setTxLoading(true);
    try {
      const params = new URLSearchParams({ page: txPage, limit: 25, partner_only: partnerOnly });
      if (txSearch) params.set('search', txSearch);
      const res = await axios.get(`${API}/admin/finance/transactions?${params}`, { headers });
      setTransactions(res.data.transactions || []);
      setTxTotal(res.data.total || 0);
      setTxPages(res.data.pages || 0);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load transactions');
    }
    finally { setTxLoading(false); }
  }, [token, txPage, partnerOnly, txSearch]);

  const fetchPartners = useCallback(async () => {
    try {
      const params = partnerFilter !== 'all' ? `?status=${partnerFilter}` : '';
      const res = await axios.get(`${API}/admin/partners${params}`, { headers });
      setPartners(res.data.applications || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load partners');
    }
  }, [token, partnerFilter]);

  useEffect(() => { fetchRevenue(); }, [fetchRevenue]);
  useEffect(() => { if (activeTab === 'transactions') fetchTransactions(); }, [activeTab, fetchTransactions]);
  useEffect(() => { if (activeTab === 'partners') fetchPartners(); }, [activeTab, fetchPartners]);

  const handleTogglePartner = async (userId) => {
    if (actionLoading) return;
    setActionLoading(true);
    try {
      await axios.post(`${API}/admin/partners/${userId}/toggle`, {}, { headers });
      toast.success('Partner status toggled.');
      fetchPartners(); fetchRevenue();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to toggle partner'); }
    finally { setActionLoading(false); }
  };

  const handlePauseUser = async (userId) => {
    if (actionLoading) return;
    setActionLoading(true);
    try {
      const res = await axios.post(`${API}/admin/users/${userId}/pause`, {}, { headers });
      toast.success(`Account ${res.data.new_status}.`);
      fetchPartners();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to pause user'); }
    finally { setActionLoading(false); }
  };

  const handleDeleteUser = async (userId) => {
    setConfirm({
      title: 'Soft-delete this account?',
      description: 'The user will lose access but data is retained for audit. Supprimer le compte ? L\'utilisateur perd l\'accès mais les données sont conservées.',
      variant: 'destructive',
      confirmText: 'Delete Account',
      successMessage: 'Account deleted',
      onConfirm: async () => {
        await axios.delete(`${API}/admin/users/${userId}`, { headers });
        fetchPartners();
      },
    });
  };

  const tabs = [
    { id: 'overview', label: 'Revenue Overview', icon: TrendingUp },
    { id: 'partners', label: 'Partner Accounts', icon: Building2 },
    { id: 'transactions', label: 'Transaction Logs', icon: CreditCard },
  ];

  const r = revenue?.revenue || {};
  const pr = revenue?.partner_revenue || {};
  const u = revenue?.users || {};
  const a = revenue?.auctions || {};

  return (
    <div className="space-y-4" data-testid="finance-dashboard">
      {/* Tab Navigation */}
      <div className="flex gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeTab === t.id
                ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            data-testid={`finance-tab-${t.id}`}
          >
            <t.icon className="w-3.5 h-3.5" /> {t.label}
          </button>
        ))}
      </div>

      {/* OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>
          ) : (
            <>
              {/* PRIMARY: Collected Fees — The #1 metric */}
              <Card className="border-2 border-emerald-200 dark:border-emerald-800 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30" data-testid="collected-fees-hero">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider mb-1">Collected Fees (Your Revenue)</p>
                      <p className="text-3xl font-bold text-emerald-800 dark:text-emerald-300" data-testid="total-collected-fees">
                        {fmt((r.total_platform_fees || 0) + (r.total_processing_fees || 0) + (r.subscription_revenue || 0))}
                      </p>
                    </div>
                    <div className="p-3 bg-emerald-100 dark:bg-emerald-900/50 rounded-xl">
                      <Landmark className="w-7 h-7 text-emerald-600 dark:text-emerald-400" />
                    </div>
                  </div>
                  {/* Fee Breakdown */}
                  <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-emerald-200 dark:border-emerald-800">
                    <div data-testid="fee-platform">
                      <div className="flex items-center gap-1.5 mb-1">
                        <Percent className="w-3.5 h-3.5 text-emerald-600" />
                        <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400">3% Platform Fee</span>
                      </div>
                      <p className="text-lg font-bold text-emerald-800 dark:text-emerald-300">{fmt(r.total_platform_fees)}</p>
                      <p className="text-[10px] text-emerald-600 dark:text-emerald-500 mt-0.5">From all auction sales</p>
                    </div>
                    <div data-testid="fee-stripe-recovery">
                      <div className="flex items-center gap-1.5 mb-1">
                        <CreditCard className="w-3.5 h-3.5 text-slate-500" />
                        <span className="text-[11px] font-medium text-slate-600 dark:text-slate-400">Stripe Cost Recovery</span>
                      </div>
                      <p className="text-lg font-bold text-slate-700 dark:text-slate-300">{fmt(r.total_processing_fees)}</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">2.9% + $0.30 passed to buyer</p>
                    </div>
                    <div data-testid="fee-subscriptions">
                      <div className="flex items-center gap-1.5 mb-1">
                        <CreditCard className="w-3.5 h-3.5 text-violet-500" />
                        <span className="text-[11px] font-medium text-violet-600 dark:text-violet-400">Subscription Revenue</span>
                      </div>
                      <p className="text-lg font-bold text-violet-700 dark:text-violet-300">{fmt(r.subscription_revenue)}</p>
                      <p className="text-[10px] text-violet-500 mt-0.5">Premium & VIP plans</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Secondary Stats Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { label: 'Hammer Volume', value: fmt(r.total_hammer_volume), icon: Gavel, color: 'text-blue-600' },
                  { label: 'Buyer Premiums', value: fmt(r.total_buyer_premiums), icon: DollarSign, color: 'text-amber-600' },
                  { label: 'Transactions', value: r.total_transactions || 0, icon: ArrowUpDown, color: 'text-slate-600' },
                  { label: 'Active Auctions', value: a.active || 0, icon: Gavel, color: 'text-cyan-600' },
                ].map((c, i) => (
                  <Card key={i} data-testid={`revenue-card-${i}`}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-[11px] text-slate-500 font-medium">{c.label}</p>
                          <p className="text-lg font-bold mt-0.5">{c.value}</p>
                        </div>
                        <c.icon className={`w-5 h-5 ${c.color} opacity-60`} />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Partner Revenue Section */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-blue-500" /> Partner Revenue Breakdown
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-[11px] text-slate-500">Partner Hammer Volume</p>
                      <p className="font-semibold">{fmt(pr.hammer_volume)}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-slate-500">3% Fees from Partners</p>
                      <p className="font-semibold text-emerald-600">{fmt(pr.platform_fees_collected)}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-slate-500">Buyer Premiums (Partner)</p>
                      <p className="font-semibold">{fmt(pr.buyer_premiums)}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-slate-500">Partner Transactions</p>
                      <p className="font-semibold">{pr.transaction_count || 0}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* User & Auction Quick Stats */}
              <div className="grid sm:grid-cols-2 gap-3">
                <Card>
                  <CardContent className="p-4">
                    <p className="text-xs text-slate-500 font-medium mb-2">User Accounts</p>
                    <div className="flex gap-4 text-sm">
                      <div><span className="font-bold text-lg">{u.total || 0}</span> <span className="text-slate-500">Total</span></div>
                      <div><span className="font-bold text-lg text-emerald-600">{u.active_partners || 0}</span> <span className="text-slate-500">Partners</span></div>
                      <div><span className="font-bold text-lg text-amber-600">{u.pending_partners || 0}</span> <span className="text-slate-500">Pending</span></div>
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4">
                    <p className="text-xs text-slate-500 font-medium mb-2">Auctions</p>
                    <div className="flex gap-4 text-sm">
                      <div><span className="font-bold text-lg">{a.total || 0}</span> <span className="text-slate-500">Total</span></div>
                      <div><span className="font-bold text-lg text-blue-600">{a.active || 0}</span> <span className="text-slate-500">Active</span></div>
                      <div><span className="font-bold text-lg text-violet-600">{a.partner_active || 0}</span> <span className="text-slate-500">Partner</span></div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </div>
      )}

      {/* PARTNERS TAB */}
      {activeTab === 'partners' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {['all', 'pending', 'verified', 'rejected'].map(f => (
              <Button key={f} variant={partnerFilter === f ? 'default' : 'outline'} size="sm"
                onClick={() => setPartnerFilter(f)} className="text-xs capitalize" data-testid={`pf-filter-${f}`}>
                {f}
              </Button>
            ))}
          </div>

          {partners.length === 0 ? (
            <div className="text-center py-8 text-slate-500 text-sm">No partner applications found.</div>
          ) : (
            <div className="space-y-2">
              {partners.map(p => (
                <Card key={p.id} data-testid={`pf-user-${p.id}`}>
                  <CardContent className="p-3">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm truncate">{p.partner_company_name || p.name || p.email}</span>
                          <Badge variant={p.is_partner ? 'default' : 'secondary'} className="text-[10px]">
                            {p.partner_verification_status}
                          </Badge>
                          {p.is_partner && <Shield className="w-3.5 h-3.5 text-emerald-500" />}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          {p.email} {p.partner_neq && `| Business Reg.: ${p.partner_neq}`}
                          {p.custom_premium_rate != null && <span className="text-blue-600 ml-2">BP: {(p.custom_premium_rate * 100).toFixed(1)}%</span>}
                        </div>
                      </div>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm" onClick={() => { setSelectedUser(p); setReviewDialog(true); }}
                          data-testid={`pf-review-${p.id}`}>
                          <Eye className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleTogglePartner(p.id)}
                          title={p.is_partner ? 'Revoke partner' : 'Grant partner'} data-testid={`pf-toggle-${p.id}`}>
                          {p.is_partner ? <ToggleRight className="w-4 h-4 text-emerald-500" /> : <ToggleLeft className="w-4 h-4 text-slate-400" />}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handlePauseUser(p.id)} data-testid={`pf-pause-${p.id}`}>
                          <Clock className="w-3.5 h-3.5 text-amber-500" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDeleteUser(p.id)} data-testid={`pf-delete-${p.id}`}>
                          <Trash2 className="w-3.5 h-3.5 text-red-400" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Review Dialog */}
          <Dialog open={reviewDialog} onOpenChange={setReviewDialog}>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Building2 className="w-5 h-5" /> {selectedUser?.partner_company_name || 'User'}
                </DialogTitle>
                <DialogDescription>{selectedUser?.email}</DialogDescription>
              </DialogHeader>
              {selectedUser && (
                <div className="space-y-4 text-sm">
                  <div className="grid grid-cols-2 gap-3">
                    <div><span className="text-xs text-slate-500">Business Reg. #</span><p className="font-medium">{selectedUser.partner_neq || '-'}</p></div>
                    <div><span className="text-xs text-slate-500">Status</span>
                      <Badge className="text-xs">{selectedUser.partner_verification_status}</Badge>
                    </div>
                    <div><span className="text-xs text-slate-500">Account Type</span><p className="font-medium capitalize">{selectedUser.account_type}</p></div>
                    <div><span className="text-xs text-slate-500">Applied</span><p className="font-medium">{selectedUser.partner_applied_at ? new Date(selectedUser.partner_applied_at).toLocaleDateString() : '-'}</p></div>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500">Documents</span>
                    <div className="space-y-1 mt-1">
                      {selectedUser.partner_neq_document && (() => {
                        // iter208 — relative path + ?token=; prefix with bare REACT_APP_BACKEND_URL (NOT API which adds /api)
                        const raw = selectedUser.partner_neq_document;
                        const abs = raw.startsWith('http') ? raw : `${process.env.REACT_APP_BACKEND_URL}${raw}`;
                        const href = `${abs}${abs.includes('?') ? '&' : '?'}token=${encodeURIComponent(token || '')}`;
                        return (
                          <a
                            href={href}
                            target="_blank"
                            rel="noreferrer"
                            data-testid="partner-doc-neq-link"
                            className="flex items-center gap-1.5 text-blue-600 hover:underline text-xs"
                          >
                            <FileText className="w-3.5 h-3.5" /> Business Registration <ExternalLink className="w-3 h-3" />
                          </a>
                        );
                      })()}
                      {(selectedUser.partner_certifications || []).map((raw, i) => {
                        const abs = raw.startsWith('http') ? raw : `${process.env.REACT_APP_BACKEND_URL}${raw}`;
                        const href = `${abs}${abs.includes('?') ? '&' : '?'}token=${encodeURIComponent(token || '')}`;
                        return (
                          <a
                            key={i}
                            href={href}
                            target="_blank"
                            rel="noreferrer"
                            data-testid={`partner-doc-cert-link-${i}`}
                            className="flex items-center gap-1.5 text-blue-600 hover:underline text-xs"
                          >
                            <Shield className="w-3.5 h-3.5" /> Certification {i + 1} <ExternalLink className="w-3 h-3" />
                          </a>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
              <DialogFooter>
                <Button variant="outline" size="sm" onClick={() => setReviewDialog(false)}>Close</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {/* TRANSACTIONS TAB */}
      {activeTab === 'transactions' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input placeholder="Search transactions..." value={txSearch}
                onChange={e => { setTxSearch(e.target.value); setTxPage(1); }}
                className="pl-9 h-8 text-sm" data-testid="tx-search" />
            </div>
            <Button variant={partnerOnly ? 'default' : 'outline'} size="sm"
              onClick={() => { setPartnerOnly(!partnerOnly); setTxPage(1); }} className="text-xs" data-testid="tx-partner-filter">
              <Building2 className="w-3.5 h-3.5 mr-1" /> Partner Only
            </Button>
            <Button variant="outline" size="sm" className="text-xs" data-testid="tx-export-csv"
              onClick={() => {
                const params = new URLSearchParams({ partner_only: partnerOnly });
                if (txSearch) params.set('search', txSearch);
                const url = `${API}/admin/finance/transactions/export?${params}`;
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', '');
                // Add auth header via fetch + blob
                fetch(url, { headers: { Authorization: `Bearer ${token}` } })
                  .then(r => r.blob())
                  .then(blob => {
                    const blobUrl = window.URL.createObjectURL(blob);
                    link.href = blobUrl;
                    link.download = `bidvex_transactions_${new Date().toISOString().slice(0,10)}.csv`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(blobUrl);
                    toast.success('CSV exported successfully.');
                  })
                  .catch(() => toast.error('Export failed.'));
              }}>
              <Download className="w-3.5 h-3.5 mr-1" /> Export CSV
            </Button>
          </div>

          {txLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>
          ) : transactions.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <CreditCard className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No transactions recorded yet.</p>
              <p className="text-xs text-slate-400 mt-1">Transactions appear here after auction payments are processed.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-xs" data-testid="tx-table">
                  <thead>
                    <tr className="border-b text-left text-slate-500">
                      <th className="pb-2 font-medium">Date</th>
                      <th className="pb-2 font-medium">Item</th>
                      <th className="pb-2 font-medium text-right">Hammer</th>
                      <th className="pb-2 font-medium text-right">BP</th>
                      <th className="pb-2 font-medium text-right">Partner Payout</th>
                      <th className="pb-2 font-medium text-right">BidVex Fee</th>
                      <th className="pb-2 font-medium text-center">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx, i) => (
                      <tr key={i} className="border-b border-slate-100 dark:border-slate-800">
                        <td className="py-2 text-slate-500">{tx.created_at ? new Date(tx.created_at).toLocaleDateString() : '-'}</td>
                        <td className="py-2 font-medium truncate max-w-[180px]">{tx.listing_title || tx.listing_id || '-'}</td>
                        <td className="py-2 text-right">{fmt(tx.hammer_price)}</td>
                        <td className="py-2 text-right">{fmt(tx.buyer_premium)}</td>
                        <td className="py-2 text-right text-emerald-600">{fmt(tx.partner_payout || tx.seller_payout)}</td>
                        <td className="py-2 text-right text-blue-600">{fmt(tx.application_fee || tx.platform_fee)}</td>
                        <td className="py-2 text-center">
                          <Badge variant={tx.is_partner_transaction ? 'default' : 'secondary'} className="text-[10px]">
                            {tx.is_partner_transaction ? 'Partner' : 'Standard'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {txPages > 1 && (
                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-slate-500">{txTotal} transactions</span>
                  <div className="flex gap-1">
                    <Button variant="outline" size="sm" disabled={txPage <= 1} onClick={() => setTxPage(p => p - 1)}>
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </Button>
                    <span className="px-2 py-1 text-xs text-slate-500">{txPage}/{txPages}</span>
                    <Button variant="outline" size="sm" disabled={txPage >= txPages} onClick={() => setTxPage(p => p + 1)}>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
      <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />
    </div>
  );
};

export default FinanceDashboard;
