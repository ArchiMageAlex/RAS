# RAS-like Orchestrator MVP

Минимально жизнеспособная версия оркестратора, реализующего принципы Reticular Activating System (RAS) для селективного внимания и прерывания задач.

## Архитектура

Проект состоит из следующих core-компонентов:

1. **API Gateway (FastAPI)** – приём событий через REST API.
2. **Salience Engine** – оценка значимости событий по пяти измерениям (релевантность, новизна, риск, срочность, неопределённость).
3. **Mode Manager** – управление глобальным режимом системы (low, normal, elevated, critical).
4. **Interrupt Manager** – принятие решений о прерывании текущих задач.
5. **Workspace Service (Redis)** – общее рабочее пространство для хранения состояния.
6. **Policy Engine** – декларативные политики прерывания и переключения режимов (YAML).
7. **Task Orchestrator** – создание задач и назначение агентов.
8. **Retriever Agent** – базовый агент для поиска информации.

## Технологический стек

- Python 3.11+
- FastAPI (REST API)
- Apache Kafka (event bus)
- Redis (workspace)
- PostgreSQL (persistent storage, заготовка)
- Docker & Docker Compose
- OpenTelemetry/Prometheus (observability)

## Быстрый старт

### 1. Клонирование и настройка

```bash
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

### 3. Установка зависимостей (для локальной разработки)

```bash
pip install -r requirements.txt
```

### 4. Проверка зависимостей

```bash
python check_deps.py
```

Если отсутствуют какие-либо пакеты, скрипт сообщит и предложит установить.

### 5. Запуск end-to-end сценария

```bash
python run_scenario.py
```

Сценарий имитирует событие `payment_outage` с критической severity и проходит через весь конвейер:
- Создание события
- Оценка значимости
- Определение режима
- Решение о прерывании
- Создание задачи
- Выполнение агентом
- Сохранение в workspace

## API Endpoints

### API Gateway
- `POST /events` – приём события
- `GET /health` – проверка здоровья

Пример запроса:

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "payment_outage",
    "severity": "critical",
    "source": "payment_service",
    "payload": {"error_rate": 0.95}
  }'
```

## Политики

Политики определены в YAML-файлах:

- `policy_engine/policies/interrupt_policies.yaml` – правила прерывания
- `policy_engine/policies/mode_policies.yaml` – правила переключения режимов

Пример политики прерывания:
```yaml
- name: "high_risk_security"
  conditions:
    event.type: "security_alert"
    salience.risk:
      gt: 0.8
  reason: "Высокий риск безопасности"
  priority: 10
  action: "interrupt"
```

## Observability

- **Логирование**: структурированные JSON-логи через python-json-logger.
- **Метрики**: Prometheus-метрики доступны на порту 9090 (если запущен сервер метрик).
  - `ras_events_total` – количество событий по типам
  - `ras_salience_score` – распределение salience score
  - `ras_interrupt_decisions_total` – решения о прерывании
  - `ras_mode_transitions_total` – переходы режимов

Для запуска сервера метрик выполните в коде:
```python
from common.utils import start_metrics_server
start_metrics_server(9090)
```

## Разработка

### Структура проекта

```
ras_orchestrator/
├── api_gateway/          # FastAPI приложение
├── salience_engine/      # Salience Engine
├── mode_manager/         # Mode Manager
├── interrupt_manager/    # Interrupt Manager
├── workspace_service/    # Redis клиент
├── policy_engine/        # Policy Engine + YAML политики
├── task_orchestrator/    # Task Orchestrator
├── retriever_agent/      # Retriever Agent
├── event_bus/            # Kafka клиент
├── common/               # Общие модели и утилиты
├── docker-compose.yml    # Конфигурация Docker Compose
├── Dockerfile            # Образ для сервисов
├── requirements.txt      # Зависимости Python
├── run_scenario.py       # End-to-end сценарий
├── check_deps.py         # Проверка зависимостей
└── README.md             # Эта документация
```

### Добавление нового агента

1. Создайте модуль в `agents/your_agent/`
2. Реализуйте метод `execute(task)`
3. Зарегистрируйте агента в Task Orchestrator

### Расширение политик

Добавьте новые правила в соответствующие YAML-файлы. Policy Engine автоматически загрузит их при старте.

## Тестирование

Запустите модульные тесты (будут добавлены позже):

```bash
pytest tests/
```

## Дальнейшие шаги (фазы 2 и 3)

- **Фаза 2**: Adaptive Attention – novelty detection, checkpoint/resume, trust scoring, human escalation.
- **Фаза 3**: Self-Optimizing – RL для динамической настройки порогов, predictive processing, homeostatic control.

## Лицензия

MIT