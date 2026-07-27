#!/usr/bin/env python3
"""Supplemental status check for iter399 after register endpoint rate-limited the main run."""
import json, time, uuid
from pathlib import Path
from dotenv import dotenv_values
from jose import jwt
from pymongo import MongoClient
import requests
ENV = dotenv_values('/app/backend/.env')
API = 'http://localhost:8001/api'
client = MongoClient(ENV['MONGO_URL'])
db = client[ENV.get('DB_NAME','bazario_db')]
email = f'iter399_status_vip_direct_{uuid.uuid4().hex[:10]}@example.com'
uid = str(uuid.uuid4())
now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
db.users.insert_one({
    'id': uid, 'email': email, 'name': 'Iter399 VIP Status Direct',
    'account_type': 'personal', 'phone': '', 'subscription_tier': 'vip',
    'subscription_status': 'active', 'preferred_language': 'en',
    'preferred_currency': 'CAD', 'role': 'user', 'account_status': 'active',
    'created_at': now, 'updated_at': now,
})
token = jwt.encode({'sub': uid, 'exp': int(time.time()) + 3600, 'type': 'access'}, ENV['JWT_SECRET'], algorithm='HS256')
r = requests.get(f'{API}/subscription/status', headers={'Authorization': f'Bearer {token}'}, timeout=45)
out = {'email': email, 'id': uid, 'status': r.status_code, 'response': r.json() if r.headers.get('content-type','').startswith('application/json') else r.text}
features = out['response'].get('features', {}) if isinstance(out['response'], dict) else {}
out['assertions'] = {
    'status_200': r.status_code == 200,
    'price': features.get('price') == '$300.00 CAD/year',
    'price_yearly_cad': features.get('price_yearly_cad') == 300.0,
    'price_monthly_cad': features.get('price_monthly_cad') == 25.0,
}
out['overall'] = 'passed' if all(out['assertions'].values()) else 'failed'
Path('/app/test_reports/iter399_vip_status_direct_result.json').write_text(json.dumps(out, indent=2, default=str))
print(json.dumps(out, indent=2, default=str))
if out['overall'] != 'passed':
    raise SystemExit(1)
