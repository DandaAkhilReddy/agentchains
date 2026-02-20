"""OpenTelemetry instrumentation for AgentChains.

Provides opt-in tracing and metrics collection. Enable by setting
OTEL_ENABLED=true and configuring the exporter endpoint.

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

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({
            "service.name": "agentchains-marketplace",
            "service.version": settings.app_version if hasattr(settings, "app_version") else "0.5.0",
            "deployment.environment": settings.environment,
        })

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=getattr(settings, "otel_exporter_endpoint", "http://localhost:4317"),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)

        # Instrument HTTPX (used for webhooks, A2A calls)
        HTTPXClientInstrumentor().instrument()

        # Instrument SQLAlchemy
        from marketplace.database import engine
        if engine:
            SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

        logger.info(
            "OpenTelemetry initialized: endpoint=%s, service=%s",
            getattr(settings, "otel_exporter_endpoint", "http://localhost:4317"),
            "agentchains-marketplace",
        )

    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-httpx "
            "opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp"
        )
    except Exception:
        logger.exception("Failed to initialize OpenTelemetry")
