# skills-data-analysis

Pull Umami daily analytics summary (basic metrics + funnel metrics) for yesterday.

## Requirements

- Python 3.9+
- Network access to Umami API
- Umami credentials and website info

No third-party Python package is required for this project right now.

## Environment Variables

Set one auth method:

- `UMAMI_API_KEY` (Umami Cloud), or
- `UMAMI_BEARER_TOKEN` (self-hosted Umami)

Required/commonly used:

- `UMAMI_BASE_URL` (default: `https://api.umami.is/v1`)
- `UMAMI_WEBSITE_ID`
- `UMAMI_TIMEZONE` (example: `Asia/Shanghai`)

Optional:

- `UMAMI_USER_AGENT` (override default browser-like UA if needed)
- `UMAMI_FUNNEL_NAMES`
- `UMAMI_FUNNEL_REPORT_MAP` (JSON map)

## Quick Start

```bash
export UMAMI_BASE_URL="https://api.umami.is/v1"
export UMAMI_API_KEY="your_api_key"  # or UMAMI_BEARER_TOKEN
export UMAMI_WEBSITE_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export UMAMI_TIMEZONE="Asia/Shanghai"

python3 scripts/umami_daily_summary.py
```

If you keep values in `.env`, load it first:

```bash
set -a
source .env
set +a
python3 scripts/umami_daily_summary.py
```

## Output

Default output: markdown summary

```bash
python3 scripts/umami_daily_summary.py --format markdown
```

JSON output:

```bash
python3 scripts/umami_daily_summary.py --format json
```

Write to file:

```bash
python3 scripts/umami_daily_summary.py --format json --output /tmp/umami_daily.json
```

## Notes

- The script uses Python standard library (`urllib`, `zoneinfo`, etc.).
- `totaltime` from Umami stats is treated as seconds.
- Funnel display names are currently:
  - `pv -> login` -> `登录率`
  - `pv -> purchase` -> `付费率`
  - `guest trial` -> `试用率`
  - `pricing` -> `价格查看率`
