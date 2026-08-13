"""
iter482+ — Lot CSV Export Routes
================================

Thin route wrapper around ``services/lot_csv_export_service.py``.

**Read-only.**  No mutation of any collection.

Endpoints
---------

    GET /api/exports/lots/{auction_id}
        Query params:
            surface         seller | public | admin  (default: seller)
            include_drafts  true|false               (default: false)

        Returns:  ``text/csv; charset=utf-8`` with ``Content-Disposition``
                  ``attachment; filename=bidvex_lots_<id>_<surface>.csv``

    GET /api/exports/lots/{auction_id}/preview
        JSON preview (row count, column list, first 5 rows) — used by the
        seller dashboard "Export CSV" panel for a quick sanity check.

Authentication
--------------
* ``surface=public``  → **no auth required**.
* ``surface=seller``  → owner-only (admin bypasses).
* ``surface=admin``   → admin-only.
"""

from __future__ import annotations
from typing import Any, Optional
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.responses import StreamingResponse

from services.lot_csv_export_service import (
    generate_csv,
    stream_csv,
    resolve_auction,
    ExportAccessDenied,
    ExportNotFound,
    CANONICAL_COLUMNS,
    ADMIN_EXTRA_COLUMNS,
)

router = APIRouter(prefix="/api/exports/lots", tags=["lot-csv-export"])
security = HTTPBearer(auto_error=False)


# ─── DI ──────────────────────────────────────────────────────────────
_state: dict = {"db": None, "auth": None}


def set_db(db):
    _state["db"] = db


def set_auth(fn):
    """`fn(credentials) -> user` — reuse existing auth resolver."""
    _state["auth"] = fn


def _db():
    return _state["db"]


async def _resolve_user(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Any:
    """Resolve current user from credentials, returning None if absent."""
    if credentials is None or _state["auth"] is None:
        return None
    try:
        return await _state["auth"](credentials)
    except HTTPException:
        return None
    except Exception:
        return None


# ─── Endpoints ───────────────────────────────────────────────────────

@router.get("/{auction_id}")
async def export_lots_csv(
    auction_id: str,
    surface: str = Query("seller", pattern="^(seller|public|admin)$"),
    include_drafts: bool = Query(False),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Download lots as CSV for the given auction."""
    db = _db()
    if db is None:
        raise HTTPException(status_code=500, detail="DB not initialized")

    user = None
    if surface in {"seller", "admin"}:
        user = await _resolve_user(credentials)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")

    try:
        filename, payload = await generate_csv(
            db, auction_id, surface, user,
            include_drafts=include_drafts,
        )
    except ExportNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ExportAccessDenied as exc:
        raise HTTPException(status_code=exc.status, detail=exc.reason)

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "private, no-store",
    }
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.get("/{auction_id}/preview")
async def export_lots_preview(
    auction_id: str,
    surface: str = Query("seller", pattern="^(seller|public|admin)$"),
    include_drafts: bool = Query(False),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """JSON preview: column list, row count, and first 5 rows."""
    db = _db()
    if db is None:
        raise HTTPException(status_code=500, detail="DB not initialized")

    user = None
    if surface in {"seller", "admin"}:
        user = await _resolve_user(credentials)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")

    try:
        _fn, payload = await generate_csv(
            db, auction_id, surface, user,
            include_drafts=include_drafts,
        )
    except ExportNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ExportAccessDenied as exc:
        raise HTTPException(status_code=exc.status, detail=exc.reason)

    # Strip BOM before parsing
    text = payload.decode("utf-8").lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    all_rows = list(reader)
    columns = list(CANONICAL_COLUMNS) + (
        list(ADMIN_EXTRA_COLUMNS) if surface == "admin" else []
    )
    return {
        "auction_id": auction_id,
        "surface": surface,
        "columns": columns,
        "row_count": len(all_rows),
        "sample_rows": all_rows[:5],
    }


__all__ = ["router", "set_db", "set_auth"]
