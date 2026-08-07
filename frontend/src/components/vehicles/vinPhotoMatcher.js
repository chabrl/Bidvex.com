/**
 * VIN-based photo → lot matcher — iter447
 *
 * Pure function. NO imports so it stays trivially testable under Jest
 * without transform config for axios / react-dropzone / sonner.
 *
 * Rules:
 *   1. Full 17-character VIN substring wins first (case-insensitive).
 *   2. Last-8 suffix matches only when EXACTLY ONE lot in the batch
 *      has that suffix.
 *   3. Last-6 suffix matches only when EXACTLY ONE lot in the batch
 *      has that suffix.
 *   4. NO stock-number fallback. Anything ambiguous → null.
 *
 * Returns the matched lot object or null.
 */
const stripExt = (name) => (name || '').replace(/\.[^.]+$/, '');
const upper = (s) => (s || '').toString().toUpperCase();

export const matchByVin = (filename, lots) => {
  if (!filename || !lots || lots.length === 0) return null;
  const stem = upper(stripExt(filename));

  const fullMatch = lots.find(
    (l) => l.vin && l.vin.length === 17 && stem.includes(upper(l.vin))
  );
  if (fullMatch) return fullMatch;

  const collectSuffix = (n) => {
    const bySuffix = new Map();
    for (const l of lots) {
      const v = upper(l.vin || '');
      if (v.length < n) continue;
      const suffix = v.slice(-n);
      if (!bySuffix.has(suffix)) bySuffix.set(suffix, []);
      bySuffix.get(suffix).push(l);
    }
    return bySuffix;
  };

  const byLast8 = collectSuffix(8);
  for (const [suf, group] of byLast8.entries()) {
    if (group.length === 1 && stem.includes(suf)) return group[0];
  }

  const byLast6 = collectSuffix(6);
  for (const [suf, group] of byLast6.entries()) {
    if (group.length === 1 && stem.includes(suf)) return group[0];
  }

  return null;
};

export default matchByVin;
