"""
Схемы валидации для политик.
"""
import logging
import yaml
from typing import Dict, Any, List
from pathlib import Path

# jsonschema - optional dependency
jsonschema = None

def _import_jsonschema():
    """Lazy import of jsonschema."""
    global jsonschema
    if jsonschema is not None:
        return
    import jsonschema as _jsonschema
    jsonschema = _jsonschema

logger = logging.getLogger(__name__)

# JSON Schema для политики
POLICY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "version": {"type": "string", "default": "1.0"},
        "description": {"type": "string"},
        "policies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "version": {"type": "string"},
                    "description": {"type": "string"},
                    "enabled": {"type": "boolean", "default": True},
                    "priority": {"type": "integer", "minimum": 0, "maximum": 100},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "conditions": {
                        "type": ["object", "array"],
                        "oneOf": [
                            {"$ref": "#/definitions/conditionGroup"},
                            {"$ref": "#/definitions/conditionLeaf"}
                        ]
                    },
                    "actions": {"type": "object"},
                    "metadata": {"type": "object"}
                },
                "required": ["name", "conditions"],
                "additionalProperties": True
            }
        }
    },
    "required": ["policies"],
    "definitions": {
        "conditionLeaf": {
            "type": "object",
            "additionalProperties": {
                "type": ["string", "number", "boolean", "object"]
            }
        },
        "conditionGroup": {
            "type": "object",
            "properties": {
                "all": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/conditionNode"}
                },
                "any": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/conditionNode"}
                },
                "not": {"$ref": "#/definitions/conditionNode"}
            },
            "additionalProperties": False
        },
        "conditionNode": {
            "type": ["object", "array"],
            "oneOf": [
                {"$ref": "#/definitions/conditionGroup"},
                {"$ref": "#/definitions/conditionLeaf"}
            ]
        }
    }
}

# Специфичные схемы для типов политик
INTERRUPT_POLICY_ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["interrupt", "delay", "ignore"]},
        "reason": {"type": "string"},
        "priority": {"type": "integer"},
        "checkpoint": {"type": "boolean"}
    },
    "required": ["action"]
}

MODE_POLICY_ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "target_mode": {"type": "string", "enum": ["critical", "elevated", "normal", "low", "idle"]},
        "reason": {"type": "string"},
        "hysteresis": {"type": "number", "minimum": 0}
    },
    "required": ["target_mode"]
}

ACTION_POLICY_ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "allowed_actions": {"type": "array", "items": {"type": "string"}},
        "denied_actions": {"type": "array", "items": {"type": "string"}},
        "require_approval": {"type": "boolean"}
    }
}

TOOL_ACCESS_POLICY_ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "allowed_tools": {"type": "array", "items": {"type": "string"}},
        "denied_tools": {"type": "array", "items": {"type": "string"}},
        "max_usage": {"type": "integer"}
    }
}

HUMAN_ESCALATION_POLICY_ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "escalation_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "notify_channels": {"type": "array", "items": {"type": "string"}},
        "timeout_seconds": {"type": "integer"}
    }
}

ROUTING_POLICY_ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "target_component": {"type": "string"},
        "load_balancing": {"type": "string", "enum": ["round_robin", "least_load", "priority"]},
        "fallback": {"type": "string"}
    }
}


class PolicyValidator:
    """Валидатор политик по схемам."""

    def __init__(self):
        self.schemas = {
            "interrupt": INTERRUPT_POLICY_ACTIONS_SCHEMA,
            "mode": MODE_POLICY_ACTIONS_SCHEMA,
            "action": ACTION_POLICY_ACTIONS_SCHEMA,
            "tool_access": TOOL_ACCESS_POLICY_ACTIONS_SCHEMA,
            "human_escalation": HUMAN_ESCALATION_POLICY_ACTIONS_SCHEMA,
            "routing": ROUTING_POLICY_ACTIONS_SCHEMA,
        }

    def validate_file(self, file_path: Path, policy_type: str = None) -> List[str]:
        """Валидирует YAML файл и возвращает список ошибок."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [f"YAML parsing error: {e}"]

        errors = []
        # Базовая валидация по общей схеме
        try:
            _import_jsonschema()
            if jsonschema:
                jsonschema.validate(instance=data, schema=POLICY_SCHEMA)
        except Exception as e:
            errors.append(f"Schema validation error: {e}")

        # Валидация действий по типу политики
        if policy_type and policy_type in self.schemas:
            for i, policy in enumerate(data.get("policies", [])):
                actions = policy.get("actions", {})
                try:
                    _import_jsonschema()
                    if jsonschema:
                        jsonschema.validate(instance=actions, schema=self.schemas[policy_type])
                except Exception as e:
                    errors.append(f"Policy '{policy.get('name')}' actions validation error: {e}")

        # Семантическая валидация
        errors.extend(self._semantic_validation(data))

        return errors

    def _semantic_validation(self, data: Dict) -> List[str]:
        """Дополнительная семантическая проверка."""
        errors = []
        policies = data.get("policies", [])
        seen_names = set()
        for policy in policies:
            name = policy.get("name")
            if name in seen_names:
                errors.append(f"Duplicate policy name: {name}")
            seen_names.add(name)

            # Проверка приоритета в диапазоне
            priority = policy.get("priority", 0)
            if not (0 <= priority <= 100):
                errors.append(f"Policy '{name}' priority {priority} out of range [0,100]")

            # Проверка условий на наличие полей
            conditions = policy.get("conditions", {})
            if not conditions:
                errors.append(f"Policy '{name}' has empty conditions")
        return errors


# Глобальный экземпляр валидатора
validator = PolicyValidator()