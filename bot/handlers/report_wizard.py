# bot/handlers/report_wizard.py
from __future__ import annotations

import re
from typing import List, Optional

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.utils.formatting import (
    format_report_html,
    chunk_text,
)

from bot.integrations.resolver import enrich_links_with_resolver  # обогащаем ТОЛЬКО платные посты

router = Router(name=__name__)


# -----------------------
# FSM
# -----------------------

class ReportFSM(StatesGroup):
    title = State()
    period = State()
    posts_links = State()
    planned = State()
    actual = State()
    mediaplan = State()
    screenshots = State()        # ← НОВЫЙ ШАГ
    organic_links = State()
    done = State()


# -----------------------
# Helpers
# -----------------------

def _split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]

def _parse_int(s: str) -> int:
    s = (s or "").strip()
    s = s.replace(" ", "").replace("\u00A0", "")
    # убрать запятые/точки-разделители
    s = re.sub(r"[,_\.](?=\d{3}\b)", "", s)
    return int(re.sub(r"[^\d\-]", "", s or "0"))

# -----------------------
# Start / Cancel
# -----------------------

@router.message(Command("cancel"))
async def cmd_cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Окей, всё отменил. Чтобы начать заново — набери /new_report")

@router.message(Command("new_report"))
async def cmd_new_report(msg: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(ReportFSM.title)
    await msg.answer(
        "Название проекта или недели (например: <i>Кинопоиск — мемы</i>):",
        parse_mode="HTML"
    )

# -----------------------
# Steps
# -----------------------

@router.message(ReportFSM.title)
async def step_title(msg: types.Message, state: FSMContext):
    await state.update_data(title=msg.text.strip())
    await state.set_state(ReportFSM.period)
    await msg.answer("Период (например: <i>14–20 октября</i>):", parse_mode="HTML")

@router.message(ReportFSM.period)
async def step_period(msg: types.Message, state: FSMContext):
    await state.update_data(period=msg.text.strip())
    await state.set_state(ReportFSM.posts_links)
    await msg.answer(
        "Ссылки на вышедшие публикации (каждая с новой строки).\n"
        "Можно так: <b>Название — https://...</b> или просто ссылкой.",
        parse_mode="HTML"
    )

@router.message(ReportFSM.posts_links)
async def step_posts(msg: types.Message, state: FSMContext):
    await state.update_data(posts_links=msg.text)
    await state.set_state(ReportFSM.planned)
    await msg.answer("Планируемый охват (число, можно с пробелами):")

@router.message(ReportFSM.planned)
async def step_planned(msg: types.Message, state: FSMContext):
    try:
        planned = _parse_int(msg.text)
    except Exception:
        await msg.answer("Не похоже на число. Введи, например: <b>1233500</b>", parse_mode="HTML")
        return
    await state.update_data(planned=planned)
    await state.set_state(ReportFSM.actual)
    await msg.answer("Фактический охват (число, можно с пробелами):")

@router.message(ReportFSM.actual)
async def step_actual(msg: types.Message, state: FSMContext):
    try:
        actual = _parse_int(msg.text)
    except Exception:
        await msg.answer("Не похоже на число. Введи, например: <b>1571600</b>", parse_mode="HTML")
        return
    await state.update_data(actual=actual)
    await state.set_state(ReportFSM.mediaplan)
    await msg.answer(
        "Ссылка на медиаплан (Google Sheets). Если нет — отправь “-”."
    )

@router.message(ReportFSM.mediaplan)
async def step_mediaplan(msg: types.Message, state: FSMContext):
    mp = msg.text.strip()
    await state.update_data(mediaplan=None if mp in {"-", "—", "нет", "Нет"} else mp)
    await state.set_state(ReportFSM.screenshots)
    await msg.answer(
        "Ссылка на папку со <b>скринами</b> (Google Drive/Диск/Облако). Если нет — отправь “-”.",
        parse_mode="HTML"
    )

@router.message(ReportFSM.screenshots)
async def step_screenshots(msg: types.Message, state: FSMContext):
    scr = msg.text.strip()
    await state.update_data(screenshots=None if scr in {"-", "—", "нет", "Нет"} else scr)
    await state.set_state(ReportFSM.organic_links)
    await msg.answer(
        "Органические (виральные) ссылки — просто <b>URL постов</b>, по одной в строке.\n"
        "Мы оставим их как есть, без преобразования в названия каналов.",
        parse_mode="HTML"
    )

@router.message(ReportFSM.organic_links)
async def step_organic(msg: types.Message, state: FSMContext):
    await state.update_data(organic_links=msg.text)
    await _finish_and_send(msg, state)

# -----------------------
# Finish
# -----------------------

async def _finish_and_send(msg: types.Message, state: FSMContext):
    data = await state.get_data()

    title: str = data.get("title") or ""
    period: str = data.get("period") or ""

    posts_links_list: List[str] = _split_lines(data.get("posts_links") or "")
    organic_links_list: List[str] = _split_lines(data.get("organic_links") or "")

    planned: int = int(data.get("planned") or 0)
    actual: int = int(data.get("actual") or 0)
    mediaplan: Optional[str] = data.get("mediaplan")
    screenshots_url: Optional[str] = data.get("screenshots")  # ← будет выведено как «Скрины: …»

    total = actual  # фактически в твоей логике «итого» = фактический + органика? оставим как есть, формула в форматтере
    growth_pct = 0.0
    if planned:
        growth_pct = round((actual - planned) / planned * 100, 2)

    # Обогащаем ТОЛЬКО основной список (платные публикации)
    posts_links_list = await enrich_links_with_resolver(posts_links_list)
    # Органику НЕ трогаем — оставляем как есть (просто URL)

    html = format_report_html(
        title=title,
        period=period,
        posts_links=posts_links_list,
        planned=planned,
        actual=actual,
        organic=0,                         # органический охват ты передаёшь ниже вручную (если нужен — можно добавить шаг)
        total=actual,                      # итог из факта (счёт ведёшь ты — оставляем так, как работало)
        mediaplan=mediaplan or "",
        screenshots_folder_url=screenshots_url,   # ← сюда попадёт ссылка «Скрины»
        growth_pct=growth_pct,
        organic_links=organic_links_list,
    )

    # шлём по частям если длинно
    for part in chunk_text(html, 3500):
        await msg.answer(part, parse_mode="HTML", disable_web_page_preview=True)

    await state.clear()
