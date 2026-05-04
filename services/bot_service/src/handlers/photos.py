import httpx
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from dependencies import user_client
from keyboards import (
    BTN_BACK,
    back_keyboard,
    main_menu_keyboard,
    manage_photos_inline_keyboard,
)
from profile_ui import send_profile_card, sorted_profile_photos
from states import EditStates
from handlers.common import require_profile_for_inline_edit

router = Router()


def photo_manager_panel_text(photo_count: int) -> str:
    if photo_count == 0:
        return "<b>Фото в анкете</b>\nПока пусто — в меню профиля есть «Добавить фото»."
    return (
        "<b>Фото в анкете</b> (в карточке сверху вниз)\n"
        "У каждого номера: <b>↑</b> выше, <b>↓</b> ниже, <b>x</b> удалить.\n"
        "Закончил — «Готово» или кнопку «Назад» под этим сообщением."
    )


async def refresh_photo_manager_panel(
    bot: Bot, chat_id: int, message_id: int, profile_id: str
) -> None:
    photos = sorted_profile_photos(await user_client.list_profile_photos(profile_id))
    await bot.edit_message_text(
        photo_manager_panel_text(len(photos)),
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=manage_photos_inline_keyboard(len(photos)),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "manage_photos")
async def manage_photos_entry(cb: CallbackQuery, state: FSMContext) -> None:
    profile = await require_profile_for_inline_edit(cb)
    if profile is None:
        return
    await state.set_state(EditStates.managing_photos)
    profile_id = str(profile["id"])
    user_id = str(profile["user_id"])
    photos = sorted_profile_photos(await user_client.list_profile_photos(profile_id))
    await state.update_data(
        manage_photos_profile_id=profile_id,
        manage_photos_user_id=user_id,
    )
    panel = await cb.message.answer(
        photo_manager_panel_text(len(photos)),
        reply_markup=manage_photos_inline_keyboard(len(photos)),
        parse_mode=ParseMode.HTML,
    )
    await state.update_data(manage_photos_panel_message_id=panel.message_id)
    await cb.message.answer(
        "<b>Назад</b> — выйти в профиль.",
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await cb.answer()


@router.callback_query(EditStates.managing_photos, F.data.startswith("ph:"))
async def manage_photos_actions(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    profile_id = data.get("manage_photos_profile_id")
    user_id = data.get("manage_photos_user_id")
    panel_mid = data.get("manage_photos_panel_message_id")
    if not profile_id or not user_id or panel_mid is None:
        await cb.answer("Сессия сброшена — открой снова из профиля", show_alert=True)
        return
    raw = cb.data or ""
    if raw == "ph:done":
        await state.clear()
        profile = await user_client.get_profile_by_user(user_id)
        if profile:
            await send_profile_card(cb.message, profile)
        await cb.answer()
        return
    body = raw.removeprefix("ph:")
    parts = body.split(":")
    if len(parts) != 2:
        await cb.answer()
        return
    idx_s, action = parts
    try:
        index = int(idx_s)
    except ValueError:
        await cb.answer()
        return
    photos = sorted_profile_photos(await user_client.list_profile_photos(profile_id))
    if index < 0 or index >= len(photos):
        return
    ids = [str(p["id"]) for p in photos]
    try:
        if action == "rm":
            await user_client.delete_profile_photo(profile_id, ids[index])
            await cb.answer("Удалено")
        elif action == "up":
            if index == 0:
                await cb.answer("Уже первая в списке")
                return
            ids[index], ids[index - 1] = ids[index - 1], ids[index]
            await user_client.reorder_profile_photos(profile_id, ids)
            await cb.answer("Выше")
        elif action == "dn":
            if index >= len(ids) - 1:
                await cb.answer("Уже последняя в списке")
                return
            ids[index], ids[index + 1] = ids[index + 1], ids[index]
            await user_client.reorder_profile_photos(profile_id, ids)
            await cb.answer("Ниже")
        else:
            await cb.answer()
            return
    except httpx.HTTPError:
        await cb.answer("Не вышло, попробуй ещё раз", show_alert=True)
        return
    try:
        await refresh_photo_manager_panel(
            cb.bot, cb.message.chat.id, panel_mid, profile_id
        )
    except TelegramBadRequest:
        pass


@router.message(EditStates.managing_photos, F.text == BTN_BACK)
async def managing_photos_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    tg = message.from_user
    if tg is None:
        return
    u = await user_client.get_user(tg.id)
    profile = await user_client.get_profile_by_user(u["id"]) if u else None
    if profile:
        await send_profile_card(message, profile)
    else:
        await message.answer("Ок.", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "edit_photo")
async def edit_photo(cb: CallbackQuery, state: FSMContext) -> None:
    profile = await require_profile_for_inline_edit(cb)
    if profile is None:
        return
    await state.set_state(EditStates.waiting_profile_photo)
    await state.update_data(
        photo_edit_profile_id=str(profile["id"]),
        photo_edit_user_id=str(profile["user_id"]),
    )
    await cb.message.answer(
        "<b>Фото</b>\nПришли картинку сообщением. Можно до <b>5</b> фото подряд; "
        "когда закончишь — нажми <b>Назад</b>.",
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await cb.answer()


@router.message(EditStates.waiting_profile_photo, F.photo)
async def edit_profile_photo_save(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    data = await state.get_data()
    profile_id = data.get("photo_edit_profile_id")
    user_id = data.get("photo_edit_user_id")
    if not profile_id or not user_id:
        await state.clear()
        await message.answer(
            "Сбилось что-то — открой профиль и попробуй снова.",
            reply_markup=main_menu_keyboard(),
        )
        return
    photos_now = await user_client.list_profile_photos(profile_id)
    if len(photos_now) >= 5:
        await message.answer(
            "У тебя уже 5 фото — это максимум. Нажимай <b>Назад</b>.",
            parse_mode=ParseMode.HTML,
        )
        return
    largest = message.photo[-1]
    file = await bot.get_file(largest.file_id)
    buf = await bot.download_file(file.file_path)
    content = buf.read()
    try:
        await user_client.upload_profile_photo(profile_id, content, "profile.jpg")
    except httpx.HTTPStatusError as e:
        if e.response is not None and e.response.status_code == 400:
            await message.answer(
                "Не удалось добавить фото (лимит 5 штук). Нажимай <b>Назад</b>.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.answer("Ошибка при загрузке — попробуй ещё раз.")
        return
    updated = await user_client.get_profile_by_user(user_id)
    photos_after = await user_client.list_profile_photos(profile_id)
    if len(photos_after) >= 5:
        await state.clear()
        m_done = await message.answer(
            "<b>Фото сохранено</b>. У тебя уже 5 фото в анкете.",
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        if updated:
            await send_profile_card(message, updated, first_menu_message=m_done)
        return
    await message.answer(
        "<b>Фото добавлено</b>. Можешь прислать ещё одно или нажми <b>Назад</b> для выхода.",
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(EditStates.waiting_profile_photo)
async def edit_profile_photo_invalid(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.clear()
        tg = message.from_user
        if tg is None:
            return
        user = await user_client.get_user(tg.id)
        profile = await user_client.get_profile_by_user(user["id"]) if user else None
        if profile:
            await send_profile_card(message, profile)
        else:
            await message.answer("Ок.", reply_markup=main_menu_keyboard())
        return
    await message.answer("Пришли фото одним сообщением или нажми <b>Назад</b>.")
