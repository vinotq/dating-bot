import uuid

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src import mq
from src.models import Match, Swipe
from src.schemas import MatchOut, SwipeCreate, SwipeResult

app = FastAPI(title="Matching Service", version="0.1.0")


@app.on_event("startup")
async def startup() -> None:
    await mq.connect()


@app.post("/api/v1/swipes", response_model=SwipeResult)
async def create_swipe(payload: SwipeCreate, db: AsyncSession = Depends(get_db)) -> SwipeResult:
    if payload.swiper_id == payload.swiped_id:
        raise HTTPException(status_code=400, detail="Cannot swipe yourself")

    swipe = Swipe(swiper_id=payload.swiper_id, swiped_id=payload.swiped_id, action=payload.action)
    try:
        db.add(swipe)
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return SwipeResult(is_match=False)

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


@app.get("/api/v1/matches/{user_id}", response_model=list[MatchOut])
async def get_matches(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[Match]:
    result = await db.scalars(
        select(Match).where(
            ((Match.user1_id == user_id) | (Match.user2_id == user_id)),
            Match.is_active == True,
        )
    )
    return list(result)
