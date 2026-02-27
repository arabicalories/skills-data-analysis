---
name: skills-data-analysis
description: Pull Umami project analytics for a fixed daily summary, format the result, then push it to Feishu webhook. Use when the user asks to aggregate yesterday full-day metrics (visitors, visits, visit duration) and funnel conversion results (for example pv to login, pv to purchase, guest trial, pricing).
---

# Skills Data Analysis

## Overview

Produce a repeatable Umami daily summary with website info and two data sections:

1. Website info
2. Basic metrics
3. Funnel metrics

Use the bundled script to avoid hand-writing API calls.

## Quick Start

Create `.env` in `KEY=` format:

```bash
UMAMI_BASE_URL=https://api.umami.is/v1
UMAMI_API_KEY=your_api_key            # Cloud auth
# UMAMI_BEARER_TOKEN=your_token        # Self-hosted auth
UMAMI_WEBSITE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
UMAMI_TIMEZONE=Asia/Shanghai
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxx
```

Run:

```bash
python3 scripts/umami_daily_summary.py
```

The script auto-loads `.env`. You can override it with `--env-file /path/to/.env`.
After summary rendering, the script pushes the final result to `FEISHU_WEBHOOK_URL`.

The script defaults to:

- yesterday (full day in `UMAMI_TIMEZONE`)
- funnel names: `pv -> login`, `pv -> purchase`, `guest trial`, `pricing`
- output format: markdown

## Workflow

1. Compute yesterday's start/end timestamps from timezone.
2. Query website metadata to get website name.
3. Query `GET /websites/:websiteId/stats` for basic metrics.
4. Query `GET /reports?type=funnel` to load configured funnel reports.
5. Match target funnel names to configured report names.
6. Run each matched funnel with `POST /reports/funnel`.
7. Render final output with:
   - `Umami`
   - `Website`
   - `基础数据`
   - `漏斗数据`
8. Push final formatted result to Feishu webhook.

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
