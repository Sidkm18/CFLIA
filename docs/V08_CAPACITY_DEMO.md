# V08: local browser outage, recovery and rate limiting

This is the start/stop demonstration: **V1 works -> report traffic fills its workers -> a normal browser page receives HTTP 503 -> stop traffic -> V1 works again.** V2 handles the same bounded client traffic with its existing report controls while normal browsing remains available.

The lab runs in a separate Docker Compose project, with separate database volumes and dedicated loopback ports. It does not modify the original V1/V2 applications, their existing stacks or any Render deployment.

## What this experiment changes

- Both demo applications have two worker slots. V1's wrapper adds 3.8 seconds to its existing 0.2-second report job, representing a slow four-second job. Waiting occupies a worker without exhausting the laptop's CPU or memory.
- V1's server sends a real HTTP 503 when both slots are occupied. There is no flag that forces an error, no fake error overlay and no shutdown of the application. The response is based on current worker availability.
- V2 runs the existing hardened application with two Gunicorn threads. It retains the existing report cache, six-per-account-per-minute quota, Nginx endpoint limits and WAF. No artificial job delay is added to its patched report implementation.
- The traffic client uses four workers, fixed localhost targets, at most four request starts per second, a maximum of 360 requests and a default 60-second run. Ctrl+C stops new traffic; in-flight jobs take up to about six seconds to finish.

This is a deliberately constrained capacity model. Describe it as a local availability and admission-control demonstration, not a distributed DDoS attack or proof of production-scale DDoS resistance.

## 1. Start the isolated lab

Open Docker Desktop and wait until Docker is ready. In Terminal:

```sh
cd /Users/sid/Desktop/NewProjects/CFL_IA_2
python3 scripts/v08_capacity_demo.py up
```

The first build may take a few minutes. Wait for **V08 capacity lab ready**.

Use a **new private browser window or separate browser profile** for this lab. Cookies are shared across ports on the same hostname, so this prevents the demo's session cookies from replacing sessions in your original local portals.

| Version | Browser address | Sign-in |
|---|---|---|
| V1 capacity lab | http://127.0.0.1:18080 | alice / alice123 |
| V2 capacity lab | https://127.0.0.1:18443 | alice and the existing local V2 Alice password |

V2's password is in `/Users/sid/Desktop/NewProjects/CFL_IA_2/v2/state/credentials.json`. Retrieve it privately before recording. This is the local password, not the separately generated Render password. Do not include passwords or actual V2 cookie values in the recording.

V2 uses the existing local development CA certificate in `v2/state/tls/ca.crt`. If Chrome or Brave shows a certificate warning, you must handle it manually in your dedicated lab window: confirm the address is `https://127.0.0.1:18443`, then use **Advanced -> Proceed to 127.0.0.1** if that site-specific option is offered. Complete this before recording. The automation does not bypass browser security warnings. Do not disable certificate validation globally. The verifier validates HTTPS against the existing CA file without bypassing verification.

Both pages show a visible **Local V08 capacity lab** banner so they cannot be confused with the Render services or original local stacks.

## 2. Show V1 working

1. Sign in to V1 as Alice.
2. Open **Support tickets**, at `http://127.0.0.1:18080/tickets`.
3. Open DevTools -> Network and enable **Disable cache** while DevTools is open. Clear the request list.
4. Reload once and show the page working. Its document request should return HTTP 200.

Say: "This isolated V1 server has two worker slots. It serves normal users correctly before repeated report jobs arrive."

## 3. Start V1 traffic and show the real error

In Terminal:

```sh
python3 /Users/sid/Desktop/NewProjects/CFL_IA_2/scripts/v08_capacity_demo.py traffic v1
```

1. Wait about two seconds after the traffic counters start.
2. Return to the V1 ticket page and reload.
3. Show **Service temporarily busy** and **HTTP 503**. In Network, select the document request and show its actual 503 status.
4. Keep the Terminal visible briefly. The counters distinguish accepted report jobs (200), rate limits (429), real capacity refusals (503), and transport errors. Do not count connection errors as successful blocking.

Say: "Repeated report jobs occupy V1's shared worker capacity. A normal page is refused because no worker is available. The process is still running; it has not been manually stopped."

If a refresh happens to land in a brief free slot, wait a second and reload once more. The error follows real occupancy, so it is not forced on every request. Keep the recording's successful take and its corresponding Network result.

## 4. Stop traffic and show recovery

1. In the traffic Terminal, press **Ctrl+C once**.
2. Wait for **Traffic stopped. Refresh the browser now.** Existing jobs are allowed to finish, normally within five seconds, with a six-second client timeout.
3. Reload the same V1 ticket URL.
4. Show the normal ticket page and HTTP 200. No server restart is needed.

Say: "Once new report traffic stops and the running jobs finish, capacity becomes available and the same page works again."

The client also stops automatically after 60 seconds if you do not press Ctrl+C. For a shorter take, add `--seconds 30`; permitted durations are 15, 30, 60 and 90 seconds.

## 5. Show V2 staying usable during traffic

1. Sign in to the separate V2 demo at `https://127.0.0.1:18443`.
2. Open `https://127.0.0.1:18443/tickets` and confirm it works.
3. If V2 report traffic or the verifier ran recently, wait **70 seconds with no report requests** for a fresh quota window. You may sign in and browse normal pages during this wait.
4. Clear Network and keep Disable cache enabled.
5. In Terminal, run:

```sh
python3 /Users/sid/Desktop/NewProjects/CFL_IA_2/scripts/v08_capacity_demo.py traffic v2
```

6. Wait about three seconds. Show HTTP **429** counts increasing in Terminal. Some initial reports may return 200, up to six per account in the application quota window; edge rate limits may reject some earlier. A warm quota can yield zero accepted reports.
7. While traffic is still running, refresh the V2 ticket page, open Overview, and return to Support tickets. Show these normal document requests returning **200**.
8. Stop the script with Ctrl+C and wait for its completion message.

Say: "V2 rejects excess report requests before they consume the shared application capacity. Its patched report path also caches results and avoids V1's repeated slow work. Normal ticket browsing continues during this same bounded client traffic."

Optional: in another Terminal, inspect actual local rate-limit evidence:

```sh
docker compose -f /Users/sid/Desktop/NewProjects/CFL_IA_2/demos/v08-capacity/compose.yaml logs --tail 80 gateway app
```

The gateway log includes statuses and limit results; the application logs `rate_limited` with policy `report`. Do not show configuration/environment dumps containing passwords.

**Limits of the claim:** this proves the behavior of these routes under this traffic pattern. It does not classify people as malicious or genuine. Alice's own report button can be limited while her other pages work. Other users' report requests can also encounter the shared IP limit, so do not promise Bob's report bypasses an IP-level limit during traffic. Other traffic patterns could still affect availability.

## 6. Optional automatic verification

Run outside the recording, then wait 70 seconds before a fresh V2 take:

```sh
python3 /Users/sid/Desktop/NewProjects/CFL_IA_2/scripts/v08_capacity_demo.py verify
```

This performs a short bounded traffic run for each version and checks actual before/during/after HTTP statuses, V2 throttling, transport errors and unchanged original source/configuration hashes. It uses normal Alice sign-in, adds no comments, changes no account details and stores no passwords or session values.

Each traffic run and verification saves a redacted JSON evidence file under `output/v08-capacity/<timestamp>/`. Keep evidence from the same run as the recording.

## Recorded rehearsal

On 18 October 2026, all 11 integration checks passed. During the short verification, three V1 normal-page requests returned 503 and all three V2 normal-page requests returned 200. V2's verification traffic produced six accepted reports and fourteen HTTP 429 responses, with no transport errors.

The interactive V1 rehearsal produced eight completed reports and thirty capacity refusals, then stopped cleanly with Ctrl+C. The same browser ticket page showed the busy screen during traffic and the normal page after stopping. A separate 15-second V2 automatic-stop rehearsal produced six HTTP 200 and fifty-four HTTP 429 responses, with no errors. Screenshots and redacted JSON are under `output/v08-capacity/`.

V1 was checked in the actual browser. V2 was checked over HTTPS with the existing CA file; the in-app browser rejected its development CA, so its visual rehearsal requires your manual certificate exception in a lab browser. No certificate protection was disabled by the automation.

## 7. Finish

Stop the traffic first. To remove only this lab's containers and networks:

```sh
python3 /Users/sid/Desktop/NewProjects/CFL_IA_2/scripts/v08_capacity_demo.py down
```

Its dedicated database volumes are retained for another take. Original local stacks and Render services remain separate. Avoid `down -v` if you want to keep the lab accounts and sessions.

Closing line: "Under this controlled local workload, V1 loses normal-page availability until report traffic stops. V2 rejects excess report work with HTTP 429 and keeps the tested normal pages available."
