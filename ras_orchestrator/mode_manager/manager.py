import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from common.models import SystemMode, SalienceScore, SystemMetrics

logger = logging.getLogger(__name__)


class ModeTransitionReason(str, Enum):
    SALIENCE_HIGH = "salience_high"
    SALIENCE_LOW = "salience_low"
    MANUAL = "manual"
    TIMEOUT = "timeout"
    POLICY = "policy"
    SYSTEM_METRICS = "system_metrics"
    COOLDOWN_EXPIRED = "cooldown_expired"


class ModeStateMachine:
    """
    Конечный автомат для управления режимами с гистерезисом.
    Определяет допустимые переходы между режимами.
    """
    # Матрица переходов: from_mode -> to_mode -> разрешён
    TRANSITIONS = {
        SystemMode.LOW: {SystemMode.NORMAL: True, SystemMode.ELEVATED: False, SystemMode.CRITICAL: False},
        SystemMode.NORMAL: {SystemMode.LOW: True, SystemMode.ELEVATED: True, SystemMode.CRITICAL: True},
        SystemMode.ELEVATED: {SystemMode.NORMAL: True, SystemMode.CRITICAL: True, SystemMode.LOW: False},
        SystemMode.CRITICAL: {SystemMode.ELEVATED: True, SystemMode.NORMAL: False, SystemMode.LOW: False},
    }

    @classmethod
    def can_transition(cls, from_mode: SystemMode, to_mode: SystemMode) -> bool:
        """Проверяет, разрешён ли переход."""
        if from_mode == to_mode:
            return True
        return cls.TRANSITIONS.get(from_mode, {}).get(to_mode, False)


class ModeManager:
    """Улучшенный менеджер режимов с гистерезисом, cooldown и системными метриками."""

    def __init__(
        self,
        initial_mode: SystemMode = SystemMode.NORMAL,
        hysteresis_up: float = 0.05,
        hysteresis_down: float = 0.03,
        cooldown_after_critical: timedelta = timedelta(minutes=5),
    ):
        self.current_mode = initial_mode
        self.transition_history: List[Dict[str, Any]] = []
        self.last_transition_time = datetime.utcnow()
        self.state_machine = ModeStateMachine()

        # Пороги для перехода (базовые)
        self.base_thresholds = {
            SystemMode.LOW: 0.2,
            SystemMode.NORMAL: 0.5,
            SystemMode.ELEVATED: 0.7,
            SystemMode.CRITICAL: 0.9,
        }
        # Гистерезис: разные пороги для повышения и понижения
        self.hysteresis_up = hysteresis_up   # дополнительный порог для повышения
        self.hysteresis_down = hysteresis_down  # дополнительный порог для понижения

        # Cooldown после critical режима
        self.cooldown_after_critical = cooldown_after_critical
        self.critical_exit_time: Optional[datetime] = None

        # Минимальное время между любыми переходами
        self.min_transition_interval = timedelta(seconds=30)

        # Системные метрики (текущие)
        self.system_metrics: Optional[SystemMetrics] = None

        # Приоритет ручного переключения (если True, автоматические переходы блокируются)
        self.manual_lock = False

    def update_system_metrics(self, metrics: SystemMetrics):
        """Обновляет системные метрики для корректировки порогов."""
        self.system_metrics = metrics

    def _adjust_thresholds(self) -> Dict[SystemMode, float]:
        """Корректирует пороги на основе системных метрик."""
        adjusted = self.base_thresholds.copy()
        if not self.system_metrics:
            return adjusted

        # Пример корректировки: при высокой нагрузке снижаем порог для elevated и critical
        load_factor = self.system_metrics.cpu_load
        error_factor = self.system_metrics.error_rate

        # Чем выше нагрузка, тем чувствительнее система (пороги понижаются)
        for mode in [SystemMode.ELEVATED, SystemMode.CRITICAL]:
            adjusted[mode] = max(0.1, adjusted[mode] - load_factor * 0.1 - error_factor * 0.05)

        # При низкой нагрузке можно повысить порог для low
        adjusted[SystemMode.LOW] = min(0.5, adjusted[SystemMode.LOW] + (1 - load_factor) * 0.1)

        return adjusted

    def evaluate(
        self,
        salience_score: SalienceScore,
        system_metrics: Optional[SystemMetrics] = None,
    ) -> SystemMode:
        """
        Определяет целевой режим на основе salience score и системных метрик.
        Возвращает текущий режим после возможного перехода.
        """
        if system_metrics:
            self.update_system_metrics(system_metrics)

        if self.manual_lock:
            logger.debug("Manual lock active, skipping automatic transition.")
            return self.current_mode

        aggregated = salience_score.aggregated
        adjusted_thresholds = self._adjust_thresholds()

        # Определение целевого режима с учётом гистерезиса
        target_mode = self._determine_target_mode(aggregated, adjusted_thresholds)

        # Проверка cooldown после critical
        if self._is_in_critical_cooldown():
            logger.debug("Critical cooldown active, blocking transitions to critical.")
            if target_mode == SystemMode.CRITICAL:
                target_mode = SystemMode.ELEVATED  # понижаем до elevated

        # Проверка минимального интервала между переходами
        if datetime.utcnow() - self.last_transition_time < self.min_transition_interval:
            logger.debug("Min transition interval not reached, skipping.")
            return self.current_mode

        # Проверка допустимости перехода по state machine
        if not self.state_machine.can_transition(self.current_mode, target_mode):
            logger.warning(
                f"Transition from {self.current_mode} to {target_mode} is not allowed by state machine."
            )
            return self.current_mode

        # Если режим изменился, выполняем переход
        if target_mode != self.current_mode:
            reason = ModeTransitionReason.SALIENCE_HIGH
            if system_metrics and system_metrics.error_rate > 0.5:
                reason = ModeTransitionReason.SYSTEM_METRICS
            self._transition(target_mode, reason)

        return self.current_mode

    def _determine_target_mode(self, aggregated: float, thresholds: Dict[SystemMode, float]) -> SystemMode:
        """
        Определяет целевой режим с гистерезисом.
        """
        current = self.current_mode
        # Пороги для повышения (более строгие)
        up_thresholds = {
            SystemMode.ELEVATED: thresholds[SystemMode.ELEVATED] + self.hysteresis_up,
            SystemMode.CRITICAL: thresholds[SystemMode.CRITICAL] + self.hysteresis_up,
        }
        # Пороги для понижения (более мягкие)
        down_thresholds = {
            SystemMode.LOW: thresholds[SystemMode.LOW] - self.hysteresis_down,
            SystemMode.NORMAL: thresholds[SystemMode.NORMAL] - self.hysteresis_down,
        }

        # Логика определения
        if aggregated >= up_thresholds[SystemMode.CRITICAL]:
            return SystemMode.CRITICAL
        elif aggregated >= up_thresholds[SystemMode.ELEVATED]:
            return SystemMode.ELEVATED
        elif aggregated <= down_thresholds[SystemMode.LOW]:
            return SystemMode.LOW
        elif aggregated <= down_thresholds[SystemMode.NORMAL]:
            return SystemMode.NORMAL
        else:
            # Остаёмся в текущем режиме (зона гистерезиса)
            return current

    def _is_in_critical_cooldown(self) -> bool:
        """Проверяет, активен ли cooldown после выхода из critical режима."""
        if self.critical_exit_time is None:
            return False
        cooldown_end = self.critical_exit_time + self.cooldown_after_critical
        return datetime.utcnow() < cooldown_end

    def _transition(self, new_mode: SystemMode, reason: ModeTransitionReason):
        """Выполняет переход в новый режим."""
        old_mode = self.current_mode
        self.current_mode = new_mode
        now = datetime.utcnow()
        self.last_transition_time = now

        # Обновляем время выхода из critical
        if old_mode == SystemMode.CRITICAL:
            self.critical_exit_time = now

        self.transition_history.append({
            "timestamp": now,
            "from": old_mode,
            "to": new_mode,
            "reason": reason.value,
            "system_metrics": self.system_metrics.__dict__ if self.system_metrics else None,
        })
        logger.info(f"Mode transition: {old_mode} -> {new_mode} (reason: {reason})")

    def get_current_mode(self) -> SystemMode:
        return self.current_mode

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.transition_history[-limit:]

    def set_mode_manually(self, new_mode: SystemMode, lock: bool = False):
        """
        Ручное переключение режима.
        Если lock=True, блокирует автоматические переходы до снятия блокировки.
        """
        self.manual_lock = lock
        self._transition(new_mode, ModeTransitionReason.MANUAL)

    def release_manual_lock(self):
        """Снимает блокировку ручного переключения."""
        self.manual_lock = False
        logger.info("Manual lock released.")

    def get_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус менеджера."""
        return {
            "current_mode": self.current_mode.value,
            "manual_lock": self.manual_lock,
            "last_transition": self.transition_history[-1] if self.transition_history else None,
            "system_metrics": self.system_metrics.__dict__ if self.system_metrics else None,
            "in_critical_cooldown": self._is_in_critical_cooldown(),
        }


# Глобальный экземпляр
mode_manager = ModeManager()


def get_mode_manager() -> ModeManager:
    return mode_manager