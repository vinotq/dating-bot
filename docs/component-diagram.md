# Диаграмма компонентов (Component Diagram)

Высокоуровневое представление сервисов, инфраструктуры и связей между ними.

```mermaid
flowchart TB
    subgraph external["Внешние системы"]
        TG[Telegram API]
    end

    subgraph services["Сервисы приложения"]
        BOT[Bot Service]
        USER[User Service]
        MATCH[Matching Service]
        RANK[Ranking Service]
        CELERY[Celery Workers]
    end

    subgraph infrastructure["Инфраструктура"]
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        MQ[RabbitMQ]
        MINIO[(MinIO)]
        PROM[Prometheus]
        GRAF[Grafana]
    end

    TG <--> BOT

    BOT -->|"HTTP REST"| USER
    BOT -->|"HTTP REST"| MATCH
    BOT -->|"HTTP REST"| RANK

    USER -->|"publish events"| MQ
    MATCH -->|"publish events"| MQ
    MQ -->|"consume events"| RANK
    MQ -->|"consume events"| BOT

    RANK --> REDIS
    RANK --> CELERY
    CELERY --> MQ

    USER --> MINIO

    BOT --> PG
    USER --> PG
    MATCH --> PG
    RANK --> PG
    CELERY --> PG

    BOT -->|"metrics"| PROM
    USER -->|"metrics"| PROM
    MATCH -->|"metrics"| PROM
    RANK -->|"metrics"| PROM
    CELERY -->|"metrics"| PROM

    PROM --> GRAF
```

## Легенда

| Тип связи | Описание |
|-----------|----------|
| HTTP REST | Синхронные запросы (профили, свайпы, лента) |
| MQ events | Асинхронные события (`match.created`, `profile.updated`, `swipe.created`) |
| metrics | Экспорт метрик для Prometheus |
