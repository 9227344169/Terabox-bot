import os
import re
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from yt_dlp import YoutubeDL

BOT_TOKEN = os.getenv("BOT_TOKEN") or "7950519159:AAFJoYri3SImSjh43E4iXAQtWED0vl1IHhc"
ADMIN_ID = int(os.getenv("ADMIN_ID") or 1669843747)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# In-memory verified users list (should use DB for persistence)
verified_users = set()

# Regex patterns for supported platforms
PLATFORM_PATTERNS = {
    "youtube": re.compile(r"(youtu\.be|youtube\.com)"),
    "instagram": re.compile(r"(instagram\.com)"),
    "terabox": re.compile(r"(teraboxshare\.com|teraboxlink\.com|terabox\.com)"),
    "twitter": re.compile(r"(twitter\.com|x\.com)"),
    "snapchat": re.compile(r"(snapchat\.com)"),
    "whatsapp": re.compile(r"(whatsapp\.com)"),
    # Add more if needed
}

# YTDL options for audio/video extraction
YTDL_OPTS_VIDEO = {
    "format": "bestvideo+bestaudio/best",
    "outtmpl": "%(id)s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
}
YTDL_OPTS_AUDIO = {
    "format": "bestaudio/best",
    "outtmpl": "%(id)s.%(ext)s",
    "quiet": True,
    "no_warnings": True,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
}

def detect_platform(url: str):
    for name, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return name
    return None

async def download_youtube(url: str, audio_only=False):
    opts = YTDL_OPTS_AUDIO if audio_only else YTDL_OPTS_VIDEO
    loop = asyncio.get_event_loop()
    ytdl = YoutubeDL(opts)
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=True))
    filename = ytdl.prepare_filename(data)
    return filename, data.get("title", "video")

async def send_file(chat_id, file_path, caption):
    try:
        async with bot:
            await bot.send_chat_action(chat_id, action=types.ChatActions.UPLOAD_DOCUMENT)
            with open(file_path, "rb") as f:
                await bot.send_document(chat_id, document=f, caption=caption)
    finally:
        try:
            os.remove(file_path)
        except Exception:
            pass

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Welcome to Downloader Ai!\n\n"
        "Send me any supported social media link and I'll help you download or watch it.\n"
        "You must be verified by admin to use this bot.\n"
        "Use /help to see commands."
    )

@dp.message_handler(commands=["help"])
async def help_handler(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    if message.from_user.id == ADMIN_ID:
        kb.add(
            InlineKeyboardButton("Verify User", callback_data="verify_user"),
            InlineKeyboardButton("Remove User", callback_data="remove_user"),
            InlineKeyboardButton("Verified List", callback_data="list_verified"),
        )
    await message.answer(
        "🤖 Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help\n\n"
        "Send any video/music link to download or watch.\n"
        "Only verified users can use the bot.",
        reply_markup=kb if kb.inline_keyboard else None,
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith(("verify_user", "remove_user", "list_verified")))
async def admin_buttons_handler(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Unauthorized", show_alert=True)
        return

    data = callback_query.data
    if data == "verify_user":
        await callback_query.message.answer("Send me the Telegram user ID to verify:")
        await bot.answer_callback_query(callback_query.id)
        dp.register_message_handler(verify_user_handler, state=None, content_types=types.ContentTypes.TEXT, chat_id=ADMIN_ID)
    elif data == "remove_user":
        await callback_query.message.answer("Send me the Telegram user ID to remove from verified:")
        await bot.answer_callback_query(callback_query.id)
        dp.register_message_handler(remove_user_handler, state=None, content_types=types.ContentTypes.TEXT, chat_id=ADMIN_ID)
    elif data == "list_verified":
        if verified_users:
            verified_list = "\n".join(str(uid) for uid in verified_users)
            await callback_query.message.answer(f"Verified users:\n{verified_list}")
        else:
            await callback_query.message.answer("No users verified yet.")
        await bot.answer_callback_query(callback_query.id)

async def verify_user_handler(message: types.Message):
    try:
        user_id = int(message.text.strip())
        if user_id in verified_users:
            await message.answer(f"User {user_id} is already verified.")
        else:
            verified_users.add(user_id)
            await message.answer(f"User {user_id} verified successfully!")
    except ValueError:
        await message.answer("Invalid user ID. Please send a numeric Telegram user ID.")
    finally:
        dp.message_handlers.unregister(verify_user_handler)

async def remove_user_handler(message: types.Message):
    try:
        user_id = int(message.text.strip())
        if user_id in verified_users:
            verified_users.remove(user_id)
            await message.answer(f"User {user_id} removed from verified list.")
        else:
            await message.answer(f"User {user_id} is not in the verified list.")
    except ValueError:
        await message.answer("Invalid user ID. Please send a numeric Telegram user ID.")
    finally:
        dp.message_handlers.unregister(remove_user_handler)

@dp.message_handler()
async def link_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID and user_id not in verified_users:
        await message.answer("❌ You are not verified to use this bot. Please contact admin.")
        return

    url = message.text.strip()
    platform = detect_platform(url)
    if not platform:
        await message.answer("❌ Unsupported or invalid link.")
        return

    # Inline buttons to choose Watch or Download
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Watch", callback_data=f"watch_{platform}|{url}"),
        InlineKeyboardButton("Download", callback_data=f"download_{platform}|{url}"),
    )
    await message.answer(f"Detected platform: {platform.capitalize()}\nChoose action:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and (c.data.startswith("watch_") or c.data.startswith("download_")))
async def action_handler(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id != ADMIN_ID and user_id not in verified_users:
        await callback_query.answer("❌ You are not verified to use this bot.", show_alert=True)
        return

    action, rest = callback_query.data.split("_", 1)
    platform, url = rest.split("|", 1)

    await callback_query.answer("Processing, please wait...")

    if platform == "youtube":
        try:
            if action == "watch":
                await callback_query.message.answer(f"Watch link: {url}\n(Open in your browser)")
            else:  # download
                filename, title = await download_youtube(url, audio_only=False)
                await send_file(callback_query.message.chat.id, filename, caption=f"🎥 {title}")
        except Exception as e:
            await callback_query.message.answer(f"Error processing YouTube link: {e}")

    elif platform == "instagram":
        await callback_query.message.answer("Instagram downloads coming soon!")

    elif platform == "terabox":
        # Placeholder: Terabox video downloader logic (implement your own scraper/API)
        await callback_query.message.answer("Terabox downloader support coming soon!")

    elif platform == "twitter":
        await callback_query.message.answer("Twitter/X downloads coming soon!")

    elif platform == "snapchat":
        await callback_query.message.answer("Snapchat downloads coming soon!")

    elif platform == "whatsapp":
        await callback_query.message.answer("WhatsApp downloads coming soon!")

    else:
        await callback_query.message.answer("Unsupported platform.")

if __name__ == "__main__":
    print("Bot started...")
    executor.start_polling(dp, skip_updates=True)
