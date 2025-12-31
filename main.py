import requests
import csv
from io import StringIO
import re
import threading
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

TOKEN = "8222654785:AAHPpiMmqiW275FnK94Ov09gmQqzHdQd-2I"
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
AUTO_DELETE_SECONDS = 300

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

# ================= TEXT =================

TEXT = {
    "welcome": {
        "en": "👋 Welcome to *PhysioProbe Book Bot*\n\nType the book name or topic.",
        "hi": "👋 *PhysioProbe Book Bot* में आपका स्वागत है\n\nकिताब या टॉपिक लिखें।"
    },
    "disclaimer": {
        "en": (
            "⚠️ Disclaimer\n\n"
            "PhysioProbe does not host or store any files.\n"
            "All materials are shared for educational reference only.\n"
            "Links point to publicly available sources.\n\n"
            "If you are a copyright owner and want content removed,\n"
            "please contact us and it will be taken down immediately.\n\n"
            "📩 Contact: @PhysioProbeAdmin"
        ),
        "hi": (
            "⚠️ अस्वीकरण\n\n"
            "PhysioProbe किसी भी फ़ाइल को होस्ट या स्टोर नहीं करता।\n"
            "सभी सामग्री केवल शैक्षणिक संदर्भ के लिए है।\n"
            "लिंक सार्वजनिक स्रोतों की ओर ले जाते हैं।\n\n"
            "यदि आप कॉपीराइट मालिक हैं और सामग्री हटवाना चाहते हैं,\n"
            "तो कृपया हमसे संपर्क करें — तुरंत हटा दी जाएगी।\n\n"
            "📩 संपर्क: @PhysioProbeAdmin"
        )
    },
    "about": {
        "en": (
            "ℹ️ About PhysioProbe\n\n"
            "PhysioProbe is an educational assistant for physiotherapy students.\n\n"
            "• We do not host files\n"
            "• We respect copyright laws\n"
            "• Content is for study reference only\n\n"
            "📩 Contact: @PhysioProbeAdmin"
        ),
        "hi": (
            "ℹ️ PhysioProbe के बारे में\n\n"
            "PhysioProbe फिजियोथेरेपी छात्रों के लिए एक शैक्षणिक सहायक है।\n\n"
            "• हम फ़ाइल होस्ट नहीं करते\n"
            "• हम कॉपीराइट नियमों का सम्मान करते हैं\n"
            "• सामग्री केवल अध्ययन हेतु है\n\n"
            "📩 संपर्क: @PhysioProbeAdmin"
        )
    },
    "terms": {
        "en": (
            "📄 Terms of Use\n\n"
            "• PhysioProbe does not own any content\n"
            "• Users are responsible for how materials are used\n"
            "• Content is provided for educational reference only\n"
            "• Copyright owners may request removal anytime\n\n"
            "Using this bot means you agree to these terms."
        ),
        "hi": (
            "📄 उपयोग की शर्तें\n\n"
            "• PhysioProbe किसी सामग्री का स्वामी नहीं है\n"
            "• सामग्री के उपयोग की ज़िम्मेदारी उपयोगकर्ता की है\n"
            "• सामग्री केवल शैक्षणिक संदर्भ के लिए है\n"
            "• कॉपीराइट मालिक हटाने का अनुरोध कर सकते हैं\n\n"
            "इस बॉट का उपयोग करने का अर्थ है इन शर्तों से सहमति।"
        )
    },
    "choose_lang": "Please choose language / भाषा चुनें",
    "join": {
        "en": "🔒 Please join @PhysioProbe to use this bot.",
        "hi": "🔒 इस बॉट के लिए @PhysioProbe जॉइन करें।"
    },
    "unlock": {
        "en": (
            "🔒 To use this bot, please:\n\n"
            "1️⃣ Join Telegram channel @PhysioProbe\n"
            "2️⃣ Subscribe to our YouTube channel\n"
            f"👉 {YOUTUBE_URL}\n\n"
            "After subscribing, click “I’ve Subscribed”"
        ),
        "hi": (
            "🔒 इस बॉट का उपयोग करने के लिए:\n\n"
            "1️⃣ Telegram चैनल @PhysioProbe जॉइन करें\n"
            "2️⃣ हमारा YouTube चैनल सब्सक्राइब करें\n"
            f"👉 {YOUTUBE_URL}\n\n"
            "सब्सक्राइब करने के बाद “मैंने सब्सक्राइब कर लिया है” पर क्लिक करें"
        )
    },
    "subscribed_btn": {
        "en": "I’ve Subscribed ✅",
        "hi": "मैंने सब्सक्राइब कर लिया है ✅"
    },
    "guidance": {
        "en": "I couldn’t clearly understand.\nTry:\n• neuro rehab\n• anatomy head & neck\n• ortho fracture",
        "hi": "विषय स्पष्ट नहीं है।\nऐसे खोजें:\n• neuro rehab\n• anatomy head & neck\n• ortho fracture"
    },
    "did_you_mean": {
        "en": "Did you mean:",
        "hi": "क्या आप यह कहना चाहते थे:"
    },
    "request_btn": {
        "en": "Request this book",
        "hi": "इस किताब को रिक्वेस्ट करें"
    },
    "results": {
        "en": "📚 Search Results",
        "hi": "📚 खोज परिणाम"
    },
    "size": {
        "en": "Size",
        "hi": "आकार"
    },
    "rating": {
        "en": "Rating",
        "hi": "रेटिंग"
    },
    "download": {
        "en": "Download",
        "hi": "डाउनलोड"
    },
    "rate_limit": {
        "en": "⏳ Please wait before another search.",
        "hi": "⏳ अगली खोज से पहले प्रतीक्षा करें।"
    },
    "request_received": {
        "en": "Your request has been received.",
        "hi": "आपकी रिक्वेस्ट प्राप्त हो गई है।"
    }
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
        return m.status in ("member","administrator","creator")
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
            "size": row.get("size_mb",""),
            "rating": row.get("rating","")
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
    all_keywords = set()
    for b in BOOKS:
        all_keywords.update(b["keywords"].split(","))
    return get_close_matches(query.lower(), all_keywords, n=5, cutoff=0.75)

# ================= COMMANDS =================

def start_cmd(update, context):
    kb = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="LANG::en")],
        [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="LANG::hi")]
    ]
    update.message.reply_text(TEXT["choose_lang"], reply_markup=InlineKeyboardMarkup(kb))

def language_callback(update, context):
    q = update.callback_query
    q.answer()
    lang = q.data.split("::")[1]
    save_language(q.from_user.id, lang)
    q.edit_message_text(
        TEXT["welcome"][lang] + "\n\n" + TEXT["disclaimer"][lang],
        parse_mode="Markdown"
    )

def about_cmd(update, context):
    lang = get_lang(update.effective_user.id)
    update.message.reply_text(TEXT["about"][lang])

def terms_cmd(update, context):
    lang = get_lang(update.effective_user.id)
    update.message.reply_text(TEXT["terms"][lang])

def reload_cmd(update, context):
    if update.effective_user.id == ADMIN_ID:
        load_books()
        update.message.reply_text("✅ Book database reloaded.")

def list_cmd(update, context):
    if update.effective_user.id == ADMIN_ID:
        update.message.reply_text("\n".join(b["title"] for b in BOOKS))

# ================= MESSAGE HANDLER =================

def handle_message(update, context):
    user = update.effective_user
    lang = get_lang(user.id)

    if not is_channel_member(context.bot, user.id):
        update.message.reply_text(TEXT["join"][lang])
        return

    if user.id not in UNLOCKED_USERS:
        kb = [[InlineKeyboardButton(TEXT["subscribed_btn"][lang], callback_data="YT_OK")]]
        update.message.reply_text(TEXT["unlock"][lang], reply_markup=InlineKeyboardMarkup(kb))
        return

    now = time.time()
    if now - LAST_QUERY_TIME.get(user.id, 0) < RATE_LIMIT_SECONDS:
        update.message.reply_text(TEXT["rate_limit"][lang])
        return
    LAST_QUERY_TIME[user.id] = now

    query = update.message.text.strip()
    results = search_books(query)

    if not results:
        sugg = spelling_suggestions(query)
        msg = TEXT["guidance"][lang]
        if sugg:
            msg += "\n\n" + TEXT["did_you_mean"][lang] + "\n" + "\n".join(f"• {s}" for s in sugg)

        kb = [[InlineKeyboardButton(TEXT["request_btn"][lang], callback_data=f"REQ::{query}")]]
        update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))
        return

    lines = [TEXT["results"][lang]]
    kb = []

    for i, b in enumerate(results, 1):
        size = b["size"] + " MB" if b["size"] else "—"
        lines.append(
            f"\n{i}. {b['title']}\n"
            f"{TEXT['size'][lang]}: {size}\n"
            f"{TEXT['rating'][lang]}: {stars(b['rating'])}"
        )
        kb.append([InlineKeyboardButton(f"{TEXT['download'][lang]} {i}", url=b["link"])])

    update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

# ================= CALLBACKS =================

def youtube_confirm(update, context):
    q = update.callback_query
    q.answer()
    UNLOCKED_USERS.add(q.from_user.id)
    q.edit_message_text(TEXT["welcome"][get_lang(q.from_user.id)], parse_mode="Markdown")

def handle_request(update, context):
    q = update.callback_query
    q.answer()
    lang = get_lang(q.from_user.id)

    try:
        requests.post(FORM_URL, data={
            ENTRY_USERNAME: q.from_user.username or q.from_user.first_name,
            ENTRY_USER_ID: str(q.from_user.id),
            ENTRY_BOOK: q.data.replace("REQ::",""),
            ENTRY_SOURCE: "bot"
        }, timeout=5)
    except:
        pass

    q.edit_message_text(TEXT["request_received"][lang])

# ================= MAIN =================

if __name__ == "__main__":
    load_books()
    load_languages()

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    updater.bot.send_message(ADMIN_ID, "🟢 PhysioProbe Bot is ONLINE / restarted")

    dp.add_handler(CommandHandler("start", start_cmd))
    dp.add_handler(CommandHandler("about", about_cmd))
    dp.add_handler(CommandHandler("terms", terms_cmd))
    dp.add_handler(CommandHandler("reload", reload_cmd))
    dp.add_handler(CommandHandler("list", list_cmd))

    dp.add_handler(CallbackQueryHandler(language_callback, pattern="^LANG::"))
    dp.add_handler(CallbackQueryHandler(youtube_confirm, pattern="^YT_OK$"))
    dp.add_handler(CallbackQueryHandler(handle_request, pattern="^REQ::"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()
