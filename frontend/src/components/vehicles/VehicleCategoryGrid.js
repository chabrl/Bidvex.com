/**
 * iter201 — Phase 2 — Vehicle Category Grid
 *
 * 15-category icon picker per CEO spec. Used by:
 *   • CreateVehicleListingPage (replaces flat input)
 *   • Search filters (future)
 *   • Admin listing reviews (future)
 *
 * Per CEO spec UI requirements:
 *   • 3-column responsive grid on desktop
 *   • 2-column on mobile
 *   • Click → expand subcategory dropdown
 *   • Selected category shown as blue pill with X to clear
 *   • Bilingual labels (EN/FR via useTranslation)
 *
 * Per CEO constraint #3:
 *   • `parts_accessories` is the only category that does NOT require a dealer
 *     licence. The grid surfaces a green "Open to all sellers" badge on it.
 */
import API_BASE from '../../config';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Loader2, X, ChevronDown, Check } from 'lucide-react';
import { Badge } from '../ui/badge';

const API = API_BASE;

const VehicleCategoryGrid = ({
  selectedCategoryId,
  selectedSubcategoryId,
  onChange,           // (categoryId, subcategoryId, fullCategory) => void
  disabled = false,
}) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/vehicles/categories`);
        if (!cancelled) setCategories(res.data?.items || []);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail || 'Failed to load categories');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const selected = useMemo(
    () => categories.find((c) => c.id === selectedCategoryId) || null,
    [categories, selectedCategoryId]
  );

  const handleCategoryClick = (cat) => {
    if (disabled) return;
    if (selectedCategoryId === cat.id) {
      // Clicking the selected card again collapses subcategory dropdown but keeps selection
      return;
    }
    onChange?.(cat.id, null, cat);
  };

  const handleSubcategoryChange = (e) => {
    if (!selected) return;
    const subId = e.target.value || null;
    onChange?.(selected.id, subId, selected);
  };

  const handleClear = () => {
    if (disabled) return;
    onChange?.(null, null, null);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 py-6" data-testid="vehicle-category-grid-loading">
        <Loader2 className="h-4 w-4 animate-spin" /> {isFr ? 'Chargement des catégories…' : 'Loading categories…'}
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2" data-testid="vehicle-category-grid-error">
        {error}
      </div>
    );
  }

  return (
    <div data-testid="vehicle-category-grid">
      {/* Selected pill */}
      {selected && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span
            className="inline-flex items-center gap-2 bg-blue-600 text-white px-3 py-1.5 rounded-full text-sm font-semibold"
            data-testid="vehicle-category-selected-pill"
          >
            <span aria-hidden>{selected.icon}</span>
            {isFr ? selected.label_fr : selected.label_en}
            <button
              type="button"
              onClick={handleClear}
              className="hover:bg-blue-700 rounded-full p-0.5"
              aria-label={isFr ? 'Effacer la sélection' : 'Clear selection'}
              data-testid="vehicle-category-clear-btn"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </span>
          {!selected.requires_dealer_license && (
            <Badge className="bg-emerald-100 text-emerald-800 border border-emerald-300">
              {isFr ? 'Ouvert à tous les vendeurs' : 'Open to all sellers'}
            </Badge>
          )}
        </div>
      )}

      {/* Category icon grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {categories.map((cat) => {
          const isSelected = selectedCategoryId === cat.id;
          const label = isFr ? cat.label_fr : cat.label_en;
          return (
            <button
              key={cat.id}
              type="button"
              onClick={() => handleCategoryClick(cat)}
              disabled={disabled}
              className={`group relative flex flex-col items-center justify-center text-center rounded-xl border-2 px-3 py-4 transition-all ${
                isSelected
                  ? 'border-blue-600 bg-blue-50 dark:bg-blue-950/30 shadow-md'
                  : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-slate-900 hover:border-blue-300 hover:bg-blue-50/50 hover:-translate-y-0.5 hover:shadow-sm'
              } ${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
              data-testid={`vehicle-category-card-${cat.id}`}
            >
              {isSelected && (
                <span className="absolute top-2 right-2 bg-blue-600 text-white rounded-full p-0.5">
                  <Check className="h-3 w-3" />
                </span>
              )}
              <span className="text-3xl sm:text-4xl mb-1.5" aria-hidden>{cat.icon}</span>
              <span className={`text-xs sm:text-sm font-semibold leading-tight ${isSelected ? 'text-blue-700 dark:text-blue-300' : 'text-gray-800 dark:text-gray-100'}`}>
                {label}
              </span>
              {!cat.requires_dealer_license && (
                <span className="absolute bottom-1.5 left-1/2 -translate-x-1/2 text-[9px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">
                  {isFr ? 'OUVERT' : 'OPEN'}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Subcategory dropdown (only when a category is selected) */}
      {selected && selected.subcategories?.length > 0 && (
        <div className="mt-4" data-testid="vehicle-subcategory-block">
          <label className="block text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
            {isFr ? 'Sous-catégorie' : 'Subcategory'}
          </label>
          <div className="relative">
            <select
              value={selectedSubcategoryId || ''}
              onChange={handleSubcategoryChange}
              disabled={disabled}
              className="w-full appearance-none rounded-lg border border-gray-300 bg-white dark:bg-slate-900 dark:border-gray-700 px-3 py-2 pr-9 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              data-testid="vehicle-subcategory-select"
            >
              <option value="">{isFr ? '— Choisir une sous-catégorie —' : '— Choose a subcategory —'}</option>
              {selected.subcategories.map((s) => (
                <option key={s.id} value={s.id}>
                  {isFr ? s.label_fr : s.label_en}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
          </div>
          {!selected.requires_dealer_license && (
            <p className="mt-2 text-xs text-emerald-700 dark:text-emerald-300">
              {isFr
                ? selected.description_fr || "Les pièces ne nécessitent pas de licence de concessionnaire."
                : selected.description_en || 'Parts do not require a dealer licence.'}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default VehicleCategoryGrid;
