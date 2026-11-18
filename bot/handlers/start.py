from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from bot.config import ADMIN_IDS

router = Router()


@router.message(CommandStart())
async def start(msg: types.Message, state: FSMContext):
    await state.clear()
    if ADMIN_IDS and msg.from_user and msg.from_user.id not in ADMIN_IDS:
        await msg.answer("Доступ ограничен. Обратитесь к администратору.")
        return
    await msg.answer(
        "Привет! Я соберу данные и пришлю готовый отчёт сообщением.\n\n"
        "Команды:\n"
        "/new_report — создать отчёт\n"
        "/cancel — отменить ввод\n"
    )
