"""
BidVex — IP-based Brute Force Protection (Redis-backed)
Tracks failed login attempts per IP. After 5 failures, blocks the IP for 24 hours.
Uses Redis when available, falls back to in-memory.
"""

import os
import time
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 15
BLOCK_DURATION = 900      # 15 minutes in seconds (was 24 hours — too aggressive)
ATTEMPT_WINDOW = 3600    # 1 hour window for counting attempts

# Key prefixes
_FAIL_PREFIX = "bf:fail:"     # bf:fail:<ip> → count of failures
_BLOCK_PREFIX = "bf:block:"   # bf:block:<ip> → blocked-until timestamp


# ─── Redis helpers (reuse the api_cache client) ─────────────────────

async def _redis():
    from services.api_cache import _get_redis
    return await _get_redis()


# ─── In-memory fallback ─────────────────────────────────────────────
_mem_fails: dict[str, list[float]] = {}   # ip → [timestamp, ...]
_mem_blocks: dict[str, float] = {}        # ip → blocked_until epoch


# ─── Public API ──────────────────────────────────────────────────────

async def check_blocked(ip: str) -> Optional[dict]:
    """
    Check if an IP is currently blocked.
    Returns None if allowed, or {"blocked": True, "until": ..., "remaining": ...} if blocked.
    """
    r = await _redis()
    now = time.time()

    if r:
        try:
            blocked_until = await r.get(f"{_BLOCK_PREFIX}{ip}")
            if blocked_until:
                until = float(blocked_until)
                if now < until:
                    remaining = int(until - now)
                    return {
                        "blocked": True,
                        "until": datetime.fromtimestamp(until, tz=timezone.utc).isoformat(),
                        "remaining_seconds": remaining,
                        "reason": f"Too many failed login attempts. Try again in {remaining // 3600}h {(remaining % 3600) // 60}m.",
                    }
                else:
                    await r.delete(f"{_BLOCK_PREFIX}{ip}")
            return None
        except Exception as e:
            logger.debug(f"[brute_force] Redis check error: {e}")

    # Memory fallback
    blocked_until = _mem_blocks.get(ip)
    if blocked_until and now < blocked_until:
        remaining = int(blocked_until - now)
        return {
            "blocked": True,
            "until": datetime.fromtimestamp(blocked_until, tz=timezone.utc).isoformat(),
            "remaining_seconds": remaining,
            "reason": f"Too many failed login attempts. Try again in {remaining // 3600}h {(remaining % 3600) // 60}m.",
        }
    elif blocked_until:
        del _mem_blocks[ip]
    return None


async def record_failure(ip: str) -> dict:
    """
    Record a failed login attempt. If threshold reached, block the IP.
    Returns {"attempts": N, "blocked": bool}.
    """
    r = await _redis()
    now = time.time()

    if r:
        try:
            key = f"{_FAIL_PREFIX}{ip}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, ATTEMPT_WINDOW)

            if count >= MAX_ATTEMPTS:
                blocked_until = now + BLOCK_DURATION
                await r.set(f"{_BLOCK_PREFIX}{ip}", str(blocked_until), ex=BLOCK_DURATION)
                await r.delete(key)
                logger.warning(f"[brute_force] IP {ip} BLOCKED for 24h after {count} failed logins")
                return {"attempts": count, "blocked": True}

            return {"attempts": count, "blocked": False}
        except Exception as e:
            logger.debug(f"[brute_force] Redis record error: {e}")

    # Memory fallback
    if ip not in _mem_fails:
        _mem_fails[ip] = []
    cutoff = now - ATTEMPT_WINDOW
    _mem_fails[ip] = [t for t in _mem_fails[ip] if t > cutoff]
    _mem_fails[ip].append(now)
    count = len(_mem_fails[ip])

    if count >= MAX_ATTEMPTS:
        _mem_blocks[ip] = now + BLOCK_DURATION
        _mem_fails.pop(ip, None)
        logger.warning(f"[brute_force] IP {ip} BLOCKED (memory) for 24h after {count} failed logins")
        return {"attempts": count, "blocked": True}

    return {"attempts": count, "blocked": False}


async def reset_failures(ip: str):
    """Clear failure count on successful login."""
    r = await _redis()
    if r:
        try:
            await r.delete(f"{_FAIL_PREFIX}{ip}")
        except Exception:
            pass
    _mem_fails.pop(ip, None)


async def unblock_ip(ip: str) -> bool:
    """Admin action: manually unblock an IP."""
    r = await _redis()
    removed = False
    if r:
        try:
            removed = bool(await r.delete(f"{_BLOCK_PREFIX}{ip}"))
            await r.delete(f"{_FAIL_PREFIX}{ip}")
        except Exception:
            pass
    if ip in _mem_blocks:
        del _mem_blocks[ip]
        removed = True
    _mem_fails.pop(ip, None)
    if removed:
        logger.info(f"[brute_force] IP {ip} manually unblocked by admin")
    return removed


async def get_blocked_ips() -> list[dict]:
    """Admin: list all currently blocked IPs."""
    result = []
    now = time.time()

    r = await _redis()
    if r:
        try:
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=f"{_BLOCK_PREFIX}*", count=100)
                for key in keys:
                    ip = key.replace(_BLOCK_PREFIX, "")
                    until_str = await r.get(key)
                    if until_str:
                        until = float(until_str)
                        if now < until:
                            result.append({
                                "ip": ip,
                                "blocked_until": datetime.fromtimestamp(until, tz=timezone.utc).isoformat(),
                                "remaining_seconds": int(until - now),
                            })
                if cursor == 0:
                    break
            return result
        except Exception as e:
            logger.debug(f"[brute_force] Redis scan error: {e}")

    # Memory fallback
    for ip, until in list(_mem_blocks.items()):
        if now < until:
            result.append({
                "ip": ip,
                "blocked_until": datetime.fromtimestamp(until, tz=timezone.utc).isoformat(),
                "remaining_seconds": int(until - now),
            })
    return result
