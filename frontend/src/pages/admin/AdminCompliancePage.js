/**
 * iter307 — Admin Compliance Dashboard
 *
 * Single page, 5 stacked sections:
 *   1. AI Watchdog Flagged Listings   — Approve & Exempt / Reject
 *   2. Bidding-Suspended Users        — One-click Reinstate
 *   3. Overdue Payments               — Retry Charge / Mark Resolved / Flag Account
 *   4. Escalated Disputes             — Add Note (resolution actions live on the
 *                                       Disputed Settlements tab)
 *   5. Bill 96 Violations             — Edit Listing / Notify Seller
 *
 * Fully bilingual EN/FR. Empty sections show a green "All clear" state.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  AlertTriangle, CheckCircle2, Shield, UserCheck, RefreshCw, Ban,
  FileEdit, Bell, Loader2, ExternalLink, ScrollText,
} from 'lucide-react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../components/ui/dialog';
import API_BASE from '../../config';

const useFr = () => {
  const { i18n } = useTranslation();
  return (i18n.language || 'en').startsWith('fr');
};

// ─── Reusable empty / loading states ─────────────────────────────────
const SectionShell = ({ icon, title, description, badge, children, testid }) => (
  <Card className="mb-6" data-testid={testid}>
    <CardHeader>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {icon}
          <div>
            <CardTitle className="text-base sm:text-lg">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
        </div>
        {badge}
      </div>
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
);

const AllClear = ({ fr }) => (
  <div className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400 py-4">
    <CheckCircle2 className="h-4 w-4" />
    {fr ? 'Tout va bien — aucune action requise.' : 'All clear — no action needed.'}
  </div>
);

// ─── Section 1: Watchdog Flagged Listings ────────────────────────────
const FlaggedListings = () => {
  const fr = useFr();
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API_BASE}/admin/compliance/flagged-listings`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setItems(r.data.items || []);
    } catch {
      setItems([]);
    }
  }, []);
  useEffect(() => { load(); }, [load]); // eslint-disable-line

  const act = async (id, action) => {
    setBusy(`${id}:${action}`);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API_BASE}/admin/compliance/flagged-listings/${id}/${action}`,
        {}, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(fr ? 'Action effectuée' : 'Action completed');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Échec' : 'Failed'));
    } finally {
      setBusy(null);
    }
  };

  if (items === null) return <Loader2 className="h-4 w-4 animate-spin" />;

  return (
    <SectionShell
      testid="compliance-section-flagged"
      icon={<AlertTriangle className="h-5 w-5 text-amber-600" />}
      title={fr ? '1. Annonces signalées par le Watchdog IA' : '1. AI Watchdog Flagged Listings'}
      description={fr ? "Annonces signalées par notre détection IA et en attente de revue."
        : 'Listings flagged by AI detection and awaiting review.'}
      badge={<Badge variant={items.length ? 'destructive' : 'secondary'}>{items.length}</Badge>}
    >
      {items.length === 0 ? <AllClear fr={fr} /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b">
              <tr className="text-left text-xs uppercase text-muted-foreground">
                <th className="py-2 pr-3">{fr ? 'Titre' : 'Title'}</th>
                <th className="py-2 pr-3">{fr ? 'Section' : 'Section'}</th>
                <th className="py-2 pr-3">{fr ? 'Vendeur' : 'Seller'}</th>
                <th className="py-2 pr-3">{fr ? 'Raison' : 'Reason'}</th>
                <th className="py-2 pr-3">{fr ? 'Signalé le' : 'Flagged'}</th>
                <th className="py-2">{fr ? 'Actions' : 'Actions'}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b last:border-0" data-testid={`flagged-row-${row.id}`}>
                  <td className="py-2 pr-3 font-medium truncate max-w-[200px]">{row.title || '—'}</td>
                  <td className="py-2 pr-3"><Badge variant="outline">{row.section}</Badge></td>
                  <td className="py-2 pr-3 text-xs">{row.seller_name || row.seller_id || '—'}</td>
                  <td className="py-2 pr-3 text-xs text-muted-foreground max-w-[220px] truncate">{row.watchdog_flag_reason || '—'}</td>
                  <td className="py-2 pr-3 text-xs">{row.watchdog_flagged_at ? new Date(row.watchdog_flagged_at).toLocaleDateString() : '—'}</td>
                  <td className="py-2 flex gap-2">
                    <Button size="sm" variant="outline" disabled={!!busy}
                      onClick={() => act(row.id, 'approve')} data-testid={`flagged-approve-${row.id}`}>
                      {busy === `${row.id}:approve` ? <Loader2 className="h-3 w-3 animate-spin" /> : (fr ? 'Approuver' : 'Approve')}
                    </Button>
                    <Button size="sm" variant="destructive" disabled={!!busy}
                      onClick={() => act(row.id, 'reject')} data-testid={`flagged-reject-${row.id}`}>
                      {busy === `${row.id}:reject` ? <Loader2 className="h-3 w-3 animate-spin" /> : (fr ? 'Rejeter' : 'Reject')}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionShell>
  );
};

// ─── Section 2: Bidding-Suspended Users ──────────────────────────────
const BiddingSuspended = () => {
  const fr = useFr();
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API_BASE}/admin/compliance/bidding-suspended`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setItems(r.data.items || []);
    } catch { setItems([]); }
  }, []);
  useEffect(() => { load(); }, [load]); // eslint-disable-line

  const reinstate = async (uid) => {
    setBusy(uid);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_BASE}/admin/compliance/bidding-suspended/${uid}/reinstate`, {},
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success(fr ? "Utilisateur réintégré" : 'User reinstated');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Échec' : 'Failed'));
    } finally { setBusy(null); }
  };

  if (items === null) return <Loader2 className="h-4 w-4 animate-spin" />;

  return (
    <SectionShell
      testid="compliance-section-suspended"
      icon={<Ban className="h-5 w-5 text-red-600" />}
      title={fr ? '2. Utilisateurs avec enchères suspendues' : '2. Bidding-Suspended Users'}
      description={fr ? "Comptes ne pouvant plus enchérir — un clic pour réintégrer." : 'Accounts unable to bid — one click to reinstate.'}
      badge={<Badge variant={items.length ? 'destructive' : 'secondary'}>{items.length}</Badge>}
    >
      {items.length === 0 ? <AllClear fr={fr} /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b">
              <tr className="text-left text-xs uppercase text-muted-foreground">
                <th className="py-2 pr-3">{fr ? 'Nom' : 'Name'}</th>
                <th className="py-2 pr-3">Email</th>
                <th className="py-2 pr-3">{fr ? 'Province' : 'Province'}</th>
                <th className="py-2 pr-3">{fr ? 'Raison' : 'Reason'}</th>
                <th className="py-2 pr-3">{fr ? 'Suspendu le' : 'Suspended'}</th>
                <th className="py-2 pr-3">{fr ? 'Total' : 'Count'}</th>
                <th className="py-2">{fr ? 'Action' : 'Action'}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id} className="border-b last:border-0" data-testid={`suspended-row-${u.id}`}>
                  <td className="py-2 pr-3 font-medium">{u.name || '—'}</td>
                  <td className="py-2 pr-3 text-xs">{u.email}</td>
                  <td className="py-2 pr-3"><Badge variant="outline">{u.province || '—'}</Badge></td>
                  <td className="py-2 pr-3 text-xs text-muted-foreground max-w-[220px] truncate">{u.bidding_suspended_reason || '—'}</td>
                  <td className="py-2 pr-3 text-xs">{u.bidding_suspended_at ? new Date(u.bidding_suspended_at).toLocaleDateString() : '—'}</td>
                  <td className="py-2 pr-3 text-center">{u.bidding_suspension_count ?? 1}</td>
                  <td className="py-2">
                    <Button size="sm" variant="outline" disabled={busy === u.id}
                      onClick={() => reinstate(u.id)} data-testid={`reinstate-btn-${u.id}`}>
                      {busy === u.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <UserCheck className="h-3 w-3 mr-1" />}
                      {fr ? 'Réintégrer' : 'Reinstate'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionShell>
  );
};

// ─── Section 3: Overdue Payments ─────────────────────────────────────
const OverduePayments = () => {
  const fr = useFr();
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API_BASE}/admin/compliance/overdue-payments`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setItems(r.data.items || []);
    } catch { setItems([]); }
  }, []);
  useEffect(() => { load(); }, [load]); // eslint-disable-line

  const act = async (id, action) => {
    setBusy(`${id}:${action}`);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_BASE}/admin/compliance/overdue-payments/${id}/${action}`, {},
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success(fr ? 'Action effectuée' : 'Action completed');
      load();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error((typeof d === 'string' ? d : JSON.stringify(d)) || (fr ? 'Échec' : 'Failed'));
    } finally { setBusy(null); }
  };

  if (items === null) return <Loader2 className="h-4 w-4 animate-spin" />;
  const formatPrice = (n) => (typeof n === 'number') ? `$${n.toFixed(2)}` : '—';

  return (
    <SectionShell
      testid="compliance-section-overdue"
      icon={<RefreshCw className="h-5 w-5 text-orange-600" />}
      title={fr ? '3. Paiements en retard' : '3. Overdue Payments'}
      description={fr ? "Transactions où le paiement automatique a échoué." : 'Transactions where auto-charge has failed.'}
      badge={<Badge variant={items.length ? 'destructive' : 'secondary'}>{items.length}</Badge>}
    >
      {items.length === 0 ? <AllClear fr={fr} /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b">
              <tr className="text-left text-xs uppercase text-muted-foreground">
                <th className="py-2 pr-3">{fr ? 'Annonce' : 'Listing'}</th>
                <th className="py-2 pr-3">{fr ? 'Section' : 'Section'}</th>
                <th className="py-2 pr-3">{fr ? 'Prix' : 'Price'}</th>
                <th className="py-2 pr-3">{fr ? 'En retard depuis' : 'Overdue since'}</th>
                <th className="py-2 pr-3">{fr ? 'Tentatives' : 'Retries'}</th>
                <th className="py-2">{fr ? 'Actions' : 'Actions'}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b last:border-0" data-testid={`overdue-row-${row.id}`}>
                  <td className="py-2 pr-3 font-medium truncate max-w-[200px]">{row.title || '—'}</td>
                  <td className="py-2 pr-3"><Badge variant="outline">{row.section}</Badge></td>
                  <td className="py-2 pr-3">{formatPrice(row.final_price || row.hammer_price || row.current_price)}</td>
                  <td className="py-2 pr-3 text-xs">{row.payment_overdue_at ? new Date(row.payment_overdue_at).toLocaleDateString() : '—'}</td>
                  <td className="py-2 pr-3 text-center">{row.auto_charge_retry_count ?? 0}</td>
                  <td className="py-2 flex flex-wrap gap-1">
                    <Button size="sm" variant="outline" disabled={!!busy}
                      onClick={() => act(row.id, 'retry')} data-testid={`overdue-retry-${row.id}`}>
                      {busy === `${row.id}:retry` ? <Loader2 className="h-3 w-3 animate-spin" /> : (fr ? 'Réessayer' : 'Retry')}
                    </Button>
                    <Button size="sm" variant="outline" disabled={!!busy}
                      onClick={() => act(row.id, 'mark-resolved')} data-testid={`overdue-resolve-${row.id}`}>
                      {fr ? 'Résolu' : 'Resolved'}
                    </Button>
                    <Button size="sm" variant="destructive" disabled={!!busy}
                      onClick={() => act(row.id, 'flag-account')} data-testid={`overdue-flag-${row.id}`}>
                      {fr ? 'Suspendre' : 'Flag'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionShell>
  );
};

// ─── Section 4: Escalated Disputes ───────────────────────────────────
const EscalatedDisputes = () => {
  const fr = useFr();
  const [items, setItems] = useState(null);
  const [noteFor, setNoteFor] = useState(null);
  const [noteText, setNoteText] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API_BASE}/admin/compliance/escalated-disputes`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setItems(r.data.items || []);
    } catch { setItems([]); }
  }, []);
  useEffect(() => { load(); }, [load]); // eslint-disable-line

  const saveNote = async () => {
    if (!noteText.trim()) return;
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_BASE}/admin/compliance/escalated-disputes/${noteFor}/note`,
        { note: noteText }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(fr ? 'Note ajoutée' : 'Note added');
      setNoteFor(null); setNoteText(''); load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Échec' : 'Failed'));
    } finally { setSaving(false); }
  };

  if (items === null) return <Loader2 className="h-4 w-4 animate-spin" />;

  return (
    <SectionShell
      testid="compliance-section-disputes"
      icon={<ScrollText className="h-5 w-5 text-purple-600" />}
      title={fr ? '4. Litiges escaladés' : '4. Escalated Disputes'}
      description={fr ? "Litiges urgents nécessitant une décision admin." : 'Urgent disputes needing admin decision.'}
      badge={<Badge variant={items.length ? 'destructive' : 'secondary'}>{items.length}</Badge>}
    >
      {items.length === 0 ? <AllClear fr={fr} /> : (
        <div className="space-y-3">
          {items.map((d) => (
            <div key={d.id} className="p-3 rounded-lg border bg-slate-50 dark:bg-slate-900/40" data-testid={`dispute-row-${d.id}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">{d.listing_title || '—'}</p>
                  <p className="text-xs text-muted-foreground">
                    {fr ? 'Acheteur' : 'Buyer'}: {d.buyer_name || '—'} • {fr ? 'Vendeur' : 'Seller'}: {d.seller_name || '—'} • ${(d.hammer_price ?? 0).toFixed(2)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {fr ? 'Escaladé' : 'Escalated'}: {d.escalated_at ? new Date(d.escalated_at).toLocaleString() : '—'}
                  </p>
                </div>
                <Button size="sm" variant="outline"
                  onClick={() => { setNoteFor(d.id); setNoteText(''); }}
                  data-testid={`dispute-add-note-${d.id}`}>
                  {fr ? 'Ajouter une note' : 'Add Note'}
                </Button>
              </div>
              {Array.isArray(d.admin_notes) && d.admin_notes.length > 0 && (
                <div className="mt-2 space-y-1">
                  {d.admin_notes.slice(-3).map((n, i) => (
                    <div key={i} className="text-xs p-2 rounded bg-white dark:bg-slate-800 border">
                      <span className="font-semibold">{n.admin_name}</span> <span className="text-muted-foreground">{new Date(n.ts).toLocaleString()}</span>
                      <p>{n.note}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <Dialog open={!!noteFor} onOpenChange={(o) => !o && setNoteFor(null)}>
        <DialogContent data-testid="dispute-note-dialog">
          <DialogHeader>
            <DialogTitle>{fr ? 'Ajouter une note admin' : 'Add Admin Note'}</DialogTitle>
          </DialogHeader>
          <Textarea value={noteText} onChange={(e) => setNoteText(e.target.value)}
            placeholder={fr ? 'Vos observations…' : 'Your observations…'}
            data-testid="dispute-note-textarea" rows={4} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setNoteFor(null)}>{fr ? 'Annuler' : 'Cancel'}</Button>
            <Button onClick={saveNote} disabled={saving || !noteText.trim()} data-testid="dispute-note-save-btn">
              {saving && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
              {fr ? 'Enregistrer' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SectionShell>
  );
};

// ─── Section 5: Bill 96 Violations ───────────────────────────────────
const Bill96Violations = () => {
  const fr = useFr();
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API_BASE}/admin/compliance/bill96-violations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setItems(r.data.items || []);
    } catch { setItems([]); }
  }, []);
  useEffect(() => { load(); }, [load]); // eslint-disable-line

  const notify = async (id) => {
    setBusy(id);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_BASE}/admin/compliance/bill96-violations/${id}/notify`, {},
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success(fr ? 'Vendeur notifié — 48 h pour corriger' : 'Seller notified — 48h to fix');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Échec' : 'Failed'));
    } finally { setBusy(null); }
  };

  if (items === null) return <Loader2 className="h-4 w-4 animate-spin" />;

  return (
    <SectionShell
      testid="compliance-section-bill96"
      icon={<Shield className="h-5 w-5 text-blue-600" />}
      title={fr ? '5. Conformité Loi 96' : '5. Bill 96 Compliance'}
      description={fr ? "Annonces QC sans titre français — auto-suspension après 48 h."
        : 'QC listings missing French title — auto-suspended 48h after notification.'}
      badge={<Badge variant={items.length ? 'destructive' : 'secondary'}>{items.length}</Badge>}
    >
      {items.length === 0 ? <AllClear fr={fr} /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b">
              <tr className="text-left text-xs uppercase text-muted-foreground">
                <th className="py-2 pr-3">{fr ? 'Titre (EN)' : 'Title (EN)'}</th>
                <th className="py-2 pr-3">{fr ? 'Section' : 'Section'}</th>
                <th className="py-2 pr-3">{fr ? 'Vendeur' : 'Seller'}</th>
                <th className="py-2 pr-3">{fr ? 'Listé le' : 'Listed'}</th>
                <th className="py-2 pr-3">{fr ? 'Notifié' : 'Notified'}</th>
                <th className="py-2">{fr ? 'Actions' : 'Actions'}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b last:border-0" data-testid={`bill96-row-${row.id}`}>
                  <td className="py-2 pr-3 font-medium truncate max-w-[200px]">{row.title || '—'}</td>
                  <td className="py-2 pr-3"><Badge variant="outline">{row.section}</Badge></td>
                  <td className="py-2 pr-3 text-xs">{row.seller_name || row.seller_id || '—'}</td>
                  <td className="py-2 pr-3 text-xs">{row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}</td>
                  <td className="py-2 pr-3 text-xs">{row.bill96_notified_at
                    ? new Date(row.bill96_notified_at).toLocaleDateString()
                    : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="py-2 flex flex-wrap gap-1">
                    <a href={`/listings/${row.id}/edit`} target="_blank" rel="noreferrer"
                       data-testid={`bill96-edit-${row.id}`}>
                      <Button size="sm" variant="outline">
                        <FileEdit className="h-3 w-3 mr-1" />
                        {fr ? 'Modifier' : 'Edit'}
                        <ExternalLink className="h-3 w-3 ml-1" />
                      </Button>
                    </a>
                    <Button size="sm" variant="outline" disabled={busy === row.id}
                      onClick={() => notify(row.id)} data-testid={`bill96-notify-${row.id}`}>
                      {busy === row.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Bell className="h-3 w-3 mr-1" />}
                      {fr ? 'Notifier' : 'Notify'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionShell>
  );
};

// ─── Page Wrapper ────────────────────────────────────────────────────
const AdminCompliancePage = () => {
  const fr = useFr();
  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4 sm:p-6" data-testid="admin-compliance-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {fr ? 'Conformité' : 'Compliance'}
        </h1>
        <p className="text-muted-foreground">
          {fr ? 'Centre de contrôle de conformité — actions admin en un clic.'
            : 'Single-page compliance command center — one-click admin actions.'}
        </p>
      </div>
      <FlaggedListings />
      <BiddingSuspended />
      <OverduePayments />
      <EscalatedDisputes />
      <Bill96Violations />
    </div>
  );
};

export default AdminCompliancePage;
