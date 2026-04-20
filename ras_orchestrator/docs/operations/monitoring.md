# Мониторинг и алертинг

Мониторинг RAS-like оркестратора осуществляется с помощью стека Observability (Prometheus, Grafana, Loki, Jaeger). В этом разделе описаны ключевые метрики, дашборды, правила алертинга и процедуры реагирования.

## Ключевые метрики

### Бизнес-метрики

| Метрика | Тип | Описание | Порог для алерта |
|---------|-----|----------|------------------|
| `ras_events_total` | Counter | Количество принятых событий, разбивка по типу и severity | Резкое падение (0 событий за 5 минут) |
| `ras_salience_score_distribution` | Histogram | Распределение salience score (0–1) | Средний score > 0.9 (возможная аномалия) |
| `ras_mode_transitions_total` | Counter | Количество переходов между режимами | Частые переходы (>10 в минуту) |
| `ras_interrupt_decisions_total` | Counter | Решения о прерывании | Высокий процент прерываний (>50% от событий) |
| `ras_tasks_created_total` | Counter | Созданные задачи | Резкий рост (>1000 в минуту) |
| `ras_tasks_completed_total` | Counter | Завершённые задачи | Низкая completion rate (<80%) |
| `ras_agent_tasks_processed_total` | Counter | Обработанные задачи агентом | Падение throughput (>30% от baseline) |

### Системные метрики

| Метрика | Тип | Описание | Порог для алерта |
|---------|-----|----------|------------------|
| `http_requests_total` | Counter | HTTP запросы к API Gateway | Высокий уровень ошибок 5xx (>5%) |
| `http_request_duration_seconds` | Histogram | Задержка обработки запросов | p95 > 1 секунда |
| `redis_operations_total` | Counter | Операции с Redis | Высокая задержка (>100 мс) |
| `kafka_consumer_lag` | Gauge | Lag потребителей Kafka | Lag > 1000 сообщений |
| `kafka_producer_record_send_total` | Counter | Отправленные записи в Kafka | Падение до 0 (проблема с producer) |
| `cpu_usage` | Gauge | Использование CPU компонентами | >80% в течение 5 минут |
| `memory_usage` | Gauge | Использование памяти | >90% от limit |

### Метрики состояния

| Метрика | Тип | Описание | Порог для алерта |
|---------|-----|----------|------------------|
| `ras_current_mode` | Gauge | Текущий режим системы (low=1, normal=2, elevated=3, critical=4) | Режим critical дольше 10 минут |
| `ras_cooldown_active` | Gauge | Активен ли cooldown после critical (0/1) | - |
| `ras_checkpoint_count` | Gauge | Количество чекпоинтов в Redis | Резкий рост (>1000) |
| `ras_active_tasks_count` | Gauge | Количество активных задач | >50 (возможная перегрузка) |

## Дашборды Grafana

Предустановленные дашборды находятся в `observability/grafana/dashboards/`. После развёртывания они автоматически загружаются в Grafana.

### 1. System Health

Общее состояние системы: здоровье компонентов, использование ресурсов, метрики инфраструктуры.

- **Панели**:
  - CPU и память по компонентам
  - Количество подов
  - Health checks (зелёный/красный)
  - Доступность Kafka, Redis, PostgreSQL

### 2. Event Flow

Визуализация потока событий через систему.

- **Панели**:
  - События в секунду по типам
  - Salience score distribution
  - Задержка обработки события (от приёма до завершения задачи)
  - Топ источников событий

### 3. Interrupt Analysis

Анализ прерываний и решений.

- **Панели**:
  - Количество решений о прерывании (всего/сработавших)
  - Причины прерываний
  - Типы прерываний (soft/hard/delayed)
  - Чекпоинты созданные/восстановленные

### 4. Task Performance

Производительность задач и агентов.

- **Панели**:
  - Время выполнения задачи (среднее, перцентили)
  - Статусы задач (pending, running, completed, failed)
  - Retry count
  - Throughput агентов

### 5. Kafka Monitoring

Мониторинг Kafka топиков и потребителей.

- **Панели**:
  - Lag по consumer groups
  - Throughput (messages in/out)
  - Размер топиков
  - Количество partitions

### 6. Redis Monitoring

Использование Redis.

- **Панели**:
  - Использование памяти
  - Количество ключей
  - Hit/miss ratio
  - Latency операций

## Правила алертинга

Правила определены в `observability/alert_rules.yml` и загружаются Prometheus.

### Критические алерты (Critical)

1. **NoEventsReceived**
   - Условие: `rate(ras_events_total[5m]) == 0`
   - Длительность: 5 минут
   - Описание: Ни одного события не получено за 5 минут. Возможна недоступность API Gateway или отсутствие трафика.

2. **HighErrorRate**
   - Условие: `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05`
   - Длительность: 2 минуты
   - Описание: Более 5% запросов возвращают ошибки 5xx.

3. **CriticalModeTooLong**
   - Условие: `ras_current_mode == 4`
   - Длительность: 10 минут
   - Описание: Система находится в critical режиме дольше 10 минут. Возможно, не удаётся обработать высокоприоритетные события.

4. **KafkaConsumerLagHigh**
   - Условие: `kafka_consumer_lag > 1000`
   - Длительность: 5 минут
   - Описание: Consumer lag превышает 1000 сообщений. Обработка событий отстаёт.

5. **RedisDown**
   - Условие: `redis_up == 0`
   - Длительность: 1 минута
   - Описание: Redis недоступен. Работа системы нарушена.

### Предупреждения (Warning)

1. **HighLatency**
   - Условие: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1`
   - Длительность: 5 минут
   - Описание: 95-й перцентиль задержки запросов превышает 1 секунду.

2. **HighCPUUsage**
   - Условие: `rate(container_cpu_usage_seconds_total[5m]) > 0.8`
   - Длительность: 10 минут
   - Описание: Использование CPU компонентом превышает 80%.

3. **HighInterruptRate**
   - Условие: `rate(ras_interrupt_decisions_total{should_interrupt="true"}[5m]) / rate(ras_interrupt_decisions_total[5m]) > 0.5`
   - Длительность: 5 минут
   - Описание: Более 50% событий приводят к прерыванию. Возможно, политики слишком агрессивны.

4. **TaskFailureRateHigh**
   - Условие: `rate(ras_tasks_failed_total[5m]) / rate(ras_tasks_created_total[5m]) > 0.2`
   - Длительность: 5 минут
   - Описание: Более 20% задач завершаются с ошибкой.

## Нотификации

Alertmanager конфигурируется через `observability/alertmanager.yml`. Поддерживаются следующие каналы:

- **Slack**: Отправка в канал `#ras-alerts`.
- **Email**: Рассылка на адреса команды.
- **PagerDuty**: Эскалация для critical алертов.
- **Webhook**: Интеграция с внутренними системами (например, OpsGenie).

Пример конфигурации Slack:

```yaml
route:
  group_by: ['alertname']
  receiver: 'slack-notifications'
receivers:
- name: 'slack-notifications'
  slack_configs:
  - channel: '#ras-alerts'
    send_resolved: true
    title: '{{ .GroupLabels.alertname }}'
    text: '{{ .Annotations.description }}'
```

## Процедуры реагирования

### 1. Получение алерта

1. Определить severity (critical/warning) и компонент.
2. Проверить соответствующий дашборд в Grafana для контекста.
3. Изучить логи (Loki) и трассировки (Jaeger) для периода алерта.

### 2. Диагностика

Используйте следующие команды для сбора информации:

```bash
# Проверить состояние подов
kubectl get pods -n ras

# Логи компонента
kubectl logs -f deployment/api-gateway -n ras

# Метарики Prometheus (если доступен порт-форвард)
kubectl port-forward svc/monitoring-prometheus 9090:9090 -n monitoring

# Проверить Kafka lag
kubectl exec -it deployment/salience-engine -n ras -- kafka-consumer-groups --bootstrap-server kafka:9092 --describe --group ras-salience
```

### 3. Временные меры

- **Перезапуск проблемного компонента**: `kubectl rollout restart deployment/api-gateway -n ras`
- **Масштабирование**: Увеличить количество реплик для компонента под нагрузкой.
- **Отключение политик**: Если алерт связан с высоким interrupt rate, временно отключите политики через API.

### 4. Постоянное решение

- Анализ root cause (логи, метрики, трассировки).
- Внесение изменений в конфигурацию, код или инфраструктуру.
- Обновление runbooks и документации.

## Ежедневные проверки

Оператор должен выполнять следующие проверки:

1. **Просмотр дашбордов**:
   - System Health: все компоненты зелёные.
   - Event Flow: поток событий стабилен.
   - Kafka lag: в пределах нормы.

2. **Проверка алертов**:
   - Убедиться, что нет необработанных critical алертов.
   - Проверить warning алерты, оценить необходимость действий.

3. **Проверка ресурсов**:
   - Достаточно ли CPU/памяти.
   - Не приближается ли использование диска к limit.

4. **Резервное копирование**:
   - Убедиться, что backup PostgreSQL и Redis выполнен успешно.

## Обслуживание

### Обновление компонентов

1. **Плановое обновление**:
   - Обновить образ контейнера до новой версии.
   - Использовать canary deployment для минимизации риска.
   - Мониторить метрики во время обновления.

2. **Обновление инфраструктуры**:
   - Обновление версий Kafka, Redis, PostgreSQL должно проводиться в соответствии с best practices поставщика.

### Очистка данных

- **Redis**: Установите TTL для ключей, чтобы автоматически очищать старые данные.
- **Kafka**: Настройте retention policy для топиков (например, 7 дней).
- **PostgreSQL**: Архивируйте старые события и задачи в cold storage.

## Документация инцидентов

Каждый инцидент должен быть документирован в системе управления инцидентами (например, Jira, Incident.io). Включите:

- Время начала и окончания.
- Затронутые компоненты.
- Root cause.
- Действия по восстановлению.
- Превентивные меры на будущее.