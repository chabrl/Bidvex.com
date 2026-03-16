"""
BidVex Team Management & RBAC Routes
Handles team invitations, role management, and permission enforcement
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
import os
import uuid
import secrets
import logging

logger = logging.getLogger(__name__)

team_router = APIRouter(prefix="/api/team", tags=["Team Management"])
security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"

db = None

VALID_ROLES = ["admin", "manager", "support"]

ROLE_PERMISSIONS = {
    "admin": {
        "manage_team": True,
        "manage_users": True,
        "manage_auctions": True,
        "manage_content": True,
        "manage_settings": True,
        "manage_finance": True,
        "view_analytics": True,
        "view_logs": True,
    },
    "manager": {
        "manage_team": False,
        "manage_users": True,
        "manage_auctions": True,
        "manage_content": True,
        "manage_settings": False,
        "manage_finance": True,
        "view_analytics": True,
        "view_logs": True,
    },
    "support": {
        "manage_team": False,
        "manage_users": False,
        "manage_auctions": False,
        "manage_content": False,
        "manage_settings": False,
        "manage_finance": False,
        "view_analytics": True,
        "view_logs": True,
    },
}


def set_team_db(database):
    global db
    db = database


class InviteRequest(BaseModel):
    email: EmailStr
    role: str
    name: Optional[str] = ""


class AcceptInviteRequest(BaseModel):
    name: str
    password: str


class UpdateRoleRequest(BaseModel):
    role: str


async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if user.get("role") != "admin" and user.get("role") != "superadmin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@team_router.post("/invite")
async def invite_team_member(req: InviteRequest, request: Request, admin: dict = Depends(get_current_admin)):
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")

    existing_user = await db.users.find_one({"email": req.email})
    if existing_user and existing_user.get("role") in VALID_ROLES:
        raise HTTPException(status_code=400, detail="This email is already a team member")

    pending = await db.team_invitations.find_one({"email": req.email, "status": "pending"})
    if pending:
        raise HTTPException(status_code=400, detail="An invitation is already pending for this email")

    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)

    invitation = {
        "id": str(uuid.uuid4()),
        "email": req.email,
        "name": req.name or "",
        "role": req.role,
        "token": token,
        "invited_by": admin["id"],
        "invited_by_name": admin.get("name", "Admin"),
        "status": "pending",
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    }

    await db.team_invitations.insert_one(invitation)

    logger.info(f"Team invitation sent to {req.email} with role {req.role} by {admin['id']}")

    origin = request.headers.get("origin", "")
    invite_link = f"{origin}/invite/{token}"

    return {
        "success": True,
        "message": f"Invitation sent to {req.email}",
        "invite_link": invite_link,
        "invitation_id": invitation["id"],
    }


@team_router.get("/invite/{token}/info")
async def get_invite_info(token: str):
    invitation = await db.team_invitations.find_one(
        {"token": token, "status": "pending"}, {"_id": 0}
    )
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found or already used")

    expires_at = datetime.fromisoformat(invitation["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="This invitation has expired")

    return {
        "email": invitation["email"],
        "role": invitation["role"],
        "invited_by_name": invitation.get("invited_by_name", "Admin"),
        "expires_at": invitation["expires_at"],
    }


@team_router.post("/invite/{token}/accept")
async def accept_invite(token: str, req: AcceptInviteRequest):
    invitation = await db.team_invitations.find_one(
        {"token": token, "status": "pending"}, {"_id": 0}
    )
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found or already used")

    expires_at = datetime.fromisoformat(invitation["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        await db.team_invitations.update_one({"token": token}, {"$set": {"status": "expired"}})
        raise HTTPException(status_code=410, detail="This invitation has expired")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = await db.users.find_one({"email": invitation["email"]})
    now = datetime.now(timezone.utc)

    if existing:
        await db.users.update_one(
            {"email": invitation["email"]},
            {"$set": {
                "role": invitation["role"],
                "name": req.name or existing.get("name", ""),
                "password": pwd_context.hash(req.password),
                "team_member": True,
                "team_joined_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }}
        )
        user_id = existing["id"]
    else:
        user_id = str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": invitation["email"],
            "password": pwd_context.hash(req.password),
            "name": req.name,
            "account_type": "personal",
            "phone": "",
            "role": invitation["role"],
            "team_member": True,
            "team_joined_at": now.isoformat(),
            "preferred_language": "en",
            "preferred_currency": "CAD",
            "phone_verified": False,
            "email_verified": True,
            "terms_agreed_at": now.isoformat(),
            "created_at": now.isoformat(),
            "updated_at": None,
        }
        await db.users.insert_one(user_doc)

    await db.team_invitations.update_one(
        {"token": token},
        {"$set": {"status": "accepted", "accepted_at": now.isoformat()}}
    )

    logger.info(f"Team invitation accepted by {invitation['email']} as {invitation['role']}")

    return {
        "success": True,
        "message": f"Welcome to the BidVex team as {invitation['role'].title()}!",
        "role": invitation["role"],
    }


@team_router.get("/members")
async def list_team_members(admin: dict = Depends(get_current_admin)):
    members = await db.users.find(
        {"role": {"$in": VALID_ROLES}},
        {"_id": 0, "password": 0}
    ).to_list(length=100)
    return {"members": members}


@team_router.get("/invitations")
async def list_invitations(admin: dict = Depends(get_current_admin)):
    invitations = await db.team_invitations.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=100)
    return {"invitations": invitations}


@team_router.put("/members/{user_id}/role")
async def update_member_role(user_id: str, req: UpdateRoleRequest, admin: dict = Depends(get_current_admin)):
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")

    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    member = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": req.role, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    logger.info(f"Role updated for {user_id} to {req.role} by {admin['id']}")
    return {"success": True, "message": f"Role updated to {req.role.title()}"}


@team_router.delete("/members/{user_id}")
async def remove_team_member(user_id: str, admin: dict = Depends(get_current_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot remove yourself from the team")

    member = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "role": "user",
            "team_member": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    logger.info(f"Team member {user_id} removed by {admin['id']}")
    return {"success": True, "message": "Team member removed"}


@team_router.delete("/invitations/{invitation_id}")
async def cancel_invitation(invitation_id: str, admin: dict = Depends(get_current_admin)):
    result = await db.team_invitations.update_one(
        {"id": invitation_id, "status": "pending"},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Invitation not found or already processed")
    return {"success": True, "message": "Invitation cancelled"}


@team_router.get("/permissions")
async def get_my_permissions(user: dict = Depends(get_current_user)):
    role = user.get("role", "user")
    permissions = ROLE_PERMISSIONS.get(role, {})
    return {"role": role, "permissions": permissions}


@team_router.get("/roles")
async def get_roles_info():
    return {
        "roles": [
            {"id": "admin", "label": "Admin", "description": "Full access to all platform features and settings"},
            {"id": "manager", "label": "Manager", "description": "Manage auctions, users, content, and finances. Cannot manage team or site settings."},
            {"id": "support", "label": "Support", "description": "View-only access to analytics and logs. Cannot modify any data."},
        ],
        "permissions": ROLE_PERMISSIONS,
    }
