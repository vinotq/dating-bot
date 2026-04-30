import html

import httpx
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from constants import GENDER_FROM_API, LOOKING_FROM_API
from dependencies import matching_client, ranking_client, user_client
from keyboards import (
    BTN_MAIN_SEARCH,
    BTN_MAIN_MATCHES,
    main_menu_keyboard,
    matches_keyboard,
    swipe_keyboard,
)
from handlers.common import allow_main_menu

router = Router()


def _search_card_text(card: dict) -> str:
    name = html.escape(card["name"])
    city = html.escape(card["city"])
    bio_raw = card.get("bio") or ""
    bio = html.escape(bio_raw) if bio_raw else "<i>не заполнено</i>"
    gender_raw = card.get("gender", "")
    looking_raw = card.get("looking_for_gender", "")
    gender = html.escape(GENDER_FROM_API.get(gender_raw, gender_raw))
    looking = html.escape(LOOKING_FROM_API.get(looking_raw, looking_raw))
    score = float(card.get("combined_score") or 0)
    raw_interests = card.get("interests") or []
    interests_line = (
        "<b>Интересы:</b> " + html.escape(", ".join(raw_interests))
        if raw_interests else ""
    )
    parts = [
        f"<b>{name}</b> · {card['age']} · {city}",
        f"<b>Пол:</b> {gender} · <b>Ищет:</b> {looking}",
        f"<b>Рейтинг:</b> <i>{score:.1f}</i> <code>(temp)</code>",
        "",
        bio,
    ]
    if interests_line:
        parts.append("")
        parts.append(interests_line)
    return "\n".join(parts)[:1020]


async def _show_card(message: Message, bot: Bot, user_id: str) -> bool:
    try:
        card = await ranking_client.get_feed(user_id)
    except httpx.HTTPError:
        await message.answer(
            "Сервис поиска недоступен — попробуй позже.",
            reply_markup=main_menu_keyboard(),
        )
        return False
    if card is None:
        await message.answer(
            "Пока больше анкет нет — возвращайся позже.",
            reply_markup=main_menu_keyboard(),
        )
        return False

    swiped_user_id = str(card["user_id"])
    card_text = _search_card_text(card)
    keyboard = swipe_keyboard(swiped_user_id)

    photo_id = card.get("primary_photo_id")
    if photo_id:
        try:
            photo_bytes = await user_client.fetch_photo_bytes(str(card["profile_id"]), str(photo_id))
            await message.answer_photo(
                BufferedInputFile(photo_bytes, filename="photo.jpg"),
                caption=card_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            return True
        except httpx.HTTPError:
            pass

    no_photo_prefix = "<i>Без фото</i> 😢\n\n"
    await message.answer(no_photo_prefix + card_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    return True


@router.message(Command("search"))
async def search_command(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await allow_main_menu(state):
        await message.answer("<b>Погоди</b> — <i>сначала ответь на вопрос выше.</i>")
        return
    await _start_search(message, bot)


@router.message(F.text == BTN_MAIN_SEARCH)
async def search_button(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await allow_main_menu(state):
        await message.answer("<b>Погоди</b> — <i>сначала ответь на вопрос выше.</i>")
        return
    await _start_search(message, bot)


async def _start_search(message: Message, bot: Bot) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await user_client.get_user(tg_user.id)
    if user is None:
        await message.answer("Сначала отправь /start.")
        return
    profile = await user_client.get_profile_by_user(user["id"])
    if profile is None:
        await message.answer("Сначала создай анкету — /start.")
        return
    await _show_card(message, bot, user["id"])


@router.callback_query(F.data.startswith("sw:like:") | F.data.startswith("sw:skip:"))
async def handle_swipe(cb: CallbackQuery, bot: Bot) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return

    parts = (cb.data or "").split(":")
    if len(parts) != 3:
        await cb.answer()
        return

    action = parts[1]          # like | skip
    swiped_user_id = parts[2]  # UUID

    user = await user_client.get_user(cb.from_user.id)
    if user is None:
        await cb.answer("Нужно зарегистрироваться — /start")
        return

    swiper_user_id = user["id"]
    if swiper_user_id == swiped_user_id:
        await cb.answer()
        return

    try:
        result = await matching_client.swipe(swiper_user_id, swiped_user_id, action)
    except httpx.HTTPStatusError:
        await cb.answer("Ошибка — попробуй ещё раз")
        return

    await cb.answer("❤️ Мэтч!" if result.get("is_match") else ("❤️" if action == "like" else "👎"))
    await cb.message.edit_reply_markup(reply_markup=None)

    if result.get("is_match"):
        await cb.message.answer(
            "<b>Это мэтч!</b> Смотри в разделе /matches.",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )

    # показываем следующую анкету
    profile = await user_client.get_profile_by_user(swiper_user_id)
    if profile:
        await _show_card(cb.message, bot, swiper_user_id)


@router.message(F.text == BTN_MAIN_MATCHES)
async def matches_button(message: Message, state: FSMContext) -> None:
    if not await allow_main_menu(state):
        await message.answer("<b>Погоди</b> — <i>сначала ответь на вопрос выше.</i>")
        return
    await _show_matches(message)


@router.message(Command("matches"))
async def matches_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_matches(message)


async def _show_matches(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await user_client.get_user(tg_user.id)
    if user is None:
        await message.answer("Сначала отправь /start.")
        return
    try:
        matches = await matching_client.get_matches(user["id"])
    except httpx.HTTPError:
        await message.answer("Не удалось загрузить мэтчи — попробуй позже.")
        return
    if not matches:
        await message.answer(
            "<b>Мэтчей пока нет</b>\n<i>Продолжай лайкать — кто-то обязательно ответит ❤️</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )
        return

    my_id = str(user["id"])
    sorted_matches = sorted(matches, key=lambda m: m.get("created_at") or "", reverse=True)

    buttons: list[tuple[str, str]] = []
    for m in sorted_matches:
        u1 = str(m["user1_id"])
        u2 = str(m["user2_id"])
        partner_id = u2 if u1 == my_id else u1
        try:
            profile = await user_client.get_profile_by_user(partner_id)
        except httpx.HTTPError:
            profile = None
        if profile is None:
            buttons.append(("анкета недоступна", partner_id))
            continue
        gender_icon = {"male": "♂", "female": "♀", "other": "·"}.get(profile.get("gender", ""), "·")
        name = profile.get("name") or "—"
        age = profile.get("age") or "—"
        city = profile.get("city") or "—"
        btn_text = f"{gender_icon} {name} · {age} · {city}"
        buttons.append((btn_text, partner_id))

    header = f"<b>💞 Твои мэтчи</b> · <i>{len(sorted_matches)}</i>\n<i>Нажми, чтобы открыть чат</i>"
    await message.answer(
        header,
        parse_mode=ParseMode.HTML,
        reply_markup=matches_keyboard(buttons),
    )


@router.callback_query(F.data.startswith("match:open:"))
async def open_match_chat(cb: CallbackQuery) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return
    parts = (cb.data or "").split(":")
    if len(parts) != 3:
        await cb.answer()
        return
    partner_id = parts[2]
    try:
        profile = await user_client.get_profile_by_user(partner_id)
    except httpx.HTTPError:
        profile = None

    if profile is None:
        await cb.answer("Анкета недоступна", show_alert=True)
        return

    name = html.escape(profile.get("name") or "—")
    city = html.escape(profile.get("city") or "—")
    age = profile.get("age") or "—"
    bio_raw = (profile.get("bio") or "").strip()
    bio = html.escape(bio_raw) if bio_raw else "<i>без описания</i>"

    await cb.message.answer(
        f"<b>{name}</b> · {age} · {city}\n\n"
        f"{bio}\n\n"
        f"<i>Чат появится чуть позже</i>",
        parse_mode=ParseMode.HTML,
    )
    await cb.answer()
