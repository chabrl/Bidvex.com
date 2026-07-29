"""
iter358 — Quebec Launch Press Release copy + JSON-LD (NewsArticle).

Ships bilingual (EN/FR) press-release pages:
    • /press/quebec-launch          (English)
    • /presse/lancement-quebec      (French)

Each page carries:
    • NewsArticle JSON-LD (headline, datePublished, author, publisher, image)
    • Reciprocal hreflang cross-references
    • Downloadable PDF fiche produit
    • Full prerendered SSR for crawlers

datePublished is FIXED to 2026-07-17 per user directive — the actual public
launch date. Do NOT parameterize this; it needs to match the JSON-LD claim
that Google indexes.
"""
from __future__ import annotations

from typing import Any, Dict

# Fixed launch date — do NOT change without coordinating with SEO ops.
# Google penalizes NewsArticle whose datePublished doesn't match a stable
# on-page publication timestamp.
PRESS_RELEASE_DATE_PUBLISHED = "2026-07-17"

# Canonical PDF asset URL (served from frontend/public/static/press/).
PRESS_RELEASE_PDF_URL = "/static/press/bidvex-quebec-launch.pdf"

# Founder attribution — verified with Charbel Lichaa's business card
# and existing platform materials (BidVex Inc. corporation number
# 1175252826 filed under Charbel Lichaa, Founder & CEO).
FOUNDER_NAME = "Charbel Lichaa"
FOUNDER_TITLE_EN = "Founder & CEO"
FOUNDER_TITLE_FR = "Fondateur et PDG"


def press_release_paths() -> Dict[str, str]:
    """EN slug ↔ FR slug pair."""
    return {
        "en": "/press/quebec-launch",
        "fr": "/presse/lancement-quebec",
    }


# ─── EN Copy ──────────────────────────────────────────────────────────
EN_TITLE = "BidVex Officially Launches in Quebec — Canada's Bilingual Auction Marketplace"
EN_META  = (
    "BidVex Inc. announces the official launch of Canada's first fully "
    "bilingual online auction marketplace in Quebec. Vehicle, storage, "
    "marketplace and lot auctions across 10 provinces at a 2.5% platform fee."
)

EN_BODY_HTML = """
<p class="lead" style="font-size:18px;color:#0B2545;font-weight:600;line-height:1.5;">
FOR IMMEDIATE RELEASE — Sherbrooke, Québec — July 17, 2026
</p>

<p>
<strong>BidVex Inc.</strong>, a Sherbrooke-based technology company, is officially launching
<strong>Canada's first fully bilingual online auction marketplace</strong>. Effective today,
the platform is open to buyers and sellers in all 10 Canadian provinces, with a special
focus on Quebec — home to BidVex's headquarters and founding team.
</p>

<p>
The platform operates <strong>four distinct auction verticals</strong> under a single
account: a general marketplace (consumer and business goods), a lots and liquidation
channel (bulk industrial and business inventory), a licensed vehicle auction (SAAQ,
OMVIC, AMVIC and VSA verified dealers), and a storage locker auction (verified facilities
across Canada).
</p>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">A 2.5% Platform Fee — Not 10 to 15%</h2>

<p>
Where traditional auction houses charge sellers commissions of 10% to 15%, BidVex has
locked in a <strong>2.5% platform fee</strong> across all four verticals. The fee is
transparent and fully disclosed at listing time — no hidden buyer's premium surprises
at settlement.
</p>

<blockquote style="border-left:4px solid #2B8FD0;padding:16px 20px;margin:24px 0;
                   background:#F0F9FF;color:#0C4A6E;font-style:italic;">
"For too long, Canadian buyers and sellers have been paying inflated fees to auction
intermediaries built on infrastructure from the 1980s. BidVex is a Canadian-owned,
bilingual, technology-first platform. We built it here in Sherbrooke — for Quebec first,
for all of Canada next. Our 2.5% platform fee isn't a launch promotion — it's our
permanent business model."
<br><br>
— <strong>Charbel Lichaa</strong>, Founder &amp; CEO, BidVex Inc.
</blockquote>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">Built for Quebec — and for All of Canada</h2>

<p>
BidVex is fully bilingual French/English at every layer — user interface, invoices, legal
documentation, customer support, and email communications — in full compliance with
<strong>Bill 96</strong> (Loi 96). The company is registered federally as BidVex Inc.
(Corporation Number 1175252826) and operates a Canadian data infrastructure compliant
with PIPEDA and Law 25.
</p>

<p>
Vehicle listings are restricted to province-licensed dealers, verified through the
appropriate provincial authorities: SAAQ (Quebec), OMVIC (Ontario), AMVIC (Alberta),
VSA (British Columbia), and equivalent bodies for other provinces. Winning bidders are
required to complete a one-time <strong>Stripe Identity KYC verification</strong>
before finalizing purchase.
</p>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">Technology Highlights</h2>
<ul style="line-height:1.9;">
    <li><strong>AI-powered fraud detection</strong> — every listing scanned before publication</li>
    <li><strong>Soft-close anti-snipe protection</strong> — bids in the final 60 seconds extend the timer</li>
    <li><strong>Stripe escrow for non-vehicle items</strong> — funds released only on confirmed pickup</li>
    <li><strong>Broker-direct payment for vehicles</strong> — hammer price settled off-platform, fully compliant with provincial dealer laws</li>
    <li><strong>Real-time bidding via WebSocket</strong> — sub-100ms latency for a snappy live-auction feel</li>
    <li><strong>Bilingual customer support</strong> — French and English, phone and email</li>
</ul>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">Launch Offer — SUMMER2026</h2>

<p>
To celebrate the Quebec launch, BidVex is offering all new sellers <strong>one month
of Premium listing features free of charge</strong> with promo code <strong>SUMMER2026</strong>.
The offer is valid through <strong>August 31, 2026</strong>.
</p>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">About BidVex Inc.</h2>

<p>
BidVex Inc. is a Canadian-owned technology company headquartered in Sherbrooke, Quebec.
Founded by Charbel Lichaa, the company operates Canada's first fully bilingual online
auction marketplace. BidVex is not affiliated with any cryptocurrency platform. Corporation
Number: 1175252826.
</p>

<hr style="margin:32px 0;border:0;border-top:1px solid #cbd5e1;">
<p style="color:#475569;font-size:14px;line-height:1.7;">
<strong>Media Contact</strong><br>
BidVex Inc.<br>
761 Rue Chalifoux, Sherbrooke, Québec, J1G 0A8<br>
Phone: +1 (450) 634-3099<br>
Email: <a href="mailto:marketing@bidvex.com" style="color:#2B8FD0;">marketing@bidvex.com</a><br>
Web: <a href="https://www.bidvex.com" style="color:#2B8FD0;">www.bidvex.com</a>
</p>
"""


# ─── FR Copy ──────────────────────────────────────────────────────────
FR_TITLE = "BidVex lance officiellement sa plateforme au Québec — La marketplace d'enchères bilingue du Canada"
FR_META  = (
    "BidVex Inc. annonce le lancement officiel de la première marketplace "
    "d'enchères en ligne entièrement bilingue au Canada. Enchères de véhicules, "
    "d'entreposage, marketplace et lots à travers les 10 provinces, avec des "
    "frais de plateforme de 2,5 %."
)

FR_BODY_HTML = """
<p class="lead" style="font-size:18px;color:#0B2545;font-weight:600;line-height:1.5;">
POUR DIFFUSION IMMÉDIATE — Sherbrooke, Québec — 17 juillet 2026
</p>

<p>
<strong>BidVex Inc.</strong>, entreprise technologique basée à Sherbrooke, lance
officiellement <strong>la première marketplace d'enchères en ligne entièrement
bilingue du Canada</strong>. Dès aujourd'hui, la plateforme est ouverte aux acheteurs
et vendeurs des 10 provinces canadiennes, avec une attention particulière au Québec —
lieu du siège social et de l'équipe fondatrice de BidVex.
</p>

<p>
La plateforme opère <strong>quatre verticales d'enchères distinctes</strong> sous
un compte unique : une marketplace générale (biens de consommation et d'affaires),
un canal de lots et liquidation (inventaires industriels et commerciaux en vrac),
des enchères de véhicules par concessionnaires licenciés (vérifiés SAAQ, OMVIC, AMVIC
et VSA), et des enchères de casiers d'entreposage (installations vérifiées à travers
le Canada).
</p>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">Des frais de plateforme de 2,5 % — non pas 10 à 15 %</h2>

<p>
Là où les maisons d'enchères traditionnelles chargent aux vendeurs des commissions
de 10 % à 15 %, BidVex propose <strong>des frais de plateforme fixes de 2,5 %</strong>
pour toutes les verticales. Les frais sont transparents et divulgués intégralement dès
la mise en ligne — aucune surprise de prime d'acheteur cachée au moment du règlement.
</p>

<blockquote style="border-left:4px solid #2B8FD0;padding:16px 20px;margin:24px 0;
                   background:#F0F9FF;color:#0C4A6E;font-style:italic;">
« Trop longtemps, les acheteurs et vendeurs canadiens ont payé des frais gonflés à
des intermédiaires d'enchères bâtis sur une infrastructure des années 1980. BidVex
est une plateforme à propriété canadienne, bilingue et technologique. Nous l'avons
construite ici, à Sherbrooke — pour le Québec d'abord, pour tout le Canada ensuite.
Nos frais de plateforme de 2,5 % ne sont pas une promotion de lancement — c'est
notre modèle d'affaires permanent. »
<br><br>
— <strong>Charbel Lichaa</strong>, Fondateur et PDG, BidVex Inc.
</blockquote>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">Conçu pour le Québec — et pour tout le Canada</h2>

<p>
BidVex est entièrement bilingue français/anglais à chaque niveau — interface
utilisateur, factures, documentation légale, support client et communications
courriel — en pleine conformité avec la <strong>Loi 96</strong>. L'entreprise
est enregistrée fédéralement sous BidVex Inc. (numéro de corporation 1175252826)
et exploite une infrastructure de données canadienne conforme à la LPRPDE
et à la Loi 25.
</p>

<p>
Les inscriptions de véhicules sont réservées aux concessionnaires licenciés par
leur province respective, vérifiés auprès des autorités appropriées : SAAQ
(Québec), OMVIC (Ontario), AMVIC (Alberta), VSA (Colombie-Britannique) et
organismes équivalents pour les autres provinces. Les gagnants d'enchères
doivent compléter une <strong>vérification d'identité KYC via Stripe Identity</strong>
avant de finaliser leur achat.
</p>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">Faits saillants technologiques</h2>
<ul style="line-height:1.9;">
    <li><strong>Détection de fraude par IA</strong> — chaque annonce est analysée avant publication</li>
    <li><strong>Protection anti-snipe par fermeture progressive</strong> — les enchères des 60 dernières secondes prolongent le minuteur</li>
    <li><strong>Séquestre Stripe pour les articles non-véhicules</strong> — les fonds sont libérés seulement à la confirmation du retrait</li>
    <li><strong>Paiement direct courtier pour les véhicules</strong> — le prix marteau est réglé hors plateforme, en pleine conformité avec les lois provinciales sur les concessionnaires</li>
    <li><strong>Enchères en temps réel par WebSocket</strong> — latence sous 100 ms pour une expérience d'enchère fluide</li>
    <li><strong>Support client bilingue</strong> — français et anglais, par téléphone et courriel</li>
</ul>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">Offre de lancement — SUMMER2026</h2>

<p>
Pour célébrer le lancement au Québec, BidVex offre à tous les nouveaux vendeurs
<strong>un mois d'inscription Premium gratuit</strong> avec le code promotionnel
<strong>SUMMER2026</strong>. L'offre est valable jusqu'au <strong>31 août 2026</strong>.
</p>

<h2 style="color:#0B2545;font-size:22px;margin-top:24px;">À propos de BidVex Inc.</h2>

<p>
BidVex Inc. est une entreprise technologique à propriété canadienne basée à
Sherbrooke, Québec. Fondée par Charbel Lichaa, l'entreprise exploite la première
marketplace d'enchères en ligne entièrement bilingue au Canada. BidVex n'est
affiliée à aucune plateforme de cryptomonnaie. Numéro de corporation : 1175252826.
</p>

<hr style="margin:32px 0;border:0;border-top:1px solid #cbd5e1;">
<p style="color:#475569;font-size:14px;line-height:1.7;">
<strong>Contact médias</strong><br>
BidVex Inc.<br>
761 Rue Chalifoux, Sherbrooke, Québec, J1G 0A8<br>
Téléphone : +1 (450) 634-3099<br>
Courriel : <a href="mailto:marketing@bidvex.com" style="color:#2B8FD0;">marketing@bidvex.com</a><br>
Web : <a href="https://www.bidvex.com" style="color:#2B8FD0;">www.bidvex.com</a>
</p>
"""


def build_press_release_entries() -> Dict[str, Dict[str, Any]]:
    """Return `_REGIONAL_LANDINGS`-compatible entries for EN + FR press pages."""
    paths = press_release_paths()
    en_path, fr_path = paths["en"], paths["fr"]
    return {
        en_path: {
            "kind": "press_release",
            "title_en": EN_TITLE,
            "desc_en":  EN_META,
            "h1_en":    EN_TITLE,
            "body_en":  EN_BODY_HTML,  # Rendered as {{ body_copy | safe }} in template
            "cta_target": "/marketplace",
            "twin_fr": fr_path,
        },
        fr_path: {
            "kind": "press_release",
            "title_fr": FR_TITLE,
            "desc_fr":  FR_META,
            "h1_fr":    FR_TITLE,
            "body_fr":  FR_BODY_HTML,
            "cta_target": "/marketplace",
            "twin_en": en_path,
            "lang_only": "fr",
        },
    }


def news_article_ld_for(lang: str) -> Dict[str, Any]:
    """Build a NewsArticle JSON-LD payload for the press-release page."""
    from services.seo_jsonld import CANONICAL_HOST

    paths = press_release_paths()
    canonical = f"{CANONICAL_HOST}{paths.get(lang, paths['en'])}"
    twin_url  = f"{CANONICAL_HOST}{paths['fr' if lang == 'en' else 'en']}"

    headline = FR_TITLE if lang == "fr" else EN_TITLE
    desc     = FR_META if lang == "fr" else EN_META
    author_role = FOUNDER_TITLE_FR if lang == "fr" else FOUNDER_TITLE_EN

    return {
        "@context": "https://schema.org",
        "@type":    "NewsArticle",
        "headline": headline,
        "description": desc,
        "datePublished": PRESS_RELEASE_DATE_PUBLISHED,
        "dateModified":  PRESS_RELEASE_DATE_PUBLISHED,
        "inLanguage":    "fr-CA" if lang == "fr" else "en-CA",
        "url":           canonical,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id":   canonical,
        },
        "author": {
            "@type": "Person",
            "name":  FOUNDER_NAME,
            "jobTitle": author_role,
            "worksFor": {
                "@type": "Organization",
                "name":  "BidVex Inc.",
                "url":   CANONICAL_HOST,
            },
        },
        "publisher": {
            "@type": "Organization",
            "name":  "BidVex Inc.",
            "url":   CANONICAL_HOST,
            "logo": {
                "@type": "ImageObject",
                "url":   f"{CANONICAL_HOST}/bidvex-icon.png",
                "width":  512,
                "height": 512,
            },
        },
        "image": [
            f"{CANONICAL_HOST}/bidvex-icon.png",
        ],
        "isPartOf": {
            "@type": "WebSite",
            "@id":   CANONICAL_HOST,
            "name":  "BidVex",
        },
        "translationOfWork": {
            "@id": twin_url,
        } if lang == "fr" else None,
    }


__all__ = [
    "PRESS_RELEASE_DATE_PUBLISHED",
    "PRESS_RELEASE_PDF_URL",
    "FOUNDER_NAME",
    "FOUNDER_TITLE_EN",
    "FOUNDER_TITLE_FR",
    "press_release_paths",
    "build_press_release_entries",
    "news_article_ld_for",
]
