# Настройка окружения для разработки

Это руководство описывает, как настроить локальное окружение для разработки и тестирования RAS-like оркестратора.

## Предварительные требования

- **Операционная система**: Linux, macOS или Windows (WSL2 рекомендуется для Windows)
- **Docker** и **Docker Compose** (для запуска зависимостей)
- **Python 3.10+** (для запуска компонентов локально)
- **Git** (для управления версиями)
- **kubectl** и **minikube** (опционально, для работы с Kubernetes)
- **Poetry** (для управления зависимостями Python) или **pip**

## Клонирование репозитория

```bash
git clone https://github.com/your-org/ras-orchestrator.git
cd ras-orchestrator
```

## Установка зависимостей

### Python зависимости

Проект использует Poetry для управления зависимостями. Установите Poetry, если ещё не установлен:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Установите зависимости:

```bash
poetry install
```

Альтернативно, можно использовать pip:

```bash
pip install -r requirements.txt
```

### Зависимости инфраструктуры

Запустите инфраструктурные сервисы (Kafka, Redis, PostgreSQL, Observability) через Docker Compose:

```bash
docker-compose up -d
```

Эта команда запустит все сервисы, определённые в `docker-compose.yml`. Проверьте, что все контейнеры работают:

```bash
docker-compose ps
```

## Настройка окружения

Создайте файл `.env` в корне проекта на основе `.env.example`:

```bash
cp .env.example .env
```

Отредактируйте `.env`, установив необходимые значения:

```env
# API Gateway
API_GATEWAY_HOST=0.0.0.0
API_GATEWAY_PORT=8000
API_KEY=dev-key-123

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_EVENTS_TOPIC=ras.events

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ras
POSTGRES_USER=ras
POSTGRES_PASSWORD=raspassword

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
```

## Запуск компонентов в режиме разработки

Каждый компонент можно запустить отдельно. Рекомендуется использовать менеджер процессов, такой как `tmux` или `docker-compose` для разработки.

### 1. API Gateway

```bash
cd api_gateway
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Или используйте скрипт:

```bash
./scripts/run_api_gateway.sh
```

### 2. Salience Engine

```bash
cd salience_engine
poetry run python consumer.py
```

### 3. Mode Manager

```bash
cd mode_manager
poetry run python consumer.py
```

### 4. Interrupt Manager

```bash
cd interrupt_manager
poetry run python consumer.py
```

### 5. Workspace Service

```bash
cd workspace_service
poetry run python -m uvicorn redis_client:app --host 0.0.0.0 --port 8002
```

### 6. Policy Engine

```bash
cd policy_engine
poetry run uvicorn api:app --reload --host 0.0.0.0 --port 8001
```

### 7. Task Orchestrator

```bash
cd task_orchestrator
poetry run python consumer.py
```

### 8. Retriever Agent

```bash
cd retriever_agent
poetry run python agent.py
```

## Запуск всех компонентов через Docker Compose (разработка)

Используйте `docker-compose.override.yml` для разработки:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Это запустит все компоненты с hot‑reload и отладкой.

## Тестирование

### Запуск unit‑тестов

```bash
pytest
```

Или для конкретного модуля:

```bash
pytest tests/test_salience_engine.py -v
```

### Запуск интеграционных тестов

Интеграционные тесты требуют работающей инфраструктуры (Kafka, Redis, PostgreSQL). Убедитесь, что Docker Compose запущен, затем:

```bash
pytest tests/test_integration.py
```

### Запуск e2e‑тестов

```bash
pytest tests/test_e2e_workflow.py
```

### Покрытие кода

```bash
pytest --cov=ras_orchestrator --cov-report=html
```

Откройте `htmlcov/index.html` в браузере.

## Отладка

### Логирование

Логи настроены через `common/logging_config.py`. Уровень логирования можно изменить через переменную окружения `LOG_LEVEL` (по умолчанию INFO).

```bash
export LOG_LEVEL=DEBUG
```

### Трассировка OpenTelemetry

Трассировка включена по умолчанию. Для просмотра трассировок запустите Jaeger:

```bash
docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one:latest
```

Трассировки будут доступны на http://localhost:16686.

### Отладка в IDE (VS Code)

Создайте конфигурацию запуска `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "API Gateway",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["api_gateway.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

## Работа с Kafka

### Создание топиков

```bash
docker exec -it ras-orchestrator-kafka-1 kafka-topics --create --topic ras.events --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092
```

### Просмотр сообщений

```bash
docker exec -it ras-orchestrator-kafka-1 kafka-console-consumer --topic ras.events --from-beginning --bootstrap-server localhost:9092
```

### Отправка тестового события

```bash
curl -X POST http://localhost:8000/events \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "test-1", "source": "test", "severity": 0.8, "urgency": 0.7, "impact": 0.9}'
```

## Работа с Redis

### Подключение к Redis CLI

```bash
docker exec -it ras-orchestrator-redis-1 redis-cli
```

### Просмотр ключей

```bash
docker exec -it ras-orchestrator-redis-1 redis-cli KEYS "*"
```

## Работа с PostgreSQL

### Подключение к БД

```bash
docker exec -it ras-orchestrator-postgres-1 psql -U ras -d ras
```

### Просмотр таблиц

```sql
SELECT * FROM events LIMIT 10;
```

## Настройка Observability стека

### Prometheus

Доступен на http://localhost:9090.

### Grafana

Доступна на http://localhost:3000 (логин: admin, пароль: admin).

### Loki

Логи доступны через Grafana (источник данных Loki) или через LogCLI.

### Jaeger

Доступен на http://localhost:16686.

## Форматирование кода и линтинг

Проект использует black, isort, flake8 и mypy.

### Форматирование

```bash
black .
isort .
```

### Линтинг

```bash
flake8
mypy .
```

### Pre‑commit хуки

Установите pre‑commit:

```bash
pre-commit install
```

Теперь при каждом коммите будут автоматически запускаться линтеры и форматтеры.

## CI/CD

GitHub Actions настроены в `.github/workflows/`. Основные workflow:

- **test.yml**: Запуск тестов при пуше в ветку.
- **lint.yml**: Проверка форматирования и линтинга.
- **build.yml**: Сборка Docker‑образов.
- **deploy.yml**: Развёртывание в staging/production.

## Структура проекта

```
ras_orchestrator/
├── api_gateway/          # API Gateway (FastAPI)
├── salience_engine/      # Salience Engine (scoring)
├── mode_manager/         # Mode Manager (state machine)
├── interrupt_manager/    # Interrupt Manager (interrupt decisions)
├── workspace_service/    # Workspace Service (Redis)
├── policy_engine/        # Policy Engine (YAML DSL, UI)
├── task_orchestrator/    # Task Orchestrator
├── retriever_agent/      # Retriever Agent (LLM integration)
├── common/               # Общие утилиты, модели, логирование
├── event_bus/            # Kafka клиент
├── integration/          # Интеграционные модули
├── performance/          # Оптимизации производительности
├── observability/        # Конфигурация мониторинга
├── tests/                # Тесты
├── scripts/              # Вспомогательные скрипты
├── docs/                 # Документация
├── docker-compose.yml    # Docker Compose для разработки
├── Dockerfile            # Dockerfile для production
├── requirements.txt      # Python зависимости
├── pyproject.toml        # Конфигурация Poetry
└── README.md             # Корневой README
```

## Советы по разработке

1. **Используйте виртуальное окружение**: Poetry автоматически создаёт его.
2. **Пишите тесты**: Для нового функционала добавляйте unit‑ и интеграционные тесты.
3. **Следуйте code style**: Используйте black и isort для форматирования.
4. **Документируйте изменения**: Обновляйте документацию при изменении API или архитектуры.
5. **Используйте feature‑branches**: Создавайте ветки для новых фич и мержите через pull request.

## Устранение проблем

### Проблемы с подключением к Kafka

Убедитесь, что Kafka запущена и доступна на `localhost:9092`. Проверьте, что топик `ras.events` создан.

### Ошибки Redis

Проверьте, что Redis запущен и принимает подключения. Убедитесь, что в `.env` указаны правильные host и port.

### Ошибки PostgreSQL

Убедитесь, что база данных создана и пользователь имеет права. Вы можете сбросить БД:

```bash
docker-compose down -v
docker-compose up -d
```

### Проблемы с импортами

Убедитесь, что PYTHONPATH включает корень проекта. Можно установить переменную:

```bash
export PYTHONPATH=$(pwd)
```

## Дополнительные ресурсы

- [Архитектурная документация](../architecture/overview.md)
- [API документация](../api/README.md)
- [Deployment руководство](../deployment/docker-compose.md)