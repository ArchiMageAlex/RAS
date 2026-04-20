"""
Consumer для Salience Engine (заглушка).
В реальности будет подписываться на топик raw_events, вычислять salience score
и публиковать в топик salience_scores.
"""
import logging
import time
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Salience Engine consumer started (simulated).")
    while True:
        time.sleep(10)
        logger.debug("Salience Engine heartbeat")