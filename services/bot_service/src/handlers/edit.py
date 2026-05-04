from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import ReplyKeyboardRemove

from dependencies import user_client
from handlers.common import require_profile_for_inline_edit, update_current_profile
from handlers.settings import start_settings_wizard
from keyboards import main_menu_keyboard
from profile_ui import send_profile_content
from states import EditStates

router = Router()


async def _edit_prompt(
    cb: CallbackQuery, text: str, state: FSMContext, next_state
) -> None:
    await state.set_state(next_state)
    await cb.message.answer(
        text,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "edit_name")
async def edit_name(cb: CallbackQuery, state: FSMContext) -> None:
    if await require_profile_for_inline_edit(cb) is None:
        return
    await _edit_prompt(
        cb,
        "<b>Имя</b> — <i>напиши, как тебя записать</i>.",
        state,
        EditStates.waiting_name,
    )
    await cb.answer()


@router.callback_query(F.data == "edit_age")
async def edit_age(cb: CallbackQuery, state: FSMContext) -> None:
    if await require_profile_for_inline_edit(cb) is None:
        return
    await _edit_prompt(
        cb,
        "<b>Сколько тебе полных лет?</b>",
        state,
        EditStates.waiting_age,
    )
    await cb.answer()


@router.callback_query(F.data == "edit_city")
async def edit_city(cb: CallbackQuery, state: FSMContext) -> None:
    if await require_profile_for_inline_edit(cb) is None:
        return
    await _edit_prompt(
        cb,
        "<b>Город</b> — <i>где ты сейчас живешь?</i>",
        state,
        EditStates.waiting_city,
    )
    await cb.answer()


@router.callback_query(F.data == "edit_bio")
async def edit_bio(cb: CallbackQuery, state: FSMContext) -> None:
    if await require_profile_for_inline_edit(cb) is None:
        return
    await _edit_prompt(
        cb,
        "<b>О себе</b> — <i>как тебе комфортно, напиши пару строк</i>.",
        state,
        EditStates.waiting_bio,
    )
    await cb.answer()


@router.callback_query(F.data == "edit_preferences")
async def edit_preferences(cb: CallbackQuery, state: FSMContext) -> None:
    if await require_profile_for_inline_edit(cb) is None:
        return
    if cb.from_user is None:
        await cb.answer()
        return
    await cb.answer()
    await start_settings_wizard(cb.message, state, telegram_id=cb.from_user.id)


@router.message(EditStates.waiting_name)
async def edit_name_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Твое имя слишком короткое, попробуй ещё раз")
        return
    if len(text) > 100:
        await message.answer("Твое имя слишком длинное, попробуй что-нибудь покороче")
        return
    await update_current_profile(message, {"name": text})
    await state.clear()


@router.message(EditStates.waiting_age)
async def edit_age_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужно целое число полных лет.")
        return
    age = int(text)
    if age < 14:
        await message.answer(
            "Сколько тебе лет? У нас можно регистрироваться только с 14 лет."
        )
        return
    await update_current_profile(message, {"age": age})
    await state.clear()


@router.message(EditStates.waiting_city)
async def edit_city_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > 100:
        await message.answer("Название твоего города слишком длинное, попробуй ещё раз")
        return
    await update_current_profile(message, {"city": text})
    await state.clear()


@router.message(EditStates.waiting_bio)
async def edit_bio_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) > 500:
        await message.answer(
            "Ничего себе ты много про себя написал, но этого многовато, укороти чуть-чуть"
        )
        return
    await update_current_profile(message, {"bio": text})
    await state.clear()


@router.callback_query(F.data == "edit_interests")
async def edit_interests(cb: CallbackQuery, state: FSMContext) -> None:
    if await require_profile_for_inline_edit(cb) is None:
        return
    await _edit_prompt(
        cb,
        "<b>Интересы</b> — <i>перечисли через запятую</i>.",
        state,
        EditStates.waiting_interests,
    )
    await cb.answer()


@router.message(EditStates.waiting_interests)
async def edit_interests_input(message: Message, state: FSMContext) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    raw = (message.text or "").strip()
    interests = [item.strip().lower() for item in raw.split(",") if item.strip()]
    unique = list(dict.fromkeys(interests))
    if not unique:
        await message.answer("Хотя бы один интерес — перечисли через запятую")
        return
    user = await user_client.get_user(tg_user.id)
    if user is None:
        return
    interests_from_api = await user_client.list_interests()
    by_name = {item["name"].lower(): item["id"] for item in interests_from_api}
    interest_ids: list[int] = []
    for name in unique:
        if name not in by_name:
            created = await user_client.create_interest(name)
            by_name[name] = created["id"]
        interest_ids.append(by_name[name])
    await user_client.set_user_interests(str(user["id"]), interest_ids)
    profile = await user_client.get_profile_by_user(str(user["id"]))
    if profile:
        await send_profile_content(message, profile)
    await message.answer("⁠", reply_markup=main_menu_keyboard())
    await state.clear()
