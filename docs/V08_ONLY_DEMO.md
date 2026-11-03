# V08-only recording commands

For the new **start traffic -> normal browser fails -> stop -> recovery** scene,
use [the separate capacity lab](V08_CAPACITY_DEMO.md) and
`scripts/v08_capacity_demo.py`. The older script below remains a short,
40-request quota comparison and does not cause a deliberate browser outage.

Use Terminal with Docker Desktop and both existing local Compose stacks running.
The dedicated script signs Alice in normally, then requests only the report
endpoint 40 times using four workers. It does not run V01-V07, add comments,
change account details, reset databases or clear quotas.

Before (V1):

```sh
python3 /Users/sid/Desktop/NewProjects/CFL_IA_2/scripts/demo_v08.py v1
```

After (V2):

```sh
python3 /Users/sid/Desktop/NewProjects/CFL_IA_2/scripts/demo_v08.py v2
```

Both stages in order:

```sh
python3 /Users/sid/Desktop/NewProjects/CFL_IA_2/scripts/demo_v08.py both
```

Record the individual response lines and final accepted/rate-limited counts.
V1 should accept all 40. V2 should return HTTP 429 for excess requests, with
at most six accepted reports in the tested quota window. The exact split is
measured, not hardcoded. Other HTTP statuses and connection failures are shown
as errors; they are not counted as blocked attacks.

Wait at least 60 seconds before repeating V2, including after the full stack
verifier. A warm quota can cause all 40 requests to receive 429. Results are
saved to the printed `output/v08-demo/<timestamp>/results.json` path without
passwords, cookies, CSRF tokens or response bodies.

Say: "The same bounded local request batch is accepted by V1. V2 applies
admission controls and rejects excess requests with HTTP 429."

This is a one-client request-burst and rate-limiting demonstration. It does
not establish distributed DDoS resistance or make the website unavailable.
Targets, request count and worker count are fixed; no public target is accepted.
