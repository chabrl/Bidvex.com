/**
 * bidvex-bot-prerender — Cloudflare Worker (iter355-v2, diagnostic-hardened)
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
 * v2 (iter355) CHANGES vs v1 (iter354):
 *   • Diagnostic header `x-bidvex-worker-invoked: 1` is stamped on
 *     EVERY response the Worker touches, even pass-throughs — so
 *     external `curl` tests can prove the Worker fired.
 *   • `?_ssr=1` bypasses BOTH the bot-UA guard AND the path-prefix
 *     guard, allowing manual SSR debug on any URL.
 *   • Body-preserving pass-through wrapper (avoids "Body has already
 *     been used" errors when re-emitting a Response).
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
 *     caches the HTML for 5 min at the edge.
 *  5. Failure-open: if the SSR endpoint 5xx's, we fall through to the
 *     SPA so we NEVER black-hole a crawler.
 * --------------------------------------------------------------------
 */

const WORKER_VERSION = 'bidvex-bot-prerender/iter355-v2';

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

const NEVER_PRERENDER_PREFIXES = [
  '/api/', '/static/', '/assets/', '/_next/', '/wp-',
];

const STATIC_EXT_REGEX = /\.(js|mjs|css|png|jpe?g|webp|avif|gif|svg|ico|map|txt|xml|json|woff2?|ttf|eot|mp4|mp3|pdf|zip)$/i;

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
  // Diagnostic prefix — allows __worker_probe/* to be treated as
  // prerender-worthy WHEN combined with ?_ssr=1 (bot UA still required
  // for real hits).
  '/__worker_probe',
];

function isPrerenderPath(path) {
  if (!path || path === '') return false;
  if (NEVER_PRERENDER_PREFIXES.some((p) => path.startsWith(p))) return false;
  if (STATIC_EXT_REGEX.test(path)) return false;
  if (path === '/') return true;
  return PRERENDER_PREFIXES.some((p) => {
    if (p === '/') return path === '/';
    if (p.endsWith('/')) return path.startsWith(p);
    return path === p || path.startsWith(p + '/') || path.startsWith(p + '?');
  });
}

function isBotUA(ua) {
  if (!ua) return false;
  return BOT_UA_REGEX.test(ua);
}

async function fetchWithTimeout(request, ms = 8000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(request, { signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
}

function pickLang(url, request) {
  const q = url.searchParams.get('lang');
  if (q === 'en' || q === 'fr') return q;
  const al = (request.headers.get('accept-language') || '').toLowerCase();
  if (al.startsWith('fr')) return 'fr';
  return 'en';
}

/**
 * Pass-through wrapper — clones the origin response and stamps the
 * diagnostic header. Used for any code path that doesn't SSR.
 */
async function stampPassthrough(request, reason) {
  const origResp = await fetch(request);
  const newHeaders = new Headers(origResp.headers);
  newHeaders.set('x-bidvex-worker-invoked', '1');
  newHeaders.set('x-bidvex-worker-version', WORKER_VERSION);
  newHeaders.set('x-bidvex-worker-branch', reason);
  return new Response(origResp.body, {
    status: origResp.status,
    statusText: origResp.statusText,
    headers: newHeaders,
  });
}

export default {
  async fetch(request, env, ctx) {
    // Loop-protection: if a previous hop already went through this Worker
    // (or if someone is spoofing) — pass straight through (no double-stamp).
    if (request.headers.get('x-bidvex-worker') === '1') {
      return fetch(request);
    }

    const url = new URL(request.url);
    const method = request.method.toUpperCase();
    const ua = request.headers.get('user-agent') || '';
    const forceSSR = url.searchParams.get('_ssr') === '1';

    // Only GET/HEAD are prerender-eligible.
    if (method !== 'GET' && method !== 'HEAD') {
      return stampPassthrough(request, 'non-get');
    }

    // Path guards. `?_ssr=1` bypasses path filtering for debug.
    if (!forceSSR && !isPrerenderPath(url.pathname)) {
      return stampPassthrough(request, 'path-not-prerender');
    }

    // Bot detection — `_ssr=1` also bypasses UA filtering.
    if (!forceSSR && !isBotUA(ua)) {
      return stampPassthrough(request, 'ua-not-bot');
    }

    // Reverse-proxy target: /api/prerender{path}?lang=xx
    const lang = pickLang(url, request);
    const target = new URL(
      `/api/prerender${url.pathname}`,
      'https://www.bidvex.com'
    );
    for (const [k, v] of url.searchParams.entries()) {
      if (k !== 'lang' && k !== '_ssr') target.searchParams.set(k, v);
    }
    target.searchParams.set('lang', lang);

    const fwdHeaders = new Headers();
    fwdHeaders.set('user-agent', ua);
    fwdHeaders.set('accept', 'text/html,application/xhtml+xml,*/*;q=0.9');
    fwdHeaders.set('accept-language', request.headers.get('accept-language') || 'en');
    fwdHeaders.set('x-forwarded-for', request.headers.get('cf-connecting-ip') || '');
    fwdHeaders.set('x-forwarded-proto', 'https');
    fwdHeaders.set('x-forwarded-host', url.hostname);
    fwdHeaders.set('x-bidvex-worker', '1');
    fwdHeaders.set('x-bidvex-original-path', url.pathname);

    let ssrResp;
    try {
      const ssrReq = new Request(target.toString(), {
        method: 'GET',
        headers: fwdHeaders,
        cf: {
          cacheEverything: true,
          cacheTtl: 300,
          cacheTtlByStatus: {
            '200-299': 300,
            '404': 30,
            '500-599': 0,
          },
        },
        redirect: 'manual',
      });
      ssrResp = await fetchWithTimeout(ssrReq, 8000);
    } catch (err) {
      return stampPassthrough(request, 'ssr-fetch-error');
    }

    if (!ssrResp) {
      return stampPassthrough(request, 'ssr-no-response');
    }
    if (ssrResp.status >= 500) {
      return stampPassthrough(request, 'ssr-5xx');
    }
    if (ssrResp.status >= 300 && ssrResp.status < 400) {
      return stampPassthrough(request, 'ssr-redirect');
    }

    const outHeaders = new Headers(ssrResp.headers);
    outHeaders.set('x-bidvex-worker-invoked', '1');
    outHeaders.set('x-bidvex-worker-version', WORKER_VERSION);
    outHeaders.set('x-bidvex-worker-branch', 'prerender-served');
    outHeaders.set('x-prerender-worker', WORKER_VERSION);
    outHeaders.set('x-prerender-bot-ua', ua.slice(0, 120));
    outHeaders.set('x-prerender-lang', lang);
    if (!outHeaders.has('cache-control')) {
      outHeaders.set('cache-control', 'public, max-age=60, s-maxage=300');
    }
    if (!outHeaders.get('content-type')) {
      outHeaders.set('content-type', 'text/html; charset=utf-8');
    }
    outHeaders.delete('cf-cache-status');
    outHeaders.delete('cf-ray');

    return new Response(ssrResp.body, {
      status: ssrResp.status,
      statusText: ssrResp.statusText,
      headers: outHeaders,
    });
  },
};
