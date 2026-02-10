"""Configuration management for DRI."""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULT_CONFIG = {
    "panel": [],
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
        "output_dir": "./data",
        "s3_bucket": None,
        "s3_prefix": "dri",
    },
    "edgar": {
        "user_agent": None,
        "rate_limit_per_sec": 10,
        "retry_attempts": 3,
        "retry_delay_sec": 2,
        "base_url": "https://www.sec.gov",
    },
}


class Config:
    """DRI configuration manager."""

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize config with optional override dict."""
        self.config = self._merge_config(DEFAULT_CONFIG.copy(), config_dict or {})
        self._validate()

    @classmethod
    def from_file(cls, path: str) -> "Config":
        """Load configuration from YAML file."""
        with open(path, "r") as f:
            user_config = yaml.safe_load(f) or {}
        return cls(user_config)

    @classmethod
    def from_default(cls) -> "Config":
        """Load default configuration from package."""
        default_path = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"
        if default_path.exists():
            return cls.from_file(str(default_path))
        return cls()

    def _merge_config(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge override into base config."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def _validate(self):
        """Validate configuration values."""
        # Check panel is not empty
        if not self.config["panel"]:
            raise ValueError("Panel must contain at least one manager")

        # Check minimum panel size
        min_size = self.config["regime"]["min_panel_members"]
        if len(self.config["panel"]) < min_size:
            raise ValueError(f"Panel size {len(self.config['panel'])} is below minimum {min_size}")

        # Check thresholds are valid
        regime = self.config["regime"]
        if not (0 <= regime["low_exposure"] < regime["high_exposure"] <= 1):
            raise ValueError("Invalid exposure thresholds")

        # Check EDGAR user agent
        user_agent = self.config["edgar"]["user_agent"] or os.getenv("SEC_USER_AGENT")
        if not user_agent:
            raise ValueError(
                "SEC User-Agent is required. Set via config['edgar']['user_agent'] "
                "or SEC_USER_AGENT environment variable"
            )
        self.config["edgar"]["user_agent"] = user_agent

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access."""
        return self.config[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with default."""
        return self.config.get(key, default)
