"""OpenTelemetry instrumentation for AgentChains.

Supports two backends:
1. Azure Application Insights (preferred in production)
2. Generic OTLP exporter (for local development with Jaeger/Zipkin)

Enable by setting OTEL_ENABLED=true. If AZURE_APPINSIGHTS_CONNECTION is set,
uses Azure Monitor exporter; otherwise falls back to OTLP gRPC exporter.

Usage:
    from marketplace.core.telemetry import setup_telemetry
    setup_telemetry(app)
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_telemetry(app: "FastAPI") -> None:
    """Initialize OpenTelemetry tracing and metrics if enabled."""
    from marketplace.config import settings

    if not getattr(settings, "otel_enabled", False):
        logger.info("OpenTelemetry disabled (OTEL_ENABLED=false)")
        return

    azure_connection = getattr(settings, "azure_appinsights_connection", "")

    if azure_connection:
        _setup_azure_monitor(app, settings, azure_connection)
    else:
        _setup_otlp_exporter(app, settings)


def _setup_azure_monitor(app: "FastAPI", settings, connection_string: str) -> None:
    """Initialize Azure Monitor OpenTelemetry exporter."""
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=connection_string,
            enable_live_metrics=True,
        )

        # Instrument FastAPI
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)

        # Instrument HTTPX
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

            HTTPXClientInstrumentor().instrument()
        except ImportError:
            pass

        # Instrument SQLAlchemy
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            from marketplace.database import engine

            if engine:
                SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        except (ImportError, Exception):
            pass

        logger.info(
            "Azure Monitor OpenTelemetry initialized (Application Insights)"
        )

    except ImportError:
        logger.warning(
            "azure-monitor-opentelemetry not installed. "
            "Install with: pip install azure-monitor-opentelemetry>=1.0"
        )
    except Exception:
        logger.exception("Failed to initialize Azure Monitor OpenTelemetry")


def _setup_otlp_exporter(app: "FastAPI", settings) -> None:
    """Initialize generic OTLP gRPC exporter (for local dev)."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({
            "service.name": getattr(settings, "otel_service_name", "agentchains-marketplace"),
            "service.version": "1.0.0",
            "deployment.environment": settings.environment,
        })

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=getattr(settings, "otel_exporter_endpoint", "http://localhost:4317"),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)

        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

            HTTPXClientInstrumentor().instrument()
        except ImportError:
            pass

        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            from marketplace.database import engine

            if engine:
                SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        except (ImportError, Exception):
            pass

        logger.info(
            "OpenTelemetry initialized: endpoint=%s, service=%s",
            getattr(settings, "otel_exporter_endpoint", "http://localhost:4317"),
            getattr(settings, "otel_service_name", "agentchains-marketplace"),
        )

    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-fastapi opentelemetry-exporter-otlp"
        )
    except Exception:
        logger.exception("Failed to initialize OpenTelemetry")
