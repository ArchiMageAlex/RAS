"""
Точка входа для Predictive Engine.
"""
import warnings
# Подавление RuntimeWarning для модуля predictive_engine и всех RuntimeWarning
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="predictive_engine")

import asyncio
import logging
from predictive_engine.engine import PredictiveEngine

logger = logging.getLogger(__name__)

async def main():
    """Основная функция запуска Predictive Engine."""
    logger.info("Starting Predictive Engine...")
    
    # Инициализация движка
    engine = PredictiveEngine()
    
    # Проверяем наличие метода initialize (асинхронного или синхронного)
    if hasattr(engine, 'initialize'):
        if asyncio.iscoroutinefunction(engine.initialize):
            await engine.initialize()
        else:
            engine.initialize()
    
    logger.info("Predictive Engine started successfully.")
    
    # Основной цикл (заглушка - можно заменить на реальную логику)
    # Если движок имеет метод run или start, используем его
    if hasattr(engine, 'run'):
        if asyncio.iscoroutinefunction(engine.run):
            await engine.run()
        else:
            engine.run()
    elif hasattr(engine, 'start'):
        if asyncio.iscoroutinefunction(engine.start):
            await engine.start()
        else:
            engine.start()
    else:
        # Если нет методов run/start, просто ждем
        logger.info("Predictive Engine running. Press Ctrl+C to stop.")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
    
    logger.info("Predictive Engine stopped.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())