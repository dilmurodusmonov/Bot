"""Server tezligini o'lchash: har bir API so'rovining davomiyligi xotirada
yig'iladi — admin /ping buyrug'i eng sekin manzillarni ko'rsatadi."""
import time
from collections import defaultdict

STARTED_AT = time.time()

# manzil -> [so'rovlar soni, jami ms, eng uzun ms]
_stats: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])


def record(path: str, ms: float) -> None:
    s = _stats[path]
    s[0] += 1
    s[1] += ms
    s[2] = max(s[2], ms)


def slowest(limit: int = 8) -> list[tuple[str, int, float, float]]:
    """(manzil, soni, o'rtacha ms, eng uzun ms) — o'rtacha vaqt bo'yicha."""
    rows = [(path, int(n), total / n, mx) for path, (n, total, mx) in _stats.items() if n]
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows[:limit]


def reset() -> None:
    _stats.clear()
