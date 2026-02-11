"""Storage layer for DRI data."""
import logging
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .aggregator import DRISnapshot
from .sensor import SensorReading

logger = logging.getLogger(__name__)


class Storage:
    """Handles reading/writing of DRI data."""

    def __init__(self, config: dict):
        """Initialize with configuration."""
        self.output_dir = Path(config["storage"]["output_dir"])
        self.s3_bucket = config["storage"].get("s3_bucket")
        self.s3_prefix = config["storage"].get("s3_prefix", "dri")

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # S3 client (lazy init)
        self._s3_client = None

    @property
    def s3_client(self):
        """Lazy initialization of S3 client."""
        if self._s3_client is None and self.s3_bucket:
            try:
                import boto3
                self._s3_client = boto3.client("s3")
            except ImportError:
                logger.warning("boto3 not installed, S3 features disabled")
        return self._s3_client

    def save_sensor_history(
        self,
        readings: List[SensorReading],
        cik: str,
        upload_s3: bool = False,
    ) -> Optional[Path]:
        """
        Save sensor readings to Parquet.

        Args:
            readings: List of SensorReading objects
            cik: Manager CIK (for filename)
            upload_s3: If True, upload to S3 after saving locally

        Returns:
            Path to saved file or None when no readings are saved
        """
        if not readings:
            logger.warning(f"No readings to save for CIK {cik}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame([asdict(r) for r in readings])

        # Save locally
        filename = f"sensor_{cik}_history.parquet"
        local_path = self.output_dir / filename
        df.to_parquet(local_path, index=False, compression="snappy")
        logger.info(f"Saved sensor history: {local_path}")

        # Upload to S3 if requested
        if upload_s3 and self.s3_bucket:
            s3_key = f"{self.s3_prefix}/sensors/{cik}/history.parquet"
            self.upload_to_s3(local_path, s3_key)

        return local_path

    def load_sensor_history(self, cik: str) -> List[SensorReading]:
        """
        Load sensor readings from Parquet.

        Args:
            cik: Manager CIK

        Returns:
            List of SensorReading objects
        """
        filename = f"sensor_{cik}_history.parquet"
        local_path = self.output_dir / filename

        if not local_path.exists():
            logger.warning(f"Sensor history not found: {local_path}")
            return []

        df = pd.read_parquet(local_path)

        # Convert dates back from string if needed
        for col in ["asof_quarter_end", "filing_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.date

        return [SensorReading(**row) for row in df.to_dict("records")]

    def save_dri_snapshot(
        self,
        snapshot: DRISnapshot,
        upload_s3: bool = False,
    ) -> Path:
        """
        Save DRI snapshot to Parquet.

        Args:
            snapshot: DRISnapshot object
            upload_s3: If True, upload to S3 after saving locally

        Returns:
            Path to saved file
        """
        # Convert to DataFrame (single row)
        df = pd.DataFrame([asdict(snapshot)])

        # Save locally
        filename = f"dri_snapshot_{snapshot.asof_date}.parquet"
        local_path = self.output_dir / filename
        df.to_parquet(local_path, index=False, compression="snappy")
        logger.info(f"Saved DRI snapshot: {local_path}")

        # Also save as "latest"
        latest_path = self.output_dir / "dri_latest.parquet"
        df.to_parquet(latest_path, index=False, compression="snappy")

        # Upload to S3 if requested
        if upload_s3 and self.s3_bucket:
            s3_key = f"{self.s3_prefix}/snapshots/{snapshot.asof_date}.parquet"
            self.upload_to_s3(local_path, s3_key)

            latest_key = f"{self.s3_prefix}/latest.parquet"
            self.upload_to_s3(latest_path, latest_key)

        return local_path

    def load_dri_snapshot(self, asof_date: Optional[str] = None) -> Optional[DRISnapshot]:
        """
        Load DRI snapshot from Parquet.

        Args:
            asof_date: Specific date to load, or None for latest

        Returns:
            DRISnapshot object or None if not found
        """
        if asof_date:
            filename = f"dri_snapshot_{asof_date}.parquet"
        else:
            filename = "dri_latest.parquet"

        local_path = self.output_dir / filename

        if not local_path.exists():
            logger.warning(f"DRI snapshot not found: {local_path}")
            return None

        df = pd.read_parquet(local_path)

        # Convert dates
        if "asof_date" in df.columns:
            df["asof_date"] = pd.to_datetime(df["asof_date"]).dt.date

        # Get first row
        row = df.iloc[0].to_dict()

        # Import here to avoid circular dependency
        from .aggregator import DRISnapshot
        row["sensor_readings"] = self._deserialize_sensor_readings(row.get("sensor_readings"))
        return DRISnapshot(**row)

    def load_dri_history(self) -> List[DRISnapshot]:
        """
        Load all DRI snapshots.

        Returns:
            List of DRISnapshot objects sorted by date
        """
        # Find all snapshot files
        snapshot_files = sorted(self.output_dir.glob("dri_snapshot_*.parquet"))

        snapshots = []
        for file_path in snapshot_files:
            try:
                df = pd.read_parquet(file_path)
                if "asof_date" in df.columns:
                    df["asof_date"] = pd.to_datetime(df["asof_date"]).dt.date

                from .aggregator import DRISnapshot
                row = df.iloc[0].to_dict()
                row["sensor_readings"] = self._deserialize_sensor_readings(row.get("sensor_readings"))
                snapshot = DRISnapshot(**row)
                snapshots.append(snapshot)
            except Exception as e:
                logger.error(f"Failed to load snapshot {file_path}: {e}")

        return sorted(snapshots, key=lambda s: s.asof_date)

    def upload_to_s3(self, local_path: Path, s3_key: str):
        """Upload file to S3."""
        if not self.s3_client:
            logger.warning("S3 client not available, skipping upload")
            return

        try:
            self.s3_client.upload_file(
                str(local_path),
                self.s3_bucket,
                s3_key,
            )
            logger.info(f"Uploaded to s3://{self.s3_bucket}/{s3_key}")
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")

    def download_from_s3(self, s3_key: str, local_path: Path):
        """Download file from S3."""
        if not self.s3_client:
            logger.warning("S3 client not available, skipping download")
            return

        try:
            self.s3_client.download_file(
                self.s3_bucket,
                s3_key,
                str(local_path),
            )
            logger.info(f"Downloaded from s3://{self.s3_bucket}/{s3_key}")
        except Exception as e:
            logger.error(f"S3 download failed: {e}")

    def _deserialize_sensor_readings(self, raw_readings) -> List[SensorReading]:
        """Convert stored sensor readings into SensorReading objects."""
        if raw_readings is None:
            return []
        if isinstance(raw_readings, float) and pd.isna(raw_readings):
            return []
        if isinstance(raw_readings, list):
            readings = []
            for item in raw_readings:
                if isinstance(item, SensorReading):
                    readings.append(item)
                elif isinstance(item, dict):
                    readings.append(SensorReading(**item))
            return readings
        return []
