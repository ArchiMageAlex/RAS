"""
Точка входа для Homeostatic Controller.
"""
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="homeostatic_controller")

import asyncio
import logging
from .controller import HomeostaticController

logger = logging.getLogger(__name__)

async def main():
    controller = HomeostaticController()
    await controller.initialize()
    logger.info("Homeostatic Controller started.")
    try:
        while True:
            await controller.update()
            await asyncio.sleep(controller.update_interval)
    except asyncio.CancelledError:
        pass
    finally:
        await controller.shutdown()

if __name__ == "__main__":
    asyncio.run(main())