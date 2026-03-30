from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import ReplyKeyboardRemove

from handlers.common import require_profile_for_inline_edit, update_current_profile
from handlers.settings import start_settings_wizard
from states import EditStates

router = Router()


async def _edit_prompt(cb: CallbackQuery, text: str, state: FSMContext, next_state) -> None:
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
        await message.answer("Сколько тебе лет? У нас можно регистрироваться только с 14 лет.")
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
        await message.answer("Ничего себе ты много про себя написал, но этого многовато, укороти чуть-чуть")
        return
    await update_current_profile(message, {"bio": text})
    await state.clear()
