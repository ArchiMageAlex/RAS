"""
Consumer для Interrupt Manager.
Подписывается на топик salience_scores и mode_updates,
принимает решения о прерывании и публикует в топик interrupt_decisions.
"""
import logging
import time
from common.utils import setup_logging
from common.telemetry import init_observability, get_tracer, business_metrics
from .manager import get_interrupt_manager
from common.models import Event, EventType, Severity, SalienceScore, SystemMode
from datetime import datetime

# Initialize observability
init_observability()

setup_logging()
logger = logging.getLogger(__name__)
tracer = get_tracer("interrupt_manager")

manager = get_interrupt_manager()

def process_event(event, salience_score, current_mode):
    """Обработка события и принятие решения о прерывании."""
    with tracer.start_as_current_span("process_interrupt_decision") as span:
        span.set_attribute("event.id", event.event_id)
        span.set_attribute("salience.score", salience_score.aggregated)
        span.set_attribute("current_mode", current_mode.value)
        try:
            decision = manager.evaluate(event, salience_score, current_mode, active_tasks=[])
            span.set_attribute("interrupt.decision", decision.should_interrupt)
            span.set_attribute("interrupt.reason", decision.reason)
            if decision.should_interrupt:
                business_metrics["interrupt_rate"].add(1, {"type": decision.interrupt_type.value})
            logger.info(f"Interrupt decision: {decision.should_interrupt} ({decision.reason})")
        except Exception as e:
            logger.error(f"Error evaluating interrupt: {e}")
            span.record_exception(e)
            business_metrics["service_error_rate"].add(1)
            raise

def simulate_consumption():
    """Симуляция потребления событий (для демо)."""
    import random
    import uuid

    while True:
        # Создаём тестовое событие
        event = Event(
            event_id=str(uuid.uuid4()),
            type=random.choice(list(EventType)),
            severity=random.choice(list(Severity)),
            source="simulator",
            timestamp=datetime.utcnow(),
            payload={"confidence": random.uniform(0.5, 1.0)},
            metadata={},
        )
        salience_score = SalienceScore(
            relevance=random.uniform(0, 1),
            novelty=random.uniform(0, 1),
            risk=random.uniform(0, 1),
            urgency=random.uniform(0, 1),
            uncertainty=random.uniform(0, 1),
            aggregated=random.uniform(0, 1),
        )
        current_mode = random.choice(list(SystemMode))
        process_event(event, salience_score, current_mode)
        time.sleep(5)

if __name__ == "__main__":
    logger.info("Interrupt Manager consumer started with observability.")
    simulate_consumption()