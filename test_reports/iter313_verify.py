"""iter313 P2 banner E2E — verify post-resume DB state + cleanup."""
import os, json
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
client = MongoClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

camp = db.external_email_campaigns.find_one(
    {'id': 'iter313-banner-test-1'}, {'_id': 0}
)
events = list(db.campaign_guardrail_events.find(
    {'campaign_id': 'iter313-banner-test-1'}, {'_id': 0}
))

print('CAMPAIGN_STATUS:', camp.get('status') if camp else None)
print('AUTO_PAUSED_RESUMED_AT:', camp.get('auto_paused_resumed_at') if camp else None)
print('EVENTS_COUNT:', len(events))
for e in events:
    print('  EVENT:', e.get('event'), '| reason:', e.get('reason') or e.get('acknowledge_risk') or e.get('resume_reason'))
print('FULL_EVENTS:', json.dumps(events, default=str))

# Cleanup
d1 = db.external_email_campaigns.delete_many({'_iter313_banner_test': True}).deleted_count
d2 = db.campaign_guardrail_events.delete_many({'campaign_id': 'iter313-banner-test-1'}).deleted_count
print(f'CLEANUP: campaigns={d1} events={d2}')
