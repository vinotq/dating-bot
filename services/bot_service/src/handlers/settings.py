from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from constants import LOOKING_FROM_API, LOOKING_TO_API
from dependencies import ranking_client, user_client
from formatters import format_search_age_range, parse_settings_age_max
from keyboards import BTN_BACK, back_keyboard, main_menu_keyboard
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
        f"Сейчас у тебя: предпочитаемый пол — {LOOKING_FROM_API.get(prefs['looking_for_gender'], prefs['looking_for_gender'])} и "
        f"возраст — {format_search_age_range(prefs['age_min'], prefs['age_max'])}.\n"
        "Кого хочешь видеть в ленте? Напиши одно слово: <b>мужчины</b>, <b>женщины</b> или <b>любой</b>.",
        reply_markup=back_keyboard(),
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
            "Напиши: <b>мужчины</b>, <b>женщины</b> или <b>любой</b>"
        )
        return
    await state.update_data(settings_looking_for_gender=LOOKING_TO_API[looking_for_raw])
    await state.set_state(EditStates.waiting_settings_age_min)
    await message.answer("С какого возраста показывать людей?", reply_markup=back_keyboard())


@router.message(EditStates.waiting_settings_age_min)
async def settings_age_min_input(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(EditStates.waiting_settings_gender)
        await message.answer(
            "Кого хочешь видеть в ленте? Напиши: мужчины, женщины или любой",
            reply_markup=back_keyboard(),
        )
        return
    age_min_text = (message.text or "").strip()
    if not age_min_text.isdigit():
        await message.answer("Нужно просто число")
        return
    age_min = int(age_min_text)
    if age_min < 14:
        await message.answer("Возраст от 14 лет и выше, попробуй ещё раз")
        return
    await state.update_data(settings_age_min=age_min)
    await state.set_state(EditStates.waiting_settings_age_max)
    await message.answer(
        "До какого возраста показывать? Число не ниже твоего минимума — или "
        "<b>без лимита</b>, если верхней границы не важна.",
        reply_markup=back_keyboard(),
    )


@router.message(EditStates.waiting_settings_age_max)
async def settings_age_max_input(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(EditStates.waiting_settings_age_min)
        await message.answer("С какого возраста показывать?", reply_markup=back_keyboard())
        return
    age_max = parse_settings_age_max(message.text or "")
    if age_max is None:
        await message.answer("Нужно число (от 14 и выше) или <b>без лимита</b>")
        return
    data = await state.get_data()
    age_min = data.get("settings_age_min")
    if not isinstance(age_min, int):
        await message.answer("Сбилось что-то, начни заново: /settings")
        return
    if age_max < 14:
        await message.answer("Либо не меньше 14, либо <b>без лимита</b>")
        return
    if age_min > age_max:
        await message.answer("Верхняя граница не может быть меньше нижней, поправь")
        return
    user_id = data.get("user_id")
    looking_for_gender = data.get("settings_looking_for_gender")
    if not user_id or not isinstance(looking_for_gender, str):
        await state.clear()
        await message.answer("Сбилось что-то, начни заново: /settings")
        return
    prefs = await user_client.update_preferences(user_id, looking_for_gender, age_min, age_max)
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
