/**
 * bidvex-bot-prerender — Cloudflare Worker (iter355)
 *
 * ONE JOB: intercept crawler / social-unfurl traffic on www.bidvex.com/*
 * and reverse-proxy it to our FastAPI SSR endpoint at
 *     https://www.bidvex.com/api/prerender{path}
 * so bots see server-rendered HTML with <title>, meta description,
 * canonical, hreflang, OpenGraph, and Schema.org JSON-LD.
 *
 * Real users are UNTOUCHED — their requests pass through to the
 * React SPA build served by the origin.
 *
 * --------------------------------------------------------------------
 * SAFETY GUARANTEES
 * --------------------------------------------------------------------
 *  1. NEVER issues a redirect. If anything goes wrong we pass through
 *     to the origin so the crawler still gets a valid response.
 *  2. Loop-protected: the sub-request to /api/prerender carries
 *     `x-bidvex-worker: 1` so any hop that re-enters the worker path
 *     is immediately passed through (belt + suspenders).
 *  3. Timeout-guarded: origin call is bounded by 8s AbortController.
 *  4. Cache-friendly: successful prerender responses are stamped with
 *     `Cache-Control: public, max-age=60, s-maxage=300` so Cloudflare
 *     caches the HTML for 5 min at the edge (huge win on repeat
 *     crawl traffic).
 *  5. Failure-open: if the SSR endpoint 5xx's, we fall through to the
 *     SPA so we NEVER black-hole a crawler.
 * --------------------------------------------------------------------
 */

const BOT_UA_REGEX = new RegExp([
  // Search engines
  'googlebot', 'google-inspectiontool', 'google-structured-data-testing-tool',
  'adsbot-google', 'mediapartners-google', 'apis-google',
  'bingbot', 'msnbot', 'bingpreview',
  'slurp', 'yahoo',
  'duckduckbot', 'duckduckgo',
  'baiduspider', 'yandex(bot|images)?', 'yeti', 'naverbot',
  'sogou', 'exabot', 'seznambot',
  // Social unfurlers
  'facebot', 'facebookexternalhit', 'meta-externalagent',
  'linkedinbot', 'twitterbot', 'x-clientua',
  'slackbot', 'slack-imgproxy',
  'discordbot',
  'whatsapp', 'telegrambot', 'vkshare',
  'redditbot', 'applebot',
  // SEO / audit crawlers
  'mj12bot', 'semrushbot', 'ahrefsbot', 'dotbot', 'petalbot',
  'bytespider', 'chrome-lighthouse',
  'w3c_validator', 'validator\\.w3\\.org',
  // Generic bot markers (last-line-of-defense)
  'headlesschrome',
].join('|'), 'i');

// Paths we ALWAYS pass through unchanged (never prerender)
const NEVER_PRERENDER_PREFIXES = [
  '/api/',       // FastAPI routes — our origin owns them
  '/static/',    // React static build assets
  '/assets/',
  '/_next/',
  '/wp-',        // ignore WP probe traffic
];

// Static file extensions — pass straight through to origin
const STATIC_EXT_REGEX = /\.(js|mjs|css|png|jpe?g|webp|avif|gif|svg|ico|map|txt|xml|json|woff2?|ttf|eot|mp4|mp3|pdf|zip)$/i;

// Whitelisted "prerender-worthy" prefixes. Anything not on this list
// falls through to the SPA even for bots — safer default than
// prerendering an unknown route (avoids Cloudflare Worker 500ing on
// paths the FastAPI /api/prerender endpoint doesn't handle).
const PRERENDER_PREFIXES = [
  '/',
  '/marketplace', '/lots-marketplace', '/lots-auction',
  '/vehicle-auctions', '/storage-auctions', '/live-auctions',
  '/broker-directory', '/prospect-directory',
  '/auctions/', '/multi-item-auctions/',
  '/vehicles/', '/storage/', '/lots/',
  '/faq', '/how-it-works',
  '/about', '/about-us', '/contact', '/help',
  '/terms', '/legal/', '/legal',
  '/privacy-policy', '/privacy',
  '/blog', '/blog/',
  '/sitemap', '/robots.txt',
];

/** Should this path be handled by the prerender endpoint? */
function isPrerenderPath(path) {
  if (!path || path === '') return false;
  if (NEVER_PRERENDER_PREFIXES.some((p) => path.startsWith(p))) return false;
  if (STATIC_EXT_REGEX.test(path)) return false;
  if (path === '/') return true;
  return PRERENDER_PREFIXES.some((p) => {
    if (p === '/') return path === '/';
    if (p.endsWith('/')) return path.startsWith(p);
    // Exact match OR "path starts with p + '/'" (avoid /faq2 matching /faq)
    return path === p || path.startsWith(p + '/') || path.startsWith(p + '?');
  });
}

/** Detect crawler / social-unfurl agents. */
function isBotUA(ua) {
  if (!ua) return false;
  return BOT_UA_REGEX.test(ua);
}

/** Bounded fetch with AbortController — 8s wall-clock limit. */
async function fetchWithTimeout(request, ms = 8000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(request, { signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
}

/** Preferred language derivation: ?lang= → accept-language → en. */
function pickLang(url, request) {
  const q = url.searchParams.get('lang');
  if (q === 'en' || q === 'fr') return q;
  const al = (request.headers.get('accept-language') || '').toLowerCase();
  if (al.startsWith('fr')) return 'fr';
  return 'en';
}

export default {
  async fetch(request, env, ctx) {
    // Loop-protection: if a previous hop already went through this Worker
    // (or if someone is spoofing) — pass straight through.
    if (request.headers.get('x-bidvex-worker') === '1') {
      return fetch(request);
    }

    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    // Only GET/HEAD are prerender-eligible.
    if (method !== 'GET' && method !== 'HEAD') {
      return fetch(request);
    }

    // Path guards.
    if (!isPrerenderPath(url.pathname)) {
      return fetch(request);
    }

    // Bot detection — also allow ?_ssr=1 for manual QA.
    const ua = request.headers.get('user-agent') || '';
    const forceSSR = url.searchParams.get('_ssr') === '1';
    if (!forceSSR && !isBotUA(ua)) {
      return fetch(request);
    }

    // Build the reverse-proxy target: /api/prerender{path}?lang=xx
    const lang = pickLang(url, request);
    const target = new URL(
      `/api/prerender${url.pathname}`,
      'https://www.bidvex.com'
    );
    // Preserve original query string but force ?lang=
    for (const [k, v] of url.searchParams.entries()) {
      if (k !== 'lang' && k !== '_ssr') target.searchParams.set(k, v);
    }
    target.searchParams.set('lang', lang);

    // Forward selected headers only. We drop cookies + auth to keep
    // the response uncorrelated with any user session (this MUST be
    // safe for Cloudflare edge caching).
    const fwdHeaders = new Headers();
    fwdHeaders.set('user-agent', ua);
    fwdHeaders.set('accept', 'text/html,application/xhtml+xml,*/*;q=0.9');
    fwdHeaders.set('accept-language', request.headers.get('accept-language') || 'en');
    fwdHeaders.set('x-forwarded-for', request.headers.get('cf-connecting-ip') || '');
    fwdHeaders.set('x-forwarded-proto', 'https');
    fwdHeaders.set('x-forwarded-host', url.hostname);
    fwdHeaders.set('x-bidvex-worker', '1');       // loop guard
    fwdHeaders.set('x-bidvex-original-path', url.pathname);

    let ssrResp;
    try {
      const ssrReq = new Request(target.toString(), {
        method: 'GET',      // always GET the SSR endpoint even if original was HEAD
        headers: fwdHeaders,
        // Cache at the edge — bot traffic is highly cacheable.
        cf: {
          cacheEverything: true,
          cacheTtl: 300,                        // 5 minutes
          cacheTtlByStatus: {
            '200-299': 300,
            '404': 30,
            '500-599': 0,
          },
        },
        redirect: 'manual',                     // NEVER follow redirects from origin
      });
      ssrResp = await fetchWithTimeout(ssrReq, 8000);
    } catch (err) {
      // Timeout / network error — fall through to SPA rather than
      // black-hole the crawler.
      return fetch(request);
    }

    // If SSR endpoint replied with a non-2xx and non-404, fall through to SPA.
    if (!ssrResp || (ssrResp.status >= 500)) {
      return fetch(request);
    }
    // If we got a redirect back from origin, DO NOT propagate — that
    // would loop the crawler. Fall through to SPA instead.
    if (ssrResp.status >= 300 && ssrResp.status < 400) {
      return fetch(request);
    }

    // Copy SSR body + headers, but stamp observability markers.
    const outHeaders = new Headers(ssrResp.headers);
    outHeaders.set('x-prerender-worker', 'bidvex-bot-prerender/iter355');
    outHeaders.set('x-prerender-bot-ua', ua.slice(0, 120));
    outHeaders.set('x-prerender-lang', lang);
    // Aggressive edge-cache for crawlers (browsers won't respect
    // this because Chrome UA won't ever hit this branch).
    if (!outHeaders.has('cache-control')) {
      outHeaders.set('cache-control', 'public, max-age=60, s-maxage=300');
    }
    // Belt: ensure content-type is HTML.
    if (!outHeaders.get('content-type')) {
      outHeaders.set('content-type', 'text/html; charset=utf-8');
    }

    // Strip origin-Cloudflare hop headers (avoid double-encoding on chained CF).
    outHeaders.delete('cf-cache-status');
    outHeaders.delete('cf-ray');

    return new Response(ssrResp.body, {
      status: ssrResp.status,
      statusText: ssrResp.statusText,
      headers: outHeaders,
    });
  },
};
