import datetime
import sqlite3
import logging
import json
import os

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- CONFIGURATION ----------------

TOKEN = os.getenv("BOT_TOKEN")  # Replace with your bot token
ADMIN_IDS = (6426448705, 6033766733, 7907820716)  # Replace with the admin's Telegram user ID (as an integer)
ADMIN_USERNAME = "rasmiyuzonadmin"  # Replace with the admin's username (without @)

# SQLite database to store ads
conn = sqlite3.connect("ads.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        media TEXT,         -- Will store a JSON array of media items [{"type": "photo", "file_id": "..."}, ...]
        media_type TEXT,    -- "photo", "video", or "mixed" (for informational purposes)
        caption TEXT,
        expire_at TEXT,
        region TEXT
    )
    """
)
conn.commit()

# ---------------- GLOBALS FOR MEDIA GROUPS & ADMIN PARAMETERS ----------------

# pending_media stores media group data for an ad.
# Key: (user_id, media_group_id), Value: dict with keys "files" (list of media dicts) and "caption"
pending_media = {}

# admin_params stores ad parameters chosen by the admin.
# Key: user_id, Value: dict with keys "ad_category" and "ad_duration"
admin_params = {}

# ---------------- DATA & CONSTANTS ----------------

# List of shop categories as tuples: (display name, callback value)
CATEGORIES = [
    ("🔥 Top", "top"),  # Top section
    ("👶 For Kids", "kids"),
    ("🏠 Real Estate", "real_estate"),
    ("🚗 Transport", "transport"),
    ("💼 Work", "work"),
    ("🐾 Pets", "pets"),
    ("🏡 Home & Garden", "home_garden"),
    ("📱 Electronics", "electronics"),
    ("👗 Clothes", "clothes"),
    ("📦 Others", "others"),
]

# List of regions as tuples: (display name, callback value)
REGIONS = [
    ("Toshkent shahar", "toshkent_shahar"),
    ("Toshkent", "toshkent"),
    ("Farg'ona", "fargona"),
    ("Namangan", "namangan"),
    ("Andijon", "andijon"),
    ("Jizzax", "jizzax"),
    ("Sirdaryo", "sirdaryo"),
    ("Navoiy", "navoiy"),
    ("Samarqand", "samarqand"),
    ("Buxoro", "buxoro"),
    ("Qashqadaryo", "qashqadaryo"),
    ("Surxondaryo", "surxondaryo"),
    ("Xorazm", "xorazm"),
    ("Qoraqalpog'iston", "qoraqalpogiston"),
]

# Time options for ads (display name, duration in days)
TIME_OPTIONS = [
    ("1 Day", 1),
    ("2 Days", 2),
    ("3 Days", 3),
    ("1 Week", 7),
    ("1 Month", 30),
]

LANGUAGES = {
    "uz": {
        "choose_language": "Tilni tanlang:",
        "main_menu": "Xush kelibsiz! Mentudan birini tanlang:",
        "shop": "🛍 Do'kon",
        "ads": "📢 E'lonlar",
        "contact_admin": f"📩 E'lon qo'shish uchun @{ADMIN_USERNAME} ga yozing.",
        "back": "🔙 Orqaga",
        # Translated categories
        "categories": {
            "top": "🔥 Eng yaxshi",
            "kids": "👶 Bolalar uchun",
            "real_estate": "🏠 Ko'chmas mulk",
            "transport": "🚗 Transport",
            "work": "💼 Ish",
            "pets": "🐾 Uy hayvonlari",
            "home_garden": "🏡 Uy va bog'",
            "electronics": "📱 Elektronika",
            "clothes": "👗 Kiyimlar",
            "others": "📦 Boshqalar",
        },
        # Translated regions
        "regions": {
            "toshkent_shahar": "Toshkent shahar",
            "toshkent": "Toshkent viloyati",
            "fargona": "Fargʻona",
            "namangan": "Namangan",
            "andijon": "Andijon",
            "jizzax": "Jizzax",
            "sirdaryo": "Sirdaryo",
            "navoiy": "Navoiy",
            "samarqand": "Samarqand",
            "buxoro": "Buxoro",
            "qashqadaryo": "Qashqadaryo",
            "surxondaryo": "Surxondaryo",
            "xorazm": "Xorazm",
            "qoraqalpogiston": "Qoraqalpogʻiston",
        },
    },
    "en": {
        "choose_language": "Choose your language:",
        "main_menu": "Welcome! Choose an option:",
        "shop": "🛍 Shop",
        "ads": "📢 Ads",
        "contact_admin": f"📩 Write to @{ADMIN_USERNAME} to place your ads.",
        "back": "🔙 Back",
        # Categories
        "categories": {
            "top": "🔥 Top",
            "kids": "👶 For Kids",
            "real_estate": "🏠 Real Estate",
            "transport": "🚗 Transport",
            "work": "💼 Work",
            "pets": "🐾 Pets",
            "home_garden": "🏡 Home & Garden",
            "electronics": "📱 Electronics",
            "clothes": "👗 Clothes",
            "others": "📦 Others",
        },
        # Regions
        "regions": {
            "toshkent_shahar": "Tashkent City",
            "toshkent": "Tashkent Region",
            "fargona": "Fergana",
            "namangan": "Namangan",
            "andijon": "Andijan",
            "jizzax": "Jizzakh",
            "sirdaryo": "Sirdarya",
            "navoiy": "Navoi",
            "samarqand": "Samarkand",
            "buxoro": "Bukhara",
            "qashqadaryo": "Kashkadarya",
            "surxondaryo": "Surkhandarya",
            "xorazm": "Khorezm",
            "qoraqalpogiston": "Karakalpakstan",
        },
    },
    "ru": {
        "choose_language": "Выберите язык:",
        "main_menu": "Добро пожаловать! Выберите опцию:",
        "shop": "🛍 Магазин",
        "ads": "📢 Объявления",
        "contact_admin": f"📩 Напишите @{ADMIN_USERNAME} для размещения объявлений.",
        "back": "🔙 Назад",
        # Categories
        "categories": {
            "top": "🔥 Топ",
            "kids": "👶 Для детей",
            "real_estate": "🏠 Недвижимость",
            "transport": "🚗 Транспорт",
            "work": "💼 Работа",
            "pets": "🐾 Животные",
            "home_garden": "🏡 Дом и сад",
            "electronics": "📱 Электроника",
            "clothes": "👗 Одежда",
            "others": "📦 Другое",
        },
        # Regions
        "regions": {
            "toshkent_shahar": "Город Ташкент",
            "toshkent": "Ташкентская область",
            "fargona": "Фергана",
            "namangan": "Наманган",
            "andijon": "Андижан",
            "jizzax": "Джиззах",
            "sirdaryo": "Сырдарья",
            "navoiy": "Навои",
            "samarqand": "Самарканд",
            "buxoro": "Бухара",
            "qashqadaryo": "Кашкадарья",
            "surxondaryo": "Сурхандарья",
            "xorazm": "Хорезм",
            "qoraqalpogiston": "Каракалпакстан",
        },
    },
}



# ---------------- HELPER FUNCTION TO SEND MAIN MENU ----------------

async def send_main_menu_for_chat(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛍 Shop", callback_data="shop")],
        [InlineKeyboardButton("📢 Ads", callback_data="ads")],
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("➕ Add Ad", callback_data="add_ad")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id, "Welcome! Choose an option:", reply_markup=reply_markup)


# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask the user to choose a language before showing the main menu."""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("O'zbekcha", callback_data="lang_uz")],
        [InlineKeyboardButton("English", callback_data="lang_en")],
        [InlineKeyboardButton("Русский", callback_data="lang_ru")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose your language / Tilni tanlang / Выберите язык:", reply_markup=reply_markup)


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    selected_lang = query.data.split("_")[1]  # Extract selected language (e.g., "uz", "en", "ru")
    context.user_data["lang"] = selected_lang  # Save the language in user data
    await query.answer()
    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data.get("lang", "en")  # Default to English if no language is set
    messages = LANGUAGES[lang]
    keyboard = [
        [InlineKeyboardButton(messages["shop"], callback_data="shop")],
        [InlineKeyboardButton(messages["ads"], callback_data="ads")],
    ]
    if update.effective_user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("➕ Add Ad", callback_data="add_ad")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = messages["main_menu"]
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Helper function to send the main menu (for callback queries)."""
    keyboard = [
        [InlineKeyboardButton("🛍 Shop", callback_data="shop")],
        [InlineKeyboardButton("📢 Ads", callback_data="ads")],
    ]
    if update.effective_user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("➕ Add Ad", callback_data="add_ad")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.message.edit_text("Welcome! Choose an option:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Welcome! Choose an option:", reply_markup=reply_markup)


# ----- SHOP & CATEGORY HANDLERS -----


async def show_category_regions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    lang = context.user_data.get("lang", "en")  # Default to English
    messages = LANGUAGES[lang]
    await query.answer()

    selected_category = query.data.split("_")[-1]
    context.user_data["selected_category"] = selected_category

    keyboard = [
        [InlineKeyboardButton(messages["regions"][callback],
                              callback_data=f"shop_filter_{selected_category}_{callback}")]
        for _, callback in REGIONS
    ]
    keyboard.append([InlineKeyboardButton(messages["back"], callback_data="shop")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(messages["shop"], reply_markup=reply_markup)


async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data.get("lang", "en")  # Default to English
    messages = LANGUAGES[lang]
    categories = CATEGORIES
    keyboard = [
        [InlineKeyboardButton(messages["categories"][callback], callback_data=f"shop_category_{callback}")]
        for _, callback in categories
    ]
    keyboard.append([InlineKeyboardButton(messages["back"], callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(messages["shop"], reply_markup=reply_markup)


async def show_top_ads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    await query.answer()

    now_iso = datetime.datetime.now().isoformat()
    cursor.execute(
        "SELECT media, media_type, caption FROM ads WHERE expire_at > ? ORDER BY id DESC LIMIT 10",
        (now_iso,),
    )
    rows = cursor.fetchall()

    if not rows:
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="shop")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("❌ Нет топовых объявлений.", reply_markup=reply_markup)
        return

    for media_json, media_type, caption in rows:
        try:
            media_items = json.loads(media_json)
        except Exception as e:
            logger.error(f"Ошибка при обработке JSON медиа: {e}")
            continue

        media_group = []
        for idx, item in enumerate(media_items):
            if item.get("type") == "photo":
                media_group.append(InputMediaPhoto(item["file_id"], caption=caption if idx == 0 else None))
            elif item.get("type") == "video":
                media_group.append(InputMediaVideo(item["file_id"], caption=caption if idx == 0 else None))
        try:
            await query.message.reply_media_group(media_group)
        except Exception as e:
            logger.error(f"Ошибка отправки медиа-группы: {e}")

    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="shop")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("🔙 Назад", reply_markup=reply_markup)


async def show_filtered_ads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display ads filtered by selected category and region."""
    query = update.callback_query
    await query.answer()

    # Extract category and region from callback data
    parts = query.data.split("_")  # Example: shop_filter_work_urban
    if len(parts) < 4:
        await query.message.edit_text("⚠️ Error: Invalid selection. Please try again.")
        return

    selected_category = parts[2]  # "work"
    selected_region = parts[3]  # "urban"
    now_iso = datetime.datetime.now().isoformat()

    # Fetch ads matching both category and region
    cursor.execute(
        "SELECT media, media_type, caption FROM ads WHERE category=? AND region=? AND expire_at > ?",
        (selected_category, selected_region, now_iso),
    )
    rows = cursor.fetchall()

    # Handle cases with no ads
    if not rows:
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="shop")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "❌ No ads found for your selection. Try a different region or category.",
            reply_markup=reply_markup
        )
        return

    # Display the ads (media items + captions)
    for media_json, media_type, caption in rows:
        try:
            media_items = json.loads(media_json)
        except Exception as e:
            logger.error(f"Error parsing media JSON: {e}")
            continue

        media_group = []
        for idx, item in enumerate(media_items):
            if item.get("type") == "photo":
                media_group.append(
                    InputMediaPhoto(item["file_id"], caption=caption if idx == 0 else None)
                )
            elif item.get("type") == "video":
                media_group.append(
                    InputMediaVideo(item["file_id"], caption=caption if idx == 0 else None)
                )

        # Send media group
        try:
            await query.message.reply_media_group(media_group)
        except Exception as e:
            logger.error(f"Error sending media group: {e}")

    # Add a Back button
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="shop")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("🔙 Back to Shop", reply_markup=reply_markup)


# ----- ADS (Contact Admin) HANDLER -----

async def ads_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = context.user_data.get("lang", "en")
    messages = LANGUAGES[lang]
    query = update.callback_query
    await query.answer()
    text = messages["contact_admin"]
    keyboard = [[InlineKeyboardButton(messages["back"], callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(text, reply_markup=reply_markup)


# ----- ADMIN ADD AD HANDLERS -----

async def add_ad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """For admins: show time options for ad duration."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        return
    keyboard = [
        [InlineKeyboardButton(text, callback_data=f"ad_duration_{days}")]
        for text, days in TIME_OPTIONS
    ]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("🕒 Select ad duration:", reply_markup=reply_markup)


async def set_ad_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store the selected duration and prompt for category."""
    query = update.callback_query
    await query.answer()
    try:
        duration = int(query.data.split("_")[2])
    except (IndexError, ValueError):
        return
    admin_params[update.effective_user.id] = {"ad_duration": duration}
    keyboard = [
        [InlineKeyboardButton(text, callback_data=f"ad_category_{callback}")]
        for text, callback in CATEGORIES
    ]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="add_ad")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("📂 Select category for your ad:", reply_markup=reply_markup)


async def set_ad_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store the selected category and prompt admin to select region."""
    query = update.callback_query
    await query.answer()

    try:
        category = query.data.split("_")[2]
    except IndexError:
        return

    if update.effective_user.id not in admin_params:
        admin_params[update.effective_user.id] = {}
    admin_params[update.effective_user.id]["ad_category"] = category

    # Prompt the admin to select a region
    keyboard = [
        [InlineKeyboardButton(text, callback_data=f"ad_region_{callback}")]
        for text, callback in REGIONS
    ]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="add_ad")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("📍 Select region for your ad:", reply_markup=reply_markup)


async def set_ad_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store the selected region and prompt the admin to send the post for the ad."""
    query = update.callback_query
    await query.answer()

    try:
        # Extract the selected region from the callback query data
        selected_region = query.data.split("_")[2]
    except IndexError:
        await query.message.edit_text("⚠️ Failed to get the selected region. Please try again.")
        return

    user_id = update.effective_user.id

    # Check if we've already initialized admin parameters
    if user_id not in admin_params:
        admin_params[user_id] = {}

    # Store the selected region in the admin_params dictionary
    admin_params[user_id]["ad_region"] = selected_region
    logger.info(f"Region set for user {user_id}: {selected_region}")

    # Prompt the admin to send the ad content
    await query.message.edit_text(
        "📸 Region is set! Now send the ad content (photos/videos and a caption)."
    )


# ----- RECEIVING THE AD POST (WITH MEDIA GROUP SUPPORT & HANDLING MIXED TYPES) -----

async def receive_ad_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive the ad post from the admin and store it."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    # Validate admin parameters (must include category, duration, and region)
    params = admin_params.get(user.id)
    if not params or not all(k in params for k in ["ad_category", "ad_duration", "ad_region"]):
        await update.message.reply_text(
            "⚠️ Missing parameters. Please start the ad creation process from the beginning."
        )
        return

    # Prepare media item dictionary for the message
    media_item = None
    if update.message.photo:
        # Use the highest resolution photo
        media_item = {"type": "photo", "file_id": update.message.photo[-1].file_id}
    elif update.message.video:
        # Use the video file
        media_item = {"type": "video", "file_id": update.message.video.file_id}

    # If no media is received, notify the admin
    if not media_item:
        await update.message.reply_text("⚠️ Please send a photo or video for your ad.")
        return

    # Handle immediately processing single media items
    media_items = [media_item]
    caption = update.message.caption if update.message.caption else ""
    media_type = "photo" if update.message.photo else "video"

    # Store the ad
    await store_ad(user.id, media_items, media_type, caption, update, context)


async def process_media_group(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback to process an accumulated media group."""
    job_data = context.job.data
    group_key = job_data["group_key"]
    chat_id = job_data["chat_id"]
    user_id = job_data["user_id"]
    ad_data = pending_media.pop(group_key, None)
    if ad_data is None:
        return

    params = admin_params.get(user_id)
    if not params:
        await context.bot.send_message(chat_id, "⚠️ Missing ad parameters. Please start over.")
        return

    ad_category = params["ad_category"]
    ad_duration = params["ad_duration"]
    expire_at = datetime.datetime.now() + datetime.timedelta(days=ad_duration)
    media_items = ad_data["files"]  # This is now a list of dicts.
    caption = ad_data["caption"] if ad_data["caption"] else ""
    if len(media_items) == 1:
        media_type = media_items[0]["type"]
    else:
        media_type = "mixed"
    # Store the JSON string of media items.
    media_json = json.dumps(media_items)
    cursor.execute(
        "INSERT INTO ads (category, media, media_type, caption, expire_at) VALUES (?, ?, ?, ?, ?)",
        (ad_category, media_json, media_type, caption, expire_at.isoformat()),
    )
    conn.commit()
    admin_params.pop(user_id, None)
    await context.bot.send_message(chat_id, "✅ Ad added successfully!")
    await send_main_menu_for_chat(chat_id, user_id, context)


async def delete_expired_ads(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete ads that have reached their time limit."""
    now_iso = datetime.datetime.now().isoformat()
    cursor.execute("DELETE FROM ads WHERE expire_at <= ?", (now_iso,))
    conn.commit()
    logger.info("Deleted expired ads.")


async def store_ad(user_id: int, media_items: list, media_type: str, caption: str, update: Update,
                   context: ContextTypes.DEFAULT_TYPE) -> None:
    """Helper function to store a non-media-group ad and then return to the main menu."""
    # Get the admin parameters (category, duration, region)
    params = admin_params.get(user_id)
    if not params:
        await update.message.reply_text("⚠️ Missing ad parameters. Please start over.")
        return

    ad_category = params.get("ad_category")  # Previously set category
    ad_duration = params.get("ad_duration")  # Previously set duration
    ad_region = params.get("ad_region")  # Previously set region

    if not (ad_category and ad_duration and ad_region):
        await update.message.reply_text("⚠️ Missing parameters (category, duration, or region). Please start over.")
        return

    # Calculate the expiration date for the ad
    expire_at = datetime.datetime.now() + datetime.timedelta(days=ad_duration)

    # Serialize media items into JSON
    media_json = json.dumps(media_items)

    # Store the ad in the database
    cursor.execute(
        "INSERT INTO ads (category, region, media, media_type, caption, expire_at) VALUES (?, ?, ?, ?, ?, ?)",
        (ad_category, ad_region, media_json, media_type, caption, expire_at.isoformat()),
    )
    conn.commit()

    # Clear the admin's session data
    admin_params.pop(user_id, None)

    # Notify admin that the ad has been added and return to the main menu
    await update.message.reply_text("✅ Ad added successfully!")
    await send_main_menu_for_chat(update.effective_chat.id, user_id, context)


# ---------------- BACK BUTTON HANDLER ----------------

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles back button callbacks that return to the main menu."""
    query = update.callback_query
    await query.answer()
    await main_menu(update, context)


# ---------------- MAIN FUNCTION ----------------

def main() -> None:
    app = Application.builder().token(TOKEN).build()

    # Command handler
    app.add_handler(CommandHandler("start", start))

    # CallbackQuery handlers
    app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(shop_menu, pattern="^shop$"))
    app.add_handler(CallbackQueryHandler(show_category_regions, pattern="^shop_category_"))
    app.add_handler(CallbackQueryHandler(show_filtered_ads, pattern="^shop_filter_"))
    app.add_handler(CallbackQueryHandler(ads_info, pattern="^ads$"))
    app.add_handler(CallbackQueryHandler(add_ad, pattern="^add_ad$"))
    app.add_handler(CallbackQueryHandler(set_ad_duration, pattern="^ad_duration_"))
    app.add_handler(CallbackQueryHandler(set_ad_category, pattern="^ad_category_"))
    app.add_handler(CallbackQueryHandler(set_ad_region, pattern="^ad_region_"))
    app.add_handler(CallbackQueryHandler(back_handler, pattern="^back$"))
    app.add_handler(CallbackQueryHandler(show_top_ads, pattern="^shop_top$"))
    app.job_queue.run_repeating(delete_expired_ads, interval=3600, first=10)

    # Message handler for receiving ad posts (photos/videos, including media groups)
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, receive_ad_post))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
