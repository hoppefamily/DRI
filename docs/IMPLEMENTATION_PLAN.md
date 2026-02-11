# DRI Implementation Plan

**Last Updated:** February 9, 2026
**Status:** Planning Phase
**Target:** Q4 2025 13F filings (arriving mid-February 2026)

---

## Executive Summary

Build a new standalone `dri` repository implementing the **Discretionary Risk Index (DRI)** — a multi-manager regime indicator measuring whether discretionary macro managers collectively permit equity risk, using normalized 13F exposure, rate of change, and cross-manager dispersion.

**Architecture:** Two-phase approach:
1. **Phase 1:** Single-manager 13F sensor (reusable building block)
2. **Phase 2:** Multi-manager DRI aggregation and regime classification

**Scope:** MVP focuses on CLI + Parquet output. Dashboard and iOS integration are future enhancements.

**Timeline:** 4-6 weeks for MVP (targeting Q4 2025 filing cycle)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Repository | New standalone repo: `dri` | Follows ecosystem pattern; independent release cycle |
| Architecture | Two-phase: sensor → aggregator | Reusable sensor module; cleaner separation of concerns |
| MVP Scope | CLI + Parquet output | Fastest path to processing Q4 2025 filings |
| JGB Signal | Deferred (manual input) | Focus on 13F core; companion signals are future work |
| Storage | Parquet + optional S3 | Matches ibkr-borrow-collector and flow-state-monitor patterns |
| Config | YAML + Python Config class | Consistent with market-state-detector pattern |
| Testing | pytest + fixtures | Standard across all projects |
| Scheduling | GitHub Actions cron | Monthly checks for quarterly 13F filings |

---

## Phase 0: Project Scaffolding

### Repository Structure

```
dri/
├── .github/
│   └── workflows/
│       ├── build-test.yml
│       └── compute-dri.yml
├── src/
│   └── dri/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py                # Command-line interface
│       ├── config.py             # YAML config management
│       ├── edgar.py              # SEC EDGAR 13F fetcher
│       ├── sensor.py             # Single-manager exposure sensor
│       ├── aggregator.py         # Multi-manager DRI aggregation
│       ├── regime.py             # Regime classification logic
│       ├── storage.py            # Parquet read/write + S3
│       └── pipeline.py           # End-to-end orchestrator
├── tests/
│   ├── conftest.py
│   ├── test_edgar.py
│   ├── test_sensor.py
│   ├── test_aggregator.py
│   ├── test_regime.py
│   ├── test_storage.py
│   └── test_pipeline.py
├── config/
│   └── default_config.yaml       # Ships with initial panel
├── fixtures/
│   └── sample_13f.xml            # Test data
├── infra/
│   └── cloudformation-template.yaml
├── pyproject.toml
├── LICENSE-APACHE-2.0
├── LICENSE-GPL-3.0
├── README.md
└── docs/
  ├── PHILOSOPHY.md
  ├── IMPLEMENTATION_PLAN.md
  ├── PANEL_MONITORING.md
  ├── PANEL_CHANGES.md
  ├── QUICKSTART.md
  ├── CLIENT_INTEGRATION.md
  └── discretionary_risk_index_dri_multi_manager_regime_indicator.md
```

### pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "dri"
version = "0.1.0"
description = "Discretionary Risk Index — Multi-manager regime indicator from 13F filings"
readme = "README.md"
requires-python = ">=3.8"
license = {text = "Apache-2.0 OR GPL-3.0"}
authors = [{name = "Michael Hoppe"}]

dependencies = [
    "pandas>=1.3.0",
    "pyyaml>=5.4",
    "pyarrow>=6.0.0",
    "requests>=2.26.0",
    "lxml>=4.6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=3.0.0",
]
s3 = [
    "boto3>=1.20.0",
]
all = [
    "dri[dev,s3]",
]

[project.scripts]
dri = "dri.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

### default_config.yaml

```yaml
# DRI Configuration
panel:
  # Initial panel - discretionary macro managers
  # CIKs to be researched and validated on SEC EDGAR
  - cik: "0001536411"
    name: "Duquesne Family Office"
    decay_type: "tactical"
    decay_halflife_days: 30

  # Placeholder for additional managers (4-7 total required)
  # - cik: "TBD"
  #   name: "TBD"
  #   decay_type: "structural"  # or "tactical"
  #   decay_halflife_days: 60

normalization:
  window_years: 5           # Rolling max window
  method: "rolling_max"     # Options: rolling_max, full_history_max

regime:
  # Exposure thresholds (0-1 scale)
  high_exposure: 0.65
  low_exposure: 0.35

  # Dispersion thresholds
  high_dispersion: 0.15
  dispersion_rising_threshold: 0.03

  # Delta thresholds
  fast_contraction_delta: -0.15

storage:
  output_dir: "./data"
  s3_bucket: null           # Optional: S3 bucket for storage
  s3_prefix: "dri"

edgar:
  user_agent: null          # Set via SEC_USER_AGENT env var
  rate_limit_per_sec: 10
  retry_attempts: 3
  retry_delay_sec: 2
```

---

## Phase 1: Single-Manager Sensor

### Overview

Build `dri.sensor` — a reusable module that computes **relative disclosed public-equity exposure** for a single manager from 13F filings. This is the building block described in the [druckenmiller-sensor plan](../../trading/trading-ideas/druckenmiller_sensor_corrected_open_source_plan.md).

### Components

#### 1. edgar.py — SEC EDGAR 13F Fetcher

**Purpose:** Fetch and parse 13F-HR filings from SEC EDGAR.

**Key Functions:**

```python
@dataclass
class Holding:
    cusip: str
    name: str
    value: float       # USD
    shares: int
    type: str         # e.g., "SH", "PRN"

@dataclass
class Filing:
    cik: str
    filing_date: date
    report_date: date  # Quarter-end date
    total_value: float
    holdings_count: int
    holdings: list[Holding]

def fetch_13f_filings(cik: str, start_date: date, end_date: date) -> list[Filing]:
    """
    Fetch 13F-HR filings for a CIK from SEC EDGAR.

    - Queries EDGAR search API or company filings index
    - Parses 13F-HR XML (informationTable)
    - Computes total_13f_value = sum(holding.value)
    - Respects SEC rate limits (10 req/sec)
    - Uses SEC_USER_AGENT env var for compliance

    Returns list of Filing objects sorted by report_date.
    """
    pass

def parse_13f_xml(xml_content: str) -> Filing:
    """Parse 13F-HR XML and extract holdings."""
    pass
```

**Implementation Notes:**
- SEC EDGAR search endpoint: `https://efts.sec.gov/LATEST/search-index`
- 13F-HR XML structure: `<informationTable>` contains `<infoTable>` entries
- Each `<infoTable>` has `<cusip>`, `<nameOfIssuer>`, `<value>`, `<shrsOrPrnAmt>`
- Rate limiting: `time.sleep(1/10)` between requests
- User-Agent: Required by SEC; format: `{company} {email}`
- Handle both primary documents and amendments (use latest for each quarter)

**Test Coverage:**
- XML parsing with synthetic fixtures (valid, malformed, empty holdings)
- EDGAR URL construction
- Rate limit behavior (mock time.sleep)
- Error handling (404, timeout, XML parse errors)

---

#### 2. sensor.py — Single-Manager Exposure Sensor

**Purpose:** Compute normalized exposure metrics from 13F filings.

**Key Classes:**

```python
@dataclass
class SensorReading:
    cik: str
    name: str
    asof_quarter_end: date
    filing_date: date
    total_13f_value: float
    exposure_index: float          # 0-100
    delta_exposure: float          # Change from prior quarter
    days_since_snapshot: int
    effective_exposure: float      # Decay-adjusted
    rolling_max_5y: float

class ManagerSensor:
    def __init__(self, config: dict):
        self.window_years = config['normalization']['window_years']

    def compute_exposure_history(self, filings: list[Filing]) -> pd.DataFrame:
        """
        Compute exposure index for each filing.

        Formula:
            Max13F_5y(t) = max(Total13F over last 5 years up to t)
            ExposureIndex(t) = (Total13F(t) / Max13F_5y(t)) * 100

        Returns DataFrame with columns:
            [report_date, total_value, rolling_max, exposure_index]
        """
        pass

    def compute_delta(self, exposure_series: pd.Series) -> pd.Series:
        """Delta = Exposure(t) - Exposure(t-1)"""
        return exposure_series.diff()

    def compute_effective_exposure(
        self,
        exposure: float,
        days_since_snapshot: int,
        decay_halflife: int
    ) -> float:
        """
        Apply exponential decay to exposure.

        Formula:
            EffectiveExposure = Exposure * 0.5^(days / halflife)

        Examples:
            - days=0: no decay (factor=1.0)
            - days=halflife: 50% decay (factor=0.5)
            - days=2*halflife: 25% decay (factor=0.25)
        """
        return exposure * (0.5 ** (days_since_snapshot / decay_halflife))

    def build_sensor_reading(
        self,
        filing: Filing,
        exposure_idx: float,
        delta: float,
        days_since: int,
        config: dict
    ) -> SensorReading:
        """Construct SensorReading with all computed fields."""
        pass
```

**Implementation Notes:**
- Exposure index is clamped to [0, 100] range
- Delta can be negative (de-risking) or positive (re-risking)
- Decay function is the **most subjective parameter** — document choices
- Tactical managers (30-day halflife): positions stale after ~2 months
- Structural managers (60-day halflife): positions stale after ~4 months
- At maximum age, effective exposure approaches zero but never negative

**Test Coverage:**
- Rolling max computation (verify window behavior, edge cases at start)
- Exposure normalization (0-100 bounds, division by zero protection)
- Delta computation (sign, magnitude, NaN handling for first reading)
- Decay function (verify halflife math, boundary conditions)
- Edge cases: single filing, no filings, value=0

---

#### 3. storage.py — Persistence Layer

**Purpose:** Save/load sensor readings and DRI snapshots.

**Key Functions:**

```python
def save_sensor_history(readings: list[SensorReading], path: Path) -> None:
    """Save sensor readings to Parquet."""
    df = pd.DataFrame([asdict(r) for r in readings])
    df.to_parquet(path, index=False, compression='snappy')

def load_sensor_history(path: Path) -> list[SensorReading]:
    """Load sensor readings from Parquet."""
    df = pd.read_parquet(path)
    return [SensorReading(**row) for row in df.to_dict('records')]

def upload_to_s3(local_path: Path, bucket: str, key: str) -> None:
    """Upload file to S3 (requires boto3)."""
    pass

def download_from_s3(bucket: str, key: str, local_path: Path) -> None:
    """Download file from S3."""
    pass
```

**S3 Path Structure:**
```
s3://{bucket}/dri/sensors/{cik}/{quarter_end_date}.parquet
s3://{bucket}/dri/snapshots/{asof_date}.parquet
s3://{bucket}/dri/latest.parquet
```

**Test Coverage:**
- Parquet roundtrip (write → read → verify)
- S3 upload/download (mocked via moto or similar)
- Path construction
- Error handling (missing files, permission errors)

---

#### 4. CLI for Phase 1

```bash
# Fetch 13F filings for a manager
dri sensor fetch <cik> --quarters 8 --output data/

# Compute exposure history from fetched filings
dri sensor compute <cik> --input data/ --output data/

# Show latest sensor reading
dri sensor show <cik> --format table|json

# Example output (table format):
# CIK          Name                     Quarter      Filing      Exposure  Delta   Days Since
# 0001536411   Duquesne Family Office   2025-09-30   2025-11-14  87.3      -5.2    87
```

**Implementation Notes:**
- Use `argparse` for CLI (consistent with market-state-detector)
- Support `--config path/to/config.yaml` override
- Use `rich` or `tabulate` for table formatting (optional)
- JSON output follows `SensorReading` schema exactly

---

## Phase 2: Multi-Manager DRI Aggregation

### Overview

Compose multiple `ManagerSensor` outputs into the DRI multi-manager regime indicator. Implements the aggregation and regime classification logic from the [DRI specification](discretionary_risk_index_dri_multi_manager_regime_indicator.md).

### Components

#### 5. aggregator.py — DRI Panel Aggregation

**Purpose:** Aggregate sensor readings from panel members into DRI metrics.

**Key Classes:**

```python
@dataclass
class DRISnapshot:
    asof_date: date
    median_effective_exposure: float
    median_delta: float
    dispersion: float              # stddev
    dispersion_spread: float       # max - min (robustness check)
    regime_state: str              # RegimeState enum value
    panel_members: list[str]       # CIK list
    companion_signals: dict        # Reserved for future (JGB yield, etc.)

class DRIAggregator:
    def __init__(self, config: dict):
        self.regime_config = config['regime']

    def compute_median_exposure(self, readings: list[SensorReading]) -> float:
        """Median of effective_exposure across panel members."""
        exposures = [r.effective_exposure for r in readings]
        return float(np.median(exposures))

    def compute_median_delta(self, readings: list[SensorReading]) -> float:
        """Median of delta_exposure across panel members."""
        deltas = [r.delta_exposure for r in readings]
        return float(np.median(deltas))

    def compute_dispersion(self, readings: list[SensorReading]) -> tuple[float, float]:
        """
        Compute dispersion metrics.

        Returns:
            (stddev, max-min spread)

        Note: With 4-7 panel members, stddev is noisy.
        Use directional trend (rising/falling) rather than absolute thresholds.
        """
        exposures = [r.effective_exposure for r in readings]
        return float(np.std(exposures)), float(np.max(exposures) - np.min(exposures))

    def aggregate(self, readings: list[SensorReading], asof_date: date) -> DRISnapshot:
        """Compute all aggregation metrics."""
        pass
```

**Implementation Notes:**
- Requires at least 4 panel members (configurable minimum)
- Handle missing readings (one manager's filing delayed): skip that manager or use last-known with increased decay
- Dispersion trend requires comparing to previous snapshot
- All metrics operate on `effective_exposure` (decay-adjusted), not raw exposure

**Test Coverage:**
- Median computation (odd/even panel sizes, outliers)
- Dispersion calculation (verify stddev formula, spread matches max-min)
- Edge cases: 4 managers (minimum), 7 managers (maximum), all equal values, one missing
- Partial failures (missing filing handling)

---

#### 6. regime.py — Regime Classification

**Purpose:** Map DRI metrics to regime states using threshold rules.

**Key Components:**

```python
class RegimeState(Enum):
    RISK_ON = "Risk ON"
    RISK_ON_FRAGILE = "Risk ON (fragile)"
    TRANSITION = "Transition"
    RISK_OFF = "Risk OFF"
    PANIC_RESET = "Panic / Reset"

class RegimeClassifier:
    def __init__(self, config: dict):
        self.high_exp = config['regime']['high_exposure']
        self.low_exp = config['regime']['low_exposure']
        self.high_disp = config['regime']['high_dispersion']
        self.disp_rising = config['regime']['dispersion_rising_threshold']
        self.fast_contract = config['regime']['fast_contraction_delta']

    def classify(
        self,
        median_exp: float,
        median_delta: float,
        dispersion: float,
        prev_dispersion: float | None
    ) -> RegimeState:
        """
        Classify regime using threshold rules.

        Logic (from DRI spec Section 5/7):

        1. Panic / Reset:
           - Fast contraction: median_delta < fast_contraction_delta
           - AND dispersion spike: dispersion > high_disp

        2. Risk OFF:
           - Low median: median_exp < low_exp
           - AND low dispersion: dispersion < high_disp

        3. Transition:
           - Falling median: median_exp declining
           - AND high dispersion: dispersion > high_disp

        4. Risk ON (fragile):
           - High median: median_exp > high_exp
           - AND rising dispersion: dispersion - prev_dispersion > disp_rising

        5. Risk ON:
           - High median: median_exp > high_exp
           - AND low dispersion: dispersion < high_disp

        Priority: Check in order 1→5, return first match.
        """
        pass
```

**Default Thresholds (calibrated for 0-1 scale):**
- `high_exposure`: 0.65 (managers carrying >65% of max risk)
- `low_exposure`: 0.35 (managers below 35% of max risk)
- `high_dispersion`: 0.15 (stddev > 15% indicates disagreement)
- `dispersion_rising_threshold`: 0.03 (3% increase = rising)
- `fast_contraction_delta`: -0.15 (15% drop = panic)

**Implementation Notes:**
- Thresholds are **subjective** — document reasoning in PHILOSOPHY.md
- Regime classifier is **stateful** (needs prev_dispersion for trends)
- Priority order matters — panic detection overrides other states
- For first reading (no history), `prev_dispersion = None` → skip trend checks

**Test Coverage:**
- All 5 regime states (construct inputs that trigger each)
- Boundary conditions (exactly at threshold values)
- Priority order (verify panic overrides risk_off if both match)
- First-reading edge case (no prior dispersion)

---

#### 7. pipeline.py — End-to-End Orchestrator

**Purpose:** Coordinate the full DRI computation pipeline.

**Key Functions:**

```python
class DRIPipeline:
    def __init__(self, config: dict):
        self.config = config
        self.sensors = {}  # cik -> ManagerSensor
        self.aggregator = DRIAggregator(config)
        self.classifier = RegimeClassifier(config)

    def run(self, asof_date: date) -> DRISnapshot:
        """
        Execute full DRI pipeline.

        Steps:
        1. For each panel member:
           a. Fetch 13F filings (if not cached)
           b. Compute exposure history
           c. Build current sensor reading
        2. Aggregate all sensor readings
        3. Classify regime
        4. Store results

        Returns DRISnapshot.
        """
        readings = []

        for panel_member in self.config['panel']:
            cik = panel_member['cik']

            try:
                # Fetch/load filings
                filings = self._load_or_fetch_filings(cik, asof_date)

                # Compute sensor reading
                sensor = ManagerSensor(self.config)
                reading = sensor.build_sensor_reading(
                    filings[-1],  # Latest filing
                    # ... other params
                )
                readings.append(reading)

            except Exception as e:
                # Log warning but continue (partial panel is OK)
                logger.warning(f"Failed to process {cik}: {e}")

        if len(readings) < 4:
            raise ValueError(f"Insufficient panel members: {len(readings)} < 4")

        # Aggregate
        snapshot = self.aggregator.aggregate(readings, asof_date)

        # Classify regime
        prev_snapshot = self._load_previous_snapshot()
        prev_disp = prev_snapshot.dispersion if prev_snapshot else None
        snapshot.regime_state = self.classifier.classify(
            snapshot.median_effective_exposure,
            snapshot.median_delta,
            snapshot.dispersion,
            prev_disp
        )

        # Store
        self._save_snapshot(snapshot)

        return snapshot
```

**Implementation Notes:**
- Graceful degradation: log failures but continue with remaining panel
- Minimum 4 readings required (configurable)
- Cache filings locally to avoid re-fetching
- Store both per-sensor Parquet AND aggregated snapshot
- Support dry-run mode for testing

**Test Coverage:**
- Full pipeline integration test (mocked EDGAR responses)
- Partial failure handling (one manager missing)
- Insufficient panel error (3 managers)
- Cache behavior (fetch vs. load)
- Dry-run mode (validates but doesn't persist)

---

#### 8. CLI for Phase 2

```bash
# Run full DRI pipeline
dri run --config config/default_config.yaml

# Show latest DRI snapshot
dri show --format table|json

# Show regime history
dri history --since 2024-01-01

# Example output (show command):
# DRI Snapshot — 2026-02-09
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Regime:                Risk ON (fragile)
# Median Exposure:       72.3%
# Median Delta:          -3.1%
# Dispersion:            0.14 (↑ from 0.11)
# Panel Members:         4
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Example output (history command):
# Date         Regime            Med Exp   Dispersion
# 2025-09-30   Risk ON           87.2      0.09
# 2025-12-31   Risk ON (fragile) 84.1      0.12
# 2026-03-31   Transition        65.3      0.18
```

**Implementation Notes:**
- `dri run` supports `--dry-run` (validate without storing)
- `dri show` uses `rich` for formatted terminal output
- `dri history` loads all snapshots and displays timeline
- JSON output matches `DRISnapshot` schema exactly

---

## Phase 2.5: Automation

### 9. GitHub Actions Workflow

**File:** `.github/workflows/compute-dri.yml`

```yaml
name: Compute DRI

on:
  schedule:
    # Run monthly on 20th (13F filings due ~45 days after quarter-end)
    - cron: '0 4 20 * *'
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  compute-dri:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[s3]"

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - name: Run DRI pipeline
        env:
          SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}
        run: |
          dri run --config config/default_config.yaml

      - name: Upload to S3
        run: |
          aws s3 sync data/ s3://${{ secrets.S3_BUCKET }}/dri/ --exclude "*" --include "*.parquet"
```

**Secrets Required:**
- `AWS_ROLE_ARN`: OIDC role for GitHub Actions
- `S3_BUCKET`: Target S3 bucket
- `SEC_USER_AGENT`: SEC-compliant User-Agent string

**Trigger Logic:**
- Monthly cron on 20th of each month (13F filings due ~Feb 14, May 15, Aug 14, Nov 14)
- Manual trigger via `workflow_dispatch`

---

### 10. CloudFormation Infrastructure

**File:** `infra/cloudformation-template.yaml`

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: DRI Infrastructure — S3 bucket and IAM role for GitHub Actions

Parameters:
  GitHubOrg:
    Type: String
    Default: hoppefamily
  GitHubRepo:
    Type: String
    Default: dri

Resources:
  DRIBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${AWS::StackName}-dri-data'
      VersioningConfiguration:
        Status: Enabled
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  GitHubActionsRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Federated: !Sub 'arn:aws:iam::${AWS::AccountId}:oidc-provider/token.actions.githubusercontent.com'
            Action: 'sts:AssumeRoleWithWebIdentity'
            Condition:
              StringEquals:
                'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com'
              StringLike:
                'token.actions.githubusercontent.com:sub': !Sub 'repo:${GitHubOrg}/${GitHubRepo}:*'
      Policies:
        - PolicyName: DRIDataAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - 's3:PutObject'
                  - 's3:GetObject'
                  - 's3:ListBucket'
                Resource:
                  - !GetAtt DRIBucket.Arn
                  - !Sub '${DRIBucket.Arn}/*'

Outputs:
  BucketName:
    Value: !Ref DRIBucket
  RoleArn:
    Value: !GetAtt GitHubActionsRole.Arn
```

**Deployment:**
```bash
aws cloudformation create-stack \
  --stack-name dri-infrastructure \
  --template-body file://infra/cloudformation-template.yaml \
  --capabilities CAPABILITY_IAM
```

---

## Testing Strategy

### Unit Tests (Phase 1)

**test_edgar.py:**
- XML parsing (valid, malformed, empty, multiple holdings)
- EDGAR URL construction and query parameters
- Rate limiting behavior (mock time.sleep)
- Error handling (404, timeout, XML parse errors, network errors)
- CIK padding (SEC requires 10-digit CIKs with leading zeros)

**test_sensor.py:**
- Rolling max computation (window behavior, edge at start of history)
- Exposure normalization (0-100 bounds, handles division by zero)
- Delta computation (positive/negative signs, NaN for first reading)
- Decay function (verify exponential formula, halflife behavior, boundaries)
- Edge cases: single filing, no filings, value=0, max value at boundary

**test_storage.py:**
- Parquet roundtrip (write → read → verify all fields preserved)
- S3 upload/download (mocked with moto)
- Path construction (verify S3 key format)
- Error handling (missing files, permissions, corrupted Parquet)

### Unit Tests (Phase 2)

**test_aggregator.py:**
- Median computation (odd/even panel sizes, handles outliers correctly)
- Dispersion metrics (stddev formula, spread = max - min)
- Edge cases: 4 managers (minimum), 7 managers (maximum suggested)
- All managers at same exposure (dispersion = 0)
- One manager missing (partial panel)

**test_regime.py:**
- All 5 regime states triggered by appropriate inputs
- Boundary conditions (exactly at threshold values)
- Priority order (panic overrides risk_off if both conditions match)
- First reading edge case (no prior dispersion available)
- Threshold sensitivity (verify small changes don't cause flapping)

**test_pipeline.py:**
- Full pipeline integration (mocked EDGAR responses)
- Partial failure handling (one manager's filing missing/delayed)
- Insufficient panel error (fewer than 4 managers)
- Cache behavior (avoids re-fetching existing data)
- Dry-run mode (validates but doesn't persist)

### Test Fixtures

**fixtures/sample_13f.xml:**
```xml
<edgarSubmission>
  <formData>
    <coverPage>...</coverPage>
    <signatureBlock>...</signatureBlock>
    <summaryPage>...</summaryPage>
    <documents>
      <document>
        <informationTable>
          <infoTable>
            <nameOfIssuer>Apple Inc.</nameOfIssuer>
            <titleOfClass>COM</titleOfClass>
            <cusip>037833100</cusip>
            <value>150000</value>
            <shrsOrPrnAmt>
              <sshPrnamt>1000</sshPrnamt>
              <sshPrnamtType>SH</sshPrnamtType>
            </shrsOrPrnAmt>
          </infoTable>
          <!-- More holdings... -->
        </informationTable>
      </document>
    </documents>
  </formData>
</edgarSubmission>
```

### Coverage Requirements

- **Minimum:** 80% line coverage across all modules
- **Critical paths:** 100% coverage for regime classification logic
- **Integration:** At least one full end-to-end test with realistic data

---

## Manual Verification

### 1. Validate EDGAR Data Fetching

**Known CIK:** Stanley Druckenmiller's Duquesne Family Office = `0001536411`

```bash
# Fetch Q3 2025 filing
dri sensor fetch 0001536411 --quarters 1

# Verify output against EDGAR manual check:
# https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001536411&type=13F-HR&dateb=&owner=exclude&count=40

# Compare:
# - Filing date
# - Total 13F value
# - Number of holdings
```

### 2. Validate Exposure Calculation

Using historical data for a known manager:
- Q3 2024: $X million
- Q4 2024: $Y million
- Q1 2025: $Z million

**Expected:**
- Max over 5 years = max(all quarters back to Q1 2020)
- Exposure Q1 2025 = (Z / Max) * 100
- Delta Q1 2025 = Exposure Q1 2025 - Exposure Q4 2024

### 3. Validate Regime Classification

**Construct synthetic panel data:**

| Manager | Effective Exposure |
|---------|-------------------|
| A       | 0.85              |
| B       | 0.82              |
| C       | 0.79              |
| D       | 0.88              |

**Expected:**
- Median = 0.835
- Dispersion (stddev) ≈ 0.038
- With default thresholds: `high_exposure=0.65`, `high_dispersion=0.15`
  → Regime = **Risk ON** (high median, low dispersion)

---

## Initial Panel Selection

### Research Required

Identify 4-7 discretionary macro managers meeting criteria:
1. Discretionary (human judgment, not quant)
2. Willing to go materially risk-off (not perma-bulls)
3. Macro-aware (rates/FX/policy sensitive)
4. Observable via consistent 13F history
5. **Likely to respond to sovereign/rate stress** (per DRI V2)

### Candidates to Research

| Name | Firm | CIK | Notes |
|------|------|-----|-------|
| Stanley Druckenmiller | Duquesne Family Office | 0001536411 | Confirmed macro-aware, risk-off capable |
| Ray Dalio | Bridgewater Associates | ??? | Macro fund, but large AUM may include systematic |
| Paul Tudor Jones | Tudor Investment Corp | ??? | Discretionary macro, commodities-aware |
| ... | ... | ... | **4-7 total required** |

**Action Item:** Research SEC EDGAR for suitable managers, validate:
- 13F filing consistency (quarterly, no gaps)
- Evidence of risk-off periods (exposure variability)
- Public statements indicating macro/rates focus

---

## Future Enhancements (Post-MVP)

### Dashboard Integration

**Streamlit Page:** Add `dri_page.py` to `market-flow-dashboard`:
- Timeline chart showing regime transitions
- Panel member exposure table (current + historical)
- Dispersion trend chart
- JGB yield overlay (when implemented)

**Data Loading:** Extend `StateRecorder` to read DRI snapshots from S3/SQLite.

### iOS App Integration

**S3 Structure:** Add `dri-states/{date}.json` to the existing S3 hierarchy:
```json
{
  "asof_date": "2026-02-09",
  "regime_state": "Risk ON (fragile)",
  "median_effective_exposure": 0.723,
  "dispersion": 0.14,
  "panel_count": 4
}
```

**Swift Model:** Add `DRIState` struct to iOS app, display in a new summary card.

### JGB Yield Integration

**Daily Fetcher:** Add `src/dri/companions/jgb_yield.py`:
- Scrape TradingEconomics or Investing.com
- Store daily JGB 30-year yield in `jgb_daily.parquet`
- Add `jgb_30y_yield_at_snapshot` to `DRISnapshot`

**Decision Framework:** Implement V2 Section 8 decision table as a CLI command:
```bash
dri recommend --jgb-yield 3.45
# Output: JGB 3-4% rising + Risk ON (fragile) → Trim to 70% equity
```

### Duration Tilt (Optional)

**Per V1 Section 2.2:** Add equity duration measurement:
- Fetch valuation data (FCF yield, P/E) for holdings
- Compute portfolio-weighted duration tilt
- Add `equity_duration_index` to `SensorReading`
- Expose in aggregated DRI snapshot

### Alerts & Monitoring

**Regime Change Alerts:**
- Detect transition from Risk ON → Risk ON (fragile)
- Send notification (email, Slack, Discord webhook)
- GitHub Actions workflow: `on: schedule` + alert logic

**Dispersion Spike Detection:**
- Alert when dispersion increases by >5% in one quarter
- Indicates belief strain building

---

## Documentation

### README.md

```markdown
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

# Fetch 13F data for panel members
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

## Documentation

- [docs/PHILOSOPHY.md](docs/PHILOSOPHY.md) — Design rationale and limitations
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — This document
```

### PHILOSOPHY.md

Key sections:
- Why 13F data (limitations and advantages)
- Why dispersion matters (belief strain > price action)
- Why no AUM weighting (each manager = one sensor)
- Decay function subjectivity (document calibration reasoning)
- Known failure modes (derivatives, fast shocks, policy suppression)
- Relationship to single-manager sensor building block

---

## Timeline & Milestones

### Week 1-2: Phase 1 (Sensor)
- [ ] Project scaffolding (pyproject.toml, config, structure)
- [ ] Implement `edgar.py` with XML parsing
- [ ] Implement `sensor.py` with exposure normalization
- [ ] Write unit tests (test_edgar, test_sensor)
- [ ] Manual validation against known CIK

### Week 3-4: Phase 2 (Aggregator)
- [ ] Implement `aggregator.py` with median/dispersion
- [ ] Implement `regime.py` with classification logic
- [ ] Implement `pipeline.py` orchestrator
- [ ] Write unit tests (test_aggregator, test_regime, test_pipeline)
- [ ] Integration test with synthetic panel data

### Week 5: Automation & Verification
- [ ] GitHub Actions workflow
- [ ] CloudFormation template for S3 + IAM
- [ ] Deploy infrastructure
- [ ] Run against Q4 2025 filings (due mid-Feb 2026)
- [ ] Document initial DRI reading

### Week 6: Polish & Documentation
- [ ] Complete README.md and PHILOSOPHY.md
- [ ] Add code comments and docstrings
- [ ] Coverage report (target 80%+)
- [ ] Release v0.1.0

---

## Success Criteria

1. **Functional:** CLI successfully processes Q4 2025 13F filings for 4+ managers
2. **Validated:** Sensor readings match hand-checked EDGAR data within 1%
3. **Regime Classification:** Produces a valid regime state (one of 5 defined)
4. **Stored:** Outputs Parquet files with correct schema
5. **Automated:** GitHub Actions workflow runs successfully
6. **Tested:** 80%+ code coverage with passing tests
7. **Documented:** README explains usage, PHILOSOPHY explains design

---

## Open Questions

1. **Panel composition:** Final list of 4-7 managers (requires EDGAR research)
2. **Decay calibration:** Validate 30-day (tactical) vs 60-day (structural) halflife assumptions
3. **Dispersion metric:** Confirm stddev is sufficient for 4-7 managers, or use IQR/spread
4. **Threshold values:** Validate default regime thresholds against historical data
5. **S3 bucket naming:** Confirm AWS account and bucket naming convention
6. **SEC User-Agent:** Format for compliance: `{company_name} {email}`

---

## References

- **DRI Specification:** [discretionary_risk_index_dri_multi_manager_regime_indicator.md](discretionary_risk_index_dri_multi_manager_regime_indicator.md)
- **DRI V2 (Japan use case):** [../../trading/trading-ideas/discretionary_risk_index_dri_v2.md](../../trading/trading-ideas/discretionary_risk_index_dri_v2.md)
- **Single-Manager Sensor Plan:** [../../trading/trading-ideas/druckenmiller_sensor_corrected_open_source_plan.md](../../trading/trading-ideas/druckenmiller_sensor_corrected_open_source_plan.md)
- **SEC EDGAR 13F Documentation:** https://www.sec.gov/divisions/investment/13ffaq.htm
- **Existing Ecosystem Patterns:**
  - [market-state-detector](../../market-state-detector/) — Config, CLI, testing patterns
  - [flow-state-monitor](../../flow-state-monitor/) — Provider pattern, S3 storage
  - [ibkr-borrow-collector](../../ibkr-borrow-collector/) — GitHub Actions, CloudFormation

---

**Next Action:** Begin Phase 0 — create `dri` repository and scaffold project structure.
