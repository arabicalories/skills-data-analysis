---
name: skills-data-analysis
description: Pull Umami project analytics for a fixed daily summary. Use when the user asks to aggregate Umami data for yesterday (full day), including basic metrics (visitors, visits, visit duration) and funnel conversion results (for example pv to login, pv to purchase, guest trial, pricing).
---

# Skills Data Analysis

## Overview

Produce a repeatable Umami daily summary with two sections:

1. Basic metrics
2. Funnel metrics

Use the bundled script to avoid hand-writing API calls.

## Quick Start

Set environment variables:

```bash
export UMAMI_BASE_URL="https://api.umami.is/v1"
export UMAMI_API_KEY="your_api_key"            # Cloud auth
# OR export UMAMI_BEARER_TOKEN="your_token"    # Self-hosted auth
export UMAMI_WEBSITE_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export UMAMI_TIMEZONE="Asia/Shanghai"
```

Run:

```bash
python3 scripts/umami_daily_summary.py
```

The script defaults to:

- yesterday (full day in `UMAMI_TIMEZONE`)
- funnel names: `pv -> login`, `pv -> purchase`, `guest trial`, `pricing`
- output format: markdown

## Workflow

1. Compute yesterday's start/end timestamps from timezone.
2. Query `GET /websites/:websiteId/stats` for basic metrics.
3. Query `GET /reports?type=funnel` to load configured funnel reports.
4. Match target funnel names to configured report names.
5. Run each matched funnel with `POST /reports/funnel`.
6. Render final output with:
   - `Umami`
   - `基础数据`
   - `漏斗数据`

## Name Matching Rules

The script tries:

1. Case-insensitive exact name match.
2. Normalized fuzzy match (removes spaces and punctuation).

If names do not match your dashboard report names, provide an explicit map:

```bash
python3 scripts/umami_daily_summary.py \
  --report-name-map '{"pv -> login":"登录漏斗","pv -> purchase":"购买漏斗","guest trial":"试用漏斗","pricing":"查看价格页面漏斗"}'
```

## Output Modes

Markdown (default):

```bash
python3 scripts/umami_daily_summary.py --format markdown
```

JSON:

```bash
python3 scripts/umami_daily_summary.py --format json
```

Write to file:

```bash
python3 scripts/umami_daily_summary.py --output /tmp/umami_daily.json --format json
```

## References

See `references/umami_api_notes.md` for endpoint and auth notes used by this skill.
