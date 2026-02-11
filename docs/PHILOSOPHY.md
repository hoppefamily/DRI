# DRI Philosophy & Design Rationale

## Core Intuition

> **Markets break when beliefs stop agreeing — not when prices look bad.**

DRI measures that agreement through the lens of discretionary macro managers who:
- Have access to institutional-grade data (cross-currency swaps, insurer balance sheets, repatriation flows)
- Are willing and able to go materially risk-off
- Express their beliefs through observable 13F position sizes

## Why 13F Data?

### Advantages
- **Public and free:** No data vendor required
- **Standardized format:** Consistent across all managers
- **Quarterly cadence:** Matches macro regime timescales
- **Historical depth:** Data back decades for established managers
- **Revealed preference:** Actions speak louder than words

### Limitations (Acceptable)
- **45-day lag:** Can't catch fast intra-quarter shocks
- **Derivatives invisible:** Options, swaps, shorts excluded
- **Non-13F assets hidden:** Cash, bonds, FX, commodities not disclosed
- **Position-only:** No entry/exit prices, no P&L

**Design choice:** These limitations are features, not bugs. DRI is designed for **slow-moving macro regime shifts**, not tactical timing.

## Why Dispersion Matters

When discretionary managers disagree about how much equity risk to carry, it signals:
- **Belief strain:** No consensus on whether risk is safe to carry
- **Information asymmetry:** Some managers see stress others don't
- **Regime fragility:** Small shocks can cause rapid opinion shifts

**Historical analogy:** Before the 2008 financial crisis, some macro managers (Paulson, Burry) were massively short while others remained long. If 13F captured shorts, dispersion would have spiked before prices broke.

**DRI hypothesis:** Rising dispersion precedes price breaks by weeks to months.

## Why No AUM Weighting?

Each manager is treated as **one independent sensor**, regardless of AUM.

**Rationale:**
1. **Avoid estimation errors:** True AUM is not disclosed in 13F
2. **Preserve signal diversity:** Small nimble funds can be early movers
3. **Simplify interpretation:** Equal weighting is transparent
4. **Match design goal:** Measure belief coherence, not capital flow

**Trade-off:** A $100B fund and a $5B fund get equal weight. This is deliberate — we care about **how many sensors agree**, not how much capital they control.

## Decay Function Subjectivity

The decay function is the **most subjective parameter** in DRI:

```python
EffectiveExposure = Exposure * 0.5^(days_since_snapshot / halflife)
```

**Tactical managers (30-day halflife):**
- Fast position turnover
- Respond quickly to market changes
- 13F snapshot stale after ~60 days (2 half-lives)

**Structural managers (60-day halflife):**
- Slower portfolio adjustments
- Hold core positions across quarters
- 13F snapshot relevant for ~120 days

**Calibration choices:**
- Based on qualitative judgment of manager style
- No optimization against historical data (avoid overfitting)
- Documented per-manager in config

**Future work:** Validate decay rates by comparing consecutive 13F filings (how much actually turned over?).

## Regime Thresholds

Default thresholds are **educated guesses**, not optimized values:

| Threshold | Value | Reasoning |
|-----------|-------|-----------|
| `high_exposure` | 0.65 | Managers carrying >65% of max = still confident |
| `low_exposure` | 0.35 | Below 35% = material de-risking |
| `high_dispersion` | 0.15 | Stddev >15% = meaningful disagreement |
| `dispersion_rising` | 0.03 | 3% increase = trend signal |
| `fast_contraction` | -0.15 | 15% drop = panic/rapid exit |

**Calibration philosophy:**
- Set conservatively (avoid false alarms)
- Directional correctness > precision
- User-configurable for different risk tolerances

**Not shown:** Historical backtesting of thresholds would require data DRI is designed to avoid (overfitting risk).

## Known Failure Modes

### 1. Fast Intra-Quarter Shocks
**Example:** COVID-19 crash (Feb-Mar 2020) happened within Q1. Q4 2019 filings showed no warning.

**Why acceptable:** DRI is not designed for pandemic-speed events. It targets slow-building macro stress (sovereign debt, carry trades, policy errors).

### 2. Risk Expressed Via Derivatives
**Example:** Manager stays 100% long in 13F but buys SPX puts for hedging.

**Why acceptable:** Derivative hedging is a different signal (volatility demand, tail risk). DRI measures **equity exposure permission**, not hedge ratios.

### 3. Policy-Suppressed Markets
**Example:** Central bank interventions delay price discovery.

**Why acceptable:** DRI can flash warning while prices remain stable — this is a feature (early signal). Price confirmation comes later.

## Relationship to Single-Manager Sensor

The single-manager sensor (`dri.sensor`) is a **reusable building block**:
- Can be used standalone for tracking one manager's risk posture
- Feeds into multi-manager DRI aggregation
- Enables future extensions (weighted DRI, sector-specific panels)

**Design pattern:** Composition over monolithic design.

## What DRI Intentionally Ignores

These are **not bugs**:
- Stock selection (which equities held)
- Sector composition (tech vs. value)
- Narrative agreement (what managers say publicly)
- Equity duration semantics (growth vs. value)
- Intraday or weekly timing

**Rationale:** Adding these increases complexity and false signals. DRI is **deliberately narrow** — it does one thing (measure belief coherence) and does it transparently.

## Companion Signals (Future Work)

DRI is most powerful when fused with:
- **JGB 30-year yield:** Daily early warning for Japan/sovereign stress
- **USD/JPY behavior:** Yen strength = repatriation signal
- **VIX term structure:** Volatility demand changes
- **Flow data:** Equity fund flows, ETF creations/redemptions

These are **out of scope for MVP** but natural extensions.

## Success Criteria

DRI succeeds if it:
1. **Provides early warning:** Dispersion rises before price breaks
2. **Avoids false alarms:** Low false positive rate (regime changes are rare)
3. **Transparent interpretation:** Users understand why regime changed
4. **Composable:** Integrates with other signals in a decision framework

DRI fails if it:
- Requires constant threshold tweaking (overfitting)
- Produces regime flips every quarter (too noisy)
- Can't be explained without handwaving (black box)

## Philosophical Stance

> "Markets are not a physics system to be modeled. They are a social system of beliefs to be observed."

DRI observes beliefs through the revealed preferences of managers who:
- Have better access to institutional data than retail investors
- Have incentives to get macro regime calls right
- Express conviction through position sizing

This is **not prediction**. This is **borrowing the judgment of people with better information**.

---

**Last updated:** February 10, 2026
