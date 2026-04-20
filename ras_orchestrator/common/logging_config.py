"""
Конфигурация структурированного логирования для RAS Orchestrator.

Настройки:
- JSON формат для логов
- Интеграция с OpenTelemetry (trace_id, span_id)
- Rotating файлы с retention policy
- Уровни логирования, конфигурируемые через переменные окружения
"""
import os
import json
import logging
import logging.handlers
from datetime import datetime
from pythonjsonlogger import jsonlogger

# Уровни логирования по умолчанию
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json или text
LOG_DIR = os.getenv("LOG_DIR", "./logs")
LOG_FILE_MAX_SIZE = int(os.getenv("LOG_FILE_MAX_SIZE", 10 * 1024 * 1024))  # 10 MB
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", 5))
LOG_FILE_NAME = os.getenv("LOG_FILE_NAME", "ras_orchestrator.log")

# Создаем директорию для логов, если её нет
os.makedirs(LOG_DIR, exist_ok=True)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Кастомный JSON форматтер, добавляющий поля OpenTelemetry.
    """
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        # Добавляем timestamp в ISO формате
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        # Добавляем trace_id и span_id из OpenTelemetry, если доступны
        span = getattr(record, "otelSpan", None)
        if span:
            context = span.get_span_context()
            log_record["trace_id"] = format(context.trace_id, "032x")
            log_record["span_id"] = format(context.span_id, "016x")
        else:
            # Пытаемся получить из текущего контекста
            from opentelemetry import trace
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                context = current_span.get_span_context()
                if context.trace_id:
                    log_record["trace_id"] = format(context.trace_id, "032x")
                if context.span_id:
                    log_record["span_id"] = format(context.span_id, "016x")

        # Добавляем baggage (business context)
        from opentelemetry import baggage
        baggage_entries = baggage.get_all()
        if baggage_entries:
            log_record["baggage"] = dict(baggage_entries)


def setup_logging():
    """
    Настраивает глобальное логирование для приложения.
    Должна быть вызвана при старте каждого компонента.
    """
    # Устанавливаем уровень логирования корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(DEFAULT_LOG_LEVEL)

    # Удаляем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Создаем обработчик для консоли
    if LOG_FORMAT == "json":
        console_handler = logging.StreamHandler()
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(module)s %(function)s %(message)s"
        )
        console_handler.setFormatter(formatter)
    else:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [trace_id=%(trace_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Создаем обработчик для файла с ротацией
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(LOG_DIR, LOG_FILE_NAME),
        maxBytes=LOG_FILE_MAX_SIZE,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    if LOG_FORMAT == "json":
        file_formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(module)s %(function)s %(message)s"
        )
    else:
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [trace_id=%(trace_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Настраиваем логирование для библиотек
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)

    logging.info("Logging configured", extra={
        "log_level": DEFAULT_LOG_LEVEL,
        "log_format": LOG_FORMAT,
        "log_dir": LOG_DIR,
    })


def get_logger(name: str) -> logging.Logger:
    """Возвращает логгер с заданным именем."""
    return logging.getLogger(name)


# Глобальная инициализация при импорте
setup_logging()