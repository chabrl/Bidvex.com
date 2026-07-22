/**
 * iter375 — Landing Page starter templates.
 *
 * Each template exports a preset that pre-fills the AdminLandingPageEditor
 * form. Templates use BidVex brand colours and bilingual EN/FR copy.
 *
 * Brand palette
 *   Navy  #0B2345 — primary headings / hero background
 *   Blue  #2B8FD0 — primary CTAs
 *   Teal  #3FB4CB — accents, gradients
 *   Green #22c55e — positive / success accents
 *
 * All class names are prefixed `lp-` so they don't collide with the
 * BidVex site chrome (header/footer) when those toggles are on.
 * FAQ accordions use native <details>/<summary> so no JS is required
 * (the backend also strips <script> tags from body HTML).
 */

/* ─── Shared CSS ─────────────────────────────────────────────────── */

const SHARED_CSS = `
/* BidVex Landing Page Template — resets & shared UI */
.lp-body { font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif; color: #0B2345; line-height: 1.6; }
.lp-body * { box-sizing: border-box; }
.lp-container { max-width: 1120px; margin: 0 auto; padding: 0 20px; }
.lp-section { padding: 72px 0; }
.lp-section-tight { padding: 48px 0; }
.lp-eyebrow { display: inline-block; padding: 6px 14px; border-radius: 999px; background: rgba(43,143,208,0.12); color: #2B8FD0; font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 16px; }
.lp-h1 { font-size: clamp(32px, 5vw, 56px); font-weight: 800; line-height: 1.1; margin: 0 0 20px; letter-spacing: -0.02em; }
.lp-h2 { font-size: clamp(26px, 3.4vw, 40px); font-weight: 800; margin: 0 0 12px; letter-spacing: -0.015em; }
.lp-h3 { font-size: 20px; font-weight: 700; margin: 0 0 8px; }
.lp-lead { font-size: 18px; color: #475569; margin: 0 0 24px; }
.lp-muted { color: #64748b; }
.lp-cta {
  display: inline-block; padding: 14px 26px; border-radius: 12px;
  background: linear-gradient(135deg, #2B8FD0 0%, #3FB4CB 100%);
  color: #fff !important; font-weight: 700; text-decoration: none; font-size: 16px;
  box-shadow: 0 10px 24px -12px rgba(43,143,208,0.55);
  transition: transform .18s ease, box-shadow .18s ease;
}
.lp-cta:hover { transform: translateY(-2px); box-shadow: 0 16px 30px -12px rgba(43,143,208,0.65); }
.lp-cta-ghost {
  display: inline-block; padding: 13px 24px; border-radius: 12px; border: 1.5px solid #cbd5e1;
  color: #0B2345 !important; font-weight: 700; text-decoration: none; font-size: 16px;
  background: #fff; transition: border-color .18s ease, background .18s ease;
}
.lp-cta-ghost:hover { border-color: #2B8FD0; background: #f1f8fd; }

/* Hero */
.lp-hero { position: relative; background: radial-gradient(1200px 500px at 10% -10%, rgba(63,180,203,0.28), transparent), radial-gradient(900px 500px at 90% 110%, rgba(43,143,208,0.25), transparent), #0B2345; color: #fff; padding: 96px 0 88px; overflow: hidden; }
.lp-hero .lp-eyebrow { background: rgba(255,255,255,0.15); color: #A9E4F0; }
.lp-hero .lp-h1 { color: #fff; }
.lp-hero .lp-lead { color: #cbd5e1; font-size: 20px; max-width: 680px; }
.lp-hero-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; }
.lp-hero .lp-cta-ghost { background: transparent; color: #fff !important; border-color: rgba(255,255,255,0.35); }
.lp-hero .lp-cta-ghost:hover { background: rgba(255,255,255,0.08); border-color: #fff; }
.lp-hero-badges { margin-top: 32px; display: flex; gap: 22px; flex-wrap: wrap; color: #94b4d0; font-size: 14px; }
.lp-hero-badges strong { color: #fff; }

/* Feature grid */
.lp-features { background: #f8fafc; }
.lp-grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-top: 40px; }
.lp-feature { background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 24px; transition: transform .2s ease, box-shadow .2s ease; }
.lp-feature:hover { transform: translateY(-4px); box-shadow: 0 20px 40px -18px rgba(11,35,69,0.18); }
.lp-feature-icon { width: 44px; height: 44px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; font-size: 22px; color: #fff; background: linear-gradient(135deg, #2B8FD0, #3FB4CB); margin-bottom: 14px; }

/* Steps (How it works) */
.lp-steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 24px; margin-top: 40px; }
.lp-step { position: relative; padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; }
.lp-step-num { position: absolute; top: -14px; left: 24px; background: #22c55e; color: #fff; width: 36px; height: 36px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; box-shadow: 0 8px 18px -6px rgba(34,197,94,0.5); }

/* Pricing */
.lp-pricing { background: #f8fafc; }
.lp-tiers { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 22px; margin-top: 40px; }
.lp-tier { background: #fff; border: 1px solid #e2e8f0; border-radius: 18px; padding: 28px; display: flex; flex-direction: column; }
.lp-tier.lp-tier-featured { border-color: #2B8FD0; box-shadow: 0 22px 44px -18px rgba(43,143,208,0.35); position: relative; }
.lp-tier-badge { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg,#2B8FD0,#3FB4CB); color: #fff; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; padding: 6px 14px; border-radius: 999px; font-weight: 700; }
.lp-tier-price { font-size: 40px; font-weight: 800; color: #0B2345; margin: 8px 0 4px; }
.lp-tier-price span { font-size: 15px; color: #64748b; font-weight: 500; }
.lp-tier ul { list-style: none; padding: 16px 0; margin: 0; flex: 1; }
.lp-tier li { padding: 8px 0 8px 26px; position: relative; color: #334155; font-size: 15px; }
.lp-tier li::before { content: '✓'; position: absolute; left: 0; top: 8px; color: #22c55e; font-weight: 800; }

/* FAQ */
.lp-faq details { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 22px; margin-bottom: 12px; transition: box-shadow .18s ease; }
.lp-faq details[open] { box-shadow: 0 10px 30px -14px rgba(11,35,69,0.15); border-color: #cfe4f4; }
.lp-faq summary { cursor: pointer; font-weight: 700; color: #0B2345; font-size: 17px; list-style: none; position: relative; padding-right: 28px; }
.lp-faq summary::-webkit-details-marker { display: none; }
.lp-faq summary::after { content: '+'; position: absolute; right: 0; top: -2px; font-size: 24px; color: #2B8FD0; font-weight: 400; transition: transform .18s ease; }
.lp-faq details[open] summary::after { content: '−'; }
.lp-faq p { margin: 12px 0 0; color: #475569; line-height: 1.7; }

/* Final CTA */
.lp-final { background: linear-gradient(135deg, #0B2345 0%, #123564 60%, #2B8FD0 100%); color: #fff; text-align: center; padding: 80px 20px; }
.lp-final .lp-h2 { color: #fff; }
.lp-final p { color: #cbd5e1; font-size: 18px; max-width: 620px; margin: 0 auto 28px; }
.lp-final .lp-cta { background: #22c55e; box-shadow: 0 12px 28px -10px rgba(34,197,94,0.5); }
.lp-final .lp-cta:hover { background: #16a34a; }

/* Text align helpers */
.lp-text-center { text-align: center; }
.lp-mt-6 { margin-top: 24px; }

@media (max-width: 640px) {
  .lp-section { padding: 56px 0; }
  .lp-hero { padding: 72px 0 64px; }
}
`;

/* ─── 1. Blank ────────────────────────────────────────────────────── */

const BLANK = {
  id: 'blank',
  name_en: 'Blank Page',
  name_fr: 'Page vierge',
  description_en: 'Start from scratch with an empty canvas.',
  description_fr: 'Partez de zéro avec un canevas vide.',
  icon: 'FileText',
  default_title_en: '',
  default_title_fr: '',
  default_meta_en: '',
  default_meta_fr: '',
  html_en: '',
  html_fr: '',
  css: '',
  js: '',
};

/* ─── 2. Seller Acquisition ─────────────────────────────────────── */

const SELLER_EN = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">For sellers</span>
      <h1 class="lp-h1">Turn assets into cash — <br/>run your auction on BidVex</h1>
      <p class="lp-lead">List surplus inventory, vehicles or equipment in minutes. Reach thousands of qualified buyers across Canada and get paid fast with escrow-backed settlement.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=seller">Start selling — it's free</a>
        <a class="lp-cta-ghost" href="/how-it-works">How it works</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>0%</strong> listing fees</span>
        <span><strong>7-day</strong> average sale</span>
        <span><strong>Escrow</strong> protected payouts</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Why sellers pick BidVex</span>
        <h2 class="lp-h2">Everything you need to run a professional auction</h2>
        <p class="lp-lead">Powerful tools — none of the complexity.</p>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">📸</div>
          <h3 class="lp-h3">Guided listing wizard</h3>
          <p class="lp-muted">Snap photos, describe your lot, set a reserve — publish in under 10 minutes.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🌐</div>
          <h3 class="lp-h3">National reach</h3>
          <p class="lp-muted">Your listing is featured in every province, in English &amp; French.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🛡️</div>
          <h3 class="lp-h3">Verified bidders</h3>
          <p class="lp-muted">KYC + payment pre-authorization keep tire-kickers away.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">💸</div>
          <h3 class="lp-h3">Fast Stripe payouts</h3>
          <p class="lp-muted">Funds land in your account within 2 business days of pickup.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📊</div>
          <h3 class="lp-h3">Live analytics</h3>
          <p class="lp-muted">Track views, watches, and bids in real time from your dashboard.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🤝</div>
          <h3 class="lp-h3">Dedicated support</h3>
          <p class="lp-muted">A real human is one click away — we help you close every deal.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">How it works</span>
        <h2 class="lp-h2">List &amp; sell in three steps</h2>
      </div>
      <div class="lp-steps">
        <div class="lp-step">
          <div class="lp-step-num">1</div>
          <h3 class="lp-h3">Create your listing</h3>
          <p class="lp-muted">Use our guided wizard — photos, description, reserve, buy-now.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">2</div>
          <h3 class="lp-h3">We promote it</h3>
          <p class="lp-muted">BidVex features your auction across search, newsletters and social ads.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">3</div>
          <h3 class="lp-h3">Get paid</h3>
          <p class="lp-muted">Buyer pays via escrow — we release funds after successful pickup.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section lp-pricing">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Simple pricing</span>
        <h2 class="lp-h2">Pay only when you sell</h2>
        <p class="lp-lead">No listing fees. No monthly minimums. No surprises.</p>
      </div>
      <div class="lp-tiers">
        <div class="lp-tier">
          <h3 class="lp-h3">Starter</h3>
          <div class="lp-tier-price">Free<span>&nbsp;/ list</span></div>
          <p class="lp-muted">Perfect for occasional sellers.</p>
          <ul>
            <li>Up to 5 active lots</li>
            <li>Standard placement</li>
            <li>5% success fee</li>
            <li>Email support</li>
          </ul>
          <a class="lp-cta-ghost" href="/auth?tab=signup&amp;role=seller">Start free</a>
        </div>
        <div class="lp-tier lp-tier-featured">
          <div class="lp-tier-badge">Most popular</div>
          <h3 class="lp-h3">Pro</h3>
          <div class="lp-tier-price">$29<span>&nbsp;/ month</span></div>
          <p class="lp-muted">For businesses selling monthly.</p>
          <ul>
            <li>Unlimited active lots</li>
            <li>Featured placement</li>
            <li>3% success fee</li>
            <li>Live chat support</li>
            <li>Custom seller storefront</li>
          </ul>
          <a class="lp-cta" href="/auth?tab=signup&amp;role=seller&amp;plan=pro">Try Pro free</a>
        </div>
        <div class="lp-tier">
          <h3 class="lp-h3">Enterprise</h3>
          <div class="lp-tier-price">Custom</div>
          <p class="lp-muted">Fleets, dealers, liquidators.</p>
          <ul>
            <li>Bulk upload &amp; API access</li>
            <li>Dedicated account manager</li>
            <li>Volume pricing</li>
            <li>SLAs &amp; white-label</li>
          </ul>
          <a class="lp-cta-ghost" href="/contact-sales">Talk to sales</a>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section lp-faq">
    <div class="lp-container" style="max-width: 780px;">
      <div class="lp-text-center">
        <span class="lp-eyebrow">FAQ</span>
        <h2 class="lp-h2">Questions, answered</h2>
      </div>
      <div class="lp-mt-6">
        <details>
          <summary>How much does it cost to list?</summary>
          <p>Listing is free on Starter and Pro plans. You only pay a success fee (3–5%) when your item sells. No hidden charges.</p>
        </details>
        <details>
          <summary>When do I get paid?</summary>
          <p>Funds are released from escrow within 2 business days of the buyer confirming pickup, and land in your Stripe-connected bank account.</p>
        </details>
        <details>
          <summary>What if a buyer doesn't pay?</summary>
          <p>Every bidder is pre-authorized before bidding. If a buyer defaults, we relist your item free of charge and pursue collection on your behalf.</p>
        </details>
        <details>
          <summary>Can I set a reserve price?</summary>
          <p>Yes. You can set a hidden reserve, a Buy-Now price, or both. If the reserve isn't met, you're never obligated to sell.</p>
        </details>
        <details>
          <summary>Do you help with shipping?</summary>
          <p>We offer optional pickup coordination and partner rates with national carriers for large items.</p>
        </details>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Ready to turn assets into cash?</h2>
      <p>Join thousands of Canadian sellers who have moved over $50M in assets on BidVex.</p>
      <a class="lp-cta" href="/auth?tab=signup&amp;role=seller">Create my free seller account</a>
    </div>
  </section>
</div>`;

const SELLER_FR = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">Pour les vendeurs</span>
      <h1 class="lp-h1">Transformez vos actifs en liquidités — <br/>vendez aux enchères sur BidVex</h1>
      <p class="lp-lead">Mettez en vente stocks excédentaires, véhicules ou équipement en quelques minutes. Atteignez des milliers d'acheteurs qualifiés partout au Canada et soyez payé rapidement grâce à notre entiercement.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=seller">Commencer à vendre — c'est gratuit</a>
        <a class="lp-cta-ghost" href="/how-it-works">Comment ça marche</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>0 %</strong> de frais d'inscription</span>
        <span><strong>7 jours</strong> pour vendre en moyenne</span>
        <span><strong>Paiements</strong> protégés par entiercement</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Pourquoi choisir BidVex</span>
        <h2 class="lp-h2">Tout ce qu'il vous faut pour une enchère professionnelle</h2>
        <p class="lp-lead">Des outils puissants — sans la complexité.</p>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">📸</div>
          <h3 class="lp-h3">Assistant de création</h3>
          <p class="lp-muted">Photos, description, prix de réserve — publiez en moins de 10 minutes.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🌐</div>
          <h3 class="lp-h3">Portée nationale</h3>
          <p class="lp-muted">Votre annonce est diffusée dans chaque province, en français et en anglais.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🛡️</div>
          <h3 class="lp-h3">Acheteurs vérifiés</h3>
          <p class="lp-muted">Vérification KYC et pré-autorisation de paiement pour éloigner les curieux.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">💸</div>
          <h3 class="lp-h3">Paiements Stripe rapides</h3>
          <p class="lp-muted">Les fonds arrivent dans votre compte dans les 2 jours ouvrables après la cueillette.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📊</div>
          <h3 class="lp-h3">Analytiques en direct</h3>
          <p class="lp-muted">Suivez vues, favoris et enchères en temps réel depuis votre tableau de bord.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🤝</div>
          <h3 class="lp-h3">Soutien dédié</h3>
          <p class="lp-muted">Un vrai humain à un clic — nous vous aidons à conclure chaque vente.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Comment ça marche</span>
        <h2 class="lp-h2">Publier et vendre en trois étapes</h2>
      </div>
      <div class="lp-steps">
        <div class="lp-step">
          <div class="lp-step-num">1</div>
          <h3 class="lp-h3">Créez votre annonce</h3>
          <p class="lp-muted">Notre assistant vous guide : photos, description, réserve, achat immédiat.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">2</div>
          <h3 class="lp-h3">Nous en faisons la promotion</h3>
          <p class="lp-muted">BidVex met votre enchère en avant : recherche, infolettres et publicité sociale.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">3</div>
          <h3 class="lp-h3">Soyez payé</h3>
          <p class="lp-muted">L'acheteur paie via entiercement — nous libérons les fonds après la cueillette.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section lp-pricing">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Tarification simple</span>
        <h2 class="lp-h2">Vous ne payez que si vous vendez</h2>
        <p class="lp-lead">Aucuns frais d'inscription. Aucun minimum mensuel. Aucune surprise.</p>
      </div>
      <div class="lp-tiers">
        <div class="lp-tier">
          <h3 class="lp-h3">Débutant</h3>
          <div class="lp-tier-price">Gratuit<span>&nbsp;/ annonce</span></div>
          <p class="lp-muted">Idéal pour les vendeurs occasionnels.</p>
          <ul>
            <li>Jusqu'à 5 lots actifs</li>
            <li>Placement standard</li>
            <li>5 % de frais de succès</li>
            <li>Soutien par courriel</li>
          </ul>
          <a class="lp-cta-ghost" href="/auth?tab=signup&amp;role=seller">Commencer gratuitement</a>
        </div>
        <div class="lp-tier lp-tier-featured">
          <div class="lp-tier-badge">Le plus populaire</div>
          <h3 class="lp-h3">Pro</h3>
          <div class="lp-tier-price">29 $<span>&nbsp;/ mois</span></div>
          <p class="lp-muted">Pour les entreprises qui vendent chaque mois.</p>
          <ul>
            <li>Lots actifs illimités</li>
            <li>Placement vedette</li>
            <li>3 % de frais de succès</li>
            <li>Clavardage en direct</li>
            <li>Vitrine vendeur personnalisée</li>
          </ul>
          <a class="lp-cta" href="/auth?tab=signup&amp;role=seller&amp;plan=pro">Essayer Pro gratuitement</a>
        </div>
        <div class="lp-tier">
          <h3 class="lp-h3">Entreprise</h3>
          <div class="lp-tier-price">Sur mesure</div>
          <p class="lp-muted">Flottes, concessionnaires, liquidateurs.</p>
          <ul>
            <li>Téléversement en lot &amp; API</li>
            <li>Gestionnaire de compte dédié</li>
            <li>Tarifs préférentiels</li>
            <li>SLA et marque blanche</li>
          </ul>
          <a class="lp-cta-ghost" href="/contact-sales">Parler aux ventes</a>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section lp-faq">
    <div class="lp-container" style="max-width: 780px;">
      <div class="lp-text-center">
        <span class="lp-eyebrow">FAQ</span>
        <h2 class="lp-h2">Vos questions, nos réponses</h2>
      </div>
      <div class="lp-mt-6">
        <details>
          <summary>Combien coûte une annonce ?</summary>
          <p>L'inscription est gratuite avec les forfaits Débutant et Pro. Vous ne payez qu'une commission de succès (3 à 5 %) lorsque votre article est vendu. Aucuns frais cachés.</p>
        </details>
        <details>
          <summary>Quand suis-je payé ?</summary>
          <p>Les fonds sont libérés de l'entiercement dans les 2 jours ouvrables suivant la confirmation de la cueillette par l'acheteur, directement dans votre compte bancaire connecté à Stripe.</p>
        </details>
        <details>
          <summary>Et si un acheteur ne paie pas ?</summary>
          <p>Chaque enchérisseur est pré-autorisé avant d'enchérir. Si un acheteur fait défaut, nous republions votre article gratuitement et effectuons le recouvrement en votre nom.</p>
        </details>
        <details>
          <summary>Puis-je fixer un prix de réserve ?</summary>
          <p>Oui. Vous pouvez définir une réserve cachée, un prix d'achat immédiat, ou les deux. Si la réserve n'est pas atteinte, vous n'êtes jamais obligé de vendre.</p>
        </details>
        <details>
          <summary>Offrez-vous de l'aide pour l'expédition ?</summary>
          <p>Nous offrons la coordination de cueillette et des tarifs préférentiels auprès de transporteurs nationaux pour les articles volumineux.</p>
        </details>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Prêt à transformer vos actifs en liquidités ?</h2>
      <p>Rejoignez des milliers de vendeurs canadiens qui ont écoulé plus de 50 M$ d'actifs sur BidVex.</p>
      <a class="lp-cta" href="/auth?tab=signup&amp;role=seller">Créer mon compte vendeur gratuit</a>
    </div>
  </section>
</div>`;

const SELLER = {
  id: 'seller-acquisition',
  name_en: 'Seller Acquisition',
  name_fr: 'Acquisition de vendeurs',
  description_en: 'Hero → features → how-it-works → pricing → FAQ → final CTA. Optimised for seller sign-ups.',
  description_fr: 'Héros → fonctionnalités → étapes → tarifs → FAQ → appel à l\'action. Optimisé pour les inscriptions vendeurs.',
  icon: 'Store',
  default_title_en: 'Sell on BidVex — Turn Assets Into Cash | Canada Auction Marketplace',
  default_title_fr: 'Vendre sur BidVex — Transformez vos actifs en liquidités | Enchères Canada',
  default_meta_en: 'List surplus inventory, vehicles or equipment on BidVex. 0% listing fees, escrow-protected payouts, and thousands of verified Canadian buyers.',
  default_meta_fr: 'Vendez stocks, véhicules ou équipement sur BidVex. 0 % de frais d\'inscription, paiements protégés et des milliers d\'acheteurs canadiens vérifiés.',
  html_en: SELLER_EN,
  html_fr: SELLER_FR,
  css: SHARED_CSS,
  js: '',
};

/* ─── 3. Buyer Acquisition ──────────────────────────────────────── */

const BUYER_EN = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">For buyers</span>
      <h1 class="lp-h1">Live auctions on cars, equipment &amp; surplus inventory</h1>
      <p class="lp-lead">Bid on thousands of verified Canadian listings — with escrow protection, transparent fees, and instant notifications.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=buyer">Create free account</a>
        <a class="lp-cta-ghost" href="/browse">Browse live auctions</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>30k+</strong> active bidders</span>
        <span><strong>Escrow</strong> protected purchases</span>
        <span><strong>EN / FR</strong> support</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Why bid on BidVex</span>
        <h2 class="lp-h2">A marketplace built for smart buyers</h2>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">🎯</div>
          <h3 class="lp-h3">Auto-bidding</h3>
          <p class="lp-muted">Set your max — we bid in your name up to that limit.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🔎</div>
          <h3 class="lp-h3">Smart search</h3>
          <p class="lp-muted">Filters by make, model, year, mileage, condition and location.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🛡️</div>
          <h3 class="lp-h3">Buyer protection</h3>
          <p class="lp-muted">Funds are held in escrow until you confirm the item as described.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🔔</div>
          <h3 class="lp-h3">Instant alerts</h3>
          <p class="lp-muted">Push + email notifications the moment you're outbid.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">💳</div>
          <h3 class="lp-h3">Flexible payment</h3>
          <p class="lp-muted">Card, ACH, or wire. Financing available on qualifying lots.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🇨🇦</div>
          <h3 class="lp-h3">Nationwide inventory</h3>
          <p class="lp-muted">Listings in every province, updated hour by hour.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Find your next deal today</h2>
      <p>Browse live auctions and place your first bid in under 60 seconds.</p>
      <a class="lp-cta" href="/browse">Browse live auctions</a>
    </div>
  </section>
</div>`;

const BUYER_FR = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">Pour les acheteurs</span>
      <h1 class="lp-h1">Enchères en direct sur voitures, équipement et stocks excédentaires</h1>
      <p class="lp-lead">Enchérissez sur des milliers d'annonces canadiennes vérifiées — avec entiercement, frais transparents et notifications instantanées.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=buyer">Créer un compte gratuit</a>
        <a class="lp-cta-ghost" href="/browse">Voir les enchères en direct</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>30 000+</strong> enchérisseurs actifs</span>
        <span><strong>Entiercement</strong> sur chaque achat</span>
        <span><strong>Soutien</strong> EN / FR</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Pourquoi enchérir sur BidVex</span>
        <h2 class="lp-h2">Un marché conçu pour les acheteurs avisés</h2>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">🎯</div>
          <h3 class="lp-h3">Enchère automatique</h3>
          <p class="lp-muted">Fixez votre maximum — nous enchérissons en votre nom jusqu'à cette limite.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🔎</div>
          <h3 class="lp-h3">Recherche intelligente</h3>
          <p class="lp-muted">Filtres par marque, modèle, année, kilométrage, état et localisation.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🛡️</div>
          <h3 class="lp-h3">Protection acheteur</h3>
          <p class="lp-muted">Vos fonds sont en entiercement jusqu'à ce que l'article soit confirmé conforme.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🔔</div>
          <h3 class="lp-h3">Alertes instantanées</h3>
          <p class="lp-muted">Notifications push et courriel dès que vous êtes surenchéri.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">💳</div>
          <h3 class="lp-h3">Paiement flexible</h3>
          <p class="lp-muted">Carte, ACH ou virement. Financement disponible sur lots éligibles.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🇨🇦</div>
          <h3 class="lp-h3">Inventaire pancanadien</h3>
          <p class="lp-muted">Annonces dans chaque province, mises à jour chaque heure.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Trouvez votre prochaine aubaine</h2>
      <p>Parcourez les enchères en direct et placez votre première mise en moins de 60 secondes.</p>
      <a class="lp-cta" href="/browse">Voir les enchères en direct</a>
    </div>
  </section>
</div>`;

const BUYER = {
  id: 'buyer-acquisition',
  name_en: 'Buyer Acquisition',
  name_fr: 'Acquisition d\'acheteurs',
  description_en: 'Hero + feature grid + CTA. Optimised for bidder sign-ups.',
  description_fr: 'Héros + grille de fonctionnalités + CTA. Optimisé pour les inscriptions d\'acheteurs.',
  icon: 'ShoppingCart',
  default_title_en: 'Bid on BidVex — Cars, Equipment &amp; Surplus Auctions | Canada',
  default_title_fr: 'Enchérir sur BidVex — Voitures, équipement, stocks | Canada',
  default_meta_en: 'Live auctions on 10,000+ verified Canadian lots. Escrow-protected, EN/FR support, and smart auto-bidding.',
  default_meta_fr: 'Enchères en direct sur 10 000+ lots canadiens vérifiés. Entiercement, soutien FR/EN et enchère automatique.',
  html_en: BUYER_EN,
  html_fr: BUYER_FR,
  css: SHARED_CSS,
  js: '',
};

/* ─── 4. Affiliate Program ──────────────────────────────────────── */

const AFFILIATE_EN = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">Partner program</span>
      <h1 class="lp-h1">Earn recurring revenue with the BidVex Affiliate Program</h1>
      <p class="lp-lead">Refer sellers and buyers to Canada's fastest-growing auction marketplace. Get paid a percentage of every commission — for the lifetime of the account.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=affiliate">Apply now</a>
        <a class="lp-cta-ghost" href="#faq">Learn more</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>10-20%</strong> commission share</span>
        <span><strong>Lifetime</strong> tracking</span>
        <span><strong>Monthly</strong> Stripe payouts</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Why partner with BidVex</span>
        <h2 class="lp-h2">Built for creators, agencies and industry pros</h2>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">💰</div>
          <h3 class="lp-h3">Generous commissions</h3>
          <p class="lp-muted">10% on buyer premiums, 20% on Pro seller subscriptions — for life.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📈</div>
          <h3 class="lp-h3">Live dashboard</h3>
          <p class="lp-muted">Track clicks, sign-ups and earnings in real time.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🎨</div>
          <h3 class="lp-h3">Creative kit</h3>
          <p class="lp-muted">Ready-made banners, copy blocks and video assets in EN &amp; FR.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section" id="faq">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">How it works</span>
        <h2 class="lp-h2">Three steps to your first payout</h2>
      </div>
      <div class="lp-steps">
        <div class="lp-step">
          <div class="lp-step-num">1</div>
          <h3 class="lp-h3">Apply &amp; get approved</h3>
          <p class="lp-muted">We review applications within 48 hours.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">2</div>
          <h3 class="lp-h3">Share your link</h3>
          <p class="lp-muted">Every click is attributed to you for 90 days across devices.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">3</div>
          <h3 class="lp-h3">Get paid monthly</h3>
          <p class="lp-muted">Payouts land in your Stripe account on the 1st of each month.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Ready to earn with BidVex?</h2>
      <p>Join hundreds of Canadian partners already earning recurring commissions.</p>
      <a class="lp-cta" href="/auth?tab=signup&amp;role=affiliate">Apply to the program</a>
    </div>
  </section>
</div>`;

const AFFILIATE_FR = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">Programme partenaire</span>
      <h1 class="lp-h1">Gagnez un revenu récurrent avec le Programme d'affiliation BidVex</h1>
      <p class="lp-lead">Recommandez vendeurs et acheteurs au marché d'enchères qui croît le plus vite au Canada. Recevez un pourcentage de chaque commission — à vie.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=affiliate">Postuler maintenant</a>
        <a class="lp-cta-ghost" href="#faq">En savoir plus</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>10 à 20 %</strong> de partage de commission</span>
        <span><strong>Suivi</strong> à vie</span>
        <span><strong>Paiements</strong> Stripe mensuels</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Pourquoi devenir partenaire</span>
        <h2 class="lp-h2">Conçu pour créateurs, agences et pros du secteur</h2>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">💰</div>
          <h3 class="lp-h3">Commissions généreuses</h3>
          <p class="lp-muted">10 % sur les primes acheteur, 20 % sur les abonnements Pro — à vie.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📈</div>
          <h3 class="lp-h3">Tableau de bord en direct</h3>
          <p class="lp-muted">Suivez clics, inscriptions et gains en temps réel.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🎨</div>
          <h3 class="lp-h3">Kit créatif</h3>
          <p class="lp-muted">Bannières, textes et vidéos prêts à l'emploi en français et en anglais.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section" id="faq">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Fonctionnement</span>
        <h2 class="lp-h2">Trois étapes vers votre premier paiement</h2>
      </div>
      <div class="lp-steps">
        <div class="lp-step">
          <div class="lp-step-num">1</div>
          <h3 class="lp-h3">Postulez et soyez approuvé</h3>
          <p class="lp-muted">Nous examinons les candidatures en moins de 48 heures.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">2</div>
          <h3 class="lp-h3">Partagez votre lien</h3>
          <p class="lp-muted">Chaque clic vous est attribué pendant 90 jours, tous appareils confondus.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">3</div>
          <h3 class="lp-h3">Soyez payé chaque mois</h3>
          <p class="lp-muted">Paiement Stripe le 1er de chaque mois.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Prêt à gagner avec BidVex ?</h2>
      <p>Rejoignez des centaines de partenaires canadiens qui touchent déjà des commissions récurrentes.</p>
      <a class="lp-cta" href="/auth?tab=signup&amp;role=affiliate">Postuler au programme</a>
    </div>
  </section>
</div>`;

const AFFILIATE = {
  id: 'affiliate-program',
  name_en: 'Affiliate Program',
  name_fr: 'Programme d\'affiliation',
  description_en: 'Recruit new affiliate partners with commission highlights and 3-step onboarding.',
  description_fr: 'Recrutez de nouveaux partenaires affiliés — commissions et parcours en 3 étapes.',
  icon: 'Handshake',
  default_title_en: 'BidVex Affiliate Program — Earn Recurring Commission',
  default_title_fr: 'Programme d\'affiliation BidVex — Gagnez des commissions récurrentes',
  default_meta_en: 'Refer sellers &amp; buyers to Canada\'s auction marketplace and earn up to 20% lifetime commission. Apply today.',
  default_meta_fr: 'Recommandez vendeurs et acheteurs au marché d\'enchères canadien et gagnez jusqu\'à 20 % de commission à vie.',
  html_en: AFFILIATE_EN,
  html_fr: AFFILIATE_FR,
  css: SHARED_CSS,
  js: '',
};

/* ─── 5. Vehicle Dealer ─────────────────────────────────────────── */

const DEALER_EN = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">For vehicle dealers</span>
      <h1 class="lp-h1">Move inventory 3× faster with wholesale &amp; retail auctions</h1>
      <p class="lp-lead">The Canadian dealer platform for trade-ins, off-lease returns and aged inventory. Bulk upload, VIN decode and instant national exposure.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=dealer">Get dealer access</a>
        <a class="lp-cta-ghost" href="/contact-sales">Book a demo</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>500+</strong> licensed dealers</span>
        <span><strong>VIN</strong> auto-decode</span>
        <span><strong>Bulk</strong> CSV upload</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Dealer toolkit</span>
        <h2 class="lp-h2">Built for busy dealership floors</h2>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">🚗</div>
          <h3 class="lp-h3">VIN decoder</h3>
          <p class="lp-muted">Auto-populate specs, options and photos from a single VIN.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📤</div>
          <h3 class="lp-h3">Bulk upload</h3>
          <p class="lp-muted">Import 100+ vehicles via CSV or dealer DMS integration.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🎯</div>
          <h3 class="lp-h3">Reserve &amp; buy-now</h3>
          <p class="lp-muted">Full control over sale price, reserves and instant purchase.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🇨🇦</div>
          <h3 class="lp-h3">National reach</h3>
          <p class="lp-muted">Exposure to dealers, wholesalers and retail buyers coast to coast.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📄</div>
          <h3 class="lp-h3">Trade documents</h3>
          <p class="lp-muted">Bill of sale, transport releases and title transfer generated automatically.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">💬</div>
          <h3 class="lp-h3">Dealer support</h3>
          <p class="lp-muted">Dedicated account manager — 7 days a week.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Cut days off your average time-to-sell</h2>
      <p>Join hundreds of Canadian dealerships moving inventory on BidVex every week.</p>
      <a class="lp-cta" href="/contact-sales">Book a dealer demo</a>
    </div>
  </section>
</div>`;

const DEALER_FR = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">Pour les concessionnaires</span>
      <h1 class="lp-h1">Écoulez votre inventaire 3× plus vite avec les enchères de gros et détail</h1>
      <p class="lp-lead">La plateforme canadienne pour reprises, retours de location et véhicules âgés. Téléversement en lot, décodage VIN et visibilité nationale instantanée.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=dealer">Obtenir un accès concessionnaire</a>
        <a class="lp-cta-ghost" href="/contact-sales">Réserver une démo</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>500+</strong> concessionnaires agréés</span>
        <span><strong>VIN</strong> décodé automatiquement</span>
        <span><strong>CSV</strong> en lot</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Boîte à outils</span>
        <h2 class="lp-h2">Conçu pour les concessions occupées</h2>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">🚗</div>
          <h3 class="lp-h3">Décodeur VIN</h3>
          <p class="lp-muted">Spécifications, options et photos remplies automatiquement à partir d'un seul VIN.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📤</div>
          <h3 class="lp-h3">Téléversement en lot</h3>
          <p class="lp-muted">Importez 100+ véhicules via CSV ou intégration DMS.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🎯</div>
          <h3 class="lp-h3">Réserve et achat immédiat</h3>
          <p class="lp-muted">Contrôle total sur le prix, les réserves et l'achat instantané.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🇨🇦</div>
          <h3 class="lp-h3">Portée nationale</h3>
          <p class="lp-muted">Visibilité auprès des concessionnaires, grossistes et particuliers d'un océan à l'autre.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📄</div>
          <h3 class="lp-h3">Documents de vente</h3>
          <p class="lp-muted">Contrat de vente, cession et transfert de titre générés automatiquement.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">💬</div>
          <h3 class="lp-h3">Soutien concessionnaire</h3>
          <p class="lp-muted">Gestionnaire dédié — 7 jours sur 7.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Réduisez vos délais moyens de vente</h2>
      <p>Rejoignez des centaines de concessions canadiennes qui écoulent leur inventaire sur BidVex chaque semaine.</p>
      <a class="lp-cta" href="/contact-sales">Réserver une démo</a>
    </div>
  </section>
</div>`;

const DEALER = {
  id: 'vehicle-dealer',
  name_en: 'Vehicle Dealer',
  name_fr: 'Concessionnaire',
  description_en: 'Dealer-focused hero, VIN/CSV toolkit grid, and demo CTA.',
  description_fr: 'Héros pour concessionnaires, grille d\'outils VIN/CSV et CTA de démo.',
  icon: 'Car',
  default_title_en: 'BidVex for Vehicle Dealers — Wholesale &amp; Retail Auctions in Canada',
  default_title_fr: 'BidVex pour concessionnaires — Enchères de gros et de détail au Canada',
  default_meta_en: 'Move inventory 3× faster with VIN auto-decode, bulk CSV upload and national auction exposure.',
  default_meta_fr: 'Écoulez votre inventaire 3× plus vite avec décodage VIN automatique et téléversement en lot.',
  html_en: DEALER_EN,
  html_fr: DEALER_FR,
  css: SHARED_CSS,
  js: '',
};

/* ─── 6. Storage Facility ───────────────────────────────────────── */

const STORAGE_EN = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">For storage facilities</span>
      <h1 class="lp-h1">Recover unpaid unit balances with compliant lien auctions</h1>
      <p class="lp-lead">Run legally-compliant self-storage unit auctions across Canada. Automated bidder KYC, notice generation, and same-day settlement.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=storage">Get facility access</a>
        <a class="lp-cta-ghost" href="/contact-sales">Talk to sales</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>Provincial</strong> lien compliance</span>
        <span><strong>Automated</strong> notices</span>
        <span><strong>Same-day</strong> pickup</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Facility toolkit</span>
        <h2 class="lp-h2">Purpose-built for self-storage operators</h2>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">📜</div>
          <h3 class="lp-h3">Compliance-first</h3>
          <p class="lp-muted">Automated notices tailored to each province's Repair &amp; Storage Liens Act.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📸</div>
          <h3 class="lp-h3">Guided unit listing</h3>
          <p class="lp-muted">Photograph, tag, and publish a unit in under 5 minutes.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🕒</div>
          <h3 class="lp-h3">Same-day pickup</h3>
          <p class="lp-muted">Winner pays &amp; retrieves the unit within 24 hours — you're paid before they leave.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">How it works</span>
        <h2 class="lp-h2">From delinquent to sold in 3 steps</h2>
      </div>
      <div class="lp-steps">
        <div class="lp-step">
          <div class="lp-step-num">1</div>
          <h3 class="lp-h3">Flag the unit</h3>
          <p class="lp-muted">Tag delinquent tenants — BidVex generates the required legal notices.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">2</div>
          <h3 class="lp-h3">Publish the auction</h3>
          <p class="lp-muted">Photos, description, and pickup window auto-scheduled.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">3</div>
          <h3 class="lp-h3">Recover funds</h3>
          <p class="lp-muted">Buyer pays, picks up, and we remit funds to your account instantly.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Turn delinquent units into recovered revenue</h2>
      <p>Trusted by 200+ self-storage facilities in Canada.</p>
      <a class="lp-cta" href="/contact-sales">Book a facility demo</a>
    </div>
  </section>
</div>`;

const STORAGE_FR = `<div class="lp-body">
  <section class="lp-hero">
    <div class="lp-container">
      <span class="lp-eyebrow">Pour les entrepôts</span>
      <h1 class="lp-h1">Recouvrez les soldes impayés avec des enchères de saisie conformes</h1>
      <p class="lp-lead">Organisez des enchères d'unités d'entreposage libre-service conformes partout au Canada. Vérification KYC automatisée, avis légaux et règlement le jour même.</p>
      <div class="lp-hero-actions">
        <a class="lp-cta" href="/auth?tab=signup&amp;role=storage">Accès entrepôt</a>
        <a class="lp-cta-ghost" href="/contact-sales">Parler aux ventes</a>
      </div>
      <div class="lp-hero-badges">
        <span><strong>Conformité</strong> provinciale</span>
        <span><strong>Avis</strong> automatisés</span>
        <span><strong>Cueillette</strong> le jour même</span>
      </div>
    </div>
  </section>

  <section class="lp-section lp-features">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Boîte à outils</span>
        <h2 class="lp-h2">Conçu pour les opérateurs d'entreposage</h2>
      </div>
      <div class="lp-grid-3">
        <div class="lp-feature">
          <div class="lp-feature-icon">📜</div>
          <h3 class="lp-h3">Conformité d'abord</h3>
          <p class="lp-muted">Avis automatisés selon la loi provinciale sur les privilèges d'entreposage.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">📸</div>
          <h3 class="lp-h3">Publication guidée</h3>
          <p class="lp-muted">Photographiez, étiquetez et publiez une unité en moins de 5 minutes.</p>
        </div>
        <div class="lp-feature">
          <div class="lp-feature-icon">🕒</div>
          <h3 class="lp-h3">Cueillette le jour même</h3>
          <p class="lp-muted">Le gagnant paie et récupère l'unité en 24 h — vous êtes payé avant son départ.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-section">
    <div class="lp-container">
      <div class="lp-text-center">
        <span class="lp-eyebrow">Fonctionnement</span>
        <h2 class="lp-h2">De délinquant à vendu en 3 étapes</h2>
      </div>
      <div class="lp-steps">
        <div class="lp-step">
          <div class="lp-step-num">1</div>
          <h3 class="lp-h3">Signalez l'unité</h3>
          <p class="lp-muted">Marquez les locataires en défaut — BidVex génère les avis légaux requis.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">2</div>
          <h3 class="lp-h3">Publiez l'enchère</h3>
          <p class="lp-muted">Photos, description et fenêtre de cueillette planifiées automatiquement.</p>
        </div>
        <div class="lp-step">
          <div class="lp-step-num">3</div>
          <h3 class="lp-h3">Récupérez les fonds</h3>
          <p class="lp-muted">L'acheteur paie, ramasse, et les fonds sont versés à votre compte immédiatement.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="lp-final">
    <div class="lp-container">
      <h2 class="lp-h2">Transformez les unités impayées en revenu recouvré</h2>
      <p>La solution de confiance de 200+ entrepôts libre-service au Canada.</p>
      <a class="lp-cta" href="/contact-sales">Réserver une démo</a>
    </div>
  </section>
</div>`;

const STORAGE = {
  id: 'storage-facility',
  name_en: 'Storage Facility',
  name_fr: 'Entreposage libre-service',
  description_en: 'Lien-auction landing page for self-storage operators.',
  description_fr: 'Page pour les enchères d\'unités d\'entreposage.',
  icon: 'Warehouse',
  default_title_en: 'BidVex for Storage Facilities — Compliant Lien Auctions in Canada',
  default_title_fr: 'BidVex pour entrepôts libre-service — Enchères de saisie conformes',
  default_meta_en: 'Recover delinquent unit balances with compliant online lien auctions. Automated notices, same-day pickup, and instant settlement.',
  default_meta_fr: 'Recouvrez les soldes impayés avec des enchères de saisie conformes. Avis automatisés et règlement immédiat.',
  html_en: STORAGE_EN,
  html_fr: STORAGE_FR,
  css: SHARED_CSS,
  js: '',
};

/* ─── Exports ───────────────────────────────────────────────────── */

export const LANDING_PAGE_TEMPLATES = [BLANK, SELLER, BUYER, AFFILIATE, DEALER, STORAGE];

export function getTemplate(id) {
  return LANDING_PAGE_TEMPLATES.find((t) => t.id === id) || BLANK;
}
