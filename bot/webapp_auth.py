import hashlib
import hmac
import json
from typing import Any, Optional
from urllib.parse import parse_qsl

from bot.config import BOT_TOKEN


def validate_init_data(init_data: str) -> Optional[dict[str, Any]]:
    """Telegram Mini App'dan kelgan initData'ni tekshiradi.

    To'g'ri bo'lsa, ichidagi foydalanuvchi ma'lumotini (dict) qaytaradi;
    imzo mos kelmasa yoki format buzilgan bo'lsa None qaytaradi.
    Algoritm: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not init_data:
        return None

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    user_raw = pairs.get("user")
    if not user_raw:
        return None

    try:
        return json.loads(user_raw)
    except json.JSONDecodeError:
        return None
