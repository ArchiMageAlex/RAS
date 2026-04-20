"""
Consumer для Retriever Agent (заглушка).
В реальности будет подписываться на топик tasks, выполнять retrieval-действия
и публиковать результаты.
"""
import logging
import time
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Retriever Agent consumer started (simulated).")
    while True:
        time.sleep(10)
        logger.debug("Retriever Agent heartbeat")