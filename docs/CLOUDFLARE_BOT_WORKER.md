# Cloudflare Bot-Prerender Worker — iter355 (hardened)

**File**: [`bidvex-bot-prerender.worker.js`](./cloudflare/bidvex-bot-prerender.worker.js) — copy-paste this file's contents into the Cloudflare Quick Editor.

Route bot User-Agent traffic on `www.bidvex.com` to our SSR prerender endpoint
so search crawlers, Facebook, LinkedIn, Slack, and WhatsApp see fully-rendered
HTML with title, meta description, Open Graph tags, and Schema.org JSON-LD.

**Real users are unaffected** — their traffic continues to the SPA build.

## What this Worker does

```
Request → Cloudflare Edge
  │
  ├─ User-Agent matches Googlebot/Bingbot/facebookexternalhit/etc.
  │    → rewrite URL to https://www.bidvex.com/api/prerender{path}
  │    → return that response (SSR HTML)
  │
  └─ Real user
       → passthrough (SPA served normally)
```

## Deploy steps

### 1. Prepare the Worker script

In the Cloudflare dashboard: **Workers & Pages → Create → Create Worker**.
Name it `bidvex-bot-prerender`. Paste the code from the next section.

### 2. Route the Worker

In the Worker's **Triggers** tab:
- Add route: `www.bidvex.com/*` on the `bidvex.com` zone.

### 3. Sanity-test after publish

```bash
# As Googlebot → should return SSR HTML with X-Prerender-Version header
curl -sI -A "Googlebot/2.1" https://www.bidvex.com/faq | grep -i prerender
# Expect:  x-prerender-version: iter354

# As real user → should return SPA (no prerender header)
curl -sI -A "Mozilla/5.0" https://www.bidvex.com/faq | grep -i prerender
# Expect:  (no output — SPA served, header not set)
```

Optional deep-check on any auction:
```bash
curl -s -A "Googlebot/2.1" https://www.bidvex.com/multi-item-auctions/{id} \
  | grep -oE '<title>[^<]+</title>|application/ld\+json'
```

## The Worker code

```js
// bidvex-bot-prerender — iter354 Cloudflare Worker
//
// Detects known search-crawler + social-unfurl User-Agents and reverse-proxies
// their request to /api/prerender{path}. Everyone else passes through to the
// SPA unchanged.

const BOT_UA_REGEX = new RegExp([
  'googlebot', 'bingbot', 'slurp', 'duckduckbot', 'baiduspider', 'yandexbot',
  'sogou', 'exabot', 'facebot', 'facebookexternalhit',
  'linkedinbot', 'twitterbot', 'slackbot', 'discordbot',
  'whatsapp', 'telegrambot', 'vkshare', 'w3c_validator',
  'redditbot', 'applebot', 'mj12bot', 'semrushbot', 'ahrefsbot',
  'yeti', 'petalbot', 'bytespider',
].join('|'), 'i');

// Paths we serve prerendered. Everything else falls through to the SPA.
const PRERENDER_PREFIXES = [
  '/', '/marketplace', '/lots-marketplace',
  '/vehicle-auctions', '/storage-auctions', '/broker-directory',
  '/auctions/', '/multi-item-auctions/', '/vehicles/', '/storage/',
  '/faq', '/how-it-works', '/about', '/about-us', '/contact',
  '/terms', '/legal/', '/privacy-policy',
];

function isPrerenderPath(path) {
  if (path.startsWith('/api/') || path.startsWith('/static/')) return false;
  if (/\.(js|css|png|jpe?g|webp|svg|ico|map|txt|xml|json)$/i.test(path)) return false;
  if (path === '/' || path === '') return true;
  return PRERENDER_PREFIXES.some(p =>
    p === '/' ? path === '/' : (path === p.replace(/\/$/, '') || path.startsWith(p))
  );
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const ua = request.headers.get('user-agent') || '';
    const forceSSR = url.searchParams.get('_ssr') === '1';

    // Only GETs, only prerender-eligible paths, only crawler UAs (or ?_ssr=1)
    if (
      request.method !== 'GET' ||
      !isPrerenderPath(url.pathname) ||
      !(forceSSR || BOT_UA_REGEX.test(ua))
    ) {
      return fetch(request);
    }

    // Rewrite → https://www.bidvex.com/api/prerender{path}?lang=...
    const lang = url.searchParams.get('lang') || (
      (request.headers.get('accept-language') || '').toLowerCase().startsWith('fr')
        ? 'fr' : 'en'
    );
    const prerenderUrl = new URL(
      `/api/prerender${url.pathname}${url.search || ''}`,
      'https://www.bidvex.com',
    );
    if (!prerenderUrl.searchParams.has('lang')) prerenderUrl.searchParams.set('lang', lang);

    const req = new Request(prerenderUrl.toString(), {
      method: 'GET',
      headers: request.headers,
    });
    const resp = await fetch(req);
    // Preserve the SSR headers (X-Prerender-Version, Cache-Control, etc.)
    return new Response(resp.body, {
      status: resp.status,
      headers: resp.headers,
    });
  },
};
```

## Rollback

If anything looks off, disable the trigger in **Workers & Pages → bidvex-bot-prerender → Triggers → Delete route**. All traffic (bots + real users) falls back to the SPA within seconds.

## Verification checklist after deploy

- [ ] `curl -A "Googlebot/2.1" https://www.bidvex.com/faq` returns valid HTML with `<title>`, meta description, JSON-LD.
- [ ] `curl -A "Mozilla/5.0" https://www.bidvex.com/faq` returns the same SPA shell as before (no X-Prerender-Version header).
- [ ] Google Search Console → **URL Inspection Tool → Test Live URL** on `https://www.bidvex.com/faq` shows the full FAQ page rendered.
- [ ] Facebook Sharing Debugger (`https://developers.facebook.com/tools/debug/`) on any auction URL shows the correct hero image + title.
- [ ] Rich Results Test (`https://search.google.com/test/rich-results`) validates Product + Event + BreadcrumbList + FAQPage.
