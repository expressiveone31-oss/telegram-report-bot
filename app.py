import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties  # добавили
from bot.config import BOT_TOKEN
from bot.handlers.start import router as start_router
from bot.handlers.report_wizard import router as report_router

logging.basicConfig(level=logging.INFO)

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Add it as an environment variable.")

    # обновлённая инициализация бота
    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(report_router)

    logging.info("Bot is starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
