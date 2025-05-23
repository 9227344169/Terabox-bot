import logging
import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# Replace with your bot token
BOT_TOKEN = "7950519159:AAFJoYri3SImSjh43E4iXAQtWED0vl1IHhc"

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Help", callback_data='help')],
        [InlineKeyboardButton("About", callback_data='about')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to Downloader AI!", reply_markup=reply_markup)

async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "help":
        await query.edit_message_text("Send any video URL to download.")
    elif data == "about":
        await query.edit_message_text("Bot by H4RSHB0Y19. Uses various APIs to fetch media.")

async def handle_message(update: Update, context: CallbackContext):
    url = update.message.text
    headers = {
        'Content-Type': 'application/json',
        'x-rapidapi-host': 'social-download-all-in-one.p.rapidapi.com',
        'x-rapidapi-key': '76194bd682msh9afcf89c5486ed5p1ddd34jsn64dccdab1f1a'
    }
    data = {"url": url}
    response = requests.post(
        'https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink',
        headers=headers,
        data=json.dumps(data)
    )

    if response.status_code == 200:
        result = response.json()
        download_url = result.get('link', 'No link found')
        await update.message.reply_text(f"Download: {download_url}")
    else:
        await update.message.reply_text("Failed to fetch download link. Please try another URL.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
