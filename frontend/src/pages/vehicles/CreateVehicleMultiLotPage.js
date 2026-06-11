import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Card } from '../../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui/tooltip';
import {
  Plus, Trash2, Save, Calendar, CheckCircle, Loader2, Car, Layers, Waves, Target, Star,
  Upload, ImageIcon, X, ArrowLeft, ArrowRight,
} from 'lucide-react';
import { toast } from 'sonner';
import { TIMING_MODES } from '../../lib/vehicleMultiLotTimingModes';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * CreateVehicleMultiLotPage — iter293 Directive 2 / iter295 P2
 *
 * iter295 P2 additions:
 *   - Per-lot Photo Gallery (S3 upload, ≥1 photo enforced for Live/Schedule,
 *     drag-to-reorder via arrow buttons, 20-photo cap).
 */
const emptyLot = () => ({
  vin: '',
  year: new Date().getFullYear(),
  make: '',
  model: '',
  title: '',
  description: '',
  mileage: 0,
  body_type: 'sedan',
  transmission: 'automatic',
  fuel_type: 'gasoline',
  drivetrain: 'fwd',
  exterior_color: '',
  interior_color: '',
  ownership_status: 'owned',
  title_status: 'clean',
  lien_status: 'clear',
  location_city: '',
  location_province: 'QC',
  location_postal_code: '',
  starting_price: 1000,
  reserve_price: '',
  bid_increment: 100,
  media: [],
});

const CreateVehicleMultiLotPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [event, setEvent] = useState(() => ({
    title: '',
    description: '',
    timing_mode: 'sequential',
    // iter293 — Lazy useState initializer keeps Date.now() out of the
    // render path (react-hooks/purity).
    start_time: new Date(Date.now() + 3600_000).toISOString().slice(0, 16),
    lot_duration_seconds: 120,
    stagger_offset_seconds: 60,
  }));
  const [lots, setLots] = useState([emptyLot()]);

  const addLot = () => setLots(prev => [...prev, emptyLot()]);
  const removeLot = (idx) => setLots(prev => prev.filter((_, i) => i !== idx));
  const updateLot = (idx, patch) => setLots(prev => prev.map((l, i) => i === idx ? { ...l, ...patch } : l));

  // iter295 P2 — Photo staging (client-side until backend has lot ids)
  const MAX_PHOTOS_PER_LOT = 20;
  const onPickFiles = (idx, fileList) => {
    if (!fileList || !fileList.length) return;
    const existing = lots[idx].pendingPhotos || [];
    const room = MAX_PHOTOS_PER_LOT - existing.length;
    if (room <= 0) {
      toast.error(`Maximum ${MAX_PHOTOS_PER_LOT} photos per lot`);
      return;
    }
    const accepted = Array.from(fileList).slice(0, room).filter((f) => f.type.startsWith('image/'));
    if (!accepted.length) {
      toast.error('Please choose image files only');
      return;
    }
    const next = [...existing];
    accepted.forEach((file) => {
      const url = URL.createObjectURL(file);
      next.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, file, previewUrl: url });
    });
    updateLot(idx, { pendingPhotos: next });
  };

  const removePhoto = (lotIdx, photoId) => {
    const pending = (lots[lotIdx].pendingPhotos || []).filter((p) => p.id !== photoId);
    updateLot(lotIdx, { pendingPhotos: pending });
  };

  const movePhoto = (lotIdx, photoId, dir) => {
    const pending = [...(lots[lotIdx].pendingPhotos || [])];
    const at = pending.findIndex((p) => p.id === photoId);
    if (at < 0) return;
    const swap = dir === 'left' ? at - 1 : at + 1;
    if (swap < 0 || swap >= pending.length) return;
    [pending[at], pending[swap]] = [pending[swap], pending[at]];
    updateLot(lotIdx, { pendingPhotos: pending });
  };

  const handleSubmit = async (intent) => {
    // Client validation
    if (!event.title.trim()) { toast.error('Event title is required'); return; }
    if (lots.length === 0) { toast.error('Add at least one lot'); return; }
    for (const [i, lot] of lots.entries()) {
      if (!lot.vin || lot.vin.length !== 17) {
        toast.error(`Lot #${i + 1} — VIN must be exactly 17 characters`);
        return;
      }
      if (!lot.title) {
        toast.error(`Lot #${i + 1} — Title is required`);
        return;
      }
      // iter299 P0 — Bill 96: QC-located lots require a French title.
      if (String(lot.location_province || '').toUpperCase() === 'QC' && !String(lot.title_fr || '').trim()) {
        toast.error(`Lot #${i + 1} — A French title is required for Quebec listings under Bill 96 / Un titre en français est obligatoire (Loi 96)`);
        return;
      }
      if (!lot.location_city || !lot.location_province) {
        toast.error(`Lot #${i + 1} — Location city + province required`);
        return;
      }
      if (!lot.starting_price || Number(lot.starting_price) <= 0) {
        toast.error(`Lot #${i + 1} — Starting price must be > 0`);
        return;
      }
      // iter295 P2 — At least 1 photo per lot when going Live / Schedule.
      if (intent !== 'draft' && (lot.pendingPhotos || []).length === 0) {
        toast.error(`Lot #${i + 1} — At least 1 photo is required to go Live / Schedule`);
        return;
      }
    }

    if (intent === 'schedule') {
      const startMs = new Date(event.start_time).getTime();
      if (!startMs || startMs <= Date.now() + 60_000) {
        toast.error('Schedule requires Start Time ≥1 min in the future');
        return;
      }
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const startISO = new Date(event.start_time).toISOString();
      // iter295 P2 — When photos are present, ALWAYS create the event
      // as draft first so we have lot ids to attach photos to. Then
      // upload photos for each lot, then promote to the requested
      // intent via the activate endpoint.
      const hasAnyPhotos = lots.some((l) => (l.pendingPhotos || []).length > 0);
      const createIntent = (intent !== 'draft' && hasAnyPhotos) ? 'draft' : intent;

      const payload = {
        title: event.title,
        description: event.description,
        timing_mode: event.timing_mode,
        start_time: startISO,
        lot_duration_seconds: Number(event.lot_duration_seconds) || 120,
        stagger_offset_seconds: Number(event.stagger_offset_seconds) || 60,
        submission_intent: createIntent,
        lots: lots.map((l) => ({
          // strip client-only fields
          vin: l.vin,
          year: Number(l.year),
          make: l.make,
          model: l.model,
          title: l.title,
          title_fr: l.title_fr || null,
          description: l.description,
          mileage: Number(l.mileage),
          body_type: l.body_type,
          transmission: l.transmission,
          fuel_type: l.fuel_type,
          drivetrain: l.drivetrain,
          exterior_color: l.exterior_color,
          interior_color: l.interior_color,
          ownership_status: l.ownership_status,
          title_status: l.title_status,
          lien_status: l.lien_status,
          location_city: l.location_city,
          location_province: l.location_province,
          location_postal_code: l.location_postal_code,
          starting_price: Number(l.starting_price),
          reserve_price: l.reserve_price ? Number(l.reserve_price) : null,
          bid_increment: Number(l.bid_increment) || 100,
          media: [],
          condition_report: l.condition_report || null,
        })),
      };
      const r = await axios.post(`${API}/vehicle-multi-lot-auctions`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const eventId = r.data.id;
      const createdLots = r.data.lots || [];

      // iter295 P2 — Upload each lot's photos in order.
      if (hasAnyPhotos) {
        toast.message('Uploading photos…');
        for (let i = 0; i < createdLots.length; i += 1) {
          const lotId = createdLots[i].id;
          const pending = lots[i]?.pendingPhotos || [];
          for (const ph of pending) {
            const fd = new FormData();
            fd.append('file', ph.file);
            try {
              await axios.post(
                `${API}/vehicle-multi-lot-auctions/${eventId}/lots/${lotId}/photos`,
                fd,
                {
                  headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'multipart/form-data',
                  },
                },
              );
            } catch (uerr) {
              console.error('photo upload failed', uerr);
              toast.error(`Lot #${i + 1} — Photo upload failed (continuing)`);
            }
          }
        }

        // Promote to requested intent if it wasn't draft.
        if (intent !== 'draft') {
          try {
            await axios.post(
              `${API}/vehicle-multi-lot-auctions/${eventId}/activate?intent=${intent}` +
                (intent === 'schedule' ? `&start_time=${encodeURIComponent(startISO)}` : ''),
              {},
              { headers: { Authorization: `Bearer ${token}` } },
            );
          } catch (aerr) {
            console.error('activate failed', aerr);
            toast.error('Event saved as draft, but activation failed — please publish from the drafts dashboard.');
          }
        }
      }

      toast.success(`Multi-lot event ${intent === 'draft' ? 'saved as draft' : intent === 'schedule' ? 'scheduled' : 'live'}!`);
      navigate(`/vehicle-multi-lot/${eventId}`);
    } catch (err) {
      console.error(err);
      toast.error(err?.response?.data?.detail || 'Failed to create multi-lot event');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6" data-testid="create-multi-lot-page">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Layers className="h-7 w-7 text-blue-600" />
          Create Multi-Lot Vehicle Auction
        </h1>
        <p className="text-sm text-gray-600 mt-1">
          Run multiple vehicle lots in one auction event — pick a timing mode below.
        </p>
      </div>

      {/* Event-level details */}
      <Card className="p-6 space-y-4" data-testid="event-details-card">
        <h2 className="text-xl font-semibold">Event Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="event-title">Event Title *</Label>
            <Input
              id="event-title"
              data-testid="event-title-input"
              value={event.title}
              onChange={e => setEvent({ ...event, title: e.target.value })}
              placeholder="e.g. March Wholesale Block — 12 Trucks"
            />
          </div>
          <div>
            <Label htmlFor="event-start">Start Time *</Label>
            <Input
              id="event-start"
              data-testid="event-start-input"
              type="datetime-local"
              value={event.start_time}
              onChange={e => setEvent({ ...event, start_time: e.target.value })}
            />
          </div>
          <div className="md:col-span-2">
            <Label className="mb-2 block">Timing Mode *</Label>
            {/* iter294 ADDENDUM — Visual mode picker with icon, short
                label, recommended-star, and tooltip carrying the full
                description. Internal API value stays sequential /
                staggered (DB unchanged). */}
            <TooltipProvider delayDuration={150}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" role="radiogroup">
                {/* Sequential Spotlight (default/recommended) */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={event.timing_mode === 'sequential'}
                      onClick={() => setEvent({ ...event, timing_mode: 'sequential' })}
                      className={`relative p-4 border-2 rounded-lg text-left transition-all hover:shadow-md ${
                        event.timing_mode === 'sequential'
                          ? 'border-indigo-600 bg-indigo-50 ring-2 ring-indigo-100'
                          : 'border-slate-200 bg-white hover:border-indigo-300'
                      }`}
                      data-testid="timing-mode-sequential-card"
                    >
                      {TIMING_MODES.sequential.recommended && (
                        <span className="absolute -top-2 -right-2 inline-flex items-center gap-1 px-2 py-0.5 bg-amber-400 text-amber-900 text-[10px] font-bold rounded-full shadow-sm">
                          <Star className="h-3 w-3 fill-current" /> Recommended
                        </span>
                      )}
                      <div className="flex items-center gap-2 mb-1">
                        <Target className="h-5 w-5 text-indigo-600" aria-hidden="true" />
                        <span className="font-semibold text-sm">{TIMING_MODES.sequential.label}</span>
                      </div>
                      <p className="text-xs text-slate-600 line-clamp-3">
                        {TIMING_MODES.sequential.description}
                      </p>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" align="start" className="max-w-xs text-xs">
                    {TIMING_MODES.sequential.description}
                  </TooltipContent>
                </Tooltip>

                {/* Synchronized Wave */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={event.timing_mode === 'staggered'}
                      onClick={() => setEvent({ ...event, timing_mode: 'staggered' })}
                      className={`relative p-4 border-2 rounded-lg text-left transition-all hover:shadow-md ${
                        event.timing_mode === 'staggered'
                          ? 'border-blue-600 bg-blue-50 ring-2 ring-blue-100'
                          : 'border-slate-200 bg-white hover:border-blue-300'
                      }`}
                      data-testid="timing-mode-staggered-card"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Waves className="h-5 w-5 text-blue-600" aria-hidden="true" />
                        <span className="font-semibold text-sm">{TIMING_MODES.staggered.label}</span>
                      </div>
                      <p className="text-xs text-slate-600 line-clamp-3">
                        {TIMING_MODES.staggered.description}
                      </p>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" align="start" className="max-w-xs text-xs">
                    {TIMING_MODES.staggered.description}
                  </TooltipContent>
                </Tooltip>
              </div>
            </TooltipProvider>
            <input
              type="hidden"
              data-testid="event-timing-mode-select"
              value={event.timing_mode}
              readOnly
            />
          </div>
          <div>
            <Label htmlFor="event-lot-duration">Per-Lot Duration (seconds)</Label>
            <Input
              id="event-lot-duration"
              data-testid="event-lot-duration-input"
              type="number"
              min={30}
              max={3600}
              value={event.lot_duration_seconds}
              onChange={e => setEvent({ ...event, lot_duration_seconds: e.target.value })}
            />
            <p className="text-xs text-gray-500 mt-1">Default 120s. Soft-close extends by +120s on late bids.</p>
          </div>
          {event.timing_mode === 'staggered' && (
            <div>
              <Label htmlFor="event-stagger">Stagger Offset (seconds)</Label>
              <Input
                id="event-stagger"
                data-testid="event-stagger-input"
                type="number"
                min={30}
                max={600}
                value={event.stagger_offset_seconds}
                onChange={e => setEvent({ ...event, stagger_offset_seconds: e.target.value })}
              />
              <p className="text-xs text-gray-500 mt-1">Time between consecutive lot starts. Default 60s.</p>
            </div>
          )}
          <div className="md:col-span-2">
            <Label htmlFor="event-desc">Description</Label>
            <Textarea
              id="event-desc"
              data-testid="event-desc-input"
              value={event.description}
              onChange={e => setEvent({ ...event, description: e.target.value })}
              placeholder="Event description, viewing details, payment terms, etc."
              rows={3}
            />
          </div>
        </div>
      </Card>

      {/* Lots */}
      <Card className="p-6 space-y-4" data-testid="lots-card">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Car className="h-5 w-5" />
            Lots ({lots.length})
          </h2>
          <Button onClick={addLot} variant="outline" size="sm" data-testid="add-lot-btn">
            <Plus className="h-4 w-4 mr-1" /> Add Lot
          </Button>
        </div>

        {lots.map((lot, idx) => (
          <Card key={idx} className="p-4 bg-gray-50 border-gray-200" data-testid={`lot-card-${idx}`}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium">Lot #{idx + 1}</h3>
              {lots.length > 1 && (
                <Button
                  onClick={() => removeLot(idx)}
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:bg-red-50"
                  data-testid={`remove-lot-btn-${idx}`}
                >
                  <Trash2 className="h-4 w-4 mr-1" /> Remove
                </Button>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <Label>VIN *</Label>
                <Input
                  data-testid={`lot-vin-${idx}`}
                  value={lot.vin}
                  maxLength={17}
                  onChange={e => updateLot(idx, { vin: e.target.value.toUpperCase() })}
                  placeholder="17-char VIN"
                />
              </div>
              <div>
                <Label>Year *</Label>
                <Input
                  data-testid={`lot-year-${idx}`}
                  type="number" min={1900} max={2100}
                  value={lot.year}
                  onChange={e => updateLot(idx, { year: e.target.value })}
                />
              </div>
              <div>
                <Label>Make *</Label>
                <Input
                  data-testid={`lot-make-${idx}`}
                  value={lot.make}
                  onChange={e => updateLot(idx, { make: e.target.value })}
                  placeholder="Ford"
                />
              </div>
              <div>
                <Label>Model *</Label>
                <Input
                  data-testid={`lot-model-${idx}`}
                  value={lot.model}
                  onChange={e => updateLot(idx, { model: e.target.value })}
                  placeholder="F-350"
                />
              </div>
              <div className="md:col-span-2">
                <Label>Title *</Label>
                <Input
                  data-testid={`lot-title-${idx}`}
                  value={lot.title}
                  onChange={e => updateLot(idx, { title: e.target.value })}
                  placeholder="e.g. 2020 Ford F-350 XL Crew Cab"
                />
              </div>
              {/* iter299 P0 — Bill 96 French lot title (required for QC-located lots). */}
              <div className="md:col-span-2">
                <Label>
                  {String(lot.location_province || '').toUpperCase() === 'QC' ? (
                    <>Title (French) / Titre (fran&ccedil;ais) <span className="text-red-600">*</span></>
                  ) : (
                    <>French Title (optional) / Titre fran&ccedil;ais (optionnel)</>
                  )}
                </Label>
                <Input
                  data-testid={`lot-title-fr-${idx}`}
                  value={lot.title_fr || ''}
                  onChange={e => updateLot(idx, { title_fr: e.target.value })}
                  placeholder="ex: 2020 Ford F-350 XL Crew Cab — véhicule de travail"
                />
                {String(lot.location_province || '').toUpperCase() === 'QC' && (
                  <p className="text-xs text-slate-500 mt-1">
                    Required for Quebec listings under Bill 96 / Obligatoire pour les annonces qu&eacute;b&eacute;coises (Loi 96)
                  </p>
                )}
              </div>
              <div>
                <Label>Mileage</Label>
                <Input
                  data-testid={`lot-mileage-${idx}`}
                  type="number" min={0}
                  value={lot.mileage}
                  onChange={e => updateLot(idx, { mileage: e.target.value })}
                />
              </div>
              <div>
                <Label>Starting Price (CAD) *</Label>
                <Input
                  data-testid={`lot-starting-price-${idx}`}
                  type="number" min={1}
                  value={lot.starting_price}
                  onChange={e => updateLot(idx, { starting_price: e.target.value })}
                />
              </div>
              <div>
                <Label>Reserve Price</Label>
                <Input
                  data-testid={`lot-reserve-${idx}`}
                  type="number" min={0}
                  value={lot.reserve_price}
                  onChange={e => updateLot(idx, { reserve_price: e.target.value })}
                  placeholder="(optional)"
                />
              </div>
              <div>
                <Label>Bid Increment</Label>
                <Input
                  data-testid={`lot-bid-increment-${idx}`}
                  type="number" min={1}
                  value={lot.bid_increment}
                  onChange={e => updateLot(idx, { bid_increment: e.target.value })}
                />
              </div>
              <div>
                <Label>City *</Label>
                <Input
                  data-testid={`lot-city-${idx}`}
                  value={lot.location_city}
                  onChange={e => updateLot(idx, { location_city: e.target.value })}
                  placeholder="Montreal"
                />
              </div>
              <div>
                <Label>Province *</Label>
                <Input
                  data-testid={`lot-province-${idx}`}
                  value={lot.location_province}
                  maxLength={2}
                  onChange={e => updateLot(idx, { location_province: e.target.value.toUpperCase() })}
                  placeholder="QC"
                />
              </div>
              <div>
                <Label>Title Status</Label>
                <Select
                  value={lot.title_status}
                  onValueChange={v => updateLot(idx, { title_status: v })}
                >
                  <SelectTrigger data-testid={`lot-title-status-${idx}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="clean">Clean</SelectItem>
                    <SelectItem value="salvage">Salvage</SelectItem>
                    <SelectItem value="rebuilt">Rebuilt</SelectItem>
                    <SelectItem value="lemon">Lemon</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-3">
                <Label>Description</Label>
                <Textarea
                  data-testid={`lot-desc-${idx}`}
                  value={lot.description}
                  onChange={e => updateLot(idx, { description: e.target.value })}
                  rows={2}
                  placeholder="Condition notes, options, equipment, defects..."
                />
              </div>

              {/* iter295 P2 — Per-lot photo gallery */}
              <div className="md:col-span-3 border-t pt-4 mt-2" data-testid={`lot-photos-block-${idx}`}>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <Label className="inline-flex items-center gap-1">
                      <ImageIcon className="h-4 w-4" /> Photos
                      <span className="text-xs text-slate-500 font-normal ml-1">
                        (min 1, max {MAX_PHOTOS_PER_LOT})
                      </span>
                    </Label>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {(lot.pendingPhotos || []).length === 0
                        ? 'No photos yet — at least 1 required to go Live or Schedule.'
                        : `${(lot.pendingPhotos || []).length} / ${MAX_PHOTOS_PER_LOT} selected.`}
                    </p>
                  </div>
                  <label
                    htmlFor={`lot-photo-input-${idx}`}
                    className="inline-flex items-center gap-1 px-3 py-2 rounded-md bg-blue-600 text-white text-sm cursor-pointer hover:bg-blue-700"
                    data-testid={`lot-photo-pick-btn-${idx}`}
                  >
                    <Upload className="h-4 w-4" /> Add Photos
                  </label>
                  <input
                    id={`lot-photo-input-${idx}`}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={(e) => onPickFiles(idx, e.target.files)}
                    data-testid={`lot-photo-input-${idx}`}
                  />
                </div>

                {(lot.pendingPhotos || []).length > 0 && (
                  <div
                    className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2"
                    data-testid={`lot-photo-grid-${idx}`}
                  >
                    {(lot.pendingPhotos || []).map((ph, pIdx) => (
                      <div
                        key={ph.id}
                        className="relative rounded-md overflow-hidden border border-slate-200 bg-slate-50 aspect-square"
                        data-testid={`lot-photo-thumb-${idx}-${pIdx}`}
                      >
                        <img
                          src={ph.previewUrl}
                          alt={`Lot ${idx + 1} photo ${pIdx + 1}`}
                          className="w-full h-full object-cover"
                        />
                        <div className="absolute top-1 left-1 inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold text-white bg-black/60 rounded">
                          {pIdx + 1}
                        </div>
                        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-1 flex items-center justify-between">
                          <button
                            type="button"
                            onClick={() => movePhoto(idx, ph.id, 'left')}
                            className="p-1 rounded bg-white/90 hover:bg-white text-slate-700 disabled:opacity-50"
                            disabled={pIdx === 0}
                            data-testid={`lot-photo-left-${idx}-${pIdx}`}
                            aria-label="Move left"
                          >
                            <ArrowLeft className="h-3 w-3" />
                          </button>
                          <button
                            type="button"
                            onClick={() => removePhoto(idx, ph.id)}
                            className="p-1 rounded bg-red-500/90 hover:bg-red-600 text-white"
                            data-testid={`lot-photo-remove-${idx}-${pIdx}`}
                            aria-label="Remove photo"
                          >
                            <X className="h-3 w-3" />
                          </button>
                          <button
                            type="button"
                            onClick={() => movePhoto(idx, ph.id, 'right')}
                            className="p-1 rounded bg-white/90 hover:bg-white text-slate-700 disabled:opacity-50"
                            disabled={pIdx === (lot.pendingPhotos || []).length - 1}
                            data-testid={`lot-photo-right-${idx}-${pIdx}`}
                            aria-label="Move right"
                          >
                            <ArrowRight className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </Card>

      {/* Submit row — Draft / Schedule / Go Live */}
      <div className="flex flex-col sm:flex-row gap-2 justify-end" data-testid="submit-row">
        <Button
          variant="outline"
          onClick={() => handleSubmit('draft')}
          disabled={loading}
          className="min-h-[48px]"
          data-testid="submit-multi-lot-draft-btn"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
          Save as Draft
        </Button>
        <Button
          variant="outline"
          onClick={() => handleSubmit('schedule')}
          disabled={loading}
          className="min-h-[48px] border-blue-600 text-blue-700 hover:bg-blue-50"
          data-testid="submit-multi-lot-schedule-btn"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Calendar className="h-4 w-4 mr-1" />}
          Schedule (Upcoming)
        </Button>
        <Button
          onClick={() => handleSubmit('live')}
          disabled={loading}
          className="min-h-[48px] bg-green-600 hover:bg-green-700"
          data-testid="submit-multi-lot-live-btn"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <CheckCircle className="h-4 w-4 mr-1" />}
          Go Live Now
        </Button>
      </div>
    </div>
  );
};

export default CreateVehicleMultiLotPage;
