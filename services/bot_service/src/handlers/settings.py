from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from constants import LOOKING_FROM_API, LOOKING_TO_API
from dependencies import notification_client, ranking_client, user_client
from formatters import format_search_age_range, parse_settings_age_max
from keyboards import (
    BTN_BACK,
    back_keyboard,
    looking_for_with_back_keyboard,
    main_menu_keyboard,
)
from states import EditStates

router = Router()


async def start_settings_wizard(
    message: Message, state: FSMContext, *, telegram_id: int | None = None
) -> None:
    tid = telegram_id
    if tid is None and message.from_user is not None:
        tid = message.from_user.id
    if tid is None:
        return
    user = await user_client.get_user(tid)
    if user is None:
        await message.answer("Сначала нажми /start")
        return
    prefs = await user_client.get_preferences(user["id"])
    await state.set_state(EditStates.waiting_settings_gender)
    await state.update_data(
        user_id=user["id"],
        settings_age_min=prefs["age_min"],
        settings_age_max=prefs["age_max"],
    )
    await message.answer(
        f"Сейчас у тебя: предпочитаемый пол — <b>{LOOKING_FROM_API.get(prefs['looking_for_gender'], prefs['looking_for_gender'])}</b>, "
        f"возраст — <b>{format_search_age_range(prefs['age_min'], prefs['age_max'])}</b>.\n\n"
        "Кого хочешь видеть в ленте?",
        reply_markup=looking_for_with_back_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("settings"))
async def settings_command(message: Message, state: FSMContext) -> None:
    await start_settings_wizard(message, state)


@router.message(EditStates.waiting_settings_gender)
async def settings_gender_input(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.clear()
        await message.answer("Настройки отменены", reply_markup=main_menu_keyboard())
        return
    looking_for_raw = (message.text or "").strip().lower()
    if looking_for_raw not in LOOKING_TO_API:
        await message.answer(
            "Напиши: <b>мужчины</b>, <b>женщины</b> или <b>любой</b>",
            parse_mode="HTML",
        )
        return
    await state.update_data(settings_looking_for_gender=LOOKING_TO_API[looking_for_raw])
    await state.set_state(EditStates.waiting_settings_age_min)
    await message.answer(
        "С какого возраста показывать людей?", reply_markup=back_keyboard()
    )


@router.message(EditStates.waiting_settings_age_min)
async def settings_age_min_input(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(EditStates.waiting_settings_gender)
        await message.answer(
            "Кого хочешь видеть в ленте?",
            reply_markup=looking_for_with_back_keyboard(),
        )
        return
    age_min_text = (message.text or "").strip()
    if not age_min_text.isdigit():
        await message.answer("<i>Нужно просто число</i>")
        return
    age_min = int(age_min_text)
    if age_min < 14:
        await message.answer("<i>Возраст от 14 лет и выше, попробуй ещё раз</i>")
        return
    await state.update_data(settings_age_min=age_min)
    await state.set_state(EditStates.waiting_settings_age_max)
    await message.answer(
        "До какого возраста показывать? Число не ниже твоего минимума — или "
        "<b>без лимита</b>, если верхней границы не важна.",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


@router.message(EditStates.waiting_settings_age_max)
async def settings_age_max_input(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(EditStates.waiting_settings_age_min)
        await message.answer(
            "С какого возраста показывать?", reply_markup=back_keyboard()
        )
        return
    age_max = parse_settings_age_max(message.text or "")
    if age_max is None:
        await message.answer(
            "Нужно число (от 14 и выше) или <b>без лимита</b>", parse_mode="HTML"
        )
        return
    data = await state.get_data()
    age_min = data.get("settings_age_min")
    if not isinstance(age_min, int):
        await message.answer("<i>Что-то пошло не так — начни заново: /settings</i>")
        return
    if age_max < 14:
        await message.answer(
            "Либо не меньше 14, либо <b>без лимита</b>", parse_mode="HTML"
        )
        return
    if age_min > age_max:
        await message.answer(
            "<i>Верхняя граница не может быть меньше нижней, поправь</i>"
        )
        return
    user_id = data.get("user_id")
    looking_for_gender = data.get("settings_looking_for_gender")
    if not user_id or not isinstance(looking_for_gender, str):
        await state.clear()
        await message.answer("<i>Что-то пошло не так — начни заново: /settings</i>")
        return
    prefs = await user_client.update_preferences(
        user_id, looking_for_gender, age_min, age_max
    )
    await state.clear()
    try:
        await ranking_client.reset_feed(user_id)
    except Exception:
        pass
    await message.answer(
        f"Сохранил: {LOOKING_FROM_API.get(prefs['looking_for_gender'], prefs['looking_for_gender'])}, "
        f"{format_search_age_range(prefs['age_min'], prefs['age_max'])}",
        reply_markup=main_menu_keyboard(),
    )


def _notif_keyboard(
    matches: bool, messages: bool, digest: bool
) -> InlineKeyboardMarkup:
    def _toggle(label: str, enabled: bool, cb: str) -> InlineKeyboardButton:
        icon = "✅" if enabled else "❌"
        return InlineKeyboardButton(text=f"{icon} {label}", callback_data=cb)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_toggle("Мэтчи", matches, "notif:toggle:matches")],
            [_toggle("Сообщения", messages, "notif:toggle:messages")],
            [_toggle("Дайджест", digest, "notif:toggle:digest")],
        ]
    )


async def _show_notif_settings(message: Message, user_id: str) -> None:
    try:
        s = await notification_client.get_settings(user_id)
    except Exception:
        await message.answer("Не удалось загрузить настройки — попробуй позже.")
        return
    await message.answer(
        "<b>Настройки уведомлений</b>\nНажми, чтобы включить или выключить:",
        parse_mode="HTML",
        reply_markup=_notif_keyboard(
            s["matches_enabled"], s["messages_enabled"], s["digest_enabled"]
        ),
    )


@router.message(Command("notifications"))
async def notifications_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await user_client.get_user(message.from_user.id)
    if user is None:
        await message.answer("Сначала нажми /start")
        return
    await _show_notif_settings(message, user["id"])


@router.callback_query(F.data.startswith("notif:toggle:"))
async def notif_toggle(cb: CallbackQuery) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return
    user = await user_client.get_user(cb.from_user.id)
    if user is None:
        await cb.answer("Сначала /start")
        return
    user_id = user["id"]
    field = (cb.data or "").split(":")[-1]  # matches / messages / digest

    try:
        s = await notification_client.get_settings(user_id)
    except Exception:
        await cb.answer("Ошибка — попробуй позже", show_alert=True)
        return

    toggled = {
        "matches": s["matches_enabled"],
        "messages": s["messages_enabled"],
        "digest": s["digest_enabled"],
    }
    if field not in toggled:
        await cb.answer()
        return
    toggled[field] = not toggled[field]

    try:
        await notification_client.update_settings(
            user_id,
            matches_enabled=toggled["matches"],
            messages_enabled=toggled["messages"],
            digest_enabled=toggled["digest"],
        )
    except Exception:
        await cb.answer("Ошибка сохранения — попробуй позже", show_alert=True)
        return

    await cb.message.edit_reply_markup(
        reply_markup=_notif_keyboard(
            toggled["matches"], toggled["messages"], toggled["digest"]
        )
    )
    await cb.answer("Сохранено")
