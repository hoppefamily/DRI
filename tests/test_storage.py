"""Tests for storage snapshot deserialization."""
import copy
from dataclasses import asdict
from datetime import date

import pandas as pd

from dri.sensor import SensorReading
from dri.storage import Storage


def _build_snapshot_row(asof_date, sensor_dict):
    return {
        "asof_date": asof_date,
        "median_effective_exposure": 0.5,
        "median_delta": 0.1,
        "dispersion": 0.2,
        "dispersion_spread": 0.3,
        "regime_state": "RiskOn",
        "panel_members": ["0001536411"],
        "sensor_readings": [sensor_dict],
        "companion_signals": None,
    }


def _build_storage(tmp_path, test_config):
    config = copy.deepcopy(test_config)
    config["storage"]["output_dir"] = str(tmp_path)
    return Storage(config)


def test_load_dri_snapshot_deserializes_sensor_readings(
    tmp_path,
    test_config,
    sample_sensor_reading,
    monkeypatch,
):
    storage = _build_storage(tmp_path, test_config)
    (tmp_path / "dri_latest.parquet").touch()

    sensor_dict = asdict(sample_sensor_reading)
    df = pd.DataFrame([_build_snapshot_row(date(2025, 12, 31), sensor_dict)])

    monkeypatch.setattr("dri.storage.pd.read_parquet", lambda path: df)

    snapshot = storage.load_dri_snapshot()

    assert snapshot is not None
    assert snapshot.sensor_readings
    assert isinstance(snapshot.sensor_readings[0], SensorReading)
    assert snapshot.sensor_readings[0].cik == sample_sensor_reading.cik


def test_load_dri_snapshot_handles_nan_sensor_readings(
    tmp_path,
    test_config,
    monkeypatch,
):
    storage = _build_storage(tmp_path, test_config)
    (tmp_path / "dri_latest.parquet").touch()

    df = pd.DataFrame([{
        "asof_date": date(2025, 12, 31),
        "median_effective_exposure": 0.5,
        "median_delta": 0.1,
        "dispersion": 0.2,
        "dispersion_spread": 0.3,
        "regime_state": "RiskOn",
        "panel_members": ["0001536411"],
        "sensor_readings": float("nan"),
        "companion_signals": None,
    }])

    monkeypatch.setattr("dri.storage.pd.read_parquet", lambda path: df)

    snapshot = storage.load_dri_snapshot()

    assert snapshot is not None
    assert snapshot.sensor_readings == []


def test_load_dri_history_deserializes_sensor_readings(
    tmp_path,
    test_config,
    sample_sensor_reading,
    monkeypatch,
):
    storage = _build_storage(tmp_path, test_config)

    (tmp_path / "dri_snapshot_2025-01-31.parquet").touch()
    (tmp_path / "dri_snapshot_2025-04-30.parquet").touch()

    sensor_dict = asdict(sample_sensor_reading)

    def fake_read_parquet(path):
        if path.name.endswith("2025-01-31.parquet"):
            asof_date = date(2025, 1, 31)
        else:
            asof_date = date(2025, 4, 30)
        return pd.DataFrame([_build_snapshot_row(asof_date, sensor_dict)])

    monkeypatch.setattr("dri.storage.pd.read_parquet", fake_read_parquet)

    snapshots = storage.load_dri_history()

    assert [s.asof_date for s in snapshots] == [date(2025, 1, 31), date(2025, 4, 30)]
    assert all(isinstance(s.sensor_readings[0], SensorReading) for s in snapshots)


def test_save_sensor_history_returns_none_when_empty(tmp_path, test_config):
    storage = _build_storage(tmp_path, test_config)

    result = storage.save_sensor_history([], "0001536411")

    assert result is None
