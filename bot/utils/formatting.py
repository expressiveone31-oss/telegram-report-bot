from typing import List, Tuple, Optional
import re
from urllib.parse import urlparse


# -----------------------
# Helpers
# -----------------------

def chunk_text(text: str, max_len: int) -> list[str]:
    """
    Аккуратно режем длинный текст на части < max_len, стараясь ломать по абзацам.
    Подходит для отправки многострочных сообщений в Telegram.
    """
    if len(text) <= max_len:
        return [text]

    paras = text.split("\n\n")
    chunks: list[str] = []
    buf = ""

    for p in paras:
        add = p if not buf else "\n\n" + p
        if len(buf) + len(add) <= max_len:
            buf += add
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= max_len:
                buf = p
            else:
                # если абзац слишком длинный — нарезаем «как есть»
                s = p
                while len(s) > max_len:
                    chunks.append(s[:max_len])
                    s = s[max_len:]
                buf = s

    if buf:
        chunks.append(buf)
    return chunks


def _fmt_int(n: int) -> str:
    """1234567 -> '1 234 567'"""
    return f"{n:,}".replace(",", " ")


def _guess_label_from_url(u: str) -> str:
    """
    Если пришла только ссылка, делаем «читаемую» метку:
      - t.me/@handle  -> handle
      - instagram.com -> Instagram
      - vk.com        -> VK
      - иначе         -> домен
    """
    try:
        p = urlparse(u)
        host = (p.netloc or "").lower().replace("www.", "")
        path = (p.path or "").strip("/")

        if host == "t.me" and path:
            return path.split("/")[0]
        if "instagram.com" in host:
            return "Instagram"
        if "vk.com" in host:
            return "VK"
        return host or u
    except Exception:
        return u


# -----------------------
# Parsing labeled links
# -----------------------

def parse_labeled_links(lines: List[str]) -> List[Tuple[str, str]]:
    """
    Принимает список строк и извлекает пары (label, url).

    Поддерживаем форматы:
      1) [label](url)
      2) label — url   |  label - url  |  label: url
      3) label <пробелы/таб/nbsp> url
      4) просто url → label из url (t.me/@handle → handle; vk/insta → домен)

    Пример входа:
      "FEMALE MEMES https://vk.com/femalememes"
      "mdk — https://vk.com/mudakoff"
      "[leoday](https://t.me/leoday)"
      "https://t.me/rhymes"
    """
    res: List[Tuple[str, str]] = []

    for raw in lines:
        s = (raw or "").strip()
        if not s:
            continue

        # 1) [label](url)
        m = re.match(r"\[(.+?)\]\((https?://[^\s)]+)\)", s)
        if m:
            res.append((m.group(1).strip(), m.group(2).strip()))
            continue

        # 2) label — url  |  label - url  |  label: url
        m = re.match(r"(.+?)\s*[—\-:]\s*(https?://\S+)", s)
        if m:
            res.append((m.group(1).strip(), m.group(2).strip()))
            continue

        # 3) label <пробелы> url  (не даём сработать, если слева уже есть http)
        m = re.match(r"(.+?)\s+(https?://\S+)$", s)
        if m and "http" not in m.group(1).lower():
            label = m.group(1).strip()
            url = m.group(2).strip()
            res.append((label, url))
            continue

        # 4) просто url
        m = re.search(r"(https?://\S+)", s)
        if m:
            url = m.group(1).strip()
            label = _guess_label_from_url(url)
            res.append((label, url))
            continue

    return res


# -----------------------
# Final report rendering
# -----------------------

def format_report_html(
    title: str,
    period: str,
    posts_links: List[str],        # список строк: "label — url" / "label url" / "url"
    planned: int,
    actual: int,
    organic: int,
    total: int,
    mediaplan: str,
    screenshots_folder_url: Optional[str],
    growth_pct: float,             # на сколько % выше плана
    organic_links: List[str],      # формат как у posts_links
) -> str:
    """
    Формируем отчёт в стиле PDF «Камбэк (3 неделя)» с утверждёнными формулировками:
      - кликабельные названия каналов
      - блоки: ссылки → план/факт (+%) → МП/скрины → органика → итог
    """

    # аккуратный вид процента (без .0)
    growth_str = str(int(growth_pct)) if abs(growth_pct - int(growth_pct)) < 1e-9 else str(growth_pct)

    # публикации
    posts = parse_labeled_links(posts_links)
    posts_block_lines: list[str] = []
    if posts:
        posts_block_lines.append("<b>Ссылки на вышедшие публикации:</b>")
        for label, url in posts:
            posts_block_lines.append(f"• <a href=\"{url}\">{label}</a>")
        posts_block_lines.append("")

    # органика — список ссылок
    organic_items = parse_labeled_links(organic_links)
    organic_lines: list[str] = []
    if organic_items:
        organic_lines.append(
            "Также по проекту есть органика. Коллеги собрали ссылки на посты, которые вышли органически:"
        )
        for label, url in organic_items:
            organic_lines.append(f"• <a href=\"{url}\">{label}</a>")
        organic_lines.append("")
    elif organic_links:
        # если переданы строки без ссылок — выводим как есть
        organic_lines.append(
            "Также по проекту есть органика. Коллеги собрали ссылки на посты, которые вышли органически:"
        )
        for row in organic_links:
            organic_lines.append(f"• {row}")
        organic_lines.append("")

    # тело отчёта
    lines: list[str] = []
    lines.append(f"<b>Отчёт по проекту:</b>\n{title}")
    if period:
        lines.append(f"<b>Период:</b> {period}")
    lines.append("")

    if posts_block_lines:
        lines.extend(posts_block_lines)

    # план/факт и проценты (формулировка №4)
    lines.append(f"<b>Планируемый охват:</b> {_fmt_int(planned)}")
    lines.append(f"<b>Фактический охват:</b> {_fmt_int(actual)}")
    lines.append(f"(Это на {growth_str}% выше планируемого охвата)")
    lines.append("")

    # МП / Скрины
    if mediaplan:
        lines.append(f"<b>Медиаплан:</b> {mediaplan}")
    if screenshots_folder_url:
        lines.append(f"<b>Скрины:</b> {screenshots_folder_url}")
    if mediaplan or screenshots_folder_url:
        lines.append("")

    # органика (формулировки №1–2)
    if organic_lines:
        lines.extend(organic_lines)
    lines.append(
        f"На данный момент суммарный охват органически вышедших постов: {_fmt_int(organic)} просмотров."
    )
    lines.append(
        "Обращаем внимание, что часть постов вышла совсем недавно. Ожидаем, что эта цифра еще увеличится."
    )
    lines.append("")

    # итог (формулировка №3)
    lines.append(f"<b>Итого охват на текущий момент – {_fmt_int(total)} просмотров</b>")

    return "\n".join(lines)
