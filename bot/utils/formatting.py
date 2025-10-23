from typing import List, Tuple
import re
from urllib.parse import urlparse

def chunk_text(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    paras = text.split("\n\n")
    chunks: list[str] = []
    buf = ""
    for p in paras:
        add = (p if not buf else "\n\n" + p)
        if len(buf) + len(add) <= max_len:
            buf += add
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= max_len:
                buf = p
            else:
                s = p
                while len(s) > max_len:
                    chunks.append(s[:max_len])
                    s = s[max_len:]
                buf = s
    if buf:
        chunks.append(buf)
    return chunks


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _guess_label_from_url(u: str) -> str:
    """
    Если пришла только ссылка, делаем «читаемую» метку:
    - для t.me/@handle → handle
    - для instagram.com/* → instagram
    - иначе — домен
    """
    try:
        p = urlparse(u)
        host = (p.netloc or "").lower().replace("www.", "")
        path = (p.path or "").strip("/")
        if host == "t.me" and path:
            # t.me/channel/123 → channel
            return path.split("/")[0]
        if "instagram.com" in host:
            return "Instagram"
        if "vk.com" in host:
            return "VK"
        return host or u
    except Exception:
        return u


def parse_labeled_links(lines: List[str]) -> List[Tuple[str, str]]:
    """
    Принимает список строк и пытается извлечь (label, url).
    Поддерживаем форматы:
      - label — url
      - label - url
      - label: url
      - [label](url)
      - просто url
    Пробелы/эм-дэши/«—» учитываем.
    """
    res: List[Tuple[str, str]] = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue

        # [label](url)
        m = re.match(r"\[(.+?)\]\((https?://[^\s)]+)\)", s)
        if m:
            res.append((m.group(1).strip(), m.group(2).strip()))
            continue

        # label — url (—, -, :)
        m = re.match(r"(.+?)\s*[—\-:]\s*(https?://\S+)", s)
        if m:
            label, url = m.group(1).strip(), m.group(2).strip()
            res.append((label, url))
            continue

        # просто url
        m = re.search(r"(https?://\S+)", s)
        if m:
            url = m.group(1).strip()
            label = _guess_label_from_url(url)
            res.append((label, url))
            continue
    return res


def format_report_html(
    title: str,
    period: str,
    posts_links: List[str],        # строки, каждая «название — ссылка» ИЛИ просто ссылка
    planned: int,
    actual: int,
    organic: int,
    total: int,
    mediaplan: str,
    screenshots_folder_url: str | None,
    growth_pct: float,             # на сколько % выше плана
    organic_links: List[str],      # как и posts_links — свободный формат
) -> str:
    """
    Формируем отчёт в стиле PDF «Камбэк (3 неделя)» с твоими формулировками.
    — кликабельные названия каналов (<a href="...">label</a>)
    — те же текстовые блоки, что ты утвердила
    """
    # аккуратный процент без .0
    if abs(growth_pct - int(growth_pct)) < 1e-9:
        growth_str = str(int(growth_pct))
    else:
        growth_str = str(growth_pct)

    # публикации
    posts = parse_labeled_links(posts_links)
    posts_block_lines: list[str] = []
    if posts:
        posts_block_lines.append("<b>Ссылки на вышедшие публикации:</b>")
        for label, url in posts:
            # кликабельная метка
            posts_block_lines.append(f"• <a href=\"{url}\">{label}</a>")
        posts_block_lines.append("")

    # органика: список ссылок (если передали метки — тоже поддержим)
    organic_items = parse_labeled_links(organic_links)
    organic_lines: list[str] = []
    if organic_items:
        organic_lines.append("Также по проекту есть органика. Коллеги собрали ссылки на посты, которые вышли органически:")
        for label, url in organic_items:
            organic_lines.append(f"• <a href=\"{url}\">{label}</a>")
        organic_lines.append("")
    elif organic_links:
        # вдруг прилетели просто строки без ссылок — покажем как есть
        organic_lines.append("Также по проекту есть органика. Коллеги собрали ссылки на посты, которые вышли органически:")
        for row in organic_links:
            organic_lines.append(f"• {row}")
        organic_lines.append("")

    # основной текст
    lines: list[str] = []
    lines.append(f"<b>Отчёт по проекту:</b>\n{title}")
    if period:
        lines.append(f"<b>Период:</b> {period}")
    lines.append("")

    # блок ссылок на публикации
    if posts_block_lines:
        lines.extend(posts_block_lines)

    # план/факт и проценты
    lines.append(f"<b>Планируемый охват:</b> {_fmt_int(planned)}")
    lines.append(f"<b>Фактический охват:</b> {_fmt_int(actual)}")
    lines.append(f"(Это на {growth_str}% выше планируемого охвата)")
    lines.append("")

    # МП и Скрины (если есть)
    if mediaplan:
        lines.append(f"<b>Медиаплан:</b> {mediaplan}")
    if screenshots_folder_url:
        lines.append(f"<b>Скрины:</b> {screenshots_folder_url}")
    if mediaplan or screenshots_folder_url:
        lines.append("")

    # органика (формулировки 1–2)
    if organic_lines:
        lines.extend(organic_lines)
    lines.append(f"На данный момент суммарный охват органически вышедших постов: {_fmt_int(organic)} просмотров.")
    lines.append("Обращаем внимание, что часть постов вышла совсем недавно. Ожидаем, что эта цифра еще увеличится.")
    lines.append("")

    # Итого (формулировка 3)
    lines.append(f"<b>Итого охват на текущий момент – {_fmt_int(total)} просмотров</b>")

    return "\n".join(lines)
