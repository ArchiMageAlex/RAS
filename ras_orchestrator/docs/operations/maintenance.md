# Процедуры обслуживания

В этом документе описаны регулярные и плановые процедуры обслуживания RAS-like оркестратора.

## Регулярные задачи

### Ежедневные

1. **Проверка состояния системы**:
   - Просмотр дашбордов Grafana (System Health, Event Flow).
   - Проверка алертов в Alertmanager.
   - Убедиться, что нет critical алертов.

2. **Проверка ресурсов**:
   - CPU и память по компонентам.
   - Использование диска (особенно для Kafka, PostgreSQL, Loki).
   - Количество подов в каждом deployment.

3. **Проверка логов**:
   - Поиск ошибок в логах ключевых компонентов (API Gateway, Salience Engine, Mode Manager).
   - Проверка логов инфраструктуры (Kafka, Redis, PostgreSQL).

4. **Резервное копирование**:
   - Убедиться, что ночной backup PostgreSQL и Redis выполнен успешно.
   - Проверить целостность backup (например, пробное восстановление в тестовой среде).

### Еженедельные

1. **Анализ метрик**:
   - Тренды за неделю: рост событий, изменение latency, использование ресурсов.
   - Выявление аномалий.

2. **Очистка старых данных**:
   - Удаление старых трассировок Jaeger (если retention настроен).
   - Очистка логов Loki старше 30 дней.
   - Архивация старых событий из PostgreSQL в cold storage.

3. **Обновление политик**:
   - Просмотр и обновление политик через веб‑интерфейс.
   - Тестирование новых политик в staging.

4. **Проверка безопасности**:
   - Аудит логов доступа.
   - Проверка актуальности SSL‑сертификатов.
   - Обновление секретов (API keys, пароли).

### Ежемесячные

1. **Обзор производительности**:
   - Анализ SLA/SLO за месяц.
   - Выявление узких мест.
   - Планирование оптимизаций.

2. **Обновление зависимостей**:
   - Проверка обновлений для Python‑пакетов, Docker‑образов, системных пакетов.
   - Планирование обновлений в staging, затем в production.

3. **Тестирование отказоустойчивости**:
   - Симуляция сбоев (chaos engineering) в staging.
   - Проверка процедур восстановления.

4. **Документация**:
   - Обновление runbooks и troubleshooting guide на основе инцидентов.
   - Ревизия архитектурной документации.

## Резервное копирование и восстановление

### PostgreSQL

**Автоматическое backup**:
- Используется `pg_dump` или WAL‑архивирование.
- Backup выполняется ежедневно в 02:00 UTC.
- Хранится 7 дней в S3‑совместимом хранилище.

**Ручной backup**:
```bash
kubectl exec -it deployment/postgres -n ras -- pg_dump -U ras -d ras -Fc > backup_$(date +%Y%m%d).dump
```

**Восстановление**:
1. Остановить приложение, чтобы избежать конфликтов.
2. Восстановить dump:
   ```bash
   kubectl exec -i deployment/postgres -n ras -- pg_restore -U ras -d ras -c < backup.dump
   ```
3. Перезапустить приложение.

### Redis

**Snapshot (RDB)**:
- Redis настроен на создание snapshot каждые 5 минут при изменении хотя бы 100 ключей.
- Snapshot сохраняется на persistent volume.

**Копирование snapshot**:
```bash
kubectl cp ras/postgres-0:/data/dump.rdb ./dump_$(date +%Y%m%d).rdb
```

**Восстановление**:
1. Остановить Redis.
2. Заменить файл dump.rdb.
3. Запустить Redis.

### Kafka

**Резервное копирование топиков**:
- Используется инструмент `kafka-mirror-maker` или `kafka-replicator`.
- Критичные топики реплицируются в другой кластер.

**Восстановление топика**:
```bash
kubectl exec -it deployment/kafka -n ras -- kafka-topics --create --topic ras.events.restored --partitions 3 --replication-factor 2 --bootstrap-server localhost:9092
kubectl exec -it deployment/kafka -n ras -- kafka-console-producer --topic ras.events.restored --bootstrap-server localhost:9092 < backup.json
```

### Файлы конфигурации и политик

- Все конфигурации хранятся в Git.
- Политики хранятся в Git и в PostgreSQL.
- Регулярно выполняется `git pull` для актуализации.

## Обновление компонентов

### Стратегия обновления

Используется rolling update с readiness/liveness пробами. Для критичных компонентов применяется canary deployment.

### Порядок обновления

1. **Обновление инфраструктурных компонентов**:
   - Kafka, Redis, PostgreSQL – обновлять по одному узлу, с проверкой стабильности.
   - Observability стек (Prometheus, Grafana, Loki, Jaeger) – обновлять в порядке зависимости.

2. **Обновление RAS‑компонентов**:
   - Порядок: API Gateway → Salience Engine → Mode Manager → Interrupt Manager → Workspace Service → Policy Engine → Task Orchestrator → Retriever Agent.
   - Между обновлениями делать паузу 5–10 минут для наблюдения за метриками.

3. **Проверка**:
   - После каждого обновления проверить health endpoints.
   - Убедиться, что метрики в норме.
   - Провести smoke‑тест (отправить тестовое событие).

### Откат

Если обновление вызывает проблемы, выполнить откат:

```bash
kubectl rollout undo deployment/api-gateway -n ras
```

## Масштабирование

### Горизонтальное масштабирование (Kubernetes)

Увеличить количество реплик для компонента:

```bash
kubectl scale deployment api-gateway --replicas=3 -n ras
```

### Вертикальное масштабирование

Изменить ресурсы (CPU, память) в манифестах deployment и применить:

```bash
kubectl apply -f deployment.yaml
```

### Автоматическое масштабирование

Настроено Horizontal Pod Autoscaler (HPA) для компонентов:

- API Gateway: масштабируется по CPU (>70%) и RPS.
- Salience Engine: масштабируется по Kafka consumer lag.
- Task Orchestrator: масштабируется по длине очереди задач.

## Очистка данных

### Kafka

Настройте retention policy в конфигурации топиков:

```yaml
# в конфигурации Kafka
log.retention.hours=168  # 7 дней
```

Ручная очистка топика:

```bash
kubectl exec -it deployment/kafka -n ras -- kafka-configs --alter --topic ras.events --add-config retention.ms=86400000 --bootstrap-server localhost:9092
```

### Redis

Установите TTL для ключей, чтобы автоматически очищать старые данные:

```python
# в коде WorkspaceService
redis_client.setex(key, ttl_seconds, value)
```

Ручная очистка:

```bash
kubectl exec -it deployment/redis -n ras -- redis-cli FLUSHDB
```

### PostgreSQL

Архивация старых событий:

```sql
-- Перенос событий старше 30 дней в архивную таблицу
INSERT INTO events_archive SELECT * FROM events WHERE created_at < NOW() - INTERVAL '30 days';
DELETE FROM events WHERE created_at < NOW() - INTERVAL '30 days';
```

### Loki

Настройте retention в конфигурации Loki:

```yaml
table_manager:
  retention_deletes_enabled: true
  retention_period: 720h  # 30 дней
```

## Обновление политик

### Через веб‑интерфейс

1. Откройте Policy Engine UI (http://policy-engine:8001).
2. Перейдите в раздел Policies.
3. Отредактируйте или добавьте новую политику.
4. Нажмите "Save & Apply".

### Через API

```bash
curl -X POST http://policy-engine:8000/api/v1/policies \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "new-policy", "content": "..."}'
```

### Через Git (Infrastructure as Code)

1. Отредактируйте YAML‑файлы в `policy_engine/policies/`.
2. Создайте pull request.
3. После мержа CI/CD автоматически применит политики.

## Обновление ML‑моделей

Salience Engine может использовать ML‑модели для scoring. Процедура обновления:

1. **Подготовка новой модели**:
   - Обучите модель на актуальных данных.
   - Сохраните в формате, поддерживаемом движком (например, ONNX, pickle).

2. **Загрузка модели**:
   - Поместите файл модели в S3 или в volume.
   - Обновите конфигурацию Salience Engine, указав путь к новой модели.

3. **Canary развёртывание**:
   - Направить часть трафика на экземпляры с новой моделью.
   - Сравнить метрики (salience score distribution, interrupt rate).

4. **Полный переход**:
   - Если метрики удовлетворительны, обновить все экземпляры.

## Мониторинг во время обслуживания

Во время процедур обслуживания необходимо усилить мониторинг:

1. **Дополнительные дашборды**:
   - Создать временный дашборд с ключевыми метриками обновляемого компонента.
2. **Алерты**:
   - Временно снизить пороги алертов для быстрого обнаружения проблем.
3. **Логи**:
   - Включить debug‑логирование для обновляемого компонента.

## Отключение системы для обслуживания

Если требуется полное отключение (например, для миграции БД), выполните:

1. **Уведомление**:
   - Уведомить пользователей о плановом простое.
   - Установить maintenance window.

2. **Остановка трафика**:
   - В Ingress установить аннотацию `nginx.ingress.kubernetes.io/maintenance: "true"`.
   - Или масштабировать API Gateway до 0 реплик.

3. **Остановка компонентов**:
   - Остановить компоненты в порядке, обратном зависимостям.
   - Дождаться graceful shutdown.

4. **Выполнение работ**:
   - Провести необходимые операции.

5. **Запуск**:
   - Запустить компоненты в правильном порядке.
   - Проверить health.
   - Возобновить трафик.

## Документирование изменений

После каждого обслуживания обновите:

1. **Changelog** в `CHANGELOG.md`.
2. **Конфигурации** в Git.
3. **Runbooks** с новыми шагами.
4. **Инвентарь** версий компонентов.

## Контакты при чрезвычайных ситуациях

- **Главный инженер**: +7‑XXX‑XXX‑XX‑XX
- **Резервный инженер**: +7‑YYY‑YYY‑YY‑YY
- **Slack канал**: #ras-maintenance