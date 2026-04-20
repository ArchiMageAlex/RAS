# Документация RAS-like оркестратора

Добро пожаловать в документацию RAS-like оркестратора — системы для обработки событий в реальном времени с механизмами selective attention, прерываний и автоматического реагирования.

## Структура документации

### 1. Архитектура
- [Обзор архитектуры](architecture/overview.md) — высокоуровневая архитектура, диаграммы, принципы работы.
- [Компоненты](architecture/components/) — детальное описание каждого компонента:
  - [API Gateway](architecture/components/api_gateway.md)
  - [Salience Engine](architecture/components/salience_engine.md)
  - [Mode Manager](architecture/components/mode_manager.md)
  - [Interrupt Manager](architecture/components/interrupt_manager.md)
  - [Workspace Service](architecture/components/workspace_service.md)
  - [Policy Engine](architecture/components/policy_engine.md)
  - [Task Orchestrator](architecture/components/task_orchestrator.md)
  - [Retriever Agent](architecture/components/retriever_agent.md)
  - [Observability Stack](architecture/components/observability.md)
- [Data Model](architecture/data_model.md) — схемы событий, задач, политик, структуры БД.

### 2. API
- [OpenAPI спецификация](api/openapi.yaml) — полная спецификация REST API в формате OpenAPI 3.0.
- [API руководство](api/README.md) — примеры запросов, аутентификация, коды ответов.
- [gRPC и Kafka](api/streaming.md) — документация по streaming API и message schemas.

### 3. Развёртывание
- [Docker Compose](deployment/docker-compose.md) — запуск всей системы локально с помощью Docker Compose.
- [Kubernetes](deployment/kubernetes.md) — развёртывание в Kubernetes (манифесты, Helm, сетевые политики).
- [Production руководство](deployment/production.md) — best practices для production: high availability, безопасность, мониторинг.

### 4. Операции
- [Мониторинг и алертинг](operations/monitoring.md) — ключевые метрики, дашборды Grafana, правила алертинга.
- [Troubleshooting](operations/troubleshooting.md) — диагностика распространённых проблем и их решения.
- [Процедуры обслуживания](operations/maintenance.md) — резервное копирование, обновления, масштабирование.

### 5. Разработка
- [Настройка окружения](development/setup.md) — руководство по настройке локальной среды для разработки.
- [Структура кода и соглашения](development/code_structure.md) — стандарты кодирования, архитектурные паттерны.
- [CI/CD Pipeline](development/cicd.md) — конфигурация GitHub Actions, автоматическое тестирование и развёртывание.

### 6. Руководство пользователя
- [Начало работы](user_guide/getting_started.md) — быстрый старт, отправка первого события, проверка состояния.
- [Примеры использования](user_guide/use_cases.md) — сценарии из реальной жизни: IT‑мониторинг, поддержка, безопасность, IoT.
- [Лучшие практики](user_guide/best_practices.md) — рекомендации по проектированию событий, политик, производительности и безопасности.

### 7. Справочные материалы
- [Глоссарий](reference/glossary.md) — определения терминов, используемых в системе.
- [Часто задаваемые вопросы (FAQ)](reference/faq.md) — ответы на общие вопросы.
- [Чеклисты](reference/checklists.md) — проверочные списки для развёртывания, мониторинга, troubleshooting.

## Быстрый старт

Если вы хотите быстро запустить систему, выполните:

```bash
git clone https://github.com/your-org/ras-orchestrator.git
cd ras-orchestrator
docker-compose up -d
```

Через несколько минут система будет доступна:
- API Gateway: http://localhost:8000
- Policy Engine UI: http://localhost:8001
- Grafana: http://localhost:3000 (логин: admin, пароль: admin)
- Jaeger: http://localhost:16686

Отправьте тестовое событие:

```bash
curl -X POST http://localhost:8000/events \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "test", "source": "test", "severity": 0.8, "urgency": 0.7, "impact": 0.9}'
```

## Целевая аудитория

- **Разработчики** — начните с [разработческой документации](development/setup.md) и [API](api/README.md).
- **Операторы (SRE/DevOps)** — изучите [развёртывание](deployment/production.md) и [операции](operations/monitoring.md).
- **Пользователи/аналитики** — ознакомьтесь с [руководством пользователя](user_guide/getting_started.md) и [примерами использования](user_guide/use_cases.md).

## Обновление документации

Документация хранится в Git и обновляется вместе с кодом. Если вы обнаружили ошибку или хотите предложить улучшение, создайте issue или pull request в репозитории.

## Лицензия

Документация распространяется под лицензией [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

## Контакты

- **GitHub Issues**: [https://github.com/your-org/ras-orchestrator/issues](https://github.com/your-org/ras-orchestrator/issues)
- **Slack**: канал `#ras-documentation`
- **Email**: docs@example.com