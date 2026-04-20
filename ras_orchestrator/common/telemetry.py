"""
OpenTelemetry instrumentation for RAS Orchestrator.

Provides centralized configuration for tracing, metrics, and logging.
"""
import os
import logging
from typing import Optional, Dict, Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import set_meter_provider, get_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service name and version
SERVICE_NAME_VALUE = os.getenv("OTEL_SERVICE_NAME", "ras-orchestrator")
SERVICE_VERSION_VALUE = os.getenv("OTEL_SERVICE_VERSION", "0.1.0")
DEPLOYMENT_ENV = os.getenv("DEPLOYMENT_ENV", "development")

# Resource attributes
resource = Resource.create({
    SERVICE_NAME: SERVICE_NAME_VALUE,
    SERVICE_VERSION: SERVICE_VERSION_VALUE,
    "deployment.environment": DEPLOYMENT_ENV,
    "telemetry.sdk.name": "opentelemetry",
    "telemetry.sdk.language": "python",
    "telemetry.sdk.version": "1.24.0",
})

# Global tracer and meter providers
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None


def init_tracing(
    exporter_type: str = "console",
    endpoint: Optional[str] = None,
    sampling_rate: float = 1.0,
) -> None:
    """
    Initialize OpenTelemetry tracing.

    Args:
        exporter_type: "console", "otlp", "jaeger"
        endpoint: Exporter endpoint (optional)
        sampling_rate: Sampling rate (0.0 to 1.0)
    """
    global _tracer_provider

    if _tracer_provider is not None:
        logger.warning("TracerProvider already initialized, skipping.")
        return

    # Create TracerProvider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Configure sampler
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    sampler = TraceIdRatioBased(sampling_rate)
    tracer_provider.sampler = sampler

    # Configure exporter
    if exporter_type == "otlp":
        if not endpoint:
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        exporter = OTLPSpanExporter(endpoint=endpoint)
    elif exporter_type == "jaeger":
        if not endpoint:
            endpoint = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
        exporter = JaegerExporter(
            agent_host_name="localhost",
            agent_port=6831,
            collector_endpoint=endpoint,
        )
    else:
        exporter = ConsoleSpanExporter()

    # Add span processor
    span_processor = BatchSpanProcessor(exporter)
    tracer_provider.add_span_processor(span_processor)

    _tracer_provider = tracer_provider
    logger.info(f"Tracing initialized with {exporter_type} exporter, sampling rate {sampling_rate}")


def init_metrics(
    exporter_type: str = "prometheus",
    endpoint: Optional[str] = None,
    port: int = 9464,
) -> None:
    """
    Initialize OpenTelemetry metrics.

    Args:
        exporter_type: "prometheus", "otlp"
        endpoint: Exporter endpoint (optional)
        port: Port for Prometheus exporter (if applicable)
    """
    global _meter_provider

    if _meter_provider is not None:
        logger.warning("MeterProvider already initialized, skipping.")
        return

    if exporter_type == "prometheus":
        from prometheus_client import start_http_server
        # Start Prometheus HTTP server
        start_http_server(port=port)
        logger.info(f"Prometheus metrics server started on port {port}")
        reader = PrometheusMetricReader()
    elif exporter_type == "otlp":
        if not endpoint:
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://localhost:4317")
        exporter = OTLPMetricExporter(endpoint=endpoint)
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5000)
    else:
        # Default to console (for debugging)
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        exporter = ConsoleMetricExporter()
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5000)

    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    set_meter_provider(meter_provider)
    _meter_provider = meter_provider
    logger.info(f"Metrics initialized with {exporter_type} exporter")


def init_logging_correlation() -> None:
    """Inject trace IDs into logs."""
    LoggingInstrumentor().instrument(set_logging_format=True)
    logger.info("Logging correlation with OpenTelemetry enabled")


def instrument_fastapi(app):
    """Instrument FastAPI application."""
    FastAPIInstrumentor.instrument_app(app)
    logger.info("FastAPI instrumented for OpenTelemetry")


def instrument_kafka():
    """Instrument Kafka clients."""
    KafkaInstrumentor().instrument()
    logger.info("Kafka instrumented for OpenTelemetry")


def instrument_redis():
    """Instrument Redis clients."""
    RedisInstrumentor().instrument()
    logger.info("Redis instrumented for OpenTelemetry")


def get_tracer(name: str = None) -> trace.Tracer:
    """Get a tracer instance."""
    if _tracer_provider is None:
        init_tracing()
    return trace.get_tracer(name or SERVICE_NAME_VALUE)


def get_meter(name: str = None):
    """Get a meter instance."""
    if _meter_provider is None:
        init_metrics()
    return get_meter_provider().get_meter(name or SERVICE_NAME_VALUE)


def init_observability(
    tracing_exporter: str = None,
    metrics_exporter: str = None,
    tracing_endpoint: Optional[str] = None,
    metrics_endpoint: Optional[str] = None,
    sampling_rate: float = 1.0,
    prometheus_port: int = 9464,
) -> None:
    """
    Full observability initialization.

    This function should be called at application startup.
    """
    # Determine exporters from environment
    tracing_exporter = tracing_exporter or os.getenv("OTEL_TRACES_EXPORTER", "console")
    metrics_exporter = metrics_exporter or os.getenv("OTEL_METRICS_EXPORTER", "prometheus")

    # Initialize components
    init_tracing(exporter_type=tracing_exporter, endpoint=tracing_endpoint, sampling_rate=sampling_rate)
    init_metrics(exporter_type=metrics_exporter, endpoint=metrics_endpoint, port=prometheus_port)
    init_logging_correlation()

    # Auto-instrument libraries
    instrument_kafka()
    instrument_redis()

    logger.info("Observability stack initialized")


# Predefined metrics
def create_business_metrics():
    """Create business metrics instruments."""
    meter = get_meter("business")
    return {
        "salience_score_distribution": meter.create_histogram(
            name="salience_score_distribution",
            description="Distribution of salience scores",
            unit="score",
        ),
        "interrupt_rate": meter.create_counter(
            name="interrupt_rate",
            description="Count of interrupts by type",
            unit="interrupt",
        ),
        "mode_transitions": meter.create_counter(
            name="mode_transitions",
            description="Count of mode transitions",
            unit="transition",
        ),
        "policy_evaluation_latency": meter.create_histogram(
            name="policy_evaluation_latency",
            description="Latency of policy evaluations",
            unit="milliseconds",
        ),
        "agent_task_completion_time": meter.create_histogram(
            name="agent_task_completion_time",
            description="Time to complete agent tasks",
            unit="milliseconds",
        ),
        "human_escalation_rate": meter.create_counter(
            name="human_escalation_rate",
            description="Count of human escalations",
            unit="escalation",
        ),
    }


def create_system_metrics():
    """Create system metrics instruments."""
    meter = get_meter("system")
    return {
        "kafka_consumer_lag": meter.create_gauge(
            name="kafka_consumer_lag",
            description="Kafka consumer lag in messages",
            unit="messages",
        ),
        "redis_latency": meter.create_histogram(
            name="redis_latency",
            description="Redis operation latency",
            unit="milliseconds",
        ),
        "postgres_query_duration": meter.create_histogram(
            name="postgres_query_duration",
            description="PostgreSQL query duration",
            unit="milliseconds",
        ),
        "service_error_rate": meter.create_counter(
            name="service_error_rate",
            description="Count of service errors",
            unit="error",
        ),
    }


# Global instances
business_metrics = create_business_metrics()
system_metrics = create_system_metrics()