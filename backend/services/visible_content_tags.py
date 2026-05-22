"""
iter219 — Storage Locker "Visible Content Tags" definitions + helpers.

The facility manager can optionally tag what they can see inside the unit
(boxes, tools, furniture, etc.) — buyers then filter by these tags on the
`/storage-auctions` browse page.

Tags are stored as ENGLISH SLUGS in MongoDB; the bilingual labels live on
the frontend. The canonical slug list is the source of truth — any payload
value that's not in this list is silently dropped (the tag system is
optional, so unknown values must NEVER block listing creation).
"""

# Canonical English slugs accepted by the API + stored in the DB.
# Bilingual labels live in CreateListingPage.js / StorageAuctionsBrowse.js.
ALLOWED_CONTENT_TAGS = (
    "boxes",          # Boîtes
    "tools",          # Outils
    "furniture",      # Meubles
    "electronics",    # Électronique
    "sporting_goods", # Articles de sport
    "appliances",     # Électroménagers
    "miscellaneous",  # Divers
)

# Permissive aliases — accept common French / casing variants and normalize
# them to canonical slugs. Keeps the contract forgiving for older clients +
# admin tooling.
_TAG_ALIASES = {
    "box":              "boxes",
    "boite":            "boxes",
    "boites":           "boxes",
    "boîte":            "boxes",
    "boîtes":           "boxes",
    "tool":             "tools",
    "outil":            "tools",
    "outils":           "tools",
    "meuble":           "furniture",
    "meubles":          "furniture",
    "electronic":       "electronics",
    "électronique":     "electronics",
    "electronique":     "electronics",
    "sport":            "sporting_goods",
    "sports":           "sporting_goods",
    "sporting_good":    "sporting_goods",
    "articles_de_sport": "sporting_goods",
    "appliance":        "appliances",
    "électroménager":   "appliances",
    "electromenager":   "appliances",
    "electromenagers":  "appliances",
    "électroménagers":  "appliances",
    "misc":             "miscellaneous",
    "divers":           "miscellaneous",
}


def sanitize_visible_content_tags(raw):
    """Normalize an incoming `visible_content_tags` payload.

    Returns a deduplicated list of canonical slugs. Unknown values are
    dropped silently — the tag system is OPTIONAL and must never block
    listing creation.
    """
    if not raw:
        return []
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in raw:
        if not isinstance(v, str):
            continue
        s = v.strip().lower().replace(" ", "_").replace("-", "_")
        if not s:
            continue
        canonical = _TAG_ALIASES.get(s, s)
        if canonical in ALLOWED_CONTENT_TAGS and canonical not in seen:
            out.append(canonical)
            seen.add(canonical)
    return out
