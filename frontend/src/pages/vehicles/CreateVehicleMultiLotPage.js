import API_BASE from '../../config';
/**
 * CreateVehicleMultiLotPage — iter303 Directive 1
 *
 * Replaces the flat single-page form with a two-layer wizard:
 *
 *   ┌─────────────────────────────────────────────────────────┐
 *   │ LAYER 1 — Event-level setup (Title, Start Time, Timing  │
 *   │           Mode, Description) — always visible at top.   │
 *   ├─────────────────────────────────────────────────────────┤
 *   │ LAYER 2 — Per-lot 6-step wizard (mirrors single vehicle │
 *   │           listing). Each lot enters its own wizard via  │
 *   │           "Add Lot" / "Edit Lot".                       │
 *   │                                                         │
 *   │   Steps: VIN & Basic Info → Specifications →            │
 *   │          Condition Report → Photos & Media →            │
 *   │          Auction Settings → Review & Submit             │
 *   │                                                         │
 *   │   Reused components from single vehicle listing:        │
 *   │     • VehicleCategoryGrid                               │
 *   │     • LocationSelector                                  │
 *   │     • VehicleProvinceEligibility (skipped — multi-lot   │
 *   │       inherits from event province)                     │
 *   │                                                         │
 *   │   Bill 96 — Title (FR) required for QC province lots.   │
 *   │   Minimum 1 photo per lot enforced before Save Lot.     │
 *   │   60-second floor on per-lot duration (event-level).    │
 *   └─────────────────────────────────────────────────────────┘
 *
 * Once at least 1 lot is saved AND no wizard is active, the bottom
 * action row reveals Save as Draft / Schedule (Upcoming) / Go Live Now.
 *
 * Fully bilingual EN/FR via inline L(en, fr) helper.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';
import VehicleCategoryGrid from '../../components/vehicles/VehicleCategoryGrid';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '../../components/ui/tooltip';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../components/ui/sheet';
import { Checkbox } from '../../components/ui/checkbox';
import {
  Car, Save, Calendar, CheckCircle, Loader2, Layers, Waves, Target, Star,
  Upload, ImageIcon, X, ArrowLeft, ArrowRight, Info, Search, Plus,
  Edit3, Trash2, FileText, Camera, DollarSign, Settings2, Gauge,
  Fuel, Palette, Shield, AlertTriangle, ChevronLeft, ChevronRight,
  BookmarkPlus, FolderOpen, Copy, FileSpreadsheet,
} from 'lucide-react';
import { TIMING_MODES, getTimingModeLabel, getTimingModeDescription } from '../../lib/vehicleMultiLotTimingModes';
import BulkImportLotsCSV from '../../components/vehicles/BulkImportLotsCSV';

const API = API_BASE;

const MIN_LOT_DURATION_SECONDS = 60;
const MAX_PHOTOS_PER_LOT = 20;
const MIN_PHOTOS_PER_LOT = 1;

const BODY_TYPES = [
  { value: 'sedan',       enLabel: 'Sedan',       frLabel: 'Berline' },
  { value: 'suv',         enLabel: 'SUV',         frLabel: 'VUS' },
  { value: 'truck',       enLabel: 'Truck',       frLabel: 'Camion' },
  { value: 'coupe',       enLabel: 'Coupe',       frLabel: 'Coupé' },
  { value: 'hatchback',   enLabel: 'Hatchback',   frLabel: 'À hayon' },
  { value: 'van',         enLabel: 'Van',         frLabel: 'Fourgonnette' },
  { value: 'convertible', enLabel: 'Convertible', frLabel: 'Décapotable' },
  { value: 'wagon',       enLabel: 'Wagon',       frLabel: 'Familiale' },
  { value: 'other',       enLabel: 'Other',       frLabel: 'Autre' },
];

const FUEL_TYPES = [
  { value: 'gasoline',      enLabel: 'Gasoline',      frLabel: 'Essence' },
  { value: 'diesel',        enLabel: 'Diesel',        frLabel: 'Diesel' },
  { value: 'electric',      enLabel: 'Electric',      frLabel: 'Électrique' },
  { value: 'hybrid',        enLabel: 'Hybrid',        frLabel: 'Hybride' },
  { value: 'plugin_hybrid', enLabel: 'Plug-in Hybrid',frLabel: 'Hybride rechargeable' },
  { value: 'other',         enLabel: 'Other',         frLabel: 'Autre' },
];

const TRANSMISSIONS = [
  { value: 'automatic', enLabel: 'Automatic',  frLabel: 'Automatique' },
  { value: 'manual',    enLabel: 'Manual',     frLabel: 'Manuelle' },
  { value: 'cvt',       enLabel: 'CVT',        frLabel: 'CVT' },
  { value: 'dct',       enLabel: 'Dual-Clutch',frLabel: 'Double embrayage' },
];

const DRIVETRAINS = [
  { value: 'fwd', enLabel: 'FWD (Front-Wheel)',  frLabel: 'Traction avant' },
  { value: 'rwd', enLabel: 'RWD (Rear-Wheel)',   frLabel: 'Propulsion arrière' },
  { value: 'awd', enLabel: 'AWD (All-Wheel)',    frLabel: 'Intégrale (AWD)' },
  { value: '4wd', enLabel: '4WD (Four-Wheel)',   frLabel: '4 roues motrices' },
];

const CONDITIONS = [
  { value: 'excellent', enLabel: 'Excellent', frLabel: 'Excellent' },
  { value: 'good',      enLabel: 'Good',      frLabel: 'Bon' },
  { value: 'fair',      enLabel: 'Fair',      frLabel: 'Passable' },
  { value: 'poor',      enLabel: 'Poor',      frLabel: 'Médiocre' },
];

const TITLE_STATUSES = [
  { value: 'clean',   enLabel: 'Clean',   frLabel: 'Propre' },
  { value: 'salvage', enLabel: 'Salvage', frLabel: 'Récupération' },
  { value: 'rebuilt', enLabel: 'Rebuilt', frLabel: 'Reconstruit' },
  { value: 'lemon',   enLabel: 'Lien',    frLabel: 'Avec privilège' },
];

const ACCIDENT_OPTIONS = [
  { value: 'unknown', enLabel: 'Unknown', frLabel: 'Inconnu' },
  { value: 'no',      enLabel: 'No',      frLabel: 'Non' },
  { value: 'yes',     enLabel: 'Yes',     frLabel: 'Oui' },
];

const PROVINCES = ['QC', 'ON', 'BC', 'AB', 'MB', 'SK', 'NS', 'NB', 'NL', 'PE', 'YT', 'NT', 'NU'];

const emptyLot = () => ({
  id: `lot-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
  // Step 1
  category_id: '',
  subcategory_id: '',
  vin: '',
  year: new Date().getFullYear(),
  make: '',
  model: '',
  trim: '',
  body_type: 'sedan',
  // Step 2
  mileage: 0,
  engine_size: '',
  transmission: 'automatic',
  drivetrain: 'fwd',
  exterior_color: '',
  interior_color: '',
  fuel_type: 'gasoline',
  doors: '',
  seats: '',
  // Step 3
  title_status: 'clean',
  condition_rating: 'good',
  known_defects: '',
  accident_history: 'unknown',
  previous_owners: '',
  last_service_date: '',
  // Step 4
  pendingPhotos: [],
  // Step 5
  starting_price: 1000,
  reserve_price: '',
  bid_increment: 100,
  location_city: '',
  location_province: 'QC',
  title: '',
  title_fr: '',
  description: '',
  lot_duration_override: '',
});

const CreateVehicleMultiLotPage = () => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const L = (en, frTxt) => (fr ? frTxt : en);

  const [loading, setLoading] = useState(false);
  const [infoSheet, setInfoSheet] = useState(null);
  const [vinLoading, setVinLoading] = useState(null); // lot id currently looking up

  // iter304 — Lot Templates (per-dealer presets that pre-fill Steps 2–5)
  const [templates, setTemplates] = useState([]);
  const [templatesMax, setTemplatesMax] = useState(20);
  const [saveTemplateModal, setSaveTemplateModal] = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);

  // iter306 — CSV bulk import
  const [csvImportOpen, setCsvImportOpen] = useState(false);
  const [draftEventId, setDraftEventId] = useState(null);
  const [creatingDraftEvent, setCreatingDraftEvent] = useState(false);

  const fetchTemplates = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) return;
      const r = await axios.get(`${API}/lot-templates`, { headers: { Authorization: `Bearer ${token}` } });
      setTemplates(r.data?.items || []);
      setTemplatesMax(r.data?.max || 20);
    } catch (_e) {
      // silent — dealer might not have permission or none exist
    }
  };
  useEffect(() => { fetchTemplates(); }, []);

  // Apply a template's fields onto the current wizard draft (Steps 2–5)
  const applyTemplate = (tplId) => {
    if (!tplId) return;
    const tpl = templates.find((t) => t.id === tplId);
    if (!tpl) return;
    const f = tpl.fields || {};
    setWizard((w) => w ? ({
      ...w,
      draft: {
        ...w.draft,
        // Step 1 — Make/Model/BodyType
        make: f.make || w.draft.make,
        model: f.model || w.draft.model,
        body_type: f.body_type || w.draft.body_type,
        // Step 2 — Specs
        engine_size: f.engine_size || w.draft.engine_size,
        transmission: f.transmission || w.draft.transmission,
        drivetrain: f.drivetrain || w.draft.drivetrain,
        fuel_type: f.fuel_type || w.draft.fuel_type,
        exterior_color: f.exterior_color || w.draft.exterior_color,
        interior_color: f.interior_color || w.draft.interior_color,
        doors: f.doors || w.draft.doors,
        seats: f.seats || w.draft.seats,
        // Step 3 — Condition
        title_status: f.title_status || w.draft.title_status,
        condition_rating: f.condition_rating || w.draft.condition_rating,
        // Step 5 — Auction settings
        starting_price: f.starting_price ?? w.draft.starting_price,
        reserve_price: f.reserve_price ?? w.draft.reserve_price,
        bid_increment: f.bid_increment ?? w.draft.bid_increment,
        location_city: f.location_city || w.draft.location_city,
        location_province: f.location_province || w.draft.location_province,
        _applied_template_id: tplId,
      },
    }) : w);
    toast.success(L(`Template "${tpl.name}" applied`, `Modèle « ${tpl.name} » appliqué`));
  };

  // Persist current draft as a new template (called from wizard Step 5)
  const persistTemplate = async (name) => {
    if (!wizard) return;
    const trimmed = (name || '').trim();
    if (!trimmed) { toast.error(L('Template name is required', 'Nom de modèle requis')); return; }
    if (trimmed.length > 60) { toast.error(L('Max 60 characters', 'Max 60 caractères')); return; }
    if (templates.length >= templatesMax) {
      toast.error(L(`Maximum ${templatesMax} templates reached`, `Maximum ${templatesMax} modèles atteint`));
      return;
    }
    setSavingTemplate(true);
    try {
      const token = localStorage.getItem('token');
      const d = wizard.draft;
      const payload = {
        name: trimmed,
        fields: {
          make: d.make, model: d.model, body_type: d.body_type,
          engine_size: d.engine_size, transmission: d.transmission,
          drivetrain: d.drivetrain, fuel_type: d.fuel_type,
          exterior_color: d.exterior_color, interior_color: d.interior_color,
          doors: String(d.doors || ''), seats: String(d.seats || ''),
          starting_price: Number(d.starting_price) || 0,
          reserve_price: d.reserve_price ? Number(d.reserve_price) : null,
          bid_increment: Number(d.bid_increment) || 100,
          location_city: d.location_city, location_province: d.location_province,
          title_status: d.title_status, condition_rating: d.condition_rating,
        },
      };
      await axios.post(`${API}/lot-templates`, payload, { headers: { Authorization: `Bearer ${token}` } });
      await fetchTemplates();
      toast.success(L(`Template "${trimmed}" saved`, `Modèle « ${trimmed} » enregistré`));
      setSaveTemplateModal(false);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object' ? (fr ? detail.message_fr : detail.message_en) : detail) || L('Failed to save template', 'Échec de la sauvegarde');
      toast.error(msg);
    } finally {
      setSavingTemplate(false);
    }
  };

  const [event, setEvent] = useState(() => ({
    title: '',
    description: '',
    timing_mode: 'sequential',
    start_time: new Date(Date.now() + 3600_000).toISOString().slice(0, 16),
    lot_duration_seconds: 120,
    stagger_offset_seconds: 60,
  }));

  // Saved lots (committed via Review & Submit)
  const [lots, setLots] = useState([]);

  // Wizard state — when non-null, the per-lot wizard renders instead of the lot list.
  // shape: { lotIndex: number | 'new', currentStep: 0..5, draft: lot }
  const [wizard, setWizard] = useState(null);

  const STEPS = useMemo(() => ([
    { id: 'vin',       enTitle: 'VIN & Basic Info',   frTitle: 'NIV et infos de base',    icon: Car },
    { id: 'specs',     enTitle: 'Specifications',     frTitle: 'Spécifications',          icon: Settings2 },
    { id: 'condition', enTitle: 'Condition Report',   frTitle: 'Rapport de condition',    icon: FileText },
    { id: 'photos',    enTitle: 'Photos & Media',     frTitle: 'Photos et médias',        icon: Camera },
    { id: 'auction',   enTitle: 'Auction Settings',   frTitle: "Paramètres de la vente",  icon: DollarSign },
    { id: 'review',    enTitle: 'Review & Submit',    frTitle: 'Révision et soumission',  icon: CheckCircle },
  ]), []);

  // ---------- Wizard helpers ----------
  const openWizardForNew = () => setWizard({ lotIndex: 'new', currentStep: 0, draft: emptyLot() });
  const openWizardForEdit = (idx) => setWizard({ lotIndex: idx, currentStep: 0, draft: { ...lots[idx] } });
  // iter305 — Duplicate Lot: clone a saved lot into a new draft. VIN, Mileage,
  // and Photos are intentionally CLEARED — those are always unique per vehicle.
  // Opens immediately in Step 1 with a banner prompting the user to fill the
  // new VIN + upload photos.
  const openWizardForDuplicate = (idx) => {
    const src = lots[idx];
    if (!src) return;
    const cloneTitle = (src.title || '').trim();
    const cloneTitleFr = (src.title_fr || '').trim();
    setWizard({
      lotIndex: 'new',
      currentStep: 0,
      _duplicate: true, // banner flag
      draft: {
        ...src,
        // Fresh id so React keys stay unique
        id: `lot-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        // CLEARED — always unique per vehicle
        vin: '',
        mileage: 0,
        pendingPhotos: [],
        // Mark the duplicated title (EN + FR)
        title: cloneTitle ? `${cloneTitle} — Copy` : '',
        title_fr: cloneTitleFr ? `${cloneTitleFr} — Copie` : (cloneTitle ? `${cloneTitle} — Copie` : ''),
        // Reset any applied template flag so the user sees the duplicate-banner
        _applied_template_id: '',
      },
    });
  };
  const cancelWizard = () => setWizard(null);

  const updateDraft = (patch) => setWizard((w) => (w ? { ...w, draft: { ...w.draft, ...patch } } : w));

  const saveLot = () => {
    if (!wizard) return;
    const lot = wizard.draft;
    // Final validations done at Review step before reaching here.
    setLots((prev) => {
      if (wizard.lotIndex === 'new') return [...prev, lot];
      const next = [...prev];
      next[wizard.lotIndex] = lot;
      return next;
    });
    setWizard(null);
    toast.success(L('Lot saved', 'Lot enregistré'));
  };

  const removeLot = (idx) => {
    if (!window.confirm(L('Delete this lot?', 'Supprimer ce lot ?'))) return;
    setLots((prev) => prev.filter((_, i) => i !== idx));
  };

  // ---------- VIN lookup ----------
  const lookupVin = async () => {
    if (!wizard) return;
    const vin = (wizard.draft.vin || '').trim().toUpperCase();
    if (vin.length !== 17) {
      toast.error(L('VIN must be exactly 17 characters', 'Le NIV doit contenir 17 caractères'));
      return;
    }
    setVinLoading(vin);
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API}/vehicles/decode-vin/${vin}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const d = r.data || {};
      updateDraft({
        year: d.year || wizard.draft.year,
        make: d.make || wizard.draft.make,
        model: d.model || wizard.draft.model,
        trim: d.trim || wizard.draft.trim,
        body_type: d.body_type || wizard.draft.body_type,
        transmission: d.transmission || wizard.draft.transmission,
        fuel_type: d.fuel_type || wizard.draft.fuel_type,
        drivetrain: d.drivetrain || wizard.draft.drivetrain,
        engine_size: d.engine_size || wizard.draft.engine_size,
      });
      toast.success(L('VIN decoded — fields auto-filled', 'NIV décodé — champs auto-remplis'));
    } catch (err) {
      toast.error(err?.response?.data?.detail || L('VIN lookup failed', 'Échec du décodage du NIV'));
    } finally {
      setVinLoading(null);
    }
  };

  // ---------- Photos (Step 4) ----------
  const addPhotos = (fileList) => {
    if (!wizard || !fileList || !fileList.length) return;
    const existing = wizard.draft.pendingPhotos || [];
    const room = MAX_PHOTOS_PER_LOT - existing.length;
    if (room <= 0) {
      toast.error(L(`Maximum ${MAX_PHOTOS_PER_LOT} photos per lot`, `Maximum ${MAX_PHOTOS_PER_LOT} photos par lot`));
      return;
    }
    const accepted = Array.from(fileList).slice(0, room).filter((f) => f.type.startsWith('image/'));
    if (!accepted.length) {
      toast.error(L('Please choose image files only', 'Veuillez choisir uniquement des images'));
      return;
    }
    const next = [...existing];
    accepted.forEach((file) => {
      const url = URL.createObjectURL(file);
      next.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, file, previewUrl: url });
    });
    updateDraft({ pendingPhotos: next });
  };

  const removePhoto = (photoId) => {
    if (!wizard) return;
    updateDraft({ pendingPhotos: (wizard.draft.pendingPhotos || []).filter((p) => p.id !== photoId) });
  };

  const movePhoto = (photoId, dir) => {
    if (!wizard) return;
    const pending = [...(wizard.draft.pendingPhotos || [])];
    const at = pending.findIndex((p) => p.id === photoId);
    if (at < 0) return;
    const swap = dir === 'left' ? at - 1 : at + 1;
    if (swap < 0 || swap >= pending.length) return;
    [pending[at], pending[swap]] = [pending[swap], pending[at]];
    updateDraft({ pendingPhotos: pending });
  };

  // ---------- Step validation ----------
  const validateStep = (stepIdx) => {
    const d = wizard.draft;
    if (stepIdx === 0) {
      if (!d.category_id) { toast.error(L('Please select a vehicle category', 'Veuillez choisir une catégorie')); return false; }
      if (!d.vin || d.vin.length !== 17) { toast.error(L('VIN must be exactly 17 characters', 'Le NIV doit contenir 17 caractères')); return false; }
      if (!d.year || !d.make || !d.model) { toast.error(L('Year, Make and Model are required', 'Année, Marque et Modèle requis')); return false; }
      if (!d.body_type) { toast.error(L('Body Type is required', 'Type de carrosserie requis')); return false; }
    }
    if (stepIdx === 1) {
      if (!d.mileage && d.mileage !== 0) { toast.error(L('Mileage is required', 'Le kilométrage est requis')); return false; }
    }
    if (stepIdx === 3) {
      if ((d.pendingPhotos || []).length < MIN_PHOTOS_PER_LOT) {
        toast.error(L(`At least ${MIN_PHOTOS_PER_LOT} photo is required`, `Au moins ${MIN_PHOTOS_PER_LOT} photo est requise`));
        return false;
      }
    }
    if (stepIdx === 4) {
      if (!d.starting_price || Number(d.starting_price) <= 0) { toast.error(L('Starting price must be > 0', 'Le prix de départ doit être > 0')); return false; }
      if (!d.location_city || !d.location_province) { toast.error(L('City and Province are required', 'Ville et Province requises')); return false; }
      if (!d.title) { toast.error(L('Listing title (EN) is required', 'Titre (EN) requis')); return false; }
      if (String(d.location_province || '').toUpperCase() === 'QC' && !String(d.title_fr || '').trim()) {
        toast.error(L('French title is required for Quebec lots (Bill 96)', 'Titre français requis pour les lots au Québec (Loi 96)'));
        return false;
      }
      if (d.lot_duration_override && Number(d.lot_duration_override) < MIN_LOT_DURATION_SECONDS) {
        toast.error(L(`Per-lot duration must be ≥ ${MIN_LOT_DURATION_SECONDS}s`, `Durée par lot ≥ ${MIN_LOT_DURATION_SECONDS}s`));
        return false;
      }
    }
    return true;
  };

  const goNext = () => {
    if (!wizard) return;
    if (!validateStep(wizard.currentStep)) return;
    setWizard({ ...wizard, currentStep: Math.min(wizard.currentStep + 1, STEPS.length - 1) });
  };

  const goPrev = () => {
    if (!wizard) return;
    setWizard({ ...wizard, currentStep: Math.max(0, wizard.currentStep - 1) });
  };

  // ---------- Final submit ----------
  const handleSubmit = async (intent) => {
    if (!event.title.trim()) { toast.error(L('Event title is required', "Titre de l'événement requis")); return; }
    if (lots.length === 0) { toast.error(L('Add at least one lot', 'Ajoutez au moins un lot')); return; }
    if (Number(event.lot_duration_seconds) < MIN_LOT_DURATION_SECONDS) {
      toast.error(L(`Per-lot duration must be ≥ ${MIN_LOT_DURATION_SECONDS}s`, `Durée par lot ≥ ${MIN_LOT_DURATION_SECONDS}s`));
      return;
    }
    if (intent === 'schedule') {
      const startMs = new Date(event.start_time).getTime();
      if (!startMs || startMs <= Date.now() + 60_000) {
        toast.error(L('Schedule requires Start Time ≥1 min in the future', "L'heure de début doit être ≥ 1 min dans le futur"));
        return;
      }
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const startISO = new Date(event.start_time).toISOString();
      const hasAnyPhotos = lots.some((l) => (l.pendingPhotos || []).length > 0);
      const createIntent = (intent !== 'draft' && hasAnyPhotos) ? 'draft' : intent;

      const payload = {
        title: event.title,
        description: event.description,
        timing_mode: event.timing_mode,
        start_time: startISO,
        lot_duration_seconds: Math.max(MIN_LOT_DURATION_SECONDS, Number(event.lot_duration_seconds) || 120),
        stagger_offset_seconds: Number(event.stagger_offset_seconds) || 60,
        submission_intent: createIntent,
        lots: lots.map((l) => ({
          vin: l.vin,
          year: Number(l.year),
          make: l.make,
          model: l.model,
          title: l.title,
          title_fr: l.title_fr || null,
          description: l.description,
          mileage: Number(l.mileage) || 0,
          body_type: l.body_type,
          transmission: l.transmission,
          fuel_type: l.fuel_type,
          drivetrain: l.drivetrain,
          exterior_color: l.exterior_color,
          interior_color: l.interior_color,
          ownership_status: 'owned',
          title_status: l.title_status,
          lien_status: 'clear',
          location_city: l.location_city,
          location_province: l.location_province,
          location_postal_code: '',
          starting_price: Number(l.starting_price),
          reserve_price: l.reserve_price ? Number(l.reserve_price) : null,
          bid_increment: Number(l.bid_increment) || 100,
          lot_duration_seconds: l.lot_duration_override ? Math.max(MIN_LOT_DURATION_SECONDS, Number(l.lot_duration_override)) : null,
          media: [],
          condition_report: {
            condition_rating: l.condition_rating,
            known_defects: l.known_defects || null,
            accident_history: l.accident_history,
            previous_owners: l.previous_owners ? Number(l.previous_owners) : null,
            last_service_date: l.last_service_date || null,
          },
          category_id: l.category_id || null,
          subcategory_id: l.subcategory_id || null,
        })),
      };

      const r = await axios.post(`${API}/vehicle-multi-lot-auctions`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const eventId = r.data.id;
      const createdLots = r.data.lots || [];

      if (hasAnyPhotos) {
        toast.message(L('Uploading photos…', 'Téléversement des photos…'));
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
                { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' } },
              );
            } catch (uerr) {
              console.error('photo upload failed', uerr);
              toast.error(L(`Lot #${i + 1} — Photo upload failed (continuing)`, `Lot n°${i + 1} — Échec de téléversement (on continue)`));
            }
          }
        }
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
            toast.error(L('Event saved as draft, but activation failed — publish from drafts.', "Événement enregistré comme brouillon — publiez-le depuis vos brouillons."));
          }
        }
      }

      toast.success(L(
        `Multi-lot event ${intent === 'draft' ? 'saved as draft' : intent === 'schedule' ? 'scheduled' : 'live'}!`,
        `Événement multi-lots ${intent === 'draft' ? 'enregistré comme brouillon' : intent === 'schedule' ? 'programmé' : 'en direct'} !`,
      ));
      navigate(`/vehicle-multi-lot/${eventId}`);
    } catch (err) {
      console.error(err);
      toast.error(err?.response?.data?.detail || L('Failed to create multi-lot event', "Échec de création de l'événement"));
    } finally {
      setLoading(false);
    }
  };

  // ===================== RENDER =====================

  // iter306 — Create a stub event (if not yet saved) and open CSV import modal
  const openCsvImport = async () => {
    if (!event.title.trim()) {
      toast.error(L('Set the event title first', "Définissez d'abord le titre de l'événement"));
      return;
    }
    if (draftEventId) {
      setCsvImportOpen(true);
      return;
    }
    setCreatingDraftEvent(true);
    try {
      const token = localStorage.getItem('token');
      const startISO = new Date(event.start_time).toISOString();
      const r = await axios.post(`${API}/vehicle-multi-lot-auctions`, {
        title: event.title,
        description: event.description || '',
        timing_mode: event.timing_mode,
        start_time: startISO,
        lot_duration_seconds: Math.max(MIN_LOT_DURATION_SECONDS, Number(event.lot_duration_seconds) || 120),
        stagger_offset_seconds: Number(event.stagger_offset_seconds) || 60,
        submission_intent: 'draft',
        lots: [], // start empty — CSV import will append
      }, { headers: { Authorization: `Bearer ${token}` } });
      setDraftEventId(r.data.id);
      setCsvImportOpen(true);
    } catch (err) {
      toast.error(err?.response?.data?.detail || L('Could not start CSV import', "Impossible de démarrer l'import CSV"));
    } finally {
      setCreatingDraftEvent(false);
    }
  };

  // After successful import, navigate to the created event so dealer can add photos
  const handleImported = (data) => {
    const eventId = data?.event_id || draftEventId;
    if (eventId) {
      navigate(`/vehicle-multi-lot/${eventId}`);
    }
  };

  if (wizard) {
    return (
      <>
        <LotWizard
          STEPS={STEPS}
          wizard={wizard}
          L={L}
          fr={fr}
          i18n={i18n}
          vinLoading={vinLoading}
          updateDraft={updateDraft}
          lookupVin={lookupVin}
          addPhotos={addPhotos}
          removePhoto={removePhoto}
          movePhoto={movePhoto}
          goNext={goNext}
          goPrev={goPrev}
          cancelWizard={cancelWizard}
          saveLot={saveLot}
          eventProvince={event.timing_mode}
          eventDurationSec={Number(event.lot_duration_seconds) || 120}
          templates={templates}
          templatesMax={templatesMax}
          applyTemplate={applyTemplate}
          onSaveAsTemplate={() => setSaveTemplateModal(true)}
        />
        {/* iter304 — modal must live OUTSIDE the wizard's conditional return
            so it's still mounted when the wizard is active. */}
        <SaveTemplateModal
          open={saveTemplateModal}
          onClose={() => setSaveTemplateModal(false)}
          onSave={persistTemplate}
          saving={savingTemplate}
          L={L}
        />
      </>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6" data-testid="create-multi-lot-page">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2">
          <Layers className="h-7 w-7 text-blue-600 flex-shrink-0" />
          {L('Create Multi-Lot Vehicle Auction', 'Créer une enchère multi-lots de véhicules')}
        </h1>
        <p className="text-sm text-gray-600 mt-1">
          {L(
            'Run multiple vehicle lots in one auction event — set the event details, then add each lot through the 6-step wizard.',
            "Organisez plusieurs lots de véhicules dans un même événement — réglez les détails, puis ajoutez chaque lot via l'assistant en 6 étapes.",
          )}
        </p>
      </div>

      {/* ========== Event-level setup ========== */}
      <Card className="p-4 sm:p-6 space-y-4" data-testid="event-details-card">
        <h2 className="text-lg sm:text-xl font-semibold">{L('Event Details', "Détails de l'événement")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="event-title">{L('Event Title *', "Titre de l'événement *")}</Label>
            <Input
              id="event-title"
              data-testid="event-title-input"
              value={event.title}
              onChange={(e) => setEvent({ ...event, title: e.target.value })}
              placeholder={L('e.g. March Wholesale Block — 12 Trucks', 'ex. Bloc de gros de mars — 12 camions')}
            />
          </div>
          <div>
            <Label htmlFor="event-start">{L('Start Time *', 'Heure de début *')}</Label>
            <Input
              id="event-start"
              data-testid="event-start-input"
              type="datetime-local"
              value={event.start_time}
              onChange={(e) => setEvent({ ...event, start_time: e.target.value })}
            />
          </div>
          <div className="md:col-span-2">
            <Label className="mb-2 block">{L('Timing Mode *', 'Mode de chronométrage *')}</Label>
            <TooltipProvider delayDuration={150}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" role="radiogroup">
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
                          <Star className="h-3 w-3 fill-current" /> {L('Recommended', 'Recommandé')}
                        </span>
                      )}
                      <div className="flex items-center gap-2 mb-1">
                        <Target className="h-5 w-5 text-indigo-600 flex-shrink-0" aria-hidden="true" />
                        <span className="font-semibold text-sm">{getTimingModeLabel('sequential', i18n.language)}</span>
                      </div>
                      <p className="text-xs text-slate-600 line-clamp-3 pr-7 sm:pr-0">
                        {getTimingModeDescription('sequential', i18n.language)}
                      </p>
                      <span
                        role="button"
                        tabIndex={0}
                        className="sm:hidden absolute bottom-2 right-2 p-1.5 rounded-full bg-slate-100 text-slate-600"
                        onClick={(e) => { e.stopPropagation(); setInfoSheet('sequential'); }}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); setInfoSheet('sequential'); } }}
                        data-testid="timing-info-sequential-btn"
                        aria-label={L('More info', "Plus d'infos")}
                      >
                        <Info className="h-4 w-4" />
                      </span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" align="start" className="max-w-xs text-xs">
                    {getTimingModeDescription('sequential', i18n.language)}
                  </TooltipContent>
                </Tooltip>

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
                        <Waves className="h-5 w-5 text-blue-600 flex-shrink-0" aria-hidden="true" />
                        <span className="font-semibold text-sm">{getTimingModeLabel('staggered', i18n.language)}</span>
                      </div>
                      <p className="text-xs text-slate-600 line-clamp-3 pr-7 sm:pr-0">
                        {getTimingModeDescription('staggered', i18n.language)}
                      </p>
                      <span
                        role="button"
                        tabIndex={0}
                        className="sm:hidden absolute bottom-2 right-2 p-1.5 rounded-full bg-slate-100 text-slate-600"
                        onClick={(e) => { e.stopPropagation(); setInfoSheet('staggered'); }}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); setInfoSheet('staggered'); } }}
                        data-testid="timing-info-staggered-btn"
                        aria-label={L('More info', "Plus d'infos")}
                      >
                        <Info className="h-4 w-4" />
                      </span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" align="start" className="max-w-xs text-xs">
                    {getTimingModeDescription('staggered', i18n.language)}
                  </TooltipContent>
                </Tooltip>
              </div>
            </TooltipProvider>
            <input type="hidden" data-testid="event-timing-mode-select" value={event.timing_mode} readOnly />
          </div>

          <div>
            <Label htmlFor="event-lot-duration">{L('Per-Lot Duration (seconds)', 'Durée par lot (secondes)')}</Label>
            <Input
              id="event-lot-duration"
              data-testid="event-lot-duration-input"
              type="number"
              min={MIN_LOT_DURATION_SECONDS}
              max={3600}
              value={event.lot_duration_seconds}
              onChange={(e) => setEvent({ ...event, lot_duration_seconds: e.target.value })}
            />
            <p className="text-xs font-medium text-slate-700 mt-1" data-testid="lot-duration-min-note">
              Minimum: 60 seconds / Minimum : 60 secondes
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              {L('Default 120s. Soft-close extends by +120s on late bids.', 'Par défaut 120 s. Clôture progressive +120 s.')}
            </p>
          </div>

          {event.timing_mode === 'staggered' && (
            <div>
              <Label htmlFor="event-stagger">{L('Stagger Offset (seconds)', 'Décalage entre lots (s)')}</Label>
              <Input
                id="event-stagger"
                data-testid="event-stagger-input"
                type="number"
                min={30}
                max={600}
                value={event.stagger_offset_seconds}
                onChange={(e) => setEvent({ ...event, stagger_offset_seconds: e.target.value })}
              />
              <p className="text-xs text-gray-500 mt-1">
                {L('Time between consecutive lot starts. Default 60s.', 'Temps entre les débuts de lots. 60 s par défaut.')}
              </p>
            </div>
          )}
          <div className="md:col-span-2">
            <Label htmlFor="event-desc">{L('Description', 'Description')}</Label>
            <Textarea
              id="event-desc"
              data-testid="event-desc-input"
              value={event.description}
              onChange={(e) => setEvent({ ...event, description: e.target.value })}
              placeholder={L('Event description, viewing details, payment terms…', "Description de l'événement, détails de visite, modalités…")}
              rows={3}
            />
          </div>
        </div>
      </Card>

      {/* ========== Lot list ========== */}
      <Card className="p-4 sm:p-6 space-y-4" data-testid="lots-card">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h2 className="text-lg sm:text-xl font-semibold flex items-center gap-2">
            <Car className="h-5 w-5" />
            Lots ({lots.length})
          </h2>
          <div className="flex gap-2 flex-wrap">
            {/* iter306 — Import from CSV */}
            <Button
              variant="outline"
              onClick={openCsvImport}
              disabled={creatingDraftEvent}
              className="min-h-[44px] border-blue-300 text-blue-700 hover:bg-blue-50"
              data-testid="open-bulk-import-btn"
            >
              {creatingDraftEvent ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <FileSpreadsheet className="h-4 w-4 mr-1" />}
              {L('Import Lots from CSV', 'Importer des lots depuis un CSV')}
            </Button>
            <Button onClick={openWizardForNew} className="min-h-[44px]" data-testid="add-lot-btn">
              <Plus className="h-4 w-4 mr-1" /> {lots.length === 0 ? L('Add Your First Lot', 'Ajouter le premier lot') : L('Add Another Lot', 'Ajouter un autre lot')}
            </Button>
          </div>
        </div>

        {lots.length === 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="lots-empty-state">
            {/* Card 1 — Add First Lot manually */}
            <button
              type="button"
              onClick={openWizardForNew}
              className="text-center py-8 px-4 border-2 border-dashed border-indigo-300 hover:border-indigo-500 hover:bg-indigo-50 rounded-lg transition-colors"
              data-testid="empty-add-first-lot-cta"
            >
              <Plus className="h-10 w-10 text-indigo-400 mx-auto mb-3" />
              <p className="text-sm font-semibold text-indigo-900 mb-1">{L('Add Your First Lot', 'Ajouter votre premier lot')}</p>
              <p className="text-xs text-slate-500">{L('Walk through the 6-step wizard for one lot at a time.', "Suivez l'assistant en 6 étapes, un lot à la fois.")}</p>
            </button>

            {/* Card 2 — Import from CSV (iter306) */}
            <button
              type="button"
              onClick={openCsvImport}
              disabled={creatingDraftEvent}
              className="text-center py-8 px-4 border-2 border-dashed border-blue-300 hover:border-blue-500 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-60"
              data-testid="empty-csv-import-cta"
            >
              <FileSpreadsheet className="h-10 w-10 text-blue-400 mx-auto mb-3" />
              <p className="text-sm font-semibold text-blue-900 mb-1">{L('Import Lots from CSV', 'Importer des lots depuis un CSV')}</p>
              <p className="text-xs text-slate-500">{L('Bulk-add up to 50 lots at once from a spreadsheet.', "Importez jusqu'à 50 lots à la fois depuis une feuille de calcul.")}</p>
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {lots.map((lot, idx) => (
              <Card key={lot.id} className="p-3 sm:p-4 bg-slate-50 border-slate-200" data-testid={`lot-card-${idx}`}>
                <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 sm:items-center">
                  {/* Thumbnail */}
                  <div className="w-full sm:w-28 aspect-[4/3] bg-slate-200 rounded-md overflow-hidden flex-shrink-0">
                    {(lot.pendingPhotos || []).length > 0 ? (
                      <img src={lot.pendingPhotos[0].previewUrl} alt={lot.title || `Lot ${idx + 1}`} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Car className="h-8 w-8 text-slate-300" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge className="bg-indigo-600 text-white">{L(`Lot #${idx + 1}`, `Lot n°${idx + 1}`)}</Badge>
                      <span className="text-xs text-slate-500">VIN: …{String(lot.vin || '').slice(-6)}</span>
                      {(lot.pendingPhotos || []).length > 0 && (
                        <Badge variant="outline" className="text-[10px]">
                          <ImageIcon className="h-3 w-3 mr-1" /> {lot.pendingPhotos.length}
                        </Badge>
                      )}
                    </div>
                    <p className="font-semibold text-sm mt-1 line-clamp-1">
                      {lot.year} {lot.make} {lot.model} {lot.trim}
                    </p>
                    <p className="text-xs text-slate-500 line-clamp-1">{lot.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      <DollarSign className="inline h-3 w-3" /> {Number(lot.starting_price).toLocaleString()} CAD · {lot.location_city}, {lot.location_province}
                    </p>
                  </div>
                  <div className="flex gap-2 sm:flex-col sm:items-end">
                    <Button size="sm" variant="outline" onClick={() => openWizardForEdit(idx)} className="flex-1 sm:flex-none min-h-[40px]" data-testid={`lot-edit-btn-${idx}`}>
                      <Edit3 className="h-3.5 w-3.5 mr-1" /> {L('Edit', 'Modifier')}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => openWizardForDuplicate(idx)} className="flex-1 sm:flex-none min-h-[40px] border-blue-300 text-blue-700 hover:bg-blue-50" data-testid={`lot-duplicate-btn-${idx}`}>
                      <Copy className="h-3.5 w-3.5 mr-1" /> {L('Duplicate Lot', 'Dupliquer le lot')}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => removeLot(idx)} className="flex-1 sm:flex-none min-h-[40px] text-red-600 hover:bg-red-50" data-testid={`lot-delete-btn-${idx}`}>
                      <Trash2 className="h-3.5 w-3.5 mr-1" /> {L('Delete', 'Supprimer')}
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Card>

      {/* ========== Bottom CTAs (only after ≥1 lot saved) ========== */}
      {lots.length > 0 && (
        <div className="flex flex-col sm:flex-row gap-2 sm:justify-end" data-testid="submit-row">
          <Button
            variant="outline"
            onClick={() => handleSubmit('draft')}
            disabled={loading}
            className="min-h-[48px] w-full sm:w-auto"
            data-testid="submit-multi-lot-draft-btn"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            {L('Save as Draft', 'Enregistrer comme brouillon')}
          </Button>
          <Button
            variant="outline"
            onClick={() => handleSubmit('schedule')}
            disabled={loading}
            className="min-h-[48px] w-full sm:w-auto border-blue-600 text-blue-700 hover:bg-blue-50"
            data-testid="submit-multi-lot-schedule-btn"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Calendar className="h-4 w-4 mr-1" />}
            {L('Schedule (Upcoming)', 'Planifier (À venir)')}
          </Button>
          <Button
            onClick={() => handleSubmit('live')}
            disabled={loading}
            className="min-h-[48px] w-full sm:w-auto bg-green-600 hover:bg-green-700"
            data-testid="submit-multi-lot-live-btn"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <CheckCircle className="h-4 w-4 mr-1" />}
            {L('Go Live Now', 'Mettre en ligne maintenant')}
          </Button>
        </div>
      )}

      {/* Mobile bottom-sheet for timing-mode info */}
      <Sheet open={!!infoSheet} onOpenChange={(o) => { if (!o) setInfoSheet(null); }}>
        <SheetContent side="bottom" className="rounded-t-2xl" data-testid="timing-info-sheet">
          <SheetHeader className="text-left">
            <SheetTitle>{infoSheet ? getTimingModeLabel(infoSheet, i18n.language) : ''}</SheetTitle>
            <SheetDescription className="text-sm">
              {infoSheet ? getTimingModeDescription(infoSheet, i18n.language) : ''}
            </SheetDescription>
          </SheetHeader>
        </SheetContent>
      </Sheet>

      {/* iter304 — Save Lot Template modal */}
      <SaveTemplateModal
        open={saveTemplateModal}
        onClose={() => setSaveTemplateModal(false)}
        onSave={persistTemplate}
        saving={savingTemplate}
        L={L}
      />

      {/* iter306 — Bulk Import Lots from CSV */}
      <BulkImportLotsCSV
        open={csvImportOpen}
        onClose={() => setCsvImportOpen(false)}
        eventId={draftEventId}
        fr={fr}
        L={L}
        onImported={handleImported}
      />
    </div>
  );
};

// ===================== Per-Lot Wizard =====================

const LotWizard = ({
  STEPS, wizard, L, fr, i18n, vinLoading,
  updateDraft, lookupVin, addPhotos, removePhoto, movePhoto,
  goNext, goPrev, cancelWizard, saveLot, eventDurationSec,
  templates = [], templatesMax = 20, applyTemplate, onSaveAsTemplate,
}) => {
  const d = wizard.draft;
  const stepIdx = wizard.currentStep;
  const progress = ((stepIdx + 1) / STEPS.length) * 100;
  const isQc = String(d.location_province || '').toUpperCase() === 'QC';

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="lot-wizard-page">
      {/* Wizard header with progress */}
      <div className="bg-white dark:bg-slate-900 border-b sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-3 sm:px-4 py-4">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h1 className="text-base sm:text-xl font-bold flex items-center gap-2 min-w-0">
              <Layers className="h-5 w-5 text-blue-600 flex-shrink-0" />
              <span className="truncate">{wizard.lotIndex === 'new' ? L('Add Lot', 'Ajouter un lot') : L('Edit Lot', 'Modifier le lot')}</span>
            </h1>
            <Button variant="ghost" size="sm" onClick={cancelWizard} className="text-slate-600 hover:text-red-600 min-h-[40px]" data-testid="lot-wizard-cancel-btn">
              <X className="h-4 w-4 mr-1" /> {L('Cancel', 'Annuler')}
            </Button>
          </div>
          {/* Step indicators */}
          <div className="flex gap-1 mt-4 overflow-x-auto pb-1 -mx-1 px-1" data-testid="lot-wizard-step-bar">
            {STEPS.map((s, i) => {
              const Icon = s.icon;
              const isActive = i === stepIdx;
              const isDone = i < stepIdx;
              return (
                <div key={s.id} className={`flex items-center gap-1.5 text-xs flex-shrink-0 px-2 py-1 rounded-full ${
                  isActive ? 'text-blue-700 bg-blue-50 font-semibold'
                    : isDone ? 'text-emerald-700' : 'text-slate-400'
                }`}>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
                    isDone ? 'bg-emerald-600 text-white' :
                    isActive ? 'bg-blue-100 text-blue-600 border border-blue-600' :
                    'bg-slate-100 text-slate-400'
                  }`}>
                    {isDone ? <CheckCircle className="h-3.5 w-3.5" /> : <Icon className="h-3 w-3" />}
                  </div>
                  <span className="hidden sm:inline">{fr ? s.frTitle : s.enTitle}</span>
                </div>
              );
            })}
          </div>
          <Progress value={progress} className="h-2 mt-2" />
        </div>
      </div>

      {/* Step content */}
      <div className="max-w-4xl mx-auto px-3 sm:px-4 py-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
              {React.createElement(STEPS[stepIdx].icon, { className: 'h-5 w-5' })}
              {fr ? STEPS[stepIdx].frTitle : STEPS[stepIdx].enTitle}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* === Step 1: VIN & Basic === */}
            {stepIdx === 0 && (
              <div className="space-y-6">
                {/* iter305 — Duplicate Lot banner: only renders when this draft
                    was opened via the "Duplicate Lot" action. Reminds the user
                    that VIN, Mileage and Photos must still be entered. */}
                {wizard._duplicate && (
                  <div className="bg-blue-50 dark:bg-blue-950 border-l-4 border-blue-500 rounded-r-lg p-3 flex items-start gap-2" data-testid="lot-duplicate-banner">
                    <Copy className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-blue-800 dark:text-blue-200">
                      {L(
                        'Lot duplicated — enter the new VIN and add photos to complete this lot.',
                        'Lot dupliqué — entrez le nouveau NIV et ajoutez des photos pour compléter ce lot.',
                      )}
                    </p>
                  </div>
                )}

                {/* iter304 — Use a Template dropdown (only shows when dealer has saved templates) */}
                {templates.length > 0 && (
                  <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-3" data-testid="template-picker-block">
                    <Label className="flex items-center gap-1.5 text-sm font-semibold text-blue-900 dark:text-blue-100">
                      <FolderOpen className="h-4 w-4" /> {L('Use a Template', 'Utiliser un modèle')}
                    </Label>
                    <p className="text-xs text-blue-700 dark:text-blue-300 mt-0.5 mb-2">
                      {L(
                        'Pre-fill Steps 2–5 from a saved template. You can still edit any field.',
                        'Pré-remplir les étapes 2 à 5 depuis un modèle enregistré. Vous pouvez modifier les champs.',
                      )}
                    </p>
                    <Select
                      value={wizard.draft._applied_template_id || ''}
                      onValueChange={(v) => { if (v === '__none__') { updateDraft({ _applied_template_id: '' }); return; } applyTemplate(v); }}
                    >
                      <SelectTrigger data-testid="template-picker-select" className="bg-white dark:bg-slate-900">
                        <SelectValue placeholder={L('No template (start blank)', 'Aucun modèle (formulaire vierge)')} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">{L('No template', 'Aucun modèle')}</SelectItem>
                        {templates.map((tpl) => (
                          <SelectItem key={tpl.id} value={tpl.id} data-testid={`template-option-${tpl.id}`}>
                            {tpl.name}
                            {tpl.fields?.make && ` · ${tpl.fields.make}${tpl.fields.model ? ` ${tpl.fields.model}` : ''}`}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                <div>
                  <Label className="text-base font-semibold">{L('Vehicle Category', 'Catégorie de véhicule')} *</Label>
                  <p className="text-xs sm:text-sm text-slate-500 mb-2">
                    {L(
                      'Pick the category that best matches this lot.',
                      'Choisissez la catégorie qui correspond à ce lot.',
                    )}
                  </p>
                  <VehicleCategoryGrid
                    selectedCategoryId={d.category_id}
                    selectedSubcategoryId={d.subcategory_id}
                    onChange={(catId, subId) => updateDraft({ category_id: catId || '', subcategory_id: subId || '' })}
                  />
                </div>

                <div>
                  <Label>{L('VIN Number', 'Numéro NIV')} *</Label>
                  <p className="text-xs text-slate-500 mb-1">{L('17-character Vehicle Identification Number', 'Numéro d\u2019identification du véhicule (17 caractères)')}</p>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <Input
                      data-testid="wizard-vin-input"
                      autoFocus={!!wizard._duplicate}
                      value={d.vin}
                      maxLength={17}
                      onChange={(e) => updateDraft({ vin: e.target.value.toUpperCase() })}
                      placeholder="e.g., 1HGBH41JXMN109186"
                      className="font-mono"
                    />
                    <Button
                      onClick={lookupVin}
                      disabled={!!vinLoading || d.vin.length !== 17}
                      className="min-h-[44px] sm:w-auto"
                      data-testid="wizard-vin-lookup-btn"
                    >
                      {vinLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Search className="h-4 w-4 mr-1" />}
                      {L('Look Up VIN', 'Rechercher le NIV')}
                    </Button>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">{(d.vin || '').length}/17 {L('characters', 'caractères')}</p>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
                  <div>
                    <Label>{L('Year', 'Année')} *</Label>
                    <Input type="number" data-testid="wizard-year-input" value={d.year} onChange={(e) => updateDraft({ year: e.target.value })} placeholder="2024" />
                  </div>
                  <div>
                    <Label>{L('Make', 'Marque')} *</Label>
                    <Input data-testid="wizard-make-input" value={d.make} onChange={(e) => updateDraft({ make: e.target.value })} placeholder="Toyota" />
                  </div>
                  <div>
                    <Label>{L('Model', 'Modèle')} *</Label>
                    <Input data-testid="wizard-model-input" value={d.model} onChange={(e) => updateDraft({ model: e.target.value })} placeholder="Camry" />
                  </div>
                  <div>
                    <Label>{L('Trim', 'Finition')}</Label>
                    <Input data-testid="wizard-trim-input" value={d.trim} onChange={(e) => updateDraft({ trim: e.target.value })} placeholder="XSE" />
                  </div>
                </div>

                <div>
                  <Label>{L('Body Type', 'Type de carrosserie')} *</Label>
                  <Select value={d.body_type} onValueChange={(v) => updateDraft({ body_type: v })}>
                    <SelectTrigger data-testid="wizard-body-type-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {BODY_TYPES.map((b) => (<SelectItem key={b.value} value={b.value}>{fr ? b.frLabel : b.enLabel}</SelectItem>))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {/* === Step 2: Specifications === */}
            {stepIdx === 1 && (
              <div className="space-y-6">
                <div>
                  <Label className="flex items-center gap-2"><Gauge className="h-4 w-4" /> {L('Mileage (km)', 'Kilométrage (km)')} *</Label>
                  <Input type="number" min={0} data-testid="wizard-mileage-input" value={d.mileage} onChange={(e) => updateDraft({ mileage: e.target.value })} placeholder="50000" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  <div>
                    <Label>{L('Engine', 'Moteur')}</Label>
                    <Input data-testid="wizard-engine-input" value={d.engine_size} onChange={(e) => updateDraft({ engine_size: e.target.value })} placeholder="2.5L I4" />
                  </div>
                  <div>
                    <Label className="flex items-center gap-1.5"><Settings2 className="h-3.5 w-3.5" /> {L('Transmission', 'Boîte')}</Label>
                    <Select value={d.transmission} onValueChange={(v) => updateDraft({ transmission: v })}>
                      <SelectTrigger data-testid="wizard-transmission-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{TRANSMISSIONS.map((tr) => (<SelectItem key={tr.value} value={tr.value}>{fr ? tr.frLabel : tr.enLabel}</SelectItem>))}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>{L('Drivetrain', 'Transmission intégrale')}</Label>
                    <Select value={d.drivetrain} onValueChange={(v) => updateDraft({ drivetrain: v })}>
                      <SelectTrigger data-testid="wizard-drivetrain-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{DRIVETRAINS.map((dt) => (<SelectItem key={dt.value} value={dt.value}>{fr ? dt.frLabel : dt.enLabel}</SelectItem>))}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="flex items-center gap-1.5"><Palette className="h-3.5 w-3.5" /> {L('Exterior Color', 'Couleur extérieure')}</Label>
                    <Input data-testid="wizard-exterior-color-input" value={d.exterior_color} onChange={(e) => updateDraft({ exterior_color: e.target.value })} placeholder="Pearl White" />
                  </div>
                  <div>
                    <Label>{L('Interior Color', 'Couleur intérieure')}</Label>
                    <Input data-testid="wizard-interior-color-input" value={d.interior_color} onChange={(e) => updateDraft({ interior_color: e.target.value })} placeholder="Black Leather" />
                  </div>
                  <div>
                    <Label className="flex items-center gap-1.5"><Fuel className="h-3.5 w-3.5" /> {L('Fuel Type', 'Carburant')}</Label>
                    <Select value={d.fuel_type} onValueChange={(v) => updateDraft({ fuel_type: v })}>
                      <SelectTrigger data-testid="wizard-fuel-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{FUEL_TYPES.map((f) => (<SelectItem key={f.value} value={f.value}>{fr ? f.frLabel : f.enLabel}</SelectItem>))}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>{L('Doors', 'Portes')}</Label>
                    <Input type="number" data-testid="wizard-doors-input" value={d.doors} onChange={(e) => updateDraft({ doors: e.target.value })} placeholder="4" />
                  </div>
                  <div>
                    <Label>{L('Seats', 'Places assises')}</Label>
                    <Input type="number" data-testid="wizard-seats-input" value={d.seats} onChange={(e) => updateDraft({ seats: e.target.value })} placeholder="5" />
                  </div>
                </div>
              </div>
            )}

            {/* === Step 3: Condition Report === */}
            {stepIdx === 2 && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <Label>{L('Title Status', 'Statut du titre')} *</Label>
                    <Select value={d.title_status} onValueChange={(v) => updateDraft({ title_status: v })}>
                      <SelectTrigger data-testid="wizard-title-status-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{TITLE_STATUSES.map((tt) => (<SelectItem key={tt.value} value={tt.value}>{fr ? tt.frLabel : tt.enLabel}</SelectItem>))}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>{L('Condition Rating', 'Évaluation de l\u2019état')} *</Label>
                    <Select value={d.condition_rating} onValueChange={(v) => updateDraft({ condition_rating: v })}>
                      <SelectTrigger data-testid="wizard-condition-rating-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{CONDITIONS.map((c) => (<SelectItem key={c.value} value={c.value}>{fr ? c.frLabel : c.enLabel}</SelectItem>))}</SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label>{L('Known Defects', 'Défauts connus')}</Label>
                  <Textarea data-testid="wizard-defects-input" value={d.known_defects} onChange={(e) => updateDraft({ known_defects: e.target.value })} rows={3} placeholder={L('Describe any known issues, repair needs, etc.', 'Décrivez les défauts connus, réparations à prévoir, etc.')} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <Label>{L('Accident History', 'Antécédents d\u2019accident')}</Label>
                    <Select value={d.accident_history} onValueChange={(v) => updateDraft({ accident_history: v })}>
                      <SelectTrigger data-testid="wizard-accident-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{ACCIDENT_OPTIONS.map((a) => (<SelectItem key={a.value} value={a.value}>{fr ? a.frLabel : a.enLabel}</SelectItem>))}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>{L('Previous Owners', 'Propriétaires précédents')}</Label>
                    <Input type="number" min={0} data-testid="wizard-previous-owners-input" value={d.previous_owners} onChange={(e) => updateDraft({ previous_owners: e.target.value })} placeholder="1" />
                  </div>
                  <div>
                    <Label>{L('Last Service Date', 'Dernière révision')}</Label>
                    <Input type="date" data-testid="wizard-last-service-input" value={d.last_service_date} onChange={(e) => updateDraft({ last_service_date: e.target.value })} />
                  </div>
                </div>
              </div>
            )}

            {/* === Step 4: Photos & Media === */}
            {stepIdx === 3 && (
              <div className="space-y-4">
                <div className={`p-3 rounded-lg ${(d.pendingPhotos || []).length >= MIN_PHOTOS_PER_LOT ? 'bg-green-50 border border-green-200' : 'bg-yellow-50 border border-yellow-200'}`}>
                  <div className="flex items-center gap-2">
                    {(d.pendingPhotos || []).length >= MIN_PHOTOS_PER_LOT ? <CheckCircle className="h-5 w-5 text-green-600" /> : <AlertTriangle className="h-5 w-5 text-yellow-600" />}
                    <span className="font-medium text-sm">
                      {(d.pendingPhotos || []).length} / {MAX_PHOTOS_PER_LOT} {L('photos uploaded', 'photos téléversées')}
                      {(d.pendingPhotos || []).length < MIN_PHOTOS_PER_LOT && (
                        <span className="text-yellow-700 ml-1">({L('minimum 1 required', 'minimum 1 requise')})</span>
                      )}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div>
                    <Label className="inline-flex items-center gap-1">
                      <ImageIcon className="h-4 w-4" /> Photos
                    </Label>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {L(`Minimum 1, maximum ${MAX_PHOTOS_PER_LOT}. First photo becomes the thumbnail.`, `Minimum 1, maximum ${MAX_PHOTOS_PER_LOT}. La 1ʳᵉ photo sert de vignette.`)}
                    </p>
                  </div>
                  <label
                    htmlFor="wizard-photo-input"
                    className="inline-flex items-center justify-center gap-1 px-3 py-2 rounded-md bg-blue-600 text-white text-sm cursor-pointer hover:bg-blue-700 w-full sm:w-auto min-h-[40px]"
                    data-testid="wizard-photo-pick-btn"
                  >
                    <Upload className="h-4 w-4" /> {L('Add Photos', 'Ajouter des photos')}
                  </label>
                  <input
                    id="wizard-photo-input"
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={(e) => addPhotos(e.target.files)}
                    data-testid="wizard-photo-input"
                  />
                </div>

                {(d.pendingPhotos || []).length > 0 && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2" data-testid="wizard-photo-grid">
                    {(d.pendingPhotos || []).map((ph, pIdx) => (
                      <div key={ph.id} className="relative rounded-md overflow-hidden border border-slate-200 bg-slate-50 aspect-square" data-testid={`wizard-photo-thumb-${pIdx}`}>
                        <img src={ph.previewUrl} alt={`Photo ${pIdx + 1}`} className="w-full h-full object-cover" />
                        <div className="absolute top-1 left-1 inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold text-white bg-black/60 rounded">
                          {pIdx + 1}{pIdx === 0 ? ' ★' : ''}
                        </div>
                        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-1 flex items-center justify-between">
                          <button type="button" onClick={() => movePhoto(ph.id, 'left')} className="p-1 rounded bg-white/90 hover:bg-white text-slate-700 disabled:opacity-50" disabled={pIdx === 0} aria-label={L('Move left', 'Déplacer à gauche')} data-testid={`wizard-photo-left-${pIdx}`}>
                            <ArrowLeft className="h-3 w-3" />
                          </button>
                          <button type="button" onClick={() => removePhoto(ph.id)} className="p-1 rounded bg-red-500/90 hover:bg-red-600 text-white" aria-label={L('Remove photo', 'Supprimer la photo')} data-testid={`wizard-photo-remove-${pIdx}`}>
                            <X className="h-3 w-3" />
                          </button>
                          <button type="button" onClick={() => movePhoto(ph.id, 'right')} className="p-1 rounded bg-white/90 hover:bg-white text-slate-700 disabled:opacity-50" disabled={pIdx === (d.pendingPhotos || []).length - 1} aria-label={L('Move right', 'Déplacer à droite')} data-testid={`wizard-photo-right-${pIdx}`}>
                            <ArrowRight className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* === Step 5: Auction Settings === */}
            {stepIdx === 4 && (
              <div className="space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <Label>{L('Starting Price (CAD)', 'Prix de départ (CAD)')} *</Label>
                    <Input type="number" min={1} data-testid="wizard-starting-price-input" value={d.starting_price} onChange={(e) => updateDraft({ starting_price: e.target.value })} />
                  </div>
                  <div>
                    <Label>{L('Reserve Price', 'Prix de réserve')}</Label>
                    <Input type="number" min={0} data-testid="wizard-reserve-input" value={d.reserve_price} onChange={(e) => updateDraft({ reserve_price: e.target.value })} placeholder={L('(optional)', '(optionnel)')} />
                  </div>
                  <div>
                    <Label>{L('Bid Increment', 'Incrément d\u2019enchère')}</Label>
                    <Input type="number" min={1} data-testid="wizard-bid-increment-input" value={d.bid_increment} onChange={(e) => updateDraft({ bid_increment: e.target.value })} />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <Label>{L('City', 'Ville')} *</Label>
                    <Input data-testid="wizard-city-input" value={d.location_city} onChange={(e) => updateDraft({ location_city: e.target.value })} placeholder={L('Montreal', 'Montréal')} />
                  </div>
                  <div>
                    <Label>{L('Province', 'Province')} *</Label>
                    <Select value={d.location_province} onValueChange={(v) => updateDraft({ location_province: v })}>
                      <SelectTrigger data-testid="wizard-province-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{PROVINCES.map((p) => (<SelectItem key={p} value={p}>{p}</SelectItem>))}</SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label>{L('Listing Title (English)', 'Titre (Anglais)')} *</Label>
                  <Input
                    data-testid="wizard-title-en-input"
                    value={d.title}
                    onChange={(e) => {
                      const v = e.target.value;
                      updateDraft({ title: v, ...(((!d.title_fr) || d.title_fr === d.title) ? { title_fr: v } : {}) });
                    }}
                    placeholder="e.g. 2020 Ford F-350 XL Crew Cab"
                  />
                </div>
                <div>
                  <Label>
                    {L('Title (French) / Titre (français)', 'Titre (français)')}
                    {isQc ? ' *' : ` (${L('optional', 'optionnel')})`}
                  </Label>
                  <Input
                    data-testid="wizard-title-fr-input"
                    value={d.title_fr}
                    onChange={(e) => updateDraft({ title_fr: e.target.value })}
                    placeholder="ex. 2020 Ford F-350 XL Crew Cab — véhicule de travail"
                  />
                  {isQc && (
                    <p className="text-[11px] text-slate-500 mt-1">
                      {L('Required for Quebec listings under Bill 96.', 'Obligatoire pour les annonces québécoises (Loi 96).')}
                    </p>
                  )}
                </div>
                <div>
                  <Label>{L('Per-Lot Duration Override (seconds)', 'Durée du lot — dérogation (s)')}</Label>
                  <Input
                    type="number"
                    min={MIN_LOT_DURATION_SECONDS}
                    data-testid="wizard-lot-duration-input"
                    value={d.lot_duration_override}
                    onChange={(e) => updateDraft({ lot_duration_override: e.target.value })}
                    placeholder={String(eventDurationSec)}
                  />
                  <p className="text-[11px] text-slate-500 mt-1">
                    {L(
                      `Leave blank to use the event default (${eventDurationSec}s). Minimum 60 seconds.`,
                      `Laissez vide pour utiliser la valeur par défaut (${eventDurationSec} s). Minimum 60 secondes.`,
                    )}
                  </p>
                </div>
                <div>
                  <Label>{L('Description', 'Description')}</Label>
                  <Textarea data-testid="wizard-description-input" value={d.description} onChange={(e) => updateDraft({ description: e.target.value })} rows={3} placeholder={L('Condition notes, options, equipment, defects…', "Notes sur l'état, options, équipements, défauts…")} />
                </div>

                {/* iter304 — Save as Template */}
                <div className="border-t pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onSaveAsTemplate}
                    className="w-full sm:w-auto min-h-[44px] border-blue-300 text-blue-700 hover:bg-blue-50"
                    data-testid="save-as-template-btn"
                    disabled={templates.length >= templatesMax}
                  >
                    <BookmarkPlus className="h-4 w-4 mr-1" /> {L('Save as Template', 'Enregistrer comme modèle')}
                    <span className="ml-2 text-[10px] text-slate-500">({templates.length}/{templatesMax})</span>
                  </Button>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {L(
                      'Save Make/Model/Specs/Pricing/Location as a reusable template for future lots. VIN, year, mileage and photos are always unique per vehicle.',
                      "Enregistrez Marque/Modèle/Spécifications/Prix/Lieu comme modèle réutilisable. NIV, année, kilométrage et photos restent uniques par véhicule.",
                    )}
                  </p>
                </div>
              </div>
            )}

            {/* === Step 6: Review & Submit === */}
            {stepIdx === 5 && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-base"><Car className="h-4 w-4" /> {L('Vehicle Info', 'Infos du véhicule')}</CardTitle>
                    </CardHeader>
                    <CardContent className="text-xs sm:text-sm space-y-1">
                      <p><strong>VIN:</strong> {d.vin}</p>
                      <p><strong>{L('Year/Make/Model', 'Année/Marque/Modèle')}:</strong> {d.year} {d.make} {d.model} {d.trim}</p>
                      <p><strong>{L('Body', 'Carrosserie')}:</strong> {d.body_type}</p>
                      <p><strong>{L('Mileage', 'Kilométrage')}:</strong> {d.mileage} km</p>
                      <p><strong>{L('Transmission', 'Boîte')}:</strong> {d.transmission}</p>
                      <p><strong>{L('Title Status', 'Titre')}:</strong> {d.title_status}</p>
                      <p><strong>{L('Condition', 'État')}:</strong> {d.condition_rating}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-base"><DollarSign className="h-4 w-4" /> {L('Auction Settings', 'Vente aux enchères')}</CardTitle>
                    </CardHeader>
                    <CardContent className="text-xs sm:text-sm space-y-1">
                      <p><strong>{L('Title (EN)', 'Titre (EN)')}:</strong> {d.title}</p>
                      {d.title_fr && <p><strong>{L('Title (FR)', 'Titre (FR)')}:</strong> {d.title_fr}</p>}
                      <p><strong>{L('Starting', 'Départ')}:</strong> ${Number(d.starting_price).toLocaleString()} CAD</p>
                      {d.reserve_price && <p><strong>{L('Reserve', 'Réserve')}:</strong> ${Number(d.reserve_price).toLocaleString()} CAD</p>}
                      <p><strong>{L('Increment', 'Incrément')}:</strong> ${d.bid_increment}</p>
                      <p><strong>{L('Location', 'Lieu')}:</strong> {d.location_city}, {d.location_province}</p>
                      <p><strong>Photos:</strong> {(d.pendingPhotos || []).length}</p>
                    </CardContent>
                  </Card>
                </div>

                {(d.pendingPhotos || []).length < MIN_PHOTOS_PER_LOT && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="text-xs sm:text-sm text-red-700">
                      <p className="font-medium">{L('Missing required photos', 'Photos requises manquantes')}</p>
                      <p>{L(`At least ${MIN_PHOTOS_PER_LOT} photo is required.`, `Au moins ${MIN_PHOTOS_PER_LOT} photo est requise.`)}</p>
                    </div>
                  </div>
                )}

                <Card className="bg-yellow-50 border-yellow-200">
                  <CardContent className="pt-4">
                    <div className="flex items-start gap-2">
                      <Shield className="h-5 w-5 text-yellow-600 mt-0.5 flex-shrink-0" />
                      <div className="text-xs sm:text-sm text-yellow-800 dark:text-yellow-200">
                        <p className="font-medium mb-1">{L('Seller Acknowledgment', 'Reconnaissance du vendeur')}</p>
                        <p>{L(
                          'By saving this lot you confirm the info is accurate and you have legal authority to sell.',
                          'En enregistrant ce lot, vous confirmez que les informations sont exactes et que vous avez l\u2019autorité légale de vendre.',
                        )}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Wizard navigation */}
        <div className="flex flex-col-reverse sm:flex-row justify-between gap-3 mt-6">
          <Button variant="outline" onClick={goPrev} disabled={stepIdx === 0} className="w-full sm:w-auto gap-2 min-h-[48px]" data-testid="wizard-prev-btn">
            <ChevronLeft className="h-4 w-4" /> {L('Previous', 'Précédent')}
          </Button>
          {stepIdx < STEPS.length - 1 ? (
            <Button onClick={goNext} className="w-full sm:w-auto gap-2 min-h-[48px]" data-testid="wizard-next-btn">
              {L('Next', 'Suivant')} <ChevronRight className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              onClick={() => {
                // Re-run all step validations before commit.
                if (!validateAll(wizard.draft, L)) return;
                saveLot();
              }}
              className="w-full sm:w-auto gap-2 min-h-[48px] bg-emerald-600 hover:bg-emerald-700"
              data-testid="wizard-save-lot-btn"
            >
              <CheckCircle className="h-4 w-4" /> {L('Save Lot', 'Enregistrer le lot')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

// Final cross-step validation
const validateAll = (d, L) => {
  if (!d.category_id) { toast.error(L('Step 1 — Vehicle category required', 'Étape 1 — Catégorie requise')); return false; }
  if (!d.vin || d.vin.length !== 17) { toast.error(L('Step 1 — VIN must be 17 characters', 'Étape 1 — NIV à 17 caractères')); return false; }
  if (!d.year || !d.make || !d.model || !d.body_type) { toast.error(L('Step 1 — Year/Make/Model/Body required', 'Étape 1 — Année/Marque/Modèle/Carrosserie requis')); return false; }
  if (!d.mileage && d.mileage !== 0) { toast.error(L('Step 2 — Mileage required', 'Étape 2 — Kilométrage requis')); return false; }
  if ((d.pendingPhotos || []).length < MIN_PHOTOS_PER_LOT) {
    toast.error(L(`Step 4 — At least ${MIN_PHOTOS_PER_LOT} photo required`, `Étape 4 — Au moins ${MIN_PHOTOS_PER_LOT} photo requise`));
    return false;
  }
  if (!d.starting_price || Number(d.starting_price) <= 0) { toast.error(L('Step 5 — Starting price > 0', 'Étape 5 — Prix de départ > 0')); return false; }
  if (!d.location_city || !d.location_province) { toast.error(L('Step 5 — City and Province required', 'Étape 5 — Ville et Province requises')); return false; }
  if (!d.title) { toast.error(L('Step 5 — Listing title required', 'Étape 5 — Titre requis')); return false; }
  if (String(d.location_province || '').toUpperCase() === 'QC' && !String(d.title_fr || '').trim()) {
    toast.error(L('Step 5 — French title required for QC lots (Bill 96)', 'Étape 5 — Titre français requis (Loi 96)'));
    return false;
  }
  if (d.lot_duration_override && Number(d.lot_duration_override) < MIN_LOT_DURATION_SECONDS) {
    toast.error(L(`Step 5 — Lot duration ≥ ${MIN_LOT_DURATION_SECONDS}s`, `Étape 5 — Durée du lot ≥ ${MIN_LOT_DURATION_SECONDS}s`));
    return false;
  }
  return true;
};

export default CreateVehicleMultiLotPage;

// ===================== SaveTemplateModal (iter304) =====================
const SaveTemplateModal = ({ open, onClose, onSave, saving, L }) => {
  const [name, setName] = useState('');
  useEffect(() => { if (!open) setName(''); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[9999] bg-black/60 flex items-center justify-center p-4" data-testid="save-template-modal">
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-2xl w-full max-w-md p-5">
        <div className="flex items-center gap-2 mb-1">
          <BookmarkPlus className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">{L('Save Lot Template', 'Enregistrer un modèle de lot')}</h3>
        </div>
        <p className="text-xs text-slate-500 mb-4">
          {L(
            'Templates speed up creating similar lots later. Maximum 60 characters.',
            'Les modèles accélèrent la création de lots similaires. Maximum 60 caractères.',
          )}
        </p>
        <Label htmlFor="tpl-name" className="text-xs">{L('Template name', 'Nom du modèle')}</Label>
        <Input
          id="tpl-name"
          data-testid="save-template-name-input"
          autoFocus
          maxLength={60}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={L('e.g. Ford F-350 Work Truck', 'ex. Ford F-350 utilitaire')}
          disabled={saving}
        />
        <p className="text-[10px] text-slate-400 mt-1 text-right">{name.length}/60</p>
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={onClose} disabled={saving} data-testid="save-template-cancel-btn">
            <X className="h-4 w-4 mr-1" /> {L('Cancel', 'Annuler')}
          </Button>
          <Button
            onClick={() => onSave(name)}
            disabled={saving || !name.trim()}
            className="bg-blue-600 hover:bg-blue-700"
            data-testid="save-template-confirm-btn"
          >
            {saving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
            {L('Save Template', 'Enregistrer le modèle')}
          </Button>
        </div>
      </div>
    </div>
  );
};

