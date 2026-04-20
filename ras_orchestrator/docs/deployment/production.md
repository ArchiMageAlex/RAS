# Production Deployment Guide

Развёртывание RAS-like оркестратора в production требует внимания к безопасности, надёжности, производительности и мониторингу. В этом руководстве описаны best practices и шаги для подготовки production-окружения.

## Архитектура production

Рекомендуемая архитектура для production:

- **Кластер Kubernetes** (минимум 3 ноды) в нескольких availability zones.
- **Управляемые сервисы** для инфраструктуры:
  - Kafka: Confluent Cloud или Amazon MSK
  - Redis: Elasticache или Redis Enterprise
  - PostgreSQL: RDS, Cloud SQL или Azure Database for PostgreSQL
- **Service mesh** (опционально): Istio или Linkerd для улучшенной безопасности и observability.
- **CDN / WAF** для защиты внешнего API (например, Cloudflare, AWS WAF).

## Подготовка

### 1. Окружение

Создайте отдельные Kubernetes namespace для production:

```bash
kubectl create namespace ras-production
```

Установите необходимые операторы и зависимости (см. [Kubernetes развёртывание](./kubernetes.md)).

### 2. Конфигурация

Все конфигурационные параметры должны храниться вне кода. Используйте:

- **ConfigMaps** для несекретных данных.
- **Secrets** для паролей, токенов, приватных ключей (шифруйте с помощью Sealed Secrets или внешнего Vault).
- **External configuration services**: HashiCorp Consul, etcd, или cloud-specific (AWS Parameter Store, Azure App Configuration).

### 3. Образы контейнеров

- Используйте конкретные теги версий (не `latest`).
- Сканируйте образы на уязвимости (Trivy, Clair).
- Храните образы в private registry (ECR, GCR, Harbor) с ограниченным доступом.
- Настройте image pull secrets в Kubernetes.

## Безопасность

### Аутентификация и авторизация

- **API Gateway**: Включите аутентификацию через JWT или OAuth2. Используйте sidecar (например, OAuth2 Proxy) или встроенную поддержку в Ingress (например, nginx-ingress с auth-url).
- **Внутренние коммуникации**: Используйте mutual TLS (mTLS) между компонентами. Service mesh упрощает настройку.
- **Доступ к базам данных**: Ограничьте доступ только с IP компонентов RAS (security groups, network policies). Используйте IAM roles для managed сервисов.

### Сетевые политики

Определите NetworkPolicy для каждого компонента, разрешая только необходимый трафик.

Пример политики для API Gateway:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-gateway-ingress
  namespace: ras-production
spec:
  podSelector:
    matchLabels:
      app: api-gateway
  policyTypes:
  - Ingress
  ingress:
  - from:
    - ipBlock:
        cidr: 0.0.0.0/0
    ports:
    - port: 80
      protocol: TCP
    - port: 443
      protocol: TCP
  - from:
    - podSelector:
        matchLabels:
          app: monitoring
    ports:
    - port: 8000
      protocol: TCP
```

### Управление секретами

Используйте HashiCorp Vault или Kubernetes External Secrets Operator для динамического управления секретами.

Пример ExternalSecret для API ключа:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: api-key
  namespace: ras-production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: api-key-secret
  data:
  - secretKey: api-key
    remoteRef:
      key: secrets/ras
      property: api-key
```

## Надёжность

### Репликация и availability

- **Компоненты RAS**: Запускайте минимум 2 реплики каждого Deployment с anti-affinity rules для распределения по разным нодам.
- **Базы данных**: Используйте multi-AZ deployment с автоматическим failover.
- **Kafka**: Минимум 3 брокера с replication factor 3 для топиков.

### Health checks

Настройте liveness и readiness probes для каждого компонента:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Circuit breakers и retry

Используйте sidecar (например, Envoy) или библиотеки (resilience4j, Polly) для реализации circuit breakers, retry, timeout при вызовах между компонентами.

### Резервное копирование

- **PostgreSQL**: Ежедневные snapshot + continuous WAL archiving.
- **Redis**: RDB snapshot каждые 6 часов + AOF append.
- **Kafka**: Используйте MirrorMaker для репликации топиков в другой кластер.
- **Конфигурации**: Храните манифесты Kubernetes в Git (GitOps) и регулярно создавайте backup etcd.

План восстановления (Disaster Recovery) должен быть протестирован.

## Производительность

### Ресурсы

Установите requests и limits для каждого контейнера на основе нагрузочного тестирования.

Пример:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1"
```

### Автомасштабирование

Настройте Horizontal Pod Autoscaler (HPA) на основе CPU, памяти или custom метрик (например, количество событий в секунду).

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: salience-engine-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: salience-engine
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: events_per_second
      target:
        type: AverageValue
        averageValue: 1000
```

### Кэширование

- Используйте Redis не только как workspace, но и как кэш для salience scores, политик.
- Настройте TTL и eviction policies.

### Оптимизация Kafka

- Настройте количество partitions в соответствии с количеством потребителей.
- Используйте compression (snappy, lz4) для уменьшения трафика.
- Мониторьте lag потребителей.

## Мониторинг и алертинг

### Метрики

- Prometheus собирает метрики со всех компонентов.
- Настройте remote write в долгосрочное хранилище (Thanos, Cortex, VictoriaMetrics).
- Создайте дашборды Grafana для ключевых метрик:
  - Latency перцентили
  - Error rates
  - Kafka lag
  - Режим системы
  - Количество прерываний

### Логи

- Centralized logging через Loki + Promtail.
- Настройте retention policy (например, 30 дней).
- Интегрируйте с SIEM (Splunk, Elasticsearch) для security auditing.

### Трассировка

- Jaeger для распределённой трассировки.
- Настройте sampling rate (например, 10% для production).
- Интегрируйте трассировки с метриками и логами (через trace_id).

### Алерты

Определите критические алерты:

1. **Высокий уровень ошибок** (>5% в течение 5 минут)
2. **Высокая задержка** (p95 > 1s)
3. **Kafka consumer lag** (>1000 сообщений)
4. **Режим critical дольше 10 минут**
5. **Недоступность компонентов** (продолжительность > 2 минут)

Настройте уведомления через Slack, Email, PagerDuty.

## Обновления

### Стратегия развёртывания

Используйте blue-green или canary deployments для минимизации риска.

Пример canary с Flagger:

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: api-gateway
  namespace: ras-production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  progressDeadlineSeconds: 60
  service:
    port: 80
  analysis:
    interval: 30s
    threshold: 5
    maxWeight: 50
    stepWeight: 10
    metrics:
    - name: request-success-rate
      threshold: 99
      interval: 1m
    - name: request-duration
      threshold: 500
      interval: 1m
```

### Откат

Подготовьте rollback plan. Храните предыдущие версии образов и манифестов.

## Тестирование production

Перед полным запуском проведите:

- **Load testing**: Смоделируйте пиковую нагрузку (например, 1000 событий/сек) и убедитесь, что система стабильна.
- **Chaos engineering**: Инжектируйте сбои (отказ ноды, сетевые задержки, недоступность Kafka) с помощью Chaos Mesh или Gremlin.
- **Failover testing**: Имитируйте отказ availability zone и проверьте восстановление.

## Документация и runbooks

Создайте runbooks для операторов на случай инцидентов:

- Как диагностировать проблему с помощью метрик, логов, трассировок.
- Как выполнить rollback.
- Как масштабировать компоненты вручную.
- Как проверить целостность данных.

## Compliance и аудит

- Включите аудит-логи Kubernetes.
- Регулярно проверяйте security policies (например, с помощью kube-bench).
- Обеспечьте соответствие стандартам (GDPR, HIPAA, SOC2) в зависимости от требований.

## Поддержка

Назначьте on-call инженеров, настройте эскалацию алертов. Используйте инструменты типа PagerDuty для управления инцидентами.

## Заключение

Production-развёртывание RAS-like оркестратора — это непрерывный процесс улучшения. Начните с минимальной конфигурации, постепенно добавляя функции безопасности, мониторинга и автоматизации. Регулярно пересматривайте архитектуру и обновляйте компоненты.