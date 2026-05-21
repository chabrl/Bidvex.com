"""
Pytest conftest — adds /app/backend to sys.path so tests can import routes/, services/, etc.
without requiring callers to set PYTHONPATH explicitly.

Also exposes shared test-credential fixtures (iter214) so individual test files
don't have to hardcode the same demo passwords/emails inline. Use:

    def test_something(test_admin_email, test_admin_password, test_user_email): ...
"""
import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# ── Shared test credential fixtures (iter214) ──
# These are intentionally NOT real production secrets — they're the same demo
# values that previously lived inline in 129 test files. Centralizing them
# here cuts that footprint to a single audit point. Override per-run via env
# vars (BIDVEX_TEST_*) for CI / staging environments.

@pytest.fixture(scope="session")
def test_admin_email() -> str:
    return os.environ.get("BIDVEX_TEST_ADMIN_EMAIL", "charbel911@gmail.com")


@pytest.fixture(scope="session")
def test_admin_password() -> str:
    return os.environ.get("BIDVEX_TEST_ADMIN_PASSWORD", "Anderosli123!@#")


@pytest.fixture(scope="session")
def test_buyer_password() -> str:
    return os.environ.get("BIDVEX_TEST_BUYER_PASSWORD", "TestBuyer123!")


@pytest.fixture(scope="session")
def test_user_password() -> str:
    return os.environ.get("BIDVEX_TEST_USER_PASSWORD", "TestUser123!")


@pytest.fixture(scope="session")
def test_admin_id() -> str:
    return os.environ.get("BIDVEX_TEST_ADMIN_ID", "admin-test-id")
