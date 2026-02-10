"""End-to-end DRI pipeline orchestrator."""
import logging
from datetime import date
from typing import List, Optional

from .aggregator import DRIAggregator, DRISnapshot
from .config import Config
from .edgar import EDGARFetcher, Filing
from .regime import RegimeClassifier
from .sensor import ManagerSensor, SensorReading
from .storage import Storage

logger = logging.getLogger(__name__)


class DRIPipeline:
    """Coordinate the full DRI computation pipeline."""

    def __init__(self, config: Config):
        """Initialize pipeline with configuration."""
        self.config = config
        self.edgar = EDGARFetcher(config.config)
        self.sensor = ManagerSensor(config.config)
        self.aggregator = DRIAggregator(config.config)
        self.classifier = RegimeClassifier(config.config)
        self.storage = Storage(config.config)

    def fetch_manager_filings(
        self,
        cik: str,
        quarters: int = 8,
    ) -> List[Filing]:
        """
        Fetch 13F filings for a manager.

        Returns cached data if available, otherwise fetches from EDGAR.
        """
        logger.info(f"Fetching filings for CIK {cik}...")

        try:
            filings = self.edgar.fetch_13f_filings(
                cik=cik,
                quarters=quarters,
            )
            logger.info(f"Fetched {len(filings)} filings for {cik}")
            return filings
        except Exception as e:
            logger.error(f"Failed to fetch filings for {cik}: {e}")
            raise

    def compute_manager_sensor(
        self,
        cik: str,
        name: str,
        filings: List[Filing],
        asof_date: date,
        decay_halflife: int,
    ) -> SensorReading:
        """
        Compute sensor reading for a manager.

        Returns:
            Latest SensorReading for asof_date
        """
        if not filings:
            raise ValueError(f"No filings available for {cik}")

        logger.info(f"Computing sensor for {name} ({cik})...")

        # Compute exposure history
        exposure_history = self.sensor.compute_exposure_history(filings)

        # Add deltas
        exposure_history["delta_exposure"] = self.sensor.compute_delta(
            exposure_history["exposure_index"]
        )

        # Build sensor reading for latest filing
        latest_filing = filings[-1]
        reading = self.sensor.build_sensor_reading(
            cik=cik,
            name=name,
            filing=latest_filing,
            exposure_history=exposure_history,
            asof_date=asof_date,
            decay_halflife=decay_halflife,
        )

        logger.info(
            f"{name}: exposure={reading.exposure_index:.1f}%, "
            f"delta={reading.delta_exposure:.1f}%, "
            f"effective={reading.effective_exposure:.3f} "
            f"({reading.days_since_snapshot} days old)"
        )

        return reading

    def run(
        self,
        asof_date: Optional[date] = None,
        upload_s3: bool = False,
        dry_run: bool = False,
    ) -> DRISnapshot:
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

        Args:
            asof_date: Date to compute DRI for (default: today)
            upload_s3: If True, upload results to S3
            dry_run: If True, validate without storing

        Returns:
            DRISnapshot object
        """
        if asof_date is None:
            asof_date = date.today()

        logger.info(f"Running DRI pipeline for {asof_date}...")

        # Process each panel member
        readings = []
        for panel_member in self.config["panel"]:
            cik = panel_member["cik"]
            name = panel_member["name"]
            decay_type = panel_member.get("decay_type", "tactical")
            decay_halflife = panel_member.get("decay_halflife_days", 30)

            try:
                # Fetch filings
                filings = self.fetch_manager_filings(cik, quarters=8)

                # Compute sensor reading
                reading = self.compute_manager_sensor(
                    cik=cik,
                    name=name,
                    filings=filings,
                    asof_date=asof_date,
                    decay_halflife=decay_halflife,
                )
                readings.append(reading)

                # Store sensor history (if not dry run)
                if not dry_run:
                    sensor_history = self.sensor.build_sensor_history(
                        cik=cik,
                        name=name,
                        filings=filings,
                        decay_halflife=decay_halflife,
                    )
                    self.storage.save_sensor_history(
                        sensor_history,
                        cik=cik,
                        upload_s3=upload_s3,
                    )

            except Exception as e:
                logger.error(f"Failed to process {name} ({cik}): {e}")
                # Continue with remaining panel members
                continue

        # Check minimum panel size
        min_size = self.config["regime"]["min_panel_members"]
        if len(readings) < min_size:
            raise ValueError(
                f"Insufficient panel members: {len(readings)} < {min_size}. "
                "Pipeline requires more successful manager readings."
            )

        # Aggregate
        logger.info("Aggregating panel readings...")
        snapshot = self.aggregator.aggregate(readings, asof_date)

        # Classify regime
        prev_snapshot = self.storage.load_dri_snapshot() if not dry_run else None
        prev_disp = prev_snapshot.dispersion if prev_snapshot else None

        regime_state = self.classifier.classify(
            median_exp=snapshot.median_effective_exposure,
            median_delta=snapshot.median_delta,
            dispersion=snapshot.dispersion,
            prev_dispersion=prev_disp,
        )
        snapshot.regime_state = regime_state.value

        logger.info(f"DRI Regime: {regime_state.value}")

        # Store snapshot (if not dry run)
        if not dry_run:
            self.storage.save_dri_snapshot(snapshot, upload_s3=upload_s3)

        return snapshot

    def show_latest(self) -> Optional[DRISnapshot]:
        """Load and return the latest DRI snapshot."""
        return self.storage.load_dri_snapshot()

    def show_history(self) -> List[DRISnapshot]:
        """Load and return all DRI snapshots."""
        return self.storage.load_dri_history()
