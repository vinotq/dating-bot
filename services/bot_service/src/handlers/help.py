from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards import BTN_MAIN_HELP
from profile_ui import send_help
from handlers.common import allow_main_menu, send_busy_message

router = Router()


@router.message(Command("help"))
async def help_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_help(message)


@router.message(F.text == BTN_MAIN_HELP)
async def menu_help(message: Message, state: FSMContext) -> None:
    if not await allow_main_menu(state):
        await send_busy_message(message)
        return
    await state.clear()
    await send_help(message)


@router.callback_query(F.data.startswith("help:"))
async def help_nav(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.message is None:
        await cb.answer()
        return
    await cb.answer()
    action = (cb.data or "").split(":")[-1]
    if action == "search":
        from handlers.search import _start_search
        from aiogram import Bot

        bot: Bot = cb.bot  # type: ignore[assignment]
        await _start_search(cb.message, bot)
    elif action == "profile":
        from profile_ui import show_profile

        await show_profile(cb.message)
    elif action == "matches":
        from handlers.search import _show_matches

        await _show_matches(cb.message)
    elif action == "settings":
        from handlers.settings import start_settings_wizard

        await start_settings_wizard(
            cb.message, state, telegram_id=cb.from_user.id if cb.from_user else None
        )
