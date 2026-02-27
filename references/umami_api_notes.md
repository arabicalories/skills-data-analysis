# Umami API Notes

This skill uses these Umami endpoints:

1. `GET /websites/{websiteId}/stats`
   - Purpose: basic metrics (`visitors`, `visits`, `totaltime`)
   - Query: `startAt`, `endAt` (epoch milliseconds)

2. `GET /reports`
   - Purpose: read configured funnel reports
   - Query: `websiteId`, `type=funnel`, `page`, `pageSize`

3. `POST /reports/funnel`
   - Purpose: execute funnel for selected date range
   - Body shape:
     - `websiteId`
     - `type: "funnel"`
     - `filters: {}`
     - `parameters.startDate` / `parameters.endDate` (ISO8601 UTC)
     - `parameters.steps` / `parameters.window`

## Authentication

Use one of:

1. Cloud key: header `x-umami-api-key`
2. Self-hosted token: header `Authorization: Bearer <token>`

## Base URL

Examples:

1. Cloud: `https://api.umami.is/v1`
2. Self-hosted: `https://your-umami-host/api`

The script appends endpoint paths (for example `/websites/...`, `/reports`).
