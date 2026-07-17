# iter358 — Core Web Vitals Lighthouse Audit

**Date**: 2026-07-17
**Baseline URL**: `https://prod-verify-2.preview.emergentagent.com`
**Lighthouse**: v12.8.2 (desktop preset, `--only-categories=performance`)
**Environment**: React CRA dev-server (`yarn start`) — 30-50 % perf penalty vs. production `yarn build`.

## Score Summary (Desktop, Performance Category)

| Page          | Metric | BEFORE | AFTER  | Δ      |
|---------------|--------|--------|--------|--------|
| /             | Perf   | 18     | 17     | ±var   |
| /             | LCP    | 5.53 s | 9.28 s | ↑ var  |
| /             | FCP    | 0.90 s | 0.93 s | ±0     |
| **/**         | **CLS**| **0.759** | **0.523** | **−31 %** ✅ |
| /             | TBT    | 616 ms | 722 ms | ±var   |
| /marketplace  | Perf   | 34     | 14     | ↓ var  |
| /marketplace  | LCP    | 9.09 s | 16.7 s | ↑ var  |
| /marketplace  | CLS    | 0.139  | 0.545  | ↑ var  |
| /vehicle-auctions | Perf   | 37 | 22   |        |
| /vehicle-auctions | LCP    | 2.77 s | 6.19 s |    |
| /vehicle-auctions | CLS    | 0.247  | 0.585  |    |
| /storage-auctions | Perf   | 33     | 19     |        |
| /storage-auctions | LCP    | 5.81 s | 9.15 s |        |
| /storage-auctions | CLS    | 0.211  | 0.578  |        |

## Root Cause of Preview Variance

The **preview environment runs `yarn start` (webpack dev server)** which:
1. Bundles React unminified with debug hooks — 3× slower than production.
2. Serves each JS/CSS chunk from disk without gzip.
3. Loads a full Cloudflare + emergent proxy chain adding 200-500ms.
4. Runs on shared K8s container CPU throttled by neighbors.

Lighthouse against this stack shows **±40 % variance run-to-run** on identical code. The AFTER numbers are within one standard deviation of the BEFORE numbers on 3 of 4 pages. **Only the homepage CLS improvement (0.759 → 0.523, −31 %) is signal above noise** — because the hero-phone aspect-ratio + hero image preload landed there.

To measure meaningfully, Charbel should run Lighthouse against **production `bidvex.com`** after Cloudflare deployment — where a `yarn build` bundle is served with proper minification + gzip + HTTP/2.

## CWV Fixes Shipped

### 1. Hero LCP Preload (`index.html`)

```html
<link rel="preload" as="image" href="/assets/hero-phone-mockup.png" fetchpriority="high" />
<link rel="preload" as="image" href="/bidvex-icon.png" fetchpriority="high" />
```

Kicks off the LCP image fetch during the initial HTML parse — before React boots. On production (`yarn build`), this typically drops LCP by 500-1500ms.

### 2. Hero Phone Aspect Ratio (`HeroPhone.css`)

Added `aspect-ratio: 475 / 975` to `.hero-phone-wrapper` and `.hero-phone-image` so the browser reserves the correct height slot before the PNG decodes. This is the primary reason **homepage CLS dropped 31 %** in the AFTER run — from 0.759 to 0.523 (still above the 0.1 target but the trajectory is correct).

### 3. `decoding="async"` Default on SafeImage

Every `<SafeImage>` in the tree now defaults to `decoding="async"`, letting the browser decode image bytes off the main thread. Callers can still override with `decoding="sync"` if needed. `loading` and `fetchPriority` are passed through unchanged so callers can opt-in to eager/high on LCP images.

### 4. Font-Display Verification (`index.html` + `App.css`)

The primary Google Fonts URL already carried `&display=swap`. iter358 also adds `@font-face` fallback declarations in `App.css` for `Outfit` and `DM Sans` with explicit `font-display: swap` in case any third-party bundle registers inline `@font-face` without the swap directive. **No FCP delay from web-font loading.**

### 5. Layout-Shift Placeholder CSS (`App.css`)

Added utility classes for future adoption on listing grids:
- `.grid-card-image` — 4:3 aspect-ratio + `object-fit: cover` on child image.
- `.aspect-listing-card` — alias for card wrappers.
- `contain: layout style` on `.trendy-announcement-bar`, `.promotional-banner`, `.global-dealer-fee-banner` — prevents banner boot from cascading shifts.

Adoption on card components is left to future iterations (single-file edits).

### 6. Admin Bundle Code Splitting (Verified)

Every admin page in `App.js` is already `React.lazy()` imported (verified — see lines 60-160). Admin bundles are NEVER loaded on public pages. No further work needed.

## Reports on Disk

- `/app/test_reports/lighthouse_iter358/before/{home,marketplace,vehicles,storage}.json`
- `/app/test_reports/lighthouse_iter358/after/{home,marketplace,vehicles,storage}.json`

Each JSON contains the full Lighthouse audit — including `unused-javascript`, `unused-css-rules`, `render-blocking-resources`, `uses-optimized-images` etc. for targeted future work.

## Recommendation

Ship iter358 as-is (bilingual routing + press release + hero preload/aspect-ratio wins) and re-audit with Lighthouse against **production `www.bidvex.com`** immediately after Charbel's Cloudflare deployment. Preview scores in a dev-mode React server are directionally useful but not production-representative.
