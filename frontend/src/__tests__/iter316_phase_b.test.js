/**
 * iter316 Phase B — Frontend wiring tests.
 *
 * Validates that the new pages (AdminDialer, ContractorDashboard,
 * AdminContractorsPage) and the route/tab wiring meet the contract
 * required by Phase B Missions B1-B5.
 *
 * Run via:  node frontend/src/__tests__/iter316_phase_b.test.js
 *
 * Each `t()` block prints PASS / FAIL with a short message and exits
 * with code 1 if any check fails. No external test runner is required
 * (matches the existing utils/errorHandler.test.js convention).
 */
const fs = require('fs');
const path = require('path');

let passes = 0;
let failures = 0;

function t(name, fn) {
  try {
    fn();
    passes += 1;
    console.log(`  PASS  ${name}`);
  } catch (e) {
    failures += 1;
    console.error(`  FAIL  ${name}\n         ${e.message}`);
  }
}

function read(rel) {
  return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8');
}

function assertIncludes(haystack, needle, hint) {
  if (!haystack.includes(needle)) {
    throw new Error(`expected to find: ${needle}${hint ? ` (${hint})` : ''}`);
  }
}

// ─── Load the files under test ────────────────────────────────────
const DIALER = read('pages/admin/AdminDialer.jsx');
const CONTRACTOR = read('pages/contractor/ContractorDashboard.jsx');
const ADMIN_CONTRACTORS = read('pages/admin/AdminContractorsPage.jsx');
const APP = read('App.js');
const ADMIN_DASH = read('pages/AdminDashboard.js');

console.log('\niter316 Phase B — Frontend wiring tests\n');

// ─── Mission B1 — AdminDialer ──────────────────────────────────────
console.log('Mission B1 — Admin Dialer UI');

t('B1.01 — admin-dialer-page data-testid root', () => {
  assertIncludes(DIALER, 'data-testid="admin-dialer-page"');
});

t('B1.02 — three-panel layout testids', () => {
  assertIncludes(DIALER, 'data-testid="dialer-outbound-panel"');
  assertIncludes(DIALER, 'data-testid="dialer-active-panel"');
  assertIncludes(DIALER, 'data-testid="dialer-history-panel"');
});

t('B1.03 — Twilio Voice SDK dynamic import', () => {
  assertIncludes(DIALER, "@twilio/voice-sdk", 'imports the browser SDK');
  assertIncludes(DIALER, 'new sdk.Device(', 'instantiates Device with token');
});

t('B1.04 — Twilio token endpoint wired', () => {
  assertIncludes(DIALER, '/twilio/token', 'POST to /api/twilio/token');
});

t('B1.05 — outbound call endpoint wired', () => {
  assertIncludes(DIALER, '/twilio/call', 'POST to /api/twilio/call');
  assertIncludes(DIALER, 'client_phone:');
});

t('B1.06 — config probe + graceful degradation', () => {
  assertIncludes(DIALER, '/twilio/config');
  assertIncludes(DIALER, 'data-testid="dialer-config-banner"');
});

t('B1.07 — mute / hangup controls present', () => {
  assertIncludes(DIALER, 'data-testid="dialer-mute-btn"');
  assertIncludes(DIALER, 'data-testid="dialer-hangup-btn"');
});

// ─── Mission B2 — AI Insights Expandable Panel ─────────────────────
console.log('\nMission B2 — AI Insights Expandable Panel');

t('B2.01 — 15-second auto-poll constant', () => {
  assertIncludes(DIALER, 'POLL_INTERVAL_MS = 15000');
});

t('B2.02 — polls only when rows pending/processing', () => {
  assertIncludes(DIALER, "['pending', 'processing'].includes");
});

t('B2.03 — AI insights data-testid panel + status line', () => {
  assertIncludes(DIALER, 'data-testid="ai-insights-panel"');
  assertIncludes(DIALER, 'data-testid="ai-insights-status-line"');
});

t('B2.04 — sentiment badges (positive/neutral/negative)', () => {
  assertIncludes(DIALER, "SENTIMENT_BADGE = {");
  assertIncludes(DIALER, "positive:");
  assertIncludes(DIALER, "neutral:");
  assertIncludes(DIALER, "negative:");
});

t('B2.05 — bilingual transcript toggle (EN / FR)', () => {
  assertIncludes(DIALER, 'data-testid="transcript-lang-en"');
  assertIncludes(DIALER, 'data-testid="transcript-lang-fr"');
});

t('B2.06 — diarized Agent/Client turns rendered', () => {
  assertIncludes(DIALER, 'data-testid="ai-insights-diarized"');
});

t('B2.07 — action items checklist rendered', () => {
  assertIncludes(DIALER, 'data-testid="ai-insights-actions"');
});

t('B2.08 — RAW audio playback admin-only', () => {
  // Recording button rendered only when isAdmin; non-admins see Lock notice.
  assertIncludes(DIALER, 'data-testid="dialer-recording-locked"');
  assertIncludes(DIALER, 'data-testid="dialer-play-recording-btn"');
  assertIncludes(DIALER, "isAdmin && call.recording_url");
});

// ─── Mission B4 — Contractor Dashboard ────────────────────────────
console.log('\nMission B4 — Contractor Dashboard');

t('B4.01 — page root testid + title', () => {
  assertIncludes(CONTRACTOR, 'data-testid="contractor-dashboard-page"');
  assertIncludes(CONTRACTOR, 'data-testid="contractor-dashboard-title"');
});

t('B4.02 — 60-second polling per spec', () => {
  assertIncludes(CONTRACTOR, 'POLL_INTERVAL_MS = 60000');
});

t('B4.03 — uses contractor dashboard backend endpoint', () => {
  assertIncludes(CONTRACTOR, '/twilio/contractor/dashboard');
});

t('B4.04 — 403 banner for non-contractors', () => {
  assertIncludes(CONTRACTOR, 'data-testid="contractor-dashboard-403"');
  assertIncludes(CONTRACTOR, 'status === 403');
});

t('B4.05 — links to iter302 Stripe Connect onboarding', () => {
  assertIncludes(CONTRACTOR, '/settlement/connect/onboard',
    'reuses iter302 Stripe Connect onboarding endpoint');
});

t('B4.06 — Stripe status card + earnings grid', () => {
  assertIncludes(CONTRACTOR, 'data-testid="stripe-status-card"');
  assertIncludes(CONTRACTOR, 'data-testid="earnings-grid"');
  assertIncludes(CONTRACTOR, 'testid="stat-accrued"');
  assertIncludes(CONTRACTOR, 'testid="stat-paid"');
});

t('B4.07 — referred accounts + commission history tables', () => {
  assertIncludes(CONTRACTOR, 'data-testid="referred-accounts-card"');
  assertIncludes(CONTRACTOR, 'data-testid="commission-history-card"');
});

// ─── Mission B5 — Admin Commission Rate Editor ────────────────────
console.log('\nMission B5 — Admin Commission Rate Editor');

t('B5.01 — admin contractors page testid root', () => {
  assertIncludes(ADMIN_CONTRACTORS, 'data-testid="admin-contractors-page"');
});

t('B5.02 — percentage → decimal conversion helper', () => {
  assertIncludes(ADMIN_CONTRACTORS, 'function pctToDecimal');
  assertIncludes(ADMIN_CONTRACTORS, '/ 100');
});

t('B5.03 — modal renders rate input for every account type', () => {
  for (const t of ['vehicle_dealer','partner','broker','liquidator','individual_seller']) {
    if (!ADMIN_CONTRACTORS.includes(t)) {
      throw new Error(`missing account type: ${t}`);
    }
  }
  assertIncludes(ADMIN_CONTRACTORS, 'data-testid="rate-input-default"');
});

t('B5.04 — PATCH commission-rates endpoint wired', () => {
  assertIncludes(ADMIN_CONTRACTORS, '/twilio/admin/contractors/');
  assertIncludes(ADMIN_CONTRACTORS, '/commission-rates');
  assertIncludes(ADMIN_CONTRACTORS, 'axios.patch');
});

t('B5.05 — Remove Referral Attribution modal + endpoint', () => {
  assertIncludes(ADMIN_CONTRACTORS, 'data-testid="remove-attribution-modal"');
  assertIncludes(ADMIN_CONTRACTORS, 'remove-referral-attribution');
});

t('B5.06 — Save button + cancel button data-testid', () => {
  assertIncludes(ADMIN_CONTRACTORS, 'data-testid="rates-save-btn"');
  assertIncludes(ADMIN_CONTRACTORS, 'data-testid="rates-cancel-btn"');
});

// ─── Routing + Admin tab wiring ───────────────────────────────────
console.log('\nApp routing & Admin tab wiring');

t('WIRE.01 — /admin/dialer route registered in App.js', () => {
  assertIncludes(APP, 'path="/admin/dialer"');
  assertIncludes(APP, 'AdminDialer');
});

t('WIRE.02 — /contractor/dashboard route registered in App.js', () => {
  assertIncludes(APP, 'path="/contractor/dashboard"');
  assertIncludes(APP, 'ContractorDashboard');
});

t('WIRE.03 — admin dashboard has new "dialer" primary tab', () => {
  assertIncludes(ADMIN_DASH, "{ id: 'dialer'");
  assertIncludes(ADMIN_DASH, 'Contractors');
});

t('WIRE.04 — admin dashboard renders AdminDialer + AdminContractorsPage', () => {
  assertIncludes(ADMIN_DASH, 'AdminContractorsPage');
  assertIncludes(ADMIN_DASH, 'AdminDialer');
});

// ─── Summary ─────────────────────────────────────────────────────
console.log(`\n  ${passes} passed, ${failures} failed`);
if (failures > 0) {
  process.exit(1);
}
process.exit(0);
