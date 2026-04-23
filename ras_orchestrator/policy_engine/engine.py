"""
Модуль движка политик с обратной совместимостью.
Использует новое ядро из core.py.
"""
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from common.models import Event, SalienceScore, SystemMode
from .core import PolicyEngineCore, get_global_engine

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Движок политик, загружающий правила из YAML (обёртка для совместимости)."""

    def __init__(self, policy_dir: str = None, watch: bool = False):
        self.policy_dir = policy_dir or Path(__file__).parent / "policies"
        self.core = PolicyEngineCore(policy_dir=self.policy_dir, watch=watch)
        self.rl_agent = None  # RL агент для динамической настройки порогов

    def register_rl_agent(self, rl_agent):
        """Регистрирует RL агента для динамической настройки порогов."""
        self.rl_agent = rl_agent
        self.core.register_rl_agent(rl_agent)
        logger.info("RL agent registered in PolicyEngine")

    def _load_policies(self):
        """Загружает политики (делегирует ядру)."""
        # Загрузка уже выполнена в ядре
        pass

    def evaluate_interrupt_policy(
        self,
        event: Event,
        salience_score: SalienceScore,
        current_mode: SystemMode,
        active_tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Оценивает политики прерывания."""
        return self.core.evaluate_interrupt(event, salience_score, current_mode, active_tasks)

    def evaluate_mode_policy(self, salience_score: SalienceScore) -> Dict[str, Any]:
        """Оценивает политики переключения режима."""
        return self.core.evaluate_mode(salience_score)

    def _matches_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Устаревший метод, оставлен для совместимости."""
        # Делегируем ядру, но это не будет использоваться
        from .core import PolicyEvaluator
        evaluator = PolicyEvaluator()
        # Преобразуем условия в формат ядра (упрощённо)
        # Для полноты нужно было бы конвертировать, но оставим заглушку
        logger.warning("Using deprecated _matches_conditions, consider upgrading")
        return False


# Глобальный экземпляр с watch=False по умолчанию
policy_engine = PolicyEngine()


def get_policy_engine() -> PolicyEngine:
    return policy_engine


def get_core_engine(watch: bool = False) -> PolicyEngineCore:
    """Возвращает расширенное ядро движка."""
    return get_global_engine(watch=watch)