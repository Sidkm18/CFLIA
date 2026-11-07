#!/usr/bin/env python3
"""Capture selected real v2 responses, redacting live credentials and tokens."""
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('stack', ROOT / 'v2/scripts/verify_stack.py')
stack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stack)
dest = ROOT / 'submission/evidence'
cookie, token, auth = stack.login()
captures = []

def capture(ident, path, method='GET', data=None, supplied_cookie=cookie, origin=None):
    result = stack.call(path, method, data, supplied_cookie, origin)
    headers = dict(result['headers'])
    if 'Set-Cookie' in headers:
        headers['Set-Cookie'] = re.sub(r'(^[^=]+=)[^;]+', r'\1[redacted]', headers['Set-Cookie'])
    body = re.sub(r'(name="csrf_token" value=")[^"]+', r'\1[redacted]', result['body'])
    safe_data = {k: '[redacted]' if k in {'csrf_token','password'} else v for k,v in (data or {}).items()}
    item = dict(id=ident, method=method, path=path, request_body=safe_data,
                request_identity='Alice session [redacted]' if supplied_cookie == cookie else supplied_cookie,
                origin=origin, status=result['status'], headers=headers, body=body,
                latency_ms=result['latency_ms'])
    captures.append(item)
    return result

capture('V01', '/login', 'POST', {'username': "' OR 1=1 -- ", 'password': 'wrong', 'csrf_token': token}, origin=stack.ORIGIN)
capture('V02', '/comment', 'POST', {'ticket_id': '1001', 'body': '<svg onload="this.outerHTML=\'<p>XSS executed</p>\'"></svg>', 'csrf_token': token}, origin=stack.ORIGIN)
capture('V03', '/ticket?id=1002')
capture('V04', '/admin', supplied_cookie='user_id=1')
capture('V04-role', '/admin')
before = stack.call('/account', cookie=cookie)
old_email = re.search(r'name="email"[^>]*value="([^"]+)"', before['body'])[1]
capture('V05', '/account/email', 'POST', {'email': 'alice.updated@example.test'}, origin='http://127.0.0.1:8091')
after = stack.call('/account', cookie=cookie)
assert f'value="{old_email}"' in after['body']
capture('V06', '/download?' + urlencode({'file':'../private/legacy-config.txt'}))
capture('V07', '/debug', supplied_cookie=None)
auth_headers = dict(auth['headers'])
auth_headers['Set-Cookie'] = re.sub(r'(^[^=]+=)[^;]+', r'\1[redacted]', auth_headers['Set-Cookie'])
captures.append({'id':'session-policy','status':auth['status'],'headers':auth_headers})
stack.call('/logout', 'POST', {'csrf_token':token}, cookie, stack.ORIGIN)
text = json.dumps({'target':stack.ORIGIN,'email_unchanged':True,'captures':captures}, indent=2)
assert all(secret not in text for secret in [cookie.split('=',1)[1],token,*stack.creds.values()])
(dest / 'v2-http-responses.json').write_text(text+'\n')
print('Captured seven attack responses, role denial and secure cookie flags; live tokens redacted.')
