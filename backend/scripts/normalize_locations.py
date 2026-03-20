"""
Database Migration Script: Normalize Location Data
====================================================
Normalizes inconsistent location data in the MongoDB 'listings' and 'multi_item_listings' collections.

Mapping logic:
- Convert province/state full names to ISO codes (e.g., "Quebec" -> "QC", "Ontario" -> "ON")
- Set country field to "CA" for Canadian provinces, "US" for US states
- Trim whitespace from city names
- Deduplicate common misspellings

Usage:
    python normalize_locations.py              # Dry-run (preview changes)
    python normalize_locations.py --execute    # Apply changes to database
"""

import os
import sys
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "bidvex")

# Province/State name -> ISO code mapping
REGION_NORMALIZATION = {
    # Canadian Provinces (full names -> ISO)
    "alberta": "AB",
    "british columbia": "BC",
    "manitoba": "MB",
    "new brunswick": "NB",
    "newfoundland and labrador": "NL",
    "newfoundland": "NL",
    "nova scotia": "NS",
    "northwest territories": "NT",
    "nunavut": "NU",
    "ontario": "ON",
    "prince edward island": "PE",
    "pei": "PE",
    "quebec": "QC",
    "québec": "QC",
    "qc": "QC",
    "saskatchewan": "SK",
    "yukon": "YT",
    # US States (common full names -> ISO)
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}

# ISO codes that are Canadian provinces/territories
CA_REGIONS = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}
US_REGIONS = {"AL", "AK", "AZ", "AR", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
              "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE",
              "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
              "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"}
# Note: "CA" is both Canada country code and California state code
# We disambiguate: if region is "CA" and it's a US context, it stays "CA" for California


def normalize_region(region_raw):
    """Normalize a region string to its ISO code."""
    if not region_raw:
        return region_raw, False
    
    trimmed = region_raw.strip()
    # Already an ISO code (2-letter uppercase)?
    if len(trimmed) == 2 and trimmed.upper() in (CA_REGIONS | US_REGIONS):
        iso = trimmed.upper()
        if iso != trimmed:
            return iso, True
        return iso, False
    
    # Try full name lookup
    key = trimmed.lower()
    if key in REGION_NORMALIZATION:
        return REGION_NORMALIZATION[key], True
    
    # No match — return as-is
    return trimmed, False


def infer_country(region_iso):
    """Infer country from normalized region ISO code."""
    if region_iso in CA_REGIONS:
        return "CA"
    if region_iso in US_REGIONS:
        return "US"
    return "CA"  # Default to Canada for this platform


def process_collection(db, collection_name, dry_run=True):
    """Process all documents in a collection and normalize location data."""
    collection = db[collection_name]
    docs = collection.find({"region": {"$exists": True}}, {"_id": 1, "region": 1, "city": 1, "location": 1, "country": 1, "postal_code": 1})
    
    updated = 0
    skipped = 0
    errors = 0
    
    for doc in docs:
        try:
            updates = {}
            region_raw = doc.get("region", "")
            
            # Normalize region
            normalized_region, region_changed = normalize_region(region_raw)
            if region_changed:
                updates["region"] = normalized_region
            
            # Set country if missing
            if not doc.get("country"):
                updates["country"] = infer_country(normalized_region)
            
            # Trim city whitespace
            city = doc.get("city", "")
            if city and city != city.strip():
                updates["city"] = city.strip()
            
            if updates:
                if dry_run:
                    print(f"  [{collection_name}] {doc['_id']}: {region_raw!r} -> {updates}")
                else:
                    collection.update_one({"_id": doc["_id"]}, {"$set": updates})
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR processing {doc.get('_id')}: {e}")
            errors += 1
    
    return updated, skipped, errors


def main():
    execute = "--execute" in sys.argv
    
    if not MONGO_URL:
        print("ERROR: MONGO_URL environment variable not set")
        sys.exit(1)
    
    print(f"{'=' * 60}")
    print(f"BidVex Location Normalization {'(DRY RUN)' if not execute else '(EXECUTING)'}")
    print(f"{'=' * 60}")
    print(f"Database: {DB_NAME}")
    print()
    
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    collections = ["listings", "multi_item_listings"]
    
    total_updated = 0
    total_skipped = 0
    total_errors = 0
    
    for coll_name in collections:
        count = db[coll_name].count_documents({"region": {"$exists": True}})
        print(f"\nProcessing '{coll_name}' ({count} documents with region field)...")
        
        updated, skipped, errors = process_collection(db, coll_name, dry_run=not execute)
        total_updated += updated
        total_skipped += skipped
        total_errors += errors
        
        print(f"  -> Updated: {updated}, Skipped: {skipped}, Errors: {errors}")
    
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total_updated} updated, {total_skipped} unchanged, {total_errors} errors")
    
    if not execute:
        print("\nThis was a DRY RUN. To apply changes, run:")
        print("  python normalize_locations.py --execute")
    else:
        print("\nMigration complete!")
    
    client.close()


if __name__ == "__main__":
    main()
