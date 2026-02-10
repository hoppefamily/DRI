"""Tests for regime classification."""
from dri.regime import RegimeClassifier, RegimeState


def test_regime_risk_on(test_config):
    """Test Risk ON classification."""
    classifier = RegimeClassifier(test_config)

    regime = classifier.classify(
        median_exp=0.75,       # High exposure
        median_delta=0.02,     # Positive delta
        dispersion=0.08,       # Low dispersion
        prev_dispersion=0.07,
    )

    assert regime == RegimeState.RISK_ON


def test_regime_risk_on_fragile(test_config):
    """Test Risk ON (fragile) classification."""
    classifier = RegimeClassifier(test_config)

    regime = classifier.classify(
        median_exp=0.75,       # High exposure
        median_delta=0.01,
        dispersion=0.12,       # Rising dispersion
        prev_dispersion=0.08,  # Delta > threshold
    )

    assert regime == RegimeState.RISK_ON_FRAGILE


def test_regime_transition(test_config):
    """Test Transition classification."""
    classifier = RegimeClassifier(test_config)

    regime = classifier.classify(
        median_exp=0.55,       # Middle exposure
        median_delta=-0.05,    # Falling
        dispersion=0.18,       # High dispersion
        prev_dispersion=0.15,
    )

    assert regime == RegimeState.TRANSITION


def test_regime_risk_off(test_config):
    """Test Risk OFF classification."""
    classifier = RegimeClassifier(test_config)

    regime = classifier.classify(
        median_exp=0.25,       # Low exposure
        median_delta=-0.02,
        dispersion=0.08,       # Low dispersion
        prev_dispersion=0.09,
    )

    assert regime == RegimeState.RISK_OFF


def test_regime_panic_reset(test_config):
    """Test Panic / Reset classification."""
    classifier = RegimeClassifier(test_config)

    regime = classifier.classify(
        median_exp=0.45,
        median_delta=-0.20,    # Fast contraction
        dispersion=0.22,       # High dispersion spike
        prev_dispersion=0.10,
    )

    assert regime == RegimeState.PANIC_RESET


def test_regime_priority_panic_over_risk_off(test_config):
    """Test that panic takes priority over risk_off."""
    classifier = RegimeClassifier(test_config)

    # Conditions match both panic and risk_off, panic should win
    regime = classifier.classify(
        median_exp=0.30,       # Low enough for risk_off
        median_delta=-0.20,    # Fast contraction (panic)
        dispersion=0.18,       # High (panic), but could be interpreted as low for risk_off context
        prev_dispersion=0.10,
    )

    # Panic should take priority
    assert regime == RegimeState.PANIC_RESET


def test_regime_no_prev_dispersion(test_config):
    """Test regime classification with no previous dispersion (first reading)."""
    classifier = RegimeClassifier(test_config)

    # Should not trigger fragile state without prev_dispersion
    regime = classifier.classify(
        median_exp=0.75,
        median_delta=0.01,
        dispersion=0.12,
        prev_dispersion=None,  # No previous data
    )

    # Should be Risk ON (can't detect fragility without trend)
    assert regime == RegimeState.RISK_ON


def test_regime_boundary_high_exposure(test_config):
    """Test regime classification at high_exposure boundary."""
    classifier = RegimeClassifier(test_config)

    # Exactly at threshold (0.65)
    regime = classifier.classify(
        median_exp=0.65,
        median_delta=0.01,
        dispersion=0.08,
        prev_dispersion=0.07,
    )

    # Should be treated as Risk ON (> condition in code)
    # Actually, our code uses >, so this should not be Risk ON
    assert regime != RegimeState.RISK_ON  # Below threshold


def test_regime_boundary_low_exposure(test_config):
    """Test regime classification at low_exposure boundary."""
    classifier = RegimeClassifier(test_config)

    # Exactly at threshold (0.35)
    regime = classifier.classify(
        median_exp=0.35,
        median_delta=0.0,
        dispersion=0.08,
        prev_dispersion=0.07,
    )

    # Should not be Risk OFF (< condition in code)
    assert regime != RegimeState.RISK_OFF
