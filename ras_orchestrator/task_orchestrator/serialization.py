"""
Serialization utilities for checkpoint state.
Supports pickle (for complex objects) and JSON (for simple dicts).
"""

import pickle
import json
import logging
from typing import Any, Dict, Optional
import base64

logger = logging.getLogger(__name__)


class SerializationError(Exception):
    """Ошибка сериализации/десериализации."""
    pass


class StateSerializer:
    """Сериализатор состояния агента."""

    @staticmethod
    def serialize(state: Any, format: str = "pickle") -> bytes:
        """
        Сериализует состояние в bytes.

        Параметры:
            state: объект состояния (любой)
            format: 'pickle' или 'json'

        Возвращает:
            bytes сериализованного состояния
        """
        if format == "pickle":
            try:
                return pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
            except (pickle.PicklingError, TypeError) as e:
                logger.error(f"Pickle serialization failed: {e}")
                raise SerializationError(f"Pickle serialization failed: {e}")
        elif format == "json":
            try:
                # JSON поддерживает только базовые типы
                if isinstance(state, dict):
                    serializable = state
                else:
                    # Попытка преобразовать в dict, если объект имеет метод dict()
                    if hasattr(state, "dict"):
                        serializable = state.dict()
                    elif hasattr(state, "__dict__"):
                        serializable = state.__dict__
                    else:
                        raise TypeError(f"Cannot JSON serialize {type(state)}")
                return json.dumps(serializable).encode("utf-8")
            except (TypeError, ValueError) as e:
                logger.error(f"JSON serialization failed: {e}")
                raise SerializationError(f"JSON serialization failed: {e}")
        else:
            raise ValueError(f"Unsupported serialization format: {format}")

    @staticmethod
    def deserialize(data: bytes, format: str = "pickle") -> Any:
        """
        Десериализует состояние из bytes.

        Параметры:
            data: bytes сериализованного состояния
            format: 'pickle' или 'json'

        Возвращает:
            восстановленный объект состояния
        """
        if format == "pickle":
            try:
                return pickle.loads(data)
            except (pickle.UnpicklingError, EOFError) as e:
                logger.error(f"Pickle deserialization failed: {e}")
                raise SerializationError(f"Pickle deserialization failed: {e}")
        elif format == "json":
            try:
                decoded = data.decode("utf-8")
                return json.loads(decoded)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"JSON deserialization failed: {e}")
                raise SerializationError(f"JSON deserialization failed: {e}")
        else:
            raise ValueError(f"Unsupported serialization format: {format}")

    @staticmethod
    def to_base64(data: bytes) -> str:
        """Кодирует bytes в base64 строку."""
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def from_base64(b64_str: str) -> bytes:
        """Декодирует base64 строку в bytes."""
        return base64.b64decode(b64_str)


class Checkpointable:
    """
    Интерфейс для объектов, поддерживающих чекпоинты.
    Агенты должны наследовать этот класс и реализовать get_state/set_state.
    """

    def get_state(self) -> Dict[str, Any]:
        """
        Возвращает состояние агента в виде словаря, пригодного для сериализации.
        """
        raise NotImplementedError("Checkpointable.get_state must be implemented")

    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Восстанавливает состояние агента из словаря.
        """
        raise NotImplementedError("Checkpointable.set_state must be implemented")