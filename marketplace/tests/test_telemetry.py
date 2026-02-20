"""Tests for OpenTelemetry setup."""

import pytest
from unittest.mock import patch, MagicMock


def test_telemetry_disabled_by_default():
    """Telemetry should not initialize when OTEL_ENABLED=false."""
    from marketplace.core.telemetry import setup_telemetry

    app = MagicMock()
    # Should not raise even without otel packages
    setup_telemetry(app)


def test_telemetry_config_defaults():
    """Verify default config values."""
    from marketplace.config import Settings

    s = Settings()
    assert s.otel_enabled is False
    assert s.otel_exporter_endpoint == "http://localhost:4317"
    assert s.otel_service_name == "agentchains-marketplace"


@patch("marketplace.config.settings")
def test_telemetry_skips_when_disabled(mock_settings):
    """Telemetry setup should skip when disabled."""
    mock_settings.otel_enabled = False
    from marketplace.core.telemetry import setup_telemetry

    app = MagicMock()
    setup_telemetry(app)
    # No exception = success
