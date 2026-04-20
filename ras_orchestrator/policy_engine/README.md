# Policy Engine for RAS Orchestrator

Policy-as-Code система для управления правилами поведения в RAS-like оркестраторе.

## Возможности

- **DSL для политик**: Поддержка сложных условий с операторами `all`, `any`, `not`, сравнениями (`gt`, `lt`, `eq`, `in`, `matches` и др.)
- **Типы политик**: Interrupt, Mode, Action, Tool Access, Human Escalation, Routing, Salience Weights, Anomaly Detection и другие.
- **Hot-reload**: Автоматическая перезагрузка политик при изменении YAML файлов.
- **Кэширование**: Кэш скомпилированных политик с инвалидацией по хешу файлов.
- **Валидация**: JSON Schema валидация синтаксиса и семантики политик.
- **Интеграция**: Готовые интеграции с компонентами оркестратора (Salience Engine, Mode Manager, Interrupt Manager, Task Orchestrator, Agent Layer, Human Escalation).
- **REST API**: Полноценный API для управления политиками, оценки и мониторинга.
- **Web UI**: Визуальный интерфейс для просмотра, тестирования и управления политиками.
- **Тестирование**: Unit tests, интеграционные тесты, performance tests.

## Архитектура

```
policy_engine/
├── core.py           # Ядро движка (парсер, evaluator, кэш, hot-reload)
├── engine.py         # Обёртка для обратной совместимости
├── schemas.py        # JSON Schema валидация
├── integration.py    # Интеграции с компонентами оркестратора
├── api.py            # REST API endpoints
├── policies/         # YAML файлы политик
│   ├── interrupt_policies.yaml
│   ├── mode_policies.yaml
│   ├── action_policies.yaml
│   ├── tool_access_policies.yaml
│   ├── human_escalation_policies.yaml
│   └── routing_policies.yaml
├── static/           # Web UI
│   └── index.html
└── tests/            # Unit tests
    └── test_core.py
```

## Использование

### 1. Загрузка политик

Политики описываются в YAML файлах в директории `policies/`. Пример:

```yaml
version: "2.0"
description: "Interrupt policies"
policies:
  - name: "high_risk_security"
    enabled: true
    priority: 10
    conditions:
      all:
        - event.type: "security_alert"
        - salience.risk:
            gt: 0.8
    actions:
      action: "interrupt"
      reason: "High security risk"
```

### 2. Использование ядра

```python
from policy_engine.core import PolicyEngineCore

engine = PolicyEngineCore(policy_dir="./policies", watch=True)
matched = engine.evaluate("interrupt", {
    "event": {"type": "security_alert"},
    "salience": {"risk": 0.9}
})
```

### 3. Интеграция с компонентами

```python
from policy_engine.integration import get_integration

integration = get_integration("interrupt")
result = integration.evaluate_interrupt(event, salience_score, current_mode, active_tasks)
```

### 4. REST API

Запустите API Gateway:

```bash
cd ras_orchestrator
uvicorn api_gateway.main:app --host 0.0.0.0 --port 8000
```

Доступные эндпоинты:

- `GET /policies/types` – список типов политик
- `GET /policies/files` – список файлов политик
- `POST /policies/evaluate` – оценка политик
- `GET /policies/{type}/list` – список политик определённого типа
- `POST /policies/reload` – перезагрузка политик

### 5. Web UI

Откройте в браузере `http://localhost:8000/policies/static/index.html` после запуска API.

## Конфигурация

### Переменные окружения

- `POLICY_ENGINE_WATCH` – включить hot-reload (true/false)
- `POLICY_ENGINE_CACHE` – включить кэширование (true/false)
- `POLICY_DIR` – путь к директории с политиками (по умолчанию `./policies`)

### Добавление новых типов политик

1. Создайте YAML файл в `policies/` с соответствующим именем.
2. Добавьте схему валидации в `schemas.py` (опционально).
3. Создайте метод интеграции в `integration.py` (опционально).

## Тестирование

Запуск unit tests:

```bash
pytest ras_orchestrator/policy_engine/tests/ -v
```

## Развёртывание

### Docker

Используйте готовый `Dockerfile` в корне проекта:

```bash
docker build -t ras-orchestrator .
docker run -p 8000:8000 ras-orchestrator
```

### Kubernetes

Пример манифеста доступен в `deployment/` (требуется создание).

## Мониторинг и аудит

- Логирование всех оценок политик (уровень INFO).
- Метрики Prometheus: количество оценок, совпадений, время выполнения.
- Audit trail изменений политик (через Git или базу данных).

## Лицензия

Проект распространяется под лицензией MIT.