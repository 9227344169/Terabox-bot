import random
import asyncio
import httpx  # replaces requests
import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = "7950519159:AAFJoYri3SImSjh43E4iXAQtWED0vl1IHhc"  # Replace with your actual bot token

users = {}
user_mails = {}
favorites = {}
last_request_time = time.time()
domain_cache = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📩 Generate Mail", callback_data="gen_mail")],
    [InlineKeyboardButton("📥 Inbox", callback_data="inbox")],
    [InlineKeyboardButton("📜 Mail List", callback_data="maillist"),
     InlineKeyboardButton("⭐ Favorite Mails", callback_data="favlist")],
    [InlineKeyboardButton("👤 Gen Fake Name", callback_data="gen_name"),
     InlineKeyboardButton("📱 Gen Fake Number", callback_data="gen_num")],
    [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]
])

def fast(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await func(update, context)
    return wrapper

@fast
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✨ *FakeMail Bot* \nDeveloper: @H4RSHB0Y 🗿\n\nWelcome to the most premium fake mail + gen bot. Let's get started! 🚀\n\nChoose a feature below:",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )

@fast
async def gen_mail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    global last_request_time, domain_cache
    current_time = time.time()
    if current_time - last_request_time < 10:
        domains = domain_cache
    else:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                domain_data = await client.get("https://api.mail.tm/domains")
                domains = domain_data.json().get("hydra:member", [])
                if not domains:
                    raise Exception("No domains received.")
                domain_cache = domains
                last_request_time = current_time
        except Exception as e:
            logger.error(f"Domain fetch error: {e}")
            await query.edit_message_text("⚠️ Failed to fetch domains. Please try again later.", reply_markup=MAIN_MENU)
            return

    max_attempts = 5
    async with httpx.AsyncClient(timeout=10) as client:
        for _ in range(max_attempts):
            username = f"user{random.randint(1000, 9999)}"
            domain = random.choice(domains)["domain"]
            email = f"{username}@{domain}"
            password = "Password@123"

            res = await client.post("https://api.mail.tm/accounts", json={"address": email, "password": password})
            if res.status_code == 201:
                break
        else:
            await query.edit_message_text("❌ All attempts failed. Try again later.", reply_markup=MAIN_MENU)
            return

        token_res = await client.post("https://api.mail.tm/token", json={"address": email, "password": password})
        token = token_res.json().get("token")

        me_res = await client.get("https://api.mail.tm/me", headers={"Authorization": f"Bearer {token}"})
        me = me_res.json()

    users[user_id] = {
        "email": email, "password": password, "token": token, "id": me.get("id")
    }
    user_mails.setdefault(user_id, []).append(email)

    await query.edit_message_text(
        text=f"📩 *Generated Email:*\n`{email}`\n\n_Tap to copy!_\nUse 📥 *Inbox* to check messages.",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )

@fast
async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    if user_id not in users:
        await query.edit_message_text("⚠️ Please generate a mail first using 📩.", reply_markup=MAIN_MENU)
        return

    token = users[user_id]["token"]
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {token}"})
        messages = res.json().get("hydra:member", [])

    if not messages:
        await query.edit_message_text(
            "📭 No new messages yet. Stay tuned! 🕐\n\n🛠 Developer: @H4RSHB0Y 🗿",
            reply_markup=MAIN_MENU
        )
        return

    text = ""
    for msg in messages[:3]:
        text += f"*From:* {msg['from']['address']}\n*Subject:* {msg['subject']}\n{msg['intro']}\n\n"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=MAIN_MENU)

@fast
async def maillist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    if user_id not in user_mails or not user_mails[user_id]:
        await query.edit_message_text("📭 No mails generated yet. 📬", reply_markup=MAIN_MENU)
        return

    buttons = []
    for email in user_mails[user_id]:
        buttons.append([
            InlineKeyboardButton(email, callback_data=f"selectmail:{email}"),
            InlineKeyboardButton("❌ Delete", callback_data=f"delete_{email}"),
            InlineKeyboardButton("⭐️ Fav", callback_data=f"fav_{email}")
        ])
    buttons.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")])
    await query.edit_message_text(
        "📜 *Your Mail List:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@fast
async def selectmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    email = query.data.split(":", 1)[1]

    for eid, data in users.items():
        if data["email"] == email:
            token = data["token"]
            break
    else:
        await query.edit_message_text("⚠️ Session expired. Please regenerate.", reply_markup=MAIN_MENU)
        return

    inbox_data = await httpx.AsyncClient(timeout=10).get("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {token}"})
    messages = inbox_data.json().get("hydra:member", [])

    if not messages:
        await query.edit_message_text(f"📭 No messages found for:\n`{email}`", parse_mode="Markdown", reply_markup=MAIN_MENU)
        return

    text = f"📬 *Inbox for:* `{email}`\n\n"
    for msg in messages[:3]:
        text += f"*From:* {msg['from']['address']}\n*Subject:* {msg['subject']}\n{msg['intro']}\n\n"

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]
    ]))

@fast
async def delete_mail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    email = query.data.split("_", 1)[1]

    if email in user_mails.get(user_id, []):
        user_mails[user_id].remove(email)
        await query.edit_message_text(f"🗑️ Deleted `{email}`", parse_mode="Markdown", reply_markup=MAIN_MENU)
    else:
        await query.edit_message_text("⚠️ Email not found in your list.", reply_markup=MAIN_MENU)

@fast
async def fav_mail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    email = query.data.split("_", 1)[1]

    favorites.setdefault(user_id, set()).add(email)
    await query.edit_message_text(f"⭐️ `{email}` added to your favorites!", parse_mode="Markdown", reply_markup=MAIN_MENU)

@fast
async def favlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    favs = favorites.get(user_id, set())
    if not favs:
        await query.edit_message_text("⭐ No favorite emails saved.", reply_markup=MAIN_MENU)
        return

    buttons = []
    for email in favs:
        buttons.append([
            InlineKeyboardButton(email, callback_data=f"selectmail:{email}"),
            InlineKeyboardButton("❌ Delete", callback_data=f"delete_{email}")
        ])
    buttons.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")])

    await query.edit_message_text(
        "⭐ *Your Favorite Emails:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@fast
async def gen_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    first_names = ["Aarav", "Vivaan", "Aditya", "Krishna", "Aryan", "Rohan", "Harsh", "Tejas", "Ajay", "Sagar"]
    last_names = ["Sharma", "Patel", "Gupta", "Singh", "Yadav", "Mehta", "Kumar", "Verma", "Jain", "Bhat"]
    full_name = f"{random.choice(first_names)} {random.choice(last_names)}"

    await query.edit_message_text(f"👤 *Generated Name:*\n`{full_name}`\n\n_Tap to copy!_", parse_mode="Markdown", reply_markup=MAIN_MENU)

@fast
async def gen_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    number = f"{random.randint(6000000000, 9999999999)}"
    await query.edit_message_text(f"📱 *Generated Number:*\n`{number}`\n\n_Tap to copy!_", parse_mode="Markdown", reply_markup=MAIN_MENU)

@fast
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="✨ *FakeMail Bot* \nDeveloper: @H4RSHB0Y 🗿\n\nChoose a feature below:",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )

def check_new_mails():
    for user_id, data in users.items():
        token = data["token"]
        last_msg_id = data.get("last_msg_id")
        try:
            res = httpx.get("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            messages = res.json().get("hydra:member", [])
            if messages:
                latest = messages[0]
                if latest["id"] != last_msg_id:
                    users[user_id]["last_msg_id"] = latest["id"]
                    text = f"📧 *New Mail from:* {latest['from']['address']}\n*Subject:* {latest['subject']}\n\n{latest['intro']}"
                    app.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error checking mail for user {user_id}: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(check_new_mails, 'interval', seconds=7)
scheduler.start()

def main():
    global app
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(gen_mail, pattern="gen_mail"))
    app.add_handler(CallbackQueryHandler(inbox, pattern="inbox"))
    app.add_handler(CallbackQueryHandler(maillist, pattern="maillist"))
    app.add_handler(CallbackQueryHandler(selectmail, pattern="selectmail:"))
    app.add_handler(CallbackQueryHandler(delete_mail, pattern="delete_"))
    app.add_handler(CallbackQueryHandler(fav_mail, pattern="fav_"))
    app.add_handler(CallbackQueryHandler(gen_name, pattern="gen_name"))
    app.add_handler(CallbackQueryHandler(gen_num, pattern="gen_num"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="back_to_menu"))
    app.add_handler(CallbackQueryHandler(favlist, pattern="favlist"))

    app.run_polling()

if __name__ == "__main__":
    main()
