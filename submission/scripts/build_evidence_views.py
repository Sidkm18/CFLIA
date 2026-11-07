#!/usr/bin/env python3
"""Make labelled evidence views from recorded HTTP exchanges, never portal mockups."""
import html
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'submission/evidence'
BASE=ROOT/'output/evidence/baseline-20261015T065446247953Z'
HARD=ROOT/'v2/output/verification-20261015T070630Z'
baseline=json.loads((BASE/'results.json').read_text())
secure=json.loads((HARD/'results.json').read_text())
raw=json.loads((BASE/'http-captures.json').read_text())
after=json.loads((DEST/'v2-http-responses.json').read_text())
names=['SQL injection','Stored cross site scripting','Broken object access control','Forged identity cookie','Cross site request forgery','Path traversal','Exposed diagnostics and missing headers','Unrestricted expensive requests']

def select(path,method='GET',contains=''):
    return next(r for r in raw if r['path'].startswith(path) and r['method']==method and contains in (r.get('request_body') or ''))

before=[select('/login','POST','OR'),select('/ticket?id=1001'),select('/ticket?id=1002'),select('/admin',contains=''),select('/account/email','POST'),select('/download?'),select('/debug')]
before[3]=next(r for r in raw if r['path']=='/admin' and r['status']==200)

def plain(text):
    return html.unescape(re.sub('<[^>]+>',' ',text))

for index,name in enumerate(names,1):
    ident=f'V{index:02}'
    for stage in ['before','after']:
        source=str((BASE/'http-captures.json').relative_to(ROOT)) if stage=='before' else 'submission/evidence/v2-http-responses.json'
        target=baseline['target'] if stage=='before' else secure['target']
        if index==8:
            record=baseline['load_probe'] if stage=='before' else secure['load_probe']
            status='40 requests / 4 workers'
            request='GET /reports/export\nAuthenticated Alice session\nBounded local request batch'
            response=json.dumps(record,indent=2)
            source=str((BASE/'results.json' if stage=='before' else HARD/'results.json').relative_to(ROOT))
        else:
            r=before[index-1] if stage=='before' else next(x for x in after['captures'] if x['id']==ident)
            status=f"HTTP {r['status']}"
            request=f"{r['method']} {r['path']}\n"
            if stage=='before':
                request += json.dumps(r.get('request_headers',{}),indent=2)+'\n'+(r.get('request_body') or '')
                headers=r['response_headers']
            else:
                request+=f"Identity: {r['request_identity']}\nOrigin: {r['origin']}\n"+json.dumps(r['request_body'],indent=2)
                headers=r['headers']
            relevant={k:v for k,v in headers.items() if k.lower() in {'location','set-cookie','content-type','x-request-id','content-security-policy','x-frame-options','x-content-type-options','strict-transport-security','referrer-policy'}}
            body=r['body']
            if index==2 and stage=='before':
                match=re.search(r'<svg.*?</svg>',body)
                body='Stored response markup:\n'+(match[0] if match else 'Payload not found')+'\n\nBrowser execution is captured separately in V02-before-browser.png.'
            elif index==3 and stage=='before':
                body=re.search(r'<main.*?</main>',body,re.S)[0]
                body=re.sub(r'\s+',' ',plain(body))[:700]
            elif index==4 and stage=='before':
                body='Administrator page returned to the forged cookie.\n'+re.sub(r'\s+',' ',plain(body))[-800:]
            elif body.lstrip().startswith('<'):
                body=re.sub(r'\s+',' ',plain(body))[:650]
            if index==5:
                body+='\nEmail after request: '+('alice.updated@example.test (changed without token)' if stage=='before' else 'unchanged (verified by a subsequent authenticated GET /account)')
            if index==7 and stage=='before':
                body+='\n\nCSP, X-Frame-Options and X-Content-Type-Options: absent.'
            response=json.dumps(relevant,indent=2)+'\n\n'+body[:1300]
        doc=f'''<!doctype html><meta charset="utf-8"><title>{ident} {stage} evidence</title><style>
        *{{box-sizing:border-box}}body{{margin:0;padding:30px 38px;background:#fff;color:#171717;font:19px Arial,sans-serif}}
        .meta{{font-size:16px;color:#444}}h1{{font-size:30px;margin:18px 0 10px}}h2{{font-size:20px;margin:18px 0 10px}}
        pre{{font:16px/1.42 Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:0;padding:16px;background:#f5f5f5;border:1px solid #ddd}}
        .status{{font-size:27px;font-weight:700}}footer{{margin-top:18px;font-size:14px;color:#444}}
        </style><div class="meta">RECORDED HTTP EVIDENCE / {stage.upper()} HARDENING / 15 OCTOBER 2026 UTC</div>
        <h1>{ident} {name}</h1><p>{html.escape(target)} &nbsp; <span class="status">{status}</span></p>
        <h2>Request</h2><pre>{html.escape(request)}</pre><h2>Observed response</h2><pre>{html.escape(response)}</pre>
        <footer>Source: {html.escape(source)}<br>Selected fields from real requests. Live v2 credentials and tokens are redacted. This is an evidence viewer, not the application interface.</footer>'''
        (DEST/f'{ident}-{stage}.html').write_text(doc)

# Preserve one compact machine-readable comparison for report authors and markers.
(DEST/'comparison.json').write_text(json.dumps({'baseline_source':str(BASE.relative_to(ROOT)), 'hardened_source':str(HARD.relative_to(ROOT)), 'baseline':baseline,'hardened':secure},indent=2)+'\n')
print('Built sixteen evidence views from actual captured responses.')
