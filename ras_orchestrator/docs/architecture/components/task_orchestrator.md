# Task Orchestrator

## Назначение

Task Orchestrator управляет жизненным циклом задач: создание, назначение агентов, отслеживание статусов, повторные попытки, приоритизация. Он получает решения о прерываниях от Interrupt Manager и создаёт соответствующие задачи для агентов.

## Архитектура

- **Создание задач**: На основе события и решения о прерывании формируется задача (Task object).
- **Назначение агентов**: Выбор подходящего агента (например, Retriever Agent) по типу задачи.
- **Отслеживание статусов**: Мониторинг выполнения задач, обновление статусов (pending, running, completed, failed, interrupted).
- **Повторные попытки**: Автоматический retry при неудачном выполнении (с экспоненциальной задержкой).
- **Приоритизация**: Очередь задач с приоритетами на основе salience score и типа прерывания.

## Модель задачи (Task)

```yaml
task_id: string
event_id: string
agent_type: string
status: enum(pending, running, completed, failed, interrupted)
created_at: datetime
updated_at: datetime
parameters: dict
result: dict (optional)
```

## Процесс оркестрации

1. **Получение решения о прерывании**: Из топика Kafka `ras.interrupt`.
2. **Создание задачи**:
   - Генерация уникального `task_id`.
   - Определение `agent_type` на основе типа события или политики.
   - Установка параметров задачи (например, запрос к внешнему API).
3. **Сохранение задачи**:
   - В PostgreSQL (для долгосрочного хранения).
   - В Workspace Service (для быстрого доступа).
4. **Назначение агенту**:
   - Публикация задачи в топик Kafka `ras.tasks.{agent_type}`.
   - Ожидание подтверждения от агента.
5. **Отслеживание выполнения**:
   - Подписка на топик `ras.results` для получения результатов.
   - Обновление статуса задачи.
6. **Обработка результата**:
   - Сохранение результата в Workspace Service и PostgreSQL.
   - Уведомление заинтересованных компонентов (например, публикация в канал обновлений).

## Повторные попытки (Retry)

- **Максимальное количество попыток**: 3 (настраивается).
- **Backoff strategy**: Экспоненциальная задержка (1s, 2s, 4s).
- **Условия retry**: Сетевые ошибки, таймауты, временные сбои внешних систем.
- **Условия отказа**: Критические ошибки (например, невалидные данные), превышение лимита попыток.

## Приоритизация

Задачи помещаются в приоритетную очередь (Redis Sorted Set). Приоритет вычисляется как:

```
priority = base_priority + salience_score * 10 + interrupt_priority
```

где:
- `base_priority`: 100 для critical, 50 для elevated, 0 для normal/low.
- `salience_score`: агрегированный score (0–1).
- `interrupt_priority`: приоритет из решения о прерывании (0–10).

## Интеграция с агентами

Task Orchestrator не выполняет задачи самостоятельно, а делегирует их специализированным агентам. Каждый агент регистрируется в Orchestrator с указанием типов задач, которые он может выполнять.

## Конфигурация

### Переменные окружения

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `TASK_ORCHESTRATOR_MAX_RETRIES` | Максимальное количество повторных попыток | `3` |
| `TASK_ORCHESTRATOR_RETRY_BACKOFF_MS` | Начальная задержка retry в миллисекундах | `1000` |
| `TASK_ORCHESTRATOR_PRIORITY_QUEUE_NAME` | Имя Redis sorted set для очереди | `ras:tasks:queue` |
| `TASK_ORCHESTRATOR_DB_URL` | URL подключения к PostgreSQL | `postgresql://ras_user:ras_password@localhost:5432/ras_db` |

### Конфигурационный файл

`task_orchestrator/config.yaml`:

```yaml
max_retries: 3
retry_backoff_ms: 1000
priority_queue: ras:tasks:queue
database:
  url: postgresql://ras_user:ras_password@localhost:5432/ras_db
  pool_size: 10
agents:
  retriever:
    topic: ras.tasks.retriever
    concurrency: 5
```

## Метрики

- `ras_tasks_created_total` (counter) – количество созданных задач.
- `ras_tasks_completed_total` (counter) – количество завершённых задач.
- `ras_tasks_failed_total` (counter) – количество неудачных задач.
- `ras_task_execution_time_seconds` (histogram) – время выполнения задачи.
- `ras_task_queue_size` (gauge) – размер очереди задач.

## API

Task Orchestrator предоставляет REST API для управления задачами:

- `GET /tasks` – список задач (с фильтрацией по статусу).
- `GET /tasks/{task_id}` – детали задачи.
- `POST /tasks` – создание задачи вручную (для тестирования).
- `DELETE /tasks/{task_id}` – отмена задачи (если возможно).
- `GET /queue` – текущее состояние очереди.

## Интеграция с Observability

- **Трассировка**: Span `task_orchestration` с атрибутами (task_id, agent_type, status).
- **Логи**: Запись ключевых событий (создание, назначение, завершение).
- **Метрики**: Экспорт в Prometheus.

## Диаграмма последовательности

```mermaid
sequenceDiagram
    participant InterruptManager
    participant TaskOrchestrator
    participant Kafka
    participant Agent
    participant Workspace

    InterruptManager->>Kafka: решение о прерывании
    Kafka->>TaskOrchestrator: consume
    TaskOrchestrator->>TaskOrchestrator: создание задачи
    TaskOrchestrator->>Workspace: сохранение задачи
    TaskOrchestrator->>Kafka: публикация задачи
    Kafka->>Agent: consume задача
    Agent->>Agent: выполнение
    Agent->>Kafka: публикация результата
    Kafka->>TaskOrchestrator: consume результат
    TaskOrchestrator->>Workspace: обновление статуса
```

## Примечания для разработчиков

- Код находится в `ras_orchestrator/task_orchestrator/`
- Основные классы: `TaskOrchestrator`, `Task`, `TaskQueue`.
- Тесты: `pytest tests/test_task_orchestrator.py`
- Запуск consumer: `python -m task_orchestrator.consumer`