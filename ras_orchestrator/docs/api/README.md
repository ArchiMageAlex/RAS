# API документация

RAS-like оркестратор предоставляет REST API для взаимодействия с внешними системами, управления политиками и мониторинга состояния. Все endpoints документированы в формате OpenAPI 3.0 (Swagger). Вы можете просмотреть интерактивную документацию, запустив сервис и перейдя по адресу `http://localhost:8000/docs` (Swagger UI) или `http://localhost:8000/redoc` (ReDoc).

## Базовый URL

- Локальная разработка: `http://localhost:8000`
- Production: `https://api.ras.example.com`

## Аутентификация

Для защиты endpoints используется API ключ, передаваемый в заголовке `X-API-Key`. В текущей версии аутентификация опциональна и может быть отключена. В production рекомендуется использовать более строгие механизмы (OAuth2, JWT).

Пример заголовка:
```http
X-API-Key: your-secret-api-key
```

## Основные endpoints

### 1. Приём событий

**POST /events**

Принимает событие от внешней системы. Событие валидируется, генерируется уникальный `event_id`, и оно публикуется в Kafka для дальнейшей обработки.

**Тело запроса:**
```json
{
  "type": "payment_outage",
  "severity": "critical",
  "source": "payment_service",
  "payload": {
    "error_rate": 0.95,
    "region": "us-east-1"
  },
  "metadata": {
    "origin": "monitoring",
    "correlation_id": "abc123"
  }
}
```

**Ответ:**
```json
{
  "event_id": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
  "status": "accepted",
  "message": "Event is being processed."
}
```

**Коды ответа:**
- `200` – успешно
- `400` – невалидные данные
- `500` – внутренняя ошибка (например, Kafka недоступна)

### 2. Проверка здоровья

**GET /health**

Возвращает статус сервиса и состояние зависимостей (Kafka, Redis, PostgreSQL).

**Ответ:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "components": {
    "kafka": "healthy",
    "redis": "healthy",
    "postgres": "healthy"
  }
}
```

### 3. Метрики Prometheus

**GET /metrics**

Возвращает метрики в формате Prometheus. Используется для мониторинга.

### 4. Управление политиками

#### GET /policies/types
Возвращает список поддерживаемых типов политик.

**Ответ:**
```json
{
  "types": [
    "interrupt",
    "mode",
    "action",
    "tool_access",
    "human_escalation",
    "routing"
  ]
}
```

#### GET /policies/files
Список YAML файлов с политиками.

#### GET /policies/file/{filename}
Содержимое конкретного файла политик.

#### POST /policies/evaluate
Оценка политик для заданного контекста.

**Тело запроса:**
```json
{
  "policy_type": "interrupt",
  "context": {
    "event": {
      "type": "security_alert",
      "severity": "critical"
    },
    "salience": {
      "risk": 0.9
    },
    "current_mode": "normal",
    "active_task_count": 3
  }
}
```

**Ответ:**
```json
{
  "matched": true,
  "policies": [
    {
      "name": "high_risk_security",
      "version": "1.0",
      "enabled": true,
      "priority": 10,
      "tags": ["security", "high_priority"],
      "conditions": { ... },
      "actions": { ... }
    }
  ],
  "actions": {
    "action": "interrupt",
    "reason": "Высокий риск безопасности"
  }
}
```

#### POST /policies/reload
Принудительная перезагрузка политик из файлов (hot-reload).

### 5. Управление задачами

#### GET /tasks
Список задач с фильтрацией по статусу.

**Параметры запроса:**
- `status` (опционально) – фильтр по статусу (pending, running, completed, failed, interrupted)
- `limit` (опционально) – максимальное количество задач (по умолчанию 100)

**Ответ:**
```json
{
  "tasks": [
    {
      "task_id": "task-123",
      "event_id": "event-456",
      "agent_type": "retriever",
      "status": "completed",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:05Z",
      "parameters": { ... },
      "result": { ... }
    }
  ]
}
```

#### GET /tasks/{task_id}
Детали задачи по ID.

### 6. Системная информация

#### GET /mode/current
Текущий режим системы.

**Ответ:**
```json
{
  "current_mode": "normal",
  "last_transition": "2024-01-01T11:30:00Z",
  "manual_lock": false
}
```

#### GET /interrupt/stats
Статистика прерываний.

**Ответ:**
```json
{
  "total_decisions": 150,
  "interrupts_triggered": 42,
  "interrupt_rate": 0.28,
  "by_type": {
    "soft": 30,
    "hard": 10,
    "delayed": 2
  },
  "checkpoint_count": 25
}
```

## Ошибки

Все endpoints возвращают ошибки в едином формате:

```json
{
  "error": "Описание ошибки",
  "detail": "Дополнительные детали (опционально)",
  "code": 400
}
```

Коды ошибок:
- `400` – Bad Request (невалидные данные)
- `401` – Unauthorized (отсутствует или неверный API ключ)
- `404` – Not Found (ресурс не найден)
- `500` – Internal Server Error (внутренняя ошибка сервиса)

## Примеры использования

### Отправка события с помощью curl

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "type": "payment_outage",
    "severity": "critical",
    "source": "payment_service",
    "payload": {"error_rate": 0.95}
  }'
```

### Получение текущего режима

```bash
curl http://localhost:8000/mode/current
```

### Оценка политик

```bash
curl -X POST http://localhost:8000/policies/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "policy_type": "interrupt",
    "context": {
      "event": {"type": "security_alert", "severity": "critical"},
      "salience": {"risk": 0.9}
    }
  }'
```

## Генерация клиентского кода

Используя OpenAPI спецификацию (`openapi.yaml`), можно сгенерировать клиентский код для различных языков с помощью инструментов типа [OpenAPI Generator](https://openapi-generator.tech/).

Пример генерации клиента для Python:

```bash
openapi-generator generate -i docs/api/openapi.yaml -g python -o ./client
```

## Примечания

- Все даты и время возвращаются в формате ISO 8601 (UTC).
- Для работы с политиками требуется аутентификация (если включена).
- Endpoints, изменяющие состояние (POST, PUT, DELETE), могут быть защищены дополнительными правами (в будущих версиях).