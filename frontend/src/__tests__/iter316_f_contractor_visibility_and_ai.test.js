/**
 * iter316-F — Frontend wiring tests for the contractor-visibility +
 * AI-voice-config-banner bug fixes.
 */
const fs = require('fs');
const path = require('path');

let passes = 0, failures = 0;
function t(name, fn) {
  try { fn(); passes += 1; console.log(`  PASS  ${name}`); }
  catch (e) { failures += 1; console.error(`  FAIL  ${name}\n         ${e.message}`); }
}
function read(rel) { return fs.readFileSync(path.join(__dirname, '..', rel), 'utf8'); }
function inc(hay, needle, hint) {
  if (!hay.includes(needle)) throw new Error(`expected: ${needle}${hint ? ` (${hint})` : ''}`);
}

const NAVBAR = read('components/Navbar.js');
const AUTH = read('pages/AuthPage.js');
const DIALER = read('pages/admin/AdminDialer.jsx');

console.log('\niter316-F — Contractor visibility + AI banner wiring tests\n');

// ─── Navbar entry points for contractors ─────────────────────────
console.log('F1 — Navbar entry points');

t('F1.01 — Contractor Dashboard menu link', () => {
  inc(NAVBAR, 'data-testid="contractor-dashboard-link"');
  inc(NAVBAR, "navigate('/contractor/dashboard')");
});

t('F1.02 — Dialer menu link', () => {
  inc(NAVBAR, 'data-testid="dialer-link"');
  inc(NAVBAR, "navigate('/admin/dialer')");
});

t('F1.03 — Both links gated by role===dialer_contractor || admin', () => {
  inc(NAVBAR, "user.role === 'dialer_contractor'");
});

t('F1.04 — Headphones icon for contractor dashboard', () => {
  inc(NAVBAR, 'Headphones');
  inc(NAVBAR, 'PhoneCall');
});

// ─── Post-login role-aware redirect ──────────────────────────────
console.log('\nF2 — Post-login redirect');

t('F2.01 — Login resolves user object and uses role for fallback', () => {
  inc(AUTH, 'loggedInUser');
  inc(AUTH, "loggedInUser?.role === 'dialer_contractor'");
});

t('F2.02 — Contractor fallback target is /contractor/dashboard', () => {
  inc(AUTH, "'/contractor/dashboard'");
});

t('F2.03 — Existing deep-link redirect (location.state.from) preserved', () => {
  inc(AUTH, 'location.state?.from?.pathname || fallback');
});

// ─── AI voice config banner ──────────────────────────────────────
console.log('\nF3 — AI voice config banner');

t('F3.01 — Banner renders when ai_voice_configured === false', () => {
  inc(DIALER, 'data-testid="dialer-ai-config-banner"');
  inc(DIALER, 'config?.ai_voice_configured === false');
});

t('F3.02 — Banner lists missing env var (GEMINI_API_KEY)', () => {
  inc(DIALER, 'ai_voice_missing');
  inc(DIALER, "['GEMINI_API_KEY']");
});

t('F3.03 — Banner only shows AFTER twilio is configured (avoid noise)', () => {
  inc(DIALER, "config?.configured && config?.ai_voice_configured === false");
});

console.log(`\n  ${passes} passed, ${failures} failed`);
if (failures > 0) process.exit(1);
process.exit(0);
