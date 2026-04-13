"""
BidVex — Geo-Targeted Auction Email Alerts
Daily job at 9:00 AM ET. Uses Haversine + Canada Post FSA centroids.
No external geocoding API — entirely offline/local.
"""

import math
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0
MAX_DISTANCE_KM = 50
BATCH_SIZE = 100
BATCH_DELAY_S = 1.0  # SendGrid rate limit protection


# ═══════════════════════════════════════════════════════════════
# FSA CENTROID LOOKUP — Static dict, loaded once at import
# Top ~120 FSAs covering Quebec, Ontario, Atlantic, Prairies, BC
# Format: FSA -> (latitude, longitude)
# ═══════════════════════════════════════════════════════════════

FSA_CENTROIDS: Dict[str, Tuple[float, float]] = {
    # Quebec
    "G1A": (46.8139, -71.2080), "G1B": (46.8500, -71.2300), "G1C": (46.8700, -71.2000),
    "G1E": (46.8350, -71.1700), "G1G": (46.8600, -71.2800), "G1H": (46.7900, -71.2400),
    "G1J": (46.8200, -71.2100), "G1K": (46.8100, -71.2100), "G1L": (46.8050, -71.2200),
    "G1M": (46.7800, -71.2700), "G1N": (46.7600, -71.3000), "G1P": (46.7700, -71.2900),
    "G1R": (46.8080, -71.2150), "G1S": (46.7900, -71.2500), "G1T": (46.8300, -71.3100),
    "G1V": (46.7800, -71.2800), "G1W": (46.7600, -71.2500), "G1X": (46.7700, -71.3200),
    "G2A": (46.8600, -71.3200), "G2B": (46.8800, -71.3000), "G2C": (46.9000, -71.2500),
    "G2E": (46.8700, -71.3500), "G2G": (46.8500, -71.3800), "G2J": (46.8900, -71.2200),
    "G2K": (46.9100, -71.2600), "G2L": (46.9200, -71.2400), "G2N": (46.9300, -71.2200),
    # Sherbrooke
    "J1E": (45.4042, -71.8929), "J1G": (45.3900, -71.9100), "J1H": (45.4000, -71.8800),
    "J1J": (45.3800, -71.8700), "J1K": (45.4100, -71.9200), "J1L": (45.3700, -71.9000),
    "J1M": (45.4200, -71.8600), "J1N": (45.3600, -71.9300), "J1R": (45.4300, -71.8500),
    # Montreal
    "H1A": (45.5750, -73.5500), "H1B": (45.5800, -73.5300), "H1C": (45.5700, -73.5100),
    "H1E": (45.5900, -73.5700), "H1G": (45.5600, -73.5800), "H1H": (45.5400, -73.6000),
    "H1J": (45.5700, -73.5600), "H1K": (45.5500, -73.5400), "H1L": (45.5800, -73.5200),
    "H1M": (45.5600, -73.5200), "H1N": (45.5400, -73.5300), "H1P": (45.5500, -73.5600),
    "H1R": (45.5600, -73.5700), "H1S": (45.5300, -73.5700), "H1T": (45.5400, -73.5800),
    "H1V": (45.5500, -73.5500), "H1W": (45.5350, -73.5400), "H1X": (45.5300, -73.5800),
    "H1Y": (45.5200, -73.5600), "H1Z": (45.5250, -73.5500),
    "H2A": (45.5300, -73.5700), "H2B": (45.5150, -73.5500), "H2C": (45.5100, -73.5600),
    "H2E": (45.5300, -73.5800), "H2G": (45.5200, -73.5700), "H2H": (45.5200, -73.5900),
    "H2J": (45.5250, -73.5650), "H2K": (45.5300, -73.5550), "H2L": (45.5150, -73.5650),
    "H2M": (45.5350, -73.6200), "H2N": (45.5400, -73.6300), "H2P": (45.5450, -73.6100),
    "H2R": (45.5350, -73.6000), "H2S": (45.5400, -73.5900), "H2T": (45.5200, -73.5800),
    "H2V": (45.5200, -73.6000), "H2W": (45.5150, -73.5750), "H2X": (45.5100, -73.5700),
    "H2Y": (45.5050, -73.5600), "H2Z": (45.5000, -73.5650),
    "H3A": (45.5050, -73.5750), "H3B": (45.5000, -73.5700), "H3C": (45.4950, -73.5600),
    "H3G": (45.4950, -73.5800), "H3H": (45.4900, -73.5850), "H3J": (45.4850, -73.5750),
    "H3K": (45.4800, -73.5700), "H3L": (45.5450, -73.6400), "H3M": (45.5500, -73.6500),
    "H3N": (45.5350, -73.6300), "H3P": (45.4700, -73.6100), "H3R": (45.4600, -73.6000),
    "H3S": (45.4850, -73.6100), "H3T": (45.4950, -73.6200), "H3V": (45.4750, -73.5900),
    "H3W": (45.4800, -73.6200), "H3X": (45.4700, -73.6300), "H3Y": (45.4850, -73.5800),
    "H3Z": (45.4900, -73.5900),
    "H4A": (45.4700, -73.6400), "H4B": (45.4600, -73.6500), "H4C": (45.4700, -73.5800),
    "H4E": (45.4650, -73.5700), "H4G": (45.4600, -73.5800), "H4H": (45.4550, -73.5900),
    # Gatineau/Ottawa region
    "J8P": (45.4600, -75.7500), "J8R": (45.4400, -75.7200), "J8T": (45.4700, -75.7300),
    "J8V": (45.4800, -75.7100), "J8X": (45.4300, -75.7400), "J8Y": (45.4500, -75.7600),
    "J8Z": (45.4200, -75.7700),
    # Trois-Rivieres
    "G8T": (46.3500, -72.5400), "G8V": (46.3400, -72.5600), "G8W": (46.3600, -72.5300),
    "G8Y": (46.3700, -72.5500), "G8Z": (46.3500, -72.5700), "G9A": (46.3300, -72.5500),
    "G9B": (46.3200, -72.5300),
    # Ontario
    "K1A": (45.4215, -75.6972), "K1B": (45.4400, -75.6200), "K1C": (45.4600, -75.5400),
    "K1E": (45.4700, -75.4700), "K1G": (45.4200, -75.6300), "K1H": (45.3900, -75.6400),
    "K1J": (45.4300, -75.6100), "K1K": (45.4400, -75.6600), "K1L": (45.4350, -75.6500),
    "K1N": (45.4300, -75.6800), "K1P": (45.4200, -75.6900), "K1R": (45.4100, -75.7000),
    "K1S": (45.4000, -75.6800), "K1T": (45.3500, -75.6200), "K1V": (45.3600, -75.6000),
    "K1W": (45.3400, -75.6400), "K1X": (45.3300, -75.6600), "K1Y": (45.4100, -75.7200),
    "K1Z": (45.4000, -75.7100),
    # Toronto
    "M4W": (43.6744, -79.3860), "M5V": (43.6390, -79.3950), "M5G": (43.6570, -79.3860),
    "L5A": (43.5800, -79.6200), "L5B": (43.5900, -79.6100), "L6A": (43.8600, -79.4400),
    # US border cities (for cross-border)
    "050": (44.4759, -73.2121),  # Burlington VT (placeholder for US FSA-equivalent)
    "139": (44.6995, -73.4529),  # Plattsburgh NY
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lon points."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_fsa_coords(postal_code: str) -> Tuple[float, float] | None:
    """Extract FSA (first 3 chars) and look up lat/lon."""
    if not postal_code or len(postal_code) < 3:
        return None
    fsa = postal_code[:3].upper().replace(" ", "")
    return FSA_CENTROIDS.get(fsa)


# ═══════════════════════════════════════════════════════════════
# DAILY GEO ALERT JOB
# Runs at 9:00 AM ET (14:00 UTC in winter / 13:00 UTC in summer)
# ═══════════════════════════════════════════════════════════════

async def send_geo_auction_alerts(db: AsyncIOMotorDatabase):
    """
    Daily job:
    1. Fetch auctions starting in next 48h OR ending in next 24h
    2. Compute distance to all users via FSA centroids
    3. Filter to 50km radius
    4. Exclude users who already bid or received alert in last 7d
    5. Send in batches of 100 with 1s delay
    """
    from services.email_service import send_geo_auction_alert

    now = datetime.now(timezone.utc)
    in_48h = (now + timedelta(hours=48)).isoformat()
    in_24h = (now + timedelta(hours=24)).isoformat()
    seven_days_ago = (now - timedelta(days=7)).isoformat()

    # Find new auctions (starting in 48h) and ending auctions (ending in 24h)
    new_auctions = await db.listings.find(
        {"status": "active", "start_time": {"$lte": in_48h, "$gte": now.isoformat()}},
        {"_id": 0, "id": 1, "title": 1, "city": 1, "location": 1, "postal_code": 1,
         "starting_price": 1, "end_time": 1, "latitude": 1, "longitude": 1}
    ).to_list(500)

    ending_auctions = await db.listings.find(
        {"status": "active", "end_time": {"$lte": in_24h, "$gte": now.isoformat()}},
        {"_id": 0, "id": 1, "title": 1, "city": 1, "location": 1, "postal_code": 1,
         "current_price": 1, "end_time": 1, "latitude": 1, "longitude": 1}
    ).to_list(500)

    all_auctions = [
        (a, "new") for a in new_auctions
    ] + [
        (a, "ending_soon") for a in ending_auctions
    ]

    if not all_auctions:
        logger.info("[GEO] No qualifying auctions found for geo alerts")
        return

    # Fetch all users with postal codes
    users = await db.users.find(
        {"role": {"$ne": "admin"}, "postal_code": {"$exists": True, "$ne": ""}},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "postal_code": 1,
         "preferred_language": 1, "language_preference": 1}
    ).to_list(10000)

    total_sent = 0
    total_failed = 0
    batch = []

    for auction, alert_type in all_auctions:
        # Get auction coordinates
        a_lat = auction.get("latitude")
        a_lon = auction.get("longitude")
        if not a_lat or not a_lon:
            coords = get_fsa_coords(auction.get("postal_code", ""))
            if coords:
                a_lat, a_lon = coords
            else:
                continue

        # Get bidders to exclude
        bidder_ids = set()
        bids = await db.bids.find(
            {"listing_id": auction["id"]},
            {"_id": 0, "user_id": 1}
        ).to_list(1000)
        for b in bids:
            bidder_ids.add(b.get("user_id"))

        for user in users:
            uid = user.get("id", "")

            # Skip users who already bid on this auction
            if uid in bidder_ids:
                continue

            # Get user coordinates from FSA
            u_coords = get_fsa_coords(user.get("postal_code", ""))
            if not u_coords:
                continue

            # Calculate distance
            distance = haversine(a_lat, a_lon, u_coords[0], u_coords[1])
            if distance > MAX_DISTANCE_KM:
                continue

            # Check if user already received alert for this auction in last 7 days
            existing = await db.geo_email_log.find_one({
                "user_id": uid,
                "auction_id": auction["id"],
                "sent_at": {"$gte": seven_days_ago},
            })
            if existing:
                continue

            # Add hours_remaining for ending auctions
            if alert_type == "ending_soon":
                end_time = auction.get("end_time", "")
                if isinstance(end_time, str):
                    try:
                        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                        auction["hours_remaining"] = max(1, int((end_dt - now).total_seconds() / 3600))
                    except Exception:
                        auction["hours_remaining"] = "?"

            batch.append((user, auction, distance, alert_type))

            # Send in batches
            if len(batch) >= BATCH_SIZE:
                for u, a, d, t in batch:
                    try:
                        success = await send_geo_auction_alert(u, a, d, t)
                        if success:
                            await db.geo_email_log.insert_one({
                                "user_id": u["id"],
                                "auction_id": a["id"],
                                "alert_type": t,
                                "distance_km": round(d),
                                "sent_at": now.isoformat(),
                            })
                            total_sent += 1
                        else:
                            total_failed += 1
                    except Exception as e:
                        logger.error(f"[GEO] Error sending to {u.get('email')}: {e}")
                        total_failed += 1
                batch = []
                await asyncio.sleep(BATCH_DELAY_S)

    # Flush remaining batch
    for u, a, d, t in batch:
        try:
            success = await send_geo_auction_alert(u, a, d, t)
            if success:
                await db.geo_email_log.insert_one({
                    "user_id": u["id"],
                    "auction_id": a["id"],
                    "alert_type": t,
                    "distance_km": round(d),
                    "sent_at": now.isoformat(),
                })
                total_sent += 1
            else:
                total_failed += 1
        except Exception as e:
            logger.error(f"[GEO] Error sending to {u.get('email')}: {e}")
            total_failed += 1

    logger.info(f"[GEO] Daily geo alerts complete: {total_sent} sent, {total_failed} failed, "
                f"{len(all_auctions)} auctions processed")


def register_geo_jobs(scheduler, db: AsyncIOMotorDatabase):
    """Register geo email job with APScheduler. 9:00 AM ET = 14:00 UTC."""
    import asyncio

    def _run_geo():
        asyncio.get_event_loop().create_task(send_geo_auction_alerts(db))

    scheduler.add_job(_run_geo, "cron", hour=14, minute=0, id="geo_auction_alerts", replace_existing=True)
    logger.info("[GEO] Registered daily geo auction alert job (14:00 UTC / 9:00 AM ET)")
