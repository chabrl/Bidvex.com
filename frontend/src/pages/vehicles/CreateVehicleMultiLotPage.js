import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Card } from '../../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Plus, Trash2, Save, Calendar, CheckCircle, Loader2, Car, Layers } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * CreateVehicleMultiLotPage — iter293 Directive 2
 *
 * Dealer wizard for creating a Copart/wholesale-style multi-lot vehicle
 * auction event. The dealer fills the event-level details (title, start
 * time, timing mode, lot duration) and adds N lots. Each lot is a
 * lightweight per-vehicle entry (VIN, year, make, model, starting price,
 * photos). On submit the dealer chooses: Save as Draft / Schedule
 * (Upcoming) / Go Live Now.
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
  const [event, setEvent] = useState({
    title: '',
    description: '',
    timing_mode: 'sequential',
    start_time: new Date(Date.now() + 3600_000).toISOString().slice(0, 16),
    lot_duration_seconds: 120,
    stagger_offset_seconds: 60,
  });
  const [lots, setLots] = useState([emptyLot()]);

  const addLot = () => setLots(prev => [...prev, emptyLot()]);
  const removeLot = (idx) => setLots(prev => prev.filter((_, i) => i !== idx));
  const updateLot = (idx, patch) => setLots(prev => prev.map((l, i) => i === idx ? { ...l, ...patch } : l));

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
      if (!lot.location_city || !lot.location_province) {
        toast.error(`Lot #${i + 1} — Location city + province required`);
        return;
      }
      if (!lot.starting_price || Number(lot.starting_price) <= 0) {
        toast.error(`Lot #${i + 1} — Starting price must be > 0`);
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
      const payload = {
        title: event.title,
        description: event.description,
        timing_mode: event.timing_mode,
        start_time: startISO,
        lot_duration_seconds: Number(event.lot_duration_seconds) || 120,
        stagger_offset_seconds: Number(event.stagger_offset_seconds) || 60,
        submission_intent: intent,
        lots: lots.map(l => ({
          ...l,
          year: Number(l.year),
          mileage: Number(l.mileage),
          starting_price: Number(l.starting_price),
          reserve_price: l.reserve_price ? Number(l.reserve_price) : null,
          bid_increment: Number(l.bid_increment) || 100,
        })),
      };
      const r = await axios.post(`${API}/vehicle-multi-lot-auctions`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(`Multi-lot event ${intent === 'draft' ? 'saved as draft' : intent === 'schedule' ? 'scheduled' : 'live'}!`);
      navigate(`/vehicle-multi-lot/${r.data.id}`);
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
          Copart-style sequential block — run multiple vehicle lots in one event.
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
          <div>
            <Label>Timing Mode *</Label>
            <Select
              value={event.timing_mode}
              onValueChange={v => setEvent({ ...event, timing_mode: v })}
            >
              <SelectTrigger data-testid="event-timing-mode-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sequential">Sequential (Copart) — lot N+1 opens after lot N ends</SelectItem>
                <SelectItem value="staggered">Staggered — each lot offset 1 min apart, run in parallel</SelectItem>
              </SelectContent>
            </Select>
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
