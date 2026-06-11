/**
 * Multi-Lot Vehicle Auction — Timing Mode display helpers.
 *
 * iter294 ADDENDUM — User-facing labels were renamed away from
 * "Copart" / "Staggered" / "Sequential" jargon. Internal API + DB
 * values stay as the original `sequential` / `staggered` strings; the
 * helpers below are display-only.
 *
 * iter302 Directive 3 — Full French (FR) display strings added. The
 * helpers accept an optional `lang` argument ('en' default) so callers
 * can stay backward compatible.
 */

export const TIMING_MODES = {
  staggered: {
    id:    'staggered',
    label: 'Synchronized Wave',
    short: 'Synchronized Wave',
    description:
      'All vehicles open for bidding at the same time, each starting 1 minute apart. ' +
      'Buyers can watch and bid across multiple lots simultaneously — ideal for ' +
      'high-volume events where you want maximum early engagement.',
    label_fr: 'Vague synchronisée',
    short_fr: 'Vague synchronisée',
    description_fr:
      "Tous les véhicules ouvrent aux enchères en même temps, chacun débutant à " +
      "1 minute d'intervalle. Les acheteurs peuvent suivre et miser sur plusieurs " +
      "lots simultanément — idéal pour les événements à fort volume où vous " +
      "souhaitez un engagement maximal dès le départ.",
    icon:  '🌊',
    recommended: false,
  },
  sequential: {
    id:    'sequential',
    label: 'One at a Time — Sequential Spotlight',
    short: 'Sequential Spotlight',
    description:
      'Each vehicle gets its own dedicated bidding window. When one lot closes, the ' +
      'next one opens automatically with a fresh 2-minute countdown. Every vehicle ' +
      'gets full buyer attention — no lot gets buried.',
    label_fr: 'Un à la fois — Projecteur séquentiel',
    short_fr: 'Projecteur séquentiel',
    description_fr:
      "Chaque véhicule dispose de sa propre fenêtre d'enchères dédiée. Quand un lot " +
      "se ferme, le suivant ouvre automatiquement avec un nouveau compte à rebours " +
      "de 2 minutes. Chaque véhicule reçoit toute l'attention des acheteurs — " +
      "aucun lot n'est noyé.",
    icon:  '🎯',
    recommended: true,
  },
};

const isFr = (lang) => String(lang || 'en').startsWith('fr');

export const getTimingModeLabel = (modeId, lang = 'en') => {
  const m = TIMING_MODES[modeId];
  if (!m) return modeId || 'Unknown';
  return (isFr(lang) && m.label_fr) || m.label;
};

export const getTimingModeShortLabel = (modeId, lang = 'en') => {
  const m = TIMING_MODES[modeId];
  if (!m) return modeId || 'Unknown';
  return (isFr(lang) && m.short_fr) || m.short;
};

export const getTimingModeDescription = (modeId, lang = 'en') => {
  const m = TIMING_MODES[modeId];
  if (!m) return '';
  return (isFr(lang) && m.description_fr) || m.description;
};
