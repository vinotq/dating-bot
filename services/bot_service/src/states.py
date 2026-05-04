from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_name = State()
    waiting_age = State()
    waiting_gender = State()
    waiting_city = State()
    waiting_interests = State()
    waiting_looking_for = State()
    waiting_bio = State()
    waiting_photo = State()
    waiting_confirm = State()


class EditStates(StatesGroup):
    waiting_name = State()
    waiting_age = State()
    waiting_city = State()
    waiting_bio = State()
    waiting_interests = State()
    waiting_profile_photo = State()
    managing_photos = State()
    waiting_settings_gender = State()
    waiting_settings_age_min = State()
    waiting_settings_age_max = State()


class ChatState(StatesGroup):
    active = State()
