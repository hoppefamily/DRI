"""Multi-manager DRI aggregation."""
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import numpy as np

from .sensor import SensorReading

logger = logging.getLogger(__name__)


@dataclass
class DRISnapshot:
    """A DRI regime snapshot at a point in time."""
    asof_date: date
    median_effective_exposure: float
    median_delta: float
    dispersion: float              # stddev
    dispersion_spread: float       # max - min (robustness check)
    regime_state: str              # RegimeState enum value
    panel_members: List[str]       # CIK list
    sensor_readings: List[SensorReading] = field(default_factory=list)  # Individual manager readings
    companion_signals: Optional[Dict] = None  # Reserved for future (JGB yield, etc.)


class DRIAggregator:
    """Aggregate sensor readings from panel members into DRI metrics."""

    def __init__(self, config: dict):
        """Initialize with configuration."""
        self.config = config
        self.min_panel_size = config["regime"]["min_panel_members"]

    def compute_median_exposure(self, readings: List[SensorReading]) -> float:
        """
        Compute median of effective_exposure across panel members.

        Returns:
            Median effective exposure (0-1 scale)
        """
        exposures = [r.effective_exposure for r in readings]
        return float(np.median(exposures))

    def compute_median_delta(self, readings: List[SensorReading]) -> float:
        """
        Compute median of delta_exposure across panel members.

        Returns:
            Median delta exposure
        """
        deltas = [r.delta_exposure for r in readings]
        # Filter out NaN values (first readings)
        deltas = [d for d in deltas if not np.isnan(d)]
        if not deltas:
            return 0.0
        return float(np.median(deltas))

    def compute_dispersion(self, readings: List[SensorReading]) -> tuple:
        """
        Compute dispersion metrics.

        Returns:
            Tuple of (stddev, max-min spread)

        Note: With 4-7 panel members, stddev is noisy.
        Use directional trend (rising/falling) rather than absolute thresholds.
        """
        exposures = [r.effective_exposure for r in readings]

        stddev = float(np.std(exposures, ddof=1))  # Sample stddev
        spread = float(np.max(exposures) - np.min(exposures))

        return stddev, spread

    def aggregate(
        self,
        readings: List[SensorReading],
        asof_date: date,
        regime_state: Optional[str] = None,
    ) -> DRISnapshot:
        """
        Compute all aggregation metrics.

        Args:
            readings: List of SensorReading objects (one per panel member)
            asof_date: Date of this snapshot
            regime_state: Pre-computed regime state (or None to skip)

        Returns:
            DRISnapshot object
        """
        # Validate panel size
        if len(readings) < self.min_panel_size:
            raise ValueError(
                f"Insufficient panel members: {len(readings)} < {self.min_panel_size}"
            )

        # Compute metrics
        median_exp = self.compute_median_exposure(readings)
        median_delta = self.compute_median_delta(readings)
        dispersion, spread = self.compute_dispersion(readings)

        # Get panel member CIKs
        panel_ciks = [r.cik for r in readings]

        # Log metrics
        logger.info(
            f"DRI Aggregation for {asof_date}: "
            f"median_exp={median_exp:.3f}, "
            f"median_delta={median_delta:.3f}, "
            f"dispersion={dispersion:.3f}, "
            f"spread={spread:.3f}"
        )

        return DRISnapshot(
            asof_date=asof_date,
            median_effective_exposure=median_exp,
            median_delta=median_delta,
            dispersion=dispersion,
            dispersion_spread=spread,
            regime_state=regime_state or "Unknown",
            panel_members=panel_ciks,
            sensor_readings=readings,
            companion_signals=None,
        )
