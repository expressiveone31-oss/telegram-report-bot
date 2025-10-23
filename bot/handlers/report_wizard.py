from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command
import re

router = Router()


class ReportFSM(StatesGroup):
    title = State()
    period = State()
    links = State()
    planned = State()
    actual = State()
    mediaplan = State()
    organic_links = State()
    organic_reach = State()
    screenshots = State()
    confirm = State()


def parse_int(text: str) -> int:
    """Возвращает целое число, очищая пробелы, запятые и прочие символы."""
    digits = re.sub(r"[^\d]", "", text or "")
    if not digits:
        raise ValueError("no digits")
    return int(digits)


@router.message(Command("new_report"))
async def start_report(msg: types.Message, state: FSMContext):
    await state.set_state(ReportFSM.title)
    await msg.answer("Название проекта или недели (например: Кинопоиск_Кибердеревня_Главная Яндекса):")


@router.message(ReportFSM.title)
async def step_title(msg: types.Message, state: FSMContext):
    await state.update_data(title=msg.text)
    await msg.answer("Период проекта (например: 14–20 октября):")
    await state.set_state(ReportFSM.period)


@router.message(ReportFSM.period)
async def step_period(msg: types.Message, state: FSMContext):
    await state.update_data(period=msg.text)
    await msg.answer("Ссылки на публикации (через Enter):")
    await state.set_state(ReportFSM.links)


@router.message(ReportFSM.links)
async def step_links(msg: types.Message, state: FSMContext):
    await state.update_data(links=msg.text)
    await msg.answer("Плановый охват (число):")
    await state.set_state(ReportFSM.planned)


@router.message(ReportFSM.planned)
async def step_planned(msg: types.Message, state: FSMContext):
    try:
        planned = parse_int(msg.text)
    except Exception:
        await msg.answer("Пожалуйста, введи число (например, 1233500). Можно с пробелами.")
        return
    await state.update_data(planned=planned)
    await msg.answer("Фактический охват (число):")
    await state.set_state(ReportFSM.actual)


@router.message(ReportFSM.actual)
async def step_actual(msg: types.Message, state: FSMContext):
    try:
        actual = parse_int(msg.text)
    except Exception:
        await msg.answer("Пожалуйста, введи число (например, 1199200). Можно с пробелами.")
        return
    await state.update_data(actual=actual)
    await msg.answer("Ссылка на медиаплан (Google Sheets):")
    await state.set_state(ReportFSM.mediaplan)


@router.message(ReportFSM.mediaplan)
async def step_mediaplan(msg: types.Message, state: FSMContext):
    await state.update_data(mediaplan=msg.text)
    await msg.answer("Ссылки на органические публикации (если есть):")
    await state.set_state(ReportFSM.organic_links)


@router.message(ReportFSM.organic_links)
async def step_organic_links(msg: types.Message, state: FSMContext):
    await state.update_data(organic_links=msg.text)
    await msg.answer("Органический охват (число, если есть):")
    await state.set_state(ReportFSM.organic_reach)


@router.message(ReportFSM.organic_reach)
async def step_organic_reach(msg: types.Message, state: FSMContext):
    try:
        organic = parse_int(msg.text)
    except Exception:
        await msg.answer("Пожалуйста, введи число (например, 98541). Можно с пробелами.")
        return

    await state.update_data(organic_reach=organic)
    await msg.answer("Отправь скриншоты (можно альбомом). Когда закончишь — напиши «Готово».")
    await state.set_state(ReportFSM.screenshots)


@router.message(ReportFSM.screenshots, F.photo)
async def step_screenshots(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(msg.photo[-1].file_id)
    await state.update_data(photos=photos)


@router.message(ReportFSM.screenshots, F.text.lower() == "готово")
async def step_done(msg: types.Message, state: FSMContext):
    data = await state.get_data()

    title = data.get("title", "")
    period = data.get("period", "")
    planned = data.get("planned", 0)
    actual = data.get("actual", 0)
    mediaplan = data.get("mediaplan", "")
    organic_links = data.get("organic_links", "")
    organic_reach = data.get("organic_reach", 0)
    photos = data.get("photos", [])

    diff = actual - planned
    over = f"(+{diff:,})" if diff > 0 else f"({diff:,})"

    text = (
        f"<b>Отчёт по проекту:</b> {title}\n"
        f"<b>Период:</b> {period}\n\n"
        f"<b>Плановый охват:</b> {planned:,}\n"
        f"<b>Фактический охват:</b> {actual:,} {over}\n"
        f"<b>Медиаплан:</b> {mediaplan}\n\n"
        f"<b>Органические ссылки:</b>\n{organic_links}\n"
        f"<b>Органический охват:</b> {organic_reach:,}\n"
    )

    await msg.answer(text)
    if photos:
        media = [types.InputMediaPhoto(p) for p in photos]
        await msg.answer_media_group(media)

    await msg.answer("✅ Отчёт собран!")
    await state.clear()
