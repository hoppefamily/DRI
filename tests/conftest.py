"""Pytest configuration and shared fixtures."""
from datetime import date, timedelta

import pytest
from dri.edgar import Filing, Holding
from dri.sensor import SensorReading


@pytest.fixture
def sample_holdings():
    """Sample holdings for testing."""
    return [
        Holding(cusip="037833100", name="Apple Inc.", value=150000, shares=1000, type="SH"),
        Holding(cusip="594918104", name="Microsoft Corp", value=120000, shares=800, type="SH"),
        Holding(cusip="30303M102", name="Meta Platforms", value=80000, shares=500, type="SH"),
    ]


@pytest.fixture
def sample_filing(sample_holdings):
    """Sample 13F filing for testing."""
    return Filing(
        cik="0001536411",
        filing_date=date(2025, 11, 14),
        report_date=date(2025, 9, 30),
        total_value=sum(h.value for h in sample_holdings),
        holdings_count=len(sample_holdings),
        holdings=sample_holdings,
    )


@pytest.fixture
def sample_filings_sequence():
    """Sequence of filings with varying values for exposure testing."""
    base_date = date(2024, 12, 31)
    values = [100000, 150000, 200000, 180000, 220000, 250000, 230000, 240000]

    filings = []
    for i, value in enumerate(values):
        quarter_date = base_date - timedelta(days=90 * (len(values) - i - 1))
        filing_date = quarter_date + timedelta(days=45)

        filings.append(Filing(
            cik="0001536411",
            filing_date=filing_date,
            report_date=quarter_date,
            total_value=value,
            holdings_count=10,
            holdings=[],
        ))

    return filings


@pytest.fixture
def sample_sensor_reading():
    """Sample sensor reading for testing."""
    return SensorReading(
        cik="0001536411",
        name="Test Manager",
        asof_quarter_end=date(2025, 9, 30),
        filing_date=date(2025, 11, 14),
        total_13f_value=350000,
        exposure_index=87.5,
        delta_exposure=-5.2,
        days_since_snapshot=45,
        effective_exposure=0.78,
        rolling_max_5y=400000,
    )


@pytest.fixture
def sample_panel_readings():
    """Sample panel of sensor readings for aggregation testing."""
    base_reading = SensorReading(
        cik="0000000001",
        name="Manager 1",
        asof_quarter_end=date(2025, 9, 30),
        filing_date=date(2025, 11, 14),
        total_13f_value=350000,
        exposure_index=85.0,
        delta_exposure=-3.0,
        days_since_snapshot=45,
        effective_exposure=0.75,
        rolling_max_5y=400000,
    )

    # Create 4 managers with varying exposures
    readings = []
    exposures = [0.75, 0.82, 0.68, 0.79]
    deltas = [-3.0, -2.5, -5.0, -1.0]

    for i, (exp, delta) in enumerate(zip(exposures, deltas)):
        reading = SensorReading(
            cik=f"000000000{i+1}",
            name=f"Manager {i+1}",
            asof_quarter_end=base_reading.asof_quarter_end,
            filing_date=base_reading.filing_date,
            total_13f_value=exp * 400000,
            exposure_index=exp * 100,
            delta_exposure=delta,
            days_since_snapshot=45,
            effective_exposure=exp,
            rolling_max_5y=400000,
        )
        readings.append(reading)

    return readings


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "panel": [
            {
                "cik": "0001536411",
                "name": "Test Manager",
                "decay_type": "tactical",
                "decay_halflife_days": 30,
            }
        ],
        "normalization": {
            "window_years": 5,
            "method": "rolling_max",
        },
        "regime": {
            "high_exposure": 0.65,
            "low_exposure": 0.35,
            "high_dispersion": 0.15,
            "dispersion_rising_threshold": 0.03,
            "fast_contraction_delta": -0.15,
            "min_panel_members": 4,
        },
        "storage": {
            "output_dir": "./test_data",
            "s3_bucket": None,
            "s3_prefix": "dri",
        },
        "edgar": {
            "user_agent": "TestAgent test@example.com",
            "rate_limit_per_sec": 10,
            "retry_attempts": 3,
            "retry_delay_sec": 1,
            "base_url": "https://www.sec.gov",
        },
    }
