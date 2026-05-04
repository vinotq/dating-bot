import httpx
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, InputMediaPhoto, Message

from dependencies import user_client
from formatters import profile_caption_for_photo
from keyboards import profile_edit_keyboard


def sorted_profile_photos(photos: list[dict]) -> list[dict]:
    return sorted(photos, key=lambda x: (x.get("display_order", 0), str(x["id"])))


async def load_profile_photo_buffers(profile_id: str) -> list[bytes]:
    items = sorted_profile_photos(await user_client.list_profile_photos(profile_id))
    buffers: list[bytes] = []
    for p in items:
        try:
            buffers.append(await user_client.fetch_photo_bytes(profile_id, str(p["id"])))
        except httpx.HTTPError:
            continue
    return buffers


async def send_profile_content(message: Message, profile: dict) -> list[int]:
    profile_id = str(profile["id"])
    buffers = await load_profile_photo_buffers(profile_id)
    caption = profile_caption_for_photo(profile)
    ids: list[int] = []

    if not buffers:
        m = await message.answer(
            caption,
            reply_markup=profile_edit_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        ids.append(m.message_id)
    elif len(buffers) == 1:
        m = await message.answer_photo(
            BufferedInputFile(buffers[0], filename="profile.jpg"),
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=profile_edit_keyboard(),
        )
        ids.append(m.message_id)
    else:
        media: list[InputMediaPhoto] = []
        for i, b in enumerate(buffers):
            part = BufferedInputFile(b, filename=f"p{i}.jpg")
            if i == 0:
                media.append(
                    InputMediaPhoto(media=part, caption=caption, parse_mode=ParseMode.HTML)
                )
            else:
                media.append(InputMediaPhoto(media=part))
        sent = await message.bot.send_media_group(chat_id=message.chat.id, media=media)
        ids.extend(m.message_id for m in sent)
        m2 = await message.answer(
            "Ниже — действия с анкетой:",
            reply_markup=profile_edit_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        ids.append(m2.message_id)

    return ids


async def send_profile_card(
    message: Message,
    profile: dict,
    *,
    first_menu_message: Message | None = None,
) -> None:
    await send_profile_content(message, profile)


async def send_help(message: Message) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Смотреть анкеты", callback_data="help:search"),
         InlineKeyboardButton(text="Мой профиль", callback_data="help:profile")],
        [InlineKeyboardButton(text="Мои мэтчи", callback_data="help:matches"),
         InlineKeyboardButton(text="Настройки", callback_data="help:settings")],
    ])
    await message.answer(
        "<b>Вот что умею</b>\n\n"
        "<b>Смотреть анкеты</b> — <i>лента с лайком и пропуском</i>\n"
        "<b>Мой профиль</b> — <i>карточка, фото, настройки</i>\n"
        "<b>Мои мэтчи</b> — <i>взаимные лайки</i>\n"
        "<b>Настройки</b> — <i>кого показывать, возраст, уведомления</i>",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def show_profile(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await user_client.get_user(tg_user.id)
    if user is None:
        await message.answer(
            "Сначала отправь /start — <i>так мы познакомимся</i>."
        )
        return
    profile = await user_client.get_profile_by_user(user["id"])
    if profile is None:
        await message.answer("Анкеты ещё нет — отправь /start.")
        return
    await send_profile_card(message, profile)
