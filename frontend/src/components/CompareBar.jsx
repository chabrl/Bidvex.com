/**
 * iter364 — CompareBar (sticky bottom bar) + CompareCheckbox (per-card).
 *
 * Renders nothing until ≥1 item is selected. From 1 selection shows
 * a "Select 1 more to compare" state; from 2+ enables "Compare Now".
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { X, GitCompare, Trash2 } from 'lucide-react';
import { useCompare } from '../contexts/CompareContext';
import SafeImage from './SafeImage';

const COPY = {
  en: {
    label: 'Compare',
    tooltip: 'Add to compare',
    tooltipMax: 'Max 4 items to compare',
    selected: (n) => `${n} selected`,
    hint:  (n) => n === 1 ? 'Select 1 more to compare' : 'Compare Now',
    cta:   'Compare Now',
    clear: 'Clear',
    close: 'Remove from compare',
  },
  fr: {
    label: 'Comparer',
    tooltip: 'Ajouter à la comparaison',
    tooltipMax: 'Maximum 4 articles à comparer',
    selected: (n) => `${n} sélectionné${n > 1 ? 's' : ''}`,
    hint: (n) => n === 1 ? 'Sélectionnez-en 1 de plus' : 'Comparer maintenant',
    cta: 'Comparer maintenant',
    clear: 'Effacer',
    close: 'Retirer de la comparaison',
  },
};

export function CompareCheckbox({ item, section = 'marketplace', className = '' }) {
  const { toggle, isSelected, count, MAX_ITEMS } = useCompare();
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const t = COPY[lang];
  const active = isSelected(item?.id || item?._id);
  const disabled = !active && count >= MAX_ITEMS;

  const onClick = (e) => {
    e.stopPropagation();
    e.preventDefault();
    toggle(item, section);
  };

  // iter366 — Circular icon-only compare button (was a pill with "Compare"
  // label overlapping the auction timer). Small footprint, positioned
  // bottom-right of the card image via the wrapper's `absolute bottom-2
  // right-2`. Never covers timer, current-bid, buy-now or seller info.
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={active ? `${t.label} ✓` : (disabled ? t.tooltipMax : t.tooltip)}
      aria-label={active ? `${t.label} ✓` : t.tooltip}
      aria-pressed={active}
      className={`inline-flex items-center justify-center w-8 h-8 rounded-full transition-all shadow-md ring-1 ring-black/5 ${
        active
          ? 'bg-primary text-white scale-110 ring-primary/40'
          : disabled
            ? 'bg-slate-100/95 text-slate-400 cursor-not-allowed'
            : 'bg-white/95 text-slate-700 hover:bg-white hover:scale-105 hover:text-primary'
      } ${className}`}
      data-testid={`compare-checkbox-${item?.id || item?._id}`}
    >
      <GitCompare className="h-4 w-4" aria-hidden="true" />
      {active && (
        <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 ring-2 ring-white" aria-hidden="true" />
      )}
    </button>
  );
}

export default function CompareBar() {
  const { selected, remove, clear, count } = useCompare();
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const t = COPY[lang];

  if (count === 0) return null;

  const canCompare = count >= 2;

  return (
    <div
      role="region"
      aria-label={t.label}
      className="fixed bottom-0 left-0 right-0 z-50 bg-[#0B2545] text-white shadow-[0_-4px_24px_rgba(0,0,0,0.25)]"
      data-testid="compare-bar"
    >
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <GitCompare className="h-5 w-5 text-[#3FB4CB] flex-shrink-0" />
          <div className="flex gap-2 overflow-x-auto flex-1" data-testid="compare-bar-thumbs">
            {selected.map((item) => (
              <div
                key={item.id}
                className="relative flex items-center gap-2 bg-white/10 rounded-lg px-2 py-1 min-w-[100px] max-w-[160px]"
                data-testid={`compare-bar-item-${item.id}`}
              >
                <SafeImage
                  src={item.image}
                  alt={item.title}
                  width={40}
                  height={40}
                  loading="lazy"
                  className="w-10 h-10 rounded object-cover border border-white/20"
                />
                <span className="text-xs truncate flex-1 hidden sm:inline" title={item.title}>
                  {item.title || '—'}
                </span>
                <button
                  type="button"
                  onClick={() => remove(item.id)}
                  className="p-0.5 rounded hover:bg-white/20"
                  aria-label={t.close}
                  data-testid={`compare-bar-remove-${item.id}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs opacity-80 hidden sm:inline" data-testid="compare-bar-count">
            {t.selected(count)}
          </span>
          <button
            type="button"
            onClick={() => navigate(lang === 'fr' ? '/fr/comparer' : '/compare')}
            disabled={!canCompare}
            className={`px-4 py-2 rounded-md font-bold text-sm transition-all min-h-[40px] flex items-center gap-1.5 ${
              canCompare
                ? 'bg-[#3FB4CB] text-[#0B2545] hover:bg-[#5FCADF] shadow-md'
                : 'bg-white/20 text-white/50 cursor-not-allowed'
            }`}
            data-testid="compare-bar-cta"
          >
            <GitCompare className="h-4 w-4" />
            {canCompare ? t.cta : t.hint(count)}
          </button>
          <button
            type="button"
            onClick={clear}
            className="p-2 rounded-md hover:bg-white/10"
            aria-label={t.clear}
            data-testid="compare-bar-clear"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
