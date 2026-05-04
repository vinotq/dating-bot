import asyncio
import base64
import io
import logging
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from minio import Minio
from minio.error import S3Error
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette_prometheus import PrometheusMiddleware
from sqlalchemy import text, select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src import mq
from src.models import Interest, Photo, Profile, User, UserInterest
from src.schemas import (
    InterestCreate,
    InterestOut,
    PhotoOrderUpdate,
    PhotoOut,
    PreferencesUpdate,
    ProfileCreate,
    ProfileOut,
    ProfileUpdate,
    UserCreate,
    UserInterestsUpdate,
    UserOut,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","service":"user_service","level":"%(levelname)s","msg":"%(message)s"}',
)

app = FastAPI(title="User Service", version="0.1.0")
app.add_middleware(PrometheusMiddleware)

registrations_total = Counter("registrations_total", "Total user registrations")
profiles_created_total = Counter("profiles_created_total", "Total profiles created")
photos_uploaded_total = Counter("photos_uploaded_total", "Total photos uploaded")

_minio: Minio | None = None
_minio_public: Minio | None = None


def _get_minio() -> Minio:
    assert _minio is not None, "MinIO client not initialized"
    return _minio


def _get_minio_public() -> Minio:
    assert _minio_public is not None, "MinIO public client not initialized"
    return _minio_public


def _s3_url(s3_key: str) -> str:
    scheme = "https" if settings.minio_use_ssl else "http"
    return f"{scheme}://{settings.minio_endpoint}/{settings.minio_bucket}/{s3_key}"


async def _minio_upload(s3_key: str, data: bytes) -> None:
    client = _get_minio()
    await asyncio.to_thread(
        client.put_object,
        settings.minio_bucket,
        s3_key,
        io.BytesIO(data),
        len(data),
        content_type="image/jpeg",
    )


async def _minio_download(s3_key: str) -> bytes:
    client = _get_minio()
    response = await asyncio.to_thread(client.get_object, settings.minio_bucket, s3_key)
    try:
        return await asyncio.to_thread(response.read)
    finally:
        response.close()
        response.release_conn()


async def _minio_delete(s3_key: str) -> None:
    try:
        client = _get_minio()
        await asyncio.to_thread(client.remove_object, settings.minio_bucket, s3_key)
    except S3Error:
        pass


def calculate_completeness(profile: Profile, has_interests: bool, photos_count: int) -> int:
    score = 0
    if profile.name and profile.age and profile.gender and profile.city:
        score += 50
    if profile.bio and profile.bio.strip():
        score += 20
    if has_interests:
        score += 15
    if photos_count > 0:
        score += 15
    return min(100, max(0, score))


async def recalculate_completeness(db: AsyncSession, profile: Profile) -> None:
    photos_count = await db.scalar(select(text("count(*)")).select_from(Photo).where(Photo.profile_id == profile.id))
    interests_count = await db.scalar(
        select(text("count(*)")).select_from(UserInterest).where(UserInterest.user_id == profile.user_id)
    )
    profile.completeness_score = calculate_completeness(
        profile=profile,
        has_interests=bool(interests_count),
        photos_count=int(photos_count or 0),
    )


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def startup() -> None:
    await mq.connect()
    global _minio, _minio_public
    # DDL выполняется в `python -m src.migrate` перед uvicorn (см. Dockerfile).
    _minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl,
    )
    _minio_public = Minio(
        settings.minio_public_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl,
    )
    bucket_exists = await asyncio.to_thread(_minio.bucket_exists, settings.minio_bucket)
    if not bucket_exists:
        await asyncio.to_thread(_minio.make_bucket, settings.minio_bucket)


@app.post("/api/v1/users", response_model=UserOut)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.scalar(select(User).where(User.telegram_id == payload.telegram_id))
    if existing:
        return existing
    user = User(telegram_id=payload.telegram_id, username=payload.username)
    db.add(user)
    await db.flush()

    if payload.referral_code:
        referrer = await db.scalar(select(User).where(User.referral_code == payload.referral_code))
        if referrer and referrer.id != user.id:
            await mq.publish("referral.created", {
                "referrer_id": str(referrer.id),
                "referred_id": str(user.id),
            })

    await db.commit()
    await db.refresh(user)
    registrations_total.inc()
    await mq.publish("user.registered", {"user_id": str(user.id), "telegram_id": user.telegram_id})
    return user


@app.get("/api/v1/users/by-uuid/{user_id}", response_model=UserOut)
async def get_user_by_uuid(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/api/v1/users/{telegram_id}", response_model=UserOut)
async def get_user_by_telegram_id(telegram_id: int, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/v1/profiles", response_model=ProfileOut)
async def create_profile(payload: ProfileCreate, db: AsyncSession = Depends(get_db)) -> Profile:
    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = await db.scalar(select(Profile).where(Profile.user_id == payload.user_id))
    if existing:
        raise HTTPException(status_code=409, detail="Profile already exists")
    profile = Profile(**payload.model_dump())
    db.add(profile)
    await recalculate_completeness(db, profile)
    await db.commit()
    await db.refresh(profile)
    profiles_created_total.inc()
    await mq.publish("profile.created", {"user_id": str(profile.user_id), "profile_id": str(profile.id), "completeness_score": profile.completeness_score})
    return profile


@app.get("/api/v1/profiles/{profile_id}", response_model=ProfileOut)
async def get_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Profile:
    profile = await db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get("/api/v1/profiles/by-user/{user_id}", response_model=ProfileOut)
async def get_profile_by_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Profile:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.put("/api/v1/profiles/{profile_id}", response_model=ProfileOut)
async def update_profile(profile_id: uuid.UUID, payload: ProfileUpdate, db: AsyncSession = Depends(get_db)) -> Profile:
    profile = await db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(profile, key, value)
    if profile.age_min < 14:
        raise HTTPException(status_code=422, detail="age_min must be at least 14")
    if profile.age_max != -1 and profile.age_max < 14:
        raise HTTPException(status_code=422, detail="age_max must be -1 (no upper limit) or >= 14")
    if profile.age_max != -1 and profile.age_min > profile.age_max:
        raise HTTPException(status_code=422, detail="age_min must not exceed age_max")
    await recalculate_completeness(db, profile)
    await db.commit()
    await db.refresh(profile)
    await mq.publish("profile.updated", {"user_id": str(profile.user_id), "profile_id": str(profile.id), "completeness_score": profile.completeness_score})
    return profile


@app.delete("/api/v1/profiles/{profile_id}")
async def delete_profile(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    profile = await db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    photos_rows = (await db.scalars(select(Photo).where(Photo.profile_id == profile_id))).all()
    s3_keys = [p.s3_key for p in photos_rows]
    await db.execute(delete(Photo).where(Photo.profile_id == profile_id))
    await db.delete(profile)
    await db.commit()
    for key in s3_keys:
        await _minio_delete(key)
    return {"ok": True}


@app.post("/api/v1/profiles/{profile_id}/photos", response_model=PhotoOut)
async def upload_photo(
    profile_id: uuid.UUID,
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    db: AsyncSession = Depends(get_db),
) -> Photo:
    profile = await db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    existing_count = await db.scalar(select(text("count(*)")).select_from(Photo).where(Photo.profile_id == profile_id))
    if int(existing_count or 0) >= 5:
        raise HTTPException(status_code=400, detail="Photo limit is 5")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    photo_id = uuid.uuid4()
    s3_key = f"profiles/{profile.user_id}/{photo_id}.jpg"
    await _minio_upload(s3_key, data)
    photo = Photo(
        id=photo_id,
        profile_id=profile_id,
        s3_key=s3_key,
        s3_url=_s3_url(s3_key),
        is_primary=is_primary,
        display_order=int(existing_count or 0),
    )
    db.add(photo)
    await recalculate_completeness(db, profile)
    await db.commit()
    await db.refresh(photo)
    photo_count = await db.scalar(select(text("count(*)")).select_from(Photo).where(Photo.profile_id == profile_id))
    photos_uploaded_total.inc()
    from src.tasks import generate_thumbnail
    generate_thumbnail.delay(s3_key, str(photo_id))
    await mq.publish("photo.uploaded", {"user_id": str(profile.user_id), "profile_id": str(profile_id), "photo_count": int(photo_count or 0)})
    return photo


@app.get("/api/v1/profiles/{profile_id}/photos", response_model=list[PhotoOut])
async def list_profile_photos(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[Photo]:
    profile = await db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    result = await db.scalars(
        select(Photo)
        .where(Photo.profile_id == profile_id)
        .order_by(Photo.display_order.asc(), Photo.created_at.asc())
    )
    return list(result)


@app.get("/api/v1/profiles/{profile_id}/photos/{photo_id}/file")
async def download_profile_photo(
    profile_id: uuid.UUID,
    photo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    profile = await db.get(Profile, profile_id)
    photo = await db.get(Photo, photo_id)
    if not profile or not photo or photo.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Photo not found")
    try:
        content = await _minio_download(photo.s3_key)
    except S3Error:
        raise HTTPException(status_code=404, detail="Photo file not found in storage")
    return Response(content=content, media_type="image/jpeg")


@app.get("/api/v1/profiles/{profile_id}/photos/{photo_id}/presigned")
async def presigned_photo_url(
    profile_id: uuid.UUID,
    photo_id: uuid.UUID,
    expires: int = 3600,
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await db.get(Profile, profile_id)
    photo = await db.get(Photo, photo_id)
    if not profile or not photo or photo.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Photo not found")
    from datetime import timedelta
    url = await asyncio.to_thread(
        _get_minio_public().presigned_get_object,
        settings.minio_bucket,
        photo.s3_key,
        expires=timedelta(seconds=expires),
    )
    return {"url": url, "expires_in": expires}


@app.delete("/api/v1/profiles/{profile_id}/photos/{photo_id}")
async def delete_photo(profile_id: uuid.UUID, photo_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    photo = await db.get(Photo, photo_id)
    profile = await db.get(Profile, profile_id)
    if not photo or not profile or photo.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Photo not found")
    s3_key = photo.s3_key
    await db.delete(photo)
    await db.flush()
    remaining = (
        await db.scalars(
            select(Photo)
            .where(Photo.profile_id == profile_id)
            .order_by(Photo.display_order.asc(), Photo.created_at.asc())
        )
    ).all()
    for i, p in enumerate(remaining):
        p.display_order = i
    await recalculate_completeness(db, profile)
    await db.commit()
    await _minio_delete(s3_key)
    return {"ok": True}


@app.put("/api/v1/profiles/{profile_id}/photos/order", response_model=list[PhotoOut])
async def reorder_profile_photos(
    profile_id: uuid.UUID, payload: PhotoOrderUpdate, db: AsyncSession = Depends(get_db)
) -> list[Photo]:
    profile = await db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    existing_rows = (await db.scalars(select(Photo).where(Photo.profile_id == profile_id))).all()
    existing_ids = {p.id for p in existing_rows}
    incoming = list(payload.photo_ids)
    if len(incoming) != len(existing_ids) or set(incoming) != existing_ids:
        raise HTTPException(
            status_code=400,
            detail="photo_ids must contain each profile photo exactly once",
        )
    id_to_photo = {p.id: p for p in existing_rows}
    for order, pid in enumerate(incoming):
        id_to_photo[pid].display_order = order
    await recalculate_completeness(db, profile)
    await db.commit()
    ordered = await db.scalars(
        select(Photo)
        .where(Photo.profile_id == profile_id)
        .order_by(Photo.display_order.asc(), Photo.created_at.asc())
    )
    return list(ordered)


@app.get("/api/v1/users/{user_id}/preferences")
async def get_preferences(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, str | int]:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "looking_for_gender": profile.looking_for_gender,
        "age_min": profile.age_min,
        "age_max": profile.age_max,
    }


@app.put("/api/v1/users/{user_id}/preferences")
async def update_preferences(
    user_id: uuid.UUID, payload: PreferencesUpdate, db: AsyncSession = Depends(get_db)
) -> dict[str, str | int]:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.looking_for_gender = payload.looking_for_gender
    profile.age_min = payload.age_min
    profile.age_max = payload.age_max
    await db.commit()
    return {
        "looking_for_gender": profile.looking_for_gender,
        "age_min": profile.age_min,
        "age_max": profile.age_max,
    }


@app.get("/api/v1/interests", response_model=list[InterestOut])
async def list_interests(db: AsyncSession = Depends(get_db)) -> list[Interest]:
    result = await db.scalars(select(Interest).order_by(Interest.name.asc()))
    return list(result)


@app.post("/api/v1/interests", response_model=InterestOut)
async def create_interest(payload: InterestCreate, db: AsyncSession = Depends(get_db)) -> Interest:
    existing = await db.scalar(select(Interest).where(Interest.name == payload.name))
    if existing:
        return existing
    interest = Interest(name=payload.name)
    db.add(interest)
    try:
        await db.commit()
        await db.refresh(interest)
        return interest
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(select(Interest).where(Interest.name == payload.name))
        if existing:
            return existing
        raise


@app.put("/api/v1/users/{user_id}/interests")
async def set_user_interests(
    user_id: uuid.UUID, payload: UserInterestsUpdate, db: AsyncSession = Depends(get_db)
) -> dict[str, bool]:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    existing = await db.scalars(select(Interest.id).where(Interest.id.in_(payload.interest_ids)))
    existing_ids = set(existing)
    if len(existing_ids) != len(set(payload.interest_ids)):
        raise HTTPException(status_code=400, detail="Some interests do not exist")
    await db.execute(delete(UserInterest).where(UserInterest.user_id == user_id))
    for interest_id in payload.interest_ids:
        db.add(UserInterest(user_id=user_id, interest_id=interest_id))
    await recalculate_completeness(db, profile)
    await db.commit()
    return {"ok": True}


def _gen_referral_code(user_id: uuid.UUID) -> str:
    raw = base64.urlsafe_b64encode(user_id.bytes).decode().rstrip("=")
    return raw[:16]


@app.post("/api/v1/users/{user_id}/referral-code")
async def get_or_create_referral_code(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.referral_code:
        user.referral_code = _gen_referral_code(user_id)
        await db.commit()
        await db.refresh(user)
    return {"referral_code": user.referral_code}


@app.get("/api/v1/referrals/by-code/{code}", response_model=UserOut)
async def get_user_by_referral_code(code: str, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.scalar(select(User).where(User.referral_code == code))
    if not user:
        raise HTTPException(status_code=404, detail="Referral code not found")
    return user
