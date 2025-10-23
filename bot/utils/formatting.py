from typing import List

def chunk_text(text: str, max_len: int) -> list[str]:
    """Split long text into chunks <= max_len, cutting on paragraph boundaries if possible."""
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
                # brutal split long paragraph
                s = p
                while len(s) > max_len:
                    chunks.append(s[:max_len])
                    s = s[max_len:]
                buf = s
    if buf:
        chunks.append(buf)
    return chunks


def format_report_html(
    title: str,
    period: str,
    posts_links: List[str],
    planned: int,
    actual: int,
    organic: int,
    total: int,
    mediaplan: str,
    screenshots_folder_url: str | None,
    growth_pct: float,
    organic_links: List[str],
) -> str:
    def fmt_int(n: int) -> str:
        return f"{n:,}".replace(",", " ")

    lines: list[str] = []
    lines.append(f"<b>{title}</b>")
    if period:
        lines.append(f"<i>Период: {period}</i>")
    lines.append("")
    lines.append("<b>Ссылки на вышедшие публикации:</b>")
    for link in posts_links:
        link = link.strip()
        if not link:
            continue
        # отображаем ссылкой как есть; Telegram превратит в URL
        lines.append(f"• {link}")
    lines.append("")
    lines.append(f"<b>Планируемый охват:</b> {fmt_int(planned)}")
    lines.append(f"<b>Фактический охват:</b> {fmt_int(actual)} (на {growth_pct}% выше плана)")
    if screenshots_folder_url:
        lines.append(f"<b>Скрины:</b> {screenshots_folder_url}")
    lines.append(f"<b>МП:</b> {mediaplan}")
    lines.append("")
    if organic_links:
        lines.append("Также по проекту есть органика. Ссылки на посты, вышедшие органически:")
        for link in organic_links:
            lines.append(f"• {link}")
    lines.append(f"На данный момент суммарный органический охват: {fmt_int(organic)} просмотров.")
    lines.append("Обращаем внимание, что часть постов вышла совсем недавно. Ожидаем рост показателя.")
    lines.append("")
    lines.append(f"<b>Итого охват на текущий момент – {fmt_int(total)} просмотров</b>")

    return "\n".join(lines)
