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

### 2. Запуск инфраструктуры через Docker Compose

```bash
docker-compose up -d
```

Запустятся:
- Zookeeper (2181)
- Kafka (9092)
- Redis (6379)
- PostgreSQL (5432)
- API Gateway (8000)
- Observability стек (Prometheus, Grafana, Loki, Jaeger)

### 3. Проверка зависимостей

```bash
python check_deps.py
```

### 4. Отправка тестового события

```bash
curl -X POST http://localhost:8000/events \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "test-1",
    "source": "test",
    "severity": 0.8,
    "urgency": 0.7,
    "impact": 0.9
  }'
```

### 5. Мониторинг

- **Grafana**: http://localhost:3000 (логин: admin, пароль: admin)
- **Jaeger**: http://localhost:16686
- **Prometheus**: http://localhost:9090

## 🏗️ Архитектура

Проект состоит из следующих core‑компонентов:

1. **API Gateway (FastAPI)** – приём событий через REST API.
2. **Salience Engine** – оценка значимости событий по трём измерениям (severity, urgency, impact) и дополнительным факторам.
3. **Mode Manager** – управление глобальным режимом системы (low, normal, elevated, critical) с гистерезисом.
4. **Interrupt Manager** – принятие решений о прерывании текущих задач, checkpointing, восстановление.
5. **Workspace Service (Redis)** – общее рабочее пространство для хранения состояния, чекпоинтов, очередей задач.
6. **Policy Engine** – декларативные политики прерывания и переключения режимов (YAML DSL), веб‑интерфейс.
7. **Task Orchestrator** – создание задач и назначение агентов.
8. **Retriever Agent** – базовый агент для выполнения задач, интеграция с LLM.
9. **Observability Stack** – OpenTelemetry, Prometheus, Grafana, Loki, Jaeger для мониторинга, логирования и трассировки.

## 🔧 Технологический стек

- **Языки**: Python 3.11+
- **Фреймворки**: FastAPI (REST API), Pydantic (валидация), SQLAlchemy (ORM)
- **Инфраструктура**: Apache Kafka (event bus), Redis (workspace), PostgreSQL (persistent storage)
- **Контейнеризация**: Docker & Docker Compose
- **Оркестрация**: Kubernetes (production)
- **Observability**: OpenTelemetry, Prometheus, Grafana, Loki, Jaeger
- **CI/CD**: GitHub Actions

## 📖 Политики

Политики определены в YAML‑файлах в `policy_engine/policies/`:

- `interrupt_policies.yaml` – правила прерывания
- `mode_policies.yaml` – правила переключения режимов
- `action_policies.yaml` – действия при срабатывании политик
- `tool_access_policies.yaml` – контроль доступа к инструментам
- `human_escalation_policies.yaml` – эскалация к человеку
- `routing_policies.yaml` – маршрутизация событий

Управление политиками через веб‑интерфейс (http://localhost:8001) или REST API.

## 📊 Observability

- **Логирование**: структурированные JSON‑логи через python‑json‑logger, сбор в Loki.
- **Метрики**: Prometheus‑метрики доступны на порту 9090.
  - `ras_events_total` – количество событий по типам
  - `ras_salience_score` – распределение salience score
  - `ras_interrupt_decisions_total` – решения о прерывании
  - `ras_mode_transitions_total` – переходы режимов
- **Трассировка**: Распределённые трассировки через Jaeger.

## 🧪 Тестирование

Запустите модульные и интеграционные тесты:

```bash
pytest tests/
```

## 📈 Дальнейшие шаги (фазы 2 и 3)

- **Фаза 2**: Adaptive Attention – novelty detection, checkpoint/resume, trust scoring, human escalation.
- **Фаза 3**: Self‑Optimizing – RL для динамической настройки порогов, predictive processing, homeostatic control.

## 📄 Лицензия

MIT