import html

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from dependencies import matching_client, user_client, clear_unread
from keyboards import BTN_CHAT_CLOSE, BTN_MAIN_INVITE, chat_keyboard, main_menu_keyboard
from states import ChatState

router = Router()


def _format_history(msgs: list[dict], my_id: str, partner_name: str = "Партнёр") -> str:
    if not msgs:
        return ""
    lines = []
    safe_partner = html.escape(partner_name)
    for m in msgs:
        prefix = "Вы" if str(m["sender_id"]) == my_id else safe_partner
        body = html.escape(m["body"][:100])
        lines.append(f"<b>{prefix}:</b> {body}")
    return "\n".join(lines) + "\n\n"


@router.callback_query(F.data == "chat:more")
async def load_more_history(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return
    data = await state.get_data()
    match_id = data.get("match_id")
    user_id = data.get("user_id")
    partner_name = data.get("partner_name") or "Партнёр"
    offset = int(data.get("history_offset") or 0)
    if not match_id or not user_id or offset == 0:
        await cb.answer("Это все сообщения")
        return
    try:
        msgs = await matching_client.get_messages(match_id)
    except httpx.HTTPError:
        await cb.answer("Не удалось загрузить — попробуй позже", show_alert=True)
        return
    page_size = 10
    new_offset = max(0, offset - page_size)
    await state.update_data(history_offset=new_offset)
    chunk = msgs[new_offset:offset]
    history = _format_history(chunk, user_id, partner_name)
    buttons = [[InlineKeyboardButton(text="Закрыть чат", callback_data="chat:close")]]
    if new_offset > 0:
        buttons.insert(
            0, [InlineKeyboardButton(text="⬆️ Загрузить ещё", callback_data="chat:more")]
        )
    await cb.message.answer(
        f"<i>— более ранние сообщения —</i>\n\n{history}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("chat:open:"))
async def open_chat(cb: CallbackQuery, state: FSMContext) -> None:
    if cb.from_user is None or cb.message is None:
        await cb.answer()
        return

    parts = (cb.data or "").split(":")
    if len(parts) != 3:
        await cb.answer()
        return

    match_id = parts[2]

    user = await user_client.get_user(cb.from_user.id)
    if not user:
        await cb.answer("Сначала /start")
        return

    my_id = str(user["id"])

    try:
        matches = await matching_client.get_matches(my_id)
    except httpx.HTTPError:
        matches = []
    match = next((m for m in matches if str(m["id"]) == match_id), None)
    partner_name = "Партнёр"
    if match is not None:
        partner_id = (
            str(match["user2_id"])
            if str(match["user1_id"]) == my_id
            else str(match["user1_id"])
        )
        try:
            profile = await user_client.get_profile_by_user(partner_id)
            if profile and profile.get("name"):
                partner_name = profile["name"]
        except httpx.HTTPError:
            pass

    try:
        msgs = await matching_client.get_messages(match_id)
    except httpx.HTTPError:
        msgs = []

    total = len(msgs)
    page_size = 10
    offset = max(0, total - page_size)

    await state.set_state(ChatState.active)
    await state.update_data(
        match_id=match_id,
        user_id=user["id"],
        history_offset=offset,
        partner_name=partner_name,
    )
    await clear_unread(my_id, match_id)

    history = _format_history(msgs[offset:], my_id, partner_name)
    safe_partner = html.escape(partner_name)

    if offset > 0:
        more_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬆️ Загрузить ещё", callback_data="chat:more"
                    )
                ]
            ]
        )
        await cb.message.answer(
            "<i>— подгрузить более ранние сообщения —</i>",
            parse_mode="HTML",
            reply_markup=more_kb,
        )
    await cb.message.answer(
        f"{history}<i>Напиши сообщение — оно отправится {safe_partner}.\nЧтобы выйти, нажми «{BTN_CHAT_CLOSE}».</i>",
        parse_mode="HTML",
        reply_markup=chat_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "chat:close")
async def close_chat(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if cb.message:
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.message.answer("Чат закрыт.", reply_markup=main_menu_keyboard())
    await cb.answer()


@router.message(ChatState.active, F.text == BTN_CHAT_CLOSE)
async def close_chat_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Чат закрыт.", reply_markup=main_menu_keyboard())


@router.message(ChatState.active, ~F.text)
async def chat_non_text(message: Message) -> None:
    await message.answer(
        "<i>Сейчас в чате поддерживается только текст. Фото и голосовые — пока недоступны.</i>",
        parse_mode="HTML",
    )


@router.message(ChatState.active, F.text)
async def send_chat_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    match_id = data.get("match_id")
    user_id = data.get("user_id")

    if not match_id or not user_id or not message.text:
        return

    try:
        await matching_client.send_message(match_id, user_id, message.text)
    except httpx.HTTPError:
        await message.answer("Ошибка отправки — попробуй снова")


@router.message(F.text == BTN_MAIN_INVITE)
async def invite_button(message: Message) -> None:
    await _send_invite(message)


@router.message(Command("invite"))
async def invite_command(message: Message) -> None:
    await _send_invite(message)


async def _send_invite(message: Message) -> None:
    if message.from_user is None:
        return
    user = await user_client.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала /start")
        return
    try:
        code = await user_client.get_referral_code(user["id"])
    except httpx.HTTPError:
        await message.answer("Не удалось создать ссылку — попробуй позже.")
        return

    from config import settings

    bot_name = settings.bot_username or "dating_bot"
    link = f"https://t.me/{bot_name}?start=ref_{code}"
    await message.answer(
        f"Пригласи друга по ссылке:\n{link}\n\n"
        "<i>За каждого приглашённого, кто заполнит анкету, твой рейтинг вырастет!</i>",
        parse_mode="HTML",
    )
