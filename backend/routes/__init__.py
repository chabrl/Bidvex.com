"""
BidVex API Routes Package
Modular router architecture for scalability and maintainability
"""

# Core routers (already existed)
from .messages import messages_router
from .analytics import analytics_router
from .auctions import auctions_router, set_db as set_auctions_db, set_notification_manager
from .auth import auth_router, set_auth_db
from .sms_verification import sms_router, set_db as set_sms_db
from .vehicles import vehicle_router, set_vehicle_db
from .tax_reports import tax_router, set_tax_db

# New modular routers
from .users import users_router, set_users_db, set_users_auth
from .marketing import marketing_router, set_marketing_db, set_marketing_auth, set_marketing_services
from .admin import admin_router, set_admin_db, set_admin_auth, set_admin_email_service
from .webhooks import webhooks_router, set_webhooks_db, set_webhooks_marketing_service
from .payments import payments_router, set_payments_db, set_payments_auth

__all__ = [
    # Core routers
    'messages_router',
    'analytics_router', 
    'auctions_router', 'set_auctions_db', 'set_notification_manager',
    'auth_router', 'set_auth_db',
    'sms_router', 'set_sms_db',
    'vehicle_router', 'set_vehicle_db',
    'tax_router', 'set_tax_db',
    # New modular routers
    'users_router', 'set_users_db', 'set_users_auth',
    'marketing_router', 'set_marketing_db', 'set_marketing_auth', 'set_marketing_services',
    'admin_router', 'set_admin_db', 'set_admin_auth', 'set_admin_email_service',
    'webhooks_router', 'set_webhooks_db', 'set_webhooks_marketing_service',
    'payments_router', 'set_payments_db', 'set_payments_auth',
]
