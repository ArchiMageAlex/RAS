# Часто задаваемые вопросы (FAQ)

## Общие вопросы

### Что такое RAS-like оркестратор?

RAS-like оркестратор — это система для обработки событий в реальном времени, вдохновлённая биологической ретикулярной активирующей системой (RAS). Она оценивает важность событий (salience scoring), управляет режимами работы (mode management) и принимает решения о прерываниях (interrupt decisions) на основе политик.

### Какие проблемы решает эта система?

- **Приоритизация событий**: Автоматическое определение, какие события требуют немедленного внимания.
- **Управление вниманием**: Динамическое переключение между режимами работы (normal, elevated, critical) в зависимости от нагрузки.
- **Автоматическое реагирование**: Выполнение действий (уведомления, создание задач, запуск скриптов) через политики.
- **Наблюдаемость**: Полный стек мониторинга, логирования и трассировки для диагностики.

### Кому подходит эта система?

- **SRE и DevOps** для обработки алертов и автоматического восстановления.
- **Команды поддержки** для приоритизации и распределения тикетов.
- **Разработчики** для управления feature flags и A/B тестирования.
- **Security teams** для координации ответа на инциденты.

### Какие технологии используются?

- **Языки**: Python (основные компоненты), SQL (PostgreSQL), YAML (политики).
- **Инфраструктура**: Kafka (event bus), Redis (рабочее пространство), PostgreSQL (постоянное хранилище).
- **Observability**: Prometheus, Grafana, Loki, Jaeger, OpenTelemetry.
- **Оркестрация**: Docker, Kubernetes.

## Установка и настройка

### Как быстро запустить систему для тестирования?

Используйте Docker Compose:

```bash
git clone https://github.com/your-org/ras-orchestrator.git
cd ras-orchestrator
docker-compose up -d
```

Через несколько минут система будет доступна на http://localhost:8000 (API Gateway) и http://localhost:3000 (Grafana).

### Какие порты используются по умолчанию?

- **8000**: API Gateway
- **8001**: Policy Engine (веб‑интерфейс)
- **8002**: Workspace Service
- **9090**: Prometheus
- **3000**: Grafana
- **16686**: Jaeger
- **9092**: Kafka
- **6379**: Redis
- **5432**: PostgreSQL

### Как изменить конфигурацию?

Скопируйте `.env.example` в `.env` и отредактируйте переменные. Для Docker Compose можно создать `docker-compose.override.yml`.

### Нужно ли отдельно настраивать Kafka и Redis?

Нет, они включены в `docker-compose.yml` и настроены автоматически. В production вы можете использовать managed services (например, Confluent Cloud, Amazon MSK, Elasticache).

## Использование

### Как отправить событие?

Используйте HTTP POST на `/events` с API‑ключом:

```bash
curl -X POST http://localhost:8000/events \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "test", "source": "test", "severity": 0.5, "urgency": 0.5, "impact": 0.5}'
```

### Где взять API‑ключ?

По умолчанию используется `dev-key-123`. В production сгенерируйте ключ и сохраните его в secrets manager. Ключ передаётся в заголовке `X-API-Key`.

### Как просмотреть логи?

Логи собираются в Loki. Используйте Grafana (раздел Explore) или LogCLI:

```bash
docker-compose exec loki logcli query '{app="api-gateway"}' --limit=10
```

### Как проверить, что событие обработано?

1. Посмотрите логи Salience Engine: `docker-compose logs salience-engine`
2. Проверьте топик Kafka `ras.salience.scores`:
   ```bash
   docker-compose exec kafka kafka-console-consumer --topic ras.salience.scores --from-beginning --bootstrap-server localhost:9092
   ```
3. Откройте Grafana дашборд **Event Flow**.

### Как создать политику?

Через веб‑интерфейс Policy Engine (http://localhost:8001) или через API:

```bash
curl -X POST http://localhost:8001/api/v1/policies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-policy",
    "condition": "event.severity > 0.8",
    "action": "webhook",
    "action_params": {"url": "http://example.com"}
  }'
```

### Как тестировать политику?

Используйте endpoint `/api/v1/policies/test`:

```bash
curl -X POST http://localhost:8001/api/v1/policies/test \
  -H "Content-Type: application/json" \
  -d '{
    "policy": "event.severity > 0.8",
    "event": {"severity": 0.9}
  }'
```

### Как управлять режимами вручную?

Отправьте запрос на `/api/v1/mode/force`:

```bash
curl -X POST http://localhost:8000/api/v1/mode/force \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{"mode": "elevated", "reason": "manual override"}'
```

## Настройка и кастомизация

### Как изменить алгоритм scoring?

Отредактируйте `salience_engine/scoring.py` или `salience_engine/advanced_scoring.py`. Вы можете выбрать линейную комбинацию, ML‑модель или написать свой алгоритм.

### Как добавить новое поле в событие?

1. Обновите модель `Event` в `common/models.py`.
2. Обновите валидацию в API Gateway.
3. При необходимости измените scoring алгоритм, чтобы учитывать новое поле.

### Как интегрироваться с внешней системой?

Используйте действие `webhook` в политиках или напишите custom action в `policy_engine/actions/`. Также можно потреблять топики Kafka (`ras.events`, `ras.tasks`) из вашего приложения.

### Как настроить алертинг?

Правила алертов определены в `observability/alert_rules.yml`. Отредактируйте файл и перезапустите Prometheus. Уведомления настраиваются в `observability/alertmanager.yml`.

### Как увеличить пропускную способность?

- Увеличьте количество partitions топика Kafka.
- Масштабируйте компоненты (например, запустите больше реплик Salience Engine).
- Оптимизируйте scoring алгоритм (кеширование, batch processing).
- Используйте более мощные инстансы для Redis и PostgreSQL.

## Поиск и устранение неисправностей

### События не поступают в систему

1. Проверьте, что API Gateway запущен: `curl http://localhost:8000/health`
2. Проверьте логи API Gateway: `docker-compose logs api-gateway`
3. Убедитесь, что Kafka доступна: `docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092`
4. Проверьте API‑ключ в заголовке запроса.

### Salience score всегда 0 или 1

1. Проверьте конфигурацию scoring в `salience_engine/scoring.py`.
2. Убедитесь, что поля `severity`, `urgency`, `impact` находятся в диапазоне [0, 1].
3. Посмотрите логи Salience Engine на наличие ошибок.

### Политики не срабатывают

1. Проверьте, что политика активна (поле `enabled: true`).
2. Протестируйте условие через `/api/v1/policies/test`.
3. Убедитесь, что событие удовлетворяет условию (проверьте значения полей).
4. Проверьте логи Policy Engine.

### Высокий Kafka lag

1. Увеличьте количество реплик consumer (например, Salience Engine).
2. Проверьте, не завис ли consumer (логи, метрики CPU).
3. Увеличьте ресурсы Kafka (память, CPU) или добавьте больше брокеров.

### Redis ошибки соединения

1. Проверьте, что Redis запущен: `docker-compose logs redis`
2. Убедитесь, что в `.env` указаны правильные `REDIS_HOST` и `REDIS_PORT`.
3. Проверьте лимиты памяти Redis (возможно, нужно увеличить `maxmemory`).

### Grafana не показывает данные

1. Убедитесь, что Prometheus собирает метрики: `curl http://localhost:9090/metrics`
2. Проверьте, что datasource Prometheus настроен в Grafana.
3. Убедитесь, что метрики экспортируются компонентами (проверьте логи компонентов).

## Безопасность

### Как защитить API?

- Используйте API‑ключи (заголовок `X-API-Key`).
- Настройте TLS (HTTPS) для API Gateway.
- Ограничьте доступ по IP с помощью firewall или Ingress rules.

### Где хранить секреты (API‑ключи, пароли)?

Используйте secrets manager (Hashicorp Vault, AWS Secrets Manager, Kubernetes Secrets) и передавайте их через переменные окружения.

### Как обеспечить безопасность коммуникации между компонентами?

- Включите TLS для Kafka, Redis, PostgreSQL.
- Используйте mTLS для внутренних gRPC коммуникаций (если используется).
- Разместите компоненты в private network.

### Как аудировать доступ к системе?

Логируйте все запросы к API Gateway и изменения политик. Логи можно отправлять в SIEM систему.

## Производительность

### Сколько событий в секунду может обработать система?

На стандартном оборудовании (4 CPU, 8 GB RAM) система обрабатывает ~1000 событий в секунду. Пропускная способность зависит от сложности scoring и количества политик.

### Как измерить производительность?

Используйте дашборд **Task Performance** в Grafana. Ключевые метрики: `ras_events_total`, `http_request_duration_seconds`, `kafka_consumer_lag`.

### Как уменьшить задержку обработки?

- Увеличьте количество partitions Kafka.
- Используйте асинхронную обработку в компонентах.
- Оптимизируйте запросы к Redis и PostgreSQL (кеширование, индексы).

## Развёртывание

### Как развернуть в Kubernetes?

Используйте манифесты из `k8s/` или Helm chart (если есть). См. [Kubernetes deployment guide](../deployment/kubernetes.md).

### Как настроить high availability?

- Запустите несколько реплик каждого компонента.
- Используйте managed Kafka и Redis с репликацией.
- Разместите поды в разных availability zones.

### Как обновить систему без простоя?

Используйте стратегию rolling update в Kubernetes или blue‑green deployment. См. [Production deployment guide](../deployment/production.md).

### Как сделать backup?

- PostgreSQL: `pg_dump` + WAL‑архивирование.
- Redis: RDB snapshot.
- Kafka: mirror maker в другой кластер.
- Конфигурации: Git.

Подробнее в [Maintenance procedures](../operations/maintenance.md).

## Поддержка

### Где получить помощь?

- **Документация**: Изучите разделы в `docs/`.
- **GitHub Issues**: Сообщайте о багах и запросах функций.
- **Slack**: Присоединяйтесь к каналу `#ras-support`.

### Как сообщить об ошибке?

Создайте issue на GitHub с подробным описанием:
1. Шаги для воспроизведения.
2. Ожидаемое поведение.
3. Фактическое поведение.
4. Логи и метрики (если возможно).

### Как предложить улучшение?

Откройте issue с меткой `enhancement` или создайте pull request.

### Есть ли коммерческая поддержка?

Да, доступны коммерческие планы поддержки и консалтинг. Свяжитесь с нами через email: support@example.com.