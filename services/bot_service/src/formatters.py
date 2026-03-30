import html

from constants import GENDER_FROM_API, LOOKING_FROM_API

def format_search_age_range(age_min: int, age_max: int) -> str:
    if age_max == -1:
        return f"от {age_min} без ограничений"
    return f"от {age_min} до {age_max}"


def parse_settings_age_max(text: str) -> int | None:
    raw = (text or "").strip()
    low = raw.lower().replace("−", "-")
    if low in ("без лимита", "без ограничений", "без ограничения", "нет", "любой", "не важно"):
        return -1
    if not low.isdigit():
        return None
    return int(low)


def profile_text_html(profile: dict) -> str:
    name = html.escape(profile["name"])
    city = html.escape(profile["city"])
    bio_raw = profile.get("bio") or "пока пусто"
    bio = html.escape(bio_raw) if profile.get("bio") else bio_raw
    gender = html.escape(GENDER_FROM_API.get(profile["gender"], profile["gender"]))
    looking = html.escape(
        LOOKING_FROM_API.get(profile["looking_for_gender"], profile["looking_for_gender"])
    )
    return (
        f"<b>Как зовут:</b> {name}\n"
        f"<b>Возраст:</b> {profile['age']}\n"
        f"<b>Пол:</b> {gender}\n"
        f"<b>Город:</b> {city}\n"
        f"<b>О себе:</b> {bio}\n"
        f"<i>Анкета заполнена на {profile['completeness_score']}%</i>\n"
        f"<b>Кого хочу видеть:</b> {looking}, "
        f"<i>{format_search_age_range(profile['age_min'], profile['age_max'])}</i>"
    )


def profile_caption_for_photo(profile: dict) -> str:
    text = profile_text_html(profile)
    if len(text) <= 1024:
        return text
    return text[:1020] + "…"
