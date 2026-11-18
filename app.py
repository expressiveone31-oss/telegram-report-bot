import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import ErrorEvent

from bot.config import BOT_TOKEN
from bot.handlers.report_wizard import router as report_router
from bot.handlers.start import router as start_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def _health_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        # Read only the request headers. Waiting for EOF deadlocks: the client
        # keeps the connection open until it receives the response.
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 4096:
            chunk = await asyncio.wait_for(reader.read(1024), timeout=5)
            if not chunk:
                break
            data += chunk
        body = b"ok"
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 2\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            + body
        )
        await writer.drain()
    except Exception:
        log.exception("healthcheck request failed")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def start_health_server() -> asyncio.AbstractServer | None:
    """Railway kills a service that has a healthcheck and never binds $PORT."""
    raw = os.getenv("PORT", "").strip()
    if not raw:
        return None
    server = await asyncio.start_server(_health_client, "0.0.0.0", int(raw))
    log.info("Health server listening on port %s", raw)
    return server


def setup_dispatcher() -> Dispatcher:
    # SimpleEventIsolation serializes updates per user, so an album of screenshots
    # cannot overwrite its own photo list.
    dp = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    dp.include_router(start_router)
    dp.include_router(report_router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> None:
        log.error("Handler failed: %s", event.exception, exc_info=event.exception)
        message = event.update.message or event.update.edited_message
        if message is None:
            return
        try:
            await message.answer(
                "Не получилось обработать сообщение. Напиши /cancel и начни с /new_report."
            )
        except Exception:
            log.exception("Failed to send error notice")

    return dp


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Add it as an environment variable.")

    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = setup_dispatcher()
    health = await start_health_server()
    try:
        # aiogram 3.10 does not drop a previously set webhook. While a webhook
        # is active, getUpdates fails and the bot stays silent.
        await bot.delete_webhook(drop_pending_updates=False)
        me = await bot.get_me()
        log.info("Bot is starting polling as @%s", me.username)
        await dp.start_polling(bot)
    finally:
        if health is not None:
            health.close()
            await health.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
