"""
Consumer для Salience Engine.
Подписывается на топик raw_events, вычисляет salience score
и публикует в топик salience_scores.
"""
import logging
import time
from common.utils import setup_logging
from common.telemetry import init_observability, get_tracer, business_metrics
from .engine import get_salience_engine

# Initialize observability
init_observability()

setup_logging()
logger = logging.getLogger(__name__)
tracer = get_tracer("salience_consumer")

engine = get_salience_engine()

def process_event(event):
    """Обработка одного события."""
    with tracer.start_as_current_span("process_event") as span:
        span.set_attribute("event.id", event.event_id)
        try:
            score = engine.compute(event)
            # Здесь должна быть публикация в Kafka
            # await produce_salience_score(event.event_id, score)
            business_metrics["interrupt_rate"].add(1, {"type": "event_processed"})
            logger.info(f"Processed event {event.event_id}, score: {score.aggregated:.3f}")
        except Exception as e:
            logger.error(f"Error processing event {event.event_id}: {e}")
            span.record_exception(e)
            business_metrics["service_error_rate"].add(1)
            raise

def simulate_consumption():
    """Симуляция потребления событий (для демо)."""
    from common.models import Event, EventType, Severity
    import uuid
    from datetime import datetime

    while True:
        # Создаём тестовое событие
        event = Event(
            event_id=str(uuid.uuid4()),
            type=EventType.SECURITY_ALERT,
            severity=Severity.HIGH,
            source="simulator",
            timestamp=datetime.utcnow(),
            payload={"confidence": 0.9},
            metadata={},
        )
        process_event(event)
        time.sleep(5)

if __name__ == "__main__":
    logger.info("Salience Engine consumer started with observability.")
    simulate_consumption()