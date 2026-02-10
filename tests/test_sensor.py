"""Tests for sensor module."""
from datetime import date

import pandas as pd
import pytest
from dri.sensor import ManagerSensor


def test_compute_exposure_history_rolling_max(test_config, sample_filings_sequence):
    """Test exposure history computation with rolling max."""
    sensor = ManagerSensor(test_config)

    exposure_history = sensor.compute_exposure_history(sample_filings_sequence)

    # Check DataFrame structure
    assert not exposure_history.empty
    assert "exposure_index" in exposure_history.columns
    assert "rolling_max" in exposure_history.columns

    # Check exposure bounds (0-100)
    assert (exposure_history["exposure_index"] >= 0).all()
    assert (exposure_history["exposure_index"] <= 100).all()

    # Check that max value gets 100% exposure
    max_value = exposure_history["total_value"].max()
    max_row = exposure_history[exposure_history["total_value"] == max_value]
    assert max_row["exposure_index"].iloc[0] == 100.0


def test_compute_delta(test_config, sample_filings_sequence):
    """Test delta computation."""
    sensor = ManagerSensor(test_config)

    exposure_history = sensor.compute_exposure_history(sample_filings_sequence)
    deltas = sensor.compute_delta(exposure_history["exposure_index"])

    # First value should be NaN
    assert pd.isna(deltas.iloc[0])

    # Check delta signs (should match direction of change)
    for i in range(1, len(exposure_history)):
        prev_exp = exposure_history["exposure_index"].iloc[i-1]
        curr_exp = exposure_history["exposure_index"].iloc[i]
        expected_delta = curr_exp - prev_exp
        assert abs(deltas.iloc[i] - expected_delta) < 0.01


def test_compute_effective_exposure_no_decay(test_config):
    """Test effective exposure with no decay (0 days)."""
    sensor = ManagerSensor(test_config)

    effective = sensor.compute_effective_exposure(
        exposure=80.0,
        days_since_snapshot=0,
        decay_halflife=30,
    )

    # Should equal original (converted to 0-1 scale)
    assert effective == pytest.approx(0.80, abs=0.001)


def test_compute_effective_exposure_one_halflife(test_config):
    """Test effective exposure after one half-life."""
    sensor = ManagerSensor(test_config)

    effective = sensor.compute_effective_exposure(
        exposure=80.0,
        days_since_snapshot=30,
        decay_halflife=30,
    )

    # Should be half of original
    assert effective == pytest.approx(0.40, abs=0.001)


def test_compute_effective_exposure_two_halflifes(test_config):
    """Test effective exposure after two half-lives."""
    sensor = ManagerSensor(test_config)

    effective = sensor.compute_effective_exposure(
        exposure=80.0,
        days_since_snapshot=60,
        decay_halflife=30,
    )

    # Should be quarter of original
    assert effective == pytest.approx(0.20, abs=0.001)


def test_build_sensor_history(test_config, sample_filings_sequence):
    """Test building complete sensor history."""
    sensor = ManagerSensor(test_config)

    readings = sensor.build_sensor_history(
        cik="0001536411",
        name="Test Manager",
        filings=sample_filings_sequence,
        decay_halflife=30,
    )

    # Should have one reading per filing
    assert len(readings) == len(sample_filings_sequence)

    # Check readings have required fields
    for reading in readings:
        assert reading.cik == "0001536411"
        assert reading.name == "Test Manager"
        assert 0 <= reading.effective_exposure <= 1
        assert reading.exposure_index >= 0
        assert reading.days_since_snapshot == 0  # Historical readings use report_date


def test_exposure_normalization_edge_case_single_filing(test_config, sample_filing):
    """Test exposure with only one filing."""
    sensor = ManagerSensor(test_config)

    exposure_history = sensor.compute_exposure_history([sample_filing])

    # Single filing should get 100% exposure (it's the max)
    assert len(exposure_history) == 1
    assert exposure_history["exposure_index"].iloc[0] == 100.0


def test_exposure_normalization_all_equal(test_config):
    """Test exposure when all filings have same value."""
    from dri.edgar import Filing

    sensor = ManagerSensor(test_config)

    # Create filings with identical values
    filings = [
        Filing(
            cik="0001536411",
            filing_date=date(2025, 11, 14),
            report_date=date(2025, 9, 30) - pd.DateOffset(months=3*i),
            total_value=100000,
            holdings_count=10,
            holdings=[],
        )
        for i in range(4)
    ]

    exposure_history = sensor.compute_exposure_history(filings)

    # All should be 100% (all equal to max)
    assert (exposure_history["exposure_index"] == 100.0).all()
