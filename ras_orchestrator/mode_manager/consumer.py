"""
Consumer для Mode Manager (заглушка).
В реальности этот сервис будет подписываться на Kafka топик salience_scores
и обновлять режим системы.
"""
import logging
import time
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Mode Manager consumer started (simulated).")
    while True:
        time.sleep(10)
        logger.debug("Mode Manager heartbeat")