#!/usr/bin/env python3
"""
Create Admin User for BidVex
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from passlib.context import CryptContext

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / 'backend' / '.env')

from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'bazario_db')

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin_user():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    admin_email = "charbeladmin@bidvex.com"
    admin_password = "Admin123!"
    
    # Check if admin already exists
    existing_admin = await db.users.find_one({"email": admin_email})
    if existing_admin:
        print(f"✅ Admin user already exists: {admin_email}")
        return
    
    # Also check for old admin email
    old_admin = await db.users.find_one({"email": "charbel@admin.bazario.com"})
    if old_admin:
        # Update the old admin email to the new one
        await db.users.update_one(
            {"email": "charbel@admin.bazario.com"},
            {"$set": {"email": admin_email}}
        )
        print(f"✅ Updated admin email from charbel@admin.bazario.com to {admin_email}")
        return
    
    # Create new admin user
    hashed_password = pwd_context.hash(admin_password)
    
    admin_user = {
        "id": str(uuid4()),
        "email": admin_email,
        "password": hashed_password,
        "name": "Charbel Admin",
        "account_type": "personal",
        "role": "admin",
        "phone": "+15145550000",
        "phone_verified": True,
        "address": None,
        "company_name": None,
        "tax_number": None,
        "bank_details": None,
        "picture": None,
        "created_at": datetime.now(timezone.utc),
        "language": "en",
        "preferred_language": "en",
        "preferred_currency": "CAD",
        "enforced_currency": None,
        "currency_locked": False,
        "location_confidence_score": None,
        "subscription_tier": "vip",
        "subscription_start": datetime.now(timezone.utc),
        "subscription_end": None,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "payment_method": None,
        "billing_cycle": "yearly"
    }
    
    await db.users.insert_one(admin_user)
    print(f"✅ Admin user created successfully!")
    print(f"   Email: {admin_email}")
    print(f"   Password: {admin_password}")
    print(f"   Role: admin")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_admin_user())
