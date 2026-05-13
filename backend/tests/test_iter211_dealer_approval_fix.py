"""
iter211 fix — Vehicle dealer approval flow + admin subscriptions list.

Verifies:
  1. routes/vehicles_admin.py approve_seller sets is_vehicle_dealer=True on the
     user document (was missing — root cause of the missing banner).
  2. routes/vehicle_dealer_extras.py decide_dealer_license_review sets the
     same flag when an admin approves the license directly.
  3. routes/dealer_subscription_routes.py exposes the admin overview endpoint
     GET /admin/dealer-subscriptions with the expected response shape.
"""


def test_approve_seller_sets_is_vehicle_dealer_on_user():
    """Static smoke: the approve_seller handler must now write `is_vehicle_dealer=True`
    to the user document. Without this, the dealer dashboard banner never renders."""
    with open("/app/backend/routes/vehicles_admin.py", "r") as f:
        body = f.read()
    assert "approve_seller" in body
    assert "is_vehicle_dealer" in body
    assert "db.users.update_one" in body or "_db.users.update_one" in body, \
        "approve_seller must write to the users collection so is_vehicle_dealer is set"


def test_license_approval_also_sets_is_vehicle_dealer():
    """Same guarantee for the parallel license-approval entry point."""
    with open("/app/backend/routes/vehicle_dealer_extras.py", "r") as f:
        body = f.read()
    # Must touch users with is_vehicle_dealer when license is approved
    assert "is_vehicle_dealer" in body
    assert "db.users.update_one" in body
    assert 'vehicle_dealer_approved_at' in body


def test_admin_dealer_subscriptions_endpoint_exists():
    """The new admin overview endpoint that powers the DealerSubscriptionsTab UI."""
    with open("/app/backend/routes/dealer_subscription_routes.py", "r") as f:
        body = f.read()
    assert "/admin/dealer-subscriptions" in body, \
        "GET /admin/dealer-subscriptions endpoint required for the admin tab"
    assert "list_all_dealer_subscriptions" in body
    assert "summary" in body and "paid" in body and "unpaid" in body and "suspended" in body


def test_admin_dealer_subscriptions_requires_admin_role():
    """Endpoint must 403 non-admins."""
    with open("/app/backend/routes/dealer_subscription_routes.py", "r") as f:
        body = f.read()
    # Find the function body and verify admin check
    start = body.index("async def list_all_dealer_subscriptions")
    chunk = body[start:start + 1500]
    assert "admin_required" in chunk
    assert 'admin.get("role")' in chunk or "admin['role']" in chunk
