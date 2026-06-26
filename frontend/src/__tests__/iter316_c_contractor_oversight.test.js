/**
 * iter316-C — Frontend wiring tests for the contractor onboarding /
 * oversight bundle (New Contractor + Promote/Demote + Drill-in).
 *
 * Run via: node frontend/src/__tests__/iter316_c_contractor_oversight.test.js
 */
const fs = require('fs');
const path = require('path');

let passes = 0;
let failures = 0;

function t(name, fn) {
  try { fn(); passes += 1; console.log(`  PASS  ${name}`); }
  catch (e) { failures += 1; console.error(`  FAIL  ${name}\n         ${e.message}`); }
}
function read(rel) {
  return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8');
}
function inc(hay, needle, hint) {
  if (!hay.includes(needle)) throw new Error(`expected: ${needle}${hint ? ` (${hint})` : ''}`);
}

const CONTRACTORS = read('pages/admin/AdminContractorsPage.jsx');
const PROFILE = read('pages/admin/AdminContractorProfilePage.jsx');
const USERMGR = read('pages/admin/EnhancedUserManager.js');
const APP = read('App.js');

console.log('\niter316-C — Contractor onboarding / oversight wiring tests\n');

// ─── "+ New Contractor" button + modal ─────────────────────────────
console.log('C1 — New Contractor flow');

t('C1.01 — "New Contractor" button data-testid', () => {
  inc(CONTRACTORS, 'data-testid="new-contractor-btn"');
});

t('C1.02 — modal has email/name/phone/province/default-rate fields', () => {
  inc(CONTRACTORS, 'data-testid="new-contractor-email"');
  inc(CONTRACTORS, 'data-testid="new-contractor-name"');
  inc(CONTRACTORS, 'data-testid="new-contractor-phone"');
  inc(CONTRACTORS, 'data-testid="new-contractor-province"');
  inc(CONTRACTORS, 'data-testid="new-contractor-default-rate"');
});

t('C1.03 — submit posts to /twilio/admin/contractors', () => {
  inc(CONTRACTORS, '/twilio/admin/contractors');
  inc(CONTRACTORS, 'axios.post');
  inc(CONTRACTORS, 'initial_default_rate');
});

t('C1.04 — invite link is shown + copy button works', () => {
  inc(CONTRACTORS, 'data-testid="new-contractor-success"');
  inc(CONTRACTORS, 'data-testid="invite-link-input"');
  inc(CONTRACTORS, 'data-testid="copy-invite-link-btn"');
  inc(CONTRACTORS, '/reset-password?token=');
});

t('C1.05 — percentage-to-decimal conversion before POST', () => {
  inc(CONTRACTORS, 'pctToDecimal(defaultRatePct)');
});

// ─── Promote / Demote actions on User Management ──────────────────
console.log('\nC2 — Promote / Demote in User Management');

t('C2.01 — Promote menu item testid', () => {
  inc(USERMGR, 'data-testid={`promote-contractor-');
});

t('C2.02 — Demote menu item testid', () => {
  inc(USERMGR, 'data-testid={`demote-contractor-');
});

t('C2.03 — View Contractor Profile menu item testid', () => {
  inc(USERMGR, 'data-testid={`view-contractor-profile-');
});

t('C2.04 — uses /twilio/admin/users/{id}/promote-to-contractor', () => {
  inc(USERMGR, '/twilio/admin/users/${u.id}/promote-to-contractor');
});

t('C2.05 — uses /twilio/admin/users/{id}/demote-from-contractor', () => {
  inc(USERMGR, '/twilio/admin/users/${u.id}/demote-from-contractor');
});

t('C2.06 — Promote shown only when role !== dialer_contractor', () => {
  inc(USERMGR, "user.role === 'dialer_contractor'", 'gate condition');
});

t('C2.07 — Navigate to /admin/contractors/{id} on View action', () => {
  inc(USERMGR, '`/admin/contractors/${user.id}`');
});

// ─── Demote action on Contractors page ─────────────────────────────

t('C2.08 — Demote button on contractor row', () => {
  inc(CONTRACTORS, 'data-testid={`demote-btn-');
  inc(CONTRACTORS, 'data-testid="demote-contractor-modal"');
  inc(CONTRACTORS, 'data-testid="demote-confirm-btn"');
});

// ─── View Contractor Profile drill-in page ─────────────────────────
console.log('\nC3 — View Contractor Profile drill-in');

t('C3.01 — route /admin/contractors/:contractorId in App.js', () => {
  inc(APP, '/admin/contractors/:contractorId');
  inc(APP, 'AdminContractorProfilePage');
});

t('C3.02 — page root + 4 tabs', () => {
  inc(PROFILE, 'data-testid="contractor-profile-page"');
  inc(PROFILE, 'data-testid="tab-calls"');
  inc(PROFILE, 'data-testid="tab-ai"');
  inc(PROFILE, 'data-testid="tab-clients"');
  inc(PROFILE, 'data-testid="tab-dashboard"');
});

t('C3.03 — fetches the profile endpoint', () => {
  inc(PROFILE, '/twilio/admin/contractors/${contractorId}/profile');
});

t('C3.04 — snapshot cards (accrued/paid/calls/referrals)', () => {
  inc(PROFILE, 'data-testid="snap-accrued"');
  inc(PROFILE, 'data-testid="snap-paid"');
  inc(PROFILE, 'data-testid="snap-calls"');
  inc(PROFILE, 'data-testid="snap-referrals"');
});

t('C3.05 — Calls tab expands a row + shows contractor notes', () => {
  inc(PROFILE, 'data-testid="calls-list"');
  inc(PROFILE, 'data-testid="call-detail-notes"');
  inc(PROFILE, 'data-testid="call-detail-summary"');
  inc(PROFILE, 'data-testid="call-detail-transcript"');
});

t('C3.06 — Calls tab transcript EN/FR toggle', () => {
  inc(PROFILE, 'data-testid="call-transcript-en"');
  inc(PROFILE, 'data-testid="call-transcript-fr"');
});

t('C3.07 — AI Report tab: sentiment + top actions', () => {
  inc(PROFILE, 'data-testid="ai-report-tab"');
  inc(PROFILE, 'data-testid="sentiment-breakdown"');
  inc(PROFILE, 'data-testid="top-actions-list"');
});

t('C3.08 — Clients tab: table with vehicle/marketplace counts', () => {
  inc(PROFILE, 'data-testid="clients-table"');
  inc(PROFILE, 'vehicle_active_count');
  inc(PROFILE, 'marketplace_active');
});

t('C3.09 — Dashboard mirror tab', () => {
  inc(PROFILE, 'data-testid="dashboard-mirror-tab"');
  inc(PROFILE, 'testid="mirror-accrued"');
  inc(PROFILE, 'testid="mirror-paid"');
  inc(PROFILE, 'data-testid="mirror-history-table"');
});

t('C3.10 — Stripe payout status mirrored', () => {
  inc(PROFILE, 'data-testid="contractor-profile-stripe"');
});

t('C3.11 — Admin-only recording playback button', () => {
  inc(PROFILE, 'data-testid="call-play-recording-btn"');
  inc(PROFILE, '/twilio/calls/${call._id || call.id}/recording');
});

t('C3.12 — Demoted-warning badge when admin views a former contractor', () => {
  inc(PROFILE, 'data-testid="contractor-profile-demoted-warning"');
});

// ─── Contractor row clickable to drill-in ────────────────────────

t('C3.13 — View button on Contractors row navigates to /admin/contractors/{id}', () => {
  inc(CONTRACTORS, 'data-testid={`view-profile-btn-');
  inc(CONTRACTORS, '/admin/contractors/${c.id}');
});

console.log(`\n  ${passes} passed, ${failures} failed`);
if (failures > 0) process.exit(1);
process.exit(0);
