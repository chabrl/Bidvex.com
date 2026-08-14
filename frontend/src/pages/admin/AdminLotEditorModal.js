/**
 * iter483.3 — Admin Lot Editor Modal (responsive · S3 uploader · reserve)
 * =======================================================================
 *
 * Admin-only per-lot editor for multi-lot auctions (marketplace + vehicle).
 * Fully responsive grid: one card per lot, no horizontal scroll.
 * Each lot card supports drag-and-drop image upload via
 * POST /api/uploads/listing-image (existing S3 endpoint).
 *
 * Reserve Price field is admin-only, hidden from buyer views.
 * Saved via PATCH /api/admin/lots/reserve-price (iter483.3).
 */
import React, { useEffect, useState, useRef, useMemo } from 'react';
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
import {
  Edit2, Loader2, ArrowLeft, X, Upload, DollarSign, Save,
} from 'lucide-react';

const API = API_BASE;

const LOT_FIELDS = [
  { key: 'title',            label: 'Title (EN)',       type: 'text' },
  { key: 'title_fr',         label: 'Title (FR)',       type: 'text' },
  { key: 'description',      label: 'Description',      type: 'textarea' },
  { key: 'category',         label: 'Category',         type: 'text' },
  { key: 'quantity',         label: 'Quantity',         type: 'number', int: true },
  { key: 'starting_price',   label: 'Starting Price',   type: 'number' },
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

const ACCEPTED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
const MAX_BYTES = 10 * 1024 * 1024;

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
  const [reservePrice, setReservePrice] = useState('');
  const [saving, setSaving] = useState(false);
  const [uploads, setUploads] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const fields = useMemo(() =>
    isVehicle ? [...LOT_FIELDS, ...VEHICLE_EXTRA_FIELDS] : LOT_FIELDS,
    [isVehicle]);

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
    if (open) { setEditingLot(null); setUploads([]); fetchLots(); }
    // eslint-disable-next-line
  }, [open, listing?.id]);

  const startEdit = (lot) => {
    const f = {};
    fields.forEach(({ key }) => { f[key] = lot[key] ?? ''; });
    setForm(f);
    setImages(Array.isArray(lot.images) ? [...lot.images] : []);
    setReservePrice(lot.reserve_price != null ? String(lot.reserve_price) : '');
    setUploads([]);
    setEditingLot(lot);
  };

  const uploadFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const trackers = files.map((f) => {
      let rejection = null;
      if (!ACCEPTED_TYPES.includes(f.type)) rejection = 'Unsupported file type';
      else if (f.size > MAX_BYTES) rejection = 'File too large (max 10 MB)';
      return {
        id: `${f.name}-${f.size}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: f.name, pct: 0,
        status: rejection ? 'error' : 'uploading',
        error: rejection, file: rejection ? null : f,
      };
    });
    setUploads((prev) => [...prev, ...trackers]);

    trackers.filter((t) => t.status === 'error').forEach((t) =>
      toast.error(`${t.name} — ${t.error}`));

    for (const t of trackers) {
      if (t.status !== 'uploading') continue;
      const form_ = new FormData();
      form_.append('file', t.file);
      try {
        const res = await axios.post(`${API}/uploads/listing-image`, form_, {
          headers: { ...headers, 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (evt) => {
            if (evt.total) {
              const pct = Math.round((evt.loaded * 100) / evt.total);
              setUploads((prev) => prev.map((row) => row.id === t.id ? { ...row, pct } : row));
            }
          },
        });
        const url = res?.data?.url;
        if (!url) throw new Error('missing_url_in_response');
        setImages((im) => [...im, url]);
        setUploads((prev) => prev.map((row) =>
          row.id === t.id ? { ...row, pct: 100, status: 'done' } : row));
      } catch (err) {
        const reason = errText(err, 'Upload failed');
        toast.error(`${t.name} — ${reason}`);
        setUploads((prev) => prev.map((row) =>
          row.id === t.id ? { ...row, status: 'error', error: reason } : row));
      }
    }
  };

  const onDrop = (e) => { e.preventDefault(); setDragActive(false); if (e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files); };
  const onDragOver = (e) => { e.preventDefault(); setDragActive(true); };
  const onDragLeave = (e) => { e.preventDefault(); setDragActive(false); };
  const onPickFile = (e) => { if (e.target.files?.length) uploadFiles(e.target.files); e.target.value = ''; };

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

      // Reserve price is admin-only via the dedicated iter483.3 route.
      const trimmedRp = String(reservePrice).trim();
      const cents = trimmedRp === ''
        ? null
        : Math.round(parseFloat(trimmedRp) * 100);
      if (cents === null || Number.isFinite(cents)) {
        await axios.patch(`${API}/admin/lots/reserve-price`, {
          auction_id: listing.id,
          target: isVehicle ? (editingLot.id || String(editingLot.lot_number)) : String(editingLot.lot_number),
          reserve_price_cents: cents,
        }, { headers });
      }

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
      <DialogContent
        className="p-0 gap-0 max-w-none sm:max-w-3xl lg:max-w-5xl h-[100dvh] sm:h-[90vh] sm:rounded-lg overflow-hidden flex flex-col"
        data-testid="admin-lot-editor-modal"
      >
        <DialogHeader className="p-4 sm:p-6 pb-2 border-b flex-shrink-0">
          <div className="flex items-center justify-between gap-2">
            <DialogTitle className="text-lg font-semibold flex items-center gap-2 truncate">
              <Edit2 className="h-5 w-5 text-cyan-600 flex-shrink-0" />
              <span className="truncate">
                {editingLot
                  ? `Edit Lot ${isVehicle ? (editingLot.lot_number ?? '') : `#${editingLot.lot_number}`}`
                  : `Lots — ${listing?.title || 'auction'}`}
              </span>
            </DialogTitle>
            <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)} aria-label="Close">
              <X className="h-5 w-5" />
            </Button>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {loading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-7 w-7 animate-spin text-cyan-600" />
            </div>
          ) : editingLot ? (
            <div className="space-y-4">
              <Button variant="ghost" size="sm" onClick={() => setEditingLot(null)}
                      data-testid="lot-editor-back-btn">
                <ArrowLeft className="h-4 w-4 mr-1" /> Back to lots
              </Button>

              {/* Field grid (responsive) */}
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

              {/* Reserve price — ADMIN ONLY (iter483.3) */}
              <div className="border-t pt-4">
                <div className="flex items-center gap-2 mb-2">
                  <DollarSign className="h-4 w-4 text-amber-600" />
                  <Label htmlFor="lot-reserve-price" className="font-semibold">
                    Reserve Price (Admin Only — hidden from public)
                  </Label>
                </div>
                <Input
                  id="lot-reserve-price"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="Leave blank to clear reserve"
                  value={reservePrice}
                  onChange={(e) => setReservePrice(e.target.value)}
                  data-testid="lot-field-reserve-price"
                />
                <p className="text-xs text-slate-500 mt-1">
                  If hammer &lt; reserve at close, the lot will be flagged "reserve not met" — NO automatic payment.
                </p>
              </div>

              {/* Image uploader (S3, iter483.3) */}
              <div className="border-t pt-4">
                <Label>Photos</Label>
                <div
                  role="button" tabIndex={0}
                  onClick={() => fileInputRef.current?.click()}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
                  onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}
                  data-testid="admin-lot-uploader-dropzone"
                  className={`border-2 border-dashed rounded-lg p-4 text-center min-h-[110px] flex flex-col justify-center transition ${
                    dragActive
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 cursor-pointer'
                      : 'border-slate-300 hover:border-blue-400 bg-slate-50 dark:bg-slate-800 cursor-pointer'
                  }`}
                >
                  <Upload className="h-6 w-6 mx-auto text-slate-500 mb-1" />
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Drag & drop or click to upload lot photos</p>
                  <p className="text-xs text-slate-500 mt-1">JPG · PNG · WEBP · 10 MB max per file</p>
                  <input
                    ref={fileInputRef} type="file"
                    accept="image/jpeg,image/jpg,image/png,image/webp"
                    multiple onChange={onPickFile}
                    className="hidden"
                    data-testid="admin-lot-uploader-input"
                  />
                </div>

                {uploads.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {uploads.map((u) => (
                      <div key={u.id} className="border rounded p-2 text-xs bg-white dark:bg-slate-900">
                        <div className="flex justify-between mb-0.5">
                          <span className="truncate">{u.name}</span>
                          <span className={u.status === 'error' ? 'text-rose-600' : u.status === 'done' ? 'text-emerald-600' : 'text-slate-500'}>
                            {u.status === 'error' ? u.error : u.status === 'done' ? '✓' : `${u.pct}%`}
                          </span>
                        </div>
                        {u.status === 'uploading' && (
                          <div className="w-full bg-slate-200 rounded-full h-1 overflow-hidden">
                            <div className="bg-blue-600 h-1" style={{ width: `${u.pct}%` }} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {images.length > 0 && (
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mt-3">
                    {images.map((u, i) => (
                      <div key={i} className="relative group">
                        <img src={u} alt="" className="w-full h-20 object-cover rounded" />
                        <Button
                          size="sm" variant="destructive"
                          onClick={() => setImages((im) => im.filter((_, idx) => idx !== i))}
                          className="absolute top-1 right-1 h-6 w-6 p-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition"
                          data-testid={`admin-lot-remove-image-${i}`}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Button onClick={saveLot} disabled={saving} className="w-full sm:w-auto" data-testid="lot-editor-save-btn">
                {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                Save Lot Changes
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {lots.length === 0 && (
                <p className="col-span-full text-sm text-slate-500 text-center py-6">No lots found in this auction.</p>
              )}
              {lots.map((lot) => (
                <div
                  key={lot.id || lot.lot_number}
                  className="border rounded-lg p-3 bg-white dark:bg-slate-900 flex flex-col gap-2"
                  data-testid={`lot-row-${lot.lot_number ?? lot.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline" className="text-xs">Lot #{lot.lot_number ?? '—'}</Badge>
                        {lot.reserve_price != null && (
                          <Badge className="bg-amber-100 text-amber-800 border-amber-300 text-xs">
                            Reserve: ${lot.reserve_price}
                          </Badge>
                        )}
                      </div>
                      <p className="font-medium truncate mt-1">
                        {lot.title || `${lot.year || ''} ${lot.make || ''} ${lot.model || ''}`.trim() || 'Untitled lot'}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Qty: {lot.quantity ?? 1} · Start: ${lot.starting_price ?? 0} · Bids: {lot.bid_count ?? 0} · {lot.status || '—'}
                      </p>
                    </div>
                    {Array.isArray(lot.images) && lot.images[0] && (
                      <img src={lot.images[0]} alt="" className="w-16 h-16 object-cover rounded flex-shrink-0" />
                    )}
                  </div>
                  <Button size="sm" variant="outline"
                          onClick={() => startEdit(lot)}
                          className="w-full sm:w-auto sm:self-end"
                          data-testid={`edit-lot-btn-${lot.lot_number ?? lot.id}`}>
                    <Edit2 className="h-4 w-4 mr-1" /> Edit Lot
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
