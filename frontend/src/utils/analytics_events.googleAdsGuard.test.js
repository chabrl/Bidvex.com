/**
 * iter482 P2-followup — Google Ads Purchase conversion idempotence test.
 *
 * Verifies that `trackGoogleAdsPurchase()` from `analytics_events.js`:
 *   1. Emits a `gtag('event', 'conversion', …)` with
 *      `send_to = AW-18140095337/<REACT_APP_GOOGLE_ADS_PURCHASE_LABEL>`
 *      and a string `transaction_id`, matching what Google Ads expects.
 *   2. Fires exactly ONCE per (browser tab, transaction_id).  A second
 *      invocation with the same `transactionId` is silently dropped even
 *      when the caller doesn't install its own upstream guard.
 *   3. Fires again for a DIFFERENT `transactionId` (guard is scoped, not
 *      global).
 *
 * Runnable directly with:
 *     node src/utils/analytics_events.googleAdsGuard.test.js
 *
 * Zero dependency on Jest / React so it can be run from any CI without
 * bringing up the full react-scripts test harness.
 */

const assert = require('node:assert');
const path = require('node:path');

async function run() {
  const store = new Map();
  const gtagCalls = [];
  globalThis.window = {
    sessionStorage: {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, v),
      removeItem: (k) => store.delete(k),
    },
    gtag: (...args) => { gtagCalls.push(args); },
  };
  process.env.REACT_APP_GOOGLE_ADS_PURCHASE_LABEL = 'ITER482_TEST_LABEL';

  const { trackGoogleAdsPurchase } = await import(
    path.join(__dirname, 'analytics_events.js')
  );

  // ── 1) First fire attaches a conversion event with the correct shape ──
  trackGoogleAdsPurchase({ value: 100.00, transactionId: 'cs_TEST_A' });
  assert.strictEqual(gtagCalls.length, 1,
    'First call must emit exactly one gtag event');
  const payload = gtagCalls[0][2];
  assert.strictEqual(payload.send_to,
    'AW-18140095337/ITER482_TEST_LABEL',
    '`send_to` must chain AW account id + REACT_APP_GOOGLE_ADS_PURCHASE_LABEL');
  assert.strictEqual(payload.transaction_id, 'cs_TEST_A',
    '`transaction_id` must be the caller-supplied id (string-coerced)');
  assert.strictEqual(payload.value, 100.00);
  assert.strictEqual(payload.currency, 'CAD');

  // ── 2) Second fire with the SAME transactionId is silently dropped ──
  trackGoogleAdsPurchase({ value: 100.00, transactionId: 'cs_TEST_A' });
  assert.strictEqual(gtagCalls.length, 1,
    'Duplicate transactionId must NOT emit a second gtag event');

  // ── 3) A different transactionId fires ──
  trackGoogleAdsPurchase({ value: 250.00, transactionId: 'cs_TEST_B' });
  assert.strictEqual(gtagCalls.length, 2,
    'A new transactionId must emit a fresh gtag event');
  assert.strictEqual(gtagCalls[1][2].transaction_id, 'cs_TEST_B');

  // ── 4) Guard survives an entire third replay ──
  trackGoogleAdsPurchase({ value: 250.00, transactionId: 'cs_TEST_B' });
  assert.strictEqual(gtagCalls.length, 2,
    'Duplicate for a different transactionId must ALSO be blocked');

  // ── 5) Guard markers are visible in sessionStorage ──
  assert.ok(store.has('bidvex_gads_conversion_cs_TEST_A'));
  assert.ok(store.has('bidvex_gads_conversion_cs_TEST_B'));

  // ── 6) Missing REACT_APP_GOOGLE_ADS_PURCHASE_LABEL disables the fire ──
  //   (defensive test — safeguards a mis-configured env)
  const gtagCallsBefore = gtagCalls.length;
  const oldLabel = process.env.REACT_APP_GOOGLE_ADS_PURCHASE_LABEL;
  process.env.REACT_APP_GOOGLE_ADS_PURCHASE_LABEL = '';
  // The module already captured the label at import time — reimport with
  // a cache-busting query string to test the label-guard path.
  const url = 'file://' + path.join(__dirname, 'analytics_events.js')
              + '?nolabel=' + Date.now();
  const { trackGoogleAdsPurchase: fnNoLabel } = await import(url);
  fnNoLabel({ value: 999.99, transactionId: 'cs_TEST_C' });
  assert.strictEqual(gtagCalls.length, gtagCallsBefore,
    'Missing REACT_APP_GOOGLE_ADS_PURCHASE_LABEL must short-circuit the fire');
  process.env.REACT_APP_GOOGLE_ADS_PURCHASE_LABEL = oldLabel;

  console.log('PASS  6/6 assertions — Google Ads purchase-conversion guard OK');
}

run().catch((e) => {
  console.error('FAIL', e);
  process.exit(1);
});
