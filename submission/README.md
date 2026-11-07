# CFLIA final submission

**Current Render-only recording:** use [the hosted external form and guide](https://legacydesk-csrf-demo.onrender.com), or [the guide source](RENDER_ONLY_DEMONSTRATION_GUIDE.md). It covers real hosted V02-V07 checks, marks V01 as platform-filtered and excludes V08. No local demo server is needed. The full-lab report and older scripts below retain their original local evidence scope.

The original portal remains at `http://127.0.0.1:8080`. The separate hardened portal is at `https://127.0.0.1:8443` (local CA). Both services returned HTTP 200 on their health endpoints during the 16 October handoff check.

## Read and present

- [Final report PDF](../output/pdf/CFLIA_Final_Report.pdf) and [editable Word report](../output/documents/CFLIA_Final_Report.docx): Plain-language explanations grouped into what we found and how we fixed it, with screenshots, website context, architecture and defensive layers.
- [Team script PDF](../output/pdf/CFLIA_Team_Script.pdf) and [editable Word script](../output/documents/CFLIA_Team_Script.docx): nine pages, four speakers, two vulnerabilities each, seven-minute timing, narration, screen actions, payloads and rehearsal checklist.
- [Demonstration guide PDF](../output/pdf/CFLIA_Demonstration_Guide.pdf) and [editable guide](DEMONSTRATION_GUIDE.md): six pages of exact recording actions, expected results, local/Render differences, evidence references and troubleshooting. Use the local lab for the complete SQLi and resource-consumption scenes.
- [Report Markdown](FINAL_REPORT.md) and [script Markdown](TEAM_SCRIPT.md) provide searchable text and relative image links.
- [All final captures](../output/playwright/final/) include 16 paired HTTP evidence screenshots, actual browser screenshots, Nmap/ZAP/tshark views and a silent evidence walkthrough. The walkthrough is source footage, not a finished narrated team video.

| Speaker | Time | Full before, fix and after sequences |
|---|---|---|
| Member 1 | 00:00–01:45 | SQL injection and stored XSS |
| Member 2 | 01:45–03:30 | Object access and forged sessions |
| Member 3 | 03:30–05:15 | CSRF and path traversal |
| Member 4 | 05:15–07:00 | Misconfiguration and resource consumption |

The report contains a team table with Siddharth Kamat and the supplied roll number filled in. The remaining team names and roll numbers are blank for completion.

## Verification

The final security capture is dated **15 October 2026**. All eight v1 findings were observed; all **19 origin tests** and **17 deployed checks** passed. The 40-request/four-worker comparison yielded 40 HTTP 200 responses in v1, then 5 HTTP 200 and 35 HTTP 429 responses in v2. These are bounded local observations, not proof of distributed denial-of-service resistance.

- [Comparison JSON](evidence/comparison.json)
- [Baseline results](../output/evidence/baseline-20261015T065446247953Z/results.json)
- [Final deployed results](../v2/output/verification-20261015T070630Z/results.json)
- [Origin test output](../v2/output/origin-tests.txt)
- [Redacted v2 responses](evidence/v2-http-responses.json)
- [ZAP proxy history](evidence/zap-proxy-history.json)
- [Wireshark capture](evidence/local-http.pcapng) and [HTTP packet fields](evidence/wireshark-http-summary.tsv)
- [Dependency audit](evidence/dependency-audit.json): no known advisories in the eight pinned Python packages at capture time.

The HTTP evidence pages render selected fields from real captures and identify their sources. They are not application UI screenshots. The full screenshots are preserved. The simplified report uses request/response excerpts without the viewer date strip or source footer, and a cropped debug excerpt keeps the first exposed account readable. Live v2 secrets are redacted or excluded.

## Run again

From the repository root:

```bash
docker compose up -d
python3 v2/scripts/setup.py
docker compose -f v2/compose.yaml up -d --build
docker compose -f v2/compose.yaml exec -T app python -m unittest discover -s tests -v
python3 v2/scripts/verify_stack.py
```

Wait at least 60 seconds between full deployed runs. The verifier adds one normal comment to v2; the baseline probe adds one harmless XSS comment and changes the known v1 test email. At handoff, only records created by our verification runs were removed: both databases have four tickets and the original one comment. No original source file was patched.

Passwords are generated locally in ignored `v2/state/credentials.json`; TLS private keys and `.env` are also ignored. Do not include these files in recordings or handoffs. See [v2 instructions](../v2/README.md) for the full deployment details.

## Rebuild documents

`scripts/build_documents.py` builds both Word files and their Markdown sources from the saved evidence. Use `--report-only` to rebuild the simplified report without changing the team script. The report wording lives in `scripts/report_content.py`. It requires Python with python-docx, Pillow and the Arial font used on this Mac. The submitted PDF exports were rendered and visually reviewed. The repository includes the final exports so rebuilding is optional.
