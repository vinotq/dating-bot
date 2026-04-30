from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

BTN_MAIN_PROFILE = "Мой профиль"
BTN_MAIN_HELP = "Помощь"
BTN_MAIN_SEARCH = "Смотреть анкеты"
BTN_MAIN_MATCHES = "Мои мэтчи"
BTN_START_SURVEY = "Запустить анкету"
BTN_BACK = "Назад"
BTN_SKIP = "Пропустить"
BTN_RESET = "Начать заново"

MAIN_MENU_TEXTS = frozenset(
    {
        BTN_MAIN_PROFILE,
        BTN_MAIN_HELP,
        BTN_MAIN_SEARCH,
        BTN_MAIN_MATCHES,
    }
)


def gender_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")],
            [KeyboardButton(text="Не скажу")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_BACK)]],
        resize_keyboard=True,
    )


def back_skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_SKIP)],
        ],
        resize_keyboard=True,
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_MAIN_SEARCH), KeyboardButton(text=BTN_MAIN_PROFILE)],
            [KeyboardButton(text=BTN_MAIN_MATCHES), KeyboardButton(text=BTN_MAIN_HELP)],
        ],
        resize_keyboard=True,
    )


def matches_keyboard(items: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """items: list of (button_text, partner_user_id)."""
    builder = InlineKeyboardBuilder()
    for text, partner_id in items:
        safe_text = text[:64]
        builder.button(text=safe_text, callback_data=f"match:open:{partner_id}")
    builder.adjust(1)
    return builder.as_markup()


def swipe_keyboard(swiped_user_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Лайк", callback_data=f"sw:like:{swiped_user_id}")
    builder.button(text="👎 Пропустить", callback_data=f"sw:skip:{swiped_user_id}")
    builder.adjust(2)
    return builder.as_markup()


def start_only_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_START_SURVEY)]],
        resize_keyboard=True,
    )


def registration_in_progress_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BACK)],
            [KeyboardButton(text=BTN_RESET)],
        ],
        resize_keyboard=True,
    )


def profile_edit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Поменять имя", callback_data="edit_name")
    builder.button(text="Поменять возраст", callback_data="edit_age")
    builder.button(text="Поменять город", callback_data="edit_city")
    builder.button(text="Поменять «о себе»", callback_data="edit_bio")
    builder.button(text="Добавить фото", callback_data="edit_photo")
    builder.button(text="Порядок и удаление фото", callback_data="manage_photos")
    builder.button(text="Настройки предпочтений", callback_data="edit_preferences")
    builder.button(text="Удалить анкету", callback_data="delete_profile")
    builder.adjust(1)
    return builder.as_markup()


def manage_photos_inline_keyboard(photo_count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(photo_count):
        n = i + 1
        builder.row(
            InlineKeyboardButton(text=f"{n} ↑", callback_data=f"ph:{i}:up"),
            InlineKeyboardButton(text=f"{n} ↓", callback_data=f"ph:{i}:dn"),
            InlineKeyboardButton(text=f"{n} x", callback_data=f"ph:{i}:rm"),
        )
    builder.row(InlineKeyboardButton(text="Готово", callback_data="ph:done"))
    return builder.as_markup()
