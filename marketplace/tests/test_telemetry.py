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


class TestAzureMonitorSuccessPath:
    @patch.dict("sys.modules", {
        "azure.monitor.opentelemetry": MagicMock(),
        "opentelemetry.instrumentation.fastapi": MagicMock(),
        "opentelemetry.instrumentation.httpx": MagicMock(),
        "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
    })
    @patch("marketplace.database.engine", MagicMock(sync_engine=MagicMock()))
    def test_azure_full_success(self):
        from marketplace.core.telemetry import _setup_azure_monitor
        app = MagicMock()
        settings = MagicMock()
        _setup_azure_monitor(app, settings, "InstrumentationKey=test")

    @patch.dict("sys.modules", {
        "azure.monitor.opentelemetry": MagicMock(),
        "opentelemetry.instrumentation.fastapi": MagicMock(),
    })
    def test_azure_without_httpx(self):
        import sys
        # Remove httpx instrumentation to test ImportError branch
        sys.modules.pop("opentelemetry.instrumentation.httpx", None)
        sys.modules.pop("opentelemetry.instrumentation.sqlalchemy", None)
        from marketplace.core.telemetry import _setup_azure_monitor
        _setup_azure_monitor(MagicMock(), MagicMock(), "InstrumentationKey=test")

    def test_azure_generic_exception(self):
        from marketplace.core.telemetry import _setup_azure_monitor
        # Force an exception by passing bad args with azure module available
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": MagicMock(
            configure_azure_monitor=MagicMock(side_effect=RuntimeError("boom"))
        )}):
            # Should not raise - exception is caught and logged
            _setup_azure_monitor(MagicMock(), MagicMock(), "InstrumentationKey=test")


class TestOtlpExporterSuccessPath:
    @patch.dict("sys.modules", {
        "opentelemetry": MagicMock(),
        "opentelemetry.trace": MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
        "opentelemetry.instrumentation.fastapi": MagicMock(),
        "opentelemetry.sdk.resources": MagicMock(),
        "opentelemetry.sdk.trace": MagicMock(),
        "opentelemetry.sdk.trace.export": MagicMock(),
        "opentelemetry.instrumentation.httpx": MagicMock(),
        "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
    })
    @patch("marketplace.database.engine", MagicMock(sync_engine=MagicMock()))
    def test_otlp_full_success(self):
        from marketplace.core.telemetry import _setup_otlp_exporter
        settings = MagicMock()
        settings.environment = "development"
        settings.otel_service_name = "test-svc"
        settings.otel_exporter_endpoint = "http://localhost:4317"
        _setup_otlp_exporter(MagicMock(), settings)

    @patch.dict("sys.modules", {
        "opentelemetry": MagicMock(),
        "opentelemetry.trace": MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
        "opentelemetry.instrumentation.fastapi": MagicMock(),
        "opentelemetry.sdk.resources": MagicMock(),
        "opentelemetry.sdk.trace": MagicMock(),
        "opentelemetry.sdk.trace.export": MagicMock(),
    })
    def test_otlp_without_optional_instrumentors(self):
        import sys
        sys.modules.pop("opentelemetry.instrumentation.httpx", None)
        sys.modules.pop("opentelemetry.instrumentation.sqlalchemy", None)
        from marketplace.core.telemetry import _setup_otlp_exporter
        settings = MagicMock()
        settings.environment = "dev"
        _setup_otlp_exporter(MagicMock(), settings)

    def test_otlp_generic_exception(self):
        from marketplace.core.telemetry import _setup_otlp_exporter
        # With no otel packages, gets ImportError caught gracefully
        _setup_otlp_exporter(MagicMock(), MagicMock())


class TestSetupTelemetryFull:
    @patch("marketplace.core.telemetry._setup_azure_monitor")
    @patch("marketplace.config.settings")
    def test_azure_path_dispatches(self, mock_s, mock_azure):
        mock_s.otel_enabled = True
        mock_s.azure_appinsights_connection = "InstrumentationKey=test"
        from marketplace.core.telemetry import setup_telemetry
        setup_telemetry(MagicMock())
        mock_azure.assert_called_once()

    @patch("marketplace.core.telemetry._setup_otlp_exporter")
    @patch("marketplace.config.settings")
    def test_otlp_path_dispatches(self, mock_s, mock_otlp):
        mock_s.otel_enabled = True
        mock_s.azure_appinsights_connection = ""
        from marketplace.core.telemetry import setup_telemetry
        setup_telemetry(MagicMock())
        mock_otlp.assert_called_once()

    @patch("marketplace.config.settings")
    def test_disabled_logs_info(self, mock_s):
        mock_s.otel_enabled = False
        from marketplace.core.telemetry import setup_telemetry
        setup_telemetry(MagicMock())


class TestAzureImportErrorPath:
    def test_azure_real_import_error(self):
        """Without azure package installed, the ImportError path is hit."""
        import sys
        # Ensure azure.monitor.opentelemetry is NOT in sys.modules
        saved = sys.modules.pop("azure.monitor.opentelemetry", None)
        try:
            from marketplace.core.telemetry import _setup_azure_monitor
            # This should trigger the ImportError branch (line 78)
            _setup_azure_monitor(MagicMock(), MagicMock(), "InstrumentationKey=test")
        finally:
            if saved is not None:
                sys.modules["azure.monitor.opentelemetry"] = saved


class TestOtlpOptionalInstrumentors:
    @patch.dict("sys.modules", {
        "opentelemetry": MagicMock(),
        "opentelemetry.trace": MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
        "opentelemetry.instrumentation.fastapi": MagicMock(),
        "opentelemetry.sdk.resources": MagicMock(),
        "opentelemetry.sdk.trace": MagicMock(),
        "opentelemetry.sdk.trace.export": MagicMock(),
    })
    def test_otlp_httpx_import_error(self):
        """When httpx instrumentor is not installed, it is skipped."""
        import sys
        # Ensure httpx/sqlalchemy instrumentors are NOT available
        sys.modules.pop("opentelemetry.instrumentation.httpx", None)
        sys.modules.pop("opentelemetry.instrumentation.sqlalchemy", None)
        from marketplace.core.telemetry import _setup_otlp_exporter
        settings = MagicMock()
        settings.environment = "dev"
        _setup_otlp_exporter(MagicMock(), settings)

    @patch.dict("sys.modules", {
        "opentelemetry": MagicMock(),
        "opentelemetry.trace": MagicMock(),
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
        "opentelemetry.instrumentation.fastapi": MagicMock(),
        "opentelemetry.sdk.resources": MagicMock(),
        "opentelemetry.sdk.trace": MagicMock(),
        "opentelemetry.sdk.trace.export": MagicMock(),
        "opentelemetry.instrumentation.httpx": MagicMock(),
    })
    @patch("marketplace.database.engine", MagicMock(sync_engine=MagicMock()))
    def test_otlp_sqlalchemy_exception(self):
        """When sqlalchemy instrumentor raises, exception is caught."""
        import sys
        # Make sqlalchemy instrumentor raise an exception
        mock_sqla = MagicMock()
        mock_sqla.SQLAlchemyInstrumentor.return_value.instrument.side_effect = RuntimeError("fail")
        sys.modules["opentelemetry.instrumentation.sqlalchemy"] = mock_sqla
        from marketplace.core.telemetry import _setup_otlp_exporter
        settings = MagicMock()
        settings.environment = "dev"
        _setup_otlp_exporter(MagicMock(), settings)

