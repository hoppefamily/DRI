"""End-to-end DRI pipeline orchestrator."""
import logging
from datetime import date, timedelta
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

    def get_expected_filing_date(self, last_filing_date: date) -> date:
        """
        Calculate expected next filing date based on last filing.

        13F-HR filings are due 45 days after quarter end.
        Quarters end: Mar 31, Jun 30, Sep 30, Dec 31

        Args:
            last_filing_date: Date of last 13F filing

        Returns:
            Expected date of next filing (45 days after next quarter end)
        """
        # Determine which quarter the last filing was for
        # Filings are typically 45-60 days after quarter end
        # So if filed in February, it was for Q4 (Dec 31)
        # If filed in May, it was for Q1 (Mar 31), etc.

        # Map filing month to corresponding quarter end
        filing_month = last_filing_date.month

        if filing_month in [2, 3]:  # Q4 previous year
            last_quarter_end_month, last_quarter_end_day = 12, 31
            last_quarter_end_year = last_filing_date.year - 1
        elif filing_month in [5, 6]:  # Q1
            last_quarter_end_month, last_quarter_end_day = 3, 31
            last_quarter_end_year = last_filing_date.year
        elif filing_month in [8, 9]:  # Q2
            last_quarter_end_month, last_quarter_end_day = 6, 30
            last_quarter_end_year = last_filing_date.year
        else:  # [11, 12, 1] Q3
            last_quarter_end_month, last_quarter_end_day = 9, 30
            last_quarter_end_year = last_filing_date.year

        # Calculate next quarter end (3 months forward)
        next_quarter_month = last_quarter_end_month + 3
        next_quarter_year = last_quarter_end_year
        if next_quarter_month > 12:
            next_quarter_month -= 12
            next_quarter_year += 1

        # Quarters always end on specific dates
        quarter_end_days = {3: 31, 6: 30, 9: 30, 12: 31}
        next_quarter_end = date(
            next_quarter_year,
            next_quarter_month,
            quarter_end_days[next_quarter_month]
        )

        # Filing deadline is 45 days after quarter end
        expected_filing = next_quarter_end + timedelta(days=45)
        return expected_filing

    def check_manager_status(
        self,
        cik: str,
        name: str,
        last_filing_date: date,
        asof_date: date,
    ) -> dict:
        """
        Classify manager filing status and return diagnostic information.

        Status levels:
        - CURRENT: Within normal quarterly cycle (< 60 days since last filing)
        - PENDING: Filing not yet due based on expected schedule
        - LATE_MINOR: 1-30 days overdue (might still be coming)
        - LATE_MODERATE: 31-90 days overdue (probably stopped filing)
        - INACTIVE: 90+ days overdue (confirmed inactive)

        Args:
            cik: Manager CIK
            name: Manager name
            last_filing_date: Date of last 13F filing
            asof_date: Current date to check against

        Returns:
            Dictionary with status, days_since, days_overdue, and action
        """
        days_since = (asof_date - last_filing_date).days
        expected_filing = self.get_expected_filing_date(last_filing_date)
        days_overdue = (asof_date - expected_filing).days

        if days_since < 60:
            status = "CURRENT"
            action = "No action needed"
        elif days_overdue < 0:
            status = "PENDING"
            action = f"Next filing expected around {expected_filing}"
        elif days_overdue < 30:
            status = "LATE_MINOR"
            action = "Monitor - may file soon (some managers file late)"
        elif days_overdue < 90:
            status = "LATE_MODERATE"
            action = "⚠️  REVIEW NEEDED - Check SEC ADV and press for status"
        else:
            status = "INACTIVE"
            action = "🚨 REPLACE RECOMMENDED - Likely stopped filing"

        return {
            "status": status,
            "days_since": days_since,
            "days_overdue": days_overdue,
            "expected_filing": expected_filing,
            "action": action,
            "check_urls": {
                "sec_adv": "https://adviserinfo.sec.gov/",
                "sec_edgar": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F&dateb=&owner=exclude&count=40",
            }
        }

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
        stale_managers = []

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

                # Determine filing status
                status_info = self.check_manager_status(
                    cik=cik,
                    name=name,
                    last_filing_date=reading.filing_date,
                    asof_date=asof_date,
                )
                reading.filing_status = status_info["status"]

                # Track stale managers for warnings (> 120 days)
                if reading.days_since_snapshot > 120:
                    stale_managers.append((name, cik, status_info))

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

        # Warn about stale data
        if stale_managers:
            logger.warning("=" * 80)
            logger.warning("STALE DATA DETECTED - Panel Review Recommended")
            logger.warning("=" * 80)
            for name, cik, status in stale_managers:
                logger.warning(f"\n{name} (CIK {cik}):")
                logger.warning(f"  Status: {status['status']}")
                logger.warning(f"  Days since filing: {status['days_since']}")
                logger.warning(f"  Days overdue: {status['days_overdue']}")
                logger.warning(f"  Action: {status['action']}")
                logger.warning(f"  SEC ADV: {status['check_urls']['sec_adv']}")
                logger.warning(f"  SEC EDGAR: {status['check_urls']['sec_edgar']}")
            logger.warning("\n" + "=" * 80)
            logger.warning("See docs/PANEL_MONITORING.md for guidance on panel member replacement")
            logger.warning("=" * 80 + "\n")

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
