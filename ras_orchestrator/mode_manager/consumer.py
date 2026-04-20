"""
Consumer для Mode Manager.
Подписывается на Kafka топик salience_scores и обновляет режим системы.
"""
import logging
import time
from common.utils import setup_logging
from common.telemetry import init_observability, get_tracer, business_metrics
from .manager import get_mode_manager

# Initialize observability
init_observability()

setup_logging()
logger = logging.getLogger(__name__)
tracer = get_tracer("mode_manager")

manager = get_mode_manager()

def process_salience_score(score):
    """Обработка salience score и обновление режима."""
    with tracer.start_as_current_span("process_salience_score") as span:
        span.set_attribute("salience.score", score.aggregated)
        try:
            new_mode = manager.evaluate(score)
            span.set_attribute("new_mode", new_mode.value)
            business_metrics["mode_transitions"].add(1, {"from": manager.current_mode.value, "to": new_mode.value})
            logger.info(f"Mode evaluated: {new_mode}")
        except Exception as e:
            logger.error(f"Error evaluating mode: {e}")
            span.record_exception(e)
            business_metrics["service_error_rate"].add(1)
            raise

def simulate_consumption():
    """Симуляция потребления salience scores (для демо)."""
    from common.models import SalienceScore
    import random

    while True:
        # Создаём тестовый salience score
        score = SalienceScore(
            relevance=random.uniform(0, 1),
            novelty=random.uniform(0, 1),
            risk=random.uniform(0, 1),
            urgency=random.uniform(0, 1),
            uncertainty=random.uniform(0, 1),
            aggregated=random.uniform(0, 1),
        )
        process_salience_score(score)
        time.sleep(5)

if __name__ == "__main__":
    logger.info("Mode Manager consumer started with observability.")
    simulate_consumption()