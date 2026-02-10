# DRI — Discretionary Risk Index

A multi-manager regime indicator measuring whether discretionary macro managers collectively permit equity risk.

## What DRI Measures

- **Normalized 13F exposure:** How much public equity risk each manager carries relative to their own historical max
- **Rate of change:** Is confidence rising or falling?
- **Cross-manager dispersion:** Are beliefs aligned or diverging?

DRI is **not** an alpha model or stock-selection tool. It measures **belief coherence** to detect regime strain before macro breaks.

## Quick Start

```bash
# Install
pip install -e ".[all]"

# Set SEC User-Agent (required for EDGAR access)
export SEC_USER_AGENT="YourCompany your@email.com"

# Fetch 13F data for a panel member
dri sensor fetch 0001536411 --quarters 8

# Run DRI pipeline
dri run --config config/default_config.yaml

# View latest regime
dri show
```

## Design Principles

1. **State, not timing:** DRI describes regime state over months/quarters
2. **No mind-reading:** Only infer what 13F disclosures support
3. **Relative scale:** Each manager defines their own "max risk-on"
4. **Composable:** Single-manager sensors feed multi-manager aggregation
5. **Transparent:** All thresholds and decay parameters are configurable

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DRI Pipeline                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │   EDGAR      │   │   EDGAR      │   │   EDGAR      │   │
│  │  Fetcher     │   │  Fetcher     │   │  Fetcher     │   │
│  │ (Manager 1)  │   │ (Manager 2)  │   │ (Manager N)  │   │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │   Manager    │   │   Manager    │   │   Manager    │   │
│  │   Sensor     │   │   Sensor     │   │   Sensor     │   │
│  │ (Exposure)   │   │ (Exposure)   │   │ (Exposure)   │   │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            ▼                                 │
│                    ┌───────────────┐                        │
│                    │  Aggregator   │                        │
│                    │ (Median, Δ,   │                        │
│                    │  Dispersion)  │                        │
│                    └───────┬───────┘                        │
│                            ▼                                 │
│                    ┌───────────────┐                        │
│                    │    Regime     │                        │
│                    │  Classifier   │                        │
│                    └───────┬───────┘                        │
│                            ▼                                 │
│                    ┌───────────────┐                        │
│                    │ DRI Snapshot  │                        │
│                    │  (Parquet)    │                        │
│                    └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Regime States

| Regime | Characteristics |
|--------|----------------|
| **Risk ON** | High median exposure, low dispersion — managers aligned and invested |
| **Risk ON (fragile)** | High median, rising dispersion — beliefs starting to diverge |
| **Transition** | Falling median, high dispersion — disagreement on risk levels |
| **Risk OFF** | Low median, low dispersion — managers aligned on caution |
| **Panic / Reset** | Fast contraction + dispersion spike — rapid de-risking |

## Documentation

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Detailed implementation guide
- [PHILOSOPHY.md](PHILOSOPHY.md) — Design rationale and limitations

## License

Dual licensed under Apache-2.0 OR GPL-3.0. See LICENSE files.

## Citation

Based on the Discretionary Risk Index specification by Michael Hoppe, 2026.
