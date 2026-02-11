# Discretionary Risk Index (DRI)

## 0) One‑sentence definition

**DRI** is a **multi‑manager regime indicator** that measures **whether discretionary macro managers collectively permit equity risk**, using **normalized 13F exposure**, **rate of change**, and **cross‑manager dispersion** to detect belief strain before macro breaks.

It is **not** an alpha model and **not** a stock‑selection tool.

---

## 1) Problem this solves

Some macro risks (e.g., slow sovereign‑bond fractures, carry‑trade stress) do not announce themselves through prices until late.

Before prices move:
- beliefs diverge
- permission to carry risk shrinks
- disagreement rises

DRI is designed to measure **belief coherence**, not returns.

---

## 2) Panel construction (non‑negotiable)

### Inclusion criteria
A manager must be:
1. Discretionary (human judgment)
2. Willing to go materially risk‑off
3. Macro‑aware (rates / FX / policy sensitive)
4. Observable via consistent 13F history

### Panel rules
- Small (4–7 managers)
- Stable (no rotation)
- No weighting by AUM

Each manager is treated as **one independent sensor**.

---

## 3) Core measurements (per manager)

### 3.1 Normalized exposure

For manager *i*:

```
Exposure_i(t) = Total13F_i(t) / Max13F_i(rolling 5y)
```

Range: 0.0 → 1.0

Meaning:
> “How much disclosed public‑equity risk this manager is willing to carry, relative to their own recent history.”

---

### 3.2 Rate of change (belief velocity)

```
ΔExposure_i(t) = Exposure_i(t) − Exposure_i(t−1)
```

Fast negative deltas matter more than low absolute levels.

---

### 3.3 Time decay (continuous interpretation)

Each snapshot decays with time:

```
EffectiveExposure_i(t) = Exposure_i(snapshot) × decay(days_since_snapshot)
```

Decay speed is manager‑specific (fast for tactical traders, slower for structural investors).

---

## 4) Aggregation (panel‑level signals)

### 4.1 Median effective exposure

Answers:
> “Is equity risk broadly permitted right now?”

---

### 4.2 Exposure momentum (median Δ)

Answers:
> “Is confidence in carrying risk rising or falling?”

---

### 4.3 Dispersion (critical)

```
Dispersion(t) = stddev(EffectiveExposure_i(t))
```

Meaning:
- Low dispersion → regime clarity
- Rising dispersion → belief strain
- High dispersion → fragile markets

Dispersion is the **earliest warning signal**.

---

## 5) Regime classification (output layer)

| Regime | Characteristics |
|------|----------------|
| Risk ON | High median, low dispersion |
| Risk ON (fragile) | High median, rising dispersion |
| Transition | Falling median, high dispersion |
| Risk OFF | Low median, low dispersion |
| Panic / Reset | Fast contraction + dispersion spike |

This describes **state**, not timing.

---

## 6) Interpretation rules (how to use)

DRI is a **prior**, not a trigger.

- Strong flows + rising dispersion → late‑cycle danger
- Flat prices + rising dispersion → hidden stress
- Falling dispersion + rising exposure → durable trends

DRI should be fused with:
- flow
- volatility
- FX stress
- rate convexity

---

## 7) What DRI intentionally ignores

- Stock selection
- Sector composition
- Narrative agreement
- Equity duration semantics

Absence of these is deliberate.

---

## 8) Failure modes (known, acceptable)

- Fast intra‑quarter shocks (e.g., sudden pandemics)
- Risk expressed mainly via derivatives
- Policy‑suppressed markets delaying price discovery

These do not invalidate the indicator.

---

## 9) Output schema (example)

Fields:
- `asof_date`
- `median_effective_exposure`
- `median_delta`
- `dispersion`
- `regime_state`
- `panel_members`

---

## 10) Core intuition (keep this)

> **Markets break when beliefs stop agreeing — not when prices look bad.**

DRI measures that agreement.
