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

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={disabled ? t.tooltipMax : t.tooltip}
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold transition-all min-h-[28px] ${
        active
          ? 'bg-primary text-white shadow-md'
          : disabled
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
            : 'bg-white/95 text-slate-700 border border-slate-200 hover:bg-slate-50 hover:border-primary/40'
      } ${className}`}
      data-testid={`compare-checkbox-${item?.id || item?._id}`}
    >
      <GitCompare className="h-3 w-3 flex-shrink-0" />
      <span>{t.label}</span>
      {active && <span className="text-[9px] opacity-80">✓</span>}
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
