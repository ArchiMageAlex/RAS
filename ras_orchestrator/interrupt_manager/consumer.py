"""
Consumer для Interrupt Manager (заглушка).
В реальности будет подписываться на топик salience_scores и mode_updates,
принимать решения о прерывании и публиковать в топик interrupt_decisions.
"""
import logging
import time
from common.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Interrupt Manager consumer started (simulated).")
    while True:
        time.sleep(10)
        logger.debug("Interrupt Manager heartbeat")