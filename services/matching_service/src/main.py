import logging
import time
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette_prometheus import PrometheusMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src import mq
from src.models import Match, Message, Swipe
from src.schemas import MatchOut, MessageCreate, MessageOut, SwipeCreate, SwipeResult

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","service":"matching_service","level":"%(levelname)s","msg":"%(message)s"}',
)

app = FastAPI(title="Matching Service", version="0.1.0")
app.add_middleware(PrometheusMiddleware)

swipes_total = Counter("swipes_total", "Total swipes", ["action"])
matches_total = Counter("matches_total", "Total matches created")
messages_total = Counter("messages_total", "Total messages sent")
swipe_duration = Histogram("swipe_duration_seconds", "Swipe processing time")


@app.on_event("startup")
async def startup() -> None:
    await mq.connect()


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


@app.post("/api/v1/swipes", response_model=SwipeResult)
async def create_swipe(
    payload: SwipeCreate, db: AsyncSession = Depends(get_db)
) -> SwipeResult:
    if payload.swiper_id == payload.swiped_id:
        raise HTTPException(status_code=400, detail="Cannot swipe yourself")

    _t0 = time.monotonic()
    try:
        swipe = Swipe(
            swiper_id=payload.swiper_id,
            swiped_id=payload.swiped_id,
            action=payload.action,
        )
        try:
            db.add(swipe)
            await db.flush()
        except IntegrityError:
            await db.rollback()
            return SwipeResult(is_match=False)

        swipes_total.labels(action=payload.action).inc()

        await mq.publish(
            "swipe.created",
            {
                "swiper_id": str(payload.swiper_id),
                "swiped_id": str(payload.swiped_id),
                "action": payload.action,
            },
        )

        match_id: uuid.UUID | None = None
        is_match = False

        if payload.action == "like":
            reverse = await db.scalar(
                select(Swipe).where(
                    Swipe.swiper_id == payload.swiped_id,
                    Swipe.swiped_id == payload.swiper_id,
                    Swipe.action == "like",
                )
            )
            if reverse:
                u1, u2 = sorted([payload.swiper_id, payload.swiped_id])
                existing_match = await db.scalar(
                    select(Match).where(Match.user1_id == u1, Match.user2_id == u2)
                )
                if not existing_match:
                    match = Match(user1_id=u1, user2_id=u2)
                    db.add(match)
                    await db.flush()
                    match_id = match.id
                    is_match = True
                    matches_total.inc()
                    await mq.publish(
                        "match.created",
                        {
                            "match_id": str(match.id),
                            "user1_id": str(u1),
                            "user2_id": str(u2),
                        },
                    )

        await db.commit()
        return SwipeResult(is_match=is_match, match_id=match_id)
    finally:
        swipe_duration.observe(time.monotonic() - _t0)


@app.get("/api/v1/swipes/{user_id}/swiped-ids")
async def get_swiped_ids(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[str]:
    result = await db.scalars(select(Swipe.swiped_id).where(Swipe.swiper_id == user_id))
    return [str(uid) for uid in result]


@app.get("/api/v1/swipes/{user_id}/stats")
async def get_swipe_stats(
    user_id: uuid.UUID,
    since: datetime = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    q = select(func.count()).where(Swipe.swiped_id == user_id, Swipe.action == "like")
    if since:
        q = q.where(Swipe.created_at >= since)
    new_likes = (await db.scalar(q)) or 0

    mq2 = select(func.count()).where(
        (Match.user1_id == user_id) | (Match.user2_id == user_id)
    )
    if since:
        mq2 = mq2.where(Match.created_at >= since)
    new_matches = (await db.scalar(mq2)) or 0

    return {"new_likes": int(new_likes), "new_matches": int(new_matches)}


@app.get("/api/v1/matches/{user_id}", response_model=list[MatchOut])
async def get_matches(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Match]:
    result = await db.scalars(
        select(Match)
        .where(
            ((Match.user1_id == user_id) | (Match.user2_id == user_id)),
            Match.is_active.is_(True),
        )
        .order_by(Match.created_at.desc())
    )
    return list(result)


@app.post("/api/v1/messages", response_model=MessageOut)
async def send_message(
    payload: MessageCreate, db: AsyncSession = Depends(get_db)
) -> Message:
    match = await db.get(Match, payload.match_id)
    if not match or not match.is_active:
        raise HTTPException(status_code=404, detail="Match not found or inactive")

    if payload.sender_id not in (match.user1_id, match.user2_id):
        raise HTTPException(status_code=403, detail="Not a participant")

    is_first = not await db.scalar(
        select(Message).where(
            Message.match_id == payload.match_id,
            Message.sender_id == payload.sender_id,
        )
    )

    msg = Message(
        match_id=payload.match_id, sender_id=payload.sender_id, body=payload.body
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    messages_total.inc()

    receiver_id = (
        match.user2_id if payload.sender_id == match.user1_id else match.user1_id
    )
    await mq.publish(
        "message.sent",
        {
            "match_id": str(payload.match_id),
            "sender_id": str(payload.sender_id),
            "receiver_id": str(receiver_id),
            "body": payload.body,
            "is_first_message": is_first,
        },
    )

    return msg


@app.get("/api/v1/messages/{match_id}", response_model=list[MessageOut])
async def get_messages(
    match_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[Message]:
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    result = await db.scalars(
        select(Message)
        .where(Message.match_id == match_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(list(result)))


@app.put("/api/v1/messages/{message_id}/read")
async def mark_read(message_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    msg = await db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_read = True
    await db.commit()
    return {"ok": True}
