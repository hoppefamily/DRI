"""
DRI — Discretionary Risk Index

A multi-manager regime indicator measuring whether discretionary macro managers
collectively permit equity risk, using normalized 13F exposure, rate of change,
and cross-manager dispersion.
"""

__version__ = "0.1.0"

from .aggregator import DRIAggregator, DRISnapshot
from .regime import RegimeClassifier, RegimeState
from .sensor import ManagerSensor, SensorReading

__all__ = [
    "ManagerSensor",
    "SensorReading",
    "DRIAggregator",
    "DRISnapshot",
    "RegimeClassifier",
    "RegimeState",
]
