# Структура кода и соглашения

В этом документе описаны стандарты кодирования, архитектурные паттерны и соглашения, используемые в проекте RAS-like оркестратора.

## Общие принципы

- **Чистый код**: Код должен быть самодокументируемым, с понятными именами переменных и функций.
- **Принцип единственной ответственности**: Каждый модуль/класс должен решать одну задачу.
- **Инверсия зависимостей**: Зависимости внедряются через интерфейсы (абстракции).
- **Тестируемость**: Код должен быть легко тестируемым (использование dependency injection, отсутствие глобального состояния).
- **Конфигурируемость**: Параметры выносятся в конфигурационные файлы или переменные окружения.

## Структура проекта

```
ras_orchestrator/
├── api_gateway/               # API Gateway (FastAPI)
│   ├── __init__.py
│   ├── main.py                # Точка входа FastAPI
│   ├── routes/                # Маршруты API
│   ├── middleware/            # Middleware (аутентификация, логирование)
│   └── schemas.py             # Pydantic схемы для запросов/ответов
├── salience_engine/           # Salience Engine
│   ├── __init__.py
│   ├── engine.py              # Основной класс SalienceEngine
│   ├── scoring.py             # Алгоритмы scoring
│   ├── advanced_scoring.py    # ML‑модели и расширенные алгоритмы
│   ├── consumer.py            # Kafka consumer для событий
│   └── models.py              # Модели данных (если не в common)
├── mode_manager/              # Mode Manager
│   ├── __init__.py
│   ├── manager.py             # ModeManager и StateMachine
│   ├── consumer.py            # Kafka consumer для salience scores
│   └── hysteresis.py          # Логика гистерезиса
├── interrupt_manager/         # Interrupt Manager
│   ├── __init__.py
│   ├── manager.py             # InterruptManager, типы прерываний
│   ├── consumer.py            # Kafka consumer для решений
│   └── checkpointing.py       # Механизм чекпоинтов
├── workspace_service/         # Workspace Service
│   ├── __init__.py
│   ├── redis_client.py        # Redis клиент и операции
│   ├── models.py              # Модели workspace
│   └── api.py                 # REST API (если требуется)
├── policy_engine/             # Policy Engine
│   ├── __init__.py
│   ├── core.py                # Ядро движка политик
│   ├── engine.py              # Исполнение политик
│   ├── schemas.py             # Схемы политик
│   ├── api.py                 # REST API для управления политиками
│   ├── static/                # Веб‑интерфейс
│   └── policies/              # YAML‑файлы политик
├── task_orchestrator/         # Task Orchestrator
│   ├── __init__.py
│   ├── orchestrator.py        # Создание и управление задачами
│   └── consumer.py            # Kafka consumer для событий прерывания
├── retriever_agent/           # Retriever Agent
│   ├── __init__.py
│   ├── agent.py               # Агент, интегрирующийся с LLM
│   └── consumer.py            # Kafka consumer для задач
├── common/                    # Общие модули
│   ├── __init__.py
│   ├── models.py              # Pydantic модели (Event, SalienceScore, Task и т.д.)
│   ├── logging_config.py      # Конфигурация логирования
│   ├── telemetry.py           # OpenTelemetry инструментация
│   └── utils.py               # Вспомогательные функции
├── event_bus/                 # Event Bus (Kafka)
│   ├── __init__.py
│   └── kafka_client.py        # Producer/Consumer обёртки
├── integration/               # Интеграции с внешними системами
│   └── coordinator.py         # Координатор интеграций
├── performance/               # Оптимизации производительности
│   └── optimizer.py           # Кэширование, пулы соединений и т.д.
├── observability/             # Конфигурация мониторинга
│   ├── prometheus.yml
│   ├── alert_rules.yml
│   ├── grafana/
│   └── loki-config.yaml
├── tests/                     # Тесты
│   ├── test_salience_engine.py
│   ├── test_mode_manager.py
│   ├── test_integration.py
│   └── ...
├── scripts/                   # Вспомогательные скрипты
│   ├── run_scenario.py
│   └── check_deps.py
├── docs/                      # Документация
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Соглашения по именованию

### Файлы и директории

- **snake_case** для файлов и директорий: `salience_engine/`, `advanced_scoring.py`.
- Исключение: файлы с основным классом могут называться как класс (например, `manager.py`).

### Классы

- **CamelCase**: `SalienceEngine`, `ModeManager`, `InterruptManager`.
- Абстрактные классы могут начинаться с `Abstract` или `Base`: `BaseScoringAlgorithm`.

### Функции и методы

- **snake_case**: `calculate_salience_score`, `process_event`.
- Геттеры/сеттеры: использовать `@property` декоратор.

### Переменные

- **snake_case**: `event_id`, `salience_score`.
- Константы: **UPPER_SNAKE_CASE**: `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`.

### Модули

- Имена модулей должны быть короткими и отражать их содержание: `utils`, `models`, `client`.

## Стиль кода

Проект следует **PEP 8** с некоторыми дополнениями:

- **Длина строки**: максимум 100 символов.
- **Отступы**: 4 пробела (без табуляций).
- **Кавычки**: двойные кавычки для строк, кроме случаев, когда внутри строки есть двойные кавычки.
- **Импорты**: группировать в следующем порядке:
  1. Стандартная библиотека
  2. Сторонние библиотеки
  3. Локальные модули
  Каждая группа отделяется пустой строкой.

Пример:

```python
import json
import os
from typing import Dict, List

from pydantic import BaseModel
from kafka import KafkaProducer

from common.models import Event
from salience_engine.scoring import calculate_score
```

## Типизация

Используется **type hints** для всех функций, методов и переменных. Для сложных типов применяются `typing` модуль и `pydantic`.

Пример:

```python
from typing import Optional, List
from pydantic import BaseModel

class Event(BaseModel):
    event_id: str
    severity: float
    urgency: float
    impact: float

def process_events(events: List[Event]) -> Optional[Dict[str, float]]:
    ...
```

## Логирование

Используется стандартный модуль `logging` с конфигурацией из `common/logging_config.py`.

- Уровни логирования:
  - **DEBUG**: Детальная информация для отладки.
  - **INFO**: Информационные сообщения о нормальной работе.
  - **WARNING**: Предупреждения о потенциальных проблемах.
  - **ERROR**: Ошибки, требующие внимания.
  - **CRITICAL**: Критические ошибки, приводящие к остановке.

Пример:

```python
import logging

logger = logging.getLogger(__name__)

def some_function():
    logger.info("Processing event")
    try:
        ...
    except Exception as e:
        logger.error(f"Failed to process event: {e}", exc_info=True)
```

## Обработка ошибок

- Используйте конкретные исключения, а не общие `Exception`.
- Создавайте пользовательские исключения в `common/exceptions.py`.
- Всегда логируйте исключения с `exc_info=True` для stack trace.
- При необходимости используйте retry с exponential backoff.

Пример:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_external_api():
    ...
```

## Конфигурация

Конфигурация выносится в переменные окружения и файлы `.env`. Используйте библиотеку `pydantic-settings` для валидации.

Пример:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_gateway_host: str = "0.0.0.0"
    api_gateway_port: int = 8000
    kafka_bootstrap_servers: str = "localhost:9092"

    class Config:
        env_file = ".env"

settings = Settings()
```

## Тестирование

### Структура тестов

- Тесты располагаются в директории `tests/`.
- Имена тестовых файлов начинаются с `test_`: `test_salience_engine.py`.
- Имена тестовых функций начинаются с `test_`: `test_calculate_score_high_severity`.
- Используйте фикстуры pytest для подготовки данных.

### Моки и стабы

Используйте `unittest.mock` для изоляции тестируемого кода от внешних зависимостей.

Пример:

```python
from unittest.mock import Mock, patch

def test_salience_engine():
    with patch('salience_engine.scoring.calculate_score') as mock_score:
        mock_score.return_value = 0.9
        result = engine.process(event)
        assert result == 0.9
```

### Интеграционные тесты

Интеграционные тесты требуют запущенной инфраструктуры (Kafka, Redis, PostgreSQL). Используйте `docker-compose` для поднятия окружения перед запуском тестов.

## Документация кода

### Docstrings

Используйте формат **Google style** для docstrings.

Пример:

```python
def calculate_salience_score(event: Event) -> float:
    """Вычисляет salience score для события.

    Args:
        event: Объект события с полями severity, urgency, impact.

    Returns:
        Значение salience score в диапазоне [0, 1].

    Raises:
        ValueError: Если поля события отсутствуют или некорректны.
    """
    ...
```

### Комментарии

- Комментируйте сложную логику, но избегайте очевидных комментариев.
- Используйте комментарии TODO, FIXME, NOTE для пометок.

Пример:

```python
# TODO: Заменить линейную комбинацию на ML‑модель.
def calculate_score(...):
    ...
```

## Git workflow

### Ветки

- **main**: Стабильная ветка, соответствует production.
- **develop**: Ветка для интеграции новых фич.
- **feature/***: Ветки для разработки новых функций.
- **bugfix/***: Ветки для исправления багов.
- **release/***: Ветки для подготовки релиза.

### Коммиты

Сообщения коммитов должны следовать **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Типы:
- **feat**: Новая функциональность.
- **fix**: Исправление бага.
- **docs**: Изменения в документации.
- **style**: Изменения форматирования (пробелы, запятые и т.д.).
- **refactor**: Рефакторинг кода без изменения поведения.
- **test**: Добавление или исправление тестов.
- **chore**: Вспомогательные изменения (обновление зависимостей, конфигурации).

Пример:

```
feat(salience): добавить ML‑модель для scoring

Использована модель XGBoost для предсказания salience score.
Добавлены тесты и обновлена документация.

Closes #123
```

### Pull Request

Каждое изменение должно проходить код‑ревью. PR должен содержать:
- Описание изменений.
- Ссылку на задачу (issue).
- Инструкции по тестированию.
- Скриншоты (если применимо).

## CI/CD

Конфигурация CI/CD находится в `.github/workflows/`. Каждый PR запускает:
1. Линтинг (black, isort, flake8, mypy).
2. Unit‑тесты.
3. Интеграционные тесты (если изменены соответствующие модули).
4. Сборка Docker‑образов.

После мержа в `main` автоматически запускается деплой в staging, затем после утверждения — в production.

## Обновление зависимостей

Зависимости управляются через `pyproject.toml` (Poetry). Для обновления:

```bash
poetry update
```

Зафиксируйте изменения в `poetry.lock` и создайте PR.

## Безопасность

- Никогда не коммитьте секреты (пароли, API‑ключи) в репозиторий.
- Используйте `git-secrets` или `pre-commit` хуки для проверки.
- Регулярно обновляйте зависимости для устранения уязвимостей.

## Производительность

- Используйте асинхронные вызовы (async/await) для I/O операций.
- Кэшируйте часто используемые данные (Redis, in‑memory cache).
- Оптимизируйте запросы к БД (индексы, batch processing).
- Мониторьте метрики производительности (latency, throughput, error rate).

## Дополнительные ресурсы

- [PEP 8](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Pytest Documentation](https://docs.pytest.org/)