"""
iter317 Directive 2 — Contractor Agreement v2 (bilingual EN/FR).

Append-only legal text. NEVER mutate this module in place — ship a v3
file if any wording changes.

Both the English and French texts are exported verbatim. We compute a
single canonical SHA-256 hash over the concatenation "VERSION\n\nEN\n\nFR"
so the audit log persists exactly what the contractor agreed to.

Garble-free French — uses Latin `indépendante` (not Arabic `مستقل`) and
the French conjunction `ou` (not the Arabic `أو`).
"""
from __future__ import annotations

import hashlib

AGREEMENT_VERSION = "v2.0"


AGREEMENT_TITLE_EN = "BidVex Contractor Services Agreement (v2.0)"
AGREEMENT_TITLE_FR = "Entente de services du contractant BidVex (v2.0)"


# ── English text (canonical) ────────────────────────────────────────────
AGREEMENT_TEXT_EN = """\
BIDVEX CONTRACTOR SERVICES AGREEMENT
Version 2.0

This BidVex Contractor Services Agreement (the "Agreement") is entered
into between BidVex Inc. ("BidVex", "we", "our") and you ("Contractor",
"you", "your") effective as of the date you electronically accept this
Agreement.

1. INDEPENDENT CONTRACTOR STATUS
You are engaged as an independent contractor. Nothing in this Agreement
shall be construed to create a partnership, employment, joint venture,
or agency relationship between you and BidVex. You shall be solely
responsible for all taxes, deductions, and remittances arising from
amounts paid to you under this Agreement.

2. SCOPE OF SERVICES
You will originate, refer, and onboard prospective client accounts to
the BidVex platform, conduct outbound calls through the BidVex Dialer,
and assist clients with onboarding to the BidVex marketplace. You will
NOT make representations, warranties, or commitments on behalf of
BidVex that are not expressly authorized in writing.

3. COMMISSION & PAYMENT
3.1 BidVex shall pay you a commission on platform fees collected from
accounts you have permanently referred, at the rate disclosed in your
Contractor Dashboard. Rates may be amended by BidVex prospectively; any
change applies only to commissions accruing AFTER the effective date.
3.2 A weekly Leaderboard Overlay of up to +1.0% may be added on entry
to the Top 5 by 7-day commission volume, subject to an absolute overlay
ceiling of +20.0% and a hard floor of 5.0% on the effective total rate.
3.3 Commissions are paid on a monthly cadence via Stripe Connect to the
account you have onboarded. Payouts require a fully completed Stripe
Connect onboarding.

4. CONFIDENTIALITY
You shall hold in strict confidence all non-public information you
receive about BidVex, its users, and its operations. This obligation
survives termination of this Agreement.

5. CODE OF CONDUCT
You will not engage in spam, harassment, misrepresentation, or any
practice that could damage BidVex's reputation or violate applicable
law (including but not limited to CASL, Bill 25, PIPEDA, and Bill 96).
All outbound communications must be respectful, accurate, and
compliant with Canadian anti-spam regulations.

6. INTELLECTUAL PROPERTY
All trademarks, logos, software, and content of BidVex remain the
exclusive property of BidVex. You receive no licence beyond the
limited right to use the BidVex Dialer and Contractor Dashboard for
the purpose of performing your Services under this Agreement.

7. DATA PROTECTION
You will treat all personal information of leads and clients in
accordance with Quebec Law 25 (formerly Bill 64), PIPEDA, and any
other applicable privacy law. You will not store, copy, or transfer
client personal data outside the BidVex platform without our prior
written consent.

8. TERMINATION
Either party may terminate this Agreement at any time, with or without
cause, on written notice. Upon termination: (a) referral attribution
on existing accounts is preserved (history is immutable); (b) future
commission accruals stop; (c) any accrued-but-unpaid commission
balance becomes payable on the next scheduled payout cycle, subject
to Stripe Connect availability.

9. INDEMNIFICATION
You will indemnify, defend, and hold harmless BidVex and its officers,
directors, employees, and agents from any claim, loss, or expense
arising out of your breach of this Agreement, your acts or omissions
as Contractor, or your violation of applicable law.

10. GOVERNING LAW
This Agreement is governed by the laws of the Province of Quebec and
the federal laws of Canada applicable therein. The parties consent to
the exclusive jurisdiction of the courts located in the District of
Montreal.

11. ELECTRONIC ACCEPTANCE
By typing your full legal name below and clicking "I Accept", you
confirm that you have read, understood, and agree to be bound by this
Agreement. An immutable audit record (including your IP address,
user-agent, timestamp, and a SHA-256 hash of this exact text) will be
stored to evidence your acceptance.
"""


# ── French text (canonical) ─────────────────────────────────────────────
# IMPORTANT — Garble-free: uses Latin `indépendante` and the conjunction
# `ou`. No Arabic substitutions allowed.
AGREEMENT_TEXT_FR = """\
ENTENTE DE SERVICES DU CONTRACTANT BIDVEX
Version 2.0

La présente Entente de services du contractant BidVex (l'« Entente »)
est conclue entre BidVex Inc. (« BidVex », « nous », « notre ») et
vous (« Contractant », « vous », « votre ») et prend effet à la date à
laquelle vous acceptez la présente Entente par voie électronique.

1. STATUT DE CONTRACTANT INDÉPENDANT
Vous êtes engagé(e) à titre de contractant(e) indépendante. Aucune
disposition de la présente Entente ne sera interprétée comme créant
une société, un emploi, une coentreprise ou une relation de mandataire
entre vous et BidVex. Vous êtes seul(e) responsable de tous les
impôts, déductions et remises découlant des sommes qui vous sont
versées en vertu de la présente Entente.

2. PORTÉE DES SERVICES
Vous initierez, recommanderez et intégrerez des comptes clients
potentiels à la plateforme BidVex, effectuerez des appels sortants via
le composeur BidVex, et assisterez les clients dans leur intégration au
marché BidVex. Vous NE ferez AUCUNE déclaration, garantie ou
engagement au nom de BidVex qui n'est pas expressément autorisé par
écrit.

3. COMMISSION ET PAIEMENT
3.1 BidVex vous versera une commission sur les frais de plateforme
perçus auprès des comptes que vous avez parrainés de manière
permanente, au taux indiqué dans votre tableau de bord du contractant.
Les taux peuvent être modifiés par BidVex à titre prospectif ; toute
modification ne s'applique qu'aux commissions accumulées APRÈS la date
d'entrée en vigueur.
3.2 Une bonification hebdomadaire (« Leaderboard Overlay ») pouvant
atteindre +1,0 % peut être ajoutée lors de l'entrée dans le Top 5 selon
le volume de commissions des 7 derniers jours, sous réserve d'un
plafond absolu de bonification de +20,0 % et d'un plancher strict de
5,0 % sur le taux total effectif.
3.3 Les commissions sont versées sur une base mensuelle via Stripe
Connect au compte que vous avez intégré. Les versements exigent une
intégration Stripe Connect entièrement complétée.

4. CONFIDENTIALITÉ
Vous garderez en toute confidentialité tous les renseignements non
publics que vous recevez concernant BidVex, ses utilisateurs et ses
activités. Cette obligation survit à la résiliation de la présente
Entente.

5. CODE DE CONDUITE
Vous ne vous livrerez à aucune pratique de pourriel, de harcèlement,
de fausse déclaration ou toute autre pratique susceptible de nuire à
la réputation de BidVex ou de contrevenir aux lois applicables (y
compris, sans s'y limiter, la LCAP, la Loi 25, la LPRPDE ou la
Loi 96). Toutes les communications sortantes doivent être respectueuses,
exactes et conformes à la réglementation canadienne anti-pourriel.

6. PROPRIÉTÉ INTELLECTUELLE
Toutes les marques de commerce, logos, logiciels et contenus de BidVex
demeurent la propriété exclusive de BidVex. Vous ne recevez aucune
licence au-delà du droit limité d'utiliser le composeur BidVex et le
tableau de bord du contractant aux fins d'exécuter vos Services en
vertu de la présente Entente.

7. PROTECTION DES DONNÉES
Vous traiterez tous les renseignements personnels des prospects et des
clients conformément à la Loi 25 du Québec (anciennement projet de
Loi 64), à la LPRPDE et à toute autre loi sur la protection de la vie
privée applicable. Vous ne stockerez, copierez ou transférerez aucune
donnée personnelle des clients en dehors de la plateforme BidVex sans
notre consentement écrit préalable.

8. RÉSILIATION
L'une ou l'autre des parties peut résilier la présente Entente à tout
moment, avec ou sans motif, sur préavis écrit. À la résiliation :
(a) l'attribution de parrainage sur les comptes existants est
préservée (l'historique est immuable) ; (b) les futures accumulations
de commissions cessent ; (c) tout solde de commission accumulé mais
non payé devient payable au prochain cycle de versement prévu, sous
réserve de la disponibilité de Stripe Connect.

9. INDEMNISATION
Vous indemniserez, défendrez et tiendrez indemnes BidVex et ses
dirigeants, administrateurs, employés et mandataires de toute
réclamation, perte ou dépense découlant de votre violation de la
présente Entente, de vos actes ou omissions à titre de Contractant ou
de votre violation des lois applicables.

10. DROIT APPLICABLE
La présente Entente est régie par les lois de la province de Québec
et les lois fédérales du Canada qui y sont applicables. Les parties
consentent à la compétence exclusive des tribunaux situés dans le
district de Montréal.

11. ACCEPTATION ÉLECTRONIQUE
En saisissant votre nom légal complet ci-dessous et en cliquant sur
« J'accepte », vous confirmez avoir lu, compris et accepté d'être
lié(e) par la présente Entente. Un enregistrement d'audit immuable
(incluant votre adresse IP, votre agent utilisateur, l'horodatage et
un hachage SHA-256 du texte exact) sera conservé pour attester votre
acceptation.
"""


def _canonical_blob() -> str:
    return f"{AGREEMENT_VERSION}\n\nEN\n\n{AGREEMENT_TEXT_EN}\n\nFR\n\n{AGREEMENT_TEXT_FR}"


def compute_text_hash() -> str:
    """SHA-256 of the canonical blob — what the audit log persists."""
    return hashlib.sha256(_canonical_blob().encode("utf-8")).hexdigest()


# Pre-compute so importing modules get the constant immediately.
AGREEMENT_TEXT_HASH = compute_text_hash()


def get_agreement() -> dict:
    """Single read-the-spec accessor used by route handlers and the
    frontend modal. Returns the title + text + version + hash."""
    return {
        "version":   AGREEMENT_VERSION,
        "title_en":  AGREEMENT_TITLE_EN,
        "title_fr":  AGREEMENT_TITLE_FR,
        "text_en":   AGREEMENT_TEXT_EN,
        "text_fr":   AGREEMENT_TEXT_FR,
        "text_hash": AGREEMENT_TEXT_HASH,
    }


__all__ = [
    "AGREEMENT_VERSION",
    "AGREEMENT_TITLE_EN",
    "AGREEMENT_TITLE_FR",
    "AGREEMENT_TEXT_EN",
    "AGREEMENT_TEXT_FR",
    "AGREEMENT_TEXT_HASH",
    "compute_text_hash",
    "get_agreement",
]
