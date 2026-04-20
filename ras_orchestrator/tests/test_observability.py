"""
Observability tests: метрики, трассировка, логирование.
"""
import pytest
import logging
import time
from unittest.mock import Mock, patch
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from prometheus_client import REGISTRY, Counter, Histogram

from common.telemetry import (
    init_tracing,
    init_metrics,
    init_logging_correlation,
    get_tracer,
    get_meter,
    business_metrics,
    system_metrics,
)
from common.utils import (
    EVENT_COUNTER,
    SALIENCE_SCORE_HISTOGRAM,
    INTERRUPT_DECISION_COUNTER,
    MODE_TRANSITION_COUNTER,
    log_with_context,
    get_correlation_id,
    set_correlation_id,
)


def test_tracing_initialization():
    """Тест инициализации трассировки."""
    # Используем Console exporter для тестов
    with patch('common.telemetry.os.getenv', return_value=None):
        init_tracing(exporter_type="console", sampling_rate=1.0)
        tracer_provider = trace.get_tracer_provider()
        assert isinstance(tracer_provider, TracerProvider)
        tracer = get_tracer("test")
        assert tracer is not None


def test_trace_creation():
    """Тест создания span."""
    init_tracing(exporter_type="console")
    tracer = get_tracer("test")
    with tracer.start_as_current_span("test_span") as span:
        span.set_attribute("test", "value")
        assert span.is_recording()
        ctx = span.get_span_context()
        assert ctx.trace_id is not None
        assert ctx.span_id is not None


def test_metrics_initialization():
    """Тест инициализации метрик."""
    with patch('common.telemetry.os.getenv', return_value=None):
        init_metrics(exporter_type="prometheus", port=0)  # порт 0 чтобы не запускать сервер
        meter_provider = metrics.get_meter_provider()
        assert isinstance(meter_provider, MeterProvider)
        meter = get_meter("test")
        assert meter is not None


def test_business_metrics_exist():
    """Тест, что бизнес-метрики созданы."""
    assert "salience_score_distribution" in business_metrics
    assert "interrupt_rate" in business_metrics
    assert "mode_transitions" in business_metrics
    assert "policy_evaluation_latency" in business_metrics
    assert "agent_task_completion_time" in business_metrics
    assert "human_escalation_rate" in business_metrics


def test_system_metrics_exist():
    """Тест, что системные метрики созданы."""
    assert "kafka_consumer_lag" in system_metrics
    assert "redis_latency" in system_metrics
    assert "postgres_query_duration" in system_metrics
    assert "service_error_rate" in system_metrics


def test_prometheus_metrics():
    """Тест метрик Prometheus (старые)."""
    # Увеличиваем счётчик
    EVENT_COUNTER.labels(event_type="test", severity="low").inc()
    # Проверяем, что метрика есть в регистре
    metric_samples = list(REGISTRY.collect())
    event_metric = None
    for metric in metric_samples:
        if metric.name == "ras_events_total":
            event_metric = metric
            break
    assert event_metric is not None
    # Проверяем labels
    for sample in event_metric.samples:
        if sample.labels.get("event_type") == "test":
            assert sample.value >= 1


def test_histogram_metric():
    """Тест гистограммы."""
    SALIENCE_SCORE_HISTOGRAM.observe(0.75)
    metric_samples = list(REGISTRY.collect())
    hist_metric = None
    for metric in metric_samples:
        if metric.name == "ras_salience_score":
            hist_metric = metric
            break
    assert hist_metric is not None


def test_logging_correlation():
    """Тест корреляции логов с трассировкой."""
    init_logging_correlation()
    # Создаём span
    tracer = get_tracer("test")
    with tracer.start_as_current_span("log_test") as span:
        # Логируем через log_with_context
        logger = logging.getLogger("test_logger")
        with patch.object(logger, 'info') as mock_info:
            log_with_context(logger, "info", "test message", extra_field="extra")
            # Проверяем, что в extra добавлены trace_id и span_id
            call_args = mock_info.call_args
            extra = call_args[1]['extra']
            assert "trace_id" in extra
            assert "span_id" in extra
            assert extra["trace_id"] == format(span.get_span_context().trace_id, "032x")
            assert extra["span_id"] == format(span.get_span_context().span_id, "016x")


def test_correlation_id_baggage():
    """Тест работы с correlation ID в baggage."""
    # Устанавливаем correlation ID
    cid = "test-correlation-123"
    set_correlation_id(cid)
    # Получаем
    retrieved = get_correlation_id()
    assert retrieved == cid


def test_metric_record():
    """Тест записи метрик через OpenTelemetry."""
    init_metrics(exporter_type="prometheus", port=0)
    meter = get_meter("test_metric")
    counter = meter.create_counter("test_counter")
    counter.add(5, {"label": "value"})
    # Поскольку мы используем PrometheusMetricReader, метрики будут доступны через REGISTRY
    # Но для простоты просто проверяем, что исключений нет
    # Можно также использовать InMemoryMetricReader для проверки значений
    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[reader])
    with patch('common.telemetry.get_meter_provider', return_value=meter_provider):
        meter2 = get_meter("test2")
        counter2 = meter2.create_counter("test_counter2")
        counter2.add(10)
        # Собираем метрики
        metrics_data = reader.get_metrics_data()
        assert len(metrics_data.resource_metrics) > 0


def test_trace_propagation():
    """Тест распространения trace через компоненты."""
    init_tracing(exporter_type="console")
    tracer = get_tracer("propagation")
    with tracer.start_as_current_span("parent") as parent:
        parent_context = trace.get_current_span().get_span_context()
        # Симулируем передачу контекста другому компоненту
        with tracer.start_as_current_span("child", context=trace.set_span_in_context(parent)):
            child_context = trace.get_current_span().get_span_context()
            # Trace ID должен совпадать
            assert child_context.trace_id == parent_context.trace_id
            # Span ID разный
            assert child_context.span_id != parent_context.span_id


def test_logging_without_trace():
    """Тест логирования без активного span."""
    logger = logging.getLogger("no_trace")
    with patch.object(logger, 'info') as mock_info:
        log_with_context(logger, "info", "no trace")
        # Должен быть вызов без trace_id/span_id
        call_args = mock_info.call_args
        extra = call_args[1]['extra']
        assert "trace_id" not in extra
        assert "span_id" not in extra


def test_observability_integration():
    """
    Интеграционный тест observability: создание события, запись метрик, трассировка.
    """
    init_tracing(exporter_type="console")
    init_metrics(exporter_type="prometheus", port=0)
    init_logging_correlation()

    tracer = get_tracer("integration")
    meter = get_meter("integration")

    with tracer.start_as_current_span("integration_span") as span:
        span.set_attribute("component", "salience_engine")
        # Записываем бизнес-метрику
        business_metrics["salience_score_distribution"].record(0.8)
        # Записываем системную метрику
        system_metrics["service_error_rate"].add(1, {"service": "test"})
        # Логируем
        logger = logging.getLogger("integration")
        with patch.object(logger, 'info') as mock_info:
            log_with_context(logger, "info", "integration test")
            mock_info.assert_called_once()

    # Проверяем, что span завершён
    assert span.is_recording() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])