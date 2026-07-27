#!/usr/bin/env python3
"""Focused verification for iter399 subscription P1 regressions.
Creates test users, temporarily unsets subscription plan Stripe monthly IDs,
uses live Stripe API credentials from backend/.env as requested, and restores
MongoDB plan fields at the end (leaving non-null price IDs whenever possible).
"""
import asyncio
import json
import os
import re
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path

import requests
import stripe
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

APP_DIR = Path('/app')
ENV = dotenv_values(APP_DIR / 'backend' / '.env')
API_BASE = os.environ.get('API_BASE') or 'http://localhost:8001/api'
MONGO_URL = ENV.get('MONGO_URL')
DB_NAME = ENV.get('DB_NAME') or 'bazario_db'
STRIPE_API_KEY = ENV.get('STRIPE_API_KEY')
stripe.api_key = STRIPE_API_KEY

RESULT = {
    'api_base': API_BASE,
    'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'tests': {},
    'created_users': [],
    'created_stripe_sessions': [],
    'created_stripe_prices_seen': [],
    'restores': [],
}

class CheckError(Exception):
    pass

def check(name, condition, detail=''):
    if not condition:
        raise CheckError(f'{name} failed: {detail}')


def redact_url(url):
    if not url:
        return url
    return re.sub(r'(cs_(test|live)_[^#?]+)', r'cs_***', url)


def register_user(label):
    email = f'iter399_{label}_{uuid.uuid4().hex[:10]}@example.com'
    payload = {
        'email': email,
        'password': 'Iter399Test!23',
        'name': f'Iter399 {label}',
        'account_type': 'personal',
        'phone': f'+1514{str(int(time.time()*1000))[-7:]}',
        'terms_agreed': True,
        'ai_disclosure_consent': True,
    }
    r = requests.post(f'{API_BASE}/auth/register', json=payload, timeout=45)
    if r.status_code not in (200, 201):
        raise CheckError(f'register {label} failed: {r.status_code} {r.text[:500]}')
    data = r.json()
    token = data.get('access_token') or data.get('token') or data.get('accessToken')
    if not token and isinstance(data.get('data'), dict):
        token = data['data'].get('access_token')
    check(f'register {label} token', bool(token), data)
    user = data.get('user') or (data.get('data') or {}).get('user') or {}
    RESULT['created_users'].append({'label': label, 'email': email, 'id': user.get('id')})
    return token, email


def auth_headers(token):
    return {'Authorization': f'Bearer {token}'}


async def get_plan(db, plan_id):
    doc = await db.subscription_plans.find_one({'plan_id': plan_id}, {'_id': 0})
    if not doc:
        raise CheckError(f'plan {plan_id} not found')
    return doc


async def unset_monthly(db, plan_id):
    before = await get_plan(db, plan_id)
    await db.subscription_plans.update_one({'plan_id': plan_id}, {'$unset': {'stripe_price_id_monthly': ''}})
    after = await get_plan(db, plan_id)
    check(f'{plan_id} monthly unset', not after.get('stripe_price_id_monthly'), after)
    return before


async def set_field(db, plan_id, field, value):
    if value is None:
        await db.subscription_plans.update_one({'plan_id': plan_id}, {'$unset': {field: ''}})
    else:
        await db.subscription_plans.update_one({'plan_id': plan_id}, {'$set': {field: value}})


async def call_create_and_assert_minted(db, plan_id):
    token, email = register_user(f'create_{plan_id}')
    before_unset = await unset_monthly(db, plan_id)
    r = requests.post(
        f'{API_BASE}/subscriptions/create',
        headers=auth_headers(token),
        json={'plan_id': plan_id, 'billing_period': 'monthly'},
        timeout=90,
    )
    doc = await get_plan(db, plan_id)
    minted = doc.get('stripe_price_id_monthly')
    RESULT['tests'][f'create_lazy_mint_{plan_id}'] = {
        'http_status': r.status_code,
        'response': r.text[:500],
        'original_monthly_price_id': before_unset.get('stripe_price_id_monthly'),
        'minted_monthly_price_id': minted,
        'email': email,
    }
    check(f'{plan_id} create returns 400', r.status_code == 400, r.text[:500])
    check(f'{plan_id} create no customer guard', 'No Stripe customer on file' in r.text, r.text[:500])
    check(f'{plan_id} monthly price minted after 400', isinstance(minted, str) and minted.startswith('price_'), doc)
    RESULT['created_stripe_prices_seen'].append({'plan_id': plan_id, 'flow': 'subscriptions/create', 'price_id': minted})
    return minted, before_unset


async def call_checkout_and_assert_subscription_session(db):
    plan_id = 'premium'
    token, email = register_user('checkout_premium')
    before_unset = await unset_monthly(db, plan_id)
    r = requests.post(
        f'{API_BASE}/subscription/checkout',
        headers=auth_headers(token),
        json={'plan_id': plan_id, 'billing_period': 'monthly', 'origin_url': 'https://prod-verify-2.preview.emergentagent.com'},
        timeout=90,
    )
    doc = await get_plan(db, plan_id)
    minted = doc.get('stripe_price_id_monthly')
    test_key = 'checkout_lazy_mint_premium_monthly'
    RESULT['tests'][test_key] = {
        'http_status': r.status_code,
        'response': r.text[:500],
        'original_monthly_price_id': before_unset.get('stripe_price_id_monthly'),
        'minted_monthly_price_id': minted,
        'email': email,
    }
    check('checkout returns success', r.status_code == 200, r.text[:800])
    data = r.json()
    session_id = data.get('session_id')
    check('checkout session_id returned', isinstance(session_id, str) and session_id.startswith('cs_'), data)
    check('checkout monthly price minted', isinstance(minted, str) and minted.startswith('price_'), doc)
    RESULT['created_stripe_prices_seen'].append({'plan_id': plan_id, 'flow': 'subscription/checkout', 'price_id': minted})
    RESULT['created_stripe_sessions'].append({'session_id': session_id})

    sess = stripe.checkout.Session.retrieve(session_id)
    line_items = stripe.checkout.Session.list_line_items(session_id, limit=5)
    line_prices = []
    for item in getattr(line_items, 'data', []) or []:
        price_obj = getattr(item, 'price', None) or (item.get('price') if isinstance(item, dict) else None)
        price_id = getattr(price_obj, 'id', None) or (price_obj.get('id') if isinstance(price_obj, dict) else None)
        if price_id:
            line_prices.append(price_id)
    RESULT['tests'][test_key].update({
        'checkout_url_redacted': redact_url(data.get('checkout_url')),
        'stripe_session_id': session_id,
        'stripe_mode': getattr(sess, 'mode', None) or sess.get('mode'),
        'stripe_status': getattr(sess, 'status', None) or sess.get('status'),
        'stripe_line_price_ids': line_prices,
    })
    check('Stripe checkout mode is subscription', (getattr(sess, 'mode', None) or sess.get('mode')) == 'subscription', sess)
    check('Stripe checkout uses minted recurring price', minted in line_prices, {'minted': minted, 'line_prices': line_prices})
    return minted, before_unset


async def verify_tier_resolver(db):
    sys.path.insert(0, str(APP_DIR / 'backend'))
    from services.subscription_service import get_tier_from_price_id_async, PRICE_ID_TO_TIER
    plan_id = 'premium'
    doc = await get_plan(db, plan_id)
    original_yearly = doc.get('stripe_price_id_yearly')
    synthetic = f'price_iter399_test_{uuid.uuid4().hex[:8]}'
    PRICE_ID_TO_TIER.pop(synthetic, None)
    await set_field(db, plan_id, 'stripe_price_id_yearly', synthetic)
    try:
        tier = await get_tier_from_price_id_async(db, synthetic)
        cached = PRICE_ID_TO_TIER.get(synthetic)
        RESULT['tests']['tier_resolver_synthetic_admin_price'] = {
            'synthetic_price_id': synthetic,
            'resolved_tier': tier,
            'cached_tier': cached,
            'original_yearly_price_id_restored': original_yearly,
        }
        check('synthetic admin price resolves premium', tier == 'premium', {'tier': tier, 'cached': cached})
    finally:
        await set_field(db, plan_id, 'stripe_price_id_yearly', original_yearly)
        RESULT['restores'].append({'plan_id': plan_id, 'field': 'stripe_price_id_yearly', 'restored_to': original_yearly})


def login_admin_or_none():
    creds = {'email': 'charbel911@gmail.com', 'password': 'Anderosli123!@#'}
    r = requests.post(f'{API_BASE}/auth/login', json=creds, timeout=45)
    if r.status_code != 200:
        return None, {'status': r.status_code, 'text': r.text[:300]}
    data = r.json()
    return data.get('access_token') or data.get('token'), {'status': r.status_code}


async def set_user_tier_and_get_status(db, tier):
    token, email = register_user(f'status_{tier}')
    # Decode user id via /auth/me when available; fallback by email lookup.
    user_doc = await db.users.find_one({'email': email}, {'_id': 0, 'id': 1})
    check(f'status user {tier} exists in db', bool(user_doc and user_doc.get('id')), {'email': email})
    await db.users.update_one(
        {'id': user_doc['id']},
        {'$set': {'subscription_tier': tier, 'subscription_status': 'active' if tier != 'free' else 'inactive'}},
    )
    r = requests.get(f'{API_BASE}/subscription/status', headers=auth_headers(token), timeout=45)
    RESULT['tests'][f'status_{tier}'] = {'http_status': r.status_code, 'response': r.text[:800], 'email': email}
    check(f'/subscription/status {tier} 200', r.status_code == 200, r.text[:800])
    data = r.json()
    features = data.get('features') or {}
    RESULT['tests'][f'status_{tier}'].update({'features': features})
    if tier == 'premium':
        check('premium status price string', features.get('price') == '$180.00 CAD/year', features)
        check('premium yearly cad surfaced', float(features.get('price_yearly_cad')) == 180.0, features)
        check('premium monthly cad surfaced', float(features.get('price_monthly_cad')) == 15.0, features)
    elif tier == 'vip':
        check('vip status price string', features.get('price') == '$300.00 CAD/year', features)
        check('vip yearly cad surfaced', float(features.get('price_yearly_cad')) == 300.0, features)
        check('vip monthly cad surfaced', float(features.get('price_monthly_cad')) == 25.0, features)
    elif tier == 'free':
        check('free status no price key', 'price' not in features, features)
        check('free status no positive yearly price', 'price_yearly_cad' not in features, features)
        check('free status no positive monthly price', 'price_monthly_cad' not in features, features)


async def main():
    if not MONGO_URL or not STRIPE_API_KEY:
        raise CheckError('Missing MONGO_URL or STRIPE_API_KEY')
    # Connectivity smoke
    health = requests.get(f'{API_BASE}/', timeout=20)
    RESULT['health'] = {'status': health.status_code, 'text': health.text[:200]}
    check('api health', health.status_code == 200, RESULT['health'])

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    original_plans = {pid: await get_plan(db, pid) for pid in ['premium', 'vip']}
    RESULT['original_plan_price_ids'] = {
        pid: {
            'stripe_price_id_monthly': doc.get('stripe_price_id_monthly'),
            'stripe_price_id_yearly': doc.get('stripe_price_id_yearly'),
            'price_monthly': doc.get('price_monthly'),
            'price_yearly': doc.get('price_yearly'),
        } for pid, doc in original_plans.items()
    }

    try:
        await call_create_and_assert_minted(db, 'premium')
        await call_create_and_assert_minted(db, 'vip')
        await call_checkout_and_assert_subscription_session(db)
        await verify_tier_resolver(db)
        await set_user_tier_and_get_status(db, 'free')
        await set_user_tier_and_get_status(db, 'premium')
        await set_user_tier_and_get_status(db, 'vip')
        RESULT['overall'] = 'passed'
    except Exception as exc:
        RESULT['overall'] = 'failed'
        RESULT['error'] = repr(exc)
        raise
    finally:
        # Keep downstream tests safe: if a monthly ID exists after minting, leave it populated.
        # If any failed before minting and left a null monthly ID, restore the original if available.
        for pid, original in original_plans.items():
            current = await get_plan(db, pid)
            if not current.get('stripe_price_id_monthly') and original.get('stripe_price_id_monthly'):
                await set_field(db, pid, 'stripe_price_id_monthly', original.get('stripe_price_id_monthly'))
                RESULT['restores'].append({'plan_id': pid, 'field': 'stripe_price_id_monthly', 'restored_to': original.get('stripe_price_id_monthly'), 'reason': 'current_missing'})
            elif current.get('stripe_price_id_monthly'):
                RESULT['restores'].append({'plan_id': pid, 'field': 'stripe_price_id_monthly', 'left_populated_as': current.get('stripe_price_id_monthly')})
        final_plans = {pid: await get_plan(db, pid) for pid in ['premium', 'vip']}
        RESULT['final_plan_price_ids'] = {
            pid: {
                'stripe_price_id_monthly': doc.get('stripe_price_id_monthly'),
                'stripe_price_id_yearly': doc.get('stripe_price_id_yearly'),
            } for pid, doc in final_plans.items()
        }
        client.close()
        out = APP_DIR / 'test_reports' / 'iter399_subscription_p1_results.json'
        out.write_text(json.dumps(RESULT, indent=2, default=str))
        print(json.dumps(RESULT, indent=2, default=str))

if __name__ == '__main__':
    asyncio.run(main())
