import os
import sqlite3
import logging
import asyncio
import httpx
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils.exceptions import Throttled
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from datetime import datetime, date

# ======= CONFIGURATION ==========
BOT_TOKEN = os.getenv("BOT_TOKEN") or "7788390714:AAFAnRw6HlPeZGHIFWhY_KsVLLm26dzFMW0"
SUPER_VIP_IDS = [int(os.getenv("SUPER_VIP_ID") or 1669843747)]
# ================================

# Logging setup
logging.basicConfig(level=logging.INFO, filename="bot.log", format='%(asctime)s - %(levelname)s - %(message)s')

# Init bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Database
DB_FILE = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            vip INTEGER DEFAULT 0,
            last_used TEXT
        )
    ''')
    conn.commit()
    conn.close()

def set_vip(user_id: int, vip_status: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, vip) VALUES (?, ?)", (user_id, vip_status))
    conn.commit()
    conn.close()

def remove_vip(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET vip=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def is_vip(user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT vip FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res and res[0] == 1

def update_usage(user_id: int, date_str: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (user_id, last_used) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET last_used=excluded.last_used
    ''', (user_id, date_str))
    conn.commit()
    conn.close()

def get_last_usage(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT last_used FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

# Cooldown middleware
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit=1):
        super().__init__()
        self.rate_limit = limit
        self.user_times = {}

    async def on_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        now = asyncio.get_event_loop().time()
        if now - self.user_times.get(user_id, 0) < self.rate_limit:
            raise Throttled(message, rate=self.rate_limit)
        self.user_times[user_id] = now

dp.middleware.setup(ThrottlingMiddleware(limit=1))

def can_use(user_id: int) -> bool:
    if user_id in SUPER_VIP_IDS or is_vip(user_id):
        return True
    last = get_last_usage(user_id)
    if not last:
        return True
    return datetime.strptime(last, "%Y-%m-%d").date() < date.today()

def set_used_today(user_id: int):
    update_usage(user_id, date.today().strftime("%Y-%m-%d"))

async def fetch_terabox_video(link: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(link)
        if response.status_code == 200:
            # Your actual video URL parsing logic here
            return f"Fetched video URL for: {link}"
        else:
            raise Exception(f"Failed to fetch video, status code: {response.status_code}")

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Welcome to the Terabox Video Downloader Bot!\n\n"
        "Send me a Terabox video link and I'll fetch the video for you.\n"
        "⚠️ Non-VIP users can download/view only once per day.\n"
        "VIPs have unlimited access.\n\nUse /help to see commands."
    )

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await message.answer(
        "🤖 *Commands:*\n"
        "/start - Welcome\n"
        "/help - Help\n"
        "/vip_add <user_id> - Add VIP (Super VIP only)\n"
        "/vip_remove <user_id> - Remove VIP (Super VIP only)\n"
        "/vip_list - Show VIPs (Super VIP only)\n"
        "/stats - Your usage stats",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=['vip_add'])
async def cmd_vip_add(message: types.Message):
    if message.from_user.id not in SUPER_VIP_IDS:
        return await message.reply("❌ Not authorized.")
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("Usage: /vip_add <user_id>")
    set_vip(int(parts[1]), 1)
    await message.reply(f"✅ User {parts[1]} is now VIP.")

@dp.message_handler(commands=['vip_remove'])
async def cmd_vip_remove(message: types.Message):
    if message.from_user.id not in SUPER_VIP_IDS:
        return await message.reply("❌ Not authorized.")
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("Usage: /vip_remove <user_id>")
    remove_vip(int(parts[1]))
    await message.reply(f"✅ VIP removed from user {parts[1]}.")

@dp.message_handler(commands=['vip_list'])
async def cmd_vip_list(message: types.Message):
    if message.from_user.id not in SUPER_VIP_IDS:
        return await message.reply("❌ Not authorized.")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE vip=1")
    vips = c.fetchall()
    conn.close()
    text = "👑 VIP Users:\n" + "\n".join(str(uid[0]) for uid in vips) if vips else "No VIPs found."
    await message.reply(text)

@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    uid = message.from_user.id
    vip = "Yes" if uid in SUPER_VIP_IDS or is_vip(uid) else "No"
    last = get_last_usage(uid) or "Never"
    await message.reply(f"📊 Your Stats:\nID: {uid}\nVIP: {vip}\nLast Used: {last}")

@dp.message_handler()
async def handle_links(message: types.Message):
    uid = message.from_user.id
    txt = message.text.strip()

    if "terabox.com" not in txt:
        return await message.reply("⚠️ Send a valid Terabox link.")

    if not can_use(uid):
        return await message.reply("🚫 Daily limit reached. Contact admin for VIP access.")

    try:
        url = await fetch_terabox_video(txt)
    except Exception as e:
        logging.error(f"Fetch error for {uid}: {e}")
        return await message.reply("❌ Failed to fetch video. Try again later.")

    if uid not in SUPER_VIP_IDS and not is_vip(uid):
        set_used_today(uid)

    await message.reply(f"✅ Video fetched:\n{url}")

if __name__ == '__main__':
    print("Starting bot...")
    init_db()
    executor.start_polling(dp, skip_updates=True)
