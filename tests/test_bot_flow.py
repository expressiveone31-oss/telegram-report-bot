import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app import setup_dispatcher, start_health_server
from bot.handlers.report_wizard import (
    ReportFSM,
    cancel_report,
    is_done_text,
    send_photos,
    step_screenshots_done,
    step_title,
)
from bot.handlers.start import start
from bot.utils.formatting import format_report_html


def _message(text=None):
    return SimpleNamespace(
        text=text,
        answer=AsyncMock(),
        answer_photo=AsyncMock(),
        answer_media_group=AsyncMock(),
        from_user=SimpleNamespace(id=1),
    )


class ReportFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        storage = MemoryStorage()
        key = StorageKey(bot_id=1, chat_id=1, user_id=1)
        self.state = FSMContext(storage=storage, key=key)

    def test_done_text_accepts_punctuation(self):
        self.assertTrue(is_done_text("Готово"))
        self.assertTrue(is_done_text(" готово. "))
        self.assertTrue(is_done_text("ГОТОВО!"))
        self.assertFalse(is_done_text("готово пожалуйста"))
        self.assertFalse(is_done_text(None))

    def test_report_html_escapes_user_text_and_sheet_urls(self):
        html = format_report_html(
            title="Проект <тест> & ко",
            period="1–2",
            posts_links=["lady — https://t.me/lady_zmei/1?a=1&b=2"],
            planned=1000,
            actual=1200,
            organic=0,
            total=1200,
            mediaplan="https://docs.google.com/spreadsheets/d/abc/edit?usp=sharing&ouid=1",
            screenshots_folder_url=None,
            growth_pct=20,
            organic_links=["https://t.me/x/2?q=1&x=2"],
        )
        self.assertIn("Проект &lt;тест&gt; &amp; ко", html)
        self.assertIn("&amp;ouid=1", html)
        self.assertIn("&amp;b=2", html)
        self.assertNotIn("<тест>", html)
        self.assertNotIn("&ouid", html)
        self.assertNotIn("&b=2", html)

    async def test_non_text_does_not_crash_the_step(self):
        await self.state.set_state(ReportFSM.title)
        msg = _message(text=None)
        await step_title(msg, self.state)
        self.assertEqual(await self.state.get_state(), ReportFSM.title.state)
        msg.answer.assert_awaited()

    async def test_start_and_cancel_clear_the_wizard(self):
        await self.state.set_state(ReportFSM.screenshots)
        await start(_message("/start"), self.state)
        self.assertIsNone(await self.state.get_state())

        await self.state.set_state(ReportFSM.screenshots)
        await cancel_report(_message("/cancel"), self.state)
        self.assertIsNone(await self.state.get_state())

    async def test_single_photo_report_is_sent_and_state_cleared(self):
        await self.state.set_state(ReportFSM.screenshots)
        await self.state.update_data(
            title="Проект <тест>",
            period="14–20 октября",
            posts_links="lady — https://t.me/lady_zmei/1",
            planned=1000,
            actual=1500,
            mediaplan="https://docs.google.com/spreadsheets/d/abc/edit?usp=sharing&ouid=1",
            organic_links="-",
            organic_reach=0,
            photos=["file-1"],
        )
        msg = _message("Готово!")
        await step_screenshots_done(msg, self.state)

        texts = [call.args[0] for call in msg.answer.await_args_list]
        self.assertTrue(any("&amp;ouid=1" in part for part in texts))
        self.assertTrue(any("&lt;тест&gt;" in part for part in texts))
        self.assertIn("✅ Отчёт собран!", texts)
        msg.answer_photo.assert_awaited_once_with("file-1")
        msg.answer_media_group.assert_not_awaited()
        self.assertIsNone(await self.state.get_state())

    async def test_photo_batches_respect_telegram_album_limits(self):
        msg = _message()
        await send_photos(msg, [f"p{i}" for i in range(11)])
        msg.answer_media_group.assert_awaited_once()
        album = msg.answer_media_group.await_args.args[0]
        self.assertEqual(len(album), 10)
        msg.answer_photo.assert_awaited_once_with("p10")

    async def test_dispatcher_builds_and_health_port_answers(self):
        dp = setup_dispatcher()
        self.assertGreaterEqual(len(dp.sub_routers), 2)

        server = None
        previous = os.environ.get("PORT")
        os.environ["PORT"] = "8765"
        try:
            server = await start_health_server()
            reader, writer = await asyncio.open_connection("127.0.0.1", 8765)
            writer.write(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            await writer.drain()
            data = await asyncio.wait_for(reader.read(1024), timeout=2)
            writer.close()
            await writer.wait_closed()
            self.assertIn(b"200 OK", data)
            self.assertTrue(data.rstrip().endswith(b"ok"))
        finally:
            if server is not None:
                server.close()
                await server.wait_closed()
            if previous is None:
                os.environ.pop("PORT", None)
            else:
                os.environ["PORT"] = previous


if __name__ == "__main__":
    unittest.main()
