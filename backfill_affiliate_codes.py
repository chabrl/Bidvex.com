#!/usr/bin/env python3
"""
Backfill affiliate codes for existing users
"""
import asyncio
import os
import sys
import random
import string
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / 'backend' / '.env')

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'bazario_db')

def generate_affiliate_code(user_id: str) -> str:
    """Generate unique affiliate code"""
    prefix = user_id[:8].upper()
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BVX{prefix}{suffix}"

async def backfill_affiliate_codes():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("🔍 Finding users without affiliate codes...")
    
    users_without_code = await db.users.find({
        "$or": [
            {"affiliate_code": {"$exists": False}},
            {"affiliate_code": None},
            {"affiliate_code": ""}
        ]
    }).to_list(None)
    
    print(f"Found {len(users_without_code)} users needing affiliate codes")
    
    for user in users_without_code:
        affiliate_code = generate_affiliate_code(user['id'])
        
        await db.users.update_one(
            {"id": user['id']},
            {"$set": {"affiliate_code": affiliate_code}}
        )
        
        print(f"✅ {user['email']}: {affiliate_code}")
    
    print(f"\n🎉 Backfill complete! {len(users_without_code)} users updated")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(backfill_affiliate_codes())
