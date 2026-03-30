from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from dependencies import user_client
from keyboards import (
    BTN_MAIN_PROFILE,
    BTN_START_SURVEY,
    back_keyboard,
    main_menu_keyboard,
    start_only_keyboard,
)
from profile_ui import send_profile_card, show_profile
from states import RegistrationStates
from handlers.common import allow_main_menu

router = Router()


class NoFsmStateFilter(BaseFilter):
    async def __call__(self, _: Message, state: FSMContext) -> bool:
        return await state.get_state() is None


@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext) -> None:
    tg_user = message.from_user
    if tg_user is None:
        await message.answer(
            "Что-то не так с аккаунтом в Telegram — <i>напиши ещё раз</i>."
        )
        return
    await state.clear()
    user = await user_client.get_user(tg_user.id)
    if user is None:
        user = await user_client.create_user(tg_user.id, tg_user.username)
    profile = await user_client.get_profile_by_user(user["id"])
    if profile is None:
        await message.answer(
            "<b>Привет!</b> Давай соберем твою анкету — <i>это займет пару минут</i>.",
            reply_markup=start_only_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        await state.update_data(user_id=user["id"])
        await state.set_state(RegistrationStates.waiting_name)
        await message.answer(
            "<b>Как тебя зовут?</b>",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    if profile["completeness_score"] <= 65:
        await message.answer(
            "<b>Анкета пока неполная.</b> Загляни в <b>профиль</b> "
            "<i>и дополни, когда будет удобно.</i>",
            reply_markup=main_menu_keyboard(),
        )
        return
    m_greet = await message.answer(
        "<b>Привет</b>, рад тебя видеть!",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await send_profile_card(message, profile, first_menu_message=m_greet)


@router.message(F.text == BTN_START_SURVEY, NoFsmStateFilter())
async def start_survey_button(message: Message, state: FSMContext) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await user_client.get_user(tg_user.id)
    if user is None or await user_client.get_profile_by_user(user["id"]) is None:
        await start_command(message, state)
        return
    await message.answer(
        "<b>Анкета уже есть</b> — <i>открой «Мой профиль».</i>",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("profile"))
async def profile_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_profile(message)


@router.message(F.text == BTN_MAIN_PROFILE)
async def menu_profile(message: Message, state: FSMContext) -> None:
    if not await allow_main_menu(state):
        await message.answer("<b>Погоди</b> — <i>сначала ответь на вопрос выше.</i>")
        return
    await state.clear()
    await show_profile(message)


@router.callback_query(F.data == "delete_profile")
async def delete_profile(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.from_user is None:
        await cb.answer("Не вижу твой профиль в чате")
        return
    user = await user_client.get_user(cb.from_user.id)
    if user is None:
        await cb.message.answer("Сначала нажми /start")
        await cb.answer()
        return
    profile = await user_client.get_profile_by_user(user["id"])
    if profile is None:
        await cb.message.answer("У тебя уже нет анкеты")
        await cb.answer()
        return
    await user_client.delete_profile(profile["id"])
    await state.clear()
    await cb.message.answer(
        "<b>Анкета удалена.</b> Чтобы собрать снова — <i>отправь /start</i>.",
        reply_markup=main_menu_keyboard(),
    )
    await cb.answer("Сделано")
