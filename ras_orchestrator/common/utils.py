import logging
import sys
from prometheus_client import Counter, Histogram, start_http_server

# Импорт новой конфигурации логирования
from .logging_config import setup_logging, get_logger

# Настройка JSON-логирования (обратная совместимость)
def setup_logging_old(level=logging.INFO):
    """
    Устаревшая функция, используйте setup_logging из logging_config.
    """
    logging.warning("setup_logging_old is deprecated, use setup_logging from logging_config")
    return setup_logging()


# Метрики Prometheus (старые, для обратной совместимости)
EVENT_COUNTER = Counter(
    "ras_events_total",
    "Total number of events ingested",
    ["event_type", "severity"]
)

SALIENCE_SCORE_HISTOGRAM = Histogram(
    "ras_salience_score",
    "Salience score distribution",
    buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
)

INTERRUPT_DECISION_COUNTER = Counter(
    "ras_interrupt_decisions_total",
    "Total interrupt decisions",
    ["decision", "reason"]
)

MODE_TRANSITION_COUNTER = Counter(
    "ras_mode_transitions_total",
    "Total mode transitions",
    ["from", "to"]
)


def start_metrics_server(port=9090):
    """Запускает HTTP-сервер для метрик Prometheus."""
    start_http_server(port)
    logging.info(f"Metrics server started on port {port}")


# Утилиты для работы с контекстом
def get_correlation_id():
    """
    Получает correlation ID из текущего контекста OpenTelemetry baggage.
    """
    from opentelemetry import baggage
    return baggage.get_baggage("correlation_id")


def set_correlation_id(cid: str):
    """
    Устанавливает correlation ID в baggage OpenTelemetry.
    """
    from opentelemetry import baggage
    import opentelemetry.context as context
    ctx = baggage.set_baggage("correlation_id", cid)
    context.attach(ctx)
    return cid


def log_with_context(logger, level, message, **kwargs):
    """
    Логирует сообщение с добавлением контекста (trace_id, span_id, correlation_id).
    """
    extra = {}
    from opentelemetry import trace
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        extra["trace_id"] = format(ctx.trace_id, "032x")
        extra["span_id"] = format(ctx.span_id, "016x")
    cid = get_correlation_id()
    if cid:
        extra["correlation_id"] = cid
    extra.update(kwargs)
    if level == "debug":
        logger.debug(message, extra=extra)
    elif level == "info":
        logger.info(message, extra=extra)
    elif level == "warning":
        logger.warning(message, extra=extra)
    elif level == "error":
        logger.error(message, extra=extra)
    elif level == "critical":
        logger.critical(message, extra=extra)
    else:
        logger.info(message, extra=extra)