import os
import requests
import csv
from io import StringIO
import re
import time
from difflib import get_close_matches
from datetime import timezone, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    Filters
)

# ================= CONFIG =================

TOKEN = os.environ.get("TOKEN")   # 🔐 required for Cyclic
ADMIN_ID = 866336338
CHANNEL_USERNAME = "@PhysioProbe"
YOUTUBE_URL = "https://www.youtube.com/@PhysioProbe"

BOOK_SHEET_ID = "1jE5-1gehOQdYsr7QC3Z2L09AhX21DvRLr7sYBeo3aqA"
BOOK_CSV_URL = f"https://docs.google.com/spreadsheets/d/{BOOK_SHEET_ID}/export?format=csv"

LANG_SHEET_ID = "1ZMxy8HI-gnHS2zjgcnNF3k_leSJqVE5UJtOD_qLYAH0"
LANG_CSV_URL = f"https://docs.google.com/spreadsheets/d/{LANG_SHEET_ID}/export?format=csv"

LANG_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdGhShTgt0e_NXTbSJ9M24ELkyQfv--stqjnKZWH9m9vfv_Vg/formResponse"
LANG_ENTRY_USER = "entry.1475021879"
LANG_ENTRY_LANG = "entry.422264672"

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSd2q8411cxwAB6DKQCqSQFq8Fj8xqyO_Z4yGAMGdLwCuWWBeg/formResponse"
ENTRY_USERNAME = "entry.1989081131"
ENTRY_USER_ID = "entry.1301266442"
ENTRY_BOOK = "entry.357487451"
ENTRY_SOURCE = "entry.2741068"

RATE_LIMIT_SECONDS = 3
IST = timezone(timedelta(hours=5, minutes=30))

# ================= STATE =================

BOOKS = []
USER_LANGUAGE = {}
LAST_QUERY_TIME = {}
UNLOCKED_USERS = set()

STOP_WORDS = {
    "i","need","want","book","pdf","any","please",
    "give","me","for","of","a","an","kitab"
}

# ================= HELPERS =================

def stars(r):
    try:
        r = float(r)
        return "⭐" * int(round(r)) + f" ({r})"
    except:
        return "—"

def clean_words(text):
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return [w for w in text.split() if w not in STOP_WORDS and len(w) > 2]

def get_lang(uid):
    return USER_LANGUAGE.get(uid, "en")

def is_channel_member(bot, uid):
    try:
        m = bot.get_chat_member(CHANNEL_USERNAME, uid)
        return m.status in ("member", "administrator", "creator")
    except:
        return False

# ================= LOADERS =================

def load_books():
    global BOOKS
    BOOKS = []
    r = requests.get(BOOK_CSV_URL, timeout=10)
    reader = csv.DictReader(StringIO(r.text))
    for row in reader:
        BOOKS.append({
            "title": row["title"],
            "keywords": row["keywords"].lower(),
            "link": row["link"],
            "size": row.get("size_mb", ""),
            "rating": row.get("rating", "")
        })

def load_languages():
    global USER_LANGUAGE
    USER_LANGUAGE = {}
    try:
        r = requests.get(LANG_CSV_URL, timeout=10)
        reader = csv.DictReader(StringIO(r.text))
        for row in reader:
            USER_LANGUAGE[int(row["user_id"])] = row["language"]
    except:
        pass

def save_language(user_id, lang):
    USER_LANGUAGE[user_id] = lang
    try:
        requests.post(LANG_FORM_URL, data={
            LANG_ENTRY_USER: user_id,
            LANG_ENTRY_LANG: lang
        }, timeout=5)
    except:
        pass

# ================= SEARCH =================

def search_books(query):
    words = clean_words(query)
    results = []
    for b in BOOKS:
        score = sum(1 for w in words if w in b["keywords"])
        if score > 0:
            results.append((score, b))
    results.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in results[:3]]

def spelling_suggestions(query):
    all_kw = set()
    for b in BOOKS:
        all_kw.update(b["keywords"].split(","))
    return get_close_matches(query.lower(), all_kw, n=5, cutoff=0.75)

# ================= COMMANDS =================

def start_cmd(update, context):
    kb = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="LANG::en")],
        [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="LANG::hi")]
    ]
    update.message.reply_text("Please choose language / भाषा चुनें",
                              reply_markup=InlineKeyboardMarkup(kb))

def language_callback(update, context):
    q = update.callback_query
    q.answer()
    lang = q.data.split("::")[1]
    save_language(q.from_user.id, lang)
    q.edit_message_text("Language set successfully.")

# ================= MESSAGE HANDLER =================

def handle_message(update, context):
    user = update.effective_user
    lang = get_lang(user.id)

    if not is_channel_member(context.bot, user.id):
        update.message.reply_text("🔒 Please join @PhysioProbe to use this bot.")
        return

    now = time.time()
    if now - LAST_QUERY_TIME.get(user.id, 0) < RATE_LIMIT_SECONDS:
        update.message.reply_text("⏳ Please wait before another search.")
        return
    LAST_QUERY_TIME[user.id] = now

    query = update.message.text.strip()
    results = search_books(query)

    if not results:
        sugg = spelling_suggestions(query)
        msg = "No results found."
        if sugg:
            msg += "\nDid you mean:\n" + "\n".join(f"• {s}" for s in sugg)
        update.message.reply_text(msg)
        return

    lines = ["📚 Search Results"]
    kb = []

    for i, b in enumerate(results, 1):
        size = b["size"] + " MB" if b["size"] else "—"
        lines.append(
            f"\n{i}. {b['title']}\n"
            f"Size: {size}\n"
            f"Rating: {stars(b['rating'])}"
        )
        kb.append([InlineKeyboardButton(f"Download {i}", url=b["link"])])

    update.message.reply_text("\n".join(lines),
                              reply_markup=InlineKeyboardMarkup(kb))

# ================= MAIN =================

if __name__ == "__main__":
    load_books()
    load_languages()

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CallbackQueryHandler(language_callback, pattern="^LANG::"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()
