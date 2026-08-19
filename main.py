import asyncio
import os
import threading
import time
import urllib.request

import database as db
from app import app as flask_app
from bot import main as bot_main


def run_web():
    db.init_db()
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)


def keep_alive():
    """Render bepul rejasi uxlab qolmasligi uchun o'ziga davriy so'rov yuboradi."""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    while True:
        time.sleep(600)  # har 10 daqiqada
        try:
            urllib.request.urlopen(url, timeout=10)
        except Exception:
            pass


if __name__ == "__main__":
    # Sayt (Flask) fon rejimida (thread) ishlaydi — Render shu portni talab qiladi
    threading.Thread(target=run_web, daemon=True).start()
    # O'z-o'zini uyg'oq ushlab turish (UptimeRobot shart emas)
    threading.Thread(target=keep_alive, daemon=True).start()
    # Bot asosiy jarayonda ishlaydi
    asyncio.run(bot_main())
