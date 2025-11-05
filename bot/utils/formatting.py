from typing import List, Tuple, Optional
import re
from urllib.parse import urlparse


# -----------------------
# Helpers
# -----------------------

def chunk_text(text: str, max_len: int) -> list[str]:
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

def parse_labeled_links(lines: List[str]) -> List[Tuple[str, str]]:
    res: List[Tuple[str, str]] = []
    for raw in lines:
        s = (raw or "").strip()
        if not s:
            continue
        m = re.match(r"\[(.+?)\]\((https?://[^\s)]+)\)", s)
        if m:
            res.append((m.group(1).strip(), m.group(2).strip()))
            continue
        m = re.match(r"(.+?)\s*[—\-:]\s*(https?://\S+)", s)
        if m:
            res.append((m.group(1).strip(), m.group(2).strip()))
            continue
        m = re.match(r"(.+?)\s+(https?://\S+)$", s)
        if m and "http" not in m.group(1).lower():
            res.append((m.group(1).strip(), m.group(2).strip()))
            continue
        m = re.search(r"(https?://\S+)", s)
        if m:
            url = m.group(1).strip()
            label = _guess_label_from_url(url)
            res.append((label, url))
            continue
    return res

def _extract_urls(lines: List[str]) -> List[str]:
    urls: List[str] = []
    for raw in lines:
        m = re.search(r"(https?://\S+)", (raw or ""))
        if m:
            urls.append(m.group(1).strip())
    return urls


# -----------------------
# Final report rendering
# -----------------------

def format_report_html(
    title: str,
    period: str,
    posts_links: List[str],
    planned: int,
    actual: int,
    organic: int,
    total: int,
    mediaplan: str,
    screenshots_folder_url: Optional[str],
    growth_pct: float,
    organic_links: List[str],
) -> str:
    growth_str = str(int(growth_pct)) if abs(growth_pct - int(growth_pct)) < 1e-9 else str(growth_pct)

    # платные публикации — кликабельные названия
    posts = parse_labeled_links(posts_links)
    posts_block_lines: list[str] = []
    if posts:
        posts_block_lines.append("<b>Ссылки на вышедшие публикации:</b>")
        for label, url in posts:
            posts_block_lines.append(f"• <a href=\"{url}\">{label}</a>")
        posts_block_lines.append("")

    # органика — ТОЛЬКО ССЫЛКИ (без преобразования в названия)
    organic_lines: list[str] = []
    org_urls = _extract_urls(organic_links)
    if org_urls:
        organic_lines.append(
            "Также по проекту есть органика. Коллеги собрали ссылки на посты, которые вышли органически:"
        )
        for u in org_urls:
            organic_lines.append(f"<a href=\"{u}\">{u}</a>")
        organic_lines.append("")

    lines: list[str] = []
    lines.append(f"<b>Отчёт по проекту:</b>\n{title}")
    if period:
        lines.append(f"<b>Период:</b> {period}")
    lines.append("")

    if posts_block_lines:
        lines.extend(posts_block_lines)

    lines.append(f"<b>Планируемый охват:</b> {_fmt_int(planned)}")
    lines.append(f"<b>Фактический охват:</b> {_fmt_int(actual)}")
    lines.append(f"(Это на {growth_str}% выше планируемого охвата)")
    lines.append("")

    if screenshots_folder_url:
        lines.append(f"<b>Скрины:</b> {screenshots_folder_url}")
    if mediaplan:
        lines.append(f"<b>МП:</b> {mediaplan}")
    if mediaplan or screenshots_folder_url:
        lines.append("")

    if organic_lines:
        lines.extend(organic_lines)

    lines.append(
        f"На данный момент суммарный охват органически вышедших постов: {_fmt_int(organic)} просмотров."
    )
    lines.append(
        "Обращаем внимание, что часть постов вышла совсем недавно. Ожидаем, что эта цифра еще увеличится."
    )
    lines.append("")
    lines.append(f"<b>Итого охват на текущий момент – {_fmt_int(total)} просмотров</b>")

    return "\n".join(lines)
