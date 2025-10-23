import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()

def _parse_admins(raw: str) -> set[int]:
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            pass
    return ids

ADMIN_IDS: set[int] = _parse_admins(ADMIN_IDS_RAW)

# Telegram limits
MAX_MESSAGE_LEN = 4096
MAX_ALBUM_PHOTOS = 10
