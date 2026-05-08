"""
iter201 — Phase 1 / Seed: province_regulations collection.

Idempotent — safe to re-run. Uses `upsert` keyed on `province_code`.

Authoritative source: BidVex CEO spec for Vehicle Auctions Canadian Legal Compliance.

Seeds all 13 jurisdictions with:
  • Regulatory body, license type (EN/FR), license-verification URL
  • Whether individual buyers may bid (boolean)
  • Whether bilingual listings are mandatory (QC, NB)
  • Tax structure (GST / PST_QST / HST as applicable)
  • Bilingual buyer-gate + seller-notice copy
  • Full bilingual name of each province / territory

Run:
    cd /app/backend && python migrations/seed_province_regulations.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


PROVINCES = [
    # ───────── BC — individual buyers allowed ─────────
    {
        "province_code": "BC",
        "province_name_en": "British Columbia",
        "province_name_fr": "Colombie-Britannique",
        "regulatory_body": "VSA — Vehicle Sales Authority of BC",
        "license_type_en": "VSA Motor Dealer Licence",
        "license_type_fr": "Permis de concessionnaire de véhicules de la VSA",
        "license_verification_url": "https://www.vsabc.ca",
        "individual_buyers_allowed": True,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": 0.05, "PST_QST": 0.07, "HST": None},
        "buyer_gate_message_en": "Individual buyers may purchase vehicles at auction in British Columbia.",
        "buyer_gate_message_fr": "Les acheteurs individuels peuvent acheter des véhicules aux enchères en Colombie-Britannique.",
        "seller_notice_en": "To list vehicles in BC, you must hold a valid VSA Motor Dealer Licence issued by the Vehicle Sales Authority of British Columbia.",
        "seller_notice_fr": "Pour inscrire des véhicules en Colombie-Britannique, vous devez détenir un permis valide de concessionnaire de véhicules délivré par la Vehicle Sales Authority of BC.",
        "additional_requirements_en": [
            "VSA-compliant disclosure: prior use, accident history, lien status",
            "CARFAX or equivalent vehicle history report",
        ],
        "additional_requirements_fr": [
            "Divulgation conforme à la VSA : usage antérieur, historique d'accidents, statut des privilèges",
            "Rapport d'historique CARFAX ou équivalent",
        ],
    },
    # ───────── AB — individual buyers allowed ─────────
    {
        "province_code": "AB",
        "province_name_en": "Alberta",
        "province_name_fr": "Alberta",
        "regulatory_body": "AMVIC — Alberta Motor Vehicle Industry Council",
        "license_type_en": "AMVIC Dealer Licence",
        "license_type_fr": "Permis de concessionnaire AMVIC",
        "license_verification_url": "https://www.amvic.org",
        "individual_buyers_allowed": True,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": 0.05, "PST_QST": 0.0, "HST": None},
        "buyer_gate_message_en": "Individual buyers may purchase vehicles at auction in Alberta.",
        "buyer_gate_message_fr": "Les acheteurs individuels peuvent acheter des véhicules aux enchères en Alberta.",
        "seller_notice_en": "To list vehicles in Alberta, you must hold a valid AMVIC Dealer Licence issued by the Alberta Motor Vehicle Industry Council.",
        "seller_notice_fr": "Pour inscrire des véhicules en Alberta, vous devez détenir un permis de concessionnaire AMVIC valide délivré par l'Alberta Motor Vehicle Industry Council.",
        "additional_requirements_en": [
            "AMVIC-compliant written disclosure",
            "Consignment > 5 vehicles/year requires consignor AMVIC registration",
        ],
        "additional_requirements_fr": [
            "Divulgation écrite conforme à l'AMVIC",
            "Pour les ventes en consignation > 5 véhicules/an, le consignateur doit aussi être inscrit AMVIC",
        ],
    },
    # ───────── SK — individual buyers allowed ─────────
    {
        "province_code": "SK",
        "province_name_en": "Saskatchewan",
        "province_name_fr": "Saskatchewan",
        "regulatory_body": "FCAA — Financial and Consumer Affairs Authority of Saskatchewan",
        "license_type_en": "Motor Vehicle Dealer Licence (FCAA / SGI)",
        "license_type_fr": "Permis de concessionnaire de véhicules (FCAA / SGI)",
        "license_verification_url": "https://fcaa.gov.sk.ca",
        "individual_buyers_allowed": True,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": 0.05, "PST_QST": 0.06, "HST": None},
        "buyer_gate_message_en": "Individual buyers may purchase vehicles at auction in Saskatchewan.",
        "buyer_gate_message_fr": "Les acheteurs individuels peuvent acheter des véhicules aux enchères en Saskatchewan.",
        "seller_notice_en": "To list vehicles in Saskatchewan, you must be registered as a Motor Vehicle Dealer under the FCAA Motor Vehicle Dealers Act, 2009.",
        "seller_notice_fr": "Pour inscrire des véhicules en Saskatchewan, vous devez être inscrit comme concessionnaire en vertu de la Motor Vehicle Dealers Act, 2009 de la FCAA.",
        "additional_requirements_en": [
            "Mechanical condition + lien search disclosure",
            "SGI vehicle registration transfer required within 14 days of sale",
        ],
        "additional_requirements_fr": [
            "Divulgation de l'état mécanique et recherche de privilèges",
            "Transfert SGI requis dans les 14 jours suivant la vente",
        ],
    },
    # ───────── MB — individual buyers allowed ─────────
    {
        "province_code": "MB",
        "province_name_en": "Manitoba",
        "province_name_fr": "Manitoba",
        "regulatory_body": "Manitoba Consumer Protection Office",
        "license_type_en": "Manitoba Vehicle Dealer Licence",
        "license_type_fr": "Permis de concessionnaire de véhicules du Manitoba",
        "license_verification_url": "https://www.gov.mb.ca/cca/cpo/",
        "individual_buyers_allowed": True,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": 0.05, "PST_QST": 0.07, "HST": None},
        "buyer_gate_message_en": "Individual buyers may purchase vehicles at auction in Manitoba.",
        "buyer_gate_message_fr": "Les acheteurs individuels peuvent acheter des véhicules aux enchères au Manitoba.",
        "seller_notice_en": "To list vehicles in Manitoba, you must hold a valid Vehicle Dealer Licence issued under Manitoba's Vehicle and Motor Vehicle Parts Dealers Act.",
        "seller_notice_fr": "Pour inscrire des véhicules au Manitoba, vous devez détenir un permis valide en vertu de la Vehicle and Motor Vehicle Parts Dealers Act du Manitoba.",
        "additional_requirements_en": [
            "Manitoba-compliant bill of sale",
            "PPSR lien search mandatory before listing",
        ],
        "additional_requirements_fr": [
            "Acte de vente conforme aux exigences du Manitoba",
            "Recherche de privilèges PPSR obligatoire avant l'inscription",
        ],
    },
    # ───────── ON — individual buyers RESTRICTED ─────────
    {
        "province_code": "ON",
        "province_name_en": "Ontario",
        "province_name_fr": "Ontario",
        "regulatory_body": "OMVIC — Ontario Motor Vehicle Industry Council",
        "license_type_en": "OMVIC Dealer Registration Certificate",
        "license_type_fr": "Certificat d'inscription de concessionnaire OMVIC",
        "license_verification_url": "https://www.omvic.ca",
        "individual_buyers_allowed": False,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": None, "PST_QST": None, "HST": 0.13},
        "buyer_gate_message_en": "Under Ontario's OMVIC regulations, purchasing vehicles from dealer auctions requires buyer registration or purchasing through a licensed OMVIC dealer. Please confirm your buyer eligibility before bidding.",
        "buyer_gate_message_fr": "En vertu des règlements de l'OMVIC en Ontario, l'achat de véhicules aux enchères de concessionnaires nécessite une inscription ou l'achat par l'intermédiaire d'un concessionnaire OMVIC licencié. Veuillez confirmer votre éligibilité avant d'enchérir.",
        "seller_notice_en": "To list vehicles in Ontario, you must hold a valid OMVIC Dealer Registration Certificate and comply with the OMVIC Code of Ethics.",
        "seller_notice_fr": "Pour inscrire des véhicules en Ontario, vous devez détenir un certificat d'inscription OMVIC valide et respecter le code d'éthique de l'OMVIC.",
        "additional_requirements_en": [
            "OMVIC-compliant vehicle disclosure (Form 1 or equivalent)",
            "OMVIC Code of Ethics attestation",
            "Trust account for buyer deposits",
            "UVIP equivalent disclosure",
        ],
        "additional_requirements_fr": [
            "Divulgation conforme OMVIC (Formulaire 1 ou équivalent)",
            "Attestation du code d'éthique OMVIC",
            "Compte en fiducie pour les dépôts des acheteurs",
            "Divulgation équivalente UVIP",
        ],
    },
    # ───────── QC — individual buyers ALLOWED with disclosure (Q1=c) ─────────
    {
        "province_code": "QC",
        "province_name_en": "Quebec",
        "province_name_fr": "Québec",
        "regulatory_body": "SAAQ / CCAQ — Société de l'assurance automobile du Québec",
        "license_type_en": "Road-vehicle dealer licence (SAAQ)",
        "license_type_fr": "Licence de commerçant de véhicules routiers (SAAQ)",
        "license_verification_url": "https://saaq.gouv.qc.ca",
        # CEO direction (Q1=c): allow individuals with mandatory LPC disclosure acknowledgement
        "individual_buyers_allowed": True,
        "individual_buyers_require_disclosure_ack": True,
        "requires_bilingual_listings": True,
        "primary_listing_language": "fr",
        "tax_rates": {"GST": 0.05, "PST_QST": 0.09975, "HST": None},
        "buyer_gate_message_en": "Quebec buyers: vehicle auction purchases are subject to Quebec's Consumer Protection Act (LPC). Confirm your eligibility and acknowledge the LPC disclosure before bidding.",
        "buyer_gate_message_fr": "Acheteurs du Québec : l'achat de véhicules aux enchères est soumis à la Loi sur la protection du consommateur (LPC) du Québec. Confirmez votre éligibilité et reconnaissez la divulgation LPC avant d'enchérir.",
        "seller_notice_en": "To list vehicles in Quebec, you must hold a valid SAAQ road-vehicle dealer licence and a Quebec Enterprise Number (NEQ). All listing content must be in French (English may be added as a secondary language).",
        "seller_notice_fr": "Pour inscrire des véhicules au Québec, vous devez détenir une licence valide de commerçant de véhicules routiers (SAAQ) et un Numéro d'entreprise du Québec (NEQ). Tout contenu d'annonce doit être en français (l'anglais peut être ajouté comme langue secondaire).",
        "additional_requirements_en": [
            "NEQ (Quebec Enterprise Number) — mandatory",
            "French-language compliance (Charter of the French Language)",
            "LPC-compliant disclosure: condition, prior accidents, liens, odometer, previous use",
        ],
        "additional_requirements_fr": [
            "NEQ (Numéro d'entreprise du Québec) — obligatoire",
            "Conformité linguistique française (Charte de la langue française)",
            "Divulgation conforme à la LPC : état, accidents antérieurs, privilèges, odomètre, usage antérieur",
        ],
    },
    # ───────── NB — individual buyers RESTRICTED, bilingual mandatory ─────────
    {
        "province_code": "NB",
        "province_name_en": "New Brunswick",
        "province_name_fr": "Nouveau-Brunswick",
        "regulatory_body": "Service New Brunswick / FCNB",
        "license_type_en": "NB Motor Vehicle Dealer Licence",
        "license_type_fr": "Permis de concessionnaire de véhicules du Nouveau-Brunswick",
        "license_verification_url": "https://www2.snb.ca",
        "individual_buyers_allowed": False,
        "requires_bilingual_listings": True,
        "tax_rates": {"GST": None, "PST_QST": None, "HST": 0.15},
        "buyer_gate_message_en": "New Brunswick auction regulations require buyer dealer registration for commercial auction purchases.",
        "buyer_gate_message_fr": "Les règlements du Nouveau-Brunswick exigent l'inscription du concessionnaire acheteur pour les achats d'enchères commerciales.",
        "seller_notice_en": "To list vehicles in New Brunswick, you must hold a valid NB Motor Vehicle Dealer Licence. Listings must be available in both English and French (NB Official Languages Act).",
        "seller_notice_fr": "Pour inscrire des véhicules au Nouveau-Brunswick, vous devez détenir un permis valide. Les annonces doivent être disponibles en anglais et en français (Loi sur les langues officielles du N.-B.).",
        "additional_requirements_en": ["Bilingual listing required (EN + FR)"],
        "additional_requirements_fr": ["Annonce bilingue requise (FR + EN)"],
    },
    # ───────── NS — individual buyers RESTRICTED ─────────
    {
        "province_code": "NS",
        "province_name_en": "Nova Scotia",
        "province_name_fr": "Nouvelle-Écosse",
        "regulatory_body": "Service Nova Scotia — Motor Vehicle Act",
        "license_type_en": "NS Motor Vehicle Dealer Licence",
        "license_type_fr": "Permis de concessionnaire de véhicules de la Nouvelle-Écosse",
        "license_verification_url": "https://novascotia.ca",
        "individual_buyers_allowed": False,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": None, "PST_QST": None, "HST": 0.15},
        "buyer_gate_message_en": "Nova Scotia restricts wholesale auction purchases to licensed dealers.",
        "buyer_gate_message_fr": "La Nouvelle-Écosse limite les achats d'enchères en gros aux concessionnaires licenciés.",
        "seller_notice_en": "To list vehicles in Nova Scotia, you must hold a valid NS Motor Vehicle Dealer Licence and disclose mandatory mechanical inspection results.",
        "seller_notice_fr": "Pour inscrire des véhicules en Nouvelle-Écosse, vous devez détenir un permis valide et divulguer les résultats de l'inspection mécanique obligatoire.",
        "additional_requirements_en": ["Mandatory mechanical inspection disclosure"],
        "additional_requirements_fr": ["Divulgation obligatoire de l'inspection mécanique"],
    },
    # ───────── PE — individual buyers RESTRICTED ─────────
    {
        "province_code": "PE",
        "province_name_en": "Prince Edward Island",
        "province_name_fr": "Île-du-Prince-Édouard",
        "regulatory_body": "PEI Consumer, Labour and Financial Services Division",
        "license_type_en": "PEI Motor Vehicle Dealer Licence",
        "license_type_fr": "Permis de concessionnaire de véhicules de l'Î.-P.-É.",
        "license_verification_url": "https://www.princeedwardisland.ca",
        "individual_buyers_allowed": False,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": None, "PST_QST": None, "HST": 0.15},
        "buyer_gate_message_en": "PEI follows Atlantic Canada standards — commercial auction purchases require dealer standing.",
        "buyer_gate_message_fr": "L'Î.-P.-É. suit les normes du Canada atlantique — les achats d'enchères commerciales exigent un statut de concessionnaire.",
        "seller_notice_en": "To list vehicles in PEI, you must hold a valid PEI Motor Vehicle Dealer Licence.",
        "seller_notice_fr": "Pour inscrire des véhicules à l'Î.-P.-É., vous devez détenir un permis valide.",
        "additional_requirements_en": [],
        "additional_requirements_fr": [],
    },
    # ───────── NL — individual buyers RESTRICTED ─────────
    {
        "province_code": "NL",
        "province_name_en": "Newfoundland and Labrador",
        "province_name_fr": "Terre-Neuve-et-Labrador",
        "regulatory_body": "Service NL — Motor Vehicle Registration Act",
        "license_type_en": "NL Motor Vehicle Dealer Licence",
        "license_type_fr": "Permis de concessionnaire de véhicules de Terre-Neuve-et-Labrador",
        "license_verification_url": "https://www.gov.nl.ca/snl/",
        "individual_buyers_allowed": False,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": None, "PST_QST": None, "HST": 0.15},
        "buyer_gate_message_en": "Commercial vehicle auctions in NL require dealer registration to purchase.",
        "buyer_gate_message_fr": "Les enchères commerciales à T.-N.-L. exigent une inscription de concessionnaire pour acheter.",
        "seller_notice_en": "To list vehicles in Newfoundland and Labrador, you must hold a valid NL Motor Vehicle Dealer Licence.",
        "seller_notice_fr": "Pour inscrire des véhicules à Terre-Neuve-et-Labrador, vous devez détenir un permis valide.",
        "additional_requirements_en": [],
        "additional_requirements_fr": [],
    },
    # ───────── Yukon — territorial, individual buyers allowed (advisory) ─────────
    {
        "province_code": "YT",
        "province_name_en": "Yukon",
        "province_name_fr": "Yukon",
        "regulatory_body": "Yukon Motor Vehicles Branch",
        "license_type_en": "Yukon dealer registration (varies)",
        "license_type_fr": "Inscription de concessionnaire du Yukon (varie)",
        "license_verification_url": "https://yukon.ca",
        "individual_buyers_allowed": True,
        "requires_admin_review": True,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": 0.05, "PST_QST": 0.0, "HST": None},
        "buyer_gate_message_en": "Yukon has limited dealer-licensing structure. Listings are flagged for BidVex compliance review before going live.",
        "buyer_gate_message_fr": "Le Yukon a une structure réglementaire limitée. Les annonces sont signalées pour examen de conformité BidVex avant la publication.",
        "seller_notice_en": "To list vehicles in Yukon, BidVex requires manual compliance review. Contact Yukon Motor Vehicles Branch for territorial requirements.",
        "seller_notice_fr": "Pour inscrire des véhicules au Yukon, BidVex exige un examen manuel de conformité. Contactez la direction des véhicules motorisés du Yukon.",
        "additional_requirements_en": ["Territorial — manual BidVex compliance review required"],
        "additional_requirements_fr": ["Territoire — examen manuel de conformité BidVex requis"],
    },
    # ───────── NT — territorial ─────────
    {
        "province_code": "NT",
        "province_name_en": "Northwest Territories",
        "province_name_fr": "Territoires du Nord-Ouest",
        "regulatory_body": "Infrastructure NWT — Motor Vehicles Act",
        "license_type_en": "NWT dealer registration (varies)",
        "license_type_fr": "Inscription de concessionnaire des T.N.-O. (varie)",
        "license_verification_url": "https://www.inf.gov.nt.ca",
        "individual_buyers_allowed": True,
        "requires_admin_review": True,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": 0.05, "PST_QST": 0.0, "HST": None},
        "buyer_gate_message_en": "Northwest Territories has limited dealer-licensing structure. Listings are flagged for BidVex compliance review before going live.",
        "buyer_gate_message_fr": "Les T.N.-O. ont une structure réglementaire limitée. Les annonces sont signalées pour examen de conformité BidVex avant la publication.",
        "seller_notice_en": "To list vehicles in NWT, BidVex requires manual compliance review. Contact Infrastructure NWT for territorial requirements.",
        "seller_notice_fr": "Pour inscrire des véhicules aux T.N.-O., BidVex exige un examen manuel de conformité. Contactez Infrastructure T.N.-O.",
        "additional_requirements_en": ["Territorial — manual BidVex compliance review required"],
        "additional_requirements_fr": ["Territoire — examen manuel de conformité BidVex requis"],
    },
    # ───────── NU — territorial ─────────
    {
        "province_code": "NU",
        "province_name_en": "Nunavut",
        "province_name_fr": "Nunavut",
        "regulatory_body": "Government of Nunavut — Motor Vehicles Act",
        "license_type_en": "Nunavut dealer registration (varies)",
        "license_type_fr": "Inscription de concessionnaire du Nunavut (varie)",
        "license_verification_url": "https://www.gov.nu.ca",
        "individual_buyers_allowed": True,
        "requires_admin_review": True,
        "requires_bilingual_listings": False,
        "tax_rates": {"GST": 0.05, "PST_QST": 0.0, "HST": None},
        "buyer_gate_message_en": "Nunavut has limited dealer-licensing structure. Listings are flagged for BidVex compliance review before going live.",
        "buyer_gate_message_fr": "Le Nunavut a une structure réglementaire limitée. Les annonces sont signalées pour examen de conformité BidVex avant la publication.",
        "seller_notice_en": "To list vehicles in Nunavut, BidVex requires manual compliance review. Contact the Government of Nunavut for territorial requirements.",
        "seller_notice_fr": "Pour inscrire des véhicules au Nunavut, BidVex exige un examen manuel de conformité. Contactez le gouvernement du Nunavut.",
        "additional_requirements_en": ["Territorial — manual BidVex compliance review required"],
        "additional_requirements_fr": ["Territoire — examen manuel de conformité BidVex requis"],
    },
]


async def seed_provinces(verbose: bool = True) -> dict:
    """Idempotent upsert of all 13 jurisdictions. Returns a per-code report."""
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    coll = db.province_regulations
    await coll.create_index("province_code", unique=True)

    report = {"upserted": [], "modified": [], "unchanged": []}
    now = datetime.now(timezone.utc)

    for prov in PROVINCES:
        code = prov["province_code"]
        # Add audit timestamps
        update_doc = {**prov, "updated_at": now}
        existing = await coll.find_one(
            {"province_code": code}, {"_id": 0, "updated_at": 0, "created_at": 0}
        )
        result = await coll.update_one(
            {"province_code": code},
            {"$set": update_doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        if result.upserted_id is not None:
            report["upserted"].append(code)
        elif existing != prov:
            report["modified"].append(code)
        else:
            report["unchanged"].append(code)

    total = await coll.count_documents({})
    if verbose:
        print(f"[seed_province_regulations] total docs: {total}")
        print(f"  upserted: {report['upserted']}")
        print(f"  modified: {report['modified']}")
        print(f"  unchanged: {report['unchanged']}")

    cli.close()
    return {**report, "total": total}


if __name__ == "__main__":
    res = asyncio.run(seed_provinces())
    if res["total"] != len(PROVINCES):
        print(f"WARNING: expected {len(PROVINCES)} docs, got {res['total']}", file=sys.stderr)
        sys.exit(1)
    print("✅ province_regulations seed complete.")
