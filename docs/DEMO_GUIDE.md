# Recording the vulnerable stage

This guide prepares the baseline segment and screenshots. The final seven-minute before/after video cannot be recorded completely until the hardening phase exists.

## Clean setup

Start with a freshly reset database. Open `http://127.0.0.1:8080`. Use Alice normally to show that this is a working service portal: sign in, view your two tickets, create a ticket, leave a normal comment, download the employee handbook and update an email.

For a clean final retest, preserve exact attack payloads, account identity, URL, concurrency and requests. Keep baseline and hardened evidence in different timestamped directories.

## Eight compact demonstrations

1. **SQL injection:** sign out. On the sign-in form, username is `' OR 1=1 -- ` (including the trailing space); password is `wrong`. The header displays Portal Administrator. Capture the form before submission and the resulting admin identity. A lone quote can also trigger the verbose SQL error.
2. **Stored XSS:** sign back in as Alice. Open ticket 1001, post the payload below, then reopen the ticket. The injected comment displays `XSS executed` inside the conversation. It is a harmless local proof; no external requests, stolen cookies or exfiltration are used.
3. **IDOR:** Alice normally sees tickets 1001 and 1003. Change the URL to `/ticket?id=1002`. Capture Alice's identity and Bob's private payroll ticket together.
4. **Weak sessions:** as Alice, `/admin` returns 403. In browser DevTools, Application/Storage → Cookies, change `user_id` from `2` to `1`. Open `/admin`: it succeeds without the admin password. Clear or restore the cookie afterward. The probe also records the denied and forged-session requests.
5. **CSRF:** sign in as Alice using the `127.0.0.1` origin. In another tab, open `http://127.0.0.1:8091/csrf.html`. Click **Confirm contact details** on the contact-preferences form. The portal account page now shows `alice.updated@example.test`. Capture both tabs/origins and the result. Ports distinguish origins, while the shared host is the same site; this deliberately demonstrates a same-site cross-origin CSRF. No claim of a cross-site cookie bypass is made.
6. **Traversal:** open `/download?file=../private/legacy-config.txt`. The returned text contains dummy `DB_PASSWORD`. Compare it with the legitimate handbook download. Absolute paths and escapes outside `app/fixtures` are blocked by the lab boundary.
7. **Misconfiguration:** open `/debug` without logging in, then inspect the response headers. Capture exposed fictional passwords and missing CSP/frame/nosniff headers. Do not infer a particular old Nginx version or CVE.
8. **Resource control:** run `python3 scripts/probe_baseline.py`. Capture measured output and `results.json`. All 40 expensive requests are accepted with no 429. This proves missing rate/admission control under these conditions; it does not prove a service outage. Capture `docker stats` during the run for resource evidence, labelled as a point-in-time observation.

Harmless XSS proof (copy exactly):

```html
<svg onload="this.outerHTML='<p>XSS executed</p>'"></svg>
```

## Screenshot checklist

| Evidence | What the image must visibly establish |
|---|---|
| B00 | Normal signed-in dashboard |
| B01 | SQLi form payload and administrator identity after submission |
| B02 | Stored comment payload and browser `XSS executed` result |
| B03 | Alice's identity, ticket 1002 URL, Bob's private ticket |
| B04 | Original 403 and forged-cookie admin success |
| B05 | Separate-origin CSRF form and modified account email |
| B06 | Traversal URL and private dummy fixture text |
| B07 | Anonymous debug leak and actual response headers |
| B08 | Bounded load results and resource/log observations |

Keep raw request/response captures alongside screenshots. A screenshot of a lab finding card describes the issue; it is not proof that the attack worked.

## Proposed final seven-minute timing

| Time | Segment |
|---|---|
| 0:00–0:30 | Problem, controlled scope and architecture |
| 0:30–2:50 | Eight baseline failures, roughly 17 seconds each |
| 2:50–4:00 | Application fixes and gateway/WAF layers |
| 4:00–6:20 | Repeat eight requests; show prevention and legitimate usage |
| 6:20–7:00 | Before/after metrics, WAF audit evidence and limitations |

Use edited cuts and pre-positioned tabs rather than reading long logs live. Include full payloads, steps and screenshots in the report even when the video shows only the decisive result.

## Portal presentation

The portal uses ordinary employee-facing copy. The security guide lives in these documents rather than in the website navigation. XSS proof is shown only after injecting the self-contained payload above; clean tickets have no permanent proof label. Earlier evidence screenshots preserve the original presentation.
