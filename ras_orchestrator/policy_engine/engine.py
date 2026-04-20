import yaml
import logging
from typing import Dict, Any, List
from pathlib import Path
from common.models import Event, SalienceScore, SystemMode

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Движок политик, загружающий правила из YAML."""

    def __init__(self, policy_dir: str = None):
        self.policy_dir = policy_dir or Path(__file__).parent / "policies"
        self.interrupt_policies = []
        self.mode_policies = []
        self._load_policies()

    def _load_policies(self):
        """Загружает политики из YAML файлов."""
        interrupt_path = self.policy_dir / "interrupt_policies.yaml"
        if interrupt_path.exists():
            with open(interrupt_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.interrupt_policies = data.get("policies", [])
                logger.info(f"Loaded {len(self.interrupt_policies)} interrupt policies")
        else:
            logger.warning(f"Interrupt policies file not found: {interrupt_path}")

        mode_path = self.policy_dir / "mode_policies.yaml"
        if mode_path.exists():
            with open(mode_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.mode_policies = data.get("policies", [])
                logger.info(f"Loaded {len(self.mode_policies)} mode policies")
        else:
            logger.warning(f"Mode policies file not found: {mode_path}")

    def evaluate_interrupt_policy(
        self,
        event: Event,
        salience_score: SalienceScore,
        current_mode: SystemMode,
        active_tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Оценивает политики прерывания."""
        context = {
            "event": event.dict(),
            "salience": salience_score.dict(),
            "current_mode": current_mode.value,
            "active_task_count": len(active_tasks),
        }
        for policy in self.interrupt_policies:
            if self._matches_conditions(policy.get("conditions", {}), context):
                logger.info(f"Interrupt policy matched: {policy.get('name')}")
                return {
                    "should_interrupt": True,
                    "reason": policy.get("reason", "policy_matched"),
                    "priority": policy.get("priority", 1),
                    "policy_name": policy.get("name"),
                }
        return {"should_interrupt": False, "reason": "no_policy_matched"}

    def evaluate_mode_policy(self, salience_score: SalienceScore) -> Dict[str, Any]:
        """Оценивает политики переключения режима."""
        context = {"salience": salience_score.dict()}
        for policy in self.mode_policies:
            if self._matches_conditions(policy.get("conditions", {}), context):
                logger.info(f"Mode policy matched: {policy.get('name')}")
                return {
                    "target_mode": policy.get("target_mode"),
                    "reason": policy.get("reason", "policy_matched"),
                    "policy_name": policy.get("name"),
                }
        return {}

    def _matches_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Проверяет, удовлетворяются ли условия."""
        for key, expected in conditions.items():
            # Простая логика: поддерживаем только прямое равенство и сравнение >, <
            value = self._get_nested(context, key)
            if isinstance(expected, dict):
                # Обработка операторов
                for op, op_value in expected.items():
                    if op == "gt":
                        if not (isinstance(value, (int, float)) and value > op_value):
                            return False
                    elif op == "lt":
                        if not (isinstance(value, (int, float)) and value < op_value):
                            return False
                    elif op == "eq":
                        if value != op_value:
                            return False
                    else:
                        logger.warning(f"Unsupported operator {op}")
                        return False
            else:
                if value != expected:
                    return False
        return True

    def _get_nested(self, d: Dict, key: str):
        """Получает значение по точечному пути."""
        parts = key.split(".")
        current = d
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


# Глобальный экземпляр
policy_engine = PolicyEngine()


def get_policy_engine() -> PolicyEngine:
    return policy_engine