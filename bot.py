import logging import json import requests from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

Bot Token and Admin ID

BOT_TOKEN = "7950519159:AAFJoYri3SImSjh43E4iXAQtWED0vl1IHhc" ADMIN_ID = 1669843747

In-memory user verification list

verified_users = set()

Enable logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO) logger = logging.getLogger(name)

RapidAPI credentials

RAPIDAPI_KEY = "76194bd682msh9afcf89c5486ed5p1ddd34jsn64dccdab1f1a" HEADERS = { "Content-Type": "application/json", "x-rapidapi-host": "social-download-all-in-one.p.rapidapi.com", "x-rapidapi-key": RAPIDAPI_KEY } API_URL = "https://social-download-all-in-one.p.rapidapi.com/v1/social/autolink"

Start command

def start(update: Update, context: CallbackContext): user_id = update.effective_user.id if user_id not in verified_users and user_id != ADMIN_ID: update.message.reply_text("You are not verified yet. Please request access from admin.") return

buttons = [
    [InlineKeyboardButton("YouTube", callback_data='yt'),
     InlineKeyboardButton("Instagram", callback_data='ig')],
    [InlineKeyboardButton("TikTok", callback_data='tiktok'),
     InlineKeyboardButton("Terabox", callback_data='terabox')],
    [InlineKeyboardButton("Snapchat", callback_data='snapchat'),
     InlineKeyboardButton("X (Twitter)", callback_data='twitter')]
]
update.message.reply_text("Welcome to Downloader AI! Share a link to begin.", reply_markup=InlineKeyboardMarkup(buttons))

Admin panel for verification

def admin(update: Update, context: CallbackContext): if update.effective_user.id != ADMIN_ID: update.message.reply_text("You are not authorized.") return

keyboard = [
    [InlineKeyboardButton("Verify User", callback_data='admin_verify'),
     InlineKeyboardButton("Remove User", callback_data='admin_remove')],
    [InlineKeyboardButton("List Verified", callback_data='admin_list')]
]
update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

Handle verification actions

def admin_actions(update: Update, context: CallbackContext): query = update.callback_query query.answer()

if query.data == "admin_verify":
    context.user_data['admin_action'] = 'verify'
    query.edit_message_text("Send the user ID to verify.")
elif query.data == "admin_remove":
    context.user_data['admin_action'] = 'remove'
    query.edit_message_text("Send the user ID to remove.")
elif query.data == "admin_list":
    if not verified_users:
        query.edit_message_text("No verified users.")
    else:
        users = "\n".join([str(uid) for uid in verified_users])
        query.edit_message_text(f"Verified Users:\n{users}")

Handle user verification input

def handle_userid_input(update: Update, context: CallbackContext): if 'admin_action' not in context.user_data: return

try:
    user_id = int(update.message.text.strip())
    if context.user_data['admin_action'] == 'verify':
        verified_users.add(user_id)
        update.message.reply_text(f"User {user_id} verified.")
    elif context.user_data['admin_action'] == 'remove':
        verified_users.discard(user_id)
        update.message.reply_text(f"User {user_id} removed.")
    context.user_data.clear()
except ValueError:
    update.message.reply_text("Invalid user ID.")

Handle shared link

def handle_link(update: Update, context: CallbackContext): user_id = update.effective_user.id if user_id not in verified_users and user_id != ADMIN_ID: update.message.reply_text("You are not verified. Contact admin.") return

url = update.message.text.strip()
data = json.dumps({"url": url})
response = requests.post(API_URL, headers=HEADERS, data=data)

if response.status_code == 200:
    result = response.json()
    if result.get("status"):
        media_url = result.get("media", [{}])[0].get("url")
        buttons = [[
            InlineKeyboardButton("Download", url=media_url),
            InlineKeyboardButton("Watch", url=media_url)
        ]]
        update.message.reply_text("Media fetched successfully:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        update.message.reply_text("Could not fetch media. Make sure link is correct.")
else:
    update.message.reply_text("Failed to connect to download server.")

if name == 'main': app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), handle_userid_input))
app.add_handler(CallbackQueryHandler(admin_actions))

print("Bot is running...")
app.run_polling()

