"""Regime classification for DRI."""
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RegimeState(Enum):
    """DRI regime states."""
    RISK_ON = "Risk ON"
    RISK_ON_FRAGILE = "Risk ON (fragile)"
    TRANSITION = "Transition"
    RISK_OFF = "Risk OFF"
    PANIC_RESET = "Panic / Reset"


class RegimeClassifier:
    """Classify DRI regime based on threshold rules."""

    def __init__(self, config: dict):
        """Initialize with threshold configuration."""
        regime_config = config["regime"]
        self.high_exp = regime_config["high_exposure"]
        self.low_exp = regime_config["low_exposure"]
        self.high_disp = regime_config["high_dispersion"]
        self.disp_rising = regime_config["dispersion_rising_threshold"]
        self.fast_contract = regime_config["fast_contraction_delta"]

    def classify(
        self,
        median_exp: float,
        median_delta: float,
        dispersion: float,
        prev_dispersion: Optional[float] = None,
    ) -> RegimeState:
        """
        Classify regime using threshold rules.

        Logic (from DRI spec Section 5/7):

        1. Panic / Reset:
           - Fast contraction: median_delta < fast_contraction_delta
           - AND dispersion spike: dispersion > high_disp

        2. Risk OFF:
           - Low median: median_exp < low_exp
           - AND low dispersion: dispersion < high_disp

        3. Transition:
           - Falling median: median_delta < 0
           - AND high dispersion: dispersion > high_disp

        4. Risk ON (fragile):
           - High median: median_exp > high_exp
           - AND rising dispersion: dispersion - prev_dispersion > disp_rising

        5. Risk ON:
           - High median: median_exp > high_exp
           - AND low dispersion: dispersion < high_disp

        Priority: Check in order 1→5, return first match.

        Args:
            median_exp: Median effective exposure (0-1 scale)
            median_delta: Median delta exposure
            dispersion: Current dispersion (stddev)
            prev_dispersion: Previous dispersion (for trend detection)

        Returns:
            RegimeState enum value
        """
        # 1. Panic / Reset
        if median_delta < self.fast_contract and dispersion > self.high_disp:
            logger.info(
                f"Regime: PANIC_RESET "
                f"(delta={median_delta:.3f} < {self.fast_contract}, "
                f"disp={dispersion:.3f} > {self.high_disp})"
            )
            return RegimeState.PANIC_RESET

        # 2. Risk OFF
        if median_exp < self.low_exp and dispersion < self.high_disp:
            logger.info(
                f"Regime: RISK_OFF "
                f"(exp={median_exp:.3f} < {self.low_exp}, "
                f"disp={dispersion:.3f} < {self.high_disp})"
            )
            return RegimeState.RISK_OFF

        # 3. Transition
        if median_delta < 0 and dispersion > self.high_disp:
            logger.info(
                f"Regime: TRANSITION "
                f"(delta={median_delta:.3f} < 0, "
                f"disp={dispersion:.3f} > {self.high_disp})"
            )
            return RegimeState.TRANSITION

        # 4. Risk ON (fragile)
        if median_exp > self.high_exp:
            if prev_dispersion is not None:
                disp_change = dispersion - prev_dispersion
                if disp_change > self.disp_rising:
                    logger.info(
                        f"Regime: RISK_ON_FRAGILE "
                        f"(exp={median_exp:.3f} > {self.high_exp}, "
                        f"disp_rising={disp_change:.3f} > {self.disp_rising})"
                    )
                    return RegimeState.RISK_ON_FRAGILE

        # 5. Risk ON (default when high exposure)
        if median_exp > self.high_exp:
            logger.info(
                f"Regime: RISK_ON "
                f"(exp={median_exp:.3f} > {self.high_exp}, "
                f"disp={dispersion:.3f} < {self.high_disp})"
            )
            return RegimeState.RISK_ON

        # Fallback: ambiguous state (between thresholds)
        # Treat as transition
        logger.warning(
            f"Ambiguous regime state "
            f"(exp={median_exp:.3f}, delta={median_delta:.3f}, disp={dispersion:.3f}), "
            f"defaulting to TRANSITION"
        )
        return RegimeState.TRANSITION
