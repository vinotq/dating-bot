# Диаграмма потоков данных (Data Flow Diagram)

Как данные проходят через систему от ввода пользователем до сохранения в БД, кэширования и доставки другим пользователям.

## Поток анкеты

```mermaid
flowchart LR
    TG[Telegram] --> BOT[Bot Service]
    BOT --> USER[User Service]
    USER --> PG[(PostgreSQL)]
    USER --> MINIO[(MinIO)]
```

Пользователь вводит данные в Telegram. Бот собирает их и отправляет в User Service. User Service сохраняет профиль в PostgreSQL и фото в MinIO.

## Поток рейтинга

```mermaid
flowchart LR
    MQ[RabbitMQ Events] --> RANK[Ranking Service]
    RANK --> PG[(PostgreSQL ratings)]
    RANK --> REDIS[(Redis feed cache)]
```

## Поток свайпа

```mermaid
flowchart LR
    TG[Telegram] --> BOT[Bot Service]
    BOT --> MATCH[Matching Service]
    MATCH --> PG[(PostgreSQL swipes/matches)]
    MATCH --> MQ[RabbitMQ]
```

Пользователь ставит лайк или пропуск в Telegram. Бот передаёт в Matching Service. Matching Service записывает в PostgreSQL и публикует события в MQ.

## Поток уведомлений

```mermaid
flowchart LR
    MQ[RabbitMQ match.created] --> BOT[Bot Service]
    BOT --> TG[Telegram]
```

## Поток фоновых задач

```mermaid
flowchart LR
    BEAT[Celery] --> MQ[RabbitMQ]
    MQ --> WORKER[Celery]
    WORKER --> PG[(PostgreSQL)]
    WORKER --> REDIS[(Redis)]
```

Celery по расписанию отправляет задачи в RabbitMQ. Он же выполняет пересчёт рейтингов, предзагрузку ленты, записывает в PostgreSQL и Redis.
