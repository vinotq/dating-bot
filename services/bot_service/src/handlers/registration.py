import html
from typing import Optional
from uuid import UUID

import httpx
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from constants import GENDER_TO_API
from dependencies import user_client
from keyboards import (
    BTN_BACK,
    BTN_RESET,
    BTN_SKIP,
    BTN_START_SURVEY,
    back_keyboard,
    back_skip_keyboard,
    gender_keyboard,
    main_menu_keyboard,
    start_only_keyboard,
)
from profile_ui import send_profile_card
from states import RegistrationStates

router = Router()


async def _reg_answer(message: Message, text: str, **kwargs) -> Message:
    return await message.answer(text, **kwargs)


async def _restart(message: Message, state: FSMContext) -> None:
    from handlers.profile import start_command

    await state.clear()
    await message.answer("Начнём сначала", reply_markup=start_only_keyboard())
    await start_command(message, state)


@router.message(RegistrationStates.waiting_name)
async def registration_name(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.clear()
        await message.answer("Регистрация отменена", reply_markup=start_only_keyboard())
        return
    if message.text == BTN_RESET:
        await _restart(message, state)
        return
    if (message.text or "").strip() == BTN_START_SURVEY:
        await _reg_answer(
            message,
            "Это кнопка меню — <b>напиши своё имя</b> текстом.",
            parse_mode=ParseMode.HTML,
        )
        return
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 100:
        await _reg_answer(
            message,
            "Твое имя слишком короткое или слишком длинное, попробуй ещё раз",
        )
        return
    await state.update_data(name=name)
    await state.set_state(RegistrationStates.waiting_age)
    await _reg_answer(message, "Сколько тебе полных лет?", reply_markup=back_keyboard())


@router.message(RegistrationStates.waiting_age)
async def registration_age(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(RegistrationStates.waiting_name)
        await _reg_answer(message, "Как тебя зовут?", reply_markup=back_keyboard())
        return
    if message.text == BTN_RESET:
        await _restart(message, state)
        return
    age_text = (message.text or "").strip()
    if not age_text.isdigit():
        await _reg_answer(
            message,
            "Нужно целое число полных лет.",
        )
        return
    age = int(age_text)
    if age < 14:
        await _reg_answer(
            message,
            "В анкете указываем возраст <b>от 14 лет</b> — напиши своё число.",
            parse_mode=ParseMode.HTML,
        )
        return
    await state.update_data(age=age)
    await state.set_state(RegistrationStates.waiting_gender)
    await _reg_answer(
        message,
        "Твой пол — выбери из пунктов ниже",
        reply_markup=gender_keyboard(),
    )


@router.message(RegistrationStates.waiting_gender)
async def registration_gender(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(RegistrationStates.waiting_age)
        await _reg_answer(message, "Сколько тебе полных лет?", reply_markup=back_keyboard())
        return
    if message.text == BTN_RESET:
        await _restart(message, state)
        return
    gender_raw = (message.text or "").strip().lower()
    if gender_raw not in GENDER_TO_API:
        await _reg_answer(
            message,
            "Выбери один из пунктов ниже: мужской, женский или не скажу",
        )
        return
    await state.update_data(gender=GENDER_TO_API[gender_raw])
    await state.set_state(RegistrationStates.waiting_city)
    await _reg_answer(
        message,
        "Откуда ты? Город напиши текстом",
        reply_markup=back_keyboard(),
    )


@router.message(RegistrationStates.waiting_city)
async def registration_city(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(RegistrationStates.waiting_gender)
        await _reg_answer(
            message,
            "Твой пол — нажми кнопку ниже",
            reply_markup=gender_keyboard(),
        )
        return
    if message.text == BTN_RESET:
        await _restart(message, state)
        return
    city = (message.text or "").strip()
    if not city or len(city) > 100:
        await _reg_answer(
            message,
            "Название твоего города слишком длинное, попробуй ещё раз",
        )
        return
    await state.update_data(city=city)
    await state.set_state(RegistrationStates.waiting_interests)
    await _reg_answer(
        message,
        "Чем увлекаешься? Через запятую, хотя бы один пункт",
        reply_markup=back_keyboard(),
    )


@router.message(RegistrationStates.waiting_interests)
async def registration_interests(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(RegistrationStates.waiting_city)
        await _reg_answer(
            message,
            "Откуда ты? Город напиши текстом",
            reply_markup=back_keyboard(),
        )
        return
    if message.text == BTN_RESET:
        await _restart(message, state)
        return
    raw = (message.text or "").strip()
    interests = [item.strip().lower() for item in raw.split(",") if item.strip()]
    unique = list(dict.fromkeys(interests))
    if not unique:
        await _reg_answer(
            message,
            "Хотя-бы один интерес, иначе нечего показывать в профиле",
        )
        return
    await state.update_data(interests=unique)
    await state.set_state(RegistrationStates.waiting_bio)
    await _reg_answer(
        message,
        "Можешь написать о себе пару строк или нажми <i>Пропустить</i>",
        reply_markup=back_skip_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("skip"), RegistrationStates.waiting_bio)
async def registration_bio_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(bio=None)
    await state.set_state(RegistrationStates.waiting_photo)
    await _reg_answer(
        message,
        "Кинь фото для анкеты или нажми <i>Пропустить</i> — без фото тоже можно",
        reply_markup=back_skip_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(RegistrationStates.waiting_bio)
async def registration_bio(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(RegistrationStates.waiting_interests)
        await _reg_answer(
            message,
            "Чем увлекаешься? Через запятую, хотя бы один пункт",
            reply_markup=back_keyboard(),
        )
        return
    if message.text == BTN_SKIP:
        await state.update_data(bio=None)
        await state.set_state(RegistrationStates.waiting_photo)
        await _reg_answer(
            message,
            "Кинь фото для анкеты или нажми <i>Пропустить</i> — без фото тоже можно",
            reply_markup=back_skip_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    if message.text == BTN_RESET:
        await _restart(message, state)
        return
    bio = (message.text or "").strip()
    if len(bio) > 500:
        await _reg_answer(
            message,
            "Ничего себе ты много про себя написал, но этого многовато, укороти чуть-чуть",
        )
        return
    await state.update_data(bio=bio or None)
    await state.set_state(RegistrationStates.waiting_photo)
    await _reg_answer(
        message,
        "Кинь фото для анкеты или нажми <i>Пропустить</i> — без фото тоже можно",
        reply_markup=back_skip_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("skip"), RegistrationStates.waiting_photo)
async def registration_photo_skip(message: Message, state: FSMContext) -> None:
    await _finish_registration(message, state, None)


@router.message(RegistrationStates.waiting_photo, F.photo)
async def registration_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    largest = message.photo[-1]
    file = await bot.get_file(largest.file_id)
    data = await bot.download_file(file.file_path)
    content = data.read()
    await _finish_registration(message, state, content)


@router.message(RegistrationStates.waiting_photo)
async def registration_photo_invalid(message: Message, state: FSMContext) -> None:
    if message.text == BTN_BACK:
        await state.set_state(RegistrationStates.waiting_bio)
        await _reg_answer(
            message,
            "Можешь написать о себе пару строк или нажми <i>Пропустить</i>",
            reply_markup=back_skip_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return
    if message.text == BTN_SKIP:
        await _finish_registration(message, state, None)
        return
    if message.text == BTN_RESET:
        await _restart(message, state)
        return
    await _reg_answer(
        message,
        "Нужна картинка или нажимай <i>Пропустить</i>",
        parse_mode=ParseMode.HTML,
    )


def _profile_create_payload(data: dict) -> dict:
    raw_uid = data["user_id"]
    user_id = str(UUID(str(raw_uid)))
    return {
        "user_id": user_id,
        "name": data["name"],
        "age": data["age"],
        "gender": data["gender"],
        "city": data["city"],
        "bio": data.get("bio"),
        "looking_for_gender": "any",
        "age_min": 14,
        "age_max": -1,
    }


def _http_error_hint(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:
        return (response.text or "")[:400]
    detail = body.get("detail") if isinstance(body, dict) else None
    if detail is None:
        return str(body)[:400]
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict) and "msg" in item:
                parts.append(str(item["msg"]))
            else:
                parts.append(str(item))
        return "; ".join(parts)[:400]
    return str(detail)[:400]


async def _finish_registration(
    message: Message, state: FSMContext, photo_content: Optional[bytes]
) -> None:
    data = await state.get_data()
    user_id_str = str(UUID(str(data["user_id"])))
    try:
        profile = await user_client.create_profile(_profile_create_payload(data))
        interests_from_api = await user_client.list_interests()
        by_name = {item["name"].lower(): item["id"] for item in interests_from_api}
        interest_ids: list[int] = []
        for interest_name in data["interests"]:
            if interest_name not in by_name:
                created = await user_client.create_interest(interest_name)
                by_name[interest_name] = created["id"]
            interest_ids.append(by_name[interest_name])
        await user_client.set_user_interests(user_id_str, interest_ids)
        if photo_content:
            await user_client.upload_profile_photo(profile["id"], photo_content, "profile.jpg")
        updated_profile = await user_client.get_profile_by_user(user_id_str)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        hint = _http_error_hint(e.response)
        if code == 409:
            await state.clear()
            await message.answer(
                "<b>Анкета уже есть</b> у этого аккаунта — <i>открой «Мой профиль».</i>",
                reply_markup=main_menu_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return
        safe = html.escape(hint) if hint else ""
        text = (
            "<b>Не удалось сохранить анкету</b> на сервере."
            if not safe
            else f"<b>Не удалось сохранить анкету.</b>\n<i>{safe}</i>"
        )
        await _reg_answer(message, text, parse_mode=ParseMode.HTML)
        return
    await state.clear()
    m_done = await message.answer(
        "<b>Всё, анкета готова!</b>",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    if updated_profile:
        await send_profile_card(message, updated_profile, first_menu_message=m_done)
    else:
        await message.answer(
            "<b>Анкета сохранена</b>, но карточку не удалось показать — "
            "<i>нажми «Мой профиль».</i>",
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )
