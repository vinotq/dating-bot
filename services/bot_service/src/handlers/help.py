from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards import BTN_MAIN_HELP
from profile_ui import send_help
from handlers.common import allow_main_menu

router = Router()


@router.message(Command("help"))
async def help_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_help(message)


@router.message(F.text == BTN_MAIN_HELP)
async def menu_help(message: Message, state: FSMContext) -> None:
    if not await allow_main_menu(state):
        await message.answer("<b>Погоди</b> — <i>сначала ответь на вопрос выше.</i>")
        return
    await state.clear()
    await send_help(message)
