import os
import sqlite3
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from datetime import date

# ======= CONFIGURATION ==========
BOT_TOKEN = os.getenv("BOT_TOKEN") or "7950519159:AAFJoYri3SImSjh43E4iXAQtWED0vl1IHhc"
SUPER_VIP_ID = int(os.getenv("SUPER_VIP_ID") or 1669843747)
DOWNLOAD_LIMIT_PER_DAY = 3
# ================================

logging.basicConfig(level=logging.INFO, filename="bot.log", format='%(asctime)s - %(levelname)s - %(message)s')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

DB_FILE = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            vip INTEGER DEFAULT 0,
            last_used TEXT,
            usage_count INTEGER DEFAULT 0
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
    if user_id == SUPER_VIP_ID:
        return True
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT vip FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res and res[0] == 1

def get_usage(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT last_used, usage_count FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    if res:
        return res[0], res[1]
    return None, 0

def update_usage(user_id: int):
    today_str = date.today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    last_used, usage_count = get_usage(user_id)
    if last_used == today_str:
        usage_count += 1
        c.execute("UPDATE users SET usage_count=? WHERE user_id=?", (usage_count, user_id))
    else:
        usage_count = 1
        c.execute("INSERT OR REPLACE INTO users (user_id, last_used, usage_count) VALUES (?, ?, ?)", (user_id, today_str, usage_count))
    conn.commit()
    conn.close()

def can_use(user_id: int) -> bool:
    if user_id == SUPER_VIP_ID or is_vip(user_id):
        return True
    last_used, usage_count = get_usage(user_id)
    today_str = date.today().strftime("%Y-%m-%d")
    if last_used == today_str and usage_count >= DOWNLOAD_LIMIT_PER_DAY:
        return False
    return True

class VIPManage(StatesGroup):
    waiting_for_user_id = State()

admin_buttons = InlineKeyboardMarkup(row_width=2)
admin_buttons.add(
    InlineKeyboardButton("➕ Add VIP", callback_data="vip_add"),
    InlineKeyboardButton("➖ Remove VIP", callback_data="vip_remove"),
    InlineKeyboardButton("📋 VIP List", callback_data="vip_list"),
)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Welcome to the Terabox Video Downloader Bot!\n\n"
        "Send me a Terabox video link and I'll fetch the video for you.\n"
        f"⚠️ Normal users can download up to {DOWNLOAD_LIMIT_PER_DAY} times per day.\n"
        "VIPs have unlimited access.\n\nUse /help to see commands."
    )

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    text = (
        "🤖 *Commands:*\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/stats - Your usage stats\n"
    )
    if message.from_user.id == SUPER_VIP_ID:
        await message.answer(text + "\nAdmin commands below:", parse_mode="Markdown", reply_markup=admin_buttons)
    else:
        await message.answer(text, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('vip_'))
async def process_admin_buttons(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    action = callback_query.data

    if user_id != SUPER_VIP_ID:
        await callback_query.answer("❌ Not authorized.", show_alert=True)
        return

    if action == "vip_add" or action == "vip_remove":
        await state.update_data(vip_action=action)
        prompt_text = "Please send the user ID to *ADD* as VIP:" if action == "vip_add" else "Please send the user ID to *REMOVE* from VIP:"
        await VIPManage.waiting_for_user_id.set()
        await callback_query.message.answer(prompt_text, parse_mode="Markdown")
        await callback_query.answer()
    elif action == "vip_list":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE vip=1")
        vips = c.fetchall()
        conn.close()
        if not vips:
            await callback_query.message.answer("No VIP users found.")
        else:
            vip_list = "\n".join(str(uid[0]) for uid in vips)
            await callback_query.message.answer(f"👑 VIP Users:\n{vip_list}")
        await callback_query.answer()

@dp.message_handler(state=VIPManage.waiting_for_user_id)
async def vip_manage_user_id_final(message: types.Message, state: FSMContext):
    data = await state.get_data()
    action = data.get('vip_action')
    user_id_text = message.text.strip()

    try:
        target_user_id = int(user_id_text)
    except ValueError:
        await message.reply("❌ Invalid user ID. Please send a numeric user ID.")
        return

    if action == "vip_add":
        set_vip(target_user_id, 1)
        await message.reply(f"✅ User `{target_user_id}` has been *added* as VIP.", parse_mode="Markdown")
    elif action == "vip_remove":
        remove_vip(target_user_id)
        await message.reply(f"✅ User `{target_user_id}` has been *removed* from VIP.", parse_mode="Markdown")

    await state.finish()

@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    user_id = message.from_user.id
    last_used, usage_count = get_usage(user_id)
    vip_status = "Yes" if is_vip(user_id) or user_id == SUPER_VIP_ID else "No"
    last_used = last_used or "Never"
    await message.answer(
        f"👤 Your stats:\n"
        f"VIP: {vip_status}\n"
        f"Downloads today: {usage_count}\n"
        f"Last used: {last_used}"
    )

@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Check if message looks like a Terabox link (simple check)
    if "terabox.com" not in text.lower():
        await message.reply("Please send a valid Terabox video link.")
        return

    if not can_use(user_id):
        await message.reply(f"❌ You reached your daily limit of {DOWNLOAD_LIMIT_PER_DAY} downloads.\nBecome VIP to get unlimited access!")
        return

    # Here, insert your existing video fetch logic:
    # For demo, just reply "Downloading video..."
    await message.reply("⏳ Fetching video, please wait...")

    # Simulate video fetch with asyncio.sleep for demo only
    await asyncio.sleep(2)

    # After video fetch (replace with real logic)
    video_url = "https://example.com/fakevideo.mp4"  # replace with real video url

    await message.reply(f"✅ Video ready: {video_url}")

    # Update usage count
    update_usage(user_id)

if __name__ == '__main__':
    init_db()
    print("Bot is starting...")
    executor.start_polling(dp, skip_updates=True)
