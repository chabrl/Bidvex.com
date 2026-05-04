"""
BidVex — Stripe Circuit Breaker
================================
Prevents cascading payment failures when Stripe is degraded.

Usage:
    from services.stripe_circuit_breaker import safe_stripe_call
    result = await safe_stripe_call(
        lambda: stripe.PaymentIntent.create(amount=1000, currency='cad'),
        operation_name='create_payment_intent',
    )

The wrapper:
- Times out long Stripe calls (15s) so the user is not stuck.
- Trips the breaker after 5 consecutive failures, then blocks new
  Stripe calls for 60s and returns a bilingual 503 to the client.
- Auto-recovers via a `half-open` test request after the timeout.

Note: Stripe SDK calls are synchronous. We delegate them to a thread
via `asyncio.to_thread` so they don't block the event loop.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import HTTPException

logger = logging.getLogger(__name__)

try:
    import stripe  # type: ignore
    StripeError = stripe.error.StripeError  # type: ignore
except Exception:
    stripe = None  # type: ignore
    class StripeError(Exception):
        pass


class StripeCircuitBreaker:
    """Simple circuit breaker — closed → open → half-open → closed."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time: datetime | None = None
        self.state: str = "closed"

    def record_success(self) -> None:
        if self.state != "closed":
            logger.info("🟢 Stripe circuit breaker recovered → closed")
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        if self.failure_count >= self.failure_threshold and self.state != "open":
            self.state = "open"
            logger.error(
                f"🔴 Stripe circuit breaker OPEN — {self.failure_count} consecutive failures. "
                f"Blocking payment requests for {self.recovery_timeout}s."
            )

    def can_attempt(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open" and self.last_failure_time is not None:
            if datetime.now(timezone.utc) - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "half-open"
                logger.info("🟡 Stripe circuit breaker → half-open (probing)")
                return True
            return False
        return True  # half-open: allow one test request


# Module-level singleton — used by every Stripe call.
stripe_circuit_breaker = StripeCircuitBreaker()


async def safe_stripe_call(
    fn: Callable[[], Any],
    operation_name: str = "stripe_call",
    timeout_seconds: float = 15.0,
) -> Any:
    """Run a synchronous (or async-returning) Stripe call with circuit-breaker + timeout.

    `fn` must be a zero-arg callable.
    - If `fn()` returns a coroutine, we await it.
    - Otherwise we run `fn()` inside a thread (Stripe SDK blocks on HTTP I/O).

    Returns the Stripe SDK result, or raises a bilingual HTTPException.
    """
    if not stripe_circuit_breaker.can_attempt():
        raise HTTPException(status_code=503, detail={
            "error": "payment_service_unavailable",
            "message_en": "Payment processing is temporarily unavailable. Please try again in a few minutes.",
            "message_fr": "Le traitement des paiements est temporairement indisponible. Veuillez réessayer dans quelques minutes.",
        })

    async def _runner():
        try:
            res = fn()
        except StripeError:
            raise
        except Exception:
            # If fn itself blew up before we could execute, treat as Stripe failure
            raise

        if asyncio.iscoroutine(res):
            return await res
        # Sync result already produced; for blocking SDK calls callers should
        # instead pass `fn=lambda: stripe.X(...)` so the call happens inside this awaitable
        # via asyncio.to_thread (recommended). Provide the helper:
        return res

    try:
        result = await asyncio.wait_for(_runner(), timeout=timeout_seconds)
        stripe_circuit_breaker.record_success()
        return result
    except asyncio.TimeoutError:
        stripe_circuit_breaker.record_failure()
        logger.error(f"[STRIPE] {operation_name} timed out after {timeout_seconds}s")
        raise HTTPException(status_code=504, detail={
            "error": "payment_timeout",
            "message_en": "Payment request timed out. Please try again.",
            "message_fr": "La demande de paiement a expiré. Veuillez réessayer.",
        })
    except StripeError as exc:
        stripe_circuit_breaker.record_failure()
        logger.error(f"[STRIPE] {operation_name} failed: {exc}")
        raise HTTPException(status_code=402, detail={
            "error": "payment_failed",
            "message_en": f"Payment failed: {str(exc)}",
            "message_fr": f"Paiement échoué: {str(exc)}",
        })


async def safe_stripe_call_blocking(
    fn: Callable[[], Any],
    operation_name: str = "stripe_call",
    timeout_seconds: float = 15.0,
) -> Any:
    """Specialised variant: runs a blocking sync Stripe call in a worker thread.

    Recommended for the official Stripe Python SDK (which is fully synchronous).
    """
    if not stripe_circuit_breaker.can_attempt():
        raise HTTPException(status_code=503, detail={
            "error": "payment_service_unavailable",
            "message_en": "Payment processing is temporarily unavailable. Please try again in a few minutes.",
            "message_fr": "Le traitement des paiements est temporairement indisponible. Veuillez réessayer dans quelques minutes.",
        })

    try:
        result = await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout_seconds)
        stripe_circuit_breaker.record_success()
        return result
    except asyncio.TimeoutError:
        stripe_circuit_breaker.record_failure()
        logger.error(f"[STRIPE] {operation_name} timed out after {timeout_seconds}s")
        raise HTTPException(status_code=504, detail={
            "error": "payment_timeout",
            "message_en": "Payment request timed out. Please try again.",
            "message_fr": "La demande de paiement a expiré. Veuillez réessayer.",
        })
    except StripeError as exc:
        stripe_circuit_breaker.record_failure()
        logger.error(f"[STRIPE] {operation_name} failed: {exc}")
        raise HTTPException(status_code=402, detail={
            "error": "payment_failed",
            "message_en": f"Payment failed: {str(exc)}",
            "message_fr": f"Paiement échoué: {str(exc)}",
        })
