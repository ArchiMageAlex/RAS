# CI/CD Pipeline

В этом документе описаны процессы непрерывной интеграции и непрерывного развёртывания (CI/CD) для RAS-like оркестратора.

## Обзор

CI/CD pipeline реализован с использованием **GitHub Actions**. Он включает следующие этапы:

1. **Линтинг и форматирование** (lint)
2. **Тестирование** (test)
3. **Сборка Docker‑образов** (build)
4. **Развёртывание в staging** (deploy-staging)
5. **Развёртывание в production** (deploy-production)

Pipeline активируется при пуше в ветки `main`, `develop` и при создании pull request.

## Файлы конфигурации

Конфигурация CI/CD находится в `.github/workflows/`:

- `lint.yml` – проверка кода (black, isort, flake8, mypy)
- `test.yml` – запуск unit‑ и интеграционных тестов
- `build.yml` – сборка Docker‑образов и публикация в Container Registry
- `deploy-staging.yml` – развёртывание в staging среду
- `deploy-production.yml` – развёртывание в production среду

## Линтинг (lint)

### Триггер

Запускается при каждом пуше в любую ветку и при каждом pull request.

### Шаги

1. **Checkout** кода.
2. **Установка Python** и зависимостей.
3. **Запуск линтеров**:
   - `black --check .` – проверка форматирования.
   - `isort --check .` – проверка сортировки импортов.
   - `flake8` – статический анализ кода.
   - `mypy .` – проверка типов.

### Конфигурация

```yaml
name: Lint

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install black isort flake8 mypy
      - run: black --check .
      - run: isort --check .
      - run: flake8
      - run: mypy .
```

## Тестирование (test)

### Триггер

Запускается при пуше в ветки `main`, `develop` и при pull request.

### Шаги

1. **Checkout** кода.
2. **Запуск инфраструктуры** через Docker Compose (Kafka, Redis, PostgreSQL).
3. **Установка Python** и зависимостей.
4. **Запуск тестов** с помощью pytest.
5. **Генерация отчёта о покрытии** (coverage).

### Конфигурация

```yaml
name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      kafka:
        image: confluentinc/cp-kafka:latest
        ...
      redis:
        image: redis:alpine
        ...
      postgres:
        image: postgres:15
        ...

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest --cov=ras_orchestrator --cov-report=xml
      - uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Сборка Docker‑образов (build)

### Триггер

Запускается при пуше в ветки `main` и `develop`, а также при создании тега (например, `v1.0.0`).

### Шаги

1. **Checkout** кода.
2. **Логин в Container Registry** (например, GitHub Container Registry, Docker Hub).
3. **Сборка образов** для каждого компонента:
   - `api-gateway`
   - `salience-engine`
   - `mode-manager`
   - `interrupt-manager`
   - `workspace-service`
   - `policy-engine`
   - `task-orchestrator`
   - `retriever-agent`
4. **Публикация образов** с тегами:
   - `latest` – для ветки `develop`
   - `stable` – для ветки `main`
   - `vX.Y.Z` – для тегов

### Конфигурация

```yaml
name: Build

on:
  push:
    branches: [ main, develop ]
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push API Gateway
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.api-gateway
          push: true
          tags: |
            ghcr.io/your-org/ras-api-gateway:latest
            ghcr.io/your-org/ras-api-gateway:${{ github.sha }}
      # аналогично для других компонентов
```

## Развёртывание в staging (deploy-staging)

### Триггер

Запускается при пуше в ветку `develop` после успешного прохождения lint, test и build.

### Шаги

1. **Checkout** кода.
2. **Установка kubectl** и настройка доступа к Kubernetes кластеру staging.
3. **Применение манифестов** из `k8s/staging/`.
4. **Проверка развёртывания** (health checks, readiness probes).
5. **Smoke‑тест** – отправка тестового события и проверка обработки.

### Конфигурация

```yaml
name: Deploy to Staging

on:
  push:
    branches: [ develop ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - uses: azure/setup-kubectl@v3
      - run: |
          echo "${{ secrets.KUBECONFIG_STAGING }}" > kubeconfig.yaml
          export KUBECONFIG=kubeconfig.yaml
          kubectl apply -f k8s/staging/
          kubectl rollout status deployment/api-gateway -n ras-staging
      - name: Smoke test
        run: |
          curl -X POST http://staging.api.example.com/events \
            -H "X-API-Key: ${{ secrets.STAGING_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{"event_id": "smoke-test", "source": "ci", "severity": 0.5}'
```

## Развёртывание в production (deploy-production)

### Триггер

Запускается вручную (workflow_dispatch) или автоматически при пуше в ветку `main` (после успешного прохождения staging).

### Шаги

1. **Checkout** кода.
2. **Установка kubectl** и настройка доступа к Kubernetes кластеру production.
3. **Применение манифестов** из `k8s/production/`.
4. **Canary deployment** (опционально) – постепенное обновление трафика.
5. **Проверка развёртывания**.
6. **Уведомление** команды (Slack, email).

### Конфигурация

```yaml
name: Deploy to Production

on:
  workflow_dispatch:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: azure/setup-kubectl@v3
      - run: |
          echo "${{ secrets.KUBECONFIG_PRODUCTION }}" > kubeconfig.yaml
          export KUBECONFIG=kubeconfig.yaml
          kubectl apply -f k8s/production/
          kubectl rollout status deployment/api-gateway -n ras-production
      - name: Notify
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          channel: '#deployments'
```

## Environment variables и секреты

Секреты хранятся в GitHub Secrets и передаются в workflow через `${{ secrets.NAME }}`.

Необходимые секреты:

- `KUBECONFIG_STAGING` – kubeconfig для staging кластера.
- `KUBECONFIG_PRODUCTION` – kubeconfig для production кластера.
- `DOCKER_USERNAME`, `DOCKER_PASSWORD` – для доступа к Container Registry.
- `STAGING_API_KEY`, `PRODUCTION_API_KEY` – API ключи для smoke‑тестов.
- `SLACK_WEBHOOK_URL` – для уведомлений.

## Качество кода (Quality Gates)

Каждый этап pipeline служит quality gate:

1. **Линтинг** должен пройти без ошибок.
2. **Тесты** должны проходить с покрытием не менее 80% (порог настраивается).
3. **Сборка** должна успешно создавать образы.
4. **Smoke‑тест** в staging должен подтвердить работоспособность.

Если любой этап fails, pipeline останавливается и развёртывание не происходит.

## Откат (Rollback)

В случае проблем после развёртывания можно выполнить откат:

### Автоматический откат

Если health checks не проходят в течение заданного времени, Kubernetes автоматически откатывает deployment (благодаря readiness/liveness пробам).

### Ручной откат

Используйте kubectl для отката к предыдущей ревизии:

```bash
kubectl rollout undo deployment/api-gateway -n ras-production
```

Или запустите workflow отката (если настроен).

## Мониторинг pipeline

Статус pipeline можно отслеживать в GitHub Actions. Также настроены уведомления в Slack при успешном/неуспешном завершении.

## Кастомизация

### Добавление нового компонента

1. Создайте Dockerfile для компонента (например, `Dockerfile.new-component`).
2. Добавьте шаг сборки в `build.yml`.
3. Создайте Kubernetes манифесты в `k8s/staging/` и `k8s/production/`.
4. Обновите smoke‑тест при необходимости.

### Изменение триггеров

Отредактируйте секцию `on` в соответствующем YAML‑файле.

### Добавление новых проверок

Например, security scanning (Trivy, Snyk) можно добавить как отдельный job в pipeline.

## Лучшие практики

1. **Идемпотентность**: Развёртывание должно быть идемпотентным (многократное применение манифестов не должно ломать систему).
2. **Версионирование**: Все образы тегируются хэшем коммита и семантическим версионированием.
3. **Изоляция сред**: Staging и production должны быть максимально изолированы.
4. **Blue‑Green или Canary**: Для production развёртывания используйте стратегии, минимизирующие downtime.
5. **Документация**: Все изменения в pipeline должны быть документированы.

## Устранение проблем

### Pipeline fails на этапе lint

- Проверьте, что код соответствует black/isort. Запустите `black .` и `isort .` локально.
- Исправьте ошибки flake8 и mypy.

### Pipeline fails на этапе test

- Убедитесь, что инфраструктурные сервисы (Kafka, Redis, PostgreSQL) доступны в CI.
- Проверьте логи тестов для определения причины падения.

### Pipeline fails на этапе deploy

- Проверьте, что секреты (KUBECONFIG, API keys) корректно установлены.
- Убедитесь, что Kubernetes кластер доступен и имеет достаточно ресурсов.
- Проверьте манифесты на синтаксические ошибки.

### Образы не публикуются

- Убедитесь, что секреты для Container Registry верны.
- Проверьте, что Dockerfile существует и не содержит ошибок.

## Дополнительные ресурсы

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Kubernetes Deployment Strategies](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy)
- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)