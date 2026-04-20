# Начало работы

Это руководство поможет вам быстро запустить RAS-like оркестратор и отправить первое событие.

## Предварительные требования

- Docker и Docker Compose
- curl или Postman для отправки HTTP запросов
- (опционально) Python 3.10+ для работы с CLI

## Быстрый старт с Docker Compose

Самый простой способ запустить всю систему — использовать Docker Compose.

1. **Клонируйте репозиторий** (если ещё не сделали):

```bash
git clone https://github.com/your-org/ras-orchestrator.git
cd ras-orchestrator
```

2. **Запустите все сервисы**:

```bash
docker-compose up -d
```

Эта команда запустит:
- **API Gateway** на порту 8000
- **Salience Engine**, **Mode Manager**, **Interrupt Manager**, **Task Orchestrator**, **Retriever Agent** (как consumers Kafka)
- **Kafka**, **Redis**, **PostgreSQL**
- **Observability стек** (Prometheus, Grafana, Loki, Jaeger)

3. **Проверьте, что все сервисы запущены**:

```bash
docker-compose ps
```

Вы должны увидеть состояние `Up` для всех контейнеров.

4. **Отправьте тестовое событие**:

```bash
curl -X POST http://localhost:8000/events \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "test-1",
    "source": "manual",
    "severity": 0.8,
    "urgency": 0.7,
    "impact": 0.9,
    "metadata": {"user": "admin"}
  }'
```

Если всё работает, вы получите ответ:

```json
{
  "event_id": "test-1",
  "status": "accepted",
  "message": "Event received and queued for processing"
}
```

5. **Проверьте обработку события**:

- **Логи**: просмотрите логи любого компонента, например:

```bash
docker-compose logs salience-engine
```

- **Grafana**: откройте http://localhost:3000 (логин: admin, пароль: admin) и перейдите на дашборд **Event Flow**.
- **Jaeger**: откройте http://localhost:16686 для просмотра трассировок.

## Структура события

Событие — это JSON объект, который отправляется в систему. Обязательные поля:

| Поле | Тип | Описание | Диапазон |
|------|-----|----------|----------|
| `event_id` | string | Уникальный идентификатор события | Любая строка |
| `source` | string | Источник события (например, "monitoring", "user", "api") | Любая строка |
| `severity` | float | Серьёзность события (насколько оно критично) | 0.0 – 1.0 |
| `urgency` | float | Срочность (насколько быстро нужно реагировать) | 0.0 – 1.0 |
| `impact` | float | Влияние (масштаб последствий) | 0.0 – 1.0 |
| `metadata` | object | Дополнительные данные | Любой JSON |

Пример:

```json
{
  "event_id": "alert-123",
  "source": "monitoring",
  "severity": 0.95,
  "urgency": 0.8,
  "impact": 0.7,
  "metadata": {
    "host": "server-01",
    "metric": "cpu_usage",
    "value": 98.5
  }
}
```

## Проверка состояния системы

### Health checks

Каждый компонент предоставляет health endpoint:

- **API Gateway**: `GET http://localhost:8000/health`
- **Policy Engine**: `GET http://localhost:8001/health`
- **Workspace Service**: `GET http://localhost:8002/health`

Пример:

```bash
curl http://localhost:8000/health
```

Ответ:

```json
{
  "status": "healthy",
  "timestamp": "2026-04-20T15:35:00Z",
  "details": {
    "kafka": "connected",
    "redis": "connected"
  }
}
```

### Метрики Prometheus

Метрики доступны на порту 9090:

```bash
curl http://localhost:9090/metrics
```

### Дашборды Grafana

Предустановленные дашборды:

1. **System Health** – общее состояние системы.
2. **Event Flow** – поток событий и задержки.
3. **Interrupt Analysis** – анализ прерываний.
4. **Task Performance** – производительность задач.
5. **Kafka Monitoring** – мониторинг Kafka.
6. **Redis Monitoring** – мониторинг Redis.

## Управление политиками

Политики определяют, как система реагирует на события. Вы можете управлять ими через веб‑интерфейс или API.

### Веб‑интерфейс

Откройте http://localhost:8001 в браузере. Вы увидите интерфейс Policy Engine, где можно:

- Просматривать существующие политики.
- Создавать новые политики.
- Тестировать политики на примерах событий.
- Активировать/деактивировать политики.

### API

Policy Engine предоставляет REST API:

- **Получить все политики**:

```bash
curl http://localhost:8001/api/v1/policies
```

- **Создать политику**:

```bash
curl -X POST http://localhost:8001/api/v1/policies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "high-severity-interrupt",
    "description": "Прерывать при высокой серьёзности",
    "condition": "event.severity > 0.9",
    "action": "interrupt",
    "action_params": {"type": "soft"}
  }'
```

- **Протестировать политику**:

```bash
curl -X POST http://localhost:8001/api/v1/policies/test \
  -H "Content-Type: application/json" \
  -d '{
    "policy": "event.severity > 0.9",
    "event": {"severity": 0.95}
  }'
```

## Создание и мониторинг задач

Когда событие приводит к прерыванию, создаётся задача. Задачи обрабатываются Retriever Agent.

### Просмотр задач

Задачи хранятся в Redis и PostgreSQL. Для просмотра можно использовать API Workspace Service:

```bash
curl http://localhost:8002/api/v1/tasks
```

Или подключиться к PostgreSQL:

```bash
docker-compose exec postgres psql -U ras -d ras -c "SELECT * FROM tasks LIMIT 5;"
```

### Статусы задач

- **pending**: Задача создана, но ещё не взята агентом.
- **running**: Агент обрабатывает задачу.
- **completed**: Задача успешно выполнена.
- **failed**: Задача завершилась с ошибкой.
- **cancelled**: Задача отменена.

## Интеграция с внешними системами

RAS-like оркестратор может интегрироваться с внешними системами через webhooks, Kafka или REST API.

### Webhooks

Настройте webhook в политике, чтобы отправлять уведомления при определённых условиях.

Пример политики с webhook:

```yaml
name: notify-slack
condition: event.severity > 0.8
action: webhook
action_params:
  url: "https://hooks.slack.com/services/..."
  method: POST
  body: |
    {
      "text": "High severity event: {{ event.event_id }}"
    }
```

### Kafka

Система публикует события в топики Kafka, которые могут потребляться внешними приложениями.

Основные топики:

- `ras.events` – исходные события.
- `ras.salience.scores` – salience scores.
- `ras.mode.transitions` – переходы между режимами.
- `ras.interrupt.decisions` – решения о прерывании.
- `ras.tasks` – задачи.

Вы можете подключить свой consumer к этим топикам.

## Отладка

### Логи

Логи всех компонентов собираются в Loki. Для поиска логов используйте Grafana (раздел Explore) или LogCLI.

Пример запроса логов API Gateway:

```bash
docker-compose exec loki logcli query '{app="api-gateway"}' --limit=10
```

### Трассировки

Трассировки хранятся в Jaeger. Откройте http://localhost:16686, выберите сервис (например, `api-gateway`) и найдите trace.

### Метрики

Используйте Prometheus для запроса метрик. Например, количество событий за последние 5 минут:

```promql
rate(ras_events_total[5m])
```

## Остановка системы

Чтобы остановить все сервисы:

```bash
docker-compose down
```

Если вы хотите также удалить тома (данные Kafka, Redis, PostgreSQL):

```bash
docker-compose down -v
```

## Дальнейшие шаги

1. **Изучите архитектуру**: Прочтите [архитектурную документацию](../architecture/overview.md).
2. **Настройте политики**: Создайте политики, соответствующие вашим use cases.
3. **Интегрируйте с вашими системами**: Настройте webhooks или Kafka consumers.
4. **Настройте мониторинг**: Добавьте алерты в Alertmanager.
5. **Разверните в production**: Следуйте [production руководству](../deployment/production.md).

## Получение помощи

- **Документация**: Все документы находятся в директории `docs/`.
- **Issues**: Сообщайте о проблемах в GitHub Issues.
- **Slack**: Присоединяйтесь к каналу `#ras-support`.