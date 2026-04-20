# Примеры использования

В этом документе описаны типичные сценарии использования RAS-like оркестратора, от простых до сложных.

## 1. Обработка критических инцидентов в IT‑мониторинге

### Контекст

У вас есть система мониторинга (например, Prometheus), которая генерирует алерты при превышении порогов CPU, памяти, диска. Некоторые алерты требуют немедленного вмешательства, другие — только записи в лог.

### Проблема

Как автоматически определить, какие алерты критичны, и запустить соответствующие действия (уведомление инженеров, запуск скриптов восстановления)?

### Решение с RAS

1. **Интеграция**: Настройте webhook в Prometheus Alertmanager, который отправляет алерты в RAS API Gateway.
2. **Scoring**: Salience Engine вычисляет salience score на основе severity (критичность алерта), urgency (время жизни) и impact (сколько сервисов затронуто).
3. **Режим системы**: Mode Manager переводит систему в elevated или critical режим при высокой нагрузке алертами.
4. **Прерывание**: Если salience score превышает порог, Interrupt Manager создаёт задачу для обработки.
5. **Действие**: Retriever Agent выполняет задачу — например, отправляет сообщение в Slack, создаёт инцидент в PagerDuty, запускает runbook через Ansible.

### Пример события

```json
{
  "event_id": "alert-cpu-server-01",
  "source": "prometheus",
  "severity": 0.9,
  "urgency": 0.8,
  "impact": 0.6,
  "metadata": {
    "alertname": "HighCPUUsage",
    "instance": "server-01",
    "value": "98%",
    "job": "node-exporter"
  }
}
```

### Политика

```yaml
name: high-cpu-alert
condition: event.severity > 0.8 and event.metadata.alertname == "HighCPUUsage"
action: interrupt
action_params:
  type: hard
  task_type: "remediate_cpu"
  priority: "high"
```

## 2. Управление задачами в распределённой команде поддержки

### Контекст

Команда поддержки получает запросы из разных каналов: email, чат, тикет‑система. Некоторые запросы срочные (например, сбой оплаты), другие могут ждать.

### Проблема

Как автоматически приоритизировать запросы и распределять их между агентами, учитывая загрузку и специализацию?

### Решение с RAS

1. **Приём запросов**: Каждый запрос преобразуется в событие и отправляется в RAS.
2. **Salience scoring**: Используются ML‑модели для определения срочности на основе текста запроса, истории клиента, времени суток.
3. **Режим работы**: Если накапливается много высокоприоритетных запросов, система переходит в elevated режим, увеличивая количество агентов (автоскейлинг).
4. **Создание задач**: Task Orchestrator создаёт задачи с метаданными (категория, требуемые навыки).
5. **Распределение**: Retriever Agent назначает задачи свободным агентам, учитывая их expertise.

### Пример события

```json
{
  "event_id": "ticket-12345",
  "source": "zendesk",
  "severity": 0.7,
  "urgency": 0.9,
  "impact": 0.5,
  "metadata": {
    "customer_tier": "premium",
    "category": "billing",
    "subject": "Payment failed",
    "created_at": "2026-04-20T10:00:00Z"
  }
}
```

### Политика

```yaml
name: premium-customer-billing
condition: event.metadata.customer_tier == "premium" and event.metadata.category == "billing"
action: interrupt
action_params:
  type: soft
  task_type: "handle_billing_ticket"
  assign_to: "billing_specialists"
  sla: "30 minutes"
```

## 3. Адаптивное управление ресурсами в облаке

### Контекст

В облачной инфраструктуре автоматически масштабируются приложения на основе метрик (CPU, RPS). Однако некоторые события (например, DDoS атака) требуют не только масштабирования, но и активации WAF, блокировки IP и уведомления security‑команды.

### Проблема

Как координировать ответ на сложные инциденты, затрагивающие несколько систем?

### Решение с RAS

1. **Сбор событий**: CloudWatch, Azure Monitor, GCP Logging отправляют метрики и логи в RAS.
2. **Композитный scoring**: Salience Engine анализирует несколько метрик одновременно, выявляя аномальные паттерны.
3. **Каскадные политики**: Policy Engine выполняет последовательность действий:
   - Если salience score > 0.7 → увеличить количество инстансов.
   - Если score > 0.9 → активировать WAF правила.
   - Если score > 0.95 → уведомить security команду и запустить forensic сбор.
4. **Чекпоинты**: Interrupt Manager сохраняет состояние перед каждым действием, чтобы можно было откатиться при необходимости.

### Пример события

```json
{
  "event_id": "ddos-detected",
  "source": "cloudflare",
  "severity": 0.95,
  "urgency": 1.0,
  "impact": 0.9,
  "metadata": {
    "attack_type": "HTTP flood",
    "requests_per_second": 10000,
    "target": "api.example.com"
  }
}
```

### Политика

```yaml
name: ddos-response
condition: event.metadata.attack_type == "HTTP flood" and event.severity > 0.9
actions:
  - action: scale
    params:
      service: "api-gateway"
      replicas: 10
  - action: enable_waf
    params:
      rule: "rate_limit_1000"
  - action: notify
    params:
      channel: "security"
      message: "DDoS attack detected on {{ event.metadata.target }}"
```

## 4. Персонализированные уведомления в приложении

### Контекст

Мобильное приложение отправляет push‑уведомления пользователям. Не все уведомления одинаково важны: некоторые информационные, другие — транзакционные (подтверждение оплаты), третьи — критические (безопасность).

### Проблема

Как определить, когда и какое уведомление отправить, чтобы не беспокоить пользователя в неподходящее время?

### Решение с RAS

1. **События от бэкенда**: Каждое потенциальное уведомление генерирует событие с параметрами: тип, важность, пользователь, контекст.
2. **Контекстуальный scoring**: Salience Engine учитывает историю пользователя, текущее время, локацию, активность в приложении.
3. **Режим пользователя**: Mode Manager для каждого пользователя может быть в режимах "active", "idle", "sleep". Уведомления в sleep режиме откладываются или подавляются.
4. **Прерывание**: Если уведомление достаточно важное, оно отправляется немедленно. Иначе ставится в очередь.

### Пример события

```json
{
  "event_id": "notif-789",
  "source": "backend",
  "severity": 0.6,
  "urgency": 0.3,
  "impact": 0.8,
  "metadata": {
    "user_id": "user-123",
    "notification_type": "transactional",
    "title": "Payment confirmed",
    "body": "Your payment of $50 was successful.",
    "timezone": "Europe/Moscow"
  }
}
```

### Политика

```yaml
name: transactional-notification
condition: event.metadata.notification_type == "transactional"
action: interrupt
action_params:
  type: delayed
  delay: "5 minutes"
  channel: "push"
  condition: "user.mode != 'sleep'"
```

## 5. Автоматическое документирование инцидентов

### Контекст

При возникновении инцидента команда тратит время на сбор логов, метрик, действий для постмортема.

### Проблема

Как автоматически собирать контекст инцидента и генерировать черновик постмортема?

### Решение с RAS

1. **Триггер**: Событие с высоким salience score активирует политику "document incident".
2. **Сбор данных**: Retriever Agent запрашивает логи из Loki, метрики из Prometheus, трассировки из Jaeger за период инцидента.
3. **Генерация отчёта**: Агент использует LLM для анализа данных и создания структурированного отчёта.
4. **Создание задачи**: Задача на проверку и доработку отчёта назначается ответственному инженеру.

### Пример события

```json
{
  "event_id": "incident-2026-04-20",
  "source": "monitoring",
  "severity": 0.9,
  "urgency": 0.7,
  "impact": 0.8,
  "metadata": {
    "component": "database",
    "start_time": "2026-04-20T14:00:00Z",
    "end_time": "2026-04-20T14:30:00Z",
    "root_cause": "connection pool exhaustion"
  }
}
```

### Политика

```yaml
name: auto-document-incident
condition: event.severity > 0.85 and event.metadata.component != ""
action: interrupt
action_params:
  type: soft
  task_type: "generate_postmortem"
  params:
    template: "standard_postmortem.md"
    assign_to: "team-lead"
```

## 6. Динамическое управление feature flags

### Контекст

Feature flags позволяют включать/выключать функциональность в runtime. Решения об изменении флагов принимаются на основе метрик (A/B тестирование, ошибки).

### Проблема

Как автоматически отключать фичу, если она вызывает рост ошибок или падение производительности?

### Решение с RAS

1. **События от мониторинга**: Система мониторинга отправляет метрики ошибок и latency для каждого feature flag.
2. **Scoring**: Salience Engine вычисляет score на основе дельты ошибок и latency.
3. **Политика**: Если score превышает порог, Policy Engine отправляет команду в сервис feature flags на отключение фичи.
4. **Уведомление**: Создаётся задача для разработчиков с деталями.

### Пример события

```json
{
  "event_id": "feature-flag-error",
  "source": "datadog",
  "severity": 0.75,
  "urgency": 0.8,
  "impact": 0.6,
  "metadata": {
    "flag_name": "new_checkout_ui",
    "error_rate_increase": 15.5,
    "latency_increase": 200,
    "timestamp": "2026-04-20T15:00:00Z"
  }
}
```

### Политика

```yaml
name: disable-feature-on-errors
condition: event.metadata.error_rate_increase > 10
action: webhook
action_params:
  url: "http://feature-flags-service/api/flags/{{ event.metadata.flag_name }}/disable"
  method: POST
```

## 7. Координация роботов в warehouse

### Контекст

На складе работают автономные роботы, которые перемещают товары. Каждый робот отправляет события о своём состоянии (заряд батареи, загрузка, местоположение).

### Проблема

Как динамически перераспределять задачи между роботами при сбое или низком заряде?

### Решение с RAS

1. **События от роботов**: Каждый робот отправляет heartbeat и event при изменении состояния.
2. **Salience scoring**: Низкий заряд батареи или поломка получают высокий score.
3. **Прерывание**: Interrupt Manager перепланирует задачи: переназначает их другим роботам.
4. **Задача на обслуживание**: Создаётся задача для техника.

### Пример события

```json
{
  "event_id": "robot-05-low-battery",
  "source": "robot-05",
  "severity": 0.8,
  "urgency": 0.9,
  "impact": 0.7,
  "metadata": {
    "battery_level": 12,
    "current_task": "move_pallet_123",
    "location": "zone-A"
  }
}
```

### Политика

```yaml
name: robot-low-battery
condition: event.metadata.battery_level < 20
action: interrupt
action_params:
  type: hard
  task_type: "reassign_tasks"
  params:
    robot_id: "{{ event.source }}"
    priority: "high"
```

## Заключение

RAS-like оркестратор предоставляет гибкую платформу для обработки событий и принятия решений в реальном времени. Эти use cases демонстрируют, как система может быть адаптирована под различные домены: IT‑операции, поддержка пользователей, безопасность, IoT и другие.

Для реализации своего сценария:

1. Определите источники событий.
2. Настройте scoring параметры.
3. Создайте политики, отражающие вашу бизнес‑логику.
4. Интегрируйте с внешними системами через webhooks или Kafka.
5. Настройте мониторинг и алертинг.

Обратитесь к [документации по архитектуре](../architecture/overview.md) и [API](../api/README.md) для деталей.