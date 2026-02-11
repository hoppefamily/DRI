# Client Integration Guide

## Overview

The DRI system outputs parquet files that serve as a complete data API for client applications (iOS, Dashboard, etc.). No Python runtime or API server is required - clients can read parquet files directly.

## Data Files

### Primary Output: `dri_latest.parquet`

The main DRI snapshot file at `data/dri_latest.parquet` contains:

**Aggregated Metrics:**
- `asof_date`: Calculation date
- `median_effective_exposure`: Panel median exposure (0-1 scale, time-decayed)
- `median_delta`: Change in exposure since prior quarter
- `dispersion`: Standard deviation of panel exposures (disagreement measure)
- `dispersion_spread`: Max - min exposure (robustness check)
- `regime_state`: Regime classification (Risk-On, Risk-Off, Transition)
- `panel_members`: List of CIK identifiers for panel managers

**Individual Manager Readings:**
- `sensor_readings`: Array of manager sensor readings with:
  - `cik`: Manager identifier
  - `name`: Manager name
  - `filing_date`: Date of last 13F-HR filing
  - `days_since_snapshot`: Age of data in days
  - `exposure_index`: Raw exposure (0-100%, not time-decayed)
  - `effective_exposure`: Time-decayed exposure used in aggregation
  - `delta_exposure`: Change since prior quarter
  - `rolling_max_5y`: 5-year historical maximum exposure
  - **`filing_status`**: Filing staleness classification (see below)

## Filing Status Levels

The `filing_status` field indicates data freshness for each manager:

| Status | Condition | UI Recommendation |
|--------|-----------|-------------------|
| `CURRENT` | Less than 92 days since filing | No special indicator - data is fresh |
| `PENDING` | Within grace period (< 92 days) | Gray dot or "Filing expected" |
| `LATE_MINOR` | 7-30 days overdue | Yellow warning - monitor |
| `LATE_MODERATE` | 31-89 days overdue | Orange alert - concerning |
| `INACTIVE` | 90+ days overdue | Red alert - likely stopped filing |

**Filing Schedule:** 13F-HR filings are due 45 days after quarter-end:
- Q1 (Mar 31) → Due May 15
- Q2 (Jun 30) → Due Aug 14
- Q3 (Sep 30) → Due Nov 14
- Q4 (Dec 31) → Due Feb 14

Grace period: 45 days filing deadline + 47 day grace = 92 days total

## Client Implementation Examples

### Swift (iOS)

```swift
import DuckDB

// Load DRI snapshot
let conn = try Connection()
let snapshot = try conn.query("""
    SELECT
        asof_date,
        regime_state,
        median_effective_exposure,
        dispersion,
        sensor_readings
    FROM read_parquet('s3://bucket/dri/latest.parquet')
""")

// Access individual manager status
for row in snapshot {
    let readings = row["sensor_readings"] as! [[String: Any]]
    for reading in readings {
        let name = reading["name"] as! String
        let status = reading["filing_status"] as! String
        let daysOld = reading["days_since_snapshot"] as! Int

        // Show status indicator
        switch status {
        case "CURRENT":
            // No indicator
        case "PENDING":
            showGrayDot(for: name)
        case "LATE_MINOR":
            showYellowWarning(for: name, daysOld: daysOld)
        case "LATE_MODERATE", "INACTIVE":
            showRedAlert(for: name, daysOld: daysOld)
        default:
            break
        }
    }
}
```

### Python (Dashboard)

```python
import pandas as pd
import plotly.graph_objects as go

# Load DRI snapshot
snapshot = pd.read_parquet('data/dri_latest.parquet')
readings = snapshot['sensor_readings'].iloc[0]

# Create status indicators
status_colors = {
    'CURRENT': 'green',
    'PENDING': 'gray',
    'LATE_MINOR': 'yellow',
    'LATE_MODERATE': 'orange',
    'INACTIVE': 'red'
}

# Build table with status indicators
fig = go.Figure(data=[go.Table(
    header=dict(values=['Manager', 'Status', 'Days Old', 'Exposure']),
    cells=dict(
        values=[
            [r['name'] for r in readings],
            [r['filing_status'] for r in readings],
            [r['days_since_snapshot'] for r in readings],
            [f"{r['exposure_index']:.1f}%" for r in readings]
        ],
        fill_color=[[status_colors[r['filing_status']] for r in readings]]
    )
)])
```

### SQL (DuckDB)

```sql
-- Filter to only current managers
SELECT
    UNNEST(sensor_readings, recursive := true)
FROM read_parquet('s3://bucket/dri/latest.parquet')
WHERE filing_status = 'CURRENT';

-- Find stale managers
SELECT
    name,
    filing_status,
    days_since_snapshot,
    filing_date
FROM (
    SELECT UNNEST(sensor_readings, recursive := true)
    FROM read_parquet('s3://bucket/dri/latest.parquet')
)
WHERE filing_status != 'CURRENT'
ORDER BY days_since_snapshot DESC;
```

## Data Updates

The DRI pipeline should be run:
- **Minimum:** Weekly (to update time-decay calculations)
- **Optimal:** Daily (to catch new filings immediately)
- **Critical:** After quarterly filing deadlines (Feb 14, May 15, Aug 14, Nov 14)

The `days_since_snapshot` and `effective_exposure` fields are recalculated on each run based on the current date, even if no new filings have been submitted.

## Historical Data

Individual manager histories are stored in `sensor_{CIK}_history.parquet` files containing:
- All available quarterly filings (typically 5 years)
- Historical exposure calculations
- Used for 5-year rolling maximum calculations

These are **not** needed for real-time dashboard display. Use `dri_latest.parquet` for current state.

## S3 Configuration

For production deployment, configure S3 in `config/default_config.yaml`:

```yaml
storage:
  local_dir: "./data"
  s3:
    bucket: "your-bucket-name"
    prefix: "dri/"
    region: "us-east-1"
```

Then upload with: `dri run --upload-s3`

Clients read directly from S3:
```sql
SELECT * FROM read_parquet('s3://your-bucket/dri/latest.parquet')
```

## Monitoring

See [PANEL_MONITORING.md](PANEL_MONITORING.md) for:
- Staleness detection workflows
- Manager replacement procedures
- Panel health monitoring best practices
