/**
 * iter316-D — Frontend wiring tests for Leaderboard + Banking
 * Validation banner + Contractor Permissions editor.
 *
 * Run via:  node frontend/src/__tests__/iter316_d_leaderboard_banking_perms.test.js
 */
const fs = require('fs');
const path = require('path');

let passes = 0;
let failures = 0;

function t(name, fn) {
  try { fn(); passes += 1; console.log(`  PASS  ${name}`); }
  catch (e) { failures += 1; console.error(`  FAIL  ${name}\n         ${e.message}`); }
}
function read(rel) { return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8'); }
function inc(hay, needle, hint) {
  if (!hay.includes(needle)) throw new Error(`expected: ${needle}${hint ? ` (${hint})` : ''}`);
}

const LB = read('pages/admin/AdminContractorsLeaderboard.jsx');
const PROFILE = read('pages/admin/AdminContractorProfilePage.jsx');
const DASH = read('pages/contractor/ContractorDashboard.jsx');
const ADMIN_DASH = read('pages/AdminDashboard.js');

console.log('\niter316-D — Leaderboard + Banking + Permissions wiring tests\n');

// ─── Leaderboard ─────────────────────────────────────────────────
console.log('D1 — Performance Leaderboard');

t('D1.01 — page root testid', () => inc(LB, 'data-testid="admin-leaderboard-page"'));
t('D1.02 — title & subtitle render', () => inc(LB, 'data-testid="admin-leaderboard-title"'));
t('D1.03 — period filter buttons (lifetime / month / week)', () => {
  inc(LB, 'data-testid={`period-${p.key}`}');
  inc(LB, "{ key: 'lifetime'");
  inc(LB, "{ key: 'month'");
  inc(LB, "{ key: 'week'");
});
t('D1.04 — sortable column headers (earnings/call_volume/referred/conversion)', () => {
  inc(LB, 'data-testid={`sort-${k.key}`}');
  inc(LB, "{ key: 'earnings'");
  inc(LB, "{ key: 'call_volume'");
  inc(LB, "{ key: 'referred_count'");
  inc(LB, "{ key: 'conversion_rate'");
});
t('D1.05 — leaderboard table testid + row testid', () => {
  inc(LB, 'data-testid="leaderboard-table"');
  inc(LB, 'data-testid={`leaderboard-row-');
});
t('D1.06 — top performer card highlight', () => {
  inc(LB, 'data-testid="leaderboard-top-performer"');
});
t('D1.07 — empty state', () => inc(LB, 'data-testid="leaderboard-empty"'));
t('D1.08 — fetches the correct endpoint with period param', () => {
  inc(LB, '/twilio/admin/contractors/leaderboard?period=${period}');
});
t('D1.09 — clicking View navigates to /admin/contractors/{id}', () => {
  inc(LB, '`/admin/contractors/${row.contractor_id}`');
  inc(LB, 'data-testid={`leaderboard-view-');
});

t('D1.10 — wired as new sub-tab in Dialer & Contractors', () => {
  inc(ADMIN_DASH, "{ id: 'leaderboard'");
  inc(ADMIN_DASH, 'AdminContractorsLeaderboard');
});

// ─── Banking validation ──────────────────────────────────────────
console.log('\nD2 — Banking validation on Contractor Dashboard');

t('D2.01 — hard-block banner data-testid', () => {
  inc(DASH, 'data-testid="banking-validation-alert"');
});
t('D2.02 — banner renders ONLY when accrued > 0 AND not ready', () => {
  inc(DASH, '!payoutReadiness.ready && payoutReadiness.accrued_total > 0');
});
t('D2.03 — "Resolve now" CTA wired to Stripe onboarding', () => {
  inc(DASH, 'data-testid="banking-validation-resolve-btn"');
  inc(DASH, 'startStripeOnboarding');
});
t('D2.04 — per-reason testid rendered', () => {
  inc(DASH, 'data-testid={`blocked-reason-${r}`}');
});
t('D2.05 — "OK" green banner shown when ready', () => {
  inc(DASH, 'data-testid="banking-validation-ok"');
});
t('D2.06 — fetches /twilio/contractor/payout-readiness', () => {
  inc(DASH, '/twilio/contractor/payout-readiness');
});

// ─── Permissions ─────────────────────────────────────────────────
console.log('\nD3 — Contractor Permissions');

t('D3.01 — Permissions tab in Admin Drill-in', () => {
  inc(PROFILE, 'data-testid="tab-permissions"');
  inc(PROFILE, 'data-testid="permissions-tab"');
});
t('D3.02 — Per-permission row + checkbox testid', () => {
  inc(PROFILE, 'data-testid={`permission-row-${perm}`}');
  inc(PROFILE, 'data-testid={`permission-toggle-${perm}`}');
});
t('D3.03 — Save permissions button + endpoint', () => {
  inc(PROFILE, 'data-testid="permissions-save-btn"');
  inc(PROFILE, '/twilio/admin/contractors/${contractorId}/permissions');
  inc(PROFILE, 'axios.patch');
});
t('D3.04 — Allowed perms come from server (whitelist enforced server-side)', () => {
  inc(PROFILE, 'allowed_options');
});

// Contractor dashboard surfaces granted permissions + Add Client modal.
t('D3.05 — Permissions card on Contractor Dashboard', () => {
  inc(DASH, 'data-testid="contractor-permissions-card"');
  inc(DASH, 'data-testid="contractor-permissions-list"');
});
t('D3.06 — Add Client button gated by add_users permission', () => {
  inc(DASH, "permissions.includes('add_users')");
  inc(DASH, 'data-testid="contractor-add-client-btn"');
});
t('D3.07 — Manage Subscriptions button gated by manage_subscriptions perm', () => {
  inc(DASH, "permissions.includes('manage_subscriptions')");
  inc(DASH, 'data-testid="contractor-manage-subs-btn"');
});
t('D3.08 — Add Client modal: email/name/phone/province/account-type fields', () => {
  inc(DASH, 'data-testid="contractor-add-client-modal"');
  inc(DASH, 'data-testid="add-client-email"');
  inc(DASH, 'data-testid="add-client-name"');
  inc(DASH, 'data-testid="add-client-phone"');
  inc(DASH, 'data-testid="add-client-province"');
  inc(DASH, 'data-testid="add-client-type"');
});
t('D3.09 — Add Client submits to /twilio/contractor/clients', () => {
  inc(DASH, '/twilio/contractor/clients');
});
t('D3.10 — Success state shows invite link', () => {
  inc(DASH, 'data-testid="add-client-success"');
  inc(DASH, 'data-testid="client-invite-link"');
});

console.log(`\n  ${passes} passed, ${failures} failed`);
if (failures > 0) process.exit(1);
process.exit(0);
