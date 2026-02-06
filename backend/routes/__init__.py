# BidVex API Routes Package
# Modular router architecture for scalability and maintainability

from .messages import messages_router
from .analytics import analytics_router
from .auctions import auctions_router
from .auth import auth_router, set_auth_db

__all__ = ['messages_router', 'analytics_router', 'auctions_router', 'auth_router', 'set_auth_db']

