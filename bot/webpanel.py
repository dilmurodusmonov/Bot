import base64
import hmac
from datetime import datetime, timezone

from aiohttp import web

from bot.config import ADMIN_PASSWORD, ADMIN_USERNAME
from bot.database import get_recent_donations, get_stats
from bot.texts import CATEGORIES, category_name, status_label

STATUS_ORDER = ("available", "reserved", "shipped", "received")


def _check_auth(request: web.Request) -> bool:
    if not ADMIN_PASSWORD:
        return False

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False

    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, _, password = decoded.partition(":")
    except Exception:
        return False

    return hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(
        password, ADMIN_PASSWORD
    )


def _unauthorized() -> web.Response:
    return web.Response(
        status=401,
        headers={"WWW-Authenticate": 'Basic realm="Ehson admin panel"'},
        text="Kirish taqiqlangan. Login va parol kerak.",
    )


async def dashboard_handler(request: web.Request) -> web.Response:
    if not _check_auth(request):
        return _unauthorized()

    stats = await get_stats()
    recent = await get_recent_donations(10)
    html = _render_dashboard(stats, recent)
    return web.Response(text=html, content_type="text/html")


def _bar(label: str, count: int, max_count: int) -> str:
    width = round((count / max_count) * 100) if max_count else 0
    return f"""
    <div class="bar-row">
      <div class="bar-label">{label}</div>
      <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
      <div class="bar-count">{count}</div>
    </div>
    """


def _recent_row(donation: dict) -> str:
    created = donation["created_at"].strftime("%Y-%m-%d %H:%M")
    desc = donation["description"] or ""
    if len(desc) > 60:
        desc = desc[:57] + "..."
    return f"""
    <tr>
      <td>#{donation['id']}</td>
      <td>{category_name(donation['category'], 'uz')}</td>
      <td class="desc">{desc}</td>
      <td><span class="pill pill-{donation['status']}">{status_label(donation['status'], 'uz')}</span></td>
      <td class="muted">{created}</td>
    </tr>
    """


def _render_dashboard(stats: dict, recent: list) -> str:
    by_status = stats.get("donations_by_status", {})
    by_category = stats.get("donations_by_category", {})

    max_status = max(by_status.values(), default=0)
    max_category = max(by_category.values(), default=0)

    status_bars = "".join(
        _bar(status_label(s, "uz"), by_status.get(s, 0), max_status) for s in STATUS_ORDER
    )
    category_bars = "".join(
        _bar(category_name(c, "uz"), by_category.get(c, 0), max_category) for c in CATEGORIES
    )

    recent_rows = "".join(_recent_row(d) for d in recent) or (
        '<tr><td colspan="5" class="muted empty">Hozircha ehsonlar yo\'q.</td></tr>'
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ehson bot — Admin panel</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: #0E1420;
    color: #E8EDF2;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    padding: 32px 20px 60px;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  header {{ display: flex; align-items: center; gap: 14px; margin-bottom: 28px; }}
  .avatar {{
    width: 46px; height: 46px; border-radius: 50%;
    background: linear-gradient(135deg,#FF9A5C,#E5484D);
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 700; font-size: 17px; flex-shrink: 0;
  }}
  h1 {{ font-size: 20px; margin: 0; }}
  .subtitle {{ color: #7C8A99; font-size: 13px; margin-top: 2px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 28px; }}
  .card {{ background: #171E27; border-radius: 16px; padding: 18px 20px; }}
  .card .value {{ font-size: 30px; font-weight: 700; }}
  .card .label {{ color: #7C8A99; font-size: 13.5px; margin-top: 4px; }}
  .card .sub {{ color: #9AA7B3; font-size: 12.5px; margin-top: 8px; }}
  section {{ background: #171E27; border-radius: 16px; padding: 20px 22px; margin-bottom: 20px; }}
  section h2 {{ font-size: 15.5px; margin: 0 0 16px; color: #F2F5F8; }}
  .bar-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
  .bar-label {{ width: 150px; font-size: 13.5px; color: #C7D0D9; flex-shrink: 0; }}
  .bar-track {{ flex: 1; background: #232B36; border-radius: 6px; height: 10px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: linear-gradient(90deg,#FF9A5C,#E5484D); border-radius: 6px; }}
  .bar-count {{ width: 30px; text-align: right; font-size: 13px; color: #9AA7B3; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  th {{ text-align: left; color: #7C8A99; font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; padding: 0 10px 10px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }}
  td {{ padding: 10px 10px 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); vertical-align: top; }}
  td.desc {{ color: #C7D0D9; }}
  td.muted {{ color: #7C8A99; }}
  td.empty {{ text-align: center; padding: 24px 0; }}
  .pill {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; background: #232B36; color: #C7D0D9; }}
  .pill-available {{ color: #9AA7B3; }}
  .pill-reserved {{ color: #FFB454; }}
  .pill-shipped {{ color: #4EA4F5; }}
  .pill-received {{ color: #3FCF7F; }}
  footer {{ text-align: center; color: #5B6670; font-size: 12px; margin-top: 30px; }}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="avatar">EB</div>
    <div>
      <h1>Ehson bot — Admin panel</h1>
      <div class="subtitle">Statistika, oxirgi holat</div>
    </div>
  </header>

  <div class="cards">
    <div class="card">
      <div class="value">{stats.get('total_users', 0)}</div>
      <div class="label">Jami foydalanuvchilar</div>
      <div class="sub">🤲 {stats.get('total_donors', 0)} Saxiy · 🙏 {stats.get('total_needy', 0)} Muhtoj</div>
    </div>
    <div class="card">
      <div class="value">{stats.get('total_donations', 0)}</div>
      <div class="label">Jami joylangan ehsonlar</div>
    </div>
    <div class="card">
      <div class="value">{stats.get('completed_donations', 0)}</div>
      <div class="label">Muvaffaqiyatli yetib borgan</div>
    </div>
  </div>

  <section>
    <h2>Status bo'yicha</h2>
    {status_bars}
  </section>

  <section>
    <h2>Bo'lim bo'yicha</h2>
    {category_bars}
  </section>

  <section>
    <h2>Oxirgi ehsonlar</h2>
    <table>
      <thead>
        <tr><th>ID</th><th>Bo'lim</th><th>Tavsif</th><th>Status</th><th>Sana</th></tr>
      </thead>
      <tbody>
        {recent_rows}
      </tbody>
    </table>
  </section>

  <footer>Yangilangan: {now} · sahifani yangilash uchun qayta oching</footer>
</div>
</body>
</html>
"""
