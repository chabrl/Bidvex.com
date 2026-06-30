"""
iter331 — Idempotent seed of the 6 original /blogs articles into MongoDB.

Runs once on app startup (via server.py lifespan hook). Safe to re-run —
every article is keyed by `slug` and we only insert when missing.

This lets the freshly-introduced press_articles CRUD render a non-empty
public /blogs page on first load without requiring an admin to manually
re-create the seed content.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid

logger = logging.getLogger(__name__)


SEED_ARTICLES: List[Dict[str, Any]] = [
    {
        "slug": "how-bidvex-auction-engine-works",
        "tag": "platform",
        "icon": "Gavel",
        "title_en": "How the BidVex Auction Engine Works — Hammer Price, Buyer Premium & Settlement",
        "title_fr": "Comment fonctionne le moteur d’enchères BidVex — Prix marteau, prime acheteur et règlement",
        "excerpt_en": "A clear breakdown of how the final hammer price is determined, when the buyer's premium applies (3%–5% by tier), and the role of the 14.975% Quebec tax on platform service fees.",
        "excerpt_fr": "Comprendre comment le prix marteau final est déterminé, quand la prime acheteur s'applique (3 % à 5 % selon le palier) et le rôle de la taxe québécoise de 14,975 % sur les frais de service.",
        "body_en": (
            "## Hammer price\n\n"
            "The final hammer price is the highest competing bid placed before the auction's natural expiry "
            "(or the seller's reserve, whichever is higher). BidVex never touches that headline number — it "
            "is the contractual amount between buyer and seller.\n\n"
            "## Buyer's premium\n\n"
            "On top of the hammer price, a transparent **buyer's premium** (3%–5% depending on tier) is added "
            "as the platform service fee. This is what funds the auction infrastructure, fraud screening, and "
            "Stripe settlement rails.\n\n"
            "## Quebec tax (TVQ / GST)\n\n"
            "Every platform service fee billed to Quebec residents includes 14.975% combined GST+TVQ, "
            "automatically calculated and remitted by BidVex.\n\n"
            "## Settlement\n\n"
            "When the auction closes, BidVex orchestrates the settlement: the buyer's pickup code is generated, "
            "the seller is notified, and once the buyer confirms pickup, funds (less platform fees) move to the "
            "seller's Stripe Connect account."
        ),
        "body_fr": (
            "## Prix marteau\n\n"
            "Le prix marteau final correspond à l'enchère gagnante la plus élevée avant l'expiration naturelle "
            "de l'enchère (ou le prix de réserve du vendeur, le plus élevé des deux). BidVex ne touche jamais ce "
            "montant — il s'agit du contrat entre l'acheteur et le vendeur.\n\n"
            "## Prime acheteur\n\n"
            "Une **prime acheteur** transparente (3 % à 5 % selon le palier) s'ajoute au prix marteau au titre "
            "des frais de service de la plateforme. Elle finance l'infrastructure d'enchères, l'analyse anti-fraude "
            "et les rails de règlement Stripe.\n\n"
            "## Taxe québécoise (TPS / TVQ)\n\n"
            "Chaque frais de service facturé aux résidents du Québec inclut une taxe combinée TPS+TVQ de 14,975 %, "
            "automatiquement calculée et reversée par BidVex.\n\n"
            "## Règlement\n\n"
            "À la clôture de l'enchère, BidVex orchestre le règlement : le code de cueillette de l'acheteur est généré, "
            "le vendeur est notifié, et dès que l'acheteur confirme la collecte, les fonds (moins les frais) sont versés "
            "sur le compte Stripe Connect du vendeur."
        ),
        "read_min": 6,
    },
    {
        "slug": "broker-and-dealer-onboarding",
        "tag": "compliance",
        "icon": "ShieldCheck",
        "title_en": "Becoming a Certified Vehicle Dealer or Broker on BidVex",
        "title_fr": "Devenir concessionnaire de véhicules certifié ou courtier sur BidVex",
        "excerpt_en": "The full broker-gate verification pipeline: OMVIC, AMVIC, VSA and SAAQ license validation, $200/yr subscription with the LAUNCH50 coupon, and the buyer security deposit mechanics.",
        "excerpt_fr": "Le pipeline complet de vérification du portail courtier : validation des licences OMVIC, AMVIC, VSA et SAAQ, abonnement annuel de 200 $ avec le coupon LAUNCH50, et la mécanique du dépôt de sécurité acheteur.",
        "body_en": (
            "## Verification pipeline\n\n"
            "Every broker / dealer applicant submits their provincial dealer licence "
            "(OMVIC for Ontario, AMVIC for Alberta, VSA for British Columbia, SAAQ for Quebec). BidVex "
            "verifies the licence number, expiry and business name against the issuing registry.\n\n"
            "## Annual subscription\n\n"
            "The broker tier runs **$200/yr**, with a launch promotion using the `LAUNCH50` coupon (50% off "
            "the first year).\n\n"
            "## Buyer security deposit\n\n"
            "Buyers placing serious bids on dealer/broker inventory pre-authorize a **$500 security deposit** on "
            "Stripe. It is released after pickup or applied as the platform service fee on default."
        ),
        "body_fr": (
            "## Pipeline de vérification\n\n"
            "Chaque candidature courtier/concessionnaire soumet sa licence provinciale "
            "(OMVIC pour l'Ontario, AMVIC pour l'Alberta, VSA pour la Colombie-Britannique, SAAQ pour le Québec). "
            "BidVex vérifie le numéro, l'échéance et le nom commercial directement au registre émetteur.\n\n"
            "## Abonnement annuel\n\n"
            "Le palier courtier est à **200 $/an**, avec une promotion de lancement via le coupon `LAUNCH50` (50 % "
            "de rabais sur la première année).\n\n"
            "## Dépôt de sécurité acheteur\n\n"
            "Les acheteurs sérieux sur l'inventaire courtier pré-autorisent un **dépôt de sécurité de 500 $** "
            "sur Stripe. Il est libéré après la collecte ou appliqué comme frais de service en cas de défaut."
        ),
        "read_min": 8,
    },
    {
        "slug": "storage-facility-liquidation-rules",
        "tag": "storage",
        "icon": "Warehouse",
        "title_en": "Commercial Storage Facility Auctions — Compliance & Buyer's Premium",
        "title_fr": "Enchères de centres d'entreposage commercial — Conformité et prime acheteur",
        "excerpt_en": "How abandoned storage unit liquidations work under Quebec self-storage statutes, including the standard 5% buyer premium and notice-period requirements.",
        "excerpt_fr": "Le fonctionnement de la liquidation des unités d'entreposage abandonnées en vertu des lois québécoises, y compris la prime acheteur standard de 5 % et les délais de préavis requis.",
        "body_en": (
            "## Statutory notice window\n\n"
            "Quebec self-storage statutes require a **45-day notice window** before abandoned-unit liquidation. "
            "BidVex stamps every storage listing with the lien-notice date so buyers can verify compliance.\n\n"
            "## Buyer's premium\n\n"
            "Storage-unit auctions carry a **flat 5% buyer's premium** that funds the platform — the facility "
            "keeps 100% of the hammer price.\n\n"
            "## Settlement\n\n"
            "On hammer close, the buyer's payment is captured immediately and the facility issues a pickup "
            "window (typically 48 hours)."
        ),
        "body_fr": (
            "## Délai de préavis légal\n\n"
            "Les lois québécoises sur l'entreposage libre-service exigent un **préavis de 45 jours** avant la "
            "liquidation d'une unité abandonnée. BidVex estampille chaque annonce d'entreposage avec la date "
            "de l'avis de privilège afin que les acheteurs puissent vérifier la conformité.\n\n"
            "## Prime acheteur\n\n"
            "Les enchères d'unités d'entreposage portent une **prime acheteur forfaitaire de 5 %** qui finance "
            "la plateforme — le centre conserve 100 % du prix marteau.\n\n"
            "## Règlement\n\n"
            "À la clôture, le paiement de l'acheteur est capté immédiatement et le centre fixe une fenêtre de "
            "cueillette (typiquement 48 heures)."
        ),
        "read_min": 5,
    },
    {
        "slug": "vehicle-hammer-direct-settlement",
        "tag": "vehicles",
        "icon": "Truck",
        "title_en": "Vehicle Hammer Price — Why BidVex Never Touches It",
        "title_fr": "Prix marteau du véhicule — Pourquoi BidVex n'y touche jamais",
        "excerpt_en": "Direct buyer-to-broker settlement, Stripe Connect only processes service fees, GST/QST split, and SAAQ/OMVIC title transfer obligations.",
        "excerpt_fr": "Règlement direct acheteur-courtier, Stripe Connect ne traite que les frais de service, ventilation TPS/TVQ, et obligations de transfert de titre SAAQ/OMVIC.",
        "body_en": (
            "## Direct settlement\n\n"
            "On vehicle auctions, the hammer price is settled **directly between buyer and broker/dealer** — "
            "BidVex never holds it in escrow. Stripe Connect only processes the platform service fee.\n\n"
            "## Title transfer\n\n"
            "The selling broker is responsible for issuing the SAAQ (QC) or OMVIC (ON) title-transfer document "
            "within 72 hours of pickup."
        ),
        "body_fr": (
            "## Règlement direct\n\n"
            "Pour les enchères de véhicules, le prix marteau est réglé **directement entre acheteur et "
            "courtier/concessionnaire** — BidVex ne le détient jamais en entiercement. Stripe Connect ne "
            "traite que les frais de service.\n\n"
            "## Transfert de titre\n\n"
            "Le courtier vendeur est responsable d'émettre le document de transfert SAAQ (QC) ou OMVIC (ON) "
            "dans les 72 heures suivant la cueillette."
        ),
        "read_min": 7,
    },
    {
        "slug": "contractor-commission-and-leaderboard",
        "tag": "partners",
        "icon": "Sparkles",
        "title_en": "Inside the Contractor Commission Engine — 5% Baseline, +1% per Week in the Top 5",
        "title_fr": "À l'intérieur du moteur de commission contractant — 5 % de base, +1 % par semaine dans le Top 5",
        "excerpt_en": "How verified contractor acquisitions earn a structural 5% baseline commission, the Monday-reset Top-5 leaderboard +1% bonus, the -1% drop-out deduction, and the 20% effective ceiling.",
        "excerpt_fr": "Comment les acquisitions de contractants vérifiés gagnent une commission de base structurelle de 5 %, le bonus +1 % du tableau Top 5 réinitialisé chaque lundi, la déduction -1 % en cas de sortie et le plafond effectif de 20 %.",
        "body_en": (
            "## Baseline 5%\n\n"
            "Every verified contractor earns a structural **5% baseline commission** on every settled transaction "
            "from accounts they referred.\n\n"
            "## Leaderboard overlay\n\n"
            "Every Monday at 08:00 EST the previous 7-day commission volume is ranked. **+1%** per consecutive "
            "week in the Top 5 (additive). **-1%** per consecutive week outside it. Effective range is clamped "
            "to **[5%, 20%]**.\n\n"
            "## Privacy\n\n"
            "Dollar earnings are never exposed in the leaderboard view — only rank, masked ID and the live "
            "overlay rate."
        ),
        "body_fr": (
            "## Base de 5 %\n\n"
            "Chaque contractant vérifié obtient une **commission de base structurelle de 5 %** sur toute "
            "transaction réglée par les comptes qu'il a parrainés.\n\n"
            "## Bonification de classement\n\n"
            "Tous les lundis à 8 h 00 (EST), le volume de commissions des 7 derniers jours est classé. **+1 %** "
            "par semaine consécutive dans le Top 5 (additif). **-1 %** par semaine hors du Top 5. La plage "
            "effective est encadrée à **[5 %, 20 %]**.\n\n"
            "## Confidentialité\n\n"
            "Les gains en dollars ne sont jamais exposés dans le tableau — uniquement le rang, l'ID masqué "
            "et le taux d'overlay en cours."
        ),
        "read_min": 6,
    },
    {
        "slug": "watchdog-fraud-engine",
        "tag": "security",
        "icon": "ShieldCheck",
        "title_en": "The Watchdog Fraud Engine — How BidVex AI Telemetry Protects Every Auction",
        "title_fr": "Le moteur antifraude Watchdog — Comment la télémétrie IA de BidVex protège chaque enchère",
        "excerpt_en": "Real-time photo-EXIF analysis, duplicate-listing detection, bid-velocity scoring, and the GenAI direct watchdog that scores every new listing before it goes live.",
        "excerpt_fr": "Analyse EXIF photo en temps réel, détection de listings dupliqués, score de vélocité d'enchères et watchdog direct GenAI qui évalue chaque nouvelle annonce avant publication.",
        "body_en": (
            "## EXIF + duplicate detection\n\n"
            "Every uploaded photo is run through an EXIF-integrity check (timestamp, GPS, manufacturer "
            "signature) and a perceptual-hash duplicate-detection pass against the existing image corpus.\n\n"
            "## Bid-velocity scoring\n\n"
            "The Watchdog continuously scores bid velocity, IP geolocation entropy and account age. "
            "Anomalies are flagged to the admin Compliance Console in real time.\n\n"
            "## GenAI pre-flight\n\n"
            "Every new listing is also scored by the GenAI direct watchdog **before it goes live** so policy "
            "violations and obvious fraud patterns are caught at submission time, not after publication."
        ),
        "body_fr": (
            "## EXIF + détection de doublons\n\n"
            "Chaque photo téléversée subit un contrôle d'intégrité EXIF (horodatage, GPS, signature "
            "manufacturier) et une passe de détection de doublons par hachage perceptuel sur le corpus "
            "d'images existant.\n\n"
            "## Score de vélocité d'enchères\n\n"
            "Le Watchdog évalue en continu la vélocité des enchères, l'entropie de géolocalisation IP et "
            "l'ancienneté du compte. Les anomalies sont signalées à la console de conformité en temps réel.\n\n"
            "## Pré-vol GenAI\n\n"
            "Chaque nouvelle annonce est aussi notée par le watchdog direct GenAI **avant publication** "
            "afin que les violations de politique et les schémas de fraude évidents soient interceptés "
            "à la soumission, pas après publication."
        ),
        "read_min": 9,
    },
]


async def seed_press_articles(db) -> Dict[str, Any]:
    """Idempotently insert the 6 default press articles. Returns counters."""
    inserted, skipped = 0, 0
    now = datetime.now(timezone.utc).isoformat()
    for art in SEED_ARTICLES:
        try:
            existing = await db.press_articles.find_one(
                {"slug": art["slug"]}, {"_id": 1, "id": 1},
            )
            if existing is not None:
                skipped += 1
                continue
            doc = {
                "id": str(uuid.uuid4()),
                "slug": art["slug"],
                "tag": art["tag"],
                "icon": art["icon"],
                "title_en": art["title_en"],
                "title_fr": art["title_fr"],
                "excerpt_en": art["excerpt_en"],
                "excerpt_fr": art["excerpt_fr"],
                "body_en": art["body_en"],
                "body_fr": art["body_fr"],
                "cover_url": None,
                "read_min": int(art["read_min"]),
                "published": True,
                "published_at": now,
                "created_at": now,
                "updated_at": now,
                "created_by": "system-seed",
            }
            await db.press_articles.insert_one(doc)
            inserted += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[blogs_seed] failed to seed {art.get('slug')}: {e}")

    logger.info(f"[blogs_seed] inserted={inserted} skipped={skipped}")
    return {"inserted": inserted, "skipped": skipped, "total": len(SEED_ARTICLES)}
