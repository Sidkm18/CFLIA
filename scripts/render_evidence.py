#!/usr/bin/env python3
"""Render recorded JSON as a standalone evidence page; no fabricated values."""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted((ROOT / "output/evidence").glob("baseline-*/results.json"))[-1]
data = json.loads(source.read_text())
e = lambda value: html.escape(str(value))
rows = "".join(f'<tr><td>{e(f["id"])}</td><td><strong>{e(f["title"])}</strong><small>{e(f["detail"])}</small></td><td>{"Observed" if f["baseline_failure_observed"] else "Not observed"}</td></tr>' for f in data["findings"])
load = data["load_probe"]
cards = "".join(f'<article><span>{e(label)}</span><strong>{e(value)}</strong></article>' for label, value in [
    ("Requests / workers", f'{load["requests"]} / {load["concurrency"]}'),
    ("HTTP responses", json.dumps(load["status_counts"])),
    ("Throughput", f'{load["throughput_rps"]} req/s'),
    ("Median / p95", f'{load["median_latency_ms"]} / {load["p95_latency_ms"]} ms')])
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Recorded baseline evidence · LegacyDesk</title><style>body{{font:14px/1.5 system-ui;color:#19241f;background:#f5f6f8;margin:0;padding:32px 50px}}main{{max-width:1250px;margin:auto}}h1{{font-size:30px;letter-spacing:-1px;margin:8px 0}}.eyebrow{{font-size:10px;letter-spacing:1px;color:#235c43}}p{{color:#758078;font-size:12px}}table{{background:white;width:100%;border-collapse:collapse;border:1px solid #e6eae6}}td,th{{text-align:left;padding:12px 18px;border-bottom:1px solid #e6eae6;font-size:12px}}th{{background:#e5f0e9;font-size:10px;letter-spacing:1px}}td:first-child{{color:#235c43;font-weight:600}}td:last-child{{color:#235c43;white-space:nowrap}}small{{display:block;color:#758078;font-size:10px;margin-top:3px}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}article{{background:white;padding:18px;border:1px solid #e6eae6;border-radius:6px}}article span{{display:block;font-size:10px;color:#758078}}article strong{{font-size:18px;display:block;margin-top:8px}}.note{{background:#f9eddb;padding:14px 18px;color:#775431;border-radius:6px;font-size:11px}}h2{{font-size:18px;margin:22px 0 12px}}@media(max-width:700px){{body{{padding:20px}}.cards{{grid-template-columns:1fr 1fr}}}}</style></head><body><main><div class="eyebrow">LEGACYDESK / CAPTURED BASELINE MEASUREMENTS</div><h1>Eight failures observed.</h1><p>Target: {e(data["target"])} · Capture timestamp (UTC): {e(data["recorded_at_utc"])}<br>Source: {e(source.name)} in {e(source.parent.name)}. This page renders the recorded JSON.</p><table><thead><tr><th>ID</th><th>BASELINE FINDING AND EVIDENCE</th><th>RESULT</th></tr></thead><tbody>{rows}</tbody></table><h2>Bounded local request probe</h2><div class="cards">{cards}</div><p class="note">{e(load["limitation"])} Browser execution and cookie behaviour are established by separate browser screenshots, not by this table.</p></main></body></html>'''
target = source.with_name("results.html")
target.write_text(page)
print(target)
