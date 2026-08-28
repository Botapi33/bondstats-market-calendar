# BondStats Market Calendar — Final v2

**The events that can reprice rates, sovereign bonds and macro expectations.**

## Product surfaces
- `index.html` — full Market Calendar
- `widget.html` — compact homepage widget showing the next four market-moving events
- `health.html` — source-health / feed diagnostic page
- `data/events.json` — reusable normalized calendar feed
- `scripts/update_calendar.py` — official-source ingestion engine
- `.github/workflows/update-calendar.yml` — automatic refresh every 6 hours
- `tests/test_calendar.py` — deterministic feed/parser checks

## Official source coverage
1. Federal Reserve — FOMC calendar
2. U.S. Bureau of Labor Statistics — official ICS calendar
3. U.S. Bureau of Economic Analysis — official release schedule
4. European Central Bank — Governing Council monetary-policy meetings
5. Bank of England — MPC decision dates
6. Bank of Japan — MPM dates
7. Swiss National Bank — monetary-policy assessments
8. U.S. Treasury / TreasuryDirect — PendingAuctions.xml

## Data-integrity rules
- Official sources only.
- No synthetic consensus/forecast values.
- Exact official times are tagged `exact`.
- Standard scheduled publication times are tagged `convention`.
- Date-only events are tagged `date` and rendered as **Time TBA**.
- If a source parser fails, the previous valid events from that source are retained and the source is marked `degraded`.
- All events expose source attribution and an official-source link.

## BondStats Impact Score
The score is deterministic and market-oriented rather than crowdsourced:
- 90–100: CRITICAL
- 70–89: HIGH
- below 70: MEDIUM

It prioritizes policy decisions, inflation, labour-market releases and sovereign funding events according to their relevance to rates and government-bond repricing.

## Deploy
1. Create a GitHub repository named `bondstats-market-calendar`.
2. Upload the full repository preserving `.github/workflows/`.
3. Enable GitHub Pages from `main` / root.
4. In repository Settings → Actions → General, ensure workflow permissions allow **Read and write permissions**.
5. Run `Update Market Calendar` once manually from Actions.
6. Open `/health.html` and confirm source status.
7. Use `/widget.html` for the BondStats homepage and `/index.html` as the full calendar.

No API key is required.

© 2026 BondStats Ltd. All rights reserved.
