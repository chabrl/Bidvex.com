/**
 * Multi-Lot Vehicle Auction — Timing Mode display helpers.
 *
 * iter294 ADDENDUM — User-facing labels were renamed away from
 * "Copart" / "Staggered" / "Sequential" jargon. Internal API + DB
 * values stay as the original `sequential` / `staggered` strings; the
 * helpers below are display-only.
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
    icon:  '🎯',
    recommended: true,
  },
};

export const getTimingModeLabel = (modeId) => {
  return TIMING_MODES[modeId]?.label || modeId || 'Unknown';
};

export const getTimingModeShortLabel = (modeId) => {
  return TIMING_MODES[modeId]?.short || modeId || 'Unknown';
};

export const getTimingModeDescription = (modeId) => {
  return TIMING_MODES[modeId]?.description || '';
};
