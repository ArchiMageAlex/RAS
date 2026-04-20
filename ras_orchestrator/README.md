# RAS-like Orchestrator

Минимально жизнеспособная версия оркестратора, реализующего принципы Reticular Activating System (RAS) для селективного внимания и прерывания задач.

## 📚 Полная документация

Полная документация находится в директории [`docs/`](docs/README.md). Она включает:

- **Архитектура** — обзор системы, компоненты, data model.
- **API** — OpenAPI спецификация, примеры запросов.
- **Развёртывание** — Docker Compose, Kubernetes, production guide.
- **Операции** — мониторинг, troubleshooting, maintenance.
- **Разработка** — настройка окружения, code style, CI/CD.
- **Руководство пользователя** — быстрый старт, use cases, best practices.
- **Справочные материалы** — глоссарий, FAQ, чеклисты.

## 🚀 Быстрый старт

### 1. Клонирование и настройка

```bash
git clone https://github.com/your-org/ras-orchestrator.git
cd ras_orchestrator
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

**Основные зависимости:**
- `fastapi` — REST API
- `pydantic` — валидация данных
- `redis` — workspace service
- `prometheus-client` — метрики
- `python-json-logger` — структурированное логирование

**Опциональные зависимости (для полной функциональности):**
- `opentelemetry-*` — трассировка и метрики
- `watchdog` — hot-reload политик
- `jsonschema` — валидация YAML-политик

### 3. Запуск инфраструктуры (опционально)

Для работы с Redis и другими сервисами:

```bash
docker-compose up -d
```

Запустятся:
- **Redis** (6379) — workspace service
- **Kafka** (9092) — event bus (опционально)
- **PostgreSQL** (5432) — персистентное хранилище (опционально)

### 4. Запуск end-to-end сценария

```bash
python run_scenario.py
```

Сценарий демонстрирует полный цикл обработки события:
1. Создание события `payment_outage` с критическим уровнем
2. Оценка значимости (Salience Engine)
3. Определение режима системы (Mode Manager)
4. Проверка необходимости прерывания (Interrupt Manager)
5. Создание и выполнение задачи (Task Orchestrator + Retriever Agent)
6. Сохранение состояния в workspace (Redis)

### 5. Отправка события через API

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "payment_outage",
    "severity": "critical",
    "source": "payment_gateway",
    "payload": {
      "service": "payment_gateway",
      "region": "eu-west-1",
      "error_rate": 0.95
    }
  }'
```

### 6. Проверка здоровья API

```bash
curl http://localhost:8000/health
```

### 7. Мониторинг

- **Prometheus метрики**: http://localhost:9090
- **Grafana**: http://localhost:3000 (логин: admin, пароль: admin)
- **Jaeger** (трассировка): http://localhost:16686

## 🏗️ Архитектура

Проект состоит из следующих core‑компонентов:

| Компонент | Описание |
|-----------|----------|
| **API Gateway** (FastAPI) | Приём событий через REST API |
| **Salience Engine** | Оценка значимости событий по 5 измерениям: relevance, novelty, risk, urgency, uncertainty |
| **Mode Manager** | Управление глобальным режимом системы (low, normal, elevated, critical) с гистерезисом и cooldown |
| **Interrupt Manager** | Принятие решений о прерывании текущих задач, checkpointing, восстановление |
| **Workspace Service** (Redis) | Общее рабочее пространство для хранения состояния, чекпоинтов, очередей задач |
| **Policy Engine** | Декларативные политики прерывания и переключения режимов (YAML DSL) |
| **Task Orchestrator** | Создание задач и назначение агентов |
| **Retriever Agent** | Базовый агент для выполнения задач retrieval |
| **Event Bus** (Kafka) | Шина событий для асинхронной коммуникации |
| **Observability Stack** | OpenTelemetry, Prometheus, Grafana, Jaeger для мониторинга |

## 🔧 Технологический стек

- **Языки**: Python 3.11+
- **Фреймворки**: FastAPI (REST API), Pydantic (валидация), asyncio
- **Инфраструктура**: Apache Kafka (event bus), Redis (workspace), PostgreSQL (persistent storage)
- **Контейнеризация**: Docker & Docker Compose
- **Оркестрация**: Kubernetes (production)
- **Observability**: OpenTelemetry, Prometheus, Grafana, Jaeger
- **CI/CD**: GitHub Actions

## 📖 Политики

Политики определены в YAML‑файлах в `policy_engine/policies/`:

| Файл | Назначение |
|------|------------|
| `interrupt_policies.yaml` | Правила прерывания задач |
| `mode_policies.yaml` | Правила переключения режимов |
| `action_policies.yaml` | Действия при срабатывании политик |
| `tool_access_policies.yaml` | Контроль доступа к инструментам |
| `human_escalation_policies.yaml` | Эскалация к человеку |
| `routing_policies.yaml` | Маршрутизация событий |

Пример политики (`interrupt_policies.yaml`):

```yaml
policies:
  - name: critical_payment_outage
    version: "1.0"
    description: "Прерывание всех задач при критическом сбое платежей"
    enabled: true
    priority: 90
    conditions:
      all:
        - event.type: payment_outage
        - event.severity: critical
        - salience.aggregated:
            gt: 0.8
    actions:
      action: interrupt
      reason: critical_payment_outage
      interrupt_type: hard
      checkpoint: true
```

## 📊 Observability

### Логирование
- Структурированные JSON-логи через `python-json-logger`
- Корреляция с trace_id и span_id из OpenTelemetry
- Сбор логов в Loki (при использовании полного стека)

### Метрики Prometheus
- `ras_events_total{event_type, severity}` — количество событий
- `ras_salience_score` — распределение salience score
- `ras_interrupt_decisions_total{decision, reason}` — решения о прерывании
- `ras_mode_transitions_total{from, to}` — переходы режимов

### Трассировка
- Распределённые трассировки через Jaeger
- Корреляция запросов через `X-Correlation-ID`

## 🧪 Тестирование

Запустите модульные и интеграционные тесты:

```bash
pytest tests/ -v
```

## 📈 Roadmap

### Фаза 2: Adaptive Attention
- [ ] Novelty detection на основе historical events
- [ ] Checkpoint/resume для длинных задач
- [ ] Trust scoring для источников событий
- [ ] Human escalation workflows

### Фаза 3: Self-Optimizing
- [ ] Reinforcement Learning для динамической настройки порогов
- [ ] Predictive processing на основе временных паттернов
- [ ] Homeostatic control для баланса нагрузки

## 📄 Лицензия

MIT