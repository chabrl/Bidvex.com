/**
 * iter364 — ComparePage.
 *
 * Full side-by-side comparison table for the up-to-4 listings the user
 * added via <CompareCheckbox>. Bilingual, works across all listing
 * sections (marketplace/lots/storage/vehicles); vehicle rows swap
 * generic fields (title/condition/city) for VIN/make/model/year.
 */
import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { GitCompare, ArrowLeft, X } from 'lucide-react';
import { useCompare } from '../contexts/CompareContext';
import SafeImage from '../components/SafeImage';
import SEO from '../components/SEO';

const COPY = {
  en: {
    title: 'Compare Listings',
    subtitle: (n) => `Side-by-side comparison of ${n} listing${n > 1 ? 's' : ''}`,
    empty: 'No items selected. Add up to 4 listings via the "Compare" button on any card.',
    back: 'Back to marketplace',
    remove: 'Remove',
    bidNow: 'Bid Now',
    viewDetails: 'View details',
    hasVehicle: 'Vehicle Details',
    hasCommon:  'Auction Details',
    fields: {
      photo: 'Photo',
      title: 'Title',
      current_bid: 'Current bid',
      time_remaining: 'Time remaining',
      starting_price: 'Starting price',
      condition: 'Condition',
      location: 'Location',
      seller: 'Seller',
      section: 'Section',
      bid_count: 'Bids placed',
      vin: 'VIN',
      make: 'Make',
      model: 'Model',
      year: 'Year',
      mileage: 'Mileage',
    },
    sections: {
      marketplace: 'Marketplace',
      lots:        'Lots',
      storage:     'Storage',
      vehicle:     'Vehicle',
    },
    tbaField: '—',
  },
  fr: {
    title: 'Comparer les articles',
    subtitle: (n) => `Comparaison côte à côte de ${n} article${n > 1 ? 's' : ''}`,
    empty: 'Aucun article sélectionné. Ajoutez jusqu\'à 4 articles via le bouton "Comparer" sur n\'importe quelle carte.',
    back: 'Retour au marché',
    remove: 'Retirer',
    bidNow: 'Enchérir',
    viewDetails: 'Voir détails',
    hasVehicle: 'Détails du véhicule',
    hasCommon:  'Détails de l\'enchère',
    fields: {
      photo: 'Photo',
      title: 'Titre',
      current_bid: 'Enchère actuelle',
      time_remaining: 'Temps restant',
      starting_price: 'Prix de départ',
      condition: 'Condition',
      location: 'Lieu',
      seller: 'Vendeur',
      section: 'Section',
      bid_count: 'Enchères placées',
      vin: 'NIV',
      make: 'Marque',
      model: 'Modèle',
      year: 'Année',
      mileage: 'Kilométrage',
    },
    sections: {
      marketplace: 'Marché',
      lots:        'Lots',
      storage:     'Entrepôt',
      vehicle:     'Véhicule',
    },
    tbaField: '—',
  },
};

const formatMoney = (n, lang) => {
  if (n == null || Number.isNaN(Number(n))) return '—';
  const v = Number(n);
  try {
    return new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', {
      style: 'currency', currency: 'CAD', maximumFractionDigits: 2,
    }).format(v);
  } catch {
    return `$${v.toFixed(2)} CAD`;
  }
};

const timeRemaining = (endDate, lang) => {
  if (!endDate) return '—';
  const end = new Date(endDate);
  const now = new Date();
  const diff = end - now;
  if (Number.isNaN(diff) || diff <= 0) return lang === 'fr' ? 'Terminée' : 'Ended';
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  if (days > 0) return `${days}${lang === 'fr' ? ' j' : 'd'} ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins} min`;
};

export default function ComparePage() {
  const { selected, remove, clear } = useCompare();
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const t = COPY[lang];

  const hasVehicle = useMemo(() => selected.some((l) => l.section === 'vehicle'), [selected]);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="compare-page">
      <SEO
        title={t.title}
        description={t.subtitle(selected.length)}
        path={lang === 'fr' ? '/fr/comparer' : '/compare'}
      />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="text-sm text-primary hover:underline inline-flex items-center gap-1 mb-4"
          data-testid="compare-back"
        >
          <ArrowLeft className="h-4 w-4" />
          {t.back}
        </button>

        <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl md:text-4xl font-black text-[#0B2545] dark:text-white flex items-center gap-2">
              <GitCompare className="h-8 w-8 text-primary" />
              {t.title}
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {t.subtitle(selected.length)}
            </p>
          </div>
          {selected.length > 0 && (
            <button
              type="button"
              onClick={clear}
              className="text-sm text-slate-500 hover:text-rose-600 inline-flex items-center gap-1"
              data-testid="compare-clear-all"
            >
              <X className="h-4 w-4" />
              {t.remove}
            </button>
          )}
        </div>

        {selected.length === 0 ? (
          <div
            className="bg-white dark:bg-slate-800 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl p-12 text-center"
            data-testid="compare-empty"
          >
            <GitCompare className="h-12 w-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500 dark:text-slate-400">{t.empty}</p>
          </div>
        ) : (
          <div className="overflow-x-auto bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700" data-testid="compare-table-wrap">
            <table className="w-full text-sm" data-testid="compare-table">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="text-left px-3 py-3 font-semibold text-slate-500 uppercase text-[11px] sticky left-0 bg-white dark:bg-slate-800 z-10 w-40">
                    {t.hasCommon}
                  </th>
                  {selected.map((item) => (
                    <th key={item.id} className="text-left px-3 py-3 min-w-[220px] max-w-[280px] align-top">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-bold text-[#0B2545] dark:text-white truncate flex-1" title={item.title}>
                          {item.title || '—'}
                        </span>
                        <button
                          type="button"
                          onClick={() => remove(item.id)}
                          className="p-1 -mt-1 -mr-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-rose-600"
                          aria-label={t.remove}
                          data-testid={`compare-remove-${item.id}`}
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                <Row label={t.fields.photo}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top">
                      <SafeImage
                        src={i.image}
                        alt={i.title}
                        width={200}
                        height={150}
                        className="w-full h-32 object-cover rounded-md border border-slate-200 dark:border-slate-700"
                        loading="lazy"
                      />
                    </td>
                  ))}
                </Row>
                <Row label={t.fields.current_bid}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top font-bold text-emerald-700 dark:text-emerald-400" data-testid={`compare-cell-currentbid-${i.id}`}>
                      {formatMoney(i.current_bid, lang)}
                    </td>
                  ))}
                </Row>
                <Row label={t.fields.time_remaining}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top">
                      {timeRemaining(i.auction_end_date, lang)}
                    </td>
                  ))}
                </Row>
                <Row label={t.fields.starting_price}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top">{formatMoney(i.starting_price, lang)}</td>
                  ))}
                </Row>
                <Row label={t.fields.condition}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top capitalize">{i.condition || t.tbaField}</td>
                  ))}
                </Row>
                <Row label={t.fields.location}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top">
                      {[i.city, i.region].filter(Boolean).join(', ') || t.tbaField}
                    </td>
                  ))}
                </Row>
                <Row label={t.fields.seller}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top truncate">{i.seller_name || t.tbaField}</td>
                  ))}
                </Row>
                <Row label={t.fields.section}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top">{t.sections[i.section] || i.section}</td>
                  ))}
                </Row>
                <Row label={t.fields.bid_count}>
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top">{i.bid_count ?? 0}</td>
                  ))}
                </Row>

                {hasVehicle && (
                  <>
                    <tr className="bg-slate-50 dark:bg-slate-900/40">
                      <td colSpan={selected.length + 1} className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        {t.hasVehicle}
                      </td>
                    </tr>
                    <Row label={t.fields.vin}>
                      {selected.map((i) => (
                        <td key={i.id} className="px-3 py-3 align-top font-mono text-xs">{i.vin || t.tbaField}</td>
                      ))}
                    </Row>
                    <Row label={t.fields.year}>
                      {selected.map((i) => (
                        <td key={i.id} className="px-3 py-3 align-top">{i.year || t.tbaField}</td>
                      ))}
                    </Row>
                    <Row label={t.fields.make}>
                      {selected.map((i) => (
                        <td key={i.id} className="px-3 py-3 align-top">{i.make || t.tbaField}</td>
                      ))}
                    </Row>
                    <Row label={t.fields.model}>
                      {selected.map((i) => (
                        <td key={i.id} className="px-3 py-3 align-top">{i.model || t.tbaField}</td>
                      ))}
                    </Row>
                    <Row label={t.fields.mileage}>
                      {selected.map((i) => (
                        <td key={i.id} className="px-3 py-3 align-top">
                          {i.mileage != null
                            ? `${Number(i.mileage).toLocaleString(lang === 'fr' ? 'fr-CA' : 'en-CA')} km`
                            : t.tbaField}
                        </td>
                      ))}
                    </Row>
                  </>
                )}

                <tr>
                  <td className="px-3 py-3 sticky left-0 bg-white dark:bg-slate-800 z-10" />
                  {selected.map((i) => (
                    <td key={i.id} className="px-3 py-3 align-top">
                      <button
                        type="button"
                        onClick={() => navigate(i.detail_path)}
                        className="w-full px-3 py-2 rounded-md bg-primary text-white font-bold text-sm hover:opacity-95 min-h-[44px]"
                        data-testid={`compare-bid-${i.id}`}
                      >
                        {t.bidNow}
                      </button>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

const Row = ({ label, children }) => (
  <tr>
    <th className="text-left px-3 py-3 font-medium text-slate-500 dark:text-slate-400 sticky left-0 bg-white dark:bg-slate-800 z-10 w-40 align-top">
      {label}
    </th>
    {children}
  </tr>
);
