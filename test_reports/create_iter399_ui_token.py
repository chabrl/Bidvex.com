import json, time, uuid
from pathlib import Path
from dotenv import dotenv_values
from jose import jwt
from pymongo import MongoClient
ENV=dotenv_values('/app/backend/.env')
client=MongoClient(ENV['MONGO_URL'])
db=client[ENV.get('DB_NAME','bazario_db')]
uid=str(uuid.uuid4())
email=f'iter399_ui_monthly_{uuid.uuid4().hex[:10]}@example.com'
now=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
db.users.insert_one({'id':uid,'email':email,'name':'Iter399 UI Monthly','account_type':'personal','phone':'','subscription_tier':'free','subscription_status':'inactive','preferred_language':'en','preferred_currency':'CAD','role':'user','account_status':'active','created_at':now,'updated_at':now})
token=jwt.encode({'sub':uid,'exp':int(time.time())+3600,'type':'access'}, ENV['JWT_SECRET'], algorithm='HS256')
out={'id':uid,'email':email,'token':token}
Path('/app/test_reports/iter399_ui_token.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'id':uid,'email':email,'token_prefix':token[:20]},indent=2))
