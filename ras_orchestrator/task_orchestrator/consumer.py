"""
Consumer для Task Orchestrator (заглушка).
В реальности будет подписываться на топик interrupt_decisions,
создавать задачи и назначать агентов.
"""
import logging
import time
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Task Orchestrator consumer started (simulated).")
    while True:
        time.sleep(10)
        logger.debug("Task Orchestrator heartbeat")