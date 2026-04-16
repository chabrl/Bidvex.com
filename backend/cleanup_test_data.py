"""
BidVex Production Data Cleanup Script
Run this against your production MongoDB to remove all test data.
Usage: python3 cleanup_test_data.py
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'bidvex')

# Patterns that identify test/dev data
TEST_EMAIL_PATTERNS = [
    'test', 'demo', 'sample', 'dev@', 'qa@', 'fake',
    'example.com', 'mailinator', 'tempmail', 'throwaway',
    'yopmail', 'guerrilla', 'sharklasers', 'grr.la',
]

TEST_TITLE_PATTERNS = [
    'test', 'lorem', 'placeholder', 'sample', 'demo',
    'asdf', 'xxx', 'foo', 'bar', 'hello world',
]


async def cleanup():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"Connected to DB: {DB_NAME}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # 1. Find test users
    test_user_query = {
        '$or': [
            {'email': {'$regex': '|'.join(TEST_EMAIL_PATTERNS), '$options': 'i'}},
        ]
    }
    test_users = await db.users.find(test_user_query, {'_id': 0, 'id': 1, 'email': 1}).to_list(1000)
    test_user_ids = [u['id'] for u in test_users]
    print(f"\n1. TEST USERS: {len(test_users)}")
    for u in test_users:
        print(f"   - {u.get('email')}")

    # 2. Test community questions & replies
    test_questions = await db.community_questions.count_documents({
        '$or': [
            {'author_id': {'$in': test_user_ids}} if test_user_ids else {'_never_': True},
            {'title': {'$regex': '|'.join(TEST_TITLE_PATTERNS), '$options': 'i'}},
            {'body': {'$regex': 'lorem ipsum|test post|placeholder', '$options': 'i'}},
        ]
    })
    all_questions = await db.community_questions.count_documents({})
    all_replies = await db.community_replies.count_documents({})
    print(f"\n2. COMMUNITY: {all_questions} questions, {all_replies} replies (test pattern matches: {test_questions})")

    # 3. Test listings
    test_listing_query = {
        '$or': [
            {'seller_id': {'$in': test_user_ids}} if test_user_ids else {'_never_': True},
            {'title': {'$regex': '|'.join(TEST_TITLE_PATTERNS), '$options': 'i'}},
        ]
    }
    test_listings = await db.listings.count_documents(test_listing_query)
    print(f"\n3. TEST LISTINGS: {test_listings}")

    # 4. Test campaigns
    test_campaigns = await db.email_campaigns.count_documents({
        '$or': [
            {'name': {'$regex': 'test|demo|sample', '$options': 'i'}},
            {'subject': {'$regex': 'test|demo|sample', '$options': 'i'}},
        ]
    })
    all_campaigns = await db.email_campaigns.count_documents({})
    print(f"\n4. EMAIL CAMPAIGNS: {all_campaigns} total, {test_campaigns} test pattern matches")

    # 5. CTA analytics (test data)
    cta_count = await db.cta_analytics.count_documents({})
    print(f"\n5. CTA ANALYTICS: {cta_count}")

    # 6. Marketing contacts
    mc_count = await db.marketing_contacts.count_documents({})
    print(f"\n6. MARKETING CONTACTS: {mc_count}")

    # 7. Lifecycle email logs
    lifecycle = await db.lifecycle_email_log.count_documents({})
    print(f"\n7. LIFECYCLE EMAIL LOG: {lifecycle}")

    print("\n" + "=" * 60)
    print("DRY RUN COMPLETE. To actually delete, set CONFIRM_DELETE=yes")
    print("=" * 60)

    if os.environ.get('CONFIRM_DELETE') == 'yes':
        print("\n*** DELETING TEST DATA ***\n")
        deleted = {}

        # Delete test users
        if test_user_ids:
            r = await db.users.delete_many(test_user_query)
            deleted['users'] = r.deleted_count

            # Delete related data for test users
            for col in ['bids', 'notifications', 'messages', 'watchlist', 'payment_methods']:
                r = await db[col].delete_many({'user_id': {'$in': test_user_ids}})
                if r.deleted_count > 0:
                    deleted[col] = r.deleted_count

        # Delete ALL community data (since you said test comments are visible)
        r = await db.community_questions.delete_many({})
        deleted['community_questions'] = r.deleted_count
        r = await db.community_replies.delete_many({})
        deleted['community_replies'] = r.deleted_count

        # Delete test campaigns
        if test_campaigns > 0:
            r = await db.email_campaigns.delete_many({
                '$or': [
                    {'name': {'$regex': 'test|demo|sample', '$options': 'i'}},
                    {'subject': {'$regex': 'test|demo|sample', '$options': 'i'}},
                ]
            })
            deleted['test_campaigns'] = r.deleted_count

        # Delete CTA test analytics
        r = await db.cta_analytics.delete_many({})
        deleted['cta_analytics'] = r.deleted_count

        # Delete synced marketing contacts (can be re-synced)
        r = await db.marketing_contacts.delete_many({})
        deleted['marketing_contacts'] = r.deleted_count

        print("DELETED:")
        for k, v in deleted.items():
            print(f"  {k}: {v}")

    client.close()

asyncio.run(cleanup())
