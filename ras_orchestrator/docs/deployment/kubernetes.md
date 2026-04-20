# Kubernetes развёртывание

Для production-развёртывания RAS-like оркестратора рекомендуется использовать Kubernetes. Это обеспечивает высокую доступность, автоматическое масштабирование, самовосстановление и удобное управление конфигурацией.

## Архитектура развёртывания

В Kubernetes каждый компонент RAS разворачивается как отдельный Deployment (или StatefulSet для stateful сервисов). Взаимодействие между компонентами осуществляется через Service и Kafka (также развёрнутый в кластере или внешний).

### Компоненты

1. **Stateless компоненты** (Deployment):
   - `api-gateway`
   - `salience-engine`
   - `mode-manager`
   - `interrupt-manager`
   - `task-orchestrator`
   - `retriever-agent`

2. **Stateful компоненты** (StatefulSet или внешние managed сервисы):
   - `kafka` (можно использовать Strimzi Operator)
   - `redis` (можно использовать Redis Helm chart)
   - `postgresql` (можно использовать внешнюю базу данных)

3. **Observability stack** (отдельные Deployments):
   - `prometheus` (через Prometheus Operator)
   - `grafana`
   - `jaeger` (через Jaeger Operator)
   - `loki` (через Loki Stack)

4. **Вспомогательные ресурсы**:
   - ConfigMaps для конфигурации
   - Secrets для паролей и ключей
   - ServiceAccounts, Roles, RoleBindings для безопасности
   - Ingress для внешнего доступа к API Gateway и Grafana

## Требования

- Kubernetes кластер версии 1.24+
- Helm 3.8+ (для установки зависимостей)
- Доступ к container registry (Docker Hub, GitLab Registry, etc.)
- Минимум 8 ГБ оперативной памяти и 4 CPU на узле (рекомендуется)

## Установка с помощью Helm

Мы предоставляем Helm chart для развёртывания всей системы. Chart находится в директории `charts/ras-orchestrator/` (будет создан). Если chart отсутствует, можно использовать отдельные charts для каждого компонента.

### 1. Установка зависимостей

Сначала установите необходимые инфраструктурные компоненты:

**Strimzi (Kafka Operator):**
```bash
helm repo add strimzi https://strimzi.io/charts/
helm install kafka-operator strimzi/strimzi-kafka-operator
```

**Redis:**
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install redis bitnami/redis --set auth.enabled=false
```

**PostgreSQL:**
```bash
helm install postgresql bitnami/postgresql --set auth.postgresPassword=ras_password
```

**Observability stack (Prometheus, Grafana, Loki, Jaeger):**
```bash
# Prometheus Stack (включает Grafana)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack

# Loki Stack
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack --set promtail.enabled=true

# Jaeger Operator
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm install jaeger jaegertracing/jaeger-operator
```

### 2. Установка RAS Orchestrator

Если есть Helm chart:

```bash
helm install ras-orchestrator ./charts/ras-orchestrator
```

Или можно развернуть компоненты по отдельности с помощью манифестов из `k8s/` директории.

## Манифесты Kubernetes

Пример манифеста для API Gateway (Deployment + Service):

```yaml
# api-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: ras
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: api-gateway
        image: ras-orchestrator/api-gateway:latest
        ports:
        - containerPort: 8000
        env:
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: "kafka-brokers.kafka.svc.cluster.local:9092"
        - name: REDIS_HOST
          value: "redis-master.redis.svc.cluster.local"
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://jaeger-collector.jaeger.svc.cluster.local:4317"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: ras
spec:
  selector:
    app: api-gateway
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

Аналогичные манифесты создаются для других компонентов.

## Конфигурация

### ConfigMaps

Конфигурационные параметры, которые могут меняться в зависимости от окружения, выносятся в ConfigMaps.

Пример ConfigMap для Salience Engine:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: salience-engine-config
  namespace: ras
data:
  salience_weights.json: |
    {
      "relevance": 0.3,
      "novelty": 0.2,
      "risk": 0.25,
      "urgency": 0.15,
      "uncertainty": 0.1
    }
```

И затем монтируется в Pod как volume.

### Secrets

Чувствительные данные (пароли, API ключи) хранятся в Secrets.

```bash
kubectl create secret generic api-keys \
  --namespace ras \
  --from-literal=api-key=supersecret
```

Использование в Pod:

```yaml
env:
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: api-keys
      key: api-key
```

## Сетевые политики

Для ограничения трафика между компонентами используйте NetworkPolicy.

Пример политики, разрешающей только API Gateway общаться с Kafka:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-gateway-to-kafka
  namespace: ras
spec:
  podSelector:
    matchLabels:
      app: kafka-broker
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
    ports:
    - port: 9092
```

## Автомасштабирование

Настройте Horizontal Pod Autoscaler (HPA) для компонентов, испытывающих переменную нагрузку (например, API Gateway, Salience Engine).

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: ras
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Ingress

Для внешнего доступа к API Gateway и Grafana настройте Ingress.

Пример с Nginx Ingress Controller:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ras-ingress
  namespace: ras
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: api.ras.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-gateway
            port:
              number: 80
  - host: grafana.ras.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: monitoring-grafana
            port:
              number: 80
```

## Мониторинг и логирование

- **Метрики**: Prometheus автоматически собирает метрики с каждого Pod (через аннотации `prometheus.io/scrape: "true"`).
- **Логи**: Loki собирает логи через Promtail, который работает как DaemonSet.
- **Трассировка**: Jaeger собирает трассировки через sidecar или прямой OTLP экспорт.

## Резервное копирование и восстановление

- **PostgreSQL**: Используйте периодические snapshot (например, через Velero) или встроенные backup инструменты базы данных.
- **Redis**: Настройте RDB или AOF persistence, регулярно создавайте backup.
- **Kafka**: Используйте MirrorMaker 2 для репликации топиков в другой кластер.

## Обновление версий

Рекомендуется использовать стратегию rolling update с readiness probes.

```bash
kubectl set image deployment/api-gateway api-gateway=ras-orchestrator/api-gateway:v1.1.0
```

Для критических обновлений можно использовать blue-green или canary deployment (с помощью инструментов типа Flagger).

## Troubleshooting

### Проверка состояния

```bash
kubectl get pods -n ras
kubectl logs deployment/api-gateway -n ras
kubectl describe pod <pod-name> -n ras
```

### Проверка соединений

```bash
# Проверить, доступен ли Kafka из Pod
kubectl exec -it deployment/api-gateway -n ras -- curl -v kafka-brokers.kafka.svc.cluster.local:9092
```

### Просмотр метрик

```bash
# Порт-форвард Prometheus
kubectl port-forward svc/monitoring-prometheus 9090:9090 -n monitoring
```

Затем откройте http://localhost:9090.

## Production рекомендации

- Используйте отдельные namespace для каждого окружения (dev, staging, production).
- Настройте Resource Quotas и Limit Ranges для контроля ресурсов.
- Включите Pod Disruption Budget для обеспечения доступности во время обновлений узлов.
- Используйте service mesh (например, Istio) для улучшенного observability и безопасности.
- Регулярно обновляйте образы контейнеров для исправления уязвимостей.

## Дальнейшие шаги

- Настройте CI/CD pipeline для автоматического развёртывания при изменениях кода.
- Интегрируйте с внешними системами мониторинга (Datadog, New Relic).
- Реализуйте multi-region развёртывание для географической отказоустойчивости.