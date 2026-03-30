from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from dependencies import user_client
from keyboards import main_menu_keyboard
from profile_ui import send_profile_content


async def allow_main_menu(state: FSMContext) -> bool:
    st = await state.get_state()
    if st is None:
        return True
    name = str(st)
    return not (name.startswith("RegistrationStates:") or name.startswith("EditStates:"))


async def require_profile_for_inline_edit(cb: CallbackQuery) -> dict | None:
    if cb.from_user is None:
        await cb.answer("Не вижу пользователя")
        return None
    user = await user_client.get_user(cb.from_user.id)
    if user is None:
        await cb.message.answer("Сначала нажми /start")
        await cb.answer()
        return None
    profile = await user_client.get_profile_by_user(user["id"])
    if profile is None:
        await cb.message.answer(
            "<b>Анкеты уже нет.</b> <i>"
            "Отправь /start и собери анкету заново.</i>",
            reply_markup=main_menu_keyboard(),
        )
        await cb.answer()
        return None
    return profile


async def update_current_profile(message: Message, updates: dict) -> bool:
    tg_user = message.from_user
    if tg_user is None:
        return False
    user = await user_client.get_user(tg_user.id)
    if user is None:
        return False
    profile = await user_client.get_profile_by_user(user["id"])
    if profile is None:
        await message.answer(
            "<b>Анкеты нет.</b> <i>Отправь /start и пройди анкету заново.</i>",
            reply_markup=main_menu_keyboard(),
        )
        return False
    updated = await user_client.update_profile(profile["id"], updates)
    await message.answer("<b>Ок</b>, <i>записал</i>.")
    await send_profile_content(message, updated)
    await message.answer("\u2060", reply_markup=main_menu_keyboard())
    return True
