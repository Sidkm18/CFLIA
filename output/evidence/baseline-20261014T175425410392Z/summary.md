# Vulnerable baseline evidence

Captured: 2026-10-14T17:54:25.410392+00:00
Target: http://127.0.0.1:8080

| Finding | Failure observed | Evidence |
|---|---|---|
| V01 SQL injection | Yes | Injected sign-in selects the admin account without its password. |
| V02 Stored XSS | Yes | Harmless SVG payload stored and returned as raw markup. Browser execution requires separate visual verification. |
| V03 Broken access control (IDOR) | Yes | Alice can read Bob's confidential fictional ticket by changing its ID. |
| V04 Weak authentication / forged session | Yes | Alice is denied; an unsigned identity cookie grants administrator access without credentials. |
| V05 CSRF | Yes | Cross-origin POST with the session cookie updates email without a token. Browser cookie behaviour must be verified separately. |
| V06 Path traversal | Yes | Download escapes its public directory into a private dummy fixture. |
| V07 Security misconfiguration | Yes | Public debug leaks fictional plaintext passwords; missing headers: content-security-policy, x-content-type-options, x-frame-options |
| V08 Unrestricted expensive requests | Yes | All 40 expensive authenticated requests accepted using four workers; no rate-limit response. |

## Bounded load probe

```json
{
  "requests": 40,
  "concurrency": 4,
  "elapsed_seconds": 2.115,
  "throughput_rps": 18.92,
  "status_counts": {
    "200": 40
  },
  "median_latency_ms": 211.06,
  "p95_latency_ms": 216.76,
  "limitation": "Bounded local probe demonstrates missing admission controls; does not establish DoS, DDoS resistance or system resource consumption."
}
```

These are baseline measurements, not post-hardening results. Stored XSS execution and browser CSRF are verified separately in screenshots/browser notes. Resource metrics have not been collected by this script.
