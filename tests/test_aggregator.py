"""Tests for DRI aggregation."""
from datetime import date

import numpy as np
import pytest
from dri.aggregator import DRIAggregator


def test_compute_median_exposure(test_config, sample_panel_readings):
    """Test median exposure computation."""
    aggregator = DRIAggregator(test_config)

    median = aggregator.compute_median_exposure(sample_panel_readings)

    # Hand-calculated median of [0.75, 0.82, 0.68, 0.79]
    expected = np.median([0.75, 0.82, 0.68, 0.79])
    assert median == pytest.approx(expected, abs=0.001)


def test_compute_median_delta(test_config, sample_panel_readings):
    """Test median delta computation."""
    aggregator = DRIAggregator(test_config)

    median_delta = aggregator.compute_median_delta(sample_panel_readings)

    # Hand-calculated median of [-3.0, -2.5, -5.0, -1.0]
    expected = np.median([-3.0, -2.5, -5.0, -1.0])
    assert median_delta == pytest.approx(expected, abs=0.001)


def test_compute_dispersion(test_config, sample_panel_readings):
    """Test dispersion computation."""
    aggregator = DRIAggregator(test_config)

    stddev, spread = aggregator.compute_dispersion(sample_panel_readings)

    # Check stddev
    exposures = [0.75, 0.82, 0.68, 0.79]
    expected_std = np.std(exposures, ddof=1)  # Sample stddev
    assert stddev == pytest.approx(expected_std, abs=0.001)

    # Check spread (max - min)
    expected_spread = max(exposures) - min(exposures)
    assert spread == pytest.approx(expected_spread, abs=0.001)


def test_aggregate_full(test_config, sample_panel_readings):
    """Test full aggregation."""
    aggregator = DRIAggregator(test_config)

    snapshot = aggregator.aggregate(
        readings=sample_panel_readings,
        asof_date=date(2025, 9, 30),
        regime_state="Risk ON",
    )

    # Check all fields are populated
    assert snapshot.asof_date == date(2025, 9, 30)
    assert 0 <= snapshot.median_effective_exposure <= 1
    assert snapshot.dispersion >= 0
    assert snapshot.dispersion_spread >= 0
    assert snapshot.regime_state == "Risk ON"
    assert len(snapshot.panel_members) == 4


def test_aggregate_insufficient_panel(test_config, sample_panel_readings):
    """Test aggregation with insufficient panel size."""
    aggregator = DRIAggregator(test_config)

    # Only use 3 readings (below minimum of 4)
    with pytest.raises(ValueError, match="Insufficient panel members"):
        aggregator.aggregate(
            readings=sample_panel_readings[:3],
            asof_date=date(2025, 9, 30),
        )


def test_dispersion_all_equal(test_config, sample_sensor_reading):
    """Test dispersion when all managers have identical exposure."""
    aggregator = DRIAggregator(test_config)

    # Create 4 identical readings
    identical_readings = [sample_sensor_reading] * 4

    stddev, spread = aggregator.compute_dispersion(identical_readings)

    # Both should be zero (no dispersion)
    assert stddev == pytest.approx(0.0, abs=0.001)
    assert spread == pytest.approx(0.0, abs=0.001)


def test_median_with_nan_deltas(test_config, sample_panel_readings):
    """Test median delta computation with NaN values (first readings)."""
    aggregator = DRIAggregator(test_config)

    # Set some deltas to NaN
    sample_panel_readings[0].delta_exposure = float('nan')
    sample_panel_readings[1].delta_exposure = float('nan')

    median_delta = aggregator.compute_median_delta(sample_panel_readings)

    # Should compute median of remaining non-NaN values
    expected = np.median([-5.0, -1.0])
    assert median_delta == pytest.approx(expected, abs=0.001)
