"""Tests for OpenTelemetry setup."""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest


def test_telemetry_disabled_by_default():
    from marketplace.core.telemetry import setup_telemetry
    setup_telemetry(MagicMock())


def test_telemetry_config_defaults():
    from marketplace.config import Settings
    s = Settings()
    assert s.otel_enabled is False
    assert s.otel_exporter_endpoint == "http://localhost:4317"
    assert s.otel_service_name == "agentchains-marketplace"


@patch("marketplace.config.settings")
def test_telemetry_skips_when_disabled(mock_settings):
    mock_settings.otel_enabled = False
    from marketplace.core.telemetry import setup_telemetry
    setup_telemetry(MagicMock())


class TestSetupAzureMonitor:
    def test_azure_import_error(self):
        from marketplace.core.telemetry import _setup_azure_monitor
        # _setup_azure_monitor imports configure_azure_monitor inside try/except
        # so ImportError is caught and logged
        _setup_azure_monitor(MagicMock(), MagicMock(), "conn")

    @patch.dict("sys.modules", {"azure.monitor.opentelemetry": MagicMock()})
    def test_azure_with_mock_module(self):
        from marketplace.core.telemetry import _setup_azure_monitor
        _setup_azure_monitor(MagicMock(), MagicMock(), "InstrumentationKey=test")


class TestSetupOtlpExporter:
    def test_otlp_import_error(self):
        from marketplace.core.telemetry import _setup_otlp_exporter
        # Without otel packages installed, ImportError caught gracefully
        _setup_otlp_exporter(MagicMock(), MagicMock())


class TestSetupTelemetryDispatch:
    def test_otel_disabled(self):
        from marketplace.core.telemetry import setup_telemetry
        setup_telemetry(MagicMock())

    @patch("marketplace.core.telemetry._setup_azure_monitor")
    @patch("marketplace.config.settings")
    def test_azure_path(self, mock_s, mock_azure):
        mock_s.otel_enabled = True
        mock_s.azure_appinsights_connection = "InstrumentationKey=test"
        from marketplace.core.telemetry import setup_telemetry
        setup_telemetry(MagicMock())
        mock_azure.assert_called_once()

    @patch("marketplace.core.telemetry._setup_otlp_exporter")
    @patch("marketplace.config.settings")
    def test_otlp_path(self, mock_s, mock_otlp):
        mock_s.otel_enabled = True
        mock_s.azure_appinsights_connection = ""
        from marketplace.core.telemetry import setup_telemetry
        setup_telemetry(MagicMock())
        mock_otlp.assert_called_once()
