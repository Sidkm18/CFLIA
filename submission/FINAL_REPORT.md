# Web Application Attack Simulation and Layered Security Hardening

WAF Rate Limiting and Defensive Controls

## Project overview

We created a vulnerable web application to understand how common attacks affect a website and the people who use it. We then built a separate hardened version and added security controls to address the problems we found. By repeating the same attacks, we could see how the changes protected information and improved the way the website handled suspicious requests.

The project follows a simple process: find a weakness, observe what happens, apply a fix and try the same request again. It shows how application changes, a Web Application Firewall and traffic controls work together to improve security.

## Team members

| Team member | Roll number |
|---|---|
| Siddharth Kamat | 1601-01-242126 |
|  |  |
|  |  |
|  |  |

---

# About the website

LegacyDesk is an employee service portal. Employees can sign in, raise support tickets, follow conversations, update their contact details and download useful resources. An administrator can access the administration page to view basic portal information.

The website was designed to look and behave like a normal service portal. Its original version contained weaknesses in login, ticket access, comments, account changes, downloads and request handling. These features gave us practical ways to observe how an application can fail when it trusts requests without enough checking.

We kept the original website available and created a separate hardened version. This allowed us to compare the same features before and after adding protection.

## Objectives

Create a vulnerable website that demonstrates common web security problems.

Understand how attacks can expose private information, change account details or cause unnecessary server work.

Fix the weaknesses in the application and add protective layers around it.

Repeat the same attacks and confirm that ordinary employee features still work.

---

# System architecture and defensive layers

Requests pass through the protective layers before reaching application data.

![Requests pass through the protective layers before reaching application data.](evidence/figures/architecture-simple-print.png)

The hardened website receives requests through an Nginx reverse proxy. The proxy handles the secure connection and controls repeated traffic. The WAF checks requests for common attack patterns before passing them to the application. The application then checks the user, validates the input and decides whether the requested action is allowed.

| Layer | What we added |
|---|---|
| Secure connection | HTTPS protects the connection between the browser and the website. |
| Reverse proxy | Request and connection controls reduce unnecessary traffic reaching the application. |
| Web Application Firewall | Suspicious requests are checked and common attack patterns are blocked. |
| Application | Safer database queries, output encoding, permission checks and stronger sessions protect website features. |
| Request handling | User-based controls and report caching reduce repeated work. |
| Logging | Security events help us understand which requests were accepted or rejected. |

The layers support each other. We fixed the application itself and also added controls at the proxy, WAF and browser level.

---

# What we found

## SQL injection

We entered a database condition into the sign-in form instead of a normal username. The website treated it as part of its database query and let us enter an administrator account without the correct password. This showed that the login form was trusting user input too much.

The sign-in request selected the administrator account.

![The sign-in request selected the administrator account.](evidence/figures/V01-before-http-print.png)

The website opened the administrator workspace.

![The website opened the administrator workspace.](evidence/figures/V01-before-admin-print.png)

---

# Stored cross site scripting

We posted a comment containing browser code and opened the ticket again. The website ran the code as part of the page. The comment changed its own content, showing that a saved message could affect what another user sees.

The saved comment was returned as page code.

![The saved comment was returned as page code.](evidence/figures/V02-before-http-print.png)

The browser ran the comment code inside the conversation.

![The browser ran the comment code inside the conversation.](evidence/figures/V02-before-browser-print.png)

---

# Access to other employee tickets

We signed in as an employee and changed the ticket identifier in a request. The website opened a ticket belonging to someone else and displayed private payroll information. It checked that we were signed in, but did not check whether we were allowed to see that ticket.

Changing the requested ticket exposed private employee information.

![Changing the requested ticket exposed private employee information.](evidence/figures/V03-before-http-print.png)

The signed-in employee could read a ticket owned by someone else.

![The signed-in employee could read a ticket owned by someone else.](evidence/figures/V03-before-browser-print.png)

---

# Weak authentication and sessions

We changed the identity value stored in the browser cookie. The website trusted the changed value and gave us administrator access. We also found that the original account passwords were stored in a readable form. A person who could copy those records would not need to guess the passwords.

The changed cookie was accepted as an administrator identity.

![The changed cookie was accepted as an administrator identity.](evidence/figures/V04-before-http-print.png)

The administrator page opened after the identity cookie was changed.

![The administrator page opened after the identity cookie was changed.](evidence/figures/V04-before-forged-print.png)

---

# Cross site request forgery

While an employee was signed in, we submitted a contact form from a separate page. It changed the employee email address without using the account form inside the portal. The website accepted the browser session without checking where the change came from.

The outside request changed the account email.

![The outside request changed the account email.](evidence/figures/V05-before-http-print.png)

The account showed the changed email after the request.

![The account showed the changed email after the request.](evidence/figures/V05-before-account-print.png)

---

# Path traversal in file downloads

We changed the filename in a download request so that it pointed outside the public downloads folder. The website returned an internal configuration file instead of the employee handbook. This showed that the download feature could expose files that were meant to stay private.

The download request reached a private configuration file.

![The download request reached a private configuration file.](evidence/figures/V06-before-http-print.png)

The internal file contents appeared in the browser.

![The internal file contents appeared in the browser.](evidence/figures/V06-before-browser-print.png)

---

# Exposed internal information

We opened a diagnostic page without signing in. It revealed account details, readable passwords and information about how the application worked. We also found that the website was missing browser security headers and showed more error information than a visitor needed.

The public diagnostic page exposed account information.

![The public diagnostic page exposed account information.](evidence/figures/V07-before-http-print.png)

Internal account records were visible without signing in.

![Internal account records were visible without signing in.](evidence/figures/V07-before-browser-print.png)

---

# Unrestricted resource consumption

This vulnerability is unrestricted resource consumption, which can cause denial of service (DoS). Repeated report requests consume capacity needed by normal visitors. Our earlier bounded check showed V1 accepting all 40 requests. In a separate local demonstration, we used two workers and four-second report jobs: V1 returned HTTP 503 during traffic and recovered after the script stopped. The traffic came from one source, so this was a local DoS demonstration rather than a distributed denial-of-service (DDoS) test.

Earlier bounded check: V1 accepted all 40 report requests.

![Earlier bounded check: V1 accepted all 40 report requests.](evidence/figures/V08-before-http-print.png)

---

# How we fixed the vulnerabilities

## SQL injection

We changed the login so that the database treats a username as text rather than an instruction. The password is checked separately, and unexpected input is rejected. We also added a Web Application Firewall to filter suspicious requests. When we repeated the attack, it no longer gave us administrator access.

The repeated request was handled by the hardened website.

![The repeated request was handled by the hardened website.](evidence/figures/V01-after-http-print.png)

---

# Fixing stored cross site scripting

We changed how comments are displayed so that user content appears as text and cannot become part of the page code. We also added browser security rules and WAF filtering. The repeated request was blocked, and a separate application check showed that the same comment stayed as harmless text.

The repeated request was handled by the hardened website.

![The repeated request was handled by the hardened website.](evidence/figures/V02-after-http-print.png)

The application displays the comment as text.

![The application displays the comment as text.](evidence/figures/v2-xss-encoded-print.png)

---

# Fixing access to other employee tickets

We added an ownership check whenever a ticket is opened or a comment is posted. Employees can work with their own tickets, while administrators keep their intended access. When we repeated the request using the same employee account, the private ticket was denied and the employee could still open their own ticket.

The repeated request was handled by the hardened website.

![The repeated request was handled by the hardened website.](evidence/figures/V03-after-http-print.png)

The hardened website denies access to another employee ticket.

![The hardened website denies access to another employee ticket.](evidence/figures/v2-idor-denied-print.png)

---

# Fixing weak authentication and sessions

We replaced the trusted identity cookie with a random session that the server checks. Sessions are replaced at sign-in, expire when no longer valid, and stop working after sign-out. Passwords are now stored as hashes instead of readable text. Changing the old cookie no longer creates an administrator session, and an employee account still cannot open administration.

The repeated request was handled by the hardened website.

![The repeated request was handled by the hardened website.](evidence/figures/V04-after-http-print.png)

---

# Fixing cross site request forgery

We added a security token to forms that change account or website data. The server checks that the token belongs to the current session and that the request comes from the portal. We also strengthened cookie handling. Repeating the outside request was rejected, and the account email stayed unchanged.

The repeated request was handled by the hardened website.

![The repeated request was handled by the hardened website.](evidence/figures/V05-after-http-print.png)

---

# Fixing path traversal in file downloads

We changed the download feature to accept only approved filenames, each linked to a fixed file chosen by the application. Users must also be signed in before downloading. The WAF adds another check for suspicious file requests. The private-file request was denied, while the employee handbook still downloaded normally.

The repeated request was handled by the hardened website.

![The repeated request was handled by the hardened website.](evidence/figures/V06-after-http-print.png)

---

# Fixing exposed internal information

We removed the public diagnostic page and replaced detailed public errors with simple messages. We added secure response headers and HTTPS to protect how the browser loads and handles the website. The diagnostic request now returns a missing-page response without exposing account information.

The repeated request was handled by the hardened website.

![The repeated request was handled by the hardened website.](evidence/figures/V07-after-http-print.png)

---

# Fixing unrestricted resource consumption

We added request and connection limits at Nginx, a quota of six report requests per account per minute, and a 30-second report cache. Excess requests receive HTTP 429 instead of triggering more report work. In the separate local capacity demonstration, V2 rejected repeated report requests while normal ticket pages continued to return HTTP 200. These controls preserve availability for the tested workload; they do not identify genuine users automatically or prove resistance to every DoS attack.

Earlier bounded check: V2 accepted 5 reports and limited 35 with HTTP 429.

![Earlier bounded check: V2 accepted 5 reports and limited 35 with HTTP 429.](evidence/figures/V08-after-http-print.png)

---

# Normal website use after the changes

After adding the security controls, we checked the features an employee would use every day. Signing in, creating a ticket, adding a normal comment and downloading the handbook continued to work. The website also remained usable on a smaller screen.

An employee creates a support ticket on the hardened website.

![An employee creates a support ticket on the hardened website.](evidence/figures/v2-ticket-created-print.png)

The ticket remains usable on a smaller screen.

![The ticket remains usable on a smaller screen.](evidence/figures/v2-mobile-ticket-print.png)

The comparison showed that the same service portal could keep its normal features while rejecting the harmful requests we had demonstrated.

---

# V08 local availability demonstration

These browser captures show the separate local capacity lab on 18 October 2026. It uses two shared workers and four-second V1 report jobs to make request contention visible.

![V1 before traffic: the ticket page loads normally in the local capacity lab.](../output/v08-capacity/screenshots/v1-before.jpg)

V1 before traffic: the ticket page loads normally in the local capacity lab.

![V1 during report traffic: both workers are occupied and the browser receives HTTP 503.](../output/v08-capacity/screenshots/v1-during-traffic.jpg)

V1 during report traffic: both workers are occupied and the browser receives HTTP 503.


---

# V08 recovery after stopping traffic

After stopping the traffic script with Ctrl+C and allowing running jobs to finish, the same browser ticket page became available again without restarting the server.

![V1 after traffic stops: the ticket page is available again in the same browser tab.](../output/v08-capacity/screenshots/v1-after-stop.jpg)

V1 after traffic stops: the ticket page is available again in the same browser tab.

V2 was checked separately over HTTPS with the local CA certificate. During the short verification, excess report requests returned HTTP 429 while the tested normal pages returned HTTP 200. Its report quota and cache reduced repeated work.

The screenshot above records V1 recovery. V2 availability is supported by the recorded HTTPS checks; no V2 browser capture from this capacity test is presented here. This deliberately constrained local test does not establish resistance to distributed denial-of-service attacks.


---

# V05 hosted external form

The CSRF demonstration uses a separate Render-hosted website. Each button submits one account-update request to the selected portal without a CSRF token. The page does not collect portal passwords or session cookies.

![The hosted external form used for the V1 and V2 account-update comparison on 18 October 2026.](../output/render-deployment/csrf-site-live.jpg)

The hosted external form used for the V1 and V2 account-update comparison on 18 October 2026.


---

# V05 hosted account state comparison

After submitting the external form, we refreshed the original authenticated account tabs. V1 showed the submitted email; V2 retained its previous email.

![V1 accepted the external update and saved csrf.hosted.v1@example.test.](../output/render-deployment/csrf-v1-account-after.jpg)

V1 accepted the external update and saved csrf.hosted.v1@example.test.

![V2 retained alice.updated@example.test after the external request was rejected.](../output/render-deployment/csrf-v2-account-after.jpg)

V2 retained alice.updated@example.test after the external request was rejected.


---

# V05 rejected request and legitimate update

The external V2 submission was rejected. A later update made through the portal's own account form succeeded. These captures show the combined browser-cookie and server-side CSRF protections.

![V2 response to the external form: Access unavailable.](../output/render-deployment/csrf-v2-rejected.jpg)

V2 response to the external form: Access unavailable.

![Captured confirmation area of a legitimate V2 account update: Account details updated.](../output/render-deployment/csrf-v2-normal-update.jpg)

Captured confirmation area of a legitimate V2 account update: Account details updated.


---

# V03 hosted ticket ownership comparison

These Render captures from 17 October 2026 compare the same ticket request using Alice's account. All employee and payroll records shown are fictional lab data.

![V1 exposed Bob's ticket 1002 while the signed-in identity remained Alice.](../output/render-deployment/v1-idor-visible.jpg)

V1 exposed Bob's ticket 1002 while the signed-in identity remained Alice.

![V2 denied the same cross-account ticket request while Alice remained signed in.](../output/render-deployment/v2-idor-denied.jpg)

V2 denied the same cross-account ticket request while Alice remained signed in.
