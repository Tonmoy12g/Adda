"""
Fun Group Bot 🤖😂
- Telegram group auto-reply bot — witty/funny Bangla replies, just for fun!
- Long polling (Render free tier friendly, no webhook needed)
- Env vars:
    TELEGRAM_BOT_TOKEN (required) — BotFather token
- No API key needed — replies come from the built-in funny reply list
- Group triggers: @mention of the bot, reply to the bot's message, /ask command
"""

import os
import random
import time
import threading
import logging
from collections import defaultdict

from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- Config ----------------
# সহজ পদ্ধতি: নিচের জায়গায় নিজের bot token বসিয়ে দিন (""-এর ভেতরে)।
# ⚠️ সতর্কতা: token বসানো ফাইল GitHub-এ দিলে repo অবশ্যই PRIVATE রাখতে হবে!
# Public repo হলে token চুরি হয়ে যাবে। চাইলে Render-এর Environment থেকেও
# দেওয়া যায় — তখন নিচের জায়গা ফাঁকা রাখলেই হবে।
PASTE_TELEGRAM_TOKEN_HERE = ""

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or PASTE_TELEGRAM_TOKEN_HERE.strip()

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN env var is missing!")

# ---------------- Built-in funny canned replies (no API key needed) ----------------
FUN_REPLIES = [
    "ভাই, এই প্রশ্ন শুনে আমার সার্কিট গরম হয়ে গেল! 🔥 একটু ঠান্ডা হতে দাও!",
    "ওহো! এত কঠিন প্রশ্ন? আমি তো বট, বিজ্ঞানী না! 😅",
    "উত্তরটা আমার জানা আছে, কিন্তু বললে মজা শেষ! 😉",
    "ভাই তুমি তো জিনিয়াস! এই প্রশ্নের উত্তর গুগলও জানে না! 🤯",
    "এক মিনিট... চিন্তা করছি... ... ... নাহ, পারলাম না! 😂",
    "এই প্রশ্নের উত্তর দিলে আমার ব্যাটারি শেষ হয়ে যাবে! 🔋",
    "বাহ! কী প্রশ্ন! 👏 তালি বাজাও সবাই!",
    "আমি শুধু মজার বট ভাই, এনসাইক্লোপিডিয়া না! 📚❌",
    "প্রশ্নটা ভালো, কিন্তু উত্তরটা আরও ভালো হতো যদি জানতাম! 😜",
    "ভাই, রাত ৩টায় এসব প্রশ্ন কোরো না, আমারও ঘুম পায়! 😴",
    "উত্তর: ৪২! (সব প্রশ্নের উত্তরই ৪২! 😎)",
    "এইটা শুনে আমার AI মাথা ঘুরাচ্ছে! 🌀",
    "তুমি প্রশ্ন করো, আমি হাসি — ডিল ডান! 🤝😂",
    "আরে ভাই, এত সিরিয়াস কেন? একটু হাসো! 😁",
    "আমার ডেটাবেজে এই প্রশ্নের উত্তর 'লোডিং...' অবস্থায় আছে! ⏳",
    "সত্যি বলতে? জানি না! কিন্তু কনফিডেন্সের সাথে বলছি! 💪😂",
    "এই গ্রুপে তুমিই সবচেয়ে মজার মানুষ, প্রশ্ন দিয়েই প্রমাণ করলে! 🏆",
    "বট হলেও আমার ফিলিংস আছে ভাই! এত কঠিন প্রশ্ন কোরো না! 🥺",
]


def _fun_answer(text: str) -> str:
    """Pick a random built-in funny reply."""
    return random.choice(FUN_REPLIES)


# ---------------- Simple anti-spam (per user cooldown) ----------------
_last_reply = defaultdict(float)
COOLDOWN_SEC = 3


def _cooldown_ok(user_id: int) -> bool:
    now = time.time()
    if now - _last_reply[user_id] < COOLDOWN_SEC:
        return False
    _last_reply[user_id] = now
    return True


# ---------------- Trigger detection ----------------
def _is_mentioned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    msg = update.message
    if not msg or not msg.text:
        return False
    username = context.bot_data.get("bot_username", "")
    if not username:
        return False
    tag = f"@{username}".lower()
    for e in msg.entities or []:
        if e.type == "mention":
            if msg.text[e.offset : e.offset + e.length].lower() == tag:
                return True
    return tag in msg.text.lower()


def _is_reply_to_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    msg = update.message
    r = msg.reply_to_message if msg else None
    return bool(
        r and r.from_user and r.from_user.is_bot and r.from_user.id == context.bot.id
    )


def _clean_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Remove the @mention so the AI sees just the question."""
    text = (update.message.text or "").strip()
    username = context.bot_data.get("bot_username", "")
    if username:
        text = text.replace(f"@{username}", "").strip()
    return text


# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ওয়াসসাপ! আমি <b>FunBot</b> 🤖😂\n\n"
        "আমাকে ডাকো এভাবে:\n"
        "• @ দিয়ে মেনশন করো — যেমন: <code>@mybot তুমি কে?</code>\n"
        "• আমার মেসেজে <b>রিপ্লাই</b> দাও\n"
        "• <code>/ask তোমার প্রশ্ন</code> লিখো\n\n"
        "মজার উত্তর গ্যারান্টি! 😉",
        parse_mode="HTML",
    )


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text(
            "ব্যবহার: <code>/ask তোমার প্রশ্ন</code>\n"
            "যেমন: <code>/ask আজকে কী খাবো?</code>",
            parse_mode="HTML",
        )
        return
    user = update.effective_user
    if not _cooldown_ok(user.id):
        return
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )
    await update.message.reply_text(_fun_answer(question))


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text or not msg.text.strip():
        return
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == "private":
        should_reply = True  # in DM, answer everything
    else:
        # in groups: only on mention or reply-to-bot
        should_reply = _is_mentioned(update, context) or _is_reply_to_bot(
            update, context
        )
    if not should_reply:
        return
    if not _cooldown_ok(user.id):
        return

    await context.bot.send_chat_action(chat_id=chat.id, action="typing")
    await msg.reply_text(_fun_answer(_clean_text(update, context)))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("Update caused error: %s", context.error)


async def post_init(app: Application):
    me = await app.bot.get_me()
    app.bot_data["bot_username"] = me.username or ""
    logger.info("Bot username: @%s", me.username)


def run_bot():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.post_init = post_init
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    logger.info("🤖 Fun Group Bot is running...")
    app.run_polling(drop_pending_updates=True)


# ---------------- Flask (keeps Render free web service alive) ----------------
flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "🤖 Fun Group Bot is running!"


@flask_app.route("/health")
def health():
    return "OK", 200


if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", "10000"))
    flask_app.run(host="0.0.0.0", port=port)
