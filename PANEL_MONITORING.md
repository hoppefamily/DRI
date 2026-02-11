# DRI Panel Monitoring & Manager Rotation Guide

**Last Updated:** February 11, 2026
**Status:** Operational Guidance

---

## Table of Contents

1. [Overview](#overview)
2. [The Problem: Manager Stops Filing](#the-problem-manager-stops-filing)
3. [Detection & Alerting](#detection--alerting)
4. [Impact Assessment](#impact-assessment)
5. [Investigation Workflow](#investigation-workflow)
6. [Replacement Decision Matrix](#replacement-decision-matrix)
7. [Panel Rotation Procedure](#panel-rotation-procedure)
8. [Candidate Manager Pool](#candidate-manager-pool)

---

## Overview

The DRI system depends on **timely 13F-HR filings** from a panel of discretionary macro managers. When a manager stops filing (due to fund closure, AUM dropping below $100M threshold, or restructuring), the signal quality degrades through:

- **Exponential decay** reducing effective exposure toward zero
- **Increased dispersion** as stale data diverges from fresh signals
- **Skewed median** pulling regime classification toward false RISK_OFF

**This document provides operational procedures for monitoring panel health and rotating managers.**

---

## The Problem: Manager Stops Filing

### Why Managers Stop Filing 13F-HR

| Reason | Frequency | Detectability | Example |
|--------|-----------|---------------|---------|
| **AUM < $100M** | Common (bear markets) | Hard to detect | Small funds after redemptions |
| **Fund Closure** | Occasional | Press coverage | Tiger Management (2000), Duquesne Capital (2010) |
| **Restructuring** | Rare | Difficult | Converting to private vehicles |
| **Entity Change** | Occasional | New CIK appears | Duquesne Capital → Duquesne Family Office |
| **Death/Retirement** | Rare | Press coverage | Succession issues |

### What SEC EDGAR Tells You

**Observable:**
- ✅ Historical filing dates and frequencies
- ✅ Last filing date
- ✅ Gaps in filing schedule

**NOT Observable:**
- ❌ Whether manager is still required to file
- ❌ Whether fund is closed or operating
- ❌ Current AUM status
- ❌ Intent or future filing plans

**The Ambiguity Window:** After a manager misses a filing deadline (45 days post-quarter), you have **60-90 days of uncertainty** before you can confidently conclude they've stopped filing.

---

## Detection & Alerting

### Automated Status Checks

The DRI pipeline automatically classifies manager status:

| Status | Criteria | Interpretation | Action |
|--------|----------|----------------|--------|
| **CURRENT** | < 60 days since filing | Normal quarterly cycle | None |
| **PENDING** | Filing not yet due | Waiting for expected filing | Monitor |
| **LATE_MINOR** | 1-30 days overdue | May file soon (late filers exist) | Watch closely |
| **LATE_MODERATE** | 31-90 days overdue | Probably stopped filing | **INVESTIGATE** |
| **INACTIVE** | 90+ days overdue | Confirmed inactive | **REPLACE** |

### Pipeline Warnings

When running `dri run`, stale managers (> 120 days) trigger warnings:

```
================================================================================
STALE DATA DETECTED - Panel Review Recommended
================================================================================

Pershing Square Capital (CIK 0001336528):
  Status: LATE_MODERATE
  Days since filing: 184
  Days overdue: 62
  Action: ⚠️  REVIEW NEEDED - Check SEC ADV and press for status
  SEC ADV: https://adviserinfo.sec.gov/
  SEC EDGAR: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=...

================================================================================
See PANEL_MONITORING.md for guidance on panel member replacement
================================================================================
```

### Manual Monitoring Schedule

**Quarterly (within 60 days of quarter end):**
- Run `dri run` and check for staleness warnings
- Review filing dates for all panel members
- Verify expected filings arrived on schedule

**When Triggered:**
- Any manager reaches `LATE_MODERATE` status
- Pipeline warnings appear
- Press reports fund closures or major redemptions

---

## Impact Assessment

### Signal Degradation Timeline

**Tactical Manager (30-day halflife):**
```
Days Since Filing → Effective Exposure Decay
  30 days:  100% → 50%
  60 days:  100% → 25%
  90 days:  100% → 12.5%
 120 days:  100% → 6.25%
 180 days:  100% → 1.56%  ← Essentially zero
```

**Structural Manager (60-day halflife):**
```
Days Since Filing → Effective Exposure Decay
  60 days:  100% → 50%
 120 days:  100% → 25%
 180 days:  100% → 12.5%
 240 days:  100% → 6.25%
 365 days:  100% → 1.0%  ← Effectively zero
```

### Impact on Regime Classification

**3-Manager Panel (1 stale @ 180 days):**
- **Median drops** by ~30-40% (one zero value)
- **Dispersion increases** (fresh vs stale divergence)
- **False RISK_OFF signals** (low median exposure)
- **TRANSITION becomes default** (high dispersion)
- **Delta signals weaken** (stale manager shows no change)

**Critical Threshold:** At **120 days**, effective exposure has decayed enough to materially impact the DRI calculation.

**Minimum Viable Panel:** 4 active managers. Dropping to 3 violates design assumptions and reduces statistical robustness.

---

## Investigation Workflow

When a manager reaches `LATE_MODERATE` status (31-90 days overdue):

### Step 1: Verify Filing Schedule

```bash
# Check their recent filing history
curl -H "User-Agent: Michael Hoppe michael@hoppefamily.de" \
  "https://data.sec.gov/submissions/CIK<CIK>.json" | \
  jq '.filings.recent | {form: .form, date: .filingDate} |
      [.form, .date] | transpose | map(select(.[0] | contains("13F")))'
```

**Questions:**
- Is this the first missed filing or a pattern?
- Are they consistently late filers?
- Did they file amendments that delayed the primary?

### Step 2: Check SEC Form ADV

Visit: `https://adviserinfo.sec.gov/`

**Look for:**
- Current AUM (Item 5)
- Number of clients
- Registration status (Active vs Withdrawn)
- Last ADV update date

**Red flags:**
- AUM near $100M threshold
- "Withdrawn" status
- ADV not updated in 12+ months

### Step 3: Search Press & Industry Sources

**Google News:**
```
"[Manager Name]" AND ("closed" OR "shutting down" OR "redemptions" OR "liquidating")
```

**Industry databases:**
- Bloomberg terminal (if available)
- BarclayHedge fund database
- Preqin hedge fund data

**Check fund website:**
- Announcements of closures
- Changes in strategy or structure

### Step 4: Contact (if appropriate)

For **institutional relationships**, consider:
- Emailing investor relations
- Checking prime broker connections

**For DRI purposes:** Usually not practical. Rely on public data and press.

---

## Replacement Decision Matrix

After investigation, use this matrix to decide:

| Evidence | AUM Status | Press Reports | Decision |
|----------|-----------|---------------|----------|
| 60+ days overdue | < $100M per ADV | None | **WAIT** - May be below threshold temporarily |
| 90+ days overdue | < $100M per ADV | None | **REPLACE** - Likely permanent |
| 60+ days overdue | Unknown | Fund closing | **REPLACE** - Confirmed closure |
| 90+ days overdue | Any | None | **REPLACE** - Too stale regardless |
| Filed recently | Any | None | **KEEP** - False alarm |
| New CIK filing | Any | Restructured | **UPDATE CIK** - Same manager, new entity |

**Conservative Threshold:** Replace at **90 days overdue** regardless of other factors. The signal degradation is too severe by this point.

---

## Panel Rotation Procedure

### Pre-Rotation Checklist

- [ ] Investigated staleness thoroughly (see Investigation Workflow)
- [ ] Confirmed 90+ days overdue OR press-reported closure
- [ ] Selected replacement candidate (see Candidate Pool below)
- [ ] Verified replacement has 20+ quarters of clean data
- [ ] Tested replacement data fetch: `dri sensor fetch <CIK> --quarters 20 --name "Manager Name"`

### Rotation Steps

**1. Document the decision:**

```bash
cd /Users/michaelhoppe/code/dri
echo "## Panel Rotation - $(date +%Y-%m-%d)

**Removed:** [Old Manager Name] (CIK [OLD_CIK])
**Reason:** [REASON - e.g., 'No filing for 120 days, likely below $100M threshold']
**Investigation:** [SUMMARY]

**Added:** [New Manager Name] (CIK [NEW_CIK])
**Rationale:** [WHY - e.g., 'Discretionary macro, 20Q history, recent AUM $5B']
" >> PANEL_CHANGES.md
```

**2. Update configuration:**

```bash
# Edit config/default_config.yaml
vim config/default_config.yaml
```

Replace the stale manager entry:
```yaml
# OLD (commented out for record)
# - cik: "0001351069"
#   name: "ValueAct Capital"
#   decay_type: "structural"
#   decay_halflife_days: 60

# NEW
- cik: "0001040273"
  name: "Third Point"
  decay_type: "structural"
  decay_halflife_days: 60
```

**3. Fetch new manager data:**

```bash
source venv/bin/activate
export SEC_USER_AGENT="Michael Hoppe michael@hoppefamily.de"

dri sensor fetch <NEW_CIK> --quarters 20 --name "New Manager Name"
```

**4. Run full pipeline:**

```bash
dri run --dry-run
# Review output, check for errors
dri run
# Production run
```

**5. Verify regime output:**

```bash
dri show
```

**6. Commit changes:**

```bash
git add config/default_config.yaml PANEL_CHANGES.md
git commit -m "Panel rotation: Replace [Old] with [New]

[Old Manager] has not filed for [X] days. Investigation showed [REASON].
Replaced with [New Manager] (CIK [NEW_CIK]) - [JUSTIFICATION].

[New Manager] characteristics:
- AUM: $[X]B
- Strategy: [Discretionary macro / Event-driven / etc.]
- History: [X] quarters of clean 13F data
- Decay type: [tactical/structural]
"

git push origin main
```

---

## Candidate Manager Pool

Maintain a list of vetted replacement candidates. Update quarterly.

### Current Vetted Candidates (as of Feb 2026)

| Manager | CIK | Style | AUM | Quarters Available | Notes |
|---------|-----|-------|-----|-------------------|-------|
| **Elliott Management** | 0001567228 | Activist/Macro | $55B | 40+ | Paul Singer, very selective |
| **Appaloosa Management** | 0001029160 | Macro | $5B | 80+ | David Tepper, tactical |
| **Baupost Group** | 0001061768 | Value/Macro | $30B | 100+ | Seth Klarman, patient capital |
| **Viking Global** | 0001103804 | Long/short equity | $24B | 60+ | O. Andreas Halvorsen, flexible |
| **Soros Fund Management** | 0001029330 | Macro | $25B | 120+ | George Soros family office |

### Evaluation Criteria for New Candidates

**Required:**
- ✅ Discretionary macro or flexible equity strategy
- ✅ Willing to hold significant cash (50%+) when defensive
- ✅ 20+ quarters of consistent 13F-HR filings
- ✅ AUM > $1B (buffer above $100M threshold)
- ✅ Clean data (no systematic filing errors)

**Preferred:**
- ⭐ AUM $5-50B (not too small, not index-tracking)
- ⭐ Public track record of market timing
- ⭐ Known for tactical positioning
- ⭐ Different investment philosophy from existing panel (diversification)

**Research Process:**

```bash
# 1. Find CIK
curl -s "https://www.sec.gov/cgi-bin/browse-edgar?company=MANAGER+NAME&type=13F&owner=exclude" | grep -o "CIK=[0-9]*" | head -1

# 2. Check filing history
curl -H "User-Agent: Michael Hoppe michael@hoppefamily.de" \
  "https://data.sec.gov/submissions/CIK<CIK>.json" | \
  jq '.filings.recent | [.form, .filingDate] | transpose | map(select(.[0] | contains("13F-HR")))'

# 3. Test data fetch
dri sensor fetch <CIK> --quarters 5 --name "Test Manager"

# 4. Check ADV for strategy description
# Visit: https://adviserinfo.sec.gov/
```

---

## Appendix: SEC 13F-HR Filing Calendar

**Quarterly Deadlines:**

| Quarter End | Deadline | Typical Filing Window |
|------------|----------|---------------------|
| March 31 (Q1) | May 15 (45 days) | May 10-15 |
| June 30 (Q2) | August 14 (45 days) | August 9-14 |
| September 30 (Q3) | November 14 (45 days) | November 9-14 |
| December 31 (Q4) | February 14 (45 days) | February 9-14 |

**Grace Period:** Most managers file within the deadline, but the SEC allows late filings with Form 13F-NT (Notice of Late Filing). However, many managers who've stopped filing simply go silent without filing 13F-NT.

**Detection Window:**
- **Day 45**: Deadline passes
- **Day 50-60**: Late but might still file
- **Day 90**: Very likely stopped filing
- **Day 120**: Effectively confirmed inactive

---

## Questions?

For operational or technical questions:
- See [README.md](README.md) for troubleshooting
- Check [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for architecture details
- Open an issue on GitHub for additional support
