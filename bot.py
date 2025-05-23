import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

logging.basicConfig(level=logging.INFO)

verified_users = set()

def build_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Verify Me", callback_data="verify")],
        [InlineKeyboardButton("Remove Me", callback_data="remove")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = build_main_keyboard()
    await update.message.reply_text(
        "Welcome to Downloader AI!
Send any supported media link (YouTube, Instagram, Terabox, etc.) to download.

Click below to verify:",
        reply_markup=keyboard
    )

async def handle_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if query.data == "verify":
        if user_id == ADMIN_ID:
            await query.answer("You are admin and already verified.")
        else:
            verified_users.add(user_id)
            await query.answer("Verified successfully!")
    elif query.data == "remove":
        verified_users.discard(user_id)
        await query.answer("Removed from verified list.")

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID and user_id not in verified_users:
        await update.message.reply_text("You are not verified. Click below to verify yourself first.",
                                        reply_markup=build_main_keyboard())
        return

    url = update.message.text.strip()
    api_url = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"
    headers = {
        "Content-Type": "application/json",
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "social-download-all-in-one.p.rapidapi.com"
    }
    response = requests.post(api_url, json={"url": url}, headers=headers)
    try:
        result = response.json()
        if "media" in result:
            for media in result["media"]:
                media_url = media.get("url")
                await update.message.reply_text(f"Download: {media_url}")
        else:
            await update.message.reply_text("No media found or unsupported link.")
    except Exception as e:
        await update.message.reply_text("An error occurred. Please try again later.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_verification))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))
    app.run_polling()

if __name__ == "__main__":
    main()
