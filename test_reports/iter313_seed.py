"""iter313 P2 banner E2E — seed an auto-paused campaign."""
import os
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
client = MongoClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

now = datetime.now(timezone.utc)
doc = {
    'id': 'iter313-banner-test-1',
    'name': 'iter313 Banner E2E',
    'subject_en': 'banner e2e',
    'body_html_en': '<p>x</p>',
    'status': 'auto_paused',
    'recipient_count': 100,
    'analytics': {'delivered': 100, 'bounced': 8, 'unsubscribed': 0, 'spam_reports': 0},
    'auto_paused_at': now.isoformat(),
    'auto_paused_reason': 'bounce_unsubscribe_ratio_exceeded',
    'auto_paused_ratio_pct': 8.0,
    'auto_paused_negative_count': 8,
    'auto_paused_attempted_count': 100,
    'created_at': now,
    'updated_at': now,
    '_iter313_banner_test': True,
}
db.external_email_campaigns.delete_many({'_iter313_banner_test': True})
db.campaign_guardrail_events.delete_many({'campaign_id': 'iter313-banner-test-1'})
db.external_email_campaigns.insert_one(doc)
print('seeded:', db.external_email_campaigns.count_documents({'id': 'iter313-banner-test-1'}))
