# V1 four-passphrase challenge

The V1 Render Docker image enables `V1_CHALLENGE_ENABLED=1`. The ordinary local
V1 entry point leaves the challenge disabled. V2 has no challenge routes or data.

Open `/challenge` or choose **Unlock flag** in the V1 sidebar. Players start as
the fictional employee `alice` / `alice123`, recover four different passphrases,
then submit them together. The server accepts any order, ignores capitalization
and surrounding spaces, and reveals the flag only when the set is complete.
Missing, repeated, incorrect, and duplicate form parameters cannot unlock it.
Success is per submission; it does not unlock the page for other visitors.

The four existing demonstration surfaces are:

| Finding | Location | Recovery path |
|---|---|---|
| V03 IDOR | Bob's ticket #1002 | Alice changes the ticket ID to read another employee's request. |
| V04 Unsigned identity | `/admin` | Changing the unsigned `user_id` cookie to `1` opens administration. |
| V06 Traversal | Private dummy configuration | `/download?file=../private/legacy-config.txt` escapes the downloads folder within the fixture sandbox. |
| V07 Debug exposure | `/debug` | The unprotected diagnostics response discloses a passphrase. |

The portal gives indirect clues without printing these paths or the answers on
the vault page. Answers and validation live in server-side `app/challenge.py`;
there is no browser answer list or flag in GET responses. This is a fictional
source-available training challenge: existing demo credentials can also grant
legitimate access to protected pages. It does not attest that an exploit occurred.

This does not depend on SQL injection being accepted by Render's edge and does
not require traffic/load testing. It adds no new intentional vulnerability.
No database migration is required; passphrases appear when the existing records
and endpoints are rendered, including with an already-seeded database.

Run the isolated, bounded HTTP checks from the repository root:

```sh
python3 deploy/render/test_v1_challenge.py
```

For a local preview, use `V1_CHALLENGE_ENABLED=1 python3 app/server.py`.
The four passphrases and flag are fictional game answers, not service credentials.
