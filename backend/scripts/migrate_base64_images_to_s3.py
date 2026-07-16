"""
Phase 5 Hotfix v4 — Migration: base64 listing images → S3.

Walks every base64 image stored in the marketplace listing collections and
re-uploads it to S3 via `services/s3_service.py`. Replaces the base64
string with the public HTTPS URL only after the upload succeeds — failures
leave the original base64 in place so the operation is fully resumable
and never destructive.

Idempotent: any value that is already an https:// URL (S3 or third-party)
is skipped. Re-running the script after partial failure picks up where it
left off.

Supported collections + image paths:
    listings              → doc.images[]               (flat string array)
    multi_item_listings   → doc.lots[].images[]        (nested string array)
    vehicle_listings      → doc.photos[].url           (object array)
    storage_auctions      → doc.photos[]               (flat string array)

Usage:
    python -m scripts.migrate_base64_images_to_s3                # full run
    python -m scripts.migrate_base64_images_to_s3 --dry-run      # report only
    python -m scripts.migrate_base64_images_to_s3 --limit 5      # process 5 docs
    python -m scripts.migrate_base64_images_to_s3 --collection listings
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Make `services.*` importable when run from /app/backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.s3_service import (  # noqa: E402
    upload_base64_to_s3, is_marketplace_s3_url, is_base64_image,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("migrate_base64_to_s3")


# ── Collection adapters ───────────────────────────────────────────────
# Each adapter knows how to (a) read the image strings out of a doc and
# (b) write them back. Adapters keep migration code DRY across the four
# slightly-different schemas.

class _Adapter:
    name: str
    collection: str
    def get_images(self, doc: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Returns [(path_key, base64_or_url), ...]. path_key is opaque
        to the adapter — used later in `set_image_at`."""
        raise NotImplementedError
    async def set_image_at(self, db, doc_id: str, path_key: str, new_url: str) -> None:
        raise NotImplementedError


class FlatImagesAdapter(_Adapter):
    """Schemas where images live at `doc.images = [str, str, ...]`.
    Used by `listings` and (with a different field) `storage_auctions`.
    """
    def __init__(self, name: str, collection: str, field: str = "images"):
        self.name = name
        self.collection = collection
        self.field = field

    def get_images(self, doc: Dict[str, Any]) -> List[Tuple[str, str]]:
        arr = doc.get(self.field) or []
        return [(f"{self.field}.{i}", v) for i, v in enumerate(arr) if isinstance(v, str)]

    async def set_image_at(self, db, doc_id: str, path_key: str, new_url: str) -> None:
        # path_key looks like "images.3" — set via positional index using
        # dollar-prefixed path: `images.3` is valid Mongo dot-notation.
        await db[self.collection].update_one(
            {"id": doc_id},
            {"$set": {path_key: new_url}},
        )


class MultiItemAdapter(_Adapter):
    """Schema where images live at `doc.lots[].images[]`."""
    name = "multi_item_listings"
    collection = "multi_item_listings"

    def get_images(self, doc: Dict[str, Any]) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        for li, lot in enumerate(doc.get("lots") or []):
            for i, v in enumerate(lot.get("images") or []):
                if isinstance(v, str):
                    out.append((f"lots.{li}.images.{i}", v))
        return out

    async def set_image_at(self, db, doc_id: str, path_key: str, new_url: str) -> None:
        await db[self.collection].update_one(
            {"id": doc_id},
            {"$set": {path_key: new_url}},
        )


class VehiclePhotosAdapter(_Adapter):
    """Schema where photos live at `doc.photos = [{"url": str, ...}, ...]`."""
    name = "vehicle_listings"
    collection = "vehicle_listings"

    def get_images(self, doc: Dict[str, Any]) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        for i, p in enumerate(doc.get("photos") or []):
            if isinstance(p, dict) and isinstance(p.get("url"), str):
                out.append((f"photos.{i}.url", p["url"]))
        return out

    async def set_image_at(self, db, doc_id: str, path_key: str, new_url: str) -> None:
        await db[self.collection].update_one(
            {"id": doc_id},
            {"$set": {path_key: new_url}},
        )


ADAPTERS: Dict[str, _Adapter] = {
    "listings":            FlatImagesAdapter("listings", "listings", "images"),
    "multi_item_listings": MultiItemAdapter(),
    "vehicle_listings":    VehiclePhotosAdapter(),
    "storage_auctions":    FlatImagesAdapter("storage_auctions", "storage_auctions", "photos"),
}


def _needs_migration(value: str) -> bool:
    """True for base64 strings (data URLs or bare). Skip if already an https URL."""
    if not isinstance(value, str) or not value:
        return False
    if value.startswith("http://") or value.startswith("https://"):
        return False
    return is_base64_image(value)


async def _migrate_doc(
    db,
    adapter: _Adapter,
    doc: Dict[str, Any],
    dry_run: bool,
) -> Tuple[int, int, int, List[Dict[str, str]]]:
    """Migrate one document. Returns (migrated, skipped, failed, migrated_rows).
    `migrated_rows` is a list of {"collection", "listing_id", "path", "url"}
    entries — used by the scheduler alert to identify affected docs."""
    images = adapter.get_images(doc)
    migrated = skipped = failed = 0
    migrated_rows: List[Dict[str, str]] = []

    for path_key, value in images:
        if not _needs_migration(value):
            skipped += 1
            continue

        if dry_run:
            logger.info(
                "[DRY-RUN] %s/%s -> would upload (%d bytes base64)",
                adapter.collection, doc["id"], len(value),
            )
            migrated += 1
            migrated_rows.append({
                "collection": adapter.collection,
                "listing_id": doc["id"],
                "path": path_key,
                "url": "(dry-run)",
            })
            continue

        # Derive an integer index from the path_key for the S3 key suffix
        try:
            idx = int(path_key.rsplit(".", 1)[-1].rstrip("url").rstrip("."))
        except (ValueError, TypeError):
            idx = 0

        try:
            new_url = await upload_base64_to_s3(value, doc["id"], idx)
            await adapter.set_image_at(db, doc["id"], path_key, new_url)
            logger.info(
                "MIGRATED %s/%s %s -> %s",
                adapter.collection, doc["id"], path_key, new_url,
            )
            migrated += 1
            migrated_rows.append({
                "collection": adapter.collection,
                "listing_id": doc["id"],
                "path": path_key,
                "url": new_url,
            })
        except Exception as e:
            logger.warning(
                "FAILED  %s/%s %s — %s (base64 left intact, will retry next run)",
                adapter.collection, doc["id"], path_key, e,
            )
            failed += 1

    return migrated, skipped, failed, migrated_rows


async def _run(args) -> int:
    mongo_url = os.environ["MONGO_URL"]
    db_name   = os.environ["DB_NAME"]
    client    = AsyncIOMotorClient(mongo_url)
    db        = client[db_name]

    target = (args.collection or "").strip()
    if target and target not in ADAPTERS:
        logger.error("Unknown collection '%s'. Valid: %s", target, list(ADAPTERS))
        return 2

    targets = [ADAPTERS[target]] if target else list(ADAPTERS.values())

    grand = {"migrated": 0, "skipped": 0, "failed": 0, "docs": 0}

    try:
        for adapter in targets:
            logger.info("─── %s ───", adapter.collection)
            cursor = db[adapter.collection].find({}, {"_id": 0})
            if args.limit:
                cursor = cursor.limit(int(args.limit))

            async for doc in cursor:
                if not doc.get("id"):
                    continue
                m, s, f, _rows = await _migrate_doc(db, adapter, doc, args.dry_run)
                grand["migrated"] += m
                grand["skipped"]  += s
                grand["failed"]   += f
                grand["docs"]     += 1

        logger.info("───")
        logger.info(
            "Done. docs=%d  migrated=%d  skipped=%d  failed=%d  dry_run=%s",
            grand["docs"], grand["migrated"], grand["skipped"], grand["failed"],
            args.dry_run,
        )
    finally:
        client.close()

    return 0 if grand["failed"] == 0 else 1


def main():
    p = argparse.ArgumentParser(description="Migrate base64 listing images to S3.")
    p.add_argument("--dry-run",    action="store_true", help="Report only — no uploads.")
    p.add_argument("--limit",      type=int, default=None, help="Max docs per collection.")
    p.add_argument("--collection", type=str, default=None,
                   help="Only migrate this collection. Valid: " + ", ".join(ADAPTERS))
    args = p.parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
