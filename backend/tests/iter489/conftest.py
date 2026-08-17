"""iter491 — clear the DCR rate limiter counters before every test
module in this directory so the OAuth suite can hammer the /register
endpoint without tripping the abuse guard."""
from __future__ import annotations

import os

import pytest_asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _reset_dcr_rate_limit():
    mc = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        await mc[os.environ["DB_NAME"]].mcp_oauth_dcr_rate.delete_many({})
    except Exception:  # noqa: BLE001
        pass
    yield
    mc.close()
