from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from dependencies import user_client
from handlers.common import allow_main_menu, send_busy_message
from keyboards import (
    BTN_MAIN_PROFILE,
    BTN_START_SURVEY,
    back_keyboard,
    main_menu_keyboard,
)
from profile_ui import show_profile
from states import RegistrationStates


def _delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, удалить", callback_data="delete_profile_confirm"
                ),
                InlineKeyboardButton(text="Нет", callback_data="delete_profile_cancel"),
            ]
        ]
    )


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

    ref_code: str | None = None
    if message.text and " " in message.text:
        arg = message.text.split(" ", 1)[1].strip()
        if arg.startswith("ref_"):
            ref_code = arg[4:]

    user = await user_client.get_user(tg_user.id)
    if user is None:
        user = await user_client.create_user(
            tg_user.id, tg_user.username, referral_code=ref_code
        )
    elif ref_code:
        await message.answer(
            "<i>Реферальная ссылка не применена — ты уже зарегистрирован.</i>",
            parse_mode="HTML",
        )
    profile = await user_client.get_profile_by_user(user["id"])
    if profile is None:
        await state.update_data(user_id=user["id"])
        await state.set_state(RegistrationStates.waiting_name)
        await message.answer(
            "<b>Привет!</b> Давай соберём анкету — это займёт пару минут.\n\n"
            "<b>Шаг 1 из 8.</b> Как тебя зовут?",
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
    await message.answer(
        "<b>Привет</b>, рад тебя видеть!",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


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
        await send_busy_message(message)
        return
    await state.clear()
    await show_profile(message)


@router.callback_query(F.data == "delete_profile")
async def delete_profile(cb: CallbackQuery) -> None:
    await cb.message.answer(
        "<b>Точно удалить анкету?</b> <i>Это действие нельзя отменить.</i>",
        reply_markup=_delete_confirm_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "delete_profile_confirm")
async def delete_profile_confirm(cb: CallbackQuery, state: FSMContext) -> None:
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
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        "<b>Анкета удалена.</b> Чтобы собрать снова — <i>отправь /start</i>.",
        reply_markup=main_menu_keyboard(),
    )
    await cb.answer("Сделано")


@router.callback_query(F.data == "delete_profile_cancel")
async def delete_profile_cancel(cb: CallbackQuery) -> None:
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("Отменено")
