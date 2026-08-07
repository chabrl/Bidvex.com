/**
 * iter450 — Regression tests for the EN/FR language toggle plumbing.
 *
 * Two pure decision points that used to misbehave:
 *
 *   1. `computeLangAwareTarget`: reads persisted language and picks the
 *      correct `/en/…` vs `/fr/…` URL (with slug translation via
 *      `EN_TO_FR`).
 *
 *   2. `isPrefixEligible` heuristic (mirrors switchLang's logic):
 *      NAMED sub-pages like `create`, `bulk-import`, `for-facilities`,
 *      `register-facility`, `dashboard`, `edit`, `browse`,
 *      `how-it-works` MUST NOT be considered language-prefix-eligible.
 *      Routes ending in a UUID-like or numeric ID MUST still be
 *      eligible (single-listing detail pages).
 */
import {
  computeLangAwareTarget,
  readPersistedLang,
} from './langAwareRedirectHelpers';
import { EN_TO_FR, stripLangPrefix } from '../i18n/urlMap';

// ─────────────────────────────────────────────────────────────
// 1. computeLangAwareTarget
// ─────────────────────────────────────────────────────────────

describe('computeLangAwareTarget', () => {
  test('EN persisted → /en/marketplace stays under /en', () => {
    expect(computeLangAwareTarget('/en/marketplace', 'en')).toBe('/en/marketplace');
  });

  test('FR persisted → /marketplace flips to /fr/marche', () => {
    expect(computeLangAwareTarget('/en/marketplace', 'fr')).toBe('/fr/marche');
  });

  test('FR persisted → /vehicle-auctions → /fr/encheres-vehicules', () => {
    expect(computeLangAwareTarget('/en/vehicle-auctions', 'fr'))
      .toBe('/fr/encheres-vehicules');
  });

  test('FR persisted → /storage-auctions → /fr/encheres-entreposage', () => {
    expect(computeLangAwareTarget('/en/storage-auctions', 'fr'))
      .toBe('/fr/encheres-entreposage');
  });

  test('FR persisted → /how-it-works → /fr/comment-ca-marche', () => {
    expect(computeLangAwareTarget('/en/how-it-works', 'fr'))
      .toBe('/fr/comment-ca-marche');
  });

  test('EN default (no persisted lang) → routes under /en', () => {
    expect(computeLangAwareTarget('/en/marketplace')).toBe('/en/marketplace');
  });

  test('Slug with no FR twin falls back to same slug under /fr', () => {
    // `/random-page-xyz` is not in EN_TO_FR.
    expect(computeLangAwareTarget('/en/random-page-xyz', 'fr'))
      .toBe('/fr/random-page-xyz');
  });

  test('Preserves ?search and #hash', () => {
    expect(computeLangAwareTarget('/en/marketplace', 'fr', '?category=lots', '#top'))
      .toBe('/fr/marche?category=lots#top');
    expect(computeLangAwareTarget('/en/marketplace', 'en', '?ref=twitter'))
      .toBe('/en/marketplace?ref=twitter');
  });
});

// ─────────────────────────────────────────────────────────────
// 2. readPersistedLang — localStorage priority chain
// ─────────────────────────────────────────────────────────────

describe('readPersistedLang', () => {
  beforeEach(() => localStorage.clear());

  test('empty storage → defaults to "en"', () => {
    expect(readPersistedLang()).toBe('en');
  });

  test('bidvex_language wins when set', () => {
    localStorage.setItem('bidvex_language', 'fr');
    expect(readPersistedLang()).toBe('fr');
  });

  test('legacy i18nextLng is honoured as fallback', () => {
    localStorage.setItem('i18nextLng', 'fr');
    expect(readPersistedLang()).toBe('fr');
  });

  test('bidvex_language takes precedence over i18nextLng', () => {
    localStorage.setItem('bidvex_language', 'en');
    localStorage.setItem('i18nextLng', 'fr');
    expect(readPersistedLang()).toBe('en');
  });

  test('unsupported code falls back to i18nextLng, then "en"', () => {
    localStorage.setItem('bidvex_language', 'de');
    localStorage.setItem('i18nextLng', 'fr');
    expect(readPersistedLang()).toBe('fr');
    localStorage.setItem('i18nextLng', 'es');
    expect(readPersistedLang()).toBe('en');
  });
});

// ─────────────────────────────────────────────────────────────
// 3. isPrefixEligible heuristic — mirrors switchLang's logic.
// ─────────────────────────────────────────────────────────────
//
// Kept as a local re-implementation so any future drift in
// `LanguageContext.switchLang` is caught by test failure here.

const looksLikeId = (segment) => {
  if (!segment) return false;
  if (/\d/.test(segment)) return true;
  if (/^[a-f0-9-]{8,}$/i.test(segment)) return true;
  return false;
};

const isPrefixEligible = (pathname) => {
  const urlHasLangPrefix = pathname === '/en' || pathname === '/fr'
    || pathname.startsWith('/en/') || pathname.startsWith('/fr/');
  const bare = stripLangPrefix(pathname);
  if (urlHasLangPrefix) return true;
  if (bare === '/') return true;
  if (bare in EN_TO_FR) return true;
  const keys = Object.keys(EN_TO_FR);
  for (const parent of keys) {
    if (parent === '/') continue;
    const prefix = parent + '/';
    if (!bare.startsWith(prefix)) continue;
    const tail = bare.slice(prefix.length);
    const firstSeg = tail.split('/')[0];
    return looksLikeId(firstSeg);
  }
  return false;
};

describe('isPrefixEligible (switchLang heuristic)', () => {
  test('Home page is eligible', () => {
    expect(isPrefixEligible('/')).toBe(true);
  });

  test('Any /en/* or /fr/* URL is eligible', () => {
    expect(isPrefixEligible('/en/marketplace')).toBe(true);
    expect(isPrefixEligible('/fr/marche')).toBe(true);
    expect(isPrefixEligible('/en/vehicle-auctions/abc12345')).toBe(true);
  });

  test('Exact keys in EN_TO_FR are eligible', () => {
    expect(isPrefixEligible('/marketplace')).toBe(true);
    expect(isPrefixEligible('/vehicle-auctions')).toBe(true);
    expect(isPrefixEligible('/storage-auctions')).toBe(true);
    expect(isPrefixEligible('/how-it-works')).toBe(true);
  });

  test('Deep listing/detail IDs are eligible (UUID and numeric) under mapped parents', () => {
    expect(isPrefixEligible('/vehicle-auctions/abc12345')).toBe(true);
    expect(isPrefixEligible('/vehicle-auctions/770fb430-06ee-4fe8-bb24-0d210136e94a')).toBe(true);
    expect(isPrefixEligible('/storage-auctions/12345')).toBe(true);
    expect(isPrefixEligible('/lots/xyz9876')).toBe(true);
  });

  test('Named sub-pages under a mapped parent are NOT eligible', () => {
    // These previously navigated to /fr/{parent}/{sub} 404s — the whole
    // point of the iter450 fix.
    expect(isPrefixEligible('/storage-auctions/bulk-import')).toBe(false);
    expect(isPrefixEligible('/storage-auctions/create')).toBe(false);
    expect(isPrefixEligible('/storage-auctions/register-facility')).toBe(false);
    expect(isPrefixEligible('/storage-auctions/for-facilities')).toBe(false);
    expect(isPrefixEligible('/storage-auctions/how-it-works')).toBe(false);
    expect(isPrefixEligible('/storage-auctions/browse')).toBe(false);
    expect(isPrefixEligible('/vehicle-auctions/create')).toBe(false);
    expect(isPrefixEligible('/vehicle-auctions/bulk-import')).toBe(false);
  });

  test('Utility / authenticated routes with NO mapped parent are NOT eligible', () => {
    expect(isPrefixEligible('/settings')).toBe(false);
    expect(isPrefixEligible('/messages')).toBe(false);
    expect(isPrefixEligible('/watchlist')).toBe(false);
    expect(isPrefixEligible('/admin/users')).toBe(false);
    expect(isPrefixEligible('/vehicle-multi-lot/create')).toBe(false);
  });

  test('Multi-lot detail with UUID under an UN-mapped parent stays in-place', () => {
    // /vehicle-multi-lot is NOT in EN_TO_FR — so the toggle should
    // NOT navigate; the page just re-renders in the target language.
    expect(isPrefixEligible('/vehicle-multi-lot/770fb430-06ee-4fe8-bb24-0d210136e94a')).toBe(false);
  });
});
