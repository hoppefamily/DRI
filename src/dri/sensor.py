"""Single-manager exposure sensor."""
import logging
from dataclasses import dataclass
from datetime import date
from typing import List

import pandas as pd

from .edgar import Filing

logger = logging.getLogger(__name__)


@dataclass
class SensorReading:
    """A single manager's exposure reading at a point in time."""
    cik: str
    name: str
    asof_quarter_end: date
    filing_date: date
    total_13f_value: float
    exposure_index: float          # 0-100
    delta_exposure: float          # Change from prior quarter
    days_since_snapshot: int
    effective_exposure: float      # Decay-adjusted (0-1 scale)
    rolling_max_5y: float


class ManagerSensor:
    """Compute normalized exposure metrics for a single manager."""

    def __init__(self, config: dict):
        """Initialize with configuration."""
        self.window_years = config["normalization"]["window_years"]
        self.method = config["normalization"]["method"]

    def compute_exposure_history(self, filings: List[Filing]) -> pd.DataFrame:
        """
        Compute exposure index for each filing.

        Formula:
            Max13F_5y(t) = max(Total13F over last 5 years up to t)
            ExposureIndex(t) = (Total13F(t) / Max13F_5y(t)) * 100

        Returns:
            DataFrame with columns: [report_date, total_value, rolling_max, exposure_index]
        """
        if not filings:
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame([{
            "report_date": f.report_date,
            "filing_date": f.filing_date,
            "total_value": f.total_value,
        } for f in filings])

        df = df.sort_values("report_date").reset_index(drop=True)

        # Compute rolling max
        if self.method == "rolling_max":
            # Rolling max over window_years
            window_quarters = self.window_years * 4
            df["rolling_max"] = df["total_value"].rolling(
                window=window_quarters,
                min_periods=1,
            ).max()
        elif self.method == "full_history_max":
            # Expanding max (full history)
            df["rolling_max"] = df["total_value"].expanding().max()
        else:
            raise ValueError(f"Unknown normalization method: {self.method}")

        # Compute exposure index (0-100)
        df["exposure_index"] = (df["total_value"] / df["rolling_max"]) * 100
        df["exposure_index"] = df["exposure_index"].clip(0, 100)

        return df

    def compute_delta(self, exposure_series: pd.Series) -> pd.Series:
        """
        Compute delta (change from prior quarter).

        Returns:
            Series with delta values (NaN for first reading)
        """
        return exposure_series.diff()

    def compute_effective_exposure(
        self,
        exposure: float,
        days_since_snapshot: int,
        decay_halflife: int,
    ) -> float:
        """
        Apply exponential decay to exposure.

        Formula:
            EffectiveExposure = Exposure * 0.5^(days / halflife)

        Args:
            exposure: Raw exposure index (0-100)
            days_since_snapshot: Days elapsed since filing report date
            decay_halflife: Half-life in days (30 for tactical, 60 for structural)

        Returns:
            Decay-adjusted exposure (0-1 scale)
        """
        decay_factor = 0.5 ** (days_since_snapshot / decay_halflife)
        # Convert from 0-100 to 0-1 scale
        return (exposure / 100.0) * decay_factor

    def build_sensor_reading(
        self,
        cik: str,
        name: str,
        filing: Filing,
        exposure_history: pd.DataFrame,
        asof_date: date,
        decay_halflife: int,
    ) -> SensorReading:
        """
        Construct a SensorReading from computed fields.

        Args:
            cik: Manager CIK
            name: Manager name
            filing: Latest filing
            exposure_history: Pre-computed exposure history
            asof_date: Date to compute effective exposure for
            decay_halflife: Decay half-life in days

        Returns:
            SensorReading object
        """
        # Get row for this filing
        row = exposure_history[exposure_history["report_date"] == filing.report_date]
        if row.empty:
            raise ValueError(f"Exposure history missing for report date {filing.report_date}")

        row = row.iloc[0]

        # Compute days since snapshot
        days_since = (asof_date - filing.report_date).days

        # Compute effective exposure
        effective_exp = self.compute_effective_exposure(
            row["exposure_index"],
            days_since,
            decay_halflife,
        )

        return SensorReading(
            cik=cik,
            name=name,
            asof_quarter_end=filing.report_date,
            filing_date=filing.filing_date,
            total_13f_value=filing.total_value,
            exposure_index=row["exposure_index"],
            delta_exposure=row.get("delta_exposure", 0.0),
            days_since_snapshot=days_since,
            effective_exposure=effective_exp,
            rolling_max_5y=row["rolling_max"],
        )

    def build_sensor_history(
        self,
        cik: str,
        name: str,
        filings: List[Filing],
        decay_halflife: int,
    ) -> List[SensorReading]:
        """
        Build full sensor history for a manager.

        Returns:
            List of SensorReading objects (one per filing)
        """
        if not filings:
            return []

        # Compute exposure history
        exposure_df = self.compute_exposure_history(filings)

        # Compute deltas
        exposure_df["delta_exposure"] = self.compute_delta(exposure_df["exposure_index"])

        # Build readings (using report_date as asof_date for historical readings)
        readings = []
        for filing in filings:
            reading = self.build_sensor_reading(
                cik=cik,
                name=name,
                filing=filing,
                exposure_history=exposure_df,
                asof_date=filing.report_date,  # At time of report, no decay
                decay_halflife=decay_halflife,
            )
            readings.append(reading)

        return readings
