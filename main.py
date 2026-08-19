import asyncio
import os
import threading

import database as db
from app import app as flask_app
from bot import main as bot_main


def run_web():
    db.init_db()
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    # Sayt (Flask) fon rejimida (thread) ishlaydi — Render shu portni talab qiladi
    threading.Thread(target=run_web, daemon=True).start()
    # Bot asosiy jarayonda ishlaydi
    asyncio.run(bot_main())
