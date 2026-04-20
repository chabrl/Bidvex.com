"""BidVex — Main entry point for uvicorn."""
import os
import logging

logger = logging.getLogger(__name__)

# ── Validate frontend build exists on startup ──
FRONTEND_BUILD_PATHS = [
    "/app/frontend/build",
    "/frontend/build",
    os.path.join(os.path.dirname(__file__), "..", "frontend", "build"),
    os.path.join(os.path.dirname(__file__), "frontend", "build"),
]

FRONTEND_BUILD = None
for path in FRONTEND_BUILD_PATHS:
    resolved = os.path.abspath(path)
    if os.path.exists(os.path.join(resolved, "index.html")):
        FRONTEND_BUILD = resolved
        break

if FRONTEND_BUILD is None:
    logger.warning("WARNING: Frontend build NOT found. Root path will not serve the React app.")
    logger.warning(f"Searched paths: {[os.path.abspath(p) for p in FRONTEND_BUILD_PATHS]}")
else:
    logger.info(f"Frontend ready to serve from: {FRONTEND_BUILD}")

# Import the FastAPI app (this triggers server.py module load)
from server import app  # noqa: F401
