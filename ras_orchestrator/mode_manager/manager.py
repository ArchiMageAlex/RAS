import logging
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta
from common.models import SystemMode, SalienceScore

logger = logging.getLogger(__name__)


class ModeTransitionReason(str, Enum):
    SALIENCE_HIGH = "salience_high"
    SALIENCE_LOW = "salience_low"
    MANUAL = "manual"
    TIMEOUT = "timeout"
    POLICY = "policy"


class ModeManager:
    """Управляет глобальным режимом системы."""

    def __init__(self, initial_mode: SystemMode = SystemMode.NORMAL):
        self.current_mode = initial_mode
        self.transition_history = []
        self.last_transition_time = datetime.utcnow()
        # Пороги для перехода (можно настраивать)
        self.thresholds = {
            SystemMode.LOW: 0.2,
            SystemMode.NORMAL: 0.5,
            SystemMode.ELEVATED: 0.7,
            SystemMode.CRITICAL: 0.9,
        }
        # Гистерезис: минимальное время между переходами
        self.cooldown = timedelta(seconds=30)

    def evaluate(self, salience_score: SalienceScore) -> SystemMode:
        """Определяет целевой режим на основе salience score."""
        aggregated = salience_score.aggregated

        # Определение режима по порогам
        target_mode = SystemMode.NORMAL
        if aggregated >= self.thresholds[SystemMode.CRITICAL]:
            target_mode = SystemMode.CRITICAL
        elif aggregated >= self.thresholds[SystemMode.ELEVATED]:
            target_mode = SystemMode.ELEVATED
        elif aggregated <= self.thresholds[SystemMode.LOW]:
            target_mode = SystemMode.LOW

        # Проверка гистерезиса по времени
        if datetime.utcnow() - self.last_transition_time < self.cooldown:
            logger.debug("Cooldown active, skipping mode transition.")
            return self.current_mode

        # Если режим изменился, выполняем переход
        if target_mode != self.current_mode:
            self._transition(target_mode, ModeTransitionReason.SALIENCE_HIGH)
        return self.current_mode

    def _transition(self, new_mode: SystemMode, reason: ModeTransitionReason):
        """Выполняет переход в новый режим."""
        old_mode = self.current_mode
        self.current_mode = new_mode
        self.last_transition_time = datetime.utcnow()
        self.transition_history.append({
            "timestamp": self.last_transition_time,
            "from": old_mode,
            "to": new_mode,
            "reason": reason,
        })
        logger.info(f"Mode transition: {old_mode} -> {new_mode} (reason: {reason})")

    def get_current_mode(self) -> SystemMode:
        return self.current_mode

    def get_history(self, limit: int = 10):
        return self.transition_history[-limit:]

    def set_mode_manually(self, new_mode: SystemMode):
        """Ручное переключение режима (например, через административный API)."""
        self._transition(new_mode, ModeTransitionReason.MANUAL)


# Глобальный экземпляр
mode_manager = ModeManager()


def get_mode_manager() -> ModeManager:
    return mode_manager