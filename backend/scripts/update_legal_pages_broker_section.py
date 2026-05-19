"""
iter217 Phase 5 Hotfix v5b — One-shot updater that appends the
Broker Ecosystem section to the Privacy Policy and Terms of Service
pages stored in `site_config` (type='legal_pages').

Idempotent: re-running detects the existing broker section and skips.

Usage:
    python -m scripts.update_legal_pages_broker_section
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

# ── Marker so we can detect idempotency ───────────────────────────────
PP_MARKER  = "<!-- BROKER_ECOSYSTEM_PRIVACY_v1 -->"
TOS_MARKER = "<!-- BROKER_ECOSYSTEM_TOS_v1 -->"

PP_EN = (
    PP_MARKER + """

## BROKER ECOSYSTEM

When you use BidVex as a Broker or as a Buyer bound to a Broker:

**Information collected:** We collect your commercial broker license number, regulatory body, corporate registration number, business name, and uploaded license documents. For buyers bound to a broker, we collect your partnership agreement status and bidding activity under that broker.

**Legal attribution:** Every bid placed via a broker is permanently recorded with the broker's license number, the buyer's user ID, IP address, device, and timestamp. These records are retained for 7 years in compliance with Canadian business record law and cannot be modified or deleted.

**Deposit handling:** Security deposits ($500 CAD pre-authorization) are processed via Stripe. BidVex does not store card numbers. Deposits are released automatically when a partnership ends in good standing, or captured in cases of default as defined in our Terms of Service.

**Broker fee disclosure:** Your broker's fee structure (fixed or percentage) is disclosed to you before you place any bid. BidVex does not set broker fees — they are independently configured by each licensed broker.

**Data sharing:** Your personal information is shared with your bound broker solely for the purpose of facilitating vehicle transactions. Brokers are contractually prohibited from using your data for any other purpose.

**Regulatory compliance:** BidVex cooperates with OMVIC, AMVIC, VSA, SAAQ, and other provincial regulatory bodies. Audit records may be disclosed in response to lawful regulatory requests.
"""
)

PP_FR = (
    PP_MARKER + """

## ÉCOSYSTÈME DE COURTIERS

Lorsque vous utilisez BidVex en tant que courtier ou en tant qu'acheteur lié à un courtier :

**Informations collectées :** Nous collectons votre numéro de permis de courtier commercial, l'organisme de réglementation, le numéro d'immatriculation de l'entreprise, la raison sociale et les documents de permis téléversés. Pour les acheteurs liés à un courtier, nous collectons votre statut de partenariat et votre activité d'enchères sous ce courtier.

**Attribution légale :** Chaque enchère placée via un courtier est enregistrée de façon permanente avec le numéro de permis du courtier, l'identifiant de l'acheteur, l'adresse IP, l'appareil et l'horodatage. Ces dossiers sont conservés pendant 7 ans conformément à la loi canadienne sur la conservation des documents commerciaux et ne peuvent être modifiés ni supprimés.

**Gestion des dépôts :** Les dépôts de garantie (préautorisation de 500 $ CAD) sont traités via Stripe. BidVex ne stocke pas les numéros de carte. Les dépôts sont libérés automatiquement à la fin d'un partenariat en règle, ou saisis en cas de défaut tel que défini dans nos Conditions d'utilisation.

**Divulgation des frais de courtier :** La structure de frais de votre courtier (fixe ou en pourcentage) vous est communiquée avant toute enchère. BidVex ne fixe pas les frais des courtiers — ils sont configurés indépendamment par chaque courtier agréé.

**Partage des données :** Vos informations personnelles sont partagées avec votre courtier lié uniquement aux fins de faciliter les transactions de véhicules. Les courtiers sont contractuellement interdits d'utiliser vos données à d'autres fins.

**Conformité réglementaire :** BidVex coopère avec l'OMVIC, l'AMVIC, la VSA, la SAAQ et d'autres organismes provinciaux. Les dossiers d'audit peuvent être divulgués en réponse à des demandes réglementaires légales.
"""
)

TOS_EN = (
    TOS_MARKER + """

## BROKER ECOSYSTEM — TERMS AND CONDITIONS

**1. BROKER ELIGIBILITY**
To register as a BidVex Broker, you must hold a valid commercial dealer, broker, or agent permit issued by the relevant provincial regulatory authority (OMVIC in Ontario, AMVIC in Alberta, VSA in British Columbia, SAAQ or OPC in Quebec, or equivalent body in other provinces). You must provide accurate license documents at registration. BidVex reserves the right to verify your credentials directly with the regulatory body and to suspend or terminate your broker account if your license lapses or is revoked.

**2. BROKER RESPONSIBILITIES**
As a Broker, you are legally responsible for all bids placed by buyers bound to your account. You must ensure that each buyer you approve has been properly identified (KYC). You must not approve buyers you have reason to believe are acting in bad faith or do not intend to complete a purchase. You are responsible for collecting payment from your buyers and ensuring vehicle transactions are completed within the timelines set by the selling dealer.

**3. BROKER FEES**
You may configure a fixed fee or a percentage-based fee to charge your buyers. BidVex charges you nothing beyond the standard 2.5% platform fee already charged on vehicle transactions. Your fee is your independent business arrangement with your buyers. BidVex is not responsible for disputes between brokers and their buyers regarding fees.

**4. BUYER BINDING AND DEPOSITS**
A buyer may bind to only one broker at a time. The $500 CAD security deposit pre-authorization is held by BidVex via Stripe on behalf of the broker. If a buyer wins a vehicle and fails to complete payment within the required deadline, the broker may authorize BidVex to capture the deposit. Deposit capture requires documented evidence of buyer default. Disputes regarding deposit capture are handled by BidVex support and are final.

**5. INTRA-BROKER BIDDING CONFLICTS**
A broker's buyers may not bid against each other on the same vehicle. BidVex's platform automatically enforces this rule. If a conflict is detected, the second bid is blocked and the broker is notified. Attempting to circumvent this rule through multiple broker accounts is a violation of these Terms and will result in permanent suspension.

**6. AUDIT TRAIL AND RECORD RETENTION**
All bids placed via the Broker Ecosystem are permanently recorded with full attribution including broker license number, buyer identity, IP address, and timestamp. These records are retained for a minimum of 7 years. They may not be altered or deleted by any party. BidVex may disclose these records to provincial regulators, law enforcement, or in legal proceedings as required by law.

**7. BROKER ACCOUNT SUSPENSION AND TERMINATION**
BidVex may suspend or terminate a broker account at any time if: (a) the broker's license is revoked or lapsed; (b) fraudulent activity is detected; (c) the broker violates these Terms; (d) a regulatory body requests suspension. Upon termination, all active buyer relationships are terminated, all deposit holds are released to the respective buyers, and all active bids are cancelled.

**8. LIMITATION OF LIABILITY**
BidVex acts as a technology platform facilitating connections between licensed brokers, buyers, and dealers. BidVex is not a party to any vehicle transaction and is not liable for disputes arising from vehicle condition, title, payment default, or non-delivery. Brokers and dealers are solely responsible for compliance with provincial vehicle sales regulations.
"""
)

TOS_FR = (
    TOS_MARKER + """

## ÉCOSYSTÈME DE COURTIERS — CONDITIONS GÉNÉRALES

**1. ADMISSIBILITÉ DU COURTIER**
Pour vous inscrire en tant que courtier BidVex, vous devez détenir un permis de concessionnaire, de courtier ou d'agent commercial valide délivré par l'autorité provinciale de réglementation compétente (OMVIC en Ontario, AMVIC en Alberta, VSA en Colombie-Britannique, SAAQ ou OPC au Québec, ou un organisme équivalent dans les autres provinces). Vous devez fournir des documents de permis exacts au moment de l'inscription. BidVex se réserve le droit de vérifier vos accréditations directement auprès de l'organisme de réglementation et de suspendre ou résilier votre compte de courtier si votre permis expire ou est révoqué.

**2. RESPONSABILITÉS DU COURTIER**
En tant que courtier, vous êtes légalement responsable de toutes les enchères placées par les acheteurs liés à votre compte. Vous devez veiller à ce que chaque acheteur que vous approuvez ait été correctement identifié (KYC). Vous ne devez pas approuver les acheteurs qui, selon vous, agissent de mauvaise foi ou n'ont pas l'intention de finaliser un achat. Vous êtes responsable de l'encaissement des paiements de vos acheteurs et de veiller à ce que les transactions de véhicules soient finalisées dans les délais fixés par le concessionnaire vendeur.

**3. FRAIS DE COURTIER**
Vous pouvez configurer des frais fixes ou des frais basés sur un pourcentage à facturer à vos acheteurs. BidVex ne vous facture rien au-delà des frais de plateforme standards de 2,5 % déjà appliqués aux transactions de véhicules. Vos frais constituent un arrangement commercial indépendant entre vous et vos acheteurs. BidVex n'est pas responsable des différends entre courtiers et acheteurs concernant les frais.

**4. ASSOCIATION D'ACHETEURS ET DÉPÔTS**
Un acheteur ne peut être lié qu'à un seul courtier à la fois. La préautorisation du dépôt de garantie de 500 $ CAD est détenue par BidVex via Stripe au nom du courtier. Si un acheteur remporte un véhicule et ne complète pas le paiement dans le délai requis, le courtier peut autoriser BidVex à saisir le dépôt. La saisie du dépôt nécessite des preuves documentées du défaut de l'acheteur. Les différends concernant la saisie du dépôt sont traités par le support de BidVex et sont définitifs.

**5. CONFLITS D'ENCHÈRES INTRA-COURTIER**
Les acheteurs d'un même courtier ne peuvent pas enchérir les uns contre les autres sur le même véhicule. La plateforme BidVex applique automatiquement cette règle. Si un conflit est détecté, la deuxième enchère est bloquée et le courtier est notifié. Toute tentative de contourner cette règle via plusieurs comptes de courtier constitue une violation des présentes Conditions et entraînera une suspension définitive.

**6. PISTE D'AUDIT ET CONSERVATION DES DOSSIERS**
Toutes les enchères placées via l'Écosystème de courtiers sont enregistrées de façon permanente avec l'attribution complète, y compris le numéro de permis du courtier, l'identité de l'acheteur, l'adresse IP et l'horodatage. Ces dossiers sont conservés pendant au moins 7 ans. Ils ne peuvent être modifiés ni supprimés par aucune partie. BidVex peut divulguer ces dossiers aux organismes provinciaux de réglementation, aux forces de l'ordre ou dans le cadre de procédures judiciaires, conformément à la loi.

**7. SUSPENSION ET RÉSILIATION DU COMPTE DE COURTIER**
BidVex peut suspendre ou résilier un compte de courtier à tout moment si : (a) le permis du courtier est révoqué ou a expiré ; (b) une activité frauduleuse est détectée ; (c) le courtier viole les présentes Conditions ; (d) un organisme de réglementation demande la suspension. À la résiliation, toutes les relations actives avec les acheteurs sont résiliées, toutes les détentions de dépôts sont libérées aux acheteurs respectifs et toutes les enchères actives sont annulées.

**8. LIMITATION DE RESPONSABILITÉ**
BidVex agit comme une plateforme technologique facilitant les connexions entre courtiers agréés, acheteurs et concessionnaires. BidVex n'est pas partie à une quelconque transaction de véhicule et n'est pas responsable des différends découlant de l'état du véhicule, du titre, du défaut de paiement ou de la non-livraison. Les courtiers et les concessionnaires sont seuls responsables du respect des règlements provinciaux sur la vente de véhicules.
"""
)


async def _append_if_missing(pages: dict, page_key: str, lang: str, marker: str, body: str) -> bool:
    """Append `body` to `pages[page_key][lang].content` if `marker` not already present."""
    if page_key not in pages:
        pages[page_key] = {}
    if lang not in pages[page_key]:
        pages[page_key][lang] = {"title": page_key.replace("_", " ").title(), "content": "", "link_type": "page", "link_value": f"/{page_key.replace('_', '-')}"}
    entry = pages[page_key][lang]
    if not isinstance(entry, dict):
        entry = {"title": page_key, "content": str(entry or ""), "link_type": "page", "link_value": f"/{page_key.replace('_', '-')}"}
        pages[page_key][lang] = entry
    current = entry.get("content") or ""
    if marker in current:
        return False
    entry["content"] = (current.rstrip() + "\n\n" + body.strip() + "\n").lstrip()
    return True


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    cfg = await db.site_config.find_one({"type": "legal_pages"}, {"_id": 0})
    if not cfg:
        # Bootstrap minimal structure
        cfg = {
            "type":  "legal_pages",
            "pages": {
                "privacy_policy": {
                    "en": {"title": "Privacy Policy", "content": "", "link_type": "page", "link_value": "/privacy-policy"},
                    "fr": {"title": "Politique de confidentialité", "content": "", "link_type": "page", "link_value": "/privacy-policy"},
                },
                "terms_of_service": {
                    "en": {"title": "Terms & Conditions", "content": "", "link_type": "page", "link_value": "/terms-of-service"},
                    "fr": {"title": "Conditions générales", "content": "", "link_type": "page", "link_value": "/terms-of-service"},
                },
            },
            "updated_at": datetime.now(timezone.utc),
        }
        await db.site_config.insert_one(cfg)
        cfg.pop("_id", None)

    pages = dict(cfg.get("pages") or {})
    changed = False

    changed |= await _append_if_missing(pages, "privacy_policy",   "en", PP_MARKER,  PP_EN)
    changed |= await _append_if_missing(pages, "privacy_policy",   "fr", PP_MARKER,  PP_FR)
    changed |= await _append_if_missing(pages, "terms_of_service", "en", TOS_MARKER, TOS_EN)
    changed |= await _append_if_missing(pages, "terms_of_service", "fr", TOS_MARKER, TOS_FR)

    if changed:
        await db.site_config.update_one(
            {"type": "legal_pages"},
            {"$set": {"pages": pages, "updated_at": datetime.now(timezone.utc), "updated_by": "broker_v5b_migration"}},
        )
        print("Broker section appended to privacy_policy + terms_of_service (EN + FR).")
    else:
        print("Broker section already present — nothing to do (idempotent).")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
