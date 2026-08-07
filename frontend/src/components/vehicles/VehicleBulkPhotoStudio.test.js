/**
 * Jest tests for matchByVin — iter447
 *
 * Rules under test:
 *   1. Full 17-char VIN wins.
 *   2. Last-8 suffix matches ONLY when exactly one lot in the batch
 *      has that suffix.
 *   3. Last-6 suffix matches ONLY when exactly one lot in the batch
 *      has that suffix.
 *   4. NO stock-number fallback.
 *   5. Ambiguous or unrecognised filenames return null.
 */
import { matchByVin } from './vinPhotoMatcher';

const mkLot = (vin) => ({ id: `lot-${vin}`, vin });

describe('matchByVin', () => {
  test('returns null when no lots', () => {
    expect(matchByVin('anything.jpg', [])).toBeNull();
  });

  test('returns null when filename empty', () => {
    expect(matchByVin('', [mkLot('1HGBH41JXMN109186')])).toBeNull();
  });

  test('full 17-char VIN match wins', () => {
    const lots = [mkLot('1HGBH41JXMN109186'), mkLot('1FTFW1ET9DFA12345')];
    const m = matchByVin('unit_1HGBH41JXMN109186_front.jpg', lots);
    expect(m?.vin).toBe('1HGBH41JXMN109186');
  });

  test('full VIN match is case-insensitive', () => {
    const lots = [mkLot('1HGBH41JXMN109186')];
    expect(matchByVin('1hgbh41jxmn109186_front.jpg', lots)?.vin).toBe('1HGBH41JXMN109186');
  });

  test('unambiguous last-8 suffix matches', () => {
    const lots = [mkLot('1HGBH41JXMN109186'), mkLot('1FTFW1ET9DFA12345')];
    // MN109186 is the last 8 of the first VIN only.
    expect(matchByVin('photo_MN109186.jpg', lots)?.vin).toBe('1HGBH41JXMN109186');
  });

  test('AMBIGUOUS last-8 suffix returns null', () => {
    // Contrived: two lots with the same last-8 suffix "MN109186".
    const lots = [
      mkLot('1HGBH41JAMN109186'),
      mkLot('1HGBH41JBMN109186'),
    ];
    expect(matchByVin('photo_MN109186.jpg', lots)).toBeNull();
  });

  test('unambiguous last-6 suffix matches', () => {
    const lots = [mkLot('1HGBH41JXMN109186'), mkLot('1FTFW1ET9DFA12345')];
    // 109186 is only in the first VIN's last-6.
    expect(matchByVin('DSC_109186.jpg', lots)?.vin).toBe('1HGBH41JXMN109186');
  });

  test('AMBIGUOUS last-6 suffix returns null', () => {
    const lots = [
      mkLot('1HGBH41JXAA109186'),
      mkLot('1HGBH41JXBB109186'),
    ];
    expect(matchByVin('front_109186.jpg', lots)).toBeNull();
  });

  test('stock-number-like tokens do NOT trigger a match', () => {
    // No VIN substring, no last-8, no last-6 — filename is stock#.
    const lots = [mkLot('1HGBH41JXMN109186'), mkLot('1FTFW1ET9DFA12345')];
    expect(matchByVin('stock_A-4471_front.jpg', lots)).toBeNull();
  });

  test('random filename returns null', () => {
    const lots = [mkLot('1HGBH41JXMN109186')];
    expect(matchByVin('IMG_1234.jpg', lots)).toBeNull();
  });

  test('preserves the exact lot object (not a copy)', () => {
    const target = mkLot('1HGBH41JXMN109186');
    const lots = [target, mkLot('1FTFW1ET9DFA12345')];
    expect(matchByVin('1HGBH41JXMN109186.png', lots)).toBe(target);
  });
});
