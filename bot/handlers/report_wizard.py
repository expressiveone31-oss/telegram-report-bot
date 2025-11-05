from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import re

from bot.utils.formatting import format_report_html, chunk_text

router = Router()


# --- FSM ---

class ReportFSM(StatesGroup):
    title = State()
    period = State()
    posts_links = State()      # ссылки на вышедшие публикации (label — url | url)
    planned = State()
    actual = State()
    mediaplan = State()
    organic_links = State()    # органические публикации (label — url | url)
    organic_reach = State()
    screenshots = State()
    confirm = State()


# --- helpers ---

def parse_int(text: str) -> int:
    """
    Извлекаем число из строки: убираем пробелы, неразрывные пробелы, запятые и прочее.
    '1 233 500' → 1233500
    """
    digits = re.sub(r"[^\d]", "", text or "")
    if not digits:
        raise ValueError("no digits")
    return int(digits)


def _split_lines(raw: str) -> list[str]:
    """Разбиваем многострочный ввод на строки, фильтруем пустые."""
    return [ln.strip() for ln in (raw or "").splitlines() if ln.strip()]


# --- commands ---

@router.message(Command("new_report"))
async def start_report(msg: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(ReportFSM.title)
    await msg.answer(
        "Название проекта или недели (например: <i>Кинопоиск_Кибердеревня_Главная Яндекса</i>):"
    )


@router.message(Command("cancel"))
async def cancel_report(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Ок, ввод отменён. Чтобы начать заново — /new_report")


# --- steps ---

@router.message(ReportFSM.title)
async def step_title(msg: types.Message, state: FSMContext):
    await state.update_data(title=msg.text.strip())
    await state.set_state(ReportFSM.period)
    await msg.answer("Период проекта (например: <i>14–20 октября</i>):")


@router.message(ReportFSM.period)
async def step_period(msg: types.Message, state: FSMContext):
    await state.update_data(period=msg.text.strip())
    await state.set_state(ReportFSM.posts_links)
    await msg.answer(
        "Ссылки на вышедшие публикации (каждую с новой строки).\n"
        "Можно так:  <b>lady_zmei — https://t.me/lady_zmei/123</b>\n"
        "Или просто ссылкой:  <b>https://t.me/lady_zmei/123</b>"
    )


@router.message(ReportFSM.posts_links)
async def step_posts_links(msg: types.Message, state: FSMContext):
    await state.update_data(posts_links=msg.text)
    await state.set_state(ReportFSM.planned)
    await msg.answer("Планируемый охват (число):")


@router.message(ReportFSM.planned)
async def step_planned(msg: types.Message, state: FSMContext):
    try:
        planned = parse_int(msg.text)
    except Exception:
        await msg.answer("Пожалуйста, введи число (например, 1233500). Можно с пробелами.")
        return
    await state.update_data(planned=planned)
    await state.set_state(ReportFSM.actual)
    await msg.answer("Фактический охват (число):")


@router.message(ReportFSM.actual)
async def step_actual(msg: types.Message, state: FSMContext):
    try:
        actual = parse_int(msg.text)
    except Exception:
        await msg.answer("Пожалуйста, введи число (например, 1199200). Можно с пробелами.")
        return
    await state.update_data(actual=actual)
    await state.set_state(ReportFSM.mediaplan)
    await msg.answer("Ссылка на медиаплан (Google Sheets):")


@router.message(ReportFSM.mediaplan)
async def step_mediaplan(msg: types.Message, state: FSMContext):
    await state.update_data(mediaplan=msg.text.strip())
    await state.set_state(ReportFSM.organic_links)
    await msg.answer(
        "Органические публикации (каждую с новой строки, формат как выше: "
        "<b>label — url</b> или просто <b>url</b>). Если нет — отправь «-»."
    )


@router.message(ReportFSM.organic_links)
async def step_organic_links(msg: types.Message, state: FSMContext):
    raw = (msg.text or "").strip()
    await state.update_data(organic_links=(" " if raw == "-" else raw))
    await state.set_state(ReportFSM.organic_reach)
    await msg.answer("Органический охват (число, если есть; если нет — 0):")


@router.message(ReportFSM.organic_reach)
async def step_organic_reach(msg: types.Message, state: FSMContext):
    try:
        organic = parse_int(msg.text)
    except Exception:
        await msg.answer("Пожалуйста, введи число (например, 98541). Можно с пробелами. Если нет — 0.")
        return

    await state.update_data(organic_reach=organic)
    await state.set_state(ReportFSM.screenshots)
    await msg.answer("Отправь скриншоты (можно альбомом). Когда закончишь — напиши «Готово».")


@router.message(ReportFSM.screenshots, F.photo)
async def step_screenshots_collect(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(msg.photo[-1].file_id)
    await state.update_data(photos=photos)


@router.message(ReportFSM.screenshots, F.text.lower() == "готово")
async def step_screenshots_done(msg: types.Message, state: FSMContext):
    data = await state.get_data()

    title = data.get("title", "")
    period = data.get("period", "")
    posts_links_raw = data.get("posts_links", "")
    planned = int(data.get("planned", 0))
    actual = int(data.get("actual", 0))
    mediaplan = data.get("mediaplan", "")
    organic_links_raw = data.get("organic_links", "")
    organic = int(data.get("organic_reach", 0))
    photos = data.get("photos", [])

    posts_links_list = _split_lines(posts_links_raw)
    organic_links_list = _split_lines(organic_links_raw)

    # расчёты
    total = actual + organic
    growth_pct = 0.0
    if planned > 0:
        growth_pct = round((actual - planned) * 100.0 / planned)

    # итоговый текст «как в PDF»
    text = format_report_html(
        title=title,
        period=period,
        posts_links=posts_links_list,
        planned=planned,
        actual=actual,
        organic=organic,
        total=total,
        mediaplan=mediaplan,
        screenshots_folder_url=None,   # можно добавить отдельным шагом при желании
        growth_pct=growth_pct,
        organic_links=organic_links_list,
    )

    # Telegram ограничивает длину сообщения → режем на части аккуратно
    for part in chunk_text(text, 3500):
        await msg.answer(part)

    if photos:
        media = [types.InputMediaPhoto(p) for p in photos]
        await msg.answer_media_group(media)

    await msg.answer("✅ Отчёт собран!")
    await state.clear()
