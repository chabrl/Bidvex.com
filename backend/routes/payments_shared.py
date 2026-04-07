"""
Shared state for payments modules.
Provides database and auth access to all payments sub-routers.
"""

from fastapi.security import HTTPBearer

security = HTTPBearer(auto_error=False)

_db = None
_get_current_user = None


def set_payments_db(db_instance):
    global _db
    _db = db_instance


def set_payments_auth(get_current_user_func):
    global _get_current_user

    async def wrapper(credentials):
        class MockRequest:
            cookies = {}
        return await get_current_user_func(MockRequest(), credentials)

    _get_current_user = wrapper


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


def get_current_user_wrapper():
    return _get_current_user
