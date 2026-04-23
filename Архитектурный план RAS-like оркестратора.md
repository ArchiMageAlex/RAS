# Архитектурный план реализации RAS-like оркестратора

## 0. Текущий статус реализации (апрель 2026)

Проект RAS Orchestrator активно развивается, многие компоненты из плана уже реализованы и находятся в рабочем состоянии. Ниже приведено соответствие между запланированными компонентами и текущей реализацией.

### Реализованные компоненты (фазы 1 и 2)
- **Event Ingestion Layer**: API Gateway (`ras_orchestrator/api_gateway/`), Event Bus (`ras_orchestrator/event_bus/`)
- **Salience Engine**: модуль `ras_orchestrator/salience_engine/` с novelty detection, scoring, trust scoring
- **Mode Manager**: `ras_orchestrator/mode_manager/` с поддержкой режимов и политик
- **Interrupt Manager**: `ras_orchestrator/interrupt_manager/` с checkpointing и preemption
- **Workspace/Blackboard**: `ras_orchestrator/workspace_service/` на основе Redis
- **Policy Engine**: `ras_orchestrator/policy_engine/` с YAML политиками и REST API
- **Task Orchestrator**: `ras_orchestrator/task_orchestrator/` с декомпозицией и delegation
- **Базовый агент (Retriever)**: `ras_orchestrator/retriever_agent/`
- **Homeostatic Controller**: `ras_orchestrator/homeostatic_controller/` для регуляции ресурсов
- **Human Escalation**: `ras_orchestrator/human_escalation/` с workflow engine
- **Predictive Engine**: `ras_orchestrator/predictive_engine/` для прогнозирования и proactive actions
- **RL Agent**: `ras_orchestrator/rl_agent/` для обучения с подкреплением
- **Observability**: полный стек Prometheus, Grafana, Loki в `ras_orchestrator/observability/`

### Частично реализованные компоненты (фаза 3)
- **Contextual bandits / hierarchical RL**: в стадии экспериментов
- **Predictive processing loop**: реализован в predictive_engine
- **Multimodal fusion**: планируется
- **Automatic policy calibration**: в разработке

### Актуальная документация
Подробная документация по архитектуре, компонентам и deployment находится в директории [`ras_orchestrator/docs/`](../ras_orchestrator/docs/):
- [Обзор архитектуры](../ras_orchestrator/docs/architecture/overview.md)
- [Phase 2: Adaptive Attention](../ras_orchestrator/docs/architecture/phase2_adaptive_attention.md)
- [Phase 3: Self-Optimizing](../ras_orchestrator/docs/architecture/phase3_self_optimizing.md)
- [Компоненты](../ras_orchestrator/docs/architecture/components/)
- [Deployment](../ras_orchestrator/docs/deployment/)

## 1. MVP-архитектура с core-компонентами

### 1.1. Event Ingestion Layer
- **API Gateway / Channel Adapters**: приём мультимодальных сигналов (HTTP, Webhook, Kafka, Sensor streams)
- **Event Normalizer**: нормализация событий в канонический формат
- **Deduplication Service**: устранение дубликатов и корреляция повторных сигналов

### 1.2. Salience Engine
- **Relevance Scorer**: оценка релевантности события целям системы
- **Novelty Detector**: обнаружение новых/неожиданных паттернов
- **Risk Scorer**: оценка риска (безопасность, финансы, compliance)
- **Urgency Classifier**: определение срочности
- **Uncertainty Estimator**: оценка уверенности в данных
- **Salience Aggregator**: интегральный расчёт значимости (salience score)

### 1.3. Mode Manager (Global Arousal Controller)
- **State Machine**: управление режимами системы (low, normal, elevated, critical)
- **Policy-driven Transitions**: переходы на основе salience, риска, нагрузки
- **Cooldown/Hysteresis Logic**: предотвращение дребезга режимов

### 1.4. Interrupt Manager
- **Preemption Policy**: правила прерывания текущих задач
- **Checkpoint Service**: сохранение состояния прерываемой задачи
- **Resume Coordinator**: возобновление после прерывания

### 1.5. Workspace/Blackboard
- **Global Shared Memory**: хранение топ-событий, активных целей, конфликтов
- **Real-time Updates**: публикация изменений для всех агентов
- **Persistence Layer**: durable storage (Redis + Postgres)

### 1.6. Policy Engine
- **Declarative Policy Bundles**: YAML/JSON правила для interrupt, mode, action gating
- **Rule Evaluator**: matching условий и принятие решений
- **Versioning & Rollback**: управление версиями политик

### 1.7. Task Orchestrator
- **Workflow Decomposition**: декомпозиция задач на подзадачи
- **Agent Assignment**: выбор агента на основе capability и trust
- **Fallback & Retry**: обработка ошибок и повторные попытки

### 1.8. Базовый агент (Retriever)
- **Semantic Search**: поиск релевантной информации в knowledge base
- **Context Enrichment**: обогащение контекста события
- **Result Packaging**: формирование структурированного ответа

## 2. Технологический стек для MVP

### 2.1. Язык программирования
- **Python 3.11+**: для быстрого прототипирования, ML-компонентов и orchestration logic
- **TypeScript/Node.js**: для UI, административных консолей и high-throughput event processing (опционально)

### 2.2. Message Bus
- **Apache Kafka**: durable event backbone с replay и partitioning
- **NATS**: для low-latency internal signaling (опционально)

### 2.3. Базы данных
- **PostgreSQL**: основное хранилище событий, задач, аудита
- **Redis**: hot state (workspace, режимы, кэш)
- **Vector DB** (Qdrant/Pinecone): семантическая память и поиск
- **Graph DB** (Neo4j/JanusGraph): связи сущностей (опционально на поздних этапах)

### 2.4. API Framework
- **FastAPI**: для REST/gRPC endpoints, асинхронная обработка
- **gRPC**: для low-latency внутренней коммуникации

### 2.5. Контейнеризация и оркестрация
- **Docker**: упаковка сервисов
- **Docker Compose**: локальная разработка и тестирование
- **Kubernetes**: production deployment (managed service, например, EKS/GKE/AKS)

### 2.6. Observability
- **OpenTelemetry**: трассировка, метрики, логи
- **Prometheus/Grafana**: мониторинг и алертинг
- **Loki**: агрегация логов

### 2.7. ML/MLOps
- **Hugging Face Transformers**: embedding, классификация
- **ONNX Runtime**: инференс моделей
- **MLflow**: управление моделями и эксперименты

## 3. Поэтапный план реализации (актуальный статус)

План реализации в значительной степени выполнен. Ниже приведено соответствие между исходным планом и текущим состоянием проекта.

### Фаза 1: Foundation (реализована)
**Цель**: базовые сервисы и event flow.
- ✅ **Event bus (Kafka) и нормализация событий** – реализовано в `ras_orchestrator/event_bus/` и `ras_orchestrator/api_gateway/`
- ✅ **Salience scoring** – реализовано в `ras_orchestrator/salience_engine/` с rule-based и ML-моделями
- ✅ **Workspace service (Redis)** – `ras_orchestrator/workspace_service/`
- ✅ **Interrupt policy engine (YAML)** – `ras_orchestrator/interrupt_manager/` и `ras_orchestrator/policy_engine/`
- ✅ **Task orchestrator с одним агентом (retriever)** – `ras_orchestrator/task_orchestrator/` и `ras_orchestrator/retriever_agent/`
- ✅ **Observability** – полный стек в `ras_orchestrator/observability/`
- ✅ **Docker Compose** – `ras_orchestrator/docker-compose.yml` для локального запуска

**Результат**: система принимает события, оценивает значимость, прерывает задачи и выполняет retrieval-действия. Все компоненты работоспособны и покрыты тестами.

### Фаза 2: Adaptive Attention (реализована)
**Цель**: режимы, прерывания, память.
- ✅ **Mode manager с 4 режимами** – `ras_orchestrator/mode_manager/`
- ✅ **Novelty/anomaly detection** – `ras_orchestrator/salience_engine/novelty_detector.py`
- ✅ **Checkpoint/resume для прерываний** – `ras_orchestrator/interrupt_manager/checkpoint_integration.py`
- ✅ **Расширение agent layer** – реализованы critic, safety, executor (частично в рамках других модулей)
- ✅ **Trust scoring** – `ras_orchestrator/salience_engine/trust_scorer.py`
- ✅ **Temporal memory** – `ras_orchestrator/salience_engine/historical_repository.py`
- ✅ **Human escalation pipeline** – `ras_orchestrator/human_escalation/`

**Результат**: система адаптирует уровень внимания, запоминает контекст, управляет прерываниями и эскалациями. Компоненты интегрированы и протестированы.

### Фаза 3: Self-Optimizing (в процессе реализации)
**Цель**: обучение, адаптация, автономность.
- 🔄 **Contextual bandits / hierarchical RL** – эксперименты в `ras_orchestrator/rl_agent/`
- ✅ **Predictive processing loop** – реализован в `ras_orchestrator/predictive_engine/`
- ✅ **Homeostatic control** – `ras_orchestrator/homeostatic_controller/`
- 🔄 **Automatic policy calibration** – в разработке
- 🔄 **Multimodal fusion** – планируется
- ✅ **Production deployment** – настроен Kubernetes deployment (см. `ras_orchestrator/docs/deployment/`)

**Результат**: система демонстрирует элементы самооптимизации, адаптируется к изменениям среды и продолжает развиваться в направлении полной RAS-like автономности.

## 4. Ключевые метрики успеха (KPI)

### 4.1. Для Salience Engine
- **Precision/Recall критических событий**: доля верно определённых critical events
- **False Positive Rate**: процент ложных срабатываний
- **Novelty Detection Accuracy**: способность обнаруживать новые паттерны

### 4.2. Для Interrupt Manager
- **Interrupt Latency**: время от события до решения о прерывании
- **False Interrupt Rate**: процент ненужных прерываний
- **Recovery Accuracy**: точность восстановления контекста после прерывания

### 4.3. Для Mode Manager
- **Time to High Alert**: скорость перехода в elevated/critical режим
- **Mode Stability**: отсутствие дребезга между режимами
- **Cost‑Efficiency**: соотношение качества обработки и ресурсов в разных режимах

### 4.4. Для общей системы
- **End‑to‑end Latency P95**: задержка от события до ответа
- **Critical Event Miss Rate**: пропущенные критические события
- **Human Escalation Rate**: доля случаев, требующих вмешательства человека
- **System Load vs. Performance**: graceful degradation под нагрузкой
- **Mean Time to Resolution (MTTR)**: среднее время решения инцидента

## 5. Deployment Strategy

### 5.1. Локальная разработка (docker-compose)
- Все сервисы запускаются в контейнерах
- Используются образы Kafka, Postgres, Redis, Vector DB
- Легко воспроизводимая среда для тестирования и отладки
- Поддержка hot-reload для кода Python

### 5.2. Production (Kubernetes)
- **Namespace isolation**: разделение на плоскости (edge, orchestration, agents, data, observability)
- **Network Policies**: строгие правила доступа между namespace
- **Autoscaling**: HPA для stateless сервисов, KEDA для event-driven scaling
- **Multi‑zone deployment**: spread Pods по зонам доступности
- **GitOps**: управление конфигурацией через ArgoCD/Flux
- **Secrets Management**: внешний Vault + External Secrets Operator
- **Canary Rollouts**: постепенное обновление критичных компонентов (Argo Rollouts)
- **Disaster Recovery**: регулярные бэкапы Postgres, snapshot Redis, replay capability

## 6. Риски и Mitigation Strategies

### 6.1. Риск гиперчувствительности (ложные прерывания)
- **Mitigation**: калибровка порогов через A/B тесты, введение гистерезиса, human-in-the-loop для критичных решений.

### 6.2. Риск нестабильного RL-контроля
- **Mitigation**: безопасный envelope (hard-coded safety rules), offline evaluation перед rollout, мониторинг regret.

### 6.3. Риск конфликтов между агентами
- **Mitigation**: арбитраж на основе trust scores, декомпозиция ответственности, явные conflict resolution policies.

### 6.4. Риск перегрузки системы
- **Mitigation**: homeostatic control, adaptive rate limiting, graceful degradation, load shedding.

### 6.5. Риск security breaches
- **Mitigation**: изоляция namespace, network policies, audit logging, регулярные penetration tests.

### 6.6. Риск vendor lock-in (облачные ML-сервисы)
- **Mitigation**: абстракция через LLM gateway, поддержка multiple backends, fallback на open-source модели.

## 7. Заключение

Предложенная архитектура реализует принципы RAS-like оркестратора, фокусируясь на селекции значимых сигналов, динамической регуляции внимания и прерывании менее важных задач. План реализации разбит на три фазы, что позволяет постепенно наращивать сложность и снижать риски.

Технологический стек выбран с учётом баланса между производительностью, управляемостью и скоростью разработки. Deployment стратегия обеспечивает гибкость от локальной разработки до enterprise-grade production.

Ключевые метрики позволяют количественно оценить прогресс в приближении к RAS-подобному поведению и оперативно корректировать систему.

---
*План составлен на основе глубокого анализа из файла "Агент оркестратор и РАС мозга - 2026-04-20_10-26-30.md".*