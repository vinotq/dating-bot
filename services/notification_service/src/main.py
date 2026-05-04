from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette_prometheus import PrometheusMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import consumer, mq
from src.db import get_db
from src.models import NotificationSettings

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","service":"notification_service","level":"%(levelname)s","msg":"%(message)s"}',
)

app = FastAPI(title="Notification Service", version="0.1.0")
app.add_middleware(PrometheusMiddleware)

notifications_sent_total = Counter("notifications_sent_total", "Total notifications sent", ["type"])


@app.on_event("startup")
async def startup() -> None:
    await mq.connect()
    asyncio.create_task(consumer.start_consumer())


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(select(1))
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/notifications/{user_id}/settings")
async def get_settings(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.scalar(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
    if not row:
        return {
            "user_id": str(user_id),
            "matches_enabled": True,
            "messages_enabled": True,
            "digest_enabled": True,
        }
    return {
        "user_id": str(row.user_id),
        "matches_enabled": row.matches_enabled,
        "messages_enabled": row.messages_enabled,
        "digest_enabled": row.digest_enabled,
    }


@app.put("/api/v1/notifications/{user_id}/settings")
async def update_settings(
    user_id: uuid.UUID,
    matches_enabled: bool = True,
    messages_enabled: bool = True,
    digest_enabled: bool = True,
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await db.scalar(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
    if not row:
        row = NotificationSettings(user_id=user_id)
        db.add(row)
    row.matches_enabled = matches_enabled
    row.messages_enabled = messages_enabled
    row.digest_enabled = digest_enabled
    await db.commit()
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000)
