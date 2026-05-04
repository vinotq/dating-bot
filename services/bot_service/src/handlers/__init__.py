from aiogram import Router

from handlers.common import router as common_router
from handlers.help import router as help_router
from handlers.profile import router as profile_router
from handlers.registration import router as registration_router
from handlers.edit import router as edit_router
from handlers.photos import router as photos_router
from handlers.settings import router as settings_router
from handlers.search import router as search_router
from handlers.chat import router as chat_router

router = Router()
router.include_router(common_router)
router.include_router(help_router)
router.include_router(chat_router)
router.include_router(search_router)
router.include_router(profile_router)
router.include_router(registration_router)
router.include_router(edit_router)
router.include_router(photos_router)
router.include_router(settings_router)
