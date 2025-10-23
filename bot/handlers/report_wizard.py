from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from typing import List

from bot.config import ADMIN_IDS, MAX_MESSAGE_LEN, MAX_ALBUM_PHOTOS
from bot.utils.formatting import format_report_html, chunk_text

router = Router()

class ReportFSM(StatesGroup):
    title = State()
    period = State()
    posts_links = State()
    planned = State()
    actual = State()
    mediaplan = State()
    organic_links = State()
    organic_reach = State()
    screenshots_mode = State()   # ask: upload photos or give folder url
    screenshots_collect = State()
    screenshots_folder_url = State()
    confirm = State()

@router.message(Command("new_report"))
async def new_report(msg: types.Message, state: FSMContext):
    if ADMIN_IDS and msg.from_user and msg.from_user.id not in ADMIN_IDS:
        await msg.answer("Доступ ограничен. Обратитесь к администратору.")
        return

    await state.set_state(ReportFSM.title)
    await state.update_data(photos=[])
    await msg.answer("Название проекта/недели (например, «Камбэк (3 неделя)»):")

@router.message(ReportFSM.title)
async def step_title(msg: types.Message, state: FSMContext):
    await state.update_data(title=msg.text.strip())
    await state.set_state(ReportFSM.period)
    await msg.answer("Период (например, «12–18 авг 2025»):")

@router.message(ReportFSM.period)
async def step_period(msg: types.Message, state: FSMContext):
    await state.update_data(period=msg.text.strip())
    await state.set_state(ReportFSM.posts_links)
    await msg.answer("Ссылки на вышедшие публикации (каждую с новой строки):")


@router.message(ReportFSM.posts_links)
async def step_posts(msg: types.Message, state: FSMContext):
    links = [l.strip() for l in msg.text.splitlines() if l.strip()]
    await state.update_data(posts_links=links)
    await state.set_state(ReportFSM.planned)
    await msg.answer("Плановый охват (число):")


@router.message(ReportFSM.planned, F.text.regexp(r"^\d[\d\s]*$"))
async def step_planned(msg: types.Message, state: FSMContext):
    planned = int(msg.text.replace(" ", ""))
    await state.update_data(planned=planned)
    await state.set_state(ReportFSM.actual)
    await msg.answer("Фактический охват (число):")


@router.message(ReportFSM.actual, F.text.regexp(r"^\d[\d\s]*$"))
async def step_actual(msg: types.Message, state: FSMContext):
    actual = int(msg.text.replace(" ", ""))
    await state.update_data(actual=actual)
    await state.set_state(ReportFSM.mediaplan)
    await msg.answer("Ссылка на МП (Google Sheets):")


@router.message(ReportFSM.mediaplan)
async def step_mediaplan(msg: types.Message, state: FSMContext):
    await state.update_data(mediaplan=msg.text.strip())
    await state.set_state(ReportFSM.organic_links)
    await msg.answer("Органические публикации (каждую с новой строки). Если нет — отправь «-»:")


@router.message(ReportFSM.organic_links)
async def step_organic_links(msg: types.Message, state: FSMContext):
    text = msg.text.strip()
    organic_links: List[str] = [] if text == "-" else [l.strip() for l in text.splitlines() if l.strip()]
    await state.update_data(organic_links=organic_links)
    await state.set_state(ReportFSM.organic_reach)
    await msg.answer("Органический охват (число, можно 0):")


@router.message(ReportFSM.organic_reach, F.text.regexp(r"^\d[\d\s]*$"))
async def step_organic_reach(msg: types.Message, state: FSMContext):
    organic_reach = int(msg.text.replace(" ", ""))
    await state.update_data(organic_reach=organic_reach)
    await state.set_state(ReportFSM.screenshots_mode)
    await msg.answer(
        "Скриншоты: отправь фото сюда (альбомами до 10) ИЛИ пришли ссылку на папку.\n\n"
        "Если хочешь загружать фото — просто начни присылать изображения.\n"
        "Когда закончишь — отправь слово <b>Готово</b>.\n"
        "Если предпочитаешь ссылку — пришли ссылку текстом.",
        parse_mode="HTML",
    )


@router.message(ReportFSM.screenshots_mode, F.photo)
async def collect_photo_first(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(msg.photo[-1].file_id)
    await state.update_data(photos=photos)
    await state.set_state(ReportFSM.screenshots_collect)
    await msg.answer("Фото добавлено. Ещё? Когда закончишь — напиши «Готово»." )


@router.message(ReportFSM.screenshots_collect, F.photo)
async def collect_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(msg.photo[-1].file_id)
    await state.update_data(photos=photos)


@router.message(ReportFSM.screenshots_collect, F.text.lower().in_({"готово", "done", "ok"}))
async def photos_done(msg: types.Message, state: FSMContext):
    await state.set_state(ReportFSM.confirm)
    data = await state.get_data()
    planned = data["planned"]
    actual = data["actual"]
    organic = data["organic_reach"]
    growth_pct = round((actual / planned - 1) * 100, 1) if planned else 0.0
    total = actual + organic
    photos_count = len(data.get("photos", []))

    preview = (
        f"<b>{data['title']}</b>\n"
        f"Период: {data['period']}\n\n"
        f"Плановый охват: {planned:,}".replace(","," ") + "\n"
        f"Фактический охват: {actual:,}".replace(","," ") + f" (на {growth_pct}% выше плана)\n"
        f"Органический охват: {organic:,}".replace(","," ") + "\n"
        f"<b>Итого:</b> {total:,}".replace(","," ") + "\n\n"
        f"Скриншотов: {photos_count} шт.\n"
        f"МП: {data['mediaplan']}\n"
        f"Постов: {len(data['posts_links'])} | Органики: {len(data['organic_links'])}\n\n"
        f"Сгенерировать отчёт? (Да/Нет)"
    )
    await msg.answer(preview, parse_mode="HTML")


@router.message(ReportFSM.screenshots_mode, F.text)
async def screenshots_folder_url(msg: types.Message, state: FSMContext):
    # user sent a link instead of photos
    await state.update_data(screenshots_folder_url=msg.text.strip())
    await state.set_state(ReportFSM.confirm)

    data = await state.get_data()
    planned = data["planned"]
    actual = data["actual"]
    organic = data["organic_reach"]
    growth_pct = round((actual / planned - 1) * 100, 1) if planned else 0.0
    total = actual + organic

    preview = (
        f"<b>{data['title']}</b>\n"
        f"Период: {data['period']}\n\n"
        f"Плановый охват: {planned:,}".replace(","," ") + "\n"
        f"Фактический охват: {actual:,}".replace(","," ") + f" (на {growth_pct}% выше плана)\n"
        f"Органический охват: {organic:,}".replace(","," ") + "\n"
        f"<b>Итого:</b> {total:,}".replace(","," ") + "\n\n"
        f"Скрины: {msg.text.strip()}\n"
        f"МП: {data['mediaplan']}\n"
        f"Постов: {len(data['posts_links'])} | Органики: {len(data['organic_links'])}\n\n"
        f"Сгенерировать отчёт? (Да/Нет)"
    )
    await msg.answer(preview, parse_mode="HTML")


@router.message(ReportFSM.confirm, F.text.lower().in_({"да", "yes", "y"}))
async def confirm_yes(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    planned = data["planned"]
    actual = data["actual"]
    organic = data["organic_reach"]
    growth_pct = round((actual / planned - 1) * 100, 1) if planned else 0.0
    total = actual + organic

    report_html = format_report_html(
        title=data["title"],
        period=data["period"],
        posts_links=data["posts_links"],
        planned=planned,
        actual=actual,
        organic=organic,
        total=total,
        mediaplan=data["mediaplan"],
        screenshots_folder_url=data.get("screenshots_folder_url"),
        growth_pct=growth_pct,
        organic_links=data["organic_links"],
    )

    chunks = chunk_text(report_html, MAX_MESSAGE_LEN)
    for chunk in chunks:
        await msg.answer(chunk, parse_mode="HTML", disable_web_page_preview=True)

    # Send photos (albums of up to 10)
    photos = data.get("photos", [])
    if photos:
        # split into batches of MAX_ALBUM_PHOTOS
        for i in range(0, len(photos), MAX_ALBUM_PHOTOS):
            batch = photos[i:i+MAX_ALBUM_PHOTOS]
            media = [types.InputMediaPhoto(media=file_id) for file_id in batch]
            await msg.answer_media_group(media)

    await state.clear()


@router.message(ReportFSM.confirm)
async def confirm_other(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Ок, отменил. Начнём заново командой /new_report")


# Fallback handlers to catch wrong input for numeric steps
@router.message(ReportFSM.planned)
async def planned_invalid(msg: types.Message, state: FSMContext):
    await msg.answer("Пожалуйста, введи число (например, 925000).")


@router.message(ReportFSM.actual)
async def actual_invalid(msg: types.Message, state: FSMContext):
    await msg.answer("Пожалуйста, введи число (например, 1199200).")


@router.message(ReportFSM.organic_reach)
async def organic_invalid(msg: types.Message, state: FSMContext):
    await msg.answer("Пожалуйста, введи число (например, 98541).")

