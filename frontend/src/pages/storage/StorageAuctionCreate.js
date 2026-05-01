import API_BASE from '../../config';
import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { Loader2, Upload, ImagePlus } from 'lucide-react';

const API = API_BASE;
const SIZES = ['5x5', '5x10', '10x10', '10x15', '10x20', '10x30+'];
const TYPES = [
  { v: 'indoor', en: 'Indoor', fr: 'Intérieur' },
  { v: 'outdoor', en: 'Outdoor', fr: 'Extérieur' },
  { v: 'climate_controlled', en: 'Climate Controlled', fr: 'Climatisé' },
  { v: 'drive_up', en: 'Drive-Up', fr: 'Accès véhicule' },
];

const StorageAuctionCreate = () => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const isFr = (i18n.language || '').startsWith('fr');

  const [form, setForm] = useState({
    unit_number: '', unit_size: '10x10', unit_type: 'indoor',
    is_lien_unit: false, past_due_balance: '',
    description_en: '', description_fr: '',
    photos: [], video_url: '',
    starting_price: 1, reserve_price: '', bid_increment: 10,
    start_time: '', end_time: '',
    cleanup_deadline_hours: 72, cleanup_deposit: 0,
    payment_methods_accepted: ['stripe', 'cash', 'etransfer'],
    soft_close_enabled: true, soft_close_extension_minutes: 10,
  });
  const [submitting, setSubmitting] = useState(false);
  const [uploadingIdx, setUploadingIdx] = useState(false);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const togglePM = (m) => setForm(p => ({
    ...p,
    payment_methods_accepted: p.payment_methods_accepted.includes(m)
      ? p.payment_methods_accepted.filter(x => x !== m)
      : [...p.payment_methods_accepted, m],
  }));

  const uploadPhotos = async (files) => {
    setUploadingIdx(true);
    const urls = [];
    try {
      for (const f of files) {
        const fd = new FormData();
        fd.append('file', f);
        const res = await axios.post(`${API}/storage-facilities/upload-photo`, fd, {
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
        });
        if (res.data?.url) urls.push(res.data.url);
      }
      set('photos', [...form.photos, ...urls].slice(0, 10));
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploadingIdx(false);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.start_time || !form.end_time) { toast.error('Set start & end times'); return; }
    if (new Date(form.start_time) >= new Date(form.end_time)) {
      toast.error(isFr ? 'L\'heure de fin doit être après le début' : 'End time must be after start time');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        starting_price: parseFloat(form.starting_price) || 1,
        reserve_price: form.reserve_price ? parseFloat(form.reserve_price) : null,
        past_due_balance: form.past_due_balance ? parseFloat(form.past_due_balance) : null,
        bid_increment: parseFloat(form.bid_increment) || 10,
        cleanup_deposit: parseFloat(form.cleanup_deposit) || 0,
        cleanup_deadline_hours: parseInt(form.cleanup_deadline_hours) || 72,
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
      };
      const res = await axios.post(`${API}/storage-facilities/auctions`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(isFr ? 'Enchère créée' : 'Auction created');
      navigate(`/storage-auctions/${res.data.id}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to create');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-8" data-testid="storage-auction-create">
      <div className="max-w-3xl mx-auto px-4">
        <h1 className="text-2xl font-bold mb-1">{isFr ? 'Nouvelle enchère' : 'Create New Auction'}</h1>
        <p className="text-sm text-muted-foreground mb-6">{isFr ? 'Liste un nouveau casier d\'entreposage' : 'List a new storage unit for auction'}</p>
        <Card className="p-6">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>{isFr ? 'Numéro d\'unité' : 'Unit Number'} *</Label>
                <Input required value={form.unit_number} onChange={e => set('unit_number', e.target.value)} placeholder="A-12" />
              </div>
              <div>
                <Label>{isFr ? 'Taille' : 'Size'} *</Label>
                <Select value={form.unit_size} onValueChange={v => set('unit_size', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{SIZES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>{isFr ? 'Type' : 'Type'} *</Label>
                <Select value={form.unit_type} onValueChange={v => set('unit_type', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{TYPES.map(t => <SelectItem key={t.v} value={t.v}>{isFr ? t.fr : t.en}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-950/30 rounded-lg">
              <Checkbox checked={form.is_lien_unit} onCheckedChange={v => set('is_lien_unit', v === true)} className="mt-0.5" />
              <div className="flex-1">
                <Label className="cursor-pointer">{isFr ? 'Unité sous droit de rétention' : 'Lien Unit'}</Label>
                <p className="text-[11px] text-muted-foreground">{isFr ? 'Locataire en défaut de paiement.' : 'Tenant in default of payment.'}</p>
                {form.is_lien_unit && (
                  <Input className="mt-2" type="number" step="0.01" placeholder={isFr ? 'Solde dû' : 'Past due balance'}
                    value={form.past_due_balance} onChange={e => set('past_due_balance', e.target.value)} />
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>{isFr ? 'Description (EN)' : 'Description (EN)'} *</Label>
                <Textarea required rows={3} value={form.description_en} onChange={e => set('description_en', e.target.value)} />
              </div>
              <div>
                <Label>{isFr ? 'Description (FR)' : 'Description (FR)'}</Label>
                <Textarea rows={3} value={form.description_fr} onChange={e => set('description_fr', e.target.value)} />
              </div>
            </div>

            {/* Photos */}
            <div>
              <Label>{isFr ? 'Photos (max 10)' : 'Photos (max 10)'}</Label>
              <div className="flex gap-2 flex-wrap mt-2">
                {form.photos.map((url, i) => (
                  <div key={i} className="relative w-20 h-20 rounded-lg overflow-hidden border">
                    <img src={url} alt={`photo ${i}`} className="w-full h-full object-cover" />
                    <button type="button" onClick={() => set('photos', form.photos.filter((_, j) => j !== i))}
                      className="absolute top-0 right-0 bg-red-500 text-white text-xs w-5 h-5">×</button>
                  </div>
                ))}
                {form.photos.length < 10 && (
                  <label className="w-20 h-20 border-2 border-dashed rounded-lg flex items-center justify-center cursor-pointer hover:border-blue-500">
                    {uploadingIdx ? <Loader2 className="h-5 w-5 animate-spin" /> : <ImagePlus className="h-5 w-5" />}
                    <input type="file" accept="image/*" multiple className="hidden"
                      onChange={e => uploadPhotos(Array.from(e.target.files || []))} />
                  </label>
                )}
              </div>
            </div>

            <div>
              <Label>{isFr ? 'URL vidéo (optionnel)' : 'Video URL (optional)'}</Label>
              <Input type="url" value={form.video_url} onChange={e => set('video_url', e.target.value)} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>{isFr ? 'Prix de départ' : 'Starting Price'} *</Label>
                <Input type="number" step="0.01" required value={form.starting_price} onChange={e => set('starting_price', e.target.value)} />
              </div>
              <div>
                <Label>{isFr ? 'Prix de réserve' : 'Reserve Price'}</Label>
                <Input type="number" step="0.01" value={form.reserve_price} onChange={e => set('reserve_price', e.target.value)} />
              </div>
              <div>
                <Label>{isFr ? 'Incrément' : 'Bid Increment'}</Label>
                <Input type="number" step="1" value={form.bid_increment} onChange={e => set('bid_increment', e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>{isFr ? 'Début' : 'Start time'} *</Label>
                <Input type="datetime-local" required value={form.start_time} onChange={e => set('start_time', e.target.value)} />
              </div>
              <div>
                <Label>{isFr ? 'Fin' : 'End time'} *</Label>
                <Input type="datetime-local" required value={form.end_time} onChange={e => set('end_time', e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>{isFr ? 'Délai de nettoyage (heures après fin)' : 'Cleanup deadline (hours after end)'}</Label>
                <Input type="number" min="24" max="168" value={form.cleanup_deadline_hours} onChange={e => set('cleanup_deadline_hours', e.target.value)} />
              </div>
              <div>
                <Label>{isFr ? 'Dépôt de nettoyage' : 'Cleaning deposit'}</Label>
                <Input type="number" step="0.01" value={form.cleanup_deposit} onChange={e => set('cleanup_deposit', e.target.value)} />
              </div>
            </div>

            <div>
              <Label className="block mb-2">{isFr ? 'Modes de paiement acceptés' : 'Payment methods accepted'}</Label>
              <div className="flex gap-3">
                {['stripe', 'cash', 'etransfer'].map(m => (
                  <label key={m} className="flex items-center gap-1.5 text-sm cursor-pointer">
                    <Checkbox checked={form.payment_methods_accepted.includes(m)} onCheckedChange={() => togglePM(m)} />
                    <span className="capitalize">{m}</span>
                  </label>
                ))}
              </div>
            </div>

            <Button type="submit" disabled={submitting} className="w-full bg-blue-600 hover:bg-blue-700 text-white" data-testid="create-auction-submit">
              {submitting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Upload className="h-4 w-4 mr-1" />}
              {isFr ? 'Publier l\'enchère' : 'Publish auction'}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default StorageAuctionCreate;
