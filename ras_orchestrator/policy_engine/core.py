"""
Ядро Policy Engine с поддержкой DSL, кэширования, hot-reload и версионирования.
"""
import yaml
import logging
import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Callable, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from common.models import Event, SalienceScore, SystemMode

logger = logging.getLogger(__name__)


class Operator(Enum):
    """Поддерживаемые операторы."""
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # regex


class LogicalOperator(Enum):
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class Condition:
    """Условие с оператором и значением."""
    field: str
    operator: Operator
    value: Any
    negated: bool = False


@dataclass
class LogicalGroup:
    """Логическая группа условий."""
    operator: LogicalOperator
    children: List[Union['LogicalGroup', Condition]] = field(default_factory=list)


@dataclass
class Policy:
    """Политика с метаданными и условиями."""
    name: str
    version: str = "1.0"
    description: str = ""
    enabled: bool = True
    priority: int = 0
    tags: List[str] = field(default_factory=list)
    conditions: LogicalGroup = None
    actions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PolicyParser:
    """Парсер YAML политик в объекты Policy."""

    @staticmethod
    def parse_yaml(file_path: Path) -> List[Policy]:
        """Загружает и парсит YAML файл."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return PolicyParser.parse_dict(data)

    @staticmethod
    def parse_dict(data: Dict) -> List[Policy]:
        """Парсит словарь в список политик."""
        policies = []
        for policy_data in data.get("policies", []):
            try:
                policy = Policy(
                    name=policy_data.get("name", "unnamed"),
                    version=policy_data.get("version", "1.0"),
                    description=policy_data.get("description", ""),
                    enabled=policy_data.get("enabled", True),
                    priority=policy_data.get("priority", 0),
                    tags=policy_data.get("tags", []),
                    actions=policy_data.get("actions", {}),
                    metadata=policy_data.get("metadata", {}),
                )
                # Парсинг условий
                conditions = policy_data.get("conditions", {})
                policy.conditions = PolicyParser._parse_conditions(conditions)
                policies.append(policy)
            except Exception as e:
                logger.error(f"Failed to parse policy {policy_data.get('name')}: {e}")
        return policies

    @staticmethod
    def _parse_conditions(cond: Any) -> LogicalGroup:
        """Рекурсивно парсит условия в логическое дерево."""
        if isinstance(cond, dict):
            # Проверяем наличие логических операторов
            if "all" in cond:
                children = [PolicyParser._parse_conditions(c) for c in cond["all"]]
                return LogicalGroup(operator=LogicalOperator.AND, children=children)
            elif "any" in cond:
                children = [PolicyParser._parse_conditions(c) for c in cond["any"]]
                return LogicalGroup(operator=LogicalOperator.OR, children=children)
            elif "not" in cond:
                child = PolicyParser._parse_conditions(cond["not"])
                return LogicalGroup(operator=LogicalOperator.NOT, children=[child])
            else:
                # Это словарь с одним условием: поле -> оператор: значение
                for field, op_value in cond.items():
                    if isinstance(op_value, dict):
                        for op, val in op_value.items():
                            operator = Operator(op)
                            return Condition(field=field, operator=operator, value=val)
                    else:
                        # Простое равенство
                        return Condition(field=field, operator=Operator.EQ, value=op_value)
        # Если cond список, трактуем как AND
        if isinstance(cond, list):
            children = [PolicyParser._parse_conditions(c) for c in cond]
            return LogicalGroup(operator=LogicalOperator.AND, children=children)
        raise ValueError(f"Unsupported condition format: {cond}")


class PolicyEvaluator:
    """Выполняет оценку политик на основе контекста."""

    def __init__(self):
        self.custom_functions: Dict[str, Callable] = {}

    def register_function(self, name: str, func: Callable):
        """Регистрирует пользовательскую функцию для использования в условиях."""
        self.custom_functions[name] = func

    def evaluate(self, policy: Policy, context: Dict[str, Any]) -> bool:
        """Оценивает политику относительно контекста."""
        if not policy.enabled:
            return False
        return self._evaluate_group(policy.conditions, context)

    def _evaluate_group(self, group: LogicalGroup, context: Dict) -> bool:
        """Оценивает логическую группу."""
        if group.operator == LogicalOperator.AND:
            return all(self._evaluate_child(c, context) for c in group.children)
        elif group.operator == LogicalOperator.OR:
            return any(self._evaluate_child(c, context) for c in group.children)
        elif group.operator == LogicalOperator.NOT:
            return not self._evaluate_child(group.children[0], context)
        else:
            raise ValueError(f"Unknown operator {group.operator}")

    def _evaluate_child(self, child: Union[LogicalGroup, Condition], context: Dict) -> bool:
        if isinstance(child, Condition):
            return self._evaluate_condition(child, context)
        else:
            return self._evaluate_group(child, context)

    def _evaluate_condition(self, cond: Condition, context: Dict) -> bool:
        """Оценивает одно условие."""
        value = self._get_value(context, cond.field)
        result = self._apply_operator(value, cond.operator, cond.value)
        return not result if cond.negated else result

    def _get_value(self, context: Dict, field: str) -> Any:
        """Извлекает значение из контекста по точечному пути."""
        parts = field.split(".")
        current = context
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def _apply_operator(self, left: Any, op: Operator, right: Any) -> bool:
        """Применяет оператор к значениям."""
        if op == Operator.EQ:
            return left == right
        elif op == Operator.NE:
            return left != right
        elif op == Operator.GT:
            return left > right
        elif op == Operator.GE:
            return left >= right
        elif op == Operator.LT:
            return left < right
        elif op == Operator.LE:
            return left <= right
        elif op == Operator.IN:
            return left in right
        elif op == Operator.NOT_IN:
            return left not in right
        elif op == Operator.CONTAINS:
            return right in left if isinstance(left, str) else False
        elif op == Operator.STARTS_WITH:
            return isinstance(left, str) and left.startswith(right)
        elif op == Operator.ENDS_WITH:
            return isinstance(left, str) and left.endswith(right)
        elif op == Operator.MATCHES:
            import re
            return bool(re.match(right, str(left)))
        else:
            raise ValueError(f"Unsupported operator {op}")


class PolicyCache:
    """Кэш скомпилированных политик с инвалидацией по хешу."""

    def __init__(self):
        self._cache: Dict[str, List[Policy]] = {}
        self._hashes: Dict[str, str] = {}
        self._lock = Lock()

    def get(self, file_path: Path) -> Optional[List[Policy]]:
        """Возвращает кэшированные политики, если файл не изменился."""
        with self._lock:
            current_hash = self._compute_hash(file_path)
            cached_hash = self._hashes.get(str(file_path))
            if cached_hash == current_hash:
                return self._cache.get(str(file_path))
        return None

    def set(self, file_path: Path, policies: List[Policy]):
        """Кэширует политики."""
        with self._lock:
            key = str(file_path)
            self._cache[key] = policies
            self._hashes[key] = self._compute_hash(file_path)

    def _compute_hash(self, file_path: Path) -> str:
        """Вычисляет MD5 хеш файла."""
        if not file_path.exists():
            return ""
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()


class PolicyWatcher(FileSystemEventHandler):
    """Отслеживает изменения файлов политик для hot-reload."""

    def __init__(self, engine: 'PolicyEngineCore'):
        self.engine = engine

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(('.yaml', '.yml')):
            logger.info(f"Policy file changed: {event.src_path}, triggering reload")
            self.engine.reload_policies()


class PolicyEngineCore:
    """Основной движок политик с поддержкой hot-reload, кэширования и DSL."""

    def __init__(self, policy_dir: Union[str, Path] = None, watch: bool = False):
        self.policy_dir = Path(policy_dir) if policy_dir else Path(__file__).parent / "policies"
        self.policy_dir.mkdir(exist_ok=True)
        self.parser = PolicyParser()
        self.evaluator = PolicyEvaluator()
        self.cache = PolicyCache()
        self.policies: Dict[str, List[Policy]] = {}  # тип -> список политик
        self.watch = watch
        self.observer = None
        self._load_all_policies()

        if watch:
            self._start_watcher()

    def _load_all_policies(self):
        """Загружает все YAML файлы из директории."""
        self.policies.clear()
        for yaml_file in self.policy_dir.glob("*.yaml"):
            self._load_policy_file(yaml_file)
        for yaml_file in self.policy_dir.glob("*.yml"):
            self._load_policy_file(yaml_file)

    def _load_policy_file(self, file_path: Path):
        """Загружает один файл политик с использованием кэша."""
        cached = self.cache.get(file_path)
        if cached is not None:
            self.policies[file_path.stem] = cached
            logger.debug(f"Loaded {len(cached)} policies from cache for {file_path.name}")
            return

        try:
            policies = self.parser.parse_yaml(file_path)
            self.cache.set(file_path, policies)
            self.policies[file_path.stem] = policies
            logger.info(f"Loaded {len(policies)} policies from {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to load policies from {file_path}: {e}")

    def reload_policies(self):
        """Перезагружает все политики."""
        logger.info("Reloading policies...")
        self._load_all_policies()

    def _start_watcher(self):
        """Запускает watchdog для отслеживания изменений."""
        self.observer = Observer()
        handler = PolicyWatcher(self)
        self.observer.schedule(handler, str(self.policy_dir), recursive=True)
        self.observer.start()
        logger.info(f"Started policy watcher on {self.policy_dir}")

    def stop(self):
        """Останавливает watcher."""
        if self.observer:
            self.observer.stop()
            self.observer.join()

    def evaluate(self, policy_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Оценивает политики заданного типа и возвращает совпавшие."""
        matched = []
        policies = self.policies.get(policy_type, [])
        for policy in sorted(policies, key=lambda p: p.priority, reverse=True):
            if self.evaluator.evaluate(policy, context):
                matched.append({
                    "policy_name": policy.name,
                    "priority": policy.priority,
                    "actions": policy.actions,
                    "metadata": policy.metadata,
                })
        return matched

    def evaluate_interrupt(
        self,
        event: Event,
        salience_score: SalienceScore,
        current_mode: SystemMode,
        active_tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Специализированная оценка для прерываний (обратная совместимость)."""
        context = {
            "event": event.dict(),
            "salience": salience_score.dict(),
            "current_mode": current_mode.value,
            "active_task_count": len(active_tasks),
        }
        matched = self.evaluate("interrupt", context)
        if matched:
            best = matched[0]  # highest priority
            return {
                "should_interrupt": True,
                "reason": best.get("actions", {}).get("reason", "policy_matched"),
                "priority": best["priority"],
                "policy_name": best["policy_name"],
            }
        return {"should_interrupt": False, "reason": "no_policy_matched"}

    def evaluate_mode(self, salience_score: SalienceScore) -> Dict[str, Any]:
        """Специализированная оценка для режимов."""
        context = {"salience": salience_score.dict()}
        matched = self.evaluate("mode", context)
        if matched:
            best = matched[0]
            return {
                "target_mode": best.get("actions", {}).get("target_mode"),
                "reason": best.get("actions", {}).get("reason", "policy_matched"),
                "policy_name": best["policy_name"],
            }
        return {}


# Глобальный экземпляр для удобства
_global_engine: Optional[PolicyEngineCore] = None


def get_global_engine(watch: bool = False) -> PolicyEngineCore:
    """Возвращает глобальный экземпляр движка."""
    global _global_engine
    if _global_engine is None:
        _global_engine = PolicyEngineCore(watch=watch)
    return _global_engine