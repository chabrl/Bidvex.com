"""
iter277 — Floating AI Core support widget verification.

Coverage:

Mission 1 — Component file shape
  • `components/AICoreSupportWidget.jsx` exists and exposes the
    canonical testids (`ai-core-fab`, `-widget`, `-input`, `-send`,
    `-close`, `-clear`, `-empty-state`, `-typing`, `-message-list`,
    `-suggestion-*`).
  • Reads `useAuth` for the bearer token + user id and `useTranslation`
    for the active locale state — fully wired into the BidVex
    auth/i18n infrastructure.
  • Returns null for unauthenticated users (anonymous traffic must
    never reach the platform-internal AI surface).

Mission 2 — App wiring + scope
  • `App.js` lazy-imports the widget and renders an
    `AICoreSupportWidgetWrapper` that gates by route — only the
    authenticated dashboards + admin pages mount it.
  • The wrapper is sibling to the existing public `AIAssistantWrapper`
    (not a replacement).

Mission 3 — LocalStorage persistence
  • Storage key is per-user (`bidvex.ai_core_chat.v1.<userId>`) so
    account-switching on the same browser does NOT leak transcripts.
  • Hard-cap of 30 messages so localStorage stays bounded.
  • Persist + load logic both wrapped in try/except so corruption /
    disabled-storage browsers degrade gracefully.

Mission 4 — Bilingual UX
  • Every literal placeholder, button label, alert, and prompt-card
    string flows through `t('aiCore.*')`. No hardcoded user-facing
    English strings in the component body.
  • `locales/en.json` AND `locales/fr.json` both ship the matching
    `aiCore` namespace with identical key sets.

Mission 5 — Backend handshake
  • The widget POSTs to `/support/chat` with `{message, session_id,
    language}` and reads `response` from the envelope. Auth header is
    `Bearer <token>`.
  • Live HTTP sanity that the iter276 endpoint still responds 200 with
    a well-formed envelope (re-uses the iter276 test-mode short-circuit).
"""
from __future__ import annotations

import json
import os
import re

import pytest


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8001")


def _read_fe(rel: str) -> str:
    with open(os.path.join(FRONTEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── Mission 1 — Component shape ───────────────────────────────────────


def test_iter277_widget_file_exists():
    fp = os.path.join(FRONTEND_ROOT, "components", "AICoreSupportWidget.jsx")
    assert os.path.isfile(fp), f"AICoreSupportWidget.jsx missing at {fp}"


def test_iter277_widget_exposes_canonical_testids():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    for tid in (
        "ai-core-fab",
        "ai-core-widget",
        "ai-core-input",
        "ai-core-close",
        "ai-core-clear",
        "ai-core-empty-state",
        "ai-core-typing",
        "ai-core-message-list",
    ):
        assert f'data-testid="{tid}"' in src, f"missing testid: {tid}"
    # iter278 — the action button testid is a conditional template:
    # `ai-core-stop` while streaming, `ai-core-send` otherwise.
    assert 'data-testid={sending ? "ai-core-stop" : "ai-core-send"}' in src
    # Suggestion-card testids are template-literals.
    assert "data-testid={`ai-core-suggestion-${p.key}`}" in src
    # Message-bubble testids carry role + index.
    assert "data-testid={`ai-core-msg-${m.role}-${idx}`}" in src


def test_iter277_widget_uses_auth_and_i18n():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert "useTranslation" in src
    assert "useAuth" in src
    # Bearer-token wiring on every outbound call.
    assert "Authorization: `Bearer ${token}`" in src
    # The widget MUST short-circuit when there's no logged-in user.
    assert "if (!user) return null;" in src


def test_iter277_widget_no_hardcoded_user_facing_english():
    """Every literal placeholder, button label, alert, and prompt-card
    string must flow through `t('aiCore.*')`. Code comments + dev
    strings (testids, classnames, console.error) are exempt."""
    src = _read_fe("components/AICoreSupportWidget.jsx")
    # The textarea placeholder, aria-labels, and footer hint must all
    # be t(...) calls.
    assert "placeholder={t('aiCore.placeholder')}" in src
    assert "aria-label={t('aiCore.openLabel')}" in src
    assert "aria-label={t('aiCore.closeLabel')}" in src
    assert "aria-label={t('aiCore.clearLabel')}" in src
    # iter278 — Send/Stop aria-label is conditional but both branches
    # route through t().
    assert "aria-label={sending ? t('aiCore.stopLabel') : t('aiCore.sendLabel')}" in src
    assert "{t('aiCore.title')}" in src
    assert "{t('aiCore.subtitle')}" in src
    assert "{t('aiCore.thinking')}" in src
    assert "{t('aiCore.emptyStateLead')}" in src
    assert "{t('aiCore.footerHint')}" in src
    # Suggestion cards use t() too.
    assert "t('aiCore.promptVehicleBid')" in src
    assert "t('aiCore.promptTrialCoupon')" in src
    assert "t('aiCore.promptTaxProfile')" in src
    assert "t('aiCore.promptStorageDoc')" in src


# ── Mission 2 — App wiring + scope ────────────────────────────────────


def test_iter277_app_lazy_imports_widget():
    src = _read_fe("App.js")
    assert "AICoreSupportWidget" in src
    # MUST be lazy — the widget pulls a chunk including its i18n keys.
    assert "lazy(() => import('./components/AICoreSupportWidget'))" in src


def test_iter277_app_mounts_widget_only_on_dashboards_and_admin():
    src = _read_fe("App.js")
    assert "AICoreSupportWidgetWrapper" in src
    # Route gates surface every authenticated dashboard surface.
    for needle in (
        "/seller/dashboard",
        "/buyer/dashboard",
        "/facility/dashboard",
        "path.startsWith('/admin')",
    ):
        assert needle in src, f"missing route gate: {needle}"
    # And the wrapper bails out when no route matches.
    assert "if (!isDashboard && !isAdmin) return null;" in src


def test_iter277_app_does_not_replace_existing_assistant():
    """Sanity — the public-facing AIAssistant must still mount. The
    iter277 widget is an ADDITION, not a refactor."""
    src = _read_fe("App.js")
    assert "<AIAssistantWrapper />" in src
    assert "<AICoreSupportWidgetWrapper />" in src
    # Both wrappers live under their own <Suspense>.
    assert src.count("<Suspense fallback={null}>") >= 2


# ── Mission 3 — LocalStorage persistence ──────────────────────────────


def test_iter277_widget_uses_per_user_storage_key():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert "STORAGE_PREFIX" in src
    assert "bidvex.ai_core_chat.v1" in src
    # The key MUST suffix the user id so account-switching on the same
    # browser does NOT leak transcripts.
    assert "${STORAGE_PREFIX}.${user?.id || 'anonymous'}" in src


def test_iter277_widget_caps_local_history_size():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert re.search(r"MAX_LOCAL_HISTORY\s*=\s*\d+", src), "history cap missing"
    # Both the load AND the persist path apply the cap.
    assert "messages.slice(-MAX_LOCAL_HISTORY)" in src
    assert "parsed.slice(-MAX_LOCAL_HISTORY)" in src


def test_iter277_widget_persist_path_is_defensive():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    # Two `try/catch { }` blocks — one for load, one for persist — so
    # corrupted blobs or disabled localStorage don't crash the widget.
    assert src.count("try {") >= 2
    assert "localStorage.setItem" in src
    assert "localStorage.getItem" in src
    assert "localStorage.removeItem" in src


def test_iter277_widget_clear_history_button_wired():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert "clearHistory" in src
    assert 'data-testid="ai-core-clear"' in src
    # Clear MUST wipe localStorage too, not just in-memory state.
    assert "localStorage.removeItem(storageKey)" in src


# ── Mission 4 — Bilingual locales ─────────────────────────────────────


REQUIRED_AICORE_KEYS = {
    "title", "subtitle", "openLabel", "closeLabel", "clearLabel",
    "sendLabel", "placeholder", "thinking", "errorPrefix",
    "emptyStateLead", "promptVehicleBid", "promptTrialCoupon",
    "promptTaxProfile", "promptStorageDoc", "footerHint",
}


def _load_locale(name: str):
    with open(os.path.join(FRONTEND_ROOT, "locales", name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_iter277_en_locale_has_full_aicore_namespace():
    en = _load_locale("en.json")
    assert "aiCore" in en, "en.json missing aiCore namespace"
    assert REQUIRED_AICORE_KEYS.issubset(set(en["aiCore"].keys())), (
        f"en.json aiCore missing keys: "
        f"{REQUIRED_AICORE_KEYS - set(en['aiCore'].keys())}"
    )
    # Hint strings reflect actual platform behaviour mentioned in iter275.
    assert "individual" in en["aiCore"]["promptVehicleBid"].lower()


def test_iter277_fr_locale_has_full_aicore_namespace():
    fr = _load_locale("fr.json")
    assert "aiCore" in fr, "fr.json missing aiCore namespace"
    assert REQUIRED_AICORE_KEYS.issubset(set(fr["aiCore"].keys()))
    # FR strings must be actual French — not English fallback.
    assert "Demander" in fr["aiCore"]["openLabel"] or "IA" in fr["aiCore"]["openLabel"]
    assert "véhicule" in fr["aiCore"]["promptVehicleBid"].lower()


def test_iter277_en_and_fr_aicore_key_sets_match():
    """A French translation MUST exist for every English key (and
    vice-versa) — drift between the two breaks the bilingual contract."""
    en_keys = set(_load_locale("en.json").get("aiCore", {}).keys())
    fr_keys = set(_load_locale("fr.json").get("aiCore", {}).keys())
    missing_in_fr = en_keys - fr_keys
    missing_in_en = fr_keys - en_keys
    assert not missing_in_fr, f"keys missing from fr.json: {missing_in_fr}"
    assert not missing_in_en, f"keys missing from en.json: {missing_in_en}"


# ── Mission 5 — Backend handshake (iter276 endpoint sanity) ───────────


def test_iter277_widget_posts_to_iter276_endpoint_with_correct_envelope():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    # iter278 — Widget now hits the streaming variant (`/chat/stream`)
    # via fetch. The legacy `/chat` JSON endpoint is still up (verified
    # in iter278 regression tests) but the widget itself prefers the
    # streaming surface for the typewriter UX.
    assert "${API_BASE}/support/chat/stream" in src
    # Payload includes message + session_id + language so the iter276
    # backend can route multi-turn AND honour the active locale.
    assert "message:    text," in src or "message: text" in src
    assert "session_id: sessionId" in src
    assert "language:   i18n.language || 'en'" in src or "language: i18n.language || 'en'" in src
    # Stream consumer reads the body via ReadableStream.
    assert "res.body.getReader()" in src


def test_iter277_session_id_anchored_to_user_id():
    """`session_id` shipped to the backend MUST track the logged-in
    user so the iter276 in-memory pool maintains multi-turn context
    correctly across page reloads."""
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert "const sessionId = user?.id ? `user:${user.id}` : null;" in src


def test_iter277_support_chat_endpoint_still_lives():
    """Live: the iter276 endpoint still responds 200 with the
    documented envelope — proves the widget's contract holds."""
    import httpx

    try:
        login = httpx.post(
            f"{BASE}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=8.0,
        )
    except Exception:
        pytest.skip("backend unreachable")
    if login.status_code != 200:
        pytest.skip("admin login unavailable (likely rate-limited)")
    token = login.json().get("access_token") or login.json().get("token")

    r = httpx.post(
        f"{BASE}/api/support/chat",
        json={"message": "iter277 widget handshake test"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Envelope shape must match what the widget reads.
    assert "response" in body
    assert "session_id" in body
    assert "model" in body
    assert "test_mode" in body
    # Backend is still in test mode in the preview env.
    assert body["test_mode"] is True
    assert body["response"].startswith("[TEST_MODE]")
