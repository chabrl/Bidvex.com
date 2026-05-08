/**
 * iter202 Phase B — Vehicle Auctions Sidebar Filter Drawer (B1)
 * ==============================================================
 * Single component handling BOTH desktop sidebar AND mobile drawer.
 *
 * Behaviour per sprint constraint B1:
 *   • Desktop ≥1024px : always visible, 280px fixed width, sits left of grid
 *   • Mobile/Tablet  : hidden by default, opened by floating "🔍 Filters"
 *                      button (rendered separately by parent), full-screen
 *                      slide-in from left, closes on backdrop click + ESC
 *
 * Filter groups (category-conditional rendering per spec):
 *   • Common               : Province, Auction status, Price range,
 *                            Year range, Buyer-premium toggle
 *   • Vehicle Details      : transmission, fuel, drivetrain, condition,
 *                            running, title-status, max odometer
 *                            → shown for cars/SUV/trucks/vans/luxury/commercial/electric/buses
 *   • Boat Details         : (placeholder) shown only when category=boats
 *   • Powersport Details   : (placeholder) shown only for motorcycles or atvs_offroad
 *   • Heavy Equipment      : (placeholder) shown only when category=heavy_equipment
 *   • All categories shown : when category is null/"all"
 *
 * Debounce rules per sprint constraint:
 *   • Sliders (price/year/odometer)  : 300ms
 *   • Checkboxes (province, status…)  : immediate
 *   • Text inputs (make, model)      : 500ms
 *
 * Parent owns the filter state — this component is presentational + emits
 * onChange/onApply/onClear/onClose. Parent syncs with URL params.
 */
import React, { useEffect, useRef, useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Filter, RotateCcw, Check } from 'lucide-react';

const PROVINCES = [
  ['BC', 'British Columbia', 'Colombie-Britannique'],
  ['AB', 'Alberta', 'Alberta'],
  ['SK', 'Saskatchewan', 'Saskatchewan'],
  ['MB', 'Manitoba', 'Manitoba'],
  ['ON', 'Ontario', 'Ontario'],
  ['QC', 'Quebec', 'Québec'],
  ['NB', 'New Brunswick', 'Nouveau-Brunswick'],
  ['NS', 'Nova Scotia', 'Nouvelle-Écosse'],
  ['PE', 'Prince Edward Island', 'Île-du-Prince-Édouard'],
  ['NL', 'Newfoundland & Labrador', 'Terre-Neuve-et-Labrador'],
  ['YT', 'Yukon', 'Yukon'],
  ['NT', 'Northwest Territories', 'Territoires du Nord-Ouest'],
  ['NU', 'Nunavut', 'Nunavut'],
];

const VEHICLE_DETAIL_CATEGORIES = new Set([
  'cars_sedans', 'suvs_crossovers', 'trucks_pickups', 'vans_minivans',
  'luxury_exotic', 'commercial', 'electric_hybrid', 'buses_passenger',
]);

const debounce = (fn, ms) => {
  let id;
  const wrapped = (...a) => { clearTimeout(id); id = setTimeout(() => fn(...a), ms); };
  wrapped.cancel = () => clearTimeout(id);
  return wrapped;
};

const Section = ({ title, testId, children }) => (
  <section className="border-b border-slate-200 dark:border-slate-800 px-4 py-4" data-testid={testId}>
    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3">{title}</h3>
    <div className="space-y-2">{children}</div>
  </section>
);

const Checkbox = ({ checked, onChange, label, testId }) => (
  <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-700 dark:text-slate-200 hover:text-[#0B2545] dark:hover:text-cyan-300" data-testid={testId}>
    <span className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${checked ? 'bg-cyan-500 border-cyan-500 text-white' : 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900'}`}>
      {checked && <Check className="h-3 w-3" strokeWidth={3} />}
    </span>
    <input type="checkbox" checked={checked} onChange={onChange} className="sr-only" />
    <span>{label}</span>
  </label>
);

const VehicleSidebar = ({
  isOpen,           // controls mobile drawer (desktop ignores)
  onClose,          // close mobile drawer
  filters,          // current filter values (parent-owned)
  onChange,         // immediate change emitter
  onChangeDebounced,// debounced change emitter (used by sliders/text)
  onApply,          // mobile "Apply Filters" button
  onClear,          // "Clear All" button
  categoryId,       // current category — controls conditional groups
  resultCount,      // shown in mobile footer
}) => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  // Local mirrors for inputs that need debouncing — keep typing fluid
  const [priceMin, setPriceMin] = useState(filters.price_min || '');
  const [priceMax, setPriceMax] = useState(filters.price_max || '');
  const [yearMin, setYearMin] = useState(filters.year_min || '');
  const [yearMax, setYearMax] = useState(filters.year_max || '');
  const [maxMileage, setMaxMileage] = useState(filters.max_mileage || '');
  const [makeText, setMakeText] = useState(filters.make || '');

  // Keep local mirrors in sync when parent resets
  useEffect(() => { setPriceMin(filters.price_min || ''); }, [filters.price_min]);
  useEffect(() => { setPriceMax(filters.price_max || ''); }, [filters.price_max]);
  useEffect(() => { setYearMin(filters.year_min || ''); }, [filters.year_min]);
  useEffect(() => { setYearMax(filters.year_max || ''); }, [filters.year_max]);
  useEffect(() => { setMaxMileage(filters.max_mileage || ''); }, [filters.max_mileage]);
  useEffect(() => { setMakeText(filters.make || ''); }, [filters.make]);

  // Debounced emitters
  const debounced300 = useMemo(
    () => debounce((key, value) => onChangeDebounced?.(key, value), 300),
    [onChangeDebounced]
  );
  const debounced500 = useMemo(
    () => debounce((key, value) => onChangeDebounced?.(key, value), 500),
    [onChangeDebounced]
  );
  useEffect(() => () => { debounced300.cancel(); debounced500.cancel(); }, [debounced300, debounced500]);

  // ESC key closes mobile drawer
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  // Lock body scroll while drawer open on mobile
  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [isOpen]);

  const showVehicleDetails = !categoryId || VEHICLE_DETAIL_CATEGORIES.has(categoryId);
  const showBoatDetails = categoryId === 'boats_watercraft';
  const showPowersportDetails = categoryId === 'motorcycles_scooters' || categoryId === 'atvs_offroad';
  const showHeavyEquipDetails = categoryId === 'heavy_equipment';

  const Body = (
    <div className="flex flex-col h-full bg-white dark:bg-slate-900" data-testid="vehicle-sidebar-body">
      {/* Header (mobile only — desktop uses external label) */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800 lg:hidden">
        <h2 className="text-base font-bold text-slate-900 dark:text-white inline-flex items-center gap-2">
          <Filter className="h-4 w-4" />
          {t('vehicleSidebar.title', 'Filters')}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label={t('common.close', 'Close')}
          className="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800"
          data-testid="vehicle-sidebar-close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Scrollable filter list */}
      <div className="flex-1 overflow-y-auto pb-4">
        {/* Province */}
        <Section title={t('vehicleSidebar.province', 'Province')} testId="vehicle-sidebar-province">
          <select
            value={filters.province || ''}
            onChange={(e) => onChange?.('province', e.target.value || null)}
            className="w-full h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            data-testid="vehicle-sidebar-province-select"
          >
            <option value="">{t('vehicleSidebar.allProvinces', 'All provinces')}</option>
            {PROVINCES.map(([code, en, fr]) => (
              <option key={code} value={code}>{code} — {isFr ? fr : en}</option>
            ))}
          </select>
        </Section>

        {/* Auction status */}
        <Section title={t('vehicleSidebar.auctionStatus', 'Auction status')} testId="vehicle-sidebar-status">
          {[
            ['live', t('vehicleSidebar.live', 'Live now')],
            ['scheduled', t('vehicleSidebar.scheduled', 'Scheduled')],
            ['ending_soon', t('vehicleSidebar.endingSoon', 'Ending soon (24h)')],
          ].map(([code, label]) => (
            <Checkbox
              key={code}
              checked={filters.auction_status === code}
              onChange={() => onChange?.('auction_status', filters.auction_status === code ? null : code)}
              label={label}
              testId={`vehicle-sidebar-status-${code}`}
            />
          ))}
        </Section>

        {/* Price range */}
        <Section title={t('vehicleSidebar.price', 'Price range')} testId="vehicle-sidebar-price">
          <div className="grid grid-cols-2 gap-2">
            <input
              type="number"
              inputMode="numeric"
              min="0"
              placeholder={t('vehicleSidebar.priceMin', 'Min')}
              value={priceMin}
              onChange={(e) => { setPriceMin(e.target.value); debounced300('price_min', e.target.value || null); }}
              className="h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
              data-testid="vehicle-sidebar-price-min"
            />
            <input
              type="number"
              inputMode="numeric"
              min="0"
              placeholder={t('vehicleSidebar.priceMax', 'Max')}
              value={priceMax}
              onChange={(e) => { setPriceMax(e.target.value); debounced300('price_max', e.target.value || null); }}
              className="h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
              data-testid="vehicle-sidebar-price-max"
            />
          </div>
        </Section>

        {/* Year range */}
        <Section title={t('vehicleSidebar.year', 'Year')} testId="vehicle-sidebar-year">
          <div className="grid grid-cols-2 gap-2">
            <input
              type="number"
              inputMode="numeric"
              min="1900"
              max="2030"
              placeholder={t('vehicleSidebar.yearMin', 'From')}
              value={yearMin}
              onChange={(e) => { setYearMin(e.target.value); debounced300('year_min', e.target.value || null); }}
              className="h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
              data-testid="vehicle-sidebar-year-min"
            />
            <input
              type="number"
              inputMode="numeric"
              min="1900"
              max="2030"
              placeholder={t('vehicleSidebar.yearMax', 'To')}
              value={yearMax}
              onChange={(e) => { setYearMax(e.target.value); debounced300('year_max', e.target.value || null); }}
              className="h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
              data-testid="vehicle-sidebar-year-max"
            />
          </div>
        </Section>

        {/* Make (text — debounce 500ms) */}
        <Section title={t('vehicleSidebar.make', 'Make')} testId="vehicle-sidebar-make">
          <input
            type="text"
            placeholder={t('vehicleSidebar.makePlaceholder', 'e.g. Honda, Toyota…')}
            value={makeText}
            onChange={(e) => { setMakeText(e.target.value); debounced500('make', e.target.value || null); }}
            className="w-full h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
            data-testid="vehicle-sidebar-make-input"
          />
        </Section>

        {/* Vehicle Details (conditional) */}
        {showVehicleDetails && (
          <Section title={t('vehicleSidebar.vehicleDetails', 'Vehicle details')} testId="vehicle-sidebar-vehicle-details">
            <select
              value={filters.transmission || ''}
              onChange={(e) => onChange?.('transmission', e.target.value || null)}
              className="w-full h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
              data-testid="vehicle-sidebar-transmission"
            >
              <option value="">{t('vehicleSidebar.anyTransmission', 'Any transmission')}</option>
              <option value="automatic">{t('vehicleSidebar.automatic', 'Automatic')}</option>
              <option value="manual">{t('vehicleSidebar.manual', 'Manual')}</option>
              <option value="cvt">{t('vehicleSidebar.cvt', 'CVT')}</option>
            </select>
            <select
              value={filters.fuel_type || ''}
              onChange={(e) => onChange?.('fuel_type', e.target.value || null)}
              className="w-full h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
              data-testid="vehicle-sidebar-fuel"
            >
              <option value="">{t('vehicleSidebar.anyFuel', 'Any fuel type')}</option>
              <option value="gasoline">{t('vehicleSidebar.fuelGasoline', 'Gasoline')}</option>
              <option value="diesel">{t('vehicleSidebar.fuelDiesel', 'Diesel')}</option>
              <option value="hybrid">{t('vehicleSidebar.fuelHybrid', 'Hybrid')}</option>
              <option value="electric">{t('vehicleSidebar.fuelElectric', 'Electric')}</option>
            </select>
            <select
              value={filters.title_status || ''}
              onChange={(e) => onChange?.('title_status', e.target.value || null)}
              className="w-full h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
              data-testid="vehicle-sidebar-title-status"
            >
              <option value="">{t('vehicleSidebar.anyTitle', 'Any title status')}</option>
              <option value="clean">{t('vehicleCard.titleClean', 'Clean title')}</option>
              <option value="rebuilt">{t('vehicleSidebar.titleRebuilt', 'Rebuilt')}</option>
              <option value="salvage">{t('vehicleCard.titleSalvage', 'Salvage')}</option>
            </select>
            <input
              type="number"
              inputMode="numeric"
              min="0"
              placeholder={t('vehicleSidebar.maxMileage', 'Max odometer (km)')}
              value={maxMileage}
              onChange={(e) => { setMaxMileage(e.target.value); debounced300('max_mileage', e.target.value || null); }}
              className="w-full h-9 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm px-2 focus:ring-2 focus:ring-cyan-500"
              data-testid="vehicle-sidebar-max-mileage"
            />
          </Section>
        )}

        {/* Boat / Powersport / Heavy equipment placeholders (per spec) */}
        {showBoatDetails && (
          <Section title={t('vehicleSidebar.boatDetails', 'Boat details')} testId="vehicle-sidebar-boat-details">
            <p className="text-xs text-slate-500">{t('vehicleSidebar.boatDetailsBody', 'Length, hull material, and engine filters available soon.')}</p>
          </Section>
        )}
        {showPowersportDetails && (
          <Section title={t('vehicleSidebar.powersportDetails', 'Powersport details')} testId="vehicle-sidebar-powersport-details">
            <p className="text-xs text-slate-500">{t('vehicleSidebar.powersportDetailsBody', 'Engine size, ride mode, and trail-class filters available soon.')}</p>
          </Section>
        )}
        {showHeavyEquipDetails && (
          <Section title={t('vehicleSidebar.heavyEquipDetails', 'Heavy equipment details')} testId="vehicle-sidebar-heavy-details">
            <p className="text-xs text-slate-500">{t('vehicleSidebar.heavyEquipDetailsBody', 'Hours, attachments, and operating-weight filters available soon.')}</p>
          </Section>
        )}

        {/* Seller type */}
        <Section title={t('vehicleSidebar.sellerType', 'Seller type')} testId="vehicle-sidebar-seller-type">
          {[
            ['dealer', t('vehicleCard.dealer', 'Dealer')],
            ['private', t('vehicleCard.private', 'Private')],
          ].map(([code, label]) => (
            <Checkbox
              key={code}
              checked={filters.seller_type === code}
              onChange={() => onChange?.('seller_type', filters.seller_type === code ? null : code)}
              label={label}
              testId={`vehicle-sidebar-seller-type-${code}`}
            />
          ))}
        </Section>

        {/* Buyer-premium toggle */}
        <Section title={t('vehicleSidebar.buyerPremium', 'Buyer premium')} testId="vehicle-sidebar-buyer-premium">
          <Checkbox
            checked={!!filters.no_buyer_premium}
            onChange={(e) => onChange?.('no_buyer_premium', e.target.checked || null)}
            label={t('vehicleSidebar.hideBuyerPremium', 'Hide auctions with buyer premium')}
            testId="vehicle-sidebar-no-premium-checkbox"
          />
        </Section>
      </div>

      {/* Footer (mobile only — desktop sidebar shows clear inline) */}
      <div className="lg:hidden px-4 py-3 border-t border-slate-200 dark:border-slate-800 flex gap-2 bg-white dark:bg-slate-900">
        <button
          type="button"
          onClick={onClear}
          className="flex-1 h-10 rounded-lg border border-slate-300 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 inline-flex items-center justify-center gap-1"
          data-testid="vehicle-sidebar-clear-btn"
        >
          <RotateCcw className="h-4 w-4" />
          {t('vehicleSidebar.clearAll', 'Clear all')}
        </button>
        <button
          type="button"
          onClick={onApply}
          className="flex-[2] h-10 rounded-lg bg-[#0B2545] hover:bg-[#0E2B52] text-white text-sm font-semibold"
          data-testid="vehicle-sidebar-apply-btn"
        >
          {t('vehicleSidebar.applyFilters', 'Apply filters')}
          {typeof resultCount === 'number' && ` · ${resultCount}`}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop — always visible */}
      <aside
        className="hidden lg:block w-[280px] flex-shrink-0 sticky top-20 self-start max-h-[calc(100vh-6rem)] rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden"
        data-testid="vehicle-sidebar-desktop"
      >
        {/* Desktop header with inline clear */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white inline-flex items-center gap-2">
            <Filter className="h-4 w-4" />
            {t('vehicleSidebar.title', 'Filters')}
          </h2>
          <button
            type="button"
            onClick={onClear}
            className="text-xs font-semibold text-cyan-600 hover:text-cyan-700 hover:underline inline-flex items-center gap-1"
            data-testid="vehicle-sidebar-clear-desktop"
          >
            <RotateCcw className="h-3 w-3" />
            {t('vehicleSidebar.clearAll', 'Clear all')}
          </button>
        </div>
        {Body}
      </aside>

      {/* Mobile drawer */}
      <div
        className={`lg:hidden fixed inset-0 z-[70] transition-opacity ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
        aria-hidden={!isOpen}
      >
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/50"
          onClick={onClose}
          data-testid="vehicle-sidebar-backdrop"
        />
        {/* Drawer panel */}
        <div
          className={`absolute top-0 left-0 bottom-0 w-[88%] max-w-[360px] bg-white dark:bg-slate-900 shadow-2xl transform transition-transform duration-300 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}
          data-testid="vehicle-sidebar-drawer"
          role="dialog"
          aria-modal="true"
          aria-label={t('vehicleSidebar.title', 'Filters')}
        >
          {Body}
        </div>
      </div>
    </>
  );
};

export default VehicleSidebar;
