"""
iter357 — Public platform stats endpoint (no auth).

Endpoint:
    GET /api/public/platform-stats

Returns humanized counters used by the social-proof widget on regional
landing pages and (optionally) the homepage.
"""
from fastapi import APIRouter
from deps import get_db
from services.platform_stats import get_platform_stats


public_stats_router = APIRouter(prefix="/public", tags=["Public"])


@public_stats_router.get("/platform-stats")
async def platform_stats():
    """Public platform counters. Cached 5 min in-process."""
    db = get_db()
    stats = await get_platform_stats(db)
    return stats
