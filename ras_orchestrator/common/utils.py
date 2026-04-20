import logging
import sys
from pythonjsonlogger import jsonlogger
from prometheus_client import Counter, Histogram, start_http_server

# Настройка JSON-логирования
def setup_logging(level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


# Метрики Prometheus
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