# Docker Compose развёртывание

Docker Compose позволяет быстро развернуть всю систему RAS-like оркестратора вместе с зависимостями (Kafka, Redis, PostgreSQL, Observability stack) на одной машине. Это идеально для разработки, тестирования и демонстраций.

## Файл docker-compose.yml

Основной файл конфигурации находится в корне проекта: `ras_orchestrator/docker-compose.yml`. Он определяет следующие сервисы:

1. **Инфраструктура**:
   - `zookeeper` – координатор для Kafka.
   - `kafka` – брокер событий.
   - `redis` – хранилище рабочего пространства.
   - `postgres` – постоянное хранилище для задач и событий.

2. **Observability stack**:
   - `prometheus` – сбор метрик.
   - `grafana` – визуализация.
   - `jaeger` – распределённая трассировка.
   - `loki` – хранение логов.
   - `promtail` – сбор логов.
   - `alertmanager` – управление алертами.

3. **Компоненты RAS**:
   - `api_gateway` – FastAPI приложение (порт 8000).
   - `salience_engine` – потребитель событий, вычисляет salience score.
   - `mode_manager` – управление режимами.
   - `interrupt_manager` – менеджер прерываний.
   - `task_orchestrator` – оркестратор задач.
   - `retriever_agent` – агент выполнения задач.

## Требования

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4 ГБ свободной оперативной памяти (минимум)
- 10 ГБ свободного места на диске

## Быстрый старт

1. Клонируйте репозиторий и перейдите в директорию проекта:

```bash
git clone <repository-url>
cd ras_orchestrator
```

2. Запустите все сервисы в фоновом режиме:

```bash
docker-compose up -d
```

3. Проверьте статус:

```bash
docker-compose ps
```

Все сервисы должны быть в состоянии `Up`. Первый запуск может занять несколько минут из-за загрузки образов.

## Порты

После запуска следующие порты будут доступны локально:

| Сервис | Порт | Назначение |
|--------|------|------------|
| API Gateway | 8000 | REST API, Swagger UI (`/docs`) |
| Grafana | 3000 | Дашборды (логин: admin, пароль: admin) |
| Prometheus | 9090 | Метрики и алерты |
| Jaeger UI | 16686 | Трассировки |
| Loki | 3100 | Логи (через Grafana) |
| Alertmanager | 9093 | Управление алертами |
| Kafka | 9092 | Брокер событий |
| Redis | 6379 | Рабочее пространство |
| PostgreSQL | 5432 | База данных |

## Конфигурация

### Переменные окружения

Каждый компонент RAS настраивается через переменные окружения, определённые в `docker-compose.yml`. Вы можете переопределить их, создав файл `.env` в той же директории.

Пример `.env`:

```env
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
REDIS_HOST=redis
POSTGRES_URL=postgresql://ras_user:ras_password@postgres:5432/ras_db
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

### Настройка Observability

- **Prometheus**: конфигурация в `observability/prometheus.yml`. Добавление новых targets требует изменения этого файла и перезапуска prometheus.
- **Grafana**: дашборды и источники данных provisioned через `observability/grafana/dashboards/` и `observability/grafana/datasources/`.
- **Alertmanager**: конфигурация алертов в `observability/alert_rules.yml` и `observability/alertmanager.yml`.

### Масштабирование компонентов

Вы можете масштабировать любой компонент RAS, запустив несколько экземпляров:

```bash
docker-compose up -d --scale salience_engine=3 --scale task_orchestrator=2
```

Kafka consumer groups автоматически распределят нагрузку между экземплярами.

## Проверка работоспособности

1. **API Gateway**: Откройте в браузере `http://localhost:8000/docs`. Должна появиться Swagger UI.

2. **Grafana**: Перейдите на `http://localhost:3000`, войдите с admin/admin. Должны быть предустановленные дашборды "System Health" и "Event Flow".

3. **Jaeger**: Перейдите на `http://localhost:16686`. Выберите сервис `api-gateway` и найдите traces.

4. **Отправка тестового события**:

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "payment_outage",
    "severity": "critical",
    "source": "test",
    "payload": {"test": true}
  }'
```

Ответ должен содержать `event_id`. Проверьте логи компонентов:

```bash
docker-compose logs salience_engine
```

## Остановка и очистка

Остановить все сервисы:

```bash
docker-compose down
```

Удалить тома (данные Redis, PostgreSQL, метрики Prometheus):

```bash
docker-compose down -v
```

Остановить только определённые сервисы:

```bash
docker-compose stop api_gateway salience_engine
```

## Production-подобное развёртывание

Docker Compose конфигурация предназначена для разработки. Для production рекомендуется:

1. **Использовать внешние managed сервисы**:
   - Kafka: Confluent Cloud, Amazon MSK
   - Redis: Elasticache, Redis Cloud
   - PostgreSQL: RDS, Cloud SQL

2. **Настройка безопасности**:
   - Включить TLS для всех соединений.
   - Использовать секреты (Docker Secrets, HashiCorp Vault) для паролей.
   - Ограничить доступ к портам с помощью сетевых политик.

3. **Мониторинг и логирование**:
   - Интегрировать Prometheus с внешним Alertmanager (например, PagerDuty).
   - Настроить экспорт логов в централизованную систему (ELK, Datadog).

4. **Высокая доступность**:
   - Запускать несколько экземпляров каждого компонента в разных availability zones.
   - Использовать балансировщик нагрузки перед API Gateway.

## Известные проблемы

- **Потребление памяти**: Observability stack может потреблять много памяти. При ограниченных ресурсах можно отключить ненужные сервисы (например, Loki, Jaeger) в `docker-compose.yml`.
- **Задержка запуска**: Kafka и Zookeeper требуют времени для инициализации. Компоненты RAS могут падать при попытке подключения до готовности Kafka. В конфигурации используется `depends_on` с условием `service_started`, но это не гарантирует полную готовность. При необходимости добавьте health checks и restart policies.
- **Данные в томах**: Тома сохраняются между перезапусками. Если нужно очистить данные, удалите тома командой `docker-compose down -v`.

## Дальнейшие шаги

После успешного развёртывания с помощью Docker Compose вы можете:

- Изучить [Kubernetes развёртывание](../deployment/kubernetes.md) для production.
- Настроить [политики](../architecture/components/policy_engine.md) под свои нужды.
- Интегрировать с внешними системами мониторинга (Prometheus remote write, Grafana Cloud).