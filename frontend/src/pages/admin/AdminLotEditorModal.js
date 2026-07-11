import React, { useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { Edit2, Loader2, ArrowLeft, X } from 'lucide-react';

const API = API_BASE;

/**
 * iter343 BUG-4 — Admin per-lot editor for multi-lot auctions.
 * Works for BOTH general lots (multi_item_listings) and vehicle
 * multi-lot events (vehicle_multi_lot_auctions). Every save hits the
 * admin lot-edit endpoint, which writes a field-level diff to Admin Logs.
 */
const LOT_FIELDS = [
  { key: 'title',            label: 'Title (EN)',       type: 'text' },
  { key: 'title_fr',         label: 'Title (FR)',       type: 'text' },
  { key: 'description',      label: 'Description',      type: 'textarea' },
  { key: 'category',         label: 'Category',         type: 'text' },
  { key: 'quantity',         label: 'Quantity',         type: 'number', int: true },
  { key: 'starting_price',   label: 'Starting Price',   type: 'number' },
  { key: 'reserve_price',    label: 'Reserve Price',    type: 'number' },
  { key: 'bid_increment',    label: 'Bid Increment',    type: 'number' },
  { key: 'condition',        label: 'Condition',        type: 'text' },
  { key: 'location',         label: 'Location',         type: 'text' },
];

const VEHICLE_EXTRA_FIELDS = [
  { key: 'year',              label: 'Year',      type: 'number', int: true },
  { key: 'make',              label: 'Make',      type: 'text' },
  { key: 'model',             label: 'Model',     type: 'text' },
  { key: 'vin',               label: 'VIN',       type: 'text' },
  { key: 'mileage',           label: 'Mileage',   type: 'number', int: true },
  { key: 'location_city',     label: 'City',      type: 'text' },
  { key: 'location_province', label: 'Province',  type: 'text' },
];

const errText = (e, fallback) => {
  const d = e?.response?.data?.detail;
  if (typeof d === 'string') return d;
  return d?.message_en || d?.message || fallback;
};

export default function AdminLotEditorModal({ open, onOpenChange, listing, headers }) {
  const isVehicle = listing?._section === 'vehicle_multi' || listing?._section === 'vehicle_multi_lot';
  const [loading, setLoading] = useState(false);
  const [lots, setLots] = useState([]);
  const [editingLot, setEditingLot] = useState(null);
  const [form, setForm] = useState({});
  const [images, setImages] = useState([]);
  const [saving, setSaving] = useState(false);

  const fetchLots = async () => {
    if (!listing?.id) return;
    setLoading(true);
    try {
      const url = isVehicle
        ? `${API}/vehicle-multi-lot-auctions/${listing.id}`
        : `${API}/multi-item-listings/${listing.id}`;
      const r = await axios.get(url, { headers });
      const doc = r.data?.event || r.data?.listing || r.data;
      setLots(Array.isArray(doc?.lots) ? doc.lots : []);
    } catch (e) {
      toast.error(errText(e, 'Failed to load lots'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) { setEditingLot(null); fetchLots(); }
    // eslint-disable-next-line
  }, [open, listing?.id]);

  const fields = isVehicle ? [...LOT_FIELDS, ...VEHICLE_EXTRA_FIELDS] : LOT_FIELDS;

  const startEdit = (lot) => {
    const f = {};
    fields.forEach(({ key }) => { f[key] = lot[key] ?? ''; });
    setForm(f);
    setImages(Array.isArray(lot.images) ? [...lot.images] : []);
    setEditingLot(lot);
  };

  const saveLot = async () => {
    setSaving(true);
    try {
      const body = {};
      fields.forEach(({ key, type, int }) => {
        const v = form[key];
        if (v === '' || v === null || v === undefined) return;
        body[key] = type === 'number' ? (int ? parseInt(v, 10) : parseFloat(v)) : v;
      });
      body.images = images;
      const lotRef = isVehicle ? editingLot.id : editingLot.lot_number;
      const url = isVehicle
        ? `${API}/admin/vehicle-multi-lot-auctions/${listing.id}/lots/${lotRef}`
        : `${API}/admin/multi-item-listings/${listing.id}/lots/${lotRef}`;
      const r = await axios.put(url, body, { headers });
      toast.success(`Lot updated (${(r.data?.updated_fields || []).length} field(s) changed)`);
      setEditingLot(null);
      fetchLots();
    } catch (e) {
      toast.error(errText(e, 'Failed to save lot'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="admin-lot-editor-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Edit2 className="h-5 w-5 text-cyan-600" />
            {editingLot
              ? `Edit Lot ${isVehicle ? (editingLot.lot_number ?? '') : `#${editingLot.lot_number}`}`
              : `Lots in "${listing?.title || 'auction'}"`}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex justify-center py-10"><Loader2 className="h-7 w-7 animate-spin text-cyan-600" /></div>
        ) : editingLot ? (
          <div className="space-y-4">
            <Button variant="ghost" size="sm" onClick={() => setEditingLot(null)} data-testid="lot-editor-back-btn">
              <ArrowLeft className="h-4 w-4 mr-1" /> Back to lots
            </Button>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {fields.map(({ key, label, type }) => (
                <div key={key} className={type === 'textarea' ? 'sm:col-span-2' : ''}>
                  <Label htmlFor={`lot-field-${key}`}>{label}</Label>
                  {type === 'textarea' ? (
                    <Textarea
                      id={`lot-field-${key}`}
                      data-testid={`lot-field-${key}`}
                      rows={3}
                      value={form[key] ?? ''}
                      onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    />
                  ) : (
                    <Input
                      id={`lot-field-${key}`}
                      data-testid={`lot-field-${key}`}
                      type={type}
                      value={form[key] ?? ''}
                      onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    />
                  )}
                </div>
              ))}
            </div>
            <div>
              <Label>Photos (URLs)</Label>
              <div className="space-y-2 mt-1">
                {images.map((u, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <img src={u} alt="" className="h-10 w-10 rounded object-cover border" />
                    <span className="text-xs text-slate-500 truncate flex-1">{u}</span>
                    <Button variant="ghost" size="sm" onClick={() => setImages((im) => im.filter((_, idx) => idx !== i))}>
                      <X className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                ))}
                <Input
                  placeholder="Paste image URL and press Enter"
                  data-testid="lot-field-add-image"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && e.target.value.trim()) {
                      setImages((im) => [...im, e.target.value.trim()].slice(0, 30));
                      e.target.value = '';
                      e.preventDefault();
                    }
                  }}
                />
              </div>
            </div>
            <Button onClick={saveLot} disabled={saving} className="w-full" data-testid="lot-editor-save-btn">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Save Lot Changes
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            {lots.length === 0 && (
              <p className="text-sm text-slate-500 text-center py-6">No lots found in this auction.</p>
            )}
            {lots.map((lot) => (
              <div
                key={lot.id || lot.lot_number}
                className="flex items-center justify-between gap-3 border rounded-lg p-3"
                data-testid={`lot-row-${lot.lot_number ?? lot.id}`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">Lot #{lot.lot_number ?? '—'}</Badge>
                    <span className="font-medium truncate">
                      {lot.title || `${lot.year || ''} ${lot.make || ''} ${lot.model || ''}`.trim() || 'Untitled lot'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Qty: {lot.quantity ?? 1} · Start: ${lot.starting_price ?? 0} · Bids: {lot.bid_count ?? 0} · {lot.status || '—'}
                  </p>
                </div>
                <Button size="sm" variant="outline" onClick={() => startEdit(lot)} data-testid={`edit-lot-btn-${lot.lot_number ?? lot.id}`}>
                  <Edit2 className="h-4 w-4 mr-1" /> Edit Lot
                </Button>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
