#!/usr/bin/env python3
"""Build the final report and four-person presentation pack from real evidence."""
import json
import re
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/documents'; OUT.mkdir(parents=True,exist_ok=True)
FIG=ROOT/'submission/evidence/figures'; FIG.mkdir(parents=True,exist_ok=True)
CAP=ROOT/'output/playwright/final'
DATA=json.loads((ROOT/'submission/evidence/comparison.json').read_text())
B=DATA['baseline']['load_probe']; H=DATA['hardened']['load_probe']

CASES=[
dict(id='V01',name='SQL injection',mapping='A05 2025 Injection',
cause='The original login concatenates the supplied username and password into executable SQL. The injected condition changes which row is selected. Search also constructs SQL from the query string.',
impact='A username payload selects the administrator without knowing the administrator password. Search can also break the normal ownership scope.',
payload="POST /login\nusername=' OR 1=1 -- \npassword=wrong",
before='The recorded response was HTTP 303 with user_id=1. The browser then displayed the administrator identity. A redirect alone would not prove authentication; the returned identity and subsequent page provide that evidence.',
steps='Open the original login page, enter the injected username and a wrong password, and submit. Show the administrator identity. Do not enter a real password.',
fix='V2 looks up the account using a bound SQL parameter, validates username syntax, and verifies a salted password hash separately. Ticket search uses bound parameters and escapes LIKE wildcards. CRS adds SQL injection detection at the gateway.',
code='v2/app/server.py   login and tickets\nSELECT * FROM users WHERE username=?\ncheck_password_hash(..., password)',
after='The same injection is rejected with HTTP 403 by the deployed WAF. Direct application tests bypass the WAF and show HTTP 400 for the invalid username, no admin access, and literal search handling.',
positive='A valid employee can still sign in and search their own tickets.',ref='[2]'),
dict(id='V02',name='Stored cross site scripting',mapping='A05 2025 Injection',
cause='The comment body is saved in SQLite and inserted into a later HTML response without output encoding. A browser therefore interprets the stored content as markup.',
impact='Stored browser code executes when the ticket is viewed. The proof changes only its own element to the words XSS executed; it does not exfiltrate data.',
payload='<svg onload="this.outerHTML=\'<p>XSS executed</p>\'"></svg>',
before='The payload was stored and returned as raw markup. A fresh browser capture showed XSS executed inside the conversation. The DOM check found one proof paragraph, confirming execution rather than merely displaying source text.',
steps='Sign in as Alice on v1, open ticket 1001, paste the payload into a comment, submit, and show the changed element in the conversation.',
fix='V2 HTML-encodes comment bodies and other untrusted text at rendering time. CSP disallows inline script and event handlers. CRS blocks the incoming XSS pattern. Encoding is the root-cause fix; a WAF rule is an additional layer.',
code='v2/app/server.py   ticket\n<div class="comment-body">{esc(c["body"])}</div>\nv2/infra/gateway.conf   Content-Security-Policy',
after='The full-stack replay receives HTTP 403. A separate direct-origin test stores the same payload and verifies escaped output. The saved v2 browser capture displays the literal payload with zero raw SVG elements and zero executed proof paragraphs.',
positive='An ordinary comment is accepted and visible on the employee ticket.',ref='[3]'),
dict(id='V03',name='Broken object access control',mapping='A01 2025 Broken Access Control',
cause='The original ticket endpoint requires a signed-in identity but does not check whether that identity owns the requested object. Changing an ID is sufficient to select another employee record.',
impact='Alice can read Bob payroll information by requesting ticket 1002. This is an authorization failure even though the request is authenticated.',
payload='GET /ticket?id=1002\nCookie: user_id=2',
before='HTTP 200 returned Bob payroll adjustment to Alice. The screenshot shows both Alice in the signed-in header and Bob as the ticket owner. ZAP history separately records changing 1001 to 1002.',
steps='Open Alice ticket 1001. Change only the id parameter to 1002 in the address bar or ZAP request editor. Keep the same Alice identity.',
fix='V2 resolves the ticket through ticket_for and checks owner_id against the server-side user ID, with an explicit administrator exception. The same check runs before reading a ticket or adding a comment.',
code='v2/app/server.py   ticket_for\nif ticket["owner_id"] != g.user["id"]\n   and g.user["role"] != "admin": abort(403)',
after='Alice receives HTTP 403 and the response does not contain Bob payroll text. Direct tests also deny comment writes to Bob ticket, while Bob and the administrator retain authorized access.',
positive='Alice can still read and comment on ticket 1001.',ref='[4]'),
dict(id='V04',name='Forged identity cookie',mapping='A07 2025 Authentication Failures',
cause='The original user_id cookie is accepted as the identity itself. Its integer value is neither unpredictable nor validated against a server-side session. Original passwords are also weak and stored as plaintext.',
impact='Replacing Alice user_id=2 with user_id=1 grants administrator privileges without authenticating as the administrator.',
payload='GET /admin\nCookie: user_id=1',
before='Alice received HTTP 403 on /admin. The forged administrator cookie received HTTP 200 and displayed the administrator page. This isolates session forgery from the separate SQL injection weakness.',
steps='Show /admin denied to Alice. In browser cookie tools change user_id from 2 to 1, reload /admin, and show that access is now granted.',
fix='V2 uses a random 256-bit session token, stores only its SHA-256 hash server-side, rotates it at login, and revokes it at logout. It enforces idle and absolute expiry, caps sessions per user, and hashes unique generated passwords using PBKDF2. The cookie has Secure, HttpOnly and SameSite Strict attributes.',
code='v2/app/server.py   new_session and finish\nCOOKIE = "__Host-legacydesk_v2"\nsecrets.token_urlsafe(32)\nPASSWORD_METHOD = "pbkdf2:sha256:600000"',
after='A request containing only user_id=1 receives HTTP 401 in v2. A valid Alice session still receives HTTP 403 on /admin. Direct tests verify old-password rejection, rotation, expiration and logout invalidation.',
positive='Valid employee login works; the administrator role is tested separately.',ref='[5]'),
dict(id='V05',name='Cross site request forgery',mapping='A01 2025 Broken Access Control',
cause='The original email update accepts a form POST with a session cookie without validating a CSRF token or the request Origin.',
impact='A form hosted on a different origin can update Alice contact address using her browser session. The local example uses a second port, so it is cross-origin while remaining on the same site.',
payload='POST /account/email\nOrigin: http://127.0.0.1:8091\nemail=alice.updated@example.test\nNo CSRF token',
before='The HTTP replay returned 303 and the account contained the replacement email. A real browser also submitted the separate contact-preferences page and arrived at the updated account.',
steps='Keep Alice signed in on v1. Open the contact-preferences form at port 8091 and press Confirm contact details. Show the destination account page.',
fix='Every v2 state-changing form includes a synchronizer token tied to the server-side session. The server validates the token with a constant-time comparison and requires an exact allowed Origin, including for login and logout. SameSite Strict provides another browser layer.',
code='v2/app/server.py   prepare\nOrigin must belong to configured ORIGINS\nhmac.compare_digest(token, g.session["csrf"])',
after='The cross-origin tokenless HTTP request receives HTTP 403 even when the harness supplies the authenticated cookie. A subsequent account read verifies the email is unchanged. Valid same-origin browser forms continue to work.',
positive='An authenticated update with the correct token and Origin succeeds.',ref='[6]'),
dict(id='V06',name='Path traversal',mapping='A01 2025 Broken Access Control',
cause='The original download endpoint joins an attacker-controlled filename to the downloads directory. Parent components can escape that directory into a private fixture directory.',
impact='A request for ../private/legacy-config.txt discloses the private configuration fixture. The containing fixtures boundary prevents this exercise from reading arbitrary host files.',
payload='GET /download?file=../private/legacy-config.txt',
before='HTTP 200 returned the internal configuration, including the fixture DB_PASSWORD value. These are seeded project values, not real infrastructure credentials.',
steps='Open the original download URL with the parent-directory filename. Point out the private configuration response instead of the public handbook.',
fix='V2 authenticates downloads and maps the exact allowed name employee-handbook.txt to a fixed server-owned file. User input is never combined into an arbitrary path. CRS provides an additional path-access filter.',
code='v2/app/server.py   download\nallowed = {"employee-handbook.txt": fixed_path}\nif filename not in allowed: abort(404)',
after='The deployed malicious filename receives HTTP 403 from the WAF without configuration data. Direct-origin tests return 404 for traversal, absolute paths and encoded variants. The public handbook still downloads for authorized users.',
positive='The authenticated employee handbook request receives HTTP 200.',ref='[1]'),
dict(id='V07',name='Exposed diagnostics and missing headers',mapping='A02 2025 Security Misconfiguration',
cause='The original /debug endpoint is publicly reachable and serializes the user table, including plaintext passwords. Error details are verbose and browser security headers are absent.',
impact='An anonymous visitor can retrieve seeded account credentials and implementation details. Missing browser policies leave fewer constraints on framing, content interpretation and injected code.',
payload='GET /debug\nNo authentication',
before='HTTP 200 exposed debug=true, the database location and the seeded password values. The captured response lacked CSP, X-Frame-Options and X-Content-Type-Options.',
steps='Open /debug anonymously and inspect the response headers. Use the captured seeded values only; never put generated v2 credentials on screen.',
fix='V2 removes the debug route, returns generic public error pages and keeps diagnostic exceptions in server logs. Nginx and the application set CSP, nosniff, frame restrictions, referrer and permissions policies. HTTPS adds HSTS. Gateway errors also use Cache-Control no-store.',
code='v2/app/server.py   error and finish\nv2/infra/gateway.conf   add_header ... always\nNo /debug route is registered',
after='Anonymous /debug returns HTTP 404 with no password data. Security headers are present on error responses. The Nmap scan shows a version banner on v1, while v2 suppresses the Nginx version; banner removal is a supporting measure, not a patch by itself.',
positive='Normal portal pages remain available with the same visual design.',ref='[1]'),
dict(id='V08',name='Unrestricted expensive requests',mapping='API4 2023 Unrestricted Resource Consumption',
cause='The original export performs work for every authenticated call and has no fine-grained admission control or caching. Its artificial 0.2 second delay makes repeated expensive work observable in a bounded local test.',
impact='One identity can repeatedly consume report capacity. The experiment measures unrestricted admission; it does not demonstrate an outage or a distributed denial-of-service attack.',
payload='GET /reports/export\n40 requests total\n4 concurrent workers\nAuthenticated Alice identity',
before=f'All 40 requests returned HTTP 200. Elapsed time was {B["elapsed_seconds"]} s, median latency {B["median_latency_ms"]} ms and p95 {B["p95_latency_ms"]} ms. No HTTP 429 was observed.',
steps='Run the bounded baseline probe against localhost. Keep the request count and worker count visible. Show the status distribution before discussing latency.',
fix='Nginx limits request rate and connections. The application uses atomic per-user quotas and caches user-scoped report data for 30 seconds. It also bounds request bodies, worker resources and timeouts. Anonymous sign-in sessions are capped at 1,000 and expired or idle entries are collected on creation.',
code='v2/infra/gateway.conf\nreports: 2 requests/second, burst 4; 12 connections/IP\nv2/app/server.py   report\nrate("report:" + str(uid), 6, 60)',
after=f'The identical 40-request, four-worker schedule produced 5 HTTP 200 responses and 35 HTTP 429 rejections. Elapsed time was {H["elapsed_seconds"]} s, median {H["median_latency_ms"]} ms and p95 {H["p95_latency_ms"]} ms. The application-only concurrent test separately admits exactly 6 of 40 calls.',
positive='An allowed report still returns Alice ticket count. Fast rejection contributes to the lower latency; the result is not an equal-work throughput benchmark.',ref='[7]')]

SPEAKERS=[
dict(name='Member 1',time='00:00 to 01:45',cases='V01 SQL injection and V02 stored XSS',
speech=[('00:00 to 00:10','This is LegacyDesk, an employee service portal behind Nginx. We tested eight weaknesses, then created a separate hardened version. Each of us will show two attacks, their fixes, and the retests.'),
('00:10 to 00:55','First, SQL injection. I enter this condition as the username and use a wrong password. The original application signs me in as the administrator because it joins input directly into SQL. Here is the fix in v2: a parameterized account lookup, separate password-hash verification, and validated input. The WAF adds another filter. Repeating the same payload now returns forbidden, and the direct application tests also confirm that it cannot create an administrator session.'),
('00:55 to 01:40','Next, stored cross-site scripting. I submit this SVG comment on the original ticket. When the page renders, the event handler replaces its element with XSS executed. In v2, comments are encoded before entering HTML. CSP restricts executable content, and the WAF blocks this payload. The same public request is rejected. In the separate origin test, the payload appears as literal text and creates no SVG element. Ordinary comments still work.'),
('01:40 to 01:45','Member two will now show object access and session security.')],
actions=['Prepare v1 login and ticket 1001, v2 HTTP evidence for V01 and V02, and the login/ticket functions side by side.', '00:10: submit the SQL username with password wrong. Show administrator identity. At 00:28, point to the v2 bound query; at 00:42, show HTTP 403.', '00:55: submit the SVG on v1 and hold XSS executed for 3 seconds. At 01:12, show esc(c["body"]) and CSP. At 01:28, show WAF rejection and the v2 encoded screenshot.'],
fixfiles='v2/app/server.py login and ticket; v2/infra/gateway.conf CSP'),
dict(name='Member 2',time='01:45 to 03:30',cases='V03 object access and V04 forged sessions',
speech=[('01:45 to 02:30','I am signed in as Alice. Changing ticket 1001 to 1002 reveals Bob payroll details in the original application. The login is valid, but permission on the selected record is missing. In v2, the shared ticket lookup checks ownership or the administrator role before reading a ticket or posting a comment. I repeat the request as Alice and receive forbidden. Alice can still open her own ticket, and the tests confirm that Bob can open his.'),
('02:30 to 03:15','The next flaw is the identity cookie. Alice cannot open administration, but changing user_id from two to one grants access in v1. V2 replaces that integer with an unpredictable server-side session and stores only a token hash. It rotates sessions on login, expires idle sessions, and invalidates logout. Passwords are now salted hashes, and the cookie is Secure, HttpOnly and SameSite Strict. The forged original cookie now receives unauthorized; a genuine Alice session remains forbidden from administration.'),
('03:15 to 03:30','These checks enforce two different boundaries: whether a session is valid and whether that user may access the requested record. Member three will show forged requests and file access.')],
actions=['Prepare Alice v1 ticket 1001, browser cookie tools, and V03/V04 v2 evidence. Close any administrator tab from Member 1 or use a separate Alice context.', '01:45: change only id=1001 to id=1002. Hold Alice header and Bob owner together. At 02:05 show ticket_for; at 02:20 show v2 HTTP 403.', '02:30: show Alice /admin denial, change user_id to 1 and reload. At 02:50 show random token and cookie flags; at 03:05 show v2 401 and Alice 403.'],
fixfiles='v2/app/server.py ticket_for, new_session, prepare, finish and logout'),
dict(name='Member 3',time='03:30 to 05:15',cases='V05 CSRF and V06 path traversal',
speech=[('03:30 to 04:15','Alice is signed in to the original portal. This contact-preferences form is hosted on a different origin. Submitting it changes her email because the original endpoint accepts a cookie without checking a token or Origin. V2 requires both a session-bound CSRF token and an exact allowed Origin on state-changing forms. SameSite cookies add another layer. Repeating the tokenless cross-origin request now returns forbidden, and an authenticated account read confirms that the email stayed unchanged.'),
('04:15 to 05:00','For path traversal, I change the download filename to a parent-directory path. The original endpoint returns the private configuration fixture instead of the handbook. V2 requires authentication and accepts only an exact allowlisted filename mapped to a fixed file. It does not build a filesystem path from the request. The WAF provides another filter. The traversal request now returns forbidden; direct origin tests also reject it with not found. A normal handbook download still succeeds.'),
('05:00 to 05:15','The CSRF fix validates the source and intent of a state change. The download fix restricts which file can be selected. Member four will finish with configuration and availability controls.')],
actions=['Prepare the v1 account, port 8091 contact form, and traversal URL. Keep v2 V05/V06 evidence ready.', '03:30: submit the separate-origin form and show the changed account email. At 03:50 point to Origin and token checks; at 04:05 show HTTP 403 and unchanged-email verification.', '04:15: open the traversal URL and hold the fixture configuration. At 04:32 show the exact download allowlist; at 04:47 show v2 denial and the normal handbook positive check.'],
fixfiles='v2/app/server.py prepare and download'),
dict(name='Member 4',time='05:15 to 07:00',cases='V07 misconfiguration and V08 resource consumption',
speech=[('05:15 to 05:55','The original public debug endpoint exposes account passwords and internal details. Its response also lacks the browser security headers we checked. V2 removes that route, uses generic errors, enforces HTTPS, and adds CSP, frame restrictions, nosniff and other policies. These headers also cover error responses, including WAF blocks. Opening debug now returns not found without account data. Generated v2 credentials remain private and are never included in our evidence.'),
('05:55 to 06:40','Finally, repeated report generation. We use a bounded local batch of forty requests with four workers. V1 accepts all forty. V2 adds Nginx request and connection limits, atomic application quotas, cached reports, bounded workers and timeouts. The same schedule now produces five successful responses and thirty-five rate-limit responses. Allowed requests still work. Faster rejection lowers measured latency, so this is evidence of admission control, not proof of protection against every denial-of-service attack.'),
('06:40 to 07:00','All eight attack scenarios now have before-and-after evidence. Nineteen application tests and seventeen deployed-stack checks pass. The original portal remains separate. The result is layered protection: application fixes, a WAF, traffic limits and security logs, with normal employee workflows preserved.')],
actions=['Prepare /debug on both versions, captured headers, the two load result files, and the comparison chart. Wait at least 60 seconds before rerunning a full rate-limit test.', '05:15: show v1 debug briefly, then the removed route and header configuration. At 05:40 show v2 HTTP 404 and response headers.', '05:55: run or play the saved 40-request result. Show 40/0 before and 5/35 after with four workers visible. At 06:20 point to Nginx limits, app quota and cache. At 06:40 show the 19-test and 17-check results.'],
fixfiles='v2/infra/gateway.conf; v2/app/server.py finish, report and new_session')]

class Writer:
    def __init__(self,title):
        self.doc=Document(); self.md=[]
        s=self.doc.sections[0]
        s.page_width=Inches(8.5);s.page_height=Inches(11)
        s.top_margin=s.bottom_margin=Inches(.65);s.left_margin=s.right_margin=Inches(.75)
        s.header_distance=s.footer_distance=Inches(.3)
        styles=self.doc.styles
        for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','Caption']:
            styles[name].font.name='Arial';styles[name].font.color.rgb=RGBColor(0,0,0)
            styles[name].paragraph_format.space_after=Pt(7)
        styles['Normal'].font.size=Pt(11)
        styles['Normal'].paragraph_format.line_spacing=1.12
        styles['Title'].font.size=Pt(25);styles['Subtitle'].font.size=Pt(14)
        styles['Heading 1'].font.size=Pt(18);styles['Heading 2'].font.size=Pt(13)
        styles['Caption'].font.size=Pt(9)
        for root in [self.doc._element, styles.element]:
            for border in root.xpath('.//w:pBdr'):
                border.getparent().remove(border)
        h=s.header.paragraphs[0];h.text='CFLIA  |  LegacyDesk security project';h.style='Caption'
        f=s.footer.paragraphs[0];f.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        f.add_run('Page ')
        field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');f._p.append(field)
        self.title(title)
    def title(self,t):
        self.doc.add_paragraph(t,'Title');self.md+=['# '+t,'']
    def p(self,t,style=None):
        self.doc.add_paragraph(t,style);self.md += [t,'']
    def h(self,t):
        self.doc.add_paragraph(t,'Heading 2');self.md+=['## '+t,'']
    def page(self,t):
        p=self.doc.add_paragraph(t,'Heading 1');p.paragraph_format.page_break_before=True
        self.md+=['---','','# '+t,'']
    def code(self,t):
        p=self.doc.add_paragraph();p.paragraph_format.space_after=Pt(8)
        for i,line in enumerate(t.splitlines()):
            r=p.add_run(('\n' if i else '')+line);r.font.name='Courier New';r.font.size=Pt(9)
        self.md+=['```text',t,'```','']
    def table(self,headers,rows,widths):
        tab=self.doc.add_table(rows=1, cols=len(headers));tab.alignment=WD_TABLE_ALIGNMENT.CENTER;tab.autofit=False
        for col,w in zip(tab.columns,widths):col.width=Inches(w)
        for cell,t,w in zip(tab.rows[0].cells,headers,widths):cell.text=str(t);cell.width=Inches(w)
        trpr=tab.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
        for row in rows:
            for cell,t,w in zip(tab.add_row().cells,row,widths):cell.text=str(t);cell.width=Inches(w)
        for i,row in enumerate(tab.rows):
            for j,cell in enumerate(row.cells):
                cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                pr=cell._tc.get_or_add_tcPr()
                borders=OxmlElement('w:tcBorders')
                for side in ['top','left','bottom','right']:
                    b=OxmlElement('w:'+side);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'D9D9D9');borders.append(b)
                pr.append(borders)
                margin=OxmlElement('w:tcMar')
                for side in ['top','left','bottom','right']:
                    m=OxmlElement('w:'+side);m.set(qn('w:w'),'95');m.set(qn('w:type'),'dxa');margin.append(m)
                pr.append(margin)
                shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E9E9E9' if i==0 else 'FFFFFF');pr.append(shade)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after=Pt(2);p.paragraph_format.line_spacing=1.05
                    for r in p.runs:r.font.size=Pt(10);r.bold=i==0
                    if j==0 and len(str(row.cells[0].text))<20:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        self.md += ['| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]
        self.md += ['| '+' | '.join(str(x).replace('\n',' ') for x in row)+' |' for row in rows]+['']
        self.doc.add_paragraph().paragraph_format.space_after=Pt(1)
    def image(self,path,caption,maxheight=4.8):
        p=Path(path);im=Image.open(p).convert('RGB')
        # Trim only empty white margins; do not change captured content.
        box=ImageChops.difference(im,Image.new('RGB',im.size,'white')).getbbox()
        if box:
            box=(0,0,im.width,min(im.height,box[3]+20));im=im.crop(box)
        if p.stem=='V07-before-http':
            # Legible excerpt through the first exposed account; the full capture stays in the pack.
            im=im.crop((0,0,im.width,735))
        derived=FIG/(p.stem+'-print.png');im.save(derived)
        width=min(7.0,maxheight*im.width/im.height)
        para=self.doc.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_after=Pt(2);para.paragraph_format.keep_with_next=True
        para.add_run().add_picture(str(derived),width=Inches(width))
        self.p(caption,'Caption');self.md+=['!['+caption+'](evidence/figures/'+derived.name+')','']
    def save(self,name,mdname):
        self.doc.core_properties.title=name.replace('_',' ')
        self.doc.core_properties.author='CFLIA project team'
        self.doc.save(OUT/(name+'.docx'))
        (ROOT/'submission'/mdname).write_text('\n'.join(line.rstrip() for line in self.md).rstrip()+'\n')

def figures():
    font='/System/Library/Fonts/Supplemental/Arial.ttf'
    im=Image.new('RGB',(1500,430),'white');d=ImageDraw.Draw(im)
    f=ImageFont.truetype(font,27);small=ImageFont.truetype(font,22)
    boxes=[('Browser','Local client'),('Nginx gateway','TLS 8443 and limits'),('ModSecurity','OWASP CRS WAF'),('Flask app','Gunicorn on 8000'),('SQLite','Private volume')]
    for i,(title,sub) in enumerate(boxes):
        x=20+i*300;d.rectangle((x,110,x+260,235),outline='#333',width=2,fill='#f3f3f3')
        d.text((x+16,138),title,font=f,fill='black');d.text((x+16,185),sub,font=small,fill='black')
        if i<4:
            d.line((x+260,172,x+294,172),fill='black',width=3);d.polygon([(x+294,172),(x+283,165),(x+283,179)],fill='black')
    d.text((22,36),'Deployed v2 request path',font=ImageFont.truetype(font,34),fill='black')
    d.text((22,290),'Only the gateway is published on loopback. WAF and application ports stay internal.',font=f,fill='black')
    d.text((22,340),'HTTP 8082 redirects to HTTPS 8443. The original stack remains separate on HTTP 8080.',font=f,fill='black')
    im.save(FIG/'architecture.png')
    im=Image.new('RGB',(1500,490),'white');d=ImageDraw.Draw(im)
    for y,(label,ok,rejected) in enumerate([('Vulnerable v1',40,0),('Hardened v2',5,35)]):
        top=55+y*140;start=300;unit=27
        d.text((28,top+24),label,font=f,fill='black')
        d.rectangle((start,top,start+ok*unit,top+85),fill='#555555')
        d.text((start+ok*unit/2,top+42),str(ok),font=f,fill='white',anchor='mm')
        if rejected:
            d.rectangle((start+ok*unit,top,start+40*unit,top+85),fill='#cccccc')
            d.text((start+(ok+rejected/2)*unit,top+42),str(rejected),font=f,fill='black',anchor='mm')
    for value in [0,10,20,30,40]:
        x=300+value*27;d.text((x,312),str(value),font=small,fill='black',anchor='mm')
    d.text((300,350),'Requests in one bounded batch with four workers',font=f,fill='black')
    d.rectangle((300,413,335,445),fill='#555555');d.text((350,416),'HTTP 200 accepted',font=small,fill='black')
    d.rectangle((760,413,795,445),fill='#cccccc');d.text((810,416),'HTTP 429 rate limited',font=small,fill='black')
    im.save(FIG/'load-comparison.png')

def report():
    w=Writer('Web Application Attack Simulation and Layered Security Hardening')
    w.p('WAF Rate Limiting and Defensive Controls','Subtitle')
    w.p('Final technical report  |  Evidence captured 15 October 2026')
    w.p('Project repository: https://github.com/Sidkm18/CFLIA  |  Private')
    w.h('Purpose and result')
    w.p('We tested eight weaknesses in LegacyDesk, an employee service portal, and implemented a separate hardened version under v2. All eight baseline weaknesses were observed. The final hardened stack passed 19 direct application tests and 17 integration checks. A repeated local load batch changed from 40 accepted requests to 5 accepted requests and 35 rate-limit responses.')
    w.p('This report explains the causes, fixes, reproduction steps and recorded results. It distinguishes real browser captures from labelled HTTP evidence views and includes the supporting raw data. The website itself retains a normal employee-portal interface.')
    w.h('Submission details')
    w.p('College or institute: ______________________________\nSubject and course: ______________________________\nGuide or faculty: ______________________________\nTeam members and roll numbers: ______________________________')
    w.h('Reading order')
    w.p('The next pages describe scope, architecture, tools and measured results. Each of the eight case studies then has a baseline page and a hardening page. Browser evidence, verification limits, operations and references follow. A separate team pack provides the seven-minute speaking script and rehearsal plan.')
    w.page('Objectives and scope')
    for t in ['Design and deploy an intentionally vulnerable application in an isolated local environment.', 'Demonstrate injection, XSS, authorization, session, CSRF, traversal, configuration and resource-consumption weaknesses.', 'Identify the root cause of each weakness and implement application and infrastructure controls.', 'Repeat the attack scenarios and compare status codes, visible behavior, latency and logs.', 'Preserve ordinary employee workflows while showing how preventive and detective controls work together.']:
        w.p(t,'List Number')
    w.h('Environment and boundaries')
    w.p('The measured environment is macOS with Docker Desktop, Python scripts, Nmap, OWASP ZAP, Wireshark tshark and Chromium browser automation. Kali Linux and Burp Suite were in the initial proposed tool list but are not claimed as tools used in these captures. ZAP provided the actual proxy request history.')
    w.p('All target traffic used the self-hosted local stacks or their isolated Docker service names. No third-party target was scanned. The download exposure reaches only a seeded private fixture; the XSS proof changes one local page element. The load workload is capped at 40 requests and four workers.')
    w.h('Interpretation of the legacy website')
    w.p('V1 already uses Nginx as a reverse proxy. Its weaknesses are in intentionally unsafe application behavior and missing defensive controls. The project does not demonstrate an exploit against an old Nginx CVE, nor does an Nginx version banner establish exploitability. The original 51 tracked files remain byte-for-byte unchanged by SHA-256 comparison.')
    w.h('OWASP mapping')
    w.p('The case labels use OWASP Top 10 2025 terminology where applicable. Eight tested vulnerabilities do not represent eight different Top 10 categories. Resource consumption is explicitly mapped to OWASP API Security API4 2023. These categories guide analysis; OWASP does not automatically patch an application. [1] [8]')
    w.page('System architecture and defensive layers')
    w.image(FIG/'architecture.png','Figure 1  Deployed architecture derived from v2 Compose and gateway configuration',2.5)
    w.table(['Layer','Implemented behavior'],[
        ['Network','Separate Compose projects and database volumes; backend and WAF ports unpublished'],
        ['Gateway','TLS 1.2 or 1.3; HTTP redirect; request and connection limits; body and timeout bounds'],
        ['WAF','ModSecurity 3.0.17 with CRS 4.30.0 in blocking mode at paranoia level 1'],
        ['Application','Bound SQL; output encoding; ownership checks; session and CSRF controls; fixed download allowlist'],
        ['Resources','Per-user quotas; cached report; anonymous session cap and garbage collection; container and worker limits'],
        ['Detection','Correlated gateway, WAF and application events; no stored live tokens in submitted evidence']],[1.25,5.75])
    w.p('Preventive controls reject known attacks and enforce application policy. Detective controls record rule matches and access denials. The response demonstrated here is automatic rejection with 401, 403, 404 or 429 as appropriate; no SOC alerting or automated incident-response system is claimed.')
    w.page('Test method and evidence provenance')
    w.p('We followed attack, observation, hardening and retest. Baseline capture began at 06:54:46 UTC. The final full-stack retest began at 07:06:30 UTC after the additional session and cache-control changes. Each request series identifies its target and version.')
    w.table(['Evidence','Location in the repository'],[
        ['Baseline responses','output/evidence/baseline-20261015T065446247953Z/'],
        ['Final full-stack checks','v2/output/verification-20261015T070630Z/'],
        ['Redacted v2 response bodies','submission/evidence/v2-http-responses.json'],
        ['Direct application tests','v2/output/origin-tests.txt'],
        ['Browser and HTTP screenshots','output/playwright/final/ and v2/output/playwright/'],
        ['Proxy and packet data','submission/evidence/zap-proxy-history.json and local-http.pcapng'],
        ['Dependency audit','submission/evidence/dependency-audit.json']],[1.65,5.35])
    w.p('Screenshots labelled recorded HTTP evidence are browser renders of real captured request and response fields. They are evidence viewers, not screenshots of a portal feature. Real portal screenshots are identified separately. V2 passwords, CSRF tokens and session values are redacted or excluded. The packet capture contains only port 8080 traffic and the intentionally weak seeded v1 values.')
    w.p('Application-only tests use temporary databases and bypass the WAF, showing that root-cause fixes do not depend solely on request signatures. Deployed checks traverse TLS, Nginx, ModSecurity and Flask. Positive tests cover sign-in, authorized ticket access, comments, handbook downloads and logout.')
    w.page('Enumeration and request interception')
    w.image(CAP/'recon-nmap.png','Figure 2  Nmap output from a bounded scan of four localhost ports',3.0)
    w.image(CAP/'zap-interception.png','Figure 3  Actual ZAP proxy history showing ticket ID modification with Alice identity',3.7)
    w.p('ZAP ran temporarily in a separate container. Only two selected local requests were proxied, with no active scan or spider. Both returned HTTP 200 in v1; the modified request disclosed Bob payroll details. The container was stopped after exporting its request history.')
    w.page('Network capture evidence')
    w.image(CAP/'wireshark-packets.png','Figure 3 A  Wireshark tshark extraction from the recorded loopback capture',5.7)
    w.p('The six-second capture recorded 132 packets on loopback with a capture filter for TCP port 8080. The displayed fields are frame number, relative time, source address, source port, HTTP method, request URI and response code. The PCAPNG file is included for inspection in Wireshark.')
    w.p('The capture observes the original HTTP service only. It does not decrypt v2 TLS, quantify distributed traffic, or establish peak resource utilization. The original project uses deliberately weak seeded account values; no generated v2 credential is present in this port-filtered capture.')
    w.page('Measured comparison')
    w.image(FIG/'load-comparison.png','Figure 4  Accepted and rejected responses for the same bounded request schedule',2.7)
    w.table(['Measure','Vulnerable v1','Hardened v2'],[
        ['Requests and workers','40 and 4','40 and 4'],['HTTP 200','40','5'],['HTTP 429','0','35'],
        ['Elapsed seconds',str(B['elapsed_seconds']),str(H['elapsed_seconds'])],
        ['Median latency ms',str(B['median_latency_ms']),str(H['median_latency_ms'])],
        ['p95 latency ms',str(B['p95_latency_ms']),str(H['p95_latency_ms'])]],[3,2,2])
    w.p('V2 rejects excess work early and caches allowed reports. Its measurements include TLS and rejected requests, so lower latency does not mean equivalent successful work ran faster. These are individual local captures, not statistically repeated capacity estimates. Container limits are configured, but the included idle resource snapshot does not establish CPU or memory peaks during a flood.')
    w.p('All eight baseline findings were observed. All 19 direct application tests and 17 final deployed-stack checks passed. WAF evidence includes SQLi rule 942100, XSS rules 941100, 941120 and 941160, path rules 930110 and 930120, and anomaly evaluation rule 949110. Exact results are retained in JSON.')
    for case in CASES:
        ident=case['id'];w.page(ident+' '+case['name']+' before hardening')
        w.p('OWASP mapping: '+case['mapping'])
        w.h('Cause and effect');w.p(case['cause']+' '+case['impact'])
        w.h('Reproduction');w.p(case['steps']);w.code(case['payload'])
        w.image(CAP/(ident+'-before-http.png'),f'Figure {ident} A  Recorded baseline HTTP evidence'+(' excerpt through the first account' if ident=='V07' else ''),4.25)
        w.p(case['before'])
        w.page(ident+' '+case['name']+' after hardening')
        w.h('Implemented fix');w.p(case['fix']+' '+case['ref'])
        w.code(case['code'])
        w.image(CAP/(ident+'-after-http.png'),f'Figure {ident} B  Recorded response through the deployed hardened gateway',4.25)
        w.p(case['after'])
        w.h('Legitimate use');w.p(case['positive'])
    for title,images in [
        ('Browser evidence for injection and scripting',[(CAP/'V01-before-admin.png','Figure 5  V1 administrator identity after injected login'),(CAP/'V02-before-browser.png','Figure 6  V1 stored payload executed inside the ticket conversation')]),
        ('Browser evidence for encoding and authorization',[(ROOT/'v2/output/playwright/v2-xss-encoded.png','Figure 7  V2 direct-origin payload displayed as encoded text'),(CAP/'V03-before-browser.png','Figure 8  V1 Alice session reading Bob ticket')]),
        ('Browser evidence for forged requests',[(CAP/'V05-before-form.png','Figure 9  Separate-origin contact form before submission'),(CAP/'V05-before-account.png','Figure 10  V1 account after browser form submission')]),
        ('Browser evidence for session forgery',[(CAP/'V04-before-denied.png','Figure 10 A  V1 administrator access denied to Alice'),(CAP/'V04-before-forged.png','Figure 10 B  V1 administrator access after changing the identity cookie')]),
        ('Browser evidence for file and diagnostic exposure',[(CAP/'V06-before-browser.png','Figure 10 C  Private configuration fixture returned by v1 traversal'),(CAP/'V07-before-browser.png','Figure 10 D  Public v1 debug response with seeded accounts')]),
        ('Browser evidence for normal workflows',[(ROOT/'v2/output/playwright/v2-ticket-created.png','Figure 11  Legitimate v2 ticket creation'),(ROOT/'v2/output/playwright/v2-mobile-ticket.png','Figure 12  V2 employee workflow at mobile width')])]:
        w.page(title)
        for image,caption in images:w.image(image,caption,3.8)
    w.page('Verification limits and maintenance')
    w.h('What the results establish')
    w.p('The captured payloads succeed in v1 and are denied or rendered inert in v2. Origin tests demonstrate ownership checks, bound queries, encoding, session and CSRF enforcement independently of the WAF. Valid portal workflows remain available. Anonymous session cleanup and the cap now prevent indefinite accumulation when clients discard pre-login cookies.')
    w.h('What remains outside the measured scope')
    w.p('This is not an exhaustive penetration test or a claim that the application has no vulnerabilities. The bounded load probe does not establish distributed denial-of-service resistance, network saturation capacity, or behavior under many independent clients. WAF tuning, sustained performance tests, production identity services, alert delivery and backup recovery require separate evaluation.')
    w.p('The dependency audit found no known advisories for the eight pinned Python packages at capture time. It does not cover every operating-system package or future advisory. Some container tags remain mutable; keep the captured runtime versions and review updates before reuse. Local certificates are appropriate to this localhost setup and require renewal; a public deployment needs a managed certificate and deployment-specific host/origin configuration.')
    w.h('Repeat the verification')
    w.code('docker compose -f v2/compose.yaml exec -T app \\\n  python -m unittest discover -s tests -v\npython3 v2/scripts/verify_stack.py')
    w.p('Wait at least 60 seconds between integration batches so persisted quotas can reset. The integration script adds a clearly named ordinary proof comment. Remove only proof records created for the recording; never reset a database containing records you want to preserve. The vulnerable original remains available separately for the before sequence.')
    w.h('Operational follow through')
    w.p('Review dependency and image updates, renew TLS material, protect the private state directory, rotate credentials when sharing the environment, inspect denied requests, and add alert routing before any real service deployment. Keep generated credentials, TLS private keys and live browser session state out of Git and recordings.')
    w.page('References and submitted files')
    refs=[
        ('[1] OWASP Top 10 2025','https://top10.owasp.org/'),
        ('[2] SQL Injection Prevention Cheat Sheet','https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html'),
        ('[3] Cross Site Scripting Prevention Cheat Sheet','https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html'),
        ('[4] Insecure Direct Object Reference Prevention','https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html'),
        ('[5] Session Management Cheat Sheet','https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html'),
        ('[6] Cross Site Request Forgery Prevention','https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html'),
        ('[7] Nginx request limiting module','https://nginx.org/en/docs/http/ngx_http_limit_req_module.html'),
        ('[8] OWASP API4 2023 Resource Consumption','https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/'),
        ('[9] OWASP Core Rule Set documentation','https://coreruleset.org/docs/'),
        ('[10] ZAP Docker documentation','https://www.zaproxy.org/docs/docker/')]
    for title,url in refs:w.p(title+'\n'+url)
    w.p('References checked 15 October 2026. Implementation claims and measurements come from the repository and captured local evidence; the references supply the security concepts and control guidance.')
    w.h('Deliverables')
    w.p('Editable report and PDF: output/documents and output/pdf. Four-person speaking and rehearsal pack: the matching Team Script documents. Screenshot and silent walkthrough pack: output/playwright/final. Raw captures and comparison data: submission/evidence. Hardened source and verification commands: v2.')
    w.save('CFLIA_Final_Report','FINAL_REPORT.md')

def team():
    w=Writer('Four Person Presentation Script and Rehearsal Guide')
    w.p('LegacyDesk attack demonstration hardening and retesting','Subtitle')
    w.p('Target running time 7 minutes  |  Four members  |  Two vulnerabilities per member')
    w.p('Each speaker owns the full before, fix and after sequence for their two vulnerabilities. Speak only the narration below; the action cues are for the screen operator. Use Member 1 to Member 4 until the team adds its names.')
    w.table(['Speaker','Time window','Two vulnerabilities'],[[s['name'],s['time'],s['cases']] for s in SPEAKERS],[1,1.7,4.3])
    w.h('How to show the fix')
    w.p('Prepare v1 and v2 tabs and the relevant code before recording. Show the v1 behavior, point to the implemented v2 change, then repeat the request on v2. The separate hardened version is already built; do not imply that a complete WAF, session system and proxy deployment was typed live in a few seconds. A brief code close-up makes the fix visible and reviewable.')
    w.p('Use the same payload and identity where applicable. V2 uses a fresh authenticated session and correct CSRF token when testing SQLi or XSS, so a CSRF failure cannot be mistaken for a WAF block. Never display the generated password file or live session tokens.')
    count=sum(len(re.findall(r"\b[\w'-]+\b",speech)) for s in SPEAKERS for _,speech in s['speech'])
    w.p(f'The narration contains approximately {count} spoken words. The time windows are a recording target, not a measured finished take. Rehearse the words and screen transitions together, leaving short holds so viewers can read the evidence.')
    for s in SPEAKERS:
        w.page(s['name']+' speaking script')
        w.p(s['time']+'  |  '+s['cases'])
        for timestamp,speech in s['speech']:w.h(timestamp.replace(':',' ').replace('to','to'));w.p(speech)
        w.h('Screen actions')
        for action in s['actions']:w.p(action)
        w.p('Fix locations: '+s['fixfiles'])
    w.page('Exact payloads and retest cues')
    for index,c in enumerate(CASES):
        if index==4:w.page('Request payloads V05 to V08')
        w.h(c['id']+' '+c['name']);w.code(c['payload'])
        w.p('After cue: '+({'V01':'403 WAF block; origin test rejects login','V02':'403 WAF block; encoded origin output','V03':'403 as Alice','V04':'401 forged identity; 403 valid Alice','V05':'403 and unchanged email','V06':'403 at WAF; 404 at direct origin','V07':'404 and secure response headers','V08':'40 requests and 4 workers; captured 5 HTTP 200 and 35 HTTP 429'}[c['id']]))
    w.page('Recording preparation')
    for text in ['Start and check both stacks. V1 is http://127.0.0.1:8080; v2 is https://127.0.0.1:8443. The contact form is http://127.0.0.1:8091/csrf.html. Use a local certificate exception only in the dedicated recording browser, or trust the provided local CA in that browser.', 'Use separate browser contexts for v1 administrator proof, v1 Alice, and v2 Alice. Cookies share a host across ports, so verify the identity visible in each portal header before each take.', 'Use alice / alice123 only for the intentionally vulnerable original. Read v2 credentials privately from v2/state/credentials.json. Do not show that file, .env, private keys, or real cookie values in the video.', 'Prepare the relevant v2 functions and gateway configuration in an editor with a readable font. Keep each code close-up to the actual fix, then return to the result.', 'Wait at least 60 seconds before a full quota retest. Record the status counts actually produced; a different warm quota can change the number accepted. Do not replace a live result with an invented 5/35 display.', 'Restore the known proof email and remove only your own XSS or verification comments after the final take. Preserve unrelated records and the original website source.']:
        w.p(text,'List Bullet')
    w.h('Evidence and commands ready to use')
    w.code('python3 scripts/probe_baseline.py\npython3 v2/scripts/verify_stack.py\ndocker compose -f v2/compose.yaml exec -T app \\\n  python -m unittest discover -s tests -v')
    w.p('The baseline command adds one harmless XSS comment and updates Alice email. The v2 integration command adds one ordinary verification comment. Use these commands for the full controlled run; for individual video scenes use the browser actions and exact payloads. Saved screenshots and the silent HTTP walkthrough are available if a live transition needs an edit.')
    w.page('Rehearsal and final recording checklist')
    for t in ['Rehearsal one: each member performs both cases without narration. Confirm identity, payload, before outcome, fix location, after denial, and one legitimate positive control.', 'Rehearsal two: read the exact spoken script with a stopwatch. Keep the four handoffs at 01:45, 03:30, 05:15 and 07:00. Shorten pauses before cutting technical explanations.', 'Rehearsal three: record one uninterrupted take. Check that payload text, HTTP status and the fix are readable, and that each speaker covers exactly two vulnerabilities.', 'Record at 1080p with consistent browser zoom and microphone level. Use short silent holds on results. Hide notifications, unrelated tabs and private credentials. Put labels such as Before and After in the video overlay if useful; keep the portal itself looking normal.', 'If a result differs: stop the take, check the active identity and quota window, repeat the real test, and narrate the verified result. Do not claim a patched defect solely because a WAF returned 403; show the application fix and its origin test.', 'Export a video no longer than seven minutes. Watch the exported file from beginning to end, including audio, handoffs, visible evidence and final test counts. The supplied silent walkthrough is source footage, not the completed narrated team video.']:
        w.p(t,'List Bullet')
    w.h('What to submit')
    w.p('Submit the final report PDF, editable report if requested, final team recording, and private repository access as required by the faculty. Keep the team script for preparation. Replace the blank college and member details before academic submission; no personal details have been invented.')
    w.save('CFLIA_Team_Script','TEAM_SCRIPT.md')
    (ROOT/'submission/speaking_plan.json').write_text(json.dumps({'target_seconds':420,'spoken_word_count':count,'speakers':SPEAKERS},indent=2)+'\n')

if __name__=='__main__':
    figures(); report();team()
    print('Created final report and four-person script DOCX with Markdown sources.')
