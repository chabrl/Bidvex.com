/**
 * AdminStorageAuctions — iter173
 * ================================
 * Admin-only dashboard for:
 *   1. Listing ALL storage auctions across all facilities
 *   2. Creating a new storage auction on behalf of any facility
 *      (bypasses the "verified-facility-owner" guard)
 *   3. Quick actions: force-close, cancel
 *
 * Uses existing backend endpoints:
 *   GET  /api/admin/storage-auctions?status=active|upcoming|sold|unsold|cancelled
 *   POST /api/admin/storage-auctions?facility_id={id}
 *   PUT  /api/admin/storage-auctions/{id}/cancel
 *   GET  /api/admin/storage-facilities
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import {
  Loader2, Plus, Package, AlertTriangle, Ban, ShieldCheck,
} from 'lucide-react';

const API = API_BASE;

const UNIT_SIZES = ['5x5', '5x10', '10x10', '10x15', '10x20', '10x30+'];
const UNIT_TYPES = ['indoor', 'outdoor', 'climate_controlled', 'drive_up'];
const PAYMENT_METHODS = ['stripe', 'cash', 'etransfer'];

const STATUS_STYLES = {
  active:    'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  upcoming:  'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200',
  sold:      'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  unsold:    'bg-slate-100 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300',
  cancelled: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200',
};

const AdminStorageAuctions = () => {
  const { token } = useAuth();
  const [auctions, setAuctions] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);

  const authHeaders = { headers: { Authorization: `Bearer ${token}` } };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const qs = statusFilter !== 'all' ? `?status=${statusFilter}` : '';
      const [a, f] = await Promise.all([
        axios.get(`${API}/admin/storage-auctions${qs}`, authHeaders),
        axios.get(`${API}/admin/storage-facilities`, authHeaders),
      ]);
      setAuctions(a.data?.auctions || a.data || []);
      setFacilities(f.data?.facilities || f.data || []);
    } catch (e) {
      toast.error('Failed to load · Échec du chargement');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = auctions.filter(a => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      (a.unit_number || '').toLowerCase().includes(q) ||
      (a.facility_name || '').toLowerCase().includes(q) ||
      (a.facility_city || '').toLowerCase().includes(q)
    );
  });

  const handleCancel = async (auction_id) => {
    if (!window.confirm('Cancel this auction? · Annuler cette enchère ?')) return;
    try {
      await axios.put(`${API}/admin/storage-auctions/${auction_id}/cancel`, {}, authHeaders);
      toast.success('Auction cancelled · Enchère annulée');
      fetchData();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Cancel failed');
    }
  };

  return (
    <div data-testid="admin-storage-auctions">
      <Card className="rounded-2xl bg-white/70 dark:bg-slate-800/50 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5 text-blue-600" />
              Storage Auctions · Enchères de stockage
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Manage all storage auctions across all facilities · Gérez toutes les enchères
            </p>
          </div>
          <Button
            onClick={() => setCreateOpen(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white"
            data-testid="admin-create-storage-auction-btn"
          >
            <Plus className="h-4 w-4 mr-1" />
            Create Auction · Créer une enchère
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filter bar */}
          <div className="flex gap-2 flex-wrap">
            <Input
              placeholder="Search unit/facility · Rechercher"
              value={filter}
              onChange={e => setFilter(e.target.value)}
              className="max-w-xs"
              data-testid="admin-storage-auction-filter"
            />
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-44" data-testid="admin-storage-status-filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="upcoming">Upcoming</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="sold">Sold</SelectItem>
                <SelectItem value="unsold">Unsold</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Table */}
          {loading ? (
            <div className="py-10 flex justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>
          ) : filtered.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground text-sm">
              No auctions found · Aucune enchère trouvée
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase text-muted-foreground border-b">
                  <tr>
                    <th className="text-left p-2">Unit · Unité</th>
                    <th className="text-left p-2">Facility · Facilité</th>
                    <th className="text-left p-2">Current · Actuel</th>
                    <th className="text-left p-2">Bids</th>
                    <th className="text-left p-2">Status · Statut</th>
                    <th className="text-left p-2">Pickup code</th>
                    <th className="text-right p-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(a => (
                    <tr key={a.id} className="border-b hover:bg-slate-50 dark:hover:bg-slate-900/50" data-testid={`admin-storage-auction-row-${a.id}`}>
                      <td className="p-2 font-semibold">#{a.unit_number}<div className="text-[10px] text-muted-foreground">{a.unit_size} · {a.unit_type}</div></td>
                      <td className="p-2">{a.facility_name || '—'}<div className="text-[10px] text-muted-foreground">{a.facility_city}, {a.facility_province}</div></td>
                      <td className="p-2">${Number(a.current_bid || 0).toLocaleString()}</td>
                      <td className="p-2">{a.bid_count || 0}</td>
                      <td className="p-2">
                        <Badge className={STATUS_STYLES[a.status] || 'bg-slate-100'}>{a.status}</Badge>
                      </td>
                      <td className="p-2 font-mono text-xs">{a.pickup_code || '—'}</td>
                      <td className="p-2 text-right">
                        {['upcoming', 'active'].includes(a.status) && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-red-300 text-red-700 hover:bg-red-50"
                            onClick={() => handleCancel(a.id)}
                            data-testid={`admin-cancel-auction-${a.id}`}
                          >
                            <Ban className="h-3 w-3 mr-1" /> Cancel · Annuler
                          </Button>
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

      <CreateStorageAuctionDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        facilities={facilities}
        onCreated={() => { setCreateOpen(false); fetchData(); }}
      />
    </div>
  );
};

// ───────────────────────────────────────
// Create dialog
// ───────────────────────────────────────
const CreateStorageAuctionDialog = ({ open, onOpenChange, facilities, onCreated }) => {
  const { token } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    facility_id: '',
    unit_number: '',
    unit_size: '10x10',
    unit_type: 'indoor',
    is_lien_unit: false,
    description_en: '',
    description_fr: '',
    starting_price: 10,
    bid_increment: 10,
    start_time: '',
    end_time: '',
    payment_method: 'cash',
    deposit_required: false,
    deposit_amount: 0,
    cleanup_deadline_hours: 72,
    soft_close_enabled: true,
    soft_close_extension_minutes: 2,
  });

  // Reset when opened
  useEffect(() => {
    if (open) {
      const now = new Date();
      const start = new Date(now.getTime() + 60 * 60 * 1000); // +1h
      const end = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000); // +7d
      setForm(f => ({
        ...f,
        start_time: start.toISOString().slice(0, 16),
        end_time: end.toISOString().slice(0, 16),
      }));
    }
  }, [open]);

  const set = (k) => (v) => setForm(f => ({ ...f, [k]: v }));
  const setE = (k) => (e) => set(k)(e.target.value);

  const handleSubmit = async () => {
    if (!form.facility_id) {
      toast.error('Pick a facility · Choisissez une facilité');
      return;
    }
    if (!form.unit_number || !form.description_en || !form.start_time || !form.end_time) {
      toast.error('Fill required fields · Remplissez les champs requis');
      return;
    }
    if (form.deposit_required && (!form.deposit_amount || form.deposit_amount <= 0)) {
      toast.error('Deposit amount must be > 0 · Le montant du dépôt doit être > 0');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        starting_price: Number(form.starting_price),
        bid_increment: Number(form.bid_increment),
        deposit_amount: Number(form.deposit_amount || 0),
        cleanup_deadline_hours: Number(form.cleanup_deadline_hours),
        soft_close_extension_minutes: Number(form.soft_close_extension_minutes),
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
      };
      const facility_id = form.facility_id;
      // API expects facility_id as query param
      delete payload.facility_id;
      await axios.post(
        `${API}/admin/storage-auctions?facility_id=${facility_id}`,
        payload,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Auction created · Enchère créée');
      onCreated?.();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'object' ? (detail.message_en || JSON.stringify(detail)) : (detail || 'Create failed');
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="admin-create-storage-dialog">
        <DialogHeader>
          <DialogTitle>
            Create Storage Auction · Créer une enchère de stockage
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            Admin mode — creating on behalf of a facility · Mode admin
          </p>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label>Facility · Facilité *</Label>
            <Select value={form.facility_id} onValueChange={set('facility_id')}>
              <SelectTrigger data-testid="admin-create-facility-select">
                <SelectValue placeholder="Pick a facility · Choisissez" />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                {facilities.map(f => (
                  <SelectItem key={f.id} value={f.id}>
                    {f.company_name} — {f.city}, {f.province} ({f.status || 'unverified'})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Unit # · Numéro d'unité *</Label>
            <Input value={form.unit_number} onChange={setE('unit_number')} data-testid="admin-create-unit-number" />
          </div>
          <div>
            <Label>Unit size · Taille</Label>
            <Select value={form.unit_size} onValueChange={set('unit_size')}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {UNIT_SIZES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Unit type · Type</Label>
            <Select value={form.unit_type} onValueChange={set('unit_type')}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {UNIT_TYPES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Payment method · Mode de paiement</Label>
            <Select value={form.payment_method} onValueChange={set('payment_method')}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {PAYMENT_METHODS.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Starting price · Mise de départ</Label>
            <Input type="number" min="0" value={form.starting_price} onChange={setE('starting_price')} />
          </div>
          <div>
            <Label>Bid increment · Incrément</Label>
            <Input type="number" min="1" value={form.bid_increment} onChange={setE('bid_increment')} />
          </div>

          <div>
            <Label>Start (local) · Début *</Label>
            <Input type="datetime-local" value={form.start_time} onChange={setE('start_time')} data-testid="admin-create-start-time" />
          </div>
          <div>
            <Label>End (local) · Fin *</Label>
            <Input type="datetime-local" value={form.end_time} onChange={setE('end_time')} data-testid="admin-create-end-time" />
          </div>

          <div className="col-span-2">
            <Label>Description (English) *</Label>
            <Textarea rows={2} value={form.description_en} onChange={setE('description_en')} data-testid="admin-create-description-en" />
          </div>
          <div className="col-span-2">
            <Label>Description (Français)</Label>
            <Textarea rows={2} value={form.description_fr} onChange={setE('description_fr')} />
          </div>

          <div className="col-span-2 flex items-center gap-2">
            <input
              type="checkbox"
              id="deposit_required"
              checked={form.deposit_required}
              onChange={e => set('deposit_required')(e.target.checked)}
            />
            <Label htmlFor="deposit_required">Require participation deposit · Exiger un dépôt</Label>
          </div>
          {form.deposit_required && (
            <div className="col-span-2">
              <Label>Deposit amount (CAD) · Montant</Label>
              <Input type="number" min="1" value={form.deposit_amount} onChange={setE('deposit_amount')} />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel · Annuler
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting}
            className="bg-blue-600 hover:bg-blue-700 text-white"
            data-testid="admin-create-storage-submit"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <ShieldCheck className="h-4 w-4 mr-1" />}
            Create · Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AdminStorageAuctions;
