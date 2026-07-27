#!/usr/bin/env python3
"""Restore yearly Stripe Price IDs changed as a side effect of lazy monthly sync test."""
import json
from pathlib import Path
from dotenv import dotenv_values
from pymongo import MongoClient
ENV = dotenv_values('/app/backend/.env')
res = json.loads(Path('/app/test_reports/iter399_subscription_p1_results.json').read_text())
client = MongoClient(ENV['MONGO_URL'])
db = client[ENV.get('DB_NAME','bazario_db')]
restored = []
for plan_id in ['premium', 'vip']:
    original = res.get('original_plan_price_ids', {}).get(plan_id, {}).get('stripe_price_id_yearly')
    if original:
        db.subscription_plans.update_one({'plan_id': plan_id}, {'$set': {'stripe_price_id_yearly': original}})
        restored.append({'plan_id': plan_id, 'stripe_price_id_yearly': original})
final = {p['plan_id']: {'stripe_price_id_monthly': p.get('stripe_price_id_monthly'), 'stripe_price_id_yearly': p.get('stripe_price_id_yearly')} for p in db.subscription_plans.find({'plan_id': {'$in': ['premium','vip']}}, {'_id':0,'plan_id':1,'stripe_price_id_monthly':1,'stripe_price_id_yearly':1})}
out = {'restored_yearly': restored, 'final': final}
Path('/app/test_reports/iter399_restore_yearly_ids_result.json').write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
