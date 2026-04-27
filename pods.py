import asyncio
from aiohttp import web
import logging
from datetime import datetime, timedelta
import aiosqlite
from cachetools import TTLCache
import os
import re
import time
from datetime import timedelta
import sys
from contextlib import asynccontextmanager
from PIL import Image, ImageDraw, ImageFont
import io
import tempfile
import html
import random
import hashlib
import hmac
import json
from urllib.parse import unquote

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile,
    WebAppInfo
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties


# ================= КОНФИГУРАЦИЯ =================

TOKEN = os.getenv('BOT_TOKEN', "8587934352:AAHdfiuD0VrNQ-Dp0801dYNnR7_nae92Aso")
CHANNEL_ID = int(os.getenv('CHANNEL_ID', "-1003713957228"))
SUPER_ADMIN = int(os.getenv('SUPER_ADMIN', "8438783644"))
ADMINS = [int(x) for x in os.getenv('ADMINS', "8438783644,8488564574,8283468381").split(',')]
BOT_USERNAME = os.getenv('BOT_USERNAME', "pods10_bot")
WEB_APP_URL = os.getenv('WEB_APP_URL', "https://your-app.vercel.app")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= КОНСТАНТЫ =================

NIGHT_MODE_START = 0
NIGHT_MODE_END = 8
NIGHT_POST_INTERVAL = 30
AUTO_POST_INTERVAL = 5
INSULT_THRESHOLD = 4
LONG_MESSAGE_THRESHOLD = 60

# ================= ИНИЦИАЛИЗАЦИЯ =================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Кэши
user_cache = TTLCache(maxsize=1000, ttl=300)
msg_cache = TTLCache(maxsize=500, ttl=60)
admin_cache = TTLCache(maxsize=100, ttl=60)
pending_cache = TTLCache(maxsize=200, ttl=30)
blacklist_cache = TTLCache(maxsize=1000, ttl=300)
user_message_cooldown = TTLCache(maxsize=1000, ttl=1800)
captcha_cache = TTLCache(maxsize=1000, ttl=600)  # Для хранения капчи
faq_cache = TTLCache(maxsize=100, ttl=3600)  # Кэш FAQ
poll_cooldown = TTLCache(maxsize=1000, ttl=30)

# Флаги
night_mode_enabled = False
auto_mode_enabled = False
maintenance_mode = False
maintenance_exceptions = set()
shutdown_flag = False
start_time = time.time()

# Блокировка для публикации
publish_lock = asyncio.Lock()

# ================= БАЗОВЫЕ СПИСКИ СЛОВ =================

DEFAULT_INSULTS = [
    # ДУРАК / ТУПОСТЬ
    "дурак", "дурака", "дураку", "дураком", "дураке", "дураки", "дураков",
    "дура", "дуры", "дуре", "дуру", "дурой",
    "дурачок", "дурачка", "дурачку",
    "идиот", "идиота", "идиоту", "идиотом", "идиотка",
    "тупой", "тупого", "тупая", "тупую", "тупые",
    "тупица", "тупицы",
    "дебил", "дебила", "дебилу", "дебилы",
    "глупый", "глупого", "глупость",
    
    # ЖИВОТНЫЕ
    "козел", "козла", "козлу", "козлы",
    "баран", "барана", "барану", "бараны",
    "осел", "осла", "ослу", "ослы",
    "свинья", "свиньи", "свинью",
    "собака", "собаки", "псина",
    "овца", "овцы",
    "корова", "коровы",
    "обезьяна", "обезьяны",
    
    # НЕГАТИВНЫЕ ЛИЧНОСТИ
    "сволочь", "сволочи",
    "гад", "гада", "гады",
    "тварь", "твари",
    "урод", "урода", "уроды",
    "мудак", "мудака", "мудаки",
    "придурок", "придурка",
    "лох", "лоха", "лохи",
    "чмо", "чма",
    "падла", "падлы",
    "гнида", "гниды",
    "мразь", "мрази",
    "скотина", "скотины",
    "стерва", "стервы",
    
    # МАТ
    "хуй", "хуя", "хую", "хуем",
    "хуйня", "хуйни",
    "пизда", "пизды", "пизде",
    "пиздец", "пиздеца",
    "блядь", "бляди", "бля",
    "сука", "суки", "суку", "сучка",
    "ебать", "ебу", "ебет", "ебал",
    "пидор", "пидора", "пидоры",
    "залупа", "залупы",
    "гандон", "гандона",
    "шлюха", "шлюхи",
    "долбоеб", "долбоеба",
    "еблан", "еблана",
    
    # НАЦИОНАЛЬНЫЕ
    "чурка", "чурки",
    "хач", "хача", "хачи",
    "жид", "жида", "жиды",
    "хохол", "хохла",
    "кацап", "кацапа",
]

IMMORAL_CONTENT = [
    "секс", "секса", "сексу",
    "порно", "порна",
    "эротика", "эротики",
    "голая", "голой", "голые",
    "обнаженная", "обнаженной",
    "писька", "письки",
    "попа", "попы",
    "жопа", "жопы",
    "сиськи", "сисек",
    "член", "члена",
    "вагина", "вагины",
    "лизать", "лижет",
    "сосать", "сосет",
    "кончить", "кончил",
    "сперма", "спермы",
    "трахнуть", "трахнул",
    "минет", "минета",
    "гей", "гея", "геи",
    "лесбиянка", "лесбиянки",
    "инцест", "инцеста",
    "педофил", "педофила",
    "зоофил", "зоофила",
]

IMMORAL_PATTERNS = [re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE) for word in IMMORAL_CONTENT]

URL_PATTERNS = [
    r'https?://\S+',
    r't\.me/\S+',
    r'@\w+',
    r'(?:www\.)\S+',
    r'\S+\.(ru|com|org|net|рф|su|xyz|top|club|site)\b',
    r'(?:telegram|tg)\.me/\S+',
    r'bit\.ly/\S+',
    r'goo\.gl/\S+',
    r'vk\.com/\S+',
    r'youtube\.com/\S+',
    r'youtu\.be/\S+',
    r'instagram\.com/\S+',
    r'tiktok\.com/\S+'
]

MAINTENANCE_MESSAGE = (
    "🔧 <b>Технические работы</b>\n\n"
    "В настоящее время проводятся технические работы. "
    "Воспользоваться ботом временно невозможно.\n\n"
    "Приносим извинения за неудобства!"
)

# ================= ФУНКЦИЯ ЭКРАНИРОВАНИЯ HTML =================

def escape_html(text: str) -> str:
    """Экранирует HTML-теги в тексте"""
    if not text:
        return ""
    return html.escape(text, quote=False)

# ================= СОСТОЯНИЯ FSM =================

class AdminStates(StatesGroup):
    waiting_for_user_search = State()
    waiting_for_exception_add = State()
    waiting_for_exception_remove = State()
    waiting_for_blacklist_add = State()
    waiting_for_blacklist_remove = State()
    waiting_for_mute_duration = State()
    waiting_for_mute_user = State()
    waiting_for_admin_message = State()
    waiting_for_reply_text = State()
    waiting_for_captcha = State()
    waiting_for_poll_question = State()
    waiting_for_poll_options = State()
    waiting_for_faq_question = State()
    waiting_for_faq_add = State()

# ================= ПУЛ БАЗЫ ДАННЫХ =================

class DatabasePool:
    def __init__(self, db_path="bot.db", max_connections=5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._connections = []
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def acquire(self):
        async with self._lock:
            if not self._connections:
                conn = await aiosqlite.connect(self.db_path)
                await conn.execute("PRAGMA journal_mode = WAL")
                await conn.execute("PRAGMA synchronous = NORMAL")
                await conn.execute("PRAGMA busy_timeout = 5000")
                self._connections.append(conn)
            conn = self._connections.pop()
        try:
            yield conn
        finally:
            async with self._lock:
                self._connections.append(conn)
    
    async def close_all(self):
        for conn in self._connections:
            await conn.close()
        self._connections.clear()

db_pool = DatabasePool()

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================

def has_links(text: str) -> bool:
    if not text:
        return False
    for pattern in URL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def count_insults_with_blacklist(text: str) -> int:
    if not text:
        return 0
    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    count = 0
    for word in words:
        if word in blacklist_cache:
            count += 1
    return count

def has_immoral_content(text: str) -> bool:
    if not text:
        return False
    for pattern in IMMORAL_PATTERNS:
        if pattern.search(text):
            return True
    return False

def get_current_mode_and_interval():
    now_utc = datetime.utcnow()
    now_msk = now_utc + timedelta(hours=3)
    hour = now_msk.hour
    
    if hour < 8:
        if night_mode_enabled:
            return 'night', NIGHT_POST_INTERVAL
        else:
            return 'night_disabled', NIGHT_POST_INTERVAL
    else:
        if auto_mode_enabled:
            return 'auto', AUTO_POST_INTERVAL
        else:
            return 'auto_disabled', AUTO_POST_INTERVAL

def can_auto_post_now() -> bool:
    now_utc = datetime.utcnow()
    now_msk = now_utc + timedelta(hours=3)
    hour = now_msk.hour
    
    if hour < 8:
        return night_mode_enabled
    else:
        return auto_mode_enabled

# ================= ГЕНЕРАЦИЯ КАПЧИ =================

def generate_captcha() -> tuple:
    """Генерирует простую математическую капчу"""
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    operations = ['+', '-', '*']
    op = random.choice(operations)
    
    if op == '+':
        answer = a + b
        question = f"{a} + {b}"
    elif op == '-':
        answer = a - b
        question = f"{a} - {b}"
    else:
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        answer = a * b
        question = f"{a} × {b}"
    
    return question, str(answer)

# ================= ИНИЦИАЛИЗАЦИЯ БД =================

async def load_blacklist_to_cache():
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT word FROM blacklist")
            words = await cursor.fetchall()
            blacklist_cache.clear()
            for word in words:
                blacklist_cache[word[0]] = True
        logger.info(f"Загружено {len(blacklist_cache)} слов")
    except Exception as e:
        logger.error(f"Ошибка загрузки черного списка: {e}")

async def load_faq_to_cache():
    """Загружает FAQ в кэш"""
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT keywords, answer FROM faq")
            faqs = await cursor.fetchall()
            faq_cache.clear()
            for keywords, answer in faqs:
                for keyword in keywords.split(','):
                    keyword = keyword.strip().lower()
                    faq_cache[keyword] = answer
        logger.info(f"Загружено {len(faqs)} FAQ записей")
    except Exception as e:
        logger.error(f"Ошибка загрузки FAQ: {e}")

async def init_db():
    async with db_pool.acquire() as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            banned INTEGER DEFAULT 0,
            mute_until TEXT,
            last_message TEXT,
            username TEXT,
            first_name TEXT,
            maintenance_exception INTEGER DEFAULT 0,
            captcha_passed INTEGER DEFAULT 0
        )
        """)
        
        # ========== ДОБАВЬ ЭТОТ БЛОК (сразу после создания таблицы users) ==========
        # Проверяем и добавляем колонку captcha_passed если её нет
        try:
            await db.execute("ALTER TABLE users ADD COLUMN captcha_passed INTEGER DEFAULT 0")
            await db.commit()
            logger.info("✅ Добавлена колонка captcha_passed в таблицу users")
        except:
            pass  # Колонка уже существует
        # ========================================================================
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            media_type TEXT,
            media_file_id TEXT,
            media_file_path TEXT,
            status TEXT DEFAULT 'pending',
            reviewer INTEGER,
            created_at TEXT,
            reviewed_at TEXT,
            auto_posted INTEGER DEFAULT 0,
            has_links INTEGER DEFAULT 0,
            insult_count INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            poll_data TEXT
        )
        """)
        
        try:
            await db.execute("ALTER TABLE messages ADD COLUMN notified_long INTEGER DEFAULT 0")
        except:
            pass
        
        try:
            await db.execute("ALTER TABLE messages ADD COLUMN poll_data TEXT")
        except:
            pass
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS ban_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            admin_id INTEGER,
            message_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS blacklist(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE,
            added_by INTEGER,
            created_at TEXT
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_actions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_id INTEGER,
            details TEXT,
            created_at TEXT
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'new'
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reply_states(
            admin_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            msg_id INTEGER,
            reply_type TEXT,
            created_at TEXT
        )
        """)
        
        # Таблица для FAQ
        await db.execute("""
        CREATE TABLE IF NOT EXISTS faq(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            keywords TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
        """)
        
        for word in DEFAULT_INSULTS:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO blacklist (word, added_by, created_at) VALUES (?, ?, ?)",
                    (word, SUPER_ADMIN, datetime.utcnow().isoformat())
                )
            except:
                pass
        
        await db.execute("INSERT OR IGNORE INTO settings VALUES('post_counter','0')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES('post_style','1')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES('night_mode','0')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES('auto_mode','0')")
        await db.execute("INSERT OR IGNORE INTO settings VALUES('maintenance','0')")
        await db.commit()
    
    await load_blacklist_to_cache()
    await load_faq_to_cache()
    
    # Добавляем базовые FAQ если пусто
    async with db_pool.acquire() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM faq")
        count = (await cursor.fetchone())[0]
        
        if count == 0:
            default_faq = [
                ("Как отправить сообщение?", "Просто напишите текст, фото или видео в этот чат. Сообщение будет опубликовано анонимно после проверки модератором.", "отправить,сообщение,написать,пост"),
                ("Сколько ждать публикацию?", "Обычно сообщения проверяются в течение 24 часов. Фото и видео всегда проходят ручную модерацию.", "ждать,публикация,долго,скоро,когда"),
                ("Почему отклонили сообщение?", "Возможные причины: наличие ссылок, сильная травля, реклама, спам или аморальный контент.", "отклонили,почему,отказ,не опубликовали"),
                ("Какие правила?", "Запрещены: ссылки на сторонние ресурсы, сильная травля, реклама, спам. Фото и видео проходят ручную модерацию.", "правила,запрещено,нельзя,можно"),
                ("Как создать опрос?", "Нажмите кнопку '📊 Создать опрос' в меню. Опросы проходят модерацию и публикуются анонимно.", "опрос,создать,голосование"),
            ]
            
            for question, answer, keywords in default_faq:
                await db.execute(
                    "INSERT INTO faq (question, answer, keywords, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                    (question, answer, keywords, SUPER_ADMIN, datetime.utcnow().isoformat())
                )
            
            await db.commit()
            logger.info("Добавлены базовые FAQ")

## ================= ВОДЯНОЙ ЗНАК =================

async def add_watermark_to_photo(photo_file_id: str) -> str:
    """Накладывает водяной знак на фото"""
    try:
        file = await bot.get_file(photo_file_id)
        photo_bytes = await bot.download_file(file.file_path)

        img = Image.open(photo_bytes).convert("RGBA")
        width, height = img.size

        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        text = "@podslu10"
        font_size = max(16, int(width * 0.04))
        
        font = None
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        fill_color = (0, 0, 0, 0)

        positions_x = [int(width * 0.12), int(width * 0.5), int(width * 0.88)]
        positions_y = []
        for i in range(5):
            y = int(height * (0.1 + i * 0.2))
            positions_y.append(y)

        for col, x in enumerate(positions_x):
            for row, y in enumerate(positions_y):
                offset_x = int(text_width * 0.2) * (hash(f"{col}{row}") % 3 - 1)
                offset_y = int(text_height * 0.2) * (hash(f"{col}{row}") % 3 - 1)
                
                final_x = x + offset_x
                final_y = y + offset_y
                
                draw_x = final_x - text_width // 2
                draw_y = final_y - text_height // 2
                
                draw.text((draw_x, draw_y), text, font=font, fill=fill_color)

        center_watermark_path = "watermark_center.png"
        
        if os.path.exists(center_watermark_path):
            try:
                center_img = Image.open(center_watermark_path).convert("RGBA")
                c_width, c_height = center_img.size
                target_size = int(width * 0.4)
                ratio = min(target_size / c_width, target_size / c_height)
                new_size = (int(c_width * ratio), int(c_height * ratio))
                center_img = center_img.resize(new_size, Image.Resampling.LANCZOS)
                
                center_array = center_img.getdata()
                new_center_array = []
                for item in center_array:
                    if item[3] > 0:
                        new_center_array.append((item[0], item[1], item[2], 155))
                    else:
                        new_center_array.append(item)
                
                center_img.putdata(new_center_array)
                
                center_x = (width - new_size[0]) // 2
                center_y = (height - new_size[1]) // 2
                
                center_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
                center_layer.paste(center_img, (center_x, center_y), center_img)
                
                combined_layer = Image.alpha_composite(txt_layer, center_layer)
            except Exception as e:
                logger.error(f"Error adding center watermark: {e}")
                combined_layer = txt_layer
        else:
            combined_layer = txt_layer

        watermarked = Image.alpha_composite(img, combined_layer).convert("RGB")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            temp_path = tmp_file.name
            watermarked.save(temp_path, format="JPEG", quality=95)

        msg = await bot.send_photo(
            chat_id=SUPER_ADMIN,
            photo=FSInputFile(temp_path)
        )
        
        new_file_id = msg.photo[-1].file_id
        os.unlink(temp_path)
        
        logger.info(f"Watermark added successfully")
        return new_file_id

    except Exception as e:
        logger.error(f"Watermark error: {e}")
        return photo_file_id

# ================= ЛОГИРОВАНИЕ =================

async def log_action(text):
    logger.info(f"ACTION: {text}")
    if not shutdown_flag:
        try:
            await bot.send_message(SUPER_ADMIN, f"📜 <b>ЛОГ</b>\n\n{text}")
        except:
            pass

def log_user_action(user_id: int, action: str, details: str = ""):
    logger.info(f"USER {user_id}: {action} {details}")

async def log_admin_action(admin_id: int, action: str, target_id: int = None, details: str = ""):
    try:
        async with db_pool.acquire() as db:
            await db.execute(
                "INSERT INTO admin_actions (admin_id, action, target_id, details, created_at) VALUES (?, ?, ?, ?, ?)",
                (admin_id, action, target_id, details, datetime.utcnow().isoformat())
            )
            await db.commit()
        logger.info(f"ADMIN ACTION: {admin_id} - {action} - {target_id} - {details}")
    except Exception as e:
        logger.error(f"Error logging admin action: {e}")

# ================= АВТОМАТИЧЕСКАЯ ПУБЛИКАЦИЯ =================

async def notify_admins_about_auto_post(msg_id: int, user_id: int, media_type: str, counter: int, mode: str):
    if shutdown_flag:
        return
    
    mode_text = "🌙 Ночной режим" if mode == 'night' else "☀️ Автоматический режим"
    interval_text = "30 мин" if mode == 'night' else "5 мин"
    
    text = (
        f"🤖 <b>Автоматическая публикация</b>\n\n"
        f"{mode_text}\n"
        f"Интервал: {interval_text}\n"
        f"Сообщение #{msg_id}\n"
        f"Номер поста: #{counter}\n"
        f"Тип: {media_type}"
    )
    
    for admin in ADMINS:
        try:
            if admin == SUPER_ADMIN:
                await bot.send_message(admin, text + f"\nОт пользователя: <code>{user_id}</code>")
            else:
                await bot.send_message(admin, text)
            await asyncio.sleep(0.1)
        except:
            pass

async def post_next_message():
    """Публикует следующее сообщение из очереди"""
    async with publish_lock:
        try:
            async with db_pool.acquire() as db:
                await db.execute("BEGIN TRANSACTION")
                
                try:
                    cursor = await db.execute("""
                        SELECT id, user_id, text, media_type, media_file_id, has_links, insult_count, poll_data
                        FROM messages 
                        WHERE status='pending' AND reviewer IS NULL AND skipped=0
                        ORDER BY created_at ASC 
                        LIMIT 1
                    """)
                    message = await cursor.fetchone()
                    
                    if not message:
                        await db.execute("ROLLBACK")
                        return
                    
                    msg_id, user_id, text, media_type, media_file_id, has_links, insult_count, poll_data = message
                    has_immoral = has_immoral_content(text) if text else False
                    
                    can_auto_post = (
                        media_type is None and
                        not has_links and
                        not has_immoral and
                        insult_count < INSULT_THRESHOLD and
                        not poll_data
                    )
                    
                    if not can_auto_post:
                        await db.execute("ROLLBACK")
                        return
                    
                    await db.execute("""
                        UPDATE messages 
                        SET status='processing', reviewed_at=? 
                        WHERE id=? AND status='pending'
                    """, (datetime.utcnow().isoformat(), msg_id))
                    
                    cursor = await db.execute("SELECT value FROM settings WHERE key='post_counter'")
                    counter = int((await cursor.fetchone())[0]) + 1
                    await db.execute("UPDATE settings SET value=? WHERE key='post_counter'", (str(counter),))
                    
                    await db.commit()
                    
                except Exception as e:
                    await db.execute("ROLLBACK")
                    logger.error(f"DB error in post_next_message: {e}")
                    return
            
            async with db_pool.acquire() as db:
                cursor = await db.execute("SELECT value FROM settings WHERE key='post_style'")
                style = (await cursor.fetchone())[0]
            
            escaped_text = escape_html(text) if text else ""
            
            if style == "1":
                header = f"💬 <b>Новое анонимное сообщение</b>\n\n"
                footer = f"\n\n━━━━━━━━━━━━━━\n✉ <a href='https://t.me/{BOT_USERNAME}'>Отправить сообщение</a>"
            elif style == "2":
                header = f"┌─────────────────┐\n│  ПОДСЛУШАНО  │\n└─────────────────┘\n\n"
                footer = f"\n\n➖➖➖➖➖➖➖➖➖\n✉ <a href='https://t.me/{BOT_USERNAME}'>Написать анонимно</a>"
            else:
                header = f"📌 <b>Анонимное сообщение</b>\n\n"
                footer = f"\n\n—\n<a href='https://t.me/{BOT_USERNAME}'>✉ Ответить</a>"
            
            try:
                await bot.send_message(
                    CHANNEL_ID,
                    f"{header}<blockquote>{escaped_text}</blockquote>{footer}",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Error sending to channel: {e}")
                async with db_pool.acquire() as db:
                    await db.execute(
                        "UPDATE messages SET status='pending', reviewed_at=NULL WHERE id=?",
                        (msg_id,)
                    )
                    await db.commit()
                return
            
            async with db_pool.acquire() as db:
                await db.execute("""
                    UPDATE messages 
                    SET status='approved', auto_posted=1 
                    WHERE id=?
                """, (msg_id,))
                await db.commit()
            
            hour = (datetime.utcnow() + timedelta(hours=3)).hour
            mode = 'night' if hour < 8 else 'auto'
            
            await notify_admins_about_auto_post(msg_id, user_id, "текст", counter, mode)
            
        except Exception as e:
            logger.error(f"Ошибка авто-публикации: {e}")

async def auto_post_messages():
    global night_mode_enabled, auto_mode_enabled, shutdown_flag
    last_post_time = 0
    
    while not shutdown_flag:
        try:
            current_time = time.time()
            
            if can_auto_post_now() and not maintenance_mode:
                _, interval = get_current_mode_and_interval()
                
                if current_time - last_post_time >= interval * 60:
                    await post_next_message()
                    last_post_time = current_time
            
            for _ in range(30):
                if shutdown_flag:
                    break
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Ошибка в автоматическом режиме: {e}")
            await asyncio.sleep(5)

# ================= ПРОВЕРКА ДОЛГИХ СООБЩЕНИЙ =================

async def check_long_pending_messages():
    while not shutdown_flag:
        try:
            now = datetime.utcnow()
            threshold = now - timedelta(minutes=LONG_MESSAGE_THRESHOLD)
            
            async with db_pool.acquire() as db:
                cursor = await db.execute("""
                    SELECT id, user_id, media_type, substr(text, 1, 100) as short_text, created_at
                    FROM messages 
                    WHERE status='pending' AND skipped=0 AND notified_long=0 AND datetime(created_at) < datetime(?)
                    ORDER BY created_at ASC
                    LIMIT 5
                """, (threshold.isoformat(),))
                
                old_messages = await cursor.fetchall()
                
                for msg in old_messages:
                    msg_id, user_id, media_type, short_text, created_at = msg
                    
                    clean_short_text = re.sub(r'<[^>]+>', '', short_text) if short_text else ""
                    
                    for admin in ADMINS:
                        if admin == SUPER_ADMIN:
                            text = (
                                f"⚠️ <b>Долгое сообщение #{msg_id}</b>\n\n"
                                f"Висит в очереди больше {LONG_MESSAGE_THRESHOLD} минут!\n"
                                f"Тип: {media_type or 'текст'}\n"
                                f"Время отправки: {created_at[:16]}\n"
                                f"Текст: {clean_short_text}\n"
                                f"От пользователя: <code>{user_id}</code>"
                            )
                        else:
                            text = (
                                f"⚠️ <b>Долгое сообщение #{msg_id}</b>\n\n"
                                f"Висит в очереди больше {LONG_MESSAGE_THRESHOLD} минут!\n"
                                f"Тип: {media_type or 'текст'}\n"
                                f"Время отправки: {created_at[:16]}\n"
                                f"Текст: {clean_short_text}"
                            )
                        
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔍 Перейти к рассмотрению", callback_data=f"review_{msg_id}")]
                        ])
                        
                        try:
                            await bot.send_message(admin, text, reply_markup=keyboard)
                        except:
                            pass
                    
                    await db.execute(
                        "UPDATE messages SET notified_long=1 WHERE id=?",
                        (msg_id,)
                    )
                
                await db.commit()
        
        except Exception as e:
            logger.error(f"Error checking long messages: {e}")
        
        for _ in range(15 * 60):
            if shutdown_flag:
                break
            await asyncio.sleep(1)

# ================= HEARTBEAT =================

async def heartbeat():
    while not shutdown_flag:
        try:
            cache_size = len(user_cache)
            mode, interval = get_current_mode_and_interval()
            
            if mode == 'night':
                mode_text = f"🌙 Ночной {'✅' if night_mode_enabled else '❌'}"
            elif mode == 'night_disabled':
                mode_text = f"🌙 Ночной ❌ (выключен)"
            elif mode == 'auto':
                mode_text = f"☀️ Автоматический {'✅' if auto_mode_enabled else '❌'}"
            else:
                mode_text = f"☀️ Автоматический ❌ (выключен)"
            
            logger.info(f"❤️ Heartbeat - Бот работает | Режим: {mode_text} (интервал {interval} мин) | Пользователей в кэше: {cache_size}")
            await bot.get_me()
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        for _ in range(60):
            if shutdown_flag:
                break
            await asyncio.sleep(1)

# ================= ОБРАБОТЧИК СТАРТА =================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    global night_mode_enabled, auto_mode_enabled, maintenance_mode
    
    try:
        async with db_pool.acquire() as db:
            await db.execute("""
                INSERT OR REPLACE INTO users (user_id, username, first_name) 
                VALUES (?, ?, ?)
            """, (message.from_user.id, message.from_user.username, message.from_user.first_name))
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in start: {e}")
    
    log_user_action(message.from_user.id, "START")

    if message.from_user.id not in ADMINS and maintenance_mode:
        try:
            async with db_pool.acquire() as db:
                cursor = await db.execute(
                    "SELECT maintenance_exception FROM users WHERE user_id=?",
                    (message.from_user.id,)
                )
                result = await cursor.fetchone()
                if not result or not result[0]:
                    await message.answer(MAINTENANCE_MESSAGE)
                    return
        except Exception as e:
            logger.error(f"DB error in maintenance check: {e}")

    if message.from_user.id in ADMINS:
        keyboard_buttons = [
            [KeyboardButton(text="🎨 Сменить стиль")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="👥 Управление пользователями")],
            [KeyboardButton(text="📨 Ожидающие проверки")],
            [KeyboardButton(text="🌐 Веб-панель")]
        ]
        
        if message.from_user.id == SUPER_ADMIN:
            night_status = "✅ Включен" if night_mode_enabled else "❌ Выключен"
            auto_status = "✅ Включен" if auto_mode_enabled else "❌ Выключен"
            maint_status = "🔧 Включены" if maintenance_mode else "🔧 Выключены"
            
            keyboard_buttons.append([KeyboardButton(text=f"🌙 Ночной режим ({night_status})")])
            keyboard_buttons.append([KeyboardButton(text=f"☀️ Авто-режим ({auto_status})")])
            keyboard_buttons.append([KeyboardButton(text=f"🛠 Техработы ({maint_status})")])
            keyboard_buttons.append([KeyboardButton(text="👥 Управление исключениями")])
            keyboard_buttons.append([KeyboardButton(text="📝 Черный список слов")])
            keyboard_buttons.append([KeyboardButton(text="❓ Управление FAQ")])
        
        keyboard_buttons.append([KeyboardButton(text="⏳ Временный мут")])
        keyboard_buttons.append([KeyboardButton(text="📋 История действий")])
        keyboard_buttons.append([KeyboardButton(text="❌ Закрыть меню")])
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=keyboard_buttons,
            resize_keyboard=True,
            input_field_placeholder="Выберите действие..."
        )
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=keyboard)
        return

    # Обычные пользователи
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ℹ Информация")],
            [KeyboardButton(text="❓ Помощь")],
            [KeyboardButton(text="❔ FAQ")],
            [KeyboardButton(text="📊 Создать опрос")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Отправьте сообщение, фото или видео..."
    )

    await message.answer(
        "👋 Добро пожаловать в «Подслушано»!\n\n"
        "📢 Здесь ты можешь:\n"
        "• Отправить анонимное сообщение\n"
        "• Поделиться историей\n"
        "• Задать вопрос сообществу\n"
        "• Создать анонимный опрос\n"
        "• Задать вопрос в FAQ\n\n"
        "⏳ Модерация: до 24 часов\n"
        "🚫 Запрещены: сильная травля, спам, реклама, ссылки\n"
        "📸 Можно: фото и видео\n\n"
        "Используй кнопки меню для навигации 👇",
        reply_markup=keyboard
    )

# ================= ПОЛЬЗОВАТЕЛЬСКИЕ КНОПКИ =================

@dp.message(F.text == "ℹ Информация")
async def info_text(message: Message):
    await message.answer(
        "ℹ <b>Информация</b>\n\n"
        "Все сообщения проходят модерацию и публикуются анонимно.\n"
        "Можно отправлять:\n"
        "• Текстовые сообщения\n"
        "• Фотографии\n"
        "• Видео\n"
        "• Опросы\n\n"
        "Фото и видео всегда проверяются модераторами."
    )

@dp.message(F.text == "❓ Помощь")
async def help_text(message: Message):
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "Просто отправьте текст, фото или видео. Они будут проверены модератором.\n"
        "Нельзя отправлять сообщения чаще, чем раз в 30 секунд.\n"
        "Максимальный размер видео: 50 МБ\n\n"
        "Запрещено:\n"
        "• Ссылки на сторонние ресурсы\n"
        "• Сильная травля\n"
        "• Реклама\n\n"
        "Фото и видео всегда проходят ручную проверку."
    )

# ================= FAQ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =================

@dp.message(F.text == "❔ FAQ")
async def faq_button(message: Message):
    """Показывает список FAQ или запускает поиск"""
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT id, question FROM faq ORDER BY id")
            faqs = await cursor.fetchall()
    except Exception as e:
        logger.error(f"Error loading FAQ: {e}")
        await message.answer("❌ Ошибка загрузки FAQ")
        return
    
    if not faqs:
        await message.answer("❔ FAQ пока пуст")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=question, callback_data=f"faq_show_{faq_id}")]
        for faq_id, question in faqs[:10]
    ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔍 Поиск по FAQ", callback_data="faq_search")
    ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="📋 Все вопросы", callback_data="faq_show_all")
    ])
    
    await message.answer(
        "❔ <b>Часто задаваемые вопросы</b>\n\n"
        "Выберите вопрос или используйте поиск:",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("faq_"))
async def faq_router(callback: CallbackQuery, state: FSMContext):
    """Единый обработчик всех FAQ-действий"""
    
    action = callback.data
    
    # === Показ ответа на вопрос (faq_show_ID) ===
    if action.startswith("faq_show_"):
        try:
            faq_id = int(action.split("_")[2])
            async with db_pool.acquire() as db:
                cursor = await db.execute(
                    "SELECT question, answer FROM faq WHERE id=?",
                    (faq_id,)
                )
                result = await cursor.fetchone()
                if result:
                    question, answer = result
                    await callback.message.answer(f"❔ <b>{question}</b>\n\n{answer}")
                else:
                    await callback.answer("Вопрос не найден", show_alert=True)
        except Exception as e:
            logger.error(f"Error getting FAQ: {e}")
            await callback.answer("Ошибка загрузки ответа", show_alert=True)
        await callback.answer()
        return
    
    # === Поиск ===
    elif action == "faq_search":
        await state.set_state(AdminStates.waiting_for_faq_question)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="faq_cancel_search")]
        ])
        await callback.message.answer(
            "🔍 Введите ключевое слово для поиска в FAQ.\n"
            "Например: правила, опрос, публикация",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    
    # === Показать все ===
    elif action == "faq_show_all":
        try:
            async with db_pool.acquire() as db:
                cursor = await db.execute("SELECT id, question FROM faq ORDER BY id")
                faqs = await cursor.fetchall()
            if not faqs:
                await callback.message.answer("❔ FAQ пока пуст")
                await callback.answer()
                return
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=question, callback_data=f"faq_show_{faq_id}")]
                for faq_id, question in faqs[:15]
            ])
            await callback.message.answer(
                "❔ <b>Все вопросы FAQ:</b>\n\n"
                "Выберите интересующий вопрос:",
                reply_markup=keyboard
            )
        except:
            await callback.answer("Ошибка загрузки")
        await callback.answer()
        return
    
    # === Отмена поиска ===
    elif action == "faq_cancel_search":
        await state.clear()
        await callback.message.delete()
        await callback.answer("Поиск отменен")
        return
    
    # === АДМИНСКИЕ КОМАНДЫ ===
    
    # Добавить FAQ
    elif action == "faq_add":
        if callback.from_user.id != SUPER_ADMIN:
            await callback.answer("Только супер-админ", show_alert=True)
            return
        await state.set_state(AdminStates.waiting_for_faq_add)
        await callback.message.answer(
            "➕ <b>Добавление FAQ</b>\n\n"
            "Отправьте данные в формате:\n\n"
            "<b>Вопрос</b>\n"
            "<b>Ответ</b>\n"
            "<b>Ключевые слова</b> (через запятую)\n\n"
            "Пример:\n"
            "Как отправить фото?\n"
            "Отправьте фото в этот чат, оно пройдет модерацию.\n"
            "фото,отправить,изображение\n\n"
            "Или /cancel для отмены"
        )
        await callback.answer()
        return
    
    # Удалить FAQ (показать список)
    elif action == "faq_remove":
        if callback.from_user.id != SUPER_ADMIN:
            await callback.answer("Только супер-админ", show_alert=True)
            return
        try:
            async with db_pool.acquire() as db:
                cursor = await db.execute("SELECT id, question FROM faq ORDER BY id")
                faqs = await cursor.fetchall()
            if not faqs:
                await callback.message.answer("FAQ пуст")
                await callback.answer()
                return
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"❌ {question}", callback_data=f"faq_delete_{faq_id}")]
                for faq_id, question in faqs[:20]
            ])
            await callback.message.answer("Выберите вопрос для удаления:", reply_markup=keyboard)
        except:
            await callback.answer("Ошибка загрузки")
        await callback.answer()
        return
    
    # Показать все (админская версия)
    elif action == "faq_list":
        if callback.from_user.id != SUPER_ADMIN:
            return
        try:
            async with db_pool.acquire() as db:
                cursor = await db.execute("SELECT id, question, answer, keywords FROM faq ORDER BY id")
                faqs = await cursor.fetchall()
            if not faqs:
                await callback.message.answer("FAQ пуст")
                await callback.answer()
                return
            text = "❓ <b>Все вопросы FAQ:</b>\n\n"
            for faq_id, question, answer, keywords in faqs:
                text += f"<b>#{faq_id}</b> {question}\n"
                text += f"Ответ: {answer[:100]}...\n"
                text += f"Ключевые слова: {keywords}\n\n"
                if len(text) > 3000:
                    await callback.message.answer(text)
                    text = ""
            if text:
                await callback.message.answer(text)
        except:
            await callback.answer("Ошибка загрузки")
        await callback.answer()
        return
    
    # Обновить кэш
    elif action == "faq_refresh":
        if callback.from_user.id != SUPER_ADMIN:
            return
        faq_cache.clear()
        await load_faq_to_cache()
        await callback.message.answer("🔄 Кэш FAQ обновлен")
        await callback.answer()
        return
    
    # Закрыть
    elif action == "faq_close":
        await callback.message.delete()
        await callback.answer()
        return
    
    # Удаление конкретного FAQ (faq_delete_ID)
    elif action.startswith("faq_delete_"):
        if callback.from_user.id != SUPER_ADMIN:
            return
        try:
            faq_id = int(action.split("_")[2])
            async with db_pool.acquire() as db:
                await db.execute("DELETE FROM faq WHERE id=?", (faq_id,))
                await db.commit()
            faq_cache.clear()
            await load_faq_to_cache()
            await callback.message.edit_text(f"✅ FAQ #{faq_id} удален")
            await log_admin_action(callback.from_user.id, "faq_remove", details=f"id={faq_id}")
        except Exception as e:
            logger.error(f"Error deleting FAQ: {e}")
            await callback.answer("Ошибка удаления")
        await callback.answer()
        return
    
    await callback.answer("Неизвестная команда")


# ================= ПОИСК FAQ (FSM) =================

@dp.message(AdminStates.waiting_for_faq_question)
async def faq_search_result(message: Message, state: FSMContext):
    """Обрабатывает поисковый запрос FAQ"""
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Поиск отменен")
        return
    
    search_text = message.text.strip().lower()
    
    if len(search_text) < 2:
        await message.answer("❌ Слишком короткий запрос. Минимум 2 символа.")
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT question, answer, keywords FROM faq")
            all_faqs = await cursor.fetchall()
    except Exception as e:
        logger.error(f"Error searching FAQ: {e}")
        await message.answer("❌ Ошибка поиска")
        await state.clear()
        return
    
    found = []
    for question, answer, keywords in all_faqs:
        if search_text in question.lower():
            found.append((question, answer, 1))
        else:
            keywords_list = keywords.split(',')
            for keyword in keywords_list:
                if keyword.strip() in search_text or search_text in keyword.strip():
                    found.append((question, answer, 2))
                    break
    
    found.sort(key=lambda x: x[2])
    
    if found:
        await message.answer(f"🔍 Найдено результатов: {len(found)}\n")
        for question, answer, _ in found[:5]:
            await message.answer(
                f"❔ <b>{question}</b>\n\n{answer}\n\n"
                f"━━━━━━━━━━━━━━━━"
            )
            await asyncio.sleep(0.3)
        if len(found) > 5:
            await message.answer(f"... и ещё {len(found) - 5} результатов. Уточните запрос.")
    else:
        await message.answer(
            "❌ Ничего не найдено.\n\n"
            "Попробуйте другие ключевые слова или посмотрите все вопросы."
        )
    
    await state.clear()


# ================= ДОБАВЛЕНИЕ FAQ (FSM) =================

@dp.message(AdminStates.waiting_for_faq_add)
async def process_faq_add(message: Message, state: FSMContext):
    if message.from_user.id != SUPER_ADMIN:
        await state.clear()
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Добавление отменено")
        return
    
    try:
        lines = message.text.strip().split('\n')
        if len(lines) < 3:
            await message.answer("❌ Неверный формат. Нужно минимум 3 строки: вопрос, ответ, ключевые слова")
            return
        
        question = lines[0].strip()
        answer = lines[1].strip()
        keywords = lines[2].strip().lower()
        
        if not question or not answer or not keywords:
            await message.answer("❌ Все поля должны быть заполнены")
            return
        
        async with db_pool.acquire() as db:
            await db.execute(
                "INSERT INTO faq (question, answer, keywords, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                (question, answer, keywords, message.from_user.id, datetime.utcnow().isoformat())
            )
            await db.commit()
        
        faq_cache.clear()
        await load_faq_to_cache()
        
        await message.answer(
            f"✅ FAQ добавлен:\n\n"
            f"<b>Вопрос:</b> {question}\n"
            f"<b>Ответ:</b> {answer}\n"
            f"<b>Ключевые слова:</b> {keywords}"
        )
        await log_admin_action(message.from_user.id, "faq_add", details=question)
        
    except Exception as e:
        logger.error(f"Error adding FAQ: {e}")
        await message.answer("❌ Ошибка при добавлении FAQ")
    
    await state.clear()


# ================= УПРАВЛЕНИЕ FAQ (супер-админ) =================

@dp.message(F.text == "❓ Управление FAQ")
async def manage_faq(message: Message):
    """Управление FAQ (только супер-админ)"""
    if message.from_user.id != SUPER_ADMIN:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT id, question, keywords FROM faq ORDER BY id")
            faqs = await cursor.fetchall()
    except Exception as e:
        logger.error(f"Error loading FAQ: {e}")
        await message.answer("❌ Ошибка загрузки FAQ")
        return
    
    text = "❓ <b>Управление FAQ</b>\n\n"
    if faqs:
        for faq_id, question, keywords in faqs[:20]:
            text += f"#{faq_id} {question}\n"
            text += f"Ключевые слова: {keywords}\n\n"
    else:
        text += "FAQ пуст\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить вопрос", callback_data="faq_add")],
        [InlineKeyboardButton(text="➖ Удалить вопрос", callback_data="faq_remove")],
        [InlineKeyboardButton(text="📋 Показать все", callback_data="faq_list")],
        [InlineKeyboardButton(text="🔄 Обновить кэш", callback_data="faq_refresh")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="faq_close")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


# ================= ВЕБ-ПАНЕЛЬ (Web App) =================

@dp.message(F.text == "🌐 Веб-панель")
async def open_web_panel(message: Message):
    """Открывает Web App для администраторов"""
    if message.from_user.id not in ADMINS:
        return
    
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    
    web_app_url = f"{WEB_APP_URL}?user_id={user_id}&username={username}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔧 Открыть панель управления",
            web_app=WebAppInfo(url=web_app_url)
        )]
    ])
    
    await message.answer(
        "🌐 <b>Веб-панель администратора</b>\n\n"
        "Нажмите кнопку ниже для открытия панели управления.\n\n"
        "📊 Статистика\n"
        "📨 Модерация сообщений\n"
        "👥 Управление пользователями\n"
        "⚙️ Настройки бота",
        reply_markup=keyboard
    )

# ================= ОПРОСЫ =================

@dp.message(F.text == "📊 Создать опрос")
async def create_poll_start(message: Message, state: FSMContext):
    """Начало создания опроса"""
    user_id = message.from_user.id
    
    if user_id in ADMINS:
        return
    
    # Проверяем кулдаун
    if user_id in poll_cooldown:
        await message.answer("⏳ Подождите 30 секунд перед созданием нового опроса.")
        return
    
    # Проверяем техработы
    if maintenance_mode:
        try:
            async with db_pool.acquire() as db:
                cursor = await db.execute(
                    "SELECT maintenance_exception FROM users WHERE user_id=?",
                    (user_id,)
                )
                result = await cursor.fetchone()
                if not result or not result[0]:
                    await message.answer(MAINTENANCE_MESSAGE)
                    return
        except Exception as e:
            logger.error(f"DB error in maintenance check: {e}")
    
    await state.set_state(AdminStates.waiting_for_poll_question)
    await message.answer(
        "📊 <b>Создание анонимного опроса</b>\n\n"
        "Шаг 1/2: Отправьте вопрос для опроса.\n"
        "Например: «Какой ваш любимый цвет?»\n\n"
        "Или /cancel для отмены"
    )

@dp.message(AdminStates.waiting_for_poll_question)
async def poll_question(message: Message, state: FSMContext):
    """Получение вопроса опроса"""
    if message.from_user.id in ADMINS:
        await state.clear()
        return
    
    # Проверяем техработы
    if maintenance_mode:
        try:
            async with db_pool.acquire() as db:
                cursor = await db.execute(
                    "SELECT maintenance_exception FROM users WHERE user_id=?",
                    (message.from_user.id,)
                )
                result = await cursor.fetchone()
                if not result or not result[0]:
                    await message.answer(MAINTENANCE_MESSAGE)
                    await state.clear()
                    return
        except Exception as e:
            logger.error(f"DB error in maintenance check: {e}")
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Создание опроса отменено")
        return
    
    question = message.text.strip()
    
    if len(question) > 255:
        await message.answer("❌ Вопрос слишком длинный. Максимум 255 символов.")
        return
    
    if len(question) < 5:
        await message.answer("❌ Вопрос слишком короткий. Минимум 5 символов.")
        return
    
    await state.update_data(poll_question=question)
    await state.set_state(AdminStates.waiting_for_poll_options)
    
    await message.answer(
        "📊 Шаг 2/2: Отправьте варианты ответов.\n\n"
        "Каждый вариант с новой строки (от 2 до 10 вариантов).\n"
        "Например:\n"
        "Красный\n"
        "Синий\n"
        "Зеленый\n"
        "Другой\n\n"
        "Или /cancel для отмены"
    )

@dp.message(AdminStates.waiting_for_poll_options)
async def poll_options(message: Message, state: FSMContext):
    """Получение вариантов ответа и создание опроса"""
    if message.from_user.id in ADMINS:
        await state.clear()
        return
    
    # Проверяем техработы
    if maintenance_mode:
        try:
            async with db_pool.acquire() as db:
                cursor = await db.execute(
                    "SELECT maintenance_exception FROM users WHERE user_id=?",
                    (message.from_user.id,)
                )
                result = await cursor.fetchone()
                if not result or not result[0]:
                    await message.answer(MAINTENANCE_MESSAGE)
                    await state.clear()
                    return
        except Exception as e:
            logger.error(f"DB error in maintenance check: {e}")
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Создание опроса отменено")
        return
    
    options_text = message.text.strip()
    options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
    
    if len(options) < 2:
        await message.answer("❌ Минимум 2 варианта ответа на опрос.")
        return
    
    if len(options) > 10:
        await message.answer("❌ Максимум 10 вариантов ответа на опрос.")
        return
    
    for opt in options:
        if len(opt) > 100:
            await message.answer(f"❌ Вариант «{opt[:50]}...» слишком длинный. Максимум 100 символов.")
            return
    
    data = await state.get_data()
    question = data.get("poll_question")
    
    if not question:
        await message.answer("❌ Ошибка: вопрос не найден. Начните заново.")
        await state.clear()
        return
    
    # Сохраняем опрос в БД
    poll_data = json.dumps({
        "question": question,
        "options": options,
        "allows_multiple_answers": True,
        "is_anonymous": True
    })
    
    now = datetime.utcnow()
    
    try:
        async with db_pool.acquire() as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, last_message) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_message=excluded.last_message
            """, (message.from_user.id, message.from_user.username, message.from_user.first_name, now.isoformat()))
            
            cursor = await db.execute("""
                INSERT INTO messages 
                (user_id, text, media_type, created_at, poll_data) 
                VALUES (?, ?, ?, ?, ?) RETURNING id
            """, (message.from_user.id, question, "poll", now.isoformat(), poll_data))
            
            row = await cursor.fetchone()
            msg_id = row[0]
            await db.commit()
    except Exception as e:
        logger.error(f"Error saving poll: {e}")
        await message.answer("❌ Ошибка при сохранении опроса")
        await state.clear()
        return
    
    # Обновляем кэш и ставим кулдаун
    user_cache[message.from_user.id] = {'banned': False, 'mute_until': None, 'last_message': now}
    poll_cooldown[message.from_user.id] = True
    pending_cache.clear()
    
    await message.answer("✅ Опрос отправлен на модерацию!")
    
    # Отправляем админам
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Перейти к опросу", callback_data=f"review_{msg_id}")]
    ])
    
    options_preview = "\n".join([f"• {escape_html(opt)}" for opt in options])
    
    for admin in ADMINS:
        try:
            if admin == SUPER_ADMIN:
                await bot.send_message(
                    admin,
                    f"📊 <b>Новый опрос</b>\n\n"
                    f"<b>Вопрос:</b> {escape_html(question)}\n\n"
                    f"<b>Варианты:</b>\n{options_preview}\n\n"
                    f"🆔 <code>{message.from_user.id}</code>\n"
                    f"👤 @{message.from_user.username or 'нет'}",
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(
                    admin,
                    f"📊 <b>Новый опрос</b>\n\n"
                    f"<b>Вопрос:</b> {escape_html(question)}\n\n"
                    f"<b>Варианты:</b>\n{options_preview}",
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Error sending poll to admin: {e}")
    
    await state.clear()

# ================= ПЕРЕКЛЮЧАТЕЛИ РЕЖИМОВ =================

@dp.message(F.text.startswith("🌙 Ночной режим"))
async def toggle_night_mode(message: Message):
    if message.from_user.id != SUPER_ADMIN:
        return
    
    global night_mode_enabled
    night_mode_enabled = not night_mode_enabled
    
    try:
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE settings SET value=? WHERE key='night_mode'",
                (str(int(night_mode_enabled)),)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in toggle_night_mode: {e}")
    
    status = "включен" if night_mode_enabled else "выключен"
    await message.answer(f"🌙 Ночной режим {status} (00:00-08:00, интервал 30 мин)")
    await log_admin_action(message.from_user.id, "night_mode_toggle", details=status)

@dp.message(F.text.startswith("☀️ Авто-режим"))
async def toggle_auto_mode(message: Message):
    if message.from_user.id != SUPER_ADMIN:
        return
    
    global auto_mode_enabled
    auto_mode_enabled = not auto_mode_enabled
    
    try:
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE settings SET value=? WHERE key='auto_mode'",
                (str(int(auto_mode_enabled)),)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in toggle_auto_mode: {e}")
    
    status = "включен" if auto_mode_enabled else "выключен"
    await message.answer(f"☀️ Автоматический режим {status} (08:01-23:59, интервал 5 мин)")
    await log_admin_action(message.from_user.id, "auto_mode_toggle", details=status)

@dp.message(F.text.startswith("🛠 Техработы"))
async def toggle_maintenance(message: Message):
    if message.from_user.id != SUPER_ADMIN:
        return
    
    global maintenance_mode
    maintenance_mode = not maintenance_mode
    
    try:
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE settings SET value=? WHERE key='maintenance'",
                (str(int(maintenance_mode)),)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in toggle_maintenance: {e}")
    
    status = "включены" if maintenance_mode else "выключены"
    await message.answer(f"🛠 Технические работы {status}")
    await log_admin_action(message.from_user.id, "maintenance_toggle", details=status)

# ================= УПРАВЛЕНИЕ ЧЕРНЫМ СПИСКОМ =================

@dp.message(F.text == "📝 Черный список слов")
async def blacklist_menu(message: Message):
    if message.from_user.id != SUPER_ADMIN:
        return
    
    text = f"📝 <b>Черный список слов</b>\n\nВсего слов: {len(blacklist_cache)}\n\n"
    words = list(blacklist_cache.keys())[:20]
    if words:
        text += "Первые 20 слов:\n"
        for i, word in enumerate(words, 1):
            text += f"{i}. <code>{escape_html(word)}</code>\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить слово", callback_data="blacklist_add")],
        [InlineKeyboardButton(text="➖ Удалить слово", callback_data="blacklist_remove")],
        [InlineKeyboardButton(text="📋 Показать все", callback_data="blacklist_show")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="blacklist_close")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data == "blacklist_add")
async def blacklist_add_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != SUPER_ADMIN:
        return
    await state.set_state(AdminStates.waiting_for_blacklist_add)
    await callback.message.answer(
        "➕ Введите слово для добавления в черный список:\n(или отправьте /cancel для отмены)"
    )
    await callback.answer()

@dp.callback_query(F.data == "blacklist_remove")
async def blacklist_remove_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != SUPER_ADMIN:
        return
    await state.set_state(AdminStates.waiting_for_blacklist_remove)
    await callback.message.answer(
        "➖ Введите слово для удаления из черного списка:\n(или отправьте /cancel для отмены)"
    )
    await callback.answer()

@dp.callback_query(F.data == "blacklist_show")
async def blacklist_show(callback: CallbackQuery):
    if callback.from_user.id != SUPER_ADMIN:
        return
    words = list(blacklist_cache.keys())
    if not words:
        await callback.message.answer("📝 Черный список пуст")
        await callback.answer()
        return
    text = "📝 <b>Полный черный список</b>\n\n"
    for i, word in enumerate(words, 1):
        text += f"{i}. <code>{escape_html(word)}</code>\n"
        if i % 50 == 0:
            await callback.message.answer(text)
            text = ""
    if text:
        await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "blacklist_close")
async def blacklist_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@dp.message(AdminStates.waiting_for_blacklist_add)
async def process_blacklist_add(message: Message, state: FSMContext):
    if message.from_user.id != SUPER_ADMIN:
        await state.clear()
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    word = message.text.strip().lower()
    
    try:
        async with db_pool.acquire() as db:
            await db.execute(
                "INSERT INTO blacklist (word, added_by, created_at) VALUES (?, ?, ?)",
                (word, message.from_user.id, datetime.utcnow().isoformat())
            )
            await db.commit()
        
        blacklist_cache[word] = True
        await message.answer(f"✅ Слово <code>{escape_html(word)}</code> добавлено в черный список")
        await log_admin_action(message.from_user.id, "blacklist_add", details=word)
        
    except aiosqlite.IntegrityError:
        await message.answer(f"❌ Слово <code>{escape_html(word)}</code> уже есть в черном списке")
    except Exception as e:
        logger.error(f"Error adding to blacklist: {e}")
        await message.answer("❌ Ошибка при добавлении слова")
    
    await state.clear()

@dp.message(AdminStates.waiting_for_blacklist_remove)
async def process_blacklist_remove(message: Message, state: FSMContext):
    if message.from_user.id != SUPER_ADMIN:
        await state.clear()
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    word = message.text.strip().lower()
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "DELETE FROM blacklist WHERE word=?",
                (word,)
            )
            await db.commit()
            
            if cursor.rowcount > 0:
                if word in blacklist_cache:
                    del blacklist_cache[word]
                await message.answer(f"✅ Слово <code>{escape_html(word)}</code> удалено из черного списка")
                await log_admin_action(message.from_user.id, "blacklist_remove", details=word)
            else:
                await message.answer(f"❌ Слово <code>{escape_html(word)}</code> не найдено в черном списке")
        
    except Exception as e:
        logger.error(f"Error removing from blacklist: {e}")
        await message.answer("❌ Ошибка при удалении слова")
    
    await state.clear()

# ================= ВРЕМЕННЫЙ МУТ =================

@dp.message(F.text == "⏳ Временный мут")
async def temporary_mute_menu(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    
    await state.set_state(AdminStates.waiting_for_mute_user)
    await message.answer(
        "⏳ Введите ID пользователя для мута:\n(или отправьте /cancel для отмены)"
    )

@dp.message(AdminStates.waiting_for_mute_user)
async def process_mute_user(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await state.clear()
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число.")
        return
    
    await state.update_data(mute_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_mute_duration)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 час", callback_data="mute_1h"),
            InlineKeyboardButton(text="3 часа", callback_data="mute_3h"),
            InlineKeyboardButton(text="6 часов", callback_data="mute_6h")
        ],
        [
            InlineKeyboardButton(text="12 часов", callback_data="mute_12h"),
            InlineKeyboardButton(text="1 день", callback_data="mute_1d"),
            InlineKeyboardButton(text="3 дня", callback_data="mute_3d")
        ],
        [
            InlineKeyboardButton(text="7 дней", callback_data="mute_7d"),
            InlineKeyboardButton(text="30 дней", callback_data="mute_30d"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="mute_cancel")
        ]
    ])
    
    await message.answer(
        f"⏳ Выберите длительность мута для пользователя <code>{user_id}</code>:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("mute_"))
async def process_mute_duration(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return
    
    data = await state.get_data()
    user_id = data.get("mute_user_id")
    
    if not user_id:
        await callback.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    duration_map = {
        "mute_1h": timedelta(hours=1), "mute_3h": timedelta(hours=3),
        "mute_6h": timedelta(hours=6), "mute_12h": timedelta(hours=12),
        "mute_1d": timedelta(days=1), "mute_3d": timedelta(days=3),
        "mute_7d": timedelta(days=7), "mute_30d": timedelta(days=30)
    }
    
    duration_text = {
        "mute_1h": "1 час", "mute_3h": "3 часа", "mute_6h": "6 часов",
        "mute_12h": "12 часов", "mute_1d": "1 день", "mute_3d": "3 дня",
        "mute_7d": "7 дней", "mute_30d": "30 дней"
    }
    
    if callback.data == "mute_cancel":
        await callback.message.edit_text("❌ Мут отменен")
        await state.clear()
        await callback.answer()
        return
    
    if callback.data in duration_map:
        mute_until = datetime.utcnow() + duration_map[callback.data]
        
        try:
            async with db_pool.acquire() as db:
                await db.execute(
                    "UPDATE users SET mute_until=? WHERE user_id=?",
                    (mute_until.isoformat(), user_id)
                )
                await db.commit()
            
            if user_id in user_cache:
                del user_cache[user_id]
            
            await callback.message.edit_text(
                f"✅ Пользователь <code>{user_id}</code> получил мут на {duration_text[callback.data]}\n"
                f"До: {mute_until.strftime('%d.%m.%Y %H:%M')} МСК"
            )
            
            try:
                await bot.send_message(
                    user_id,
                    f"⏳ Вы получили временный мут на {duration_text[callback.data]}.\n"
                    f"Снять мут может только администратор."
                )
            except:
                pass
            
            await log_admin_action(
                callback.from_user.id, "temporary_mute", user_id,
                f"duration: {duration_text[callback.data]}"
            )
            
        except Exception as e:
            logger.error(f"Error applying mute: {e}")
            await callback.message.edit_text("❌ Ошибка при применении мута")
        
        await state.clear()
        await callback.answer()

# ================= ИСТОРИЯ ДЕЙСТВИЙ =================

@dp.message(F.text == "📋 История действий")
async def show_admin_history(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("""
                SELECT admin_id, action, target_id, details, created_at
                FROM admin_actions
                ORDER BY created_at DESC
                LIMIT 20
            """)
            actions = await cursor.fetchall()
    except Exception as e:
        logger.error(f"Error loading admin history: {e}")
        await message.answer("❌ Ошибка загрузки истории")
        return
    
    if not actions:
        await message.answer("📋 История действий пуста")
        return
    
    text = "📋 <b>Последние действия админов</b>\n\n"
    
    for admin_id, action, target_id, details, created_at in actions:
        try:
            action_date = datetime.fromisoformat(created_at)
            date_str = action_date.strftime('%d.%m %H:%M')
        except:
            date_str = created_at[:16] if created_at else "неизвестно"
        
        action_emoji = {
            "approve": "✅", "reject": "❌", "mute": "🔇", "ban": "🔨",
            "unban": "✅", "unmute": "🔊", "skip": "⏭",
            "blacklist_add": "📝➕", "blacklist_remove": "📝➖",
            "temporary_mute": "⏳", "reply": "💬",
            "approve_watermark": "✅➕",
            "night_mode_toggle": "🌙", "auto_mode_toggle": "☀️",
            "faq_add": "❓➕", "faq_remove": "❓➖"
        }.get(action, "📌")
        
        target_text = f" <code>{target_id}</code>" if target_id else ""
        details_text = f" ({details})" if details else ""
        
        text += f"{action_emoji} <b>{action}</b>{target_text}{details_text}\n"
        text += f"👤 <code>{admin_id}</code> | {date_str}\n\n"
        
        if len(text) > 3000:
            text += "... и другие"
            break
    
    if message.from_user.id == SUPER_ADMIN:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Экспорт истории", callback_data="export_history")]
        ])
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text)

@dp.callback_query(F.data == "export_history")
async def export_history(callback: CallbackQuery):
    if callback.from_user.id != SUPER_ADMIN:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("""
                SELECT admin_id, action, target_id, details, created_at
                FROM admin_actions
                ORDER BY created_at DESC
                LIMIT 100
            """)
            actions = await cursor.fetchall()
    except Exception as e:
        logger.error(f"Error exporting history: {e}")
        await callback.answer("❌ Ошибка экспорта")
        return
    
    text = "Дата;Админ;Действие;Цель;Детали\n"
    for admin_id, action, target_id, details, created_at in actions:
        try:
            action_date = datetime.fromisoformat(created_at)
            date_str = action_date.strftime('%Y-%m-%d %H:%M')
        except:
            date_str = created_at[:16] if created_at else "неизвестно"
        
        text += f"{date_str};{admin_id};{action};{target_id or ''};{details or ''}\n"
    
    file = io.BytesIO(text.encode('utf-8'))
    file.name = "admin_history.txt"
    
    await callback.message.answer_document(
        document=('admin_history.txt', file),
        caption="📊 Полная история действий"
    )
    
    await callback.answer()

# ================= СТАТИСТИКА =================

@dp.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM users) as total_users,
                    (SELECT COUNT(*) FROM users WHERE banned=1) as banned_users,
                    (SELECT COUNT(*) FROM users WHERE mute_until > datetime('now')) as muted_users,
                    (SELECT COUNT(*) FROM users WHERE maintenance_exception=1) as exception_users,
                    (SELECT COUNT(*) FROM users WHERE captcha_passed=1) as verified_users,
                    (SELECT COUNT(*) FROM messages) as total_messages,
                    (SELECT COUNT(*) FROM messages WHERE status='pending') as pending_messages,
                    (SELECT COUNT(*) FROM messages WHERE media_type IS NOT NULL) as media_messages,
                    (SELECT COUNT(*) FROM messages WHERE auto_posted=1) as auto_posted,
                    (SELECT COUNT(*) FROM messages WHERE has_links=1) as with_links,
                    (SELECT COUNT(*) FROM messages WHERE skipped=1) as skipped_messages,
                    (SELECT COUNT(*) FROM messages WHERE insult_count >= ?) as heavy_insults,
                    (SELECT value FROM settings WHERE key='post_counter') as post_counter,
                    (SELECT COUNT(*) FROM blacklist) as blacklist_count,
                    (SELECT COUNT(*) FROM admin_actions WHERE date(created_at) = date('now')) as today_actions,
                    (SELECT COUNT(*) FROM admin_messages WHERE status='new') as new_messages,
                    (SELECT COUNT(*) FROM faq) as faq_count
            """, (INSULT_THRESHOLD,))
            
            result = await cursor.fetchone()
            (total_users, banned_users, muted_users, exception_users, verified_users,
             total_messages, pending_messages, media_messages, auto_posted, with_links,
             skipped_messages, heavy_insults, post_counter, blacklist_count,
             today_actions, new_messages, faq_count) = result
    except Exception as e:
        logger.error(f"DB error in admin_stats: {e}")
        await message.answer("❌ Ошибка получения статистики")
        return
    
    mode, interval = get_current_mode_and_interval()
    if mode == 'night':
        mode_text = f"🌙 Ночной {'✅' if night_mode_enabled else '❌'}"
    elif mode == 'night_disabled':
        mode_text = "🌙 Ночной ❌ (выключен)"
    elif mode == 'auto':
        mode_text = f"☀️ Автоматический {'✅' if auto_mode_enabled else '❌'}"
    else:
        mode_text = "☀️ Автоматический ❌ (выключен)"
    
    stats_text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"   ✅ Прошли капчу: {verified_users}\n"
        f"⛔ Забанено: {banned_users}\n"
        f"🔇 В муте: {muted_users}\n"
        f"⭐ В исключении: {exception_users}\n"
        f"📨 Всего сообщений: {total_messages}\n"
        f"   📝 Текстовых: {total_messages - media_messages}\n"
        f"   🖼 С медиа: {media_messages}\n"
        f"   🔗 Со ссылками: {with_links}\n"
        f"   🤬 С матом: {heavy_insults}\n"
        f"   🤖 Авто-пост: {auto_posted}\n"
        f"   ⏭ Пропущено: {skipped_messages}\n"
        f"⏳ Ожидают проверки: {pending_messages}\n"
        f"📝 Опубликовано постов: {post_counter}\n"
        f"📚 Черный список: {blacklist_count} слов\n"
        f"❓ FAQ записей: {faq_count}\n"
        f"📋 Действий сегодня: {today_actions}\n"
        f"📩 Новых личных сообщений: {new_messages}\n"
        f"🌙 Ночной режим: {'✅' if night_mode_enabled else '❌'}\n"
        f"☀️ Авто-режим: {'✅' if auto_mode_enabled else '❌'}\n"
        f"🛠 Техработы: {'✅' if maintenance_mode else '❌'}\n"
        f"⏱ Текущий режим: {mode_text} (интервал {interval} мин)"
    )
    
    await message.answer(stats_text)

# ================= СМЕНА СТИЛЯ =================

@dp.message(F.text == "🎨 Сменить стиль")
async def admin_style(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key='post_style'")
            current_style = (await cursor.fetchone())[0]
    except Exception as e:
        logger.error(f"DB error in admin_style: {e}")
        current_style = "1"
    
    styles = {"1": "Обычный", "2": "С рамкой", "3": "Минимализм"}
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ' if current_style=='1' else ''}Стиль 1 - Обычный", 
            callback_data="set_style_1"
        )],
        [InlineKeyboardButton(
            text=f"{'✅ ' if current_style=='2' else ''}Стиль 2 - С рамкой", 
            callback_data="set_style_2"
        )],
        [InlineKeyboardButton(
            text=f"{'✅ ' if current_style=='3' else ''}Стиль 3 - Минимализм", 
            callback_data="set_style_3"
        )]
    ])
    
    await message.answer(
        f"🎨 <b>Текущий стиль: {styles[current_style]}</b>\n\nВыберите новый стиль:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("set_style_"))
async def set_style(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return
    
    style_num = callback.data.split("_")[2]
    
    try:
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE settings SET value=? WHERE key='post_style'",
                (style_num,)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in set_style: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return
    
    if "stats" in admin_cache:
        del admin_cache["stats"]
    
    styles = {"1": "Обычный", "2": "С рамкой", "3": "Минимализм"}
    await callback.answer(f"Стиль изменен на {styles[style_num]}")
    await callback.message.edit_text(f"✅ Стиль успешно изменен на <b>{styles[style_num]}</b>")

# ================= КАПЧА ДЛЯ НОВЫХ ПОЛЬЗОВАТЕЛЕЙ =================

def generate_captcha() -> tuple:
    """Генерирует простую математическую капчу"""
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    operations = ['+', '-', '*']
    op = random.choice(operations)
    
    if op == '+':
        answer = a + b
        question = f"{a} + {b}"
    elif op == '-':
        answer = a - b
        question = f"{a} - {b}"
    else:
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        answer = a * b
        question = f"{a} × {b}"
    
    return question, str(answer)

async def check_user_captcha(user_id: int) -> bool:
    """Проверяет, прошел ли пользователь капчу.
    Админы автоматически считаются прошедшими.
    Возвращает True если капча пройдена или проверка не нужна."""
    
    # Админы всегда проходят
    if user_id in ADMINS:
        return True
    
    # Супер-админ тоже всегда проходит
    if user_id == SUPER_ADMIN:
        return True
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT captcha_passed FROM users WHERE user_id=?",
                (user_id,)
            )
            result = await cursor.fetchone()
            
            # Если пользователь есть в БД и прошел капчу
            if result and result[0] == 1:
                return True
            
            # Если пользователь есть, но не прошел капчу
            if result and result[0] == 0:
                return False
            
            # Если пользователя нет в БД - создаем запись
            if not result:
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, captcha_passed) VALUES (?, 0)",
                    (user_id,)
                )
                await db.commit()
                return False
            
            return False
            
    except Exception as e:
        logger.error(f"Error checking captcha for user {user_id}: {e}")
        # В случае ошибки БД - пропускаем пользователя
        return True

async def set_captcha_passed(user_id: int):
    """Отмечает, что пользователь прошел капчу"""
    if user_id in ADMINS or user_id == SUPER_ADMIN:
        return  # Админам не нужно отмечать
    
    try:
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE users SET captcha_passed=1 WHERE user_id=?",
                (user_id,)
            )
            await db.commit()
            logger.info(f"✅ Captcha passed for user {user_id}")
    except Exception as e:
        logger.error(f"Error setting captcha passed for user {user_id}: {e}")
        # Пробуем создать колонку, если её нет
        try:
            async with db_pool.acquire() as db:
                # Проверяем, существует ли колонка
            #    try:
            #        await db.execute("ALTER TABLE users ADD COLUMN captcha_passed INTEGER DEFAULT 0")
            #        await db.commit()
             #       logger.info("Added captcha_passed column to users table")
            #    except:
            #        pass  # Колонка уже существует или другая ошибка
                
                # Пробуем снова обновить
                await db.execute(
                    "UPDATE users SET captcha_passed=1 WHERE user_id=?",
                    (user_id,)
                )
                await db.commit()
                logger.info(f"✅ Captcha passed for user {user_id} (after fix)")
        except Exception as e2:
            logger.error(f"Failed to set captcha passed for user {user_id}: {e2}")

async def ensure_captcha_column():
    """Проверяет и добавляет колонку captcha_passed если её нет"""
    try:
        async with db_pool.acquire() as db:
            # Пробуем выполнить запрос к колонке
            try:
                await db.execute("SELECT captcha_passed FROM users LIMIT 1")
            except:
                # Колонки нет - добавляем
                await db.execute("ALTER TABLE users ADD COLUMN captcha_passed INTEGER DEFAULT 0")
                await db.commit()
                logger.info("✅ Added captcha_passed column to existing users table")
    except Exception as e:
        logger.error(f"Error ensuring captcha column: {e}")

# Функция для отображения капчи пользователю
async def send_captcha(message: Message):
    """Отправляет капчу пользователю"""
    user_id = message.from_user.id
    
    question, answer = generate_captcha()
    captcha_cache[user_id] = answer
    
    await message.answer(
        "🤖 <b>Проверка на бота</b>\n\n"
        f"Решите пример: <b>{question} = ?</b>\n\n"
        "Отправьте только число в ответном сообщении.\n"
        "Это нужно сделать один раз.",
        parse_mode=ParseMode.HTML
    )

# Функция для проверки ответа на капчу
async def verify_captcha_answer(message: Message) -> bool:
    """Проверяет ответ пользователя на капчу.
    Возвращает True если ответ правильный."""
    user_id = message.from_user.id
    
    # Если пользователь не в кэше капчи - странная ситуация
    if user_id not in captcha_cache:
        return False
    
    # Проверяем, что сообщение текстовое
    if not message.text:
        return False
    
    # Сравниваем ответ
    user_answer = message.text.strip()
    correct_answer = captcha_cache[user_id]
    
    if user_answer == correct_answer:
        # Правильный ответ
        await set_captcha_passed(user_id)
        del captcha_cache[user_id]
        return True
    else:
        # Неправильный ответ - генерируем новую капчу
        question, answer = generate_captcha()
        captcha_cache[user_id] = answer
        return False

# Функция для сброса капчи (если нужно)
async def reset_captcha(user_id: int):
    """Сбрасывает статус капчи для пользователя (для отладки)"""
    if user_id in captcha_cache:
        del captcha_cache[user_id]
    
    try:
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE users SET captcha_passed=0 WHERE user_id=?",
                (user_id,)
            )
            await db.commit()
        logger.info(f"Captcha reset for user {user_id}")
    except Exception as e:
        logger.error(f"Error resetting captcha: {e}")

# ================= ОБРАБОТЧИК СООБЩЕНИЙ ПОЛЬЗОВАТЕЛЯ =================

@dp.message(F.photo | F.video | F.text)
async def handle_user_media(message: Message, state: FSMContext):
    """Обработка сообщений от обычных пользователей"""
    
    # ========== ПРОВЕРКА ДЛЯ АДМИНОВ ==========
    if message.from_user.id in ADMINS:
        # Обрабатываем админские кнопки прямо здесь
        if message.text and message.text.startswith("🌙"):
            await toggle_night_mode(message)
            return
        elif message.text and message.text.startswith("☀️"):
            await toggle_auto_mode(message)
            return
        elif message.text and message.text.startswith("🛠"):
            await toggle_maintenance(message)
            return
        elif message.text == "🎨 Сменить стиль":
            await admin_style(message)
            return
        elif message.text == "📊 Статистика":
            await admin_stats(message)
            return
        elif message.text == "👥 Управление пользователями":
            await admin_users(message, state)
            return
        elif message.text == "📨 Ожидающие проверки":
            await admin_pending_messages(message)
            return
        elif message.text == "⏳ Временный мут":
            await temporary_mute_menu(message, state)
            return
        elif message.text == "📋 История действий":
            await show_admin_history(message)
            return
        elif message.text == "📝 Черный список слов":
            await blacklist_menu(message)
            return
        elif message.text == "❓ Управление FAQ":
            await manage_faq(message)
            return
        elif message.text == "🌐 Веб-панель":
            await open_web_panel(message)
            return
        elif message.text == "👥 Управление исключениями":
            await manage_exceptions(message)
            return
        elif message.text == "❌ Закрыть меню":
            await close_menu(message, state)
            return
        else:
            # Игнорируем все остальные сообщения от админов
            return
    # ==========================================

    # Проверяем, не в состоянии ли FSM (кроме разрешенных)
    current_state = await state.get_state()
    if current_state is not None:
        allowed_states = [
            "AdminStates:waiting_for_faq_question",
            "AdminStates:waiting_for_poll_question",
            "AdminStates:waiting_for_poll_options"
        ]
        if current_state not in allowed_states:
            return

    # Игнорируем команды и кнопки меню для обычных пользователей
    if message.text and (message.text.startswith('/') or message.text in 
        ["🎨 Сменить стиль", "📊 Статистика", "👥 Управление пользователями", 
         "📨 Ожидающие проверки", "❌ Закрыть меню", "ℹ Информация", "❓ Помощь",
         "⏳ Временный мут", "📋 История действий", "📝 Черный список слов",
         "❌ Отмена", "❔ FAQ", "📊 Создать опрос", "❓ Управление FAQ",
         "🌐 Веб-панель", "👥 Управление исключениями",
         "🌙 Ночной режим", "☀️ Авто-режим", "🛠 Техработы"]):
        return

    # Проверяем техработы
    if maintenance_mode:
        try:
            async with db_pool.acquire() as db:
                cursor = await db.execute(
                    "SELECT maintenance_exception FROM users WHERE user_id=?",
                    (message.from_user.id,)
                )
                result = await cursor.fetchone()
                if not result or not result[0]:
                    await message.answer(MAINTENANCE_MESSAGE)
                    return
        except Exception as e:
            logger.error(f"DB error in maintenance check: {e}")

    user_id = message.from_user.id

   # # ========== ПРОВЕРКА КАПЧИ ==========
    # if not await check_user_captcha(user_id):
    #    if user_id in captcha_cache:
    #         # Уже есть активная капча - проверяем ответ
    #         if message.text and message.text.strip() == captcha_cache[user_id]:
    #             # Правильный ответ!
    #             await set_captcha_passed(user_id)
    #             del captcha_cache[user_id]
    #             await message.answer(
    #                "✅ Проверка пройдена! Теперь вы можете отправлять сообщения.\n\n"
    #                "Отправьте текст, фото или видео для публикации.\n"
    #                "Используйте кнопки меню для навигации."
    #            )
    #            return
    #        else:
    #            # Неправильный ответ - генерируем новую капчу
    #            question, answer = generate_captcha()
    #           captcha_cache[user_id] = answer
    #            await message.answer(
    #                "❌ Неверный ответ. Попробуйте ещё раз:\n\n"
    #                f"<b>{question} = ?</b>\n\n"
    #                "Отправьте только число."
    #            )
    #            return
    #    else:
    #        # Первый раз - отправляем капчу
    #       question, answer = generate_captcha()
    #        captcha_cache[user_id] = answer
    #        
    #        await message.answer(
    #            "🤖 <b>Проверка на бота</b>\n\n"
    #            f"Решите пример: <b>{question} = ?</b>\n\n"
    #            "Отправьте только число в ответном сообщении.\n"
    #            "Это нужно сделать один раз."
    #        )
    #        return
    # ===================================
    
    now = datetime.utcnow()

    # Проверяем кэш пользователя
    if user_id in user_cache:
        user_data = user_cache[user_id]
        if user_data.get('banned'):
            await message.answer("⛔ Вы заблокированы.")
            return
        if user_data.get('mute_until') and now < user_data['mute_until']:
            until_str = user_data['mute_until'].strftime('%d.%m.%Y %H:%M')
            await message.answer(f"⏳ Вы временно ограничены до {until_str} МСК.")
            return
        if user_data.get('last_message') and (now - user_data['last_message']).seconds < 30:
            await message.answer("⏳ Подождите 30 секунд.")
            return

    # Проверяем БД
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT banned, mute_until, last_message FROM users WHERE user_id=?",
                (user_id,)
            )
            user = await cursor.fetchone()

            if user:
                banned, mute_until_str, last_message_str = user
                
                if banned:
                    await message.answer("⛔ Вы заблокированы.")
                    return

                if mute_until_str:
                    try:
                        mute_until = datetime.fromisoformat(mute_until_str)
                        if now < mute_until:
                            until_str = mute_until.strftime('%d.%m.%Y %H:%M')
                            await message.answer(f"⏳ Вы временно ограничены до {until_str} МСК.")
                            return
                    except:
                        pass

                if last_message_str:
                    try:
                        last_message = datetime.fromisoformat(last_message_str)
                        if (now - last_message).seconds < 30:
                            await message.answer("⏳ Подождите 30 секунд.")
                            return
                    except:
                        pass

            # Определяем тип медиа
            media_type = None
            media_file_id = None
            text = message.caption if message.caption else message.text
            
            if message.photo:
                media_type = "photo"
                media_file_id = message.photo[-1].file_id
            elif message.video:
                media_type = "video"
                media_file_id = message.video.file_id

            # Проверки
            has_links_flag = has_links(text) if text else False
            insult_count = count_insults_with_blacklist(text) if text else 0
            has_immoral_flag = has_immoral_content(text) if text else False

            # Сохраняем пользователя
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, last_message) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_message=excluded.last_message
            """, (user_id, message.from_user.username, message.from_user.first_name, now.isoformat()))

            # Сохраняем сообщение
            cursor = await db.execute("""
                INSERT INTO messages 
                (user_id, text, media_type, media_file_id, created_at, has_links, insult_count) 
                VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id
            """, (user_id, text, media_type, media_file_id, now.isoformat(), has_links_flag, insult_count))
            
            row = await cursor.fetchone()
            msg_id = row[0]
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in handle_user_media: {e}")
        await message.answer("❌ Ошибка при сохранении сообщения")
        return

    # Обновляем кэш
    user_cache[user_id] = {'banned': False, 'mute_until': None, 'last_message': now}
    if "stats" in admin_cache:
        del admin_cache["stats"]
    pending_cache.clear()

    # Подтверждение пользователю
    if media_type == "photo":
        await message.answer("✅ Фото отправлено на модерацию.")
    elif media_type == "video":
        await message.answer("✅ Видео отправлено на модерацию.")
    else:
        await message.answer("✅ Сообщение отправлено на модерацию.")

    # Отправляем админам
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Перейти к рассмотрению", callback_data=f"review_{msg_id}")]
    ])

    warnings = []
    if has_links_flag:
        warnings.append("🔗 ССЫЛКИ")
    if insult_count >= INSULT_THRESHOLD:
        warnings.append(f"🤬 МНОГО ОСКОРБЛЕНИЙ ({insult_count})")
    if has_immoral_flag:
        warnings.append("🔞 АМОРАЛЬНЫЙ КОНТЕНТ")
    if media_type:
        warnings.append("🚫 МЕДИА")
    
    warning_text = f"\n\n⚠️ {' | '.join(warnings)}" if warnings else ""
    display_text = escape_html(text) if text else "без текста"

    tasks = []
    for admin in ADMINS:
        if admin == SUPER_ADMIN:
            if media_type == "photo":
                tasks.append(
                    bot.send_photo(
                        admin,
                        photo=media_file_id,
                        caption=f"📸 <b>Новое фото</b>{warning_text}\n\n<b>Подпись:</b> {display_text}\n\n🆔 <code>{user_id}</code>\n👤 @{message.from_user.username or 'нет'}",
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                )
            elif media_type == "video":
                tasks.append(
                    bot.send_video(
                        admin,
                        video=media_file_id,
                        caption=f"🎥 <b>Новое видео</b>{warning_text}\n\n<b>Подпись:</b> {display_text}\n\n🆔 <code>{user_id}</code>\n👤 @{message.from_user.username or 'нет'}",
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                )
            else:
                tasks.append(
                    bot.send_message(
                        admin,
                        f"📨 <b>Новое сообщение</b>{warning_text}\n\n<blockquote>{display_text}</blockquote>\n\n🆔 <code>{user_id}</code>\n👤 @{message.from_user.username or 'нет'}",
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                )
        else:
            if media_type == "photo":
                tasks.append(
                    bot.send_photo(
                        admin,
                        photo=media_file_id,
                        caption=f"📸 <b>Новое фото</b>{warning_text}\n\n<b>Подпись:</b> {display_text}",
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                )
            elif media_type == "video":
                tasks.append(
                    bot.send_video(
                        admin,
                        video=media_file_id,
                        caption=f"🎥 <b>Новое видео</b>{warning_text}\n\n<b>Подпись:</b> {display_text}",
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                )
            else:
                tasks.append(
                    bot.send_message(
                        admin,
                        f"📨 <b>Новое сообщение</b>{warning_text}\n\n<blockquote>{display_text}</blockquote>",
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                )
    
    if tasks:
        for task in tasks:
            if shutdown_flag:
                return
            try:
                await task
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Error sending to admin: {e}")

## ================= ОТВЕТЫ НА СООБЩЕНИЯ (через БД) =================

@dp.callback_query(F.data.startswith("reply_"))
async def reply_to_message(callback: CallbackQuery, state: FSMContext):
    """Начать ответ на сообщение"""
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])

    async with db_pool.acquire() as db:
        cursor = await db.execute(
            "SELECT user_id FROM messages WHERE id=?",
            (msg_id,)
        )
        result = await cursor.fetchone()
        
    if not result:
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        return

    user_id = result[0]
    
    try:
        async with db_pool.acquire() as db:
            await db.execute("""
                INSERT OR REPLACE INTO reply_states (admin_id, user_id, msg_id, reply_type, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (callback.from_user.id, user_id, msg_id, "message", datetime.utcnow().isoformat()))
            await db.commit()
    except Exception as e:
        logger.error(f"Error saving reply state: {e}")
        await callback.answer("❌ Ошибка сохранения состояния")
        return
    
    await state.set_state(AdminStates.waiting_for_reply_text)
    await callback.message.answer(
        f"📝 Введите текст ответа для пользователя <code>{user_id}</code>\n"
        f"(или отправьте /cancel для отмены)"
    )
    await callback.answer()


@dp.message(AdminStates.waiting_for_reply_text)
async def handle_reply_input(message: Message, state: FSMContext):
    """Обрабатывает ввод ответа от админа"""
    
    if message.from_user.id not in ADMINS:
        await state.clear()
        return
    
    if message.text == "/cancel":
        try:
            async with db_pool.acquire() as db:
                await db.execute(
                    "DELETE FROM reply_states WHERE admin_id=?",
                    (message.from_user.id,)
                )
                await db.commit()
        except:
            pass
        
        await state.clear()
        await message.answer("❌ Ответ отменён")
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT user_id, msg_id, reply_type FROM reply_states WHERE admin_id=?",
                (message.from_user.id,)
            )
            result = await cursor.fetchone()
            
            if not result:
                await state.clear()
                await message.answer("❌ Ошибка: данные ответа не найдены")
                return
            
            user_id, msg_id, reply_type = result
            
            await db.execute(
                "DELETE FROM reply_states WHERE admin_id=?",
                (message.from_user.id,)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error reading reply state: {e}")
        await state.clear()
        await message.answer("❌ Ошибка чтения данных")
        return
    
    try:
        await bot.send_message(
            user_id,
            f"📝 <b>Ответ от администратора</b>\n\n{message.text}"
        )
        
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}")
        await log_admin_action(message.from_user.id, "reply", user_id)
        
    except Exception as e:
        logger.error(f"Reply error: {e}")
        await message.answer(f"❌ Ошибка при отправке ответа: {e}")
    
    await state.clear()

# ================= ПРОСМОТР СООБЩЕНИЯ =================

@dp.callback_query(F.data.startswith("review_"))
async def review(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])
    cache_key = f"msg_{msg_id}"
    
    if cache_key in msg_cache:
        await callback.answer("Сообщение уже обрабатывается", show_alert=True)
        return

    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT reviewer, status, media_type, media_file_id, text, has_links, insult_count, skipped, poll_data FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()

            if not result:
                await callback.answer("Сообщение не найдено", show_alert=True)
                return

            reviewer, status, media_type, media_file_id, text, has_links, insult_count, skipped, poll_data = result

            if status != "pending":
                await callback.answer("Уже обработано", show_alert=True)
                return
            
            if skipped:
                await callback.answer("Сообщение пропущено", show_alert=True)
                return

            if reviewer and reviewer != callback.from_user.id:
                cursor = await db.execute(
                    "SELECT username, first_name FROM users WHERE user_id=?",
                    (reviewer,)
                )
                admin_info = await cursor.fetchone()
                admin_name = admin_info[0] or admin_info[1] or str(reviewer)
                await callback.answer(f"Уже рассматривается админом @{admin_name}", show_alert=True)
                return

            await db.execute(
                "UPDATE messages SET reviewer=? WHERE id=?",
                (callback.from_user.id, msg_id)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in review: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return

    msg_cache[cache_key] = callback.from_user.id

    escaped_text = escape_html(text) if text else ""
    
    # Если это опрос, показываем предпросмотр
    poll_preview = ""
    if poll_data:
        try:
            poll = json.loads(poll_data)
            poll_preview = f"\n\n📊 <b>ОПРОС</b>\nВопрос: {poll['question']}\n"
            poll_preview += "Варианты:\n" + "\n".join([f"• {opt}" for opt in poll['options']])
        except:
            pass
    
    # Создаем клавиатуру
    if poll_data:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Опубликовать опрос", callback_data=f"approve_{msg_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{msg_id}")],
            [InlineKeyboardButton(text="⏳ Мут 7д", callback_data=f"mute_{msg_id}")],
            [InlineKeyboardButton(text="🔨 Бан", callback_data=f"ban_{msg_id}")],
            [InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{msg_id}"),
             InlineKeyboardButton(text="↩️ Отменить", callback_data=f"cancel_review_{msg_id}")]
        ])
    elif media_type == "photo":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{msg_id}"),
                InlineKeyboardButton(text="✅➕ Водяной знак", callback_data=f"watermark_{msg_id}")
            ],
            [
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{msg_id}"),
                InlineKeyboardButton(text="⏳ Мут 7д", callback_data=f"mute_{msg_id}")
            ],
            [
                InlineKeyboardButton(text="🔨 Бан", callback_data=f"ban_{msg_id}"),
                InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"skip_{msg_id}")
            ],
            [
                InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{msg_id}"),
                InlineKeyboardButton(text="↩️ Отменить", callback_data=f"cancel_review_{msg_id}")
            ]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{msg_id}")],
            [
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{msg_id}"),
                InlineKeyboardButton(text="⏳ Мут 7д", callback_data=f"mute_{msg_id}")
            ],
            [
                InlineKeyboardButton(text="🔨 Бан", callback_data=f"ban_{msg_id}"),
                InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"skip_{msg_id}")
            ],
            [
                InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{msg_id}"),
                InlineKeyboardButton(text="↩️ Отменить", callback_data=f"cancel_review_{msg_id}")
            ]
        ])

    warnings = []
    if has_links:
        warnings.append("🔗 ССЫЛКИ")
    if insult_count >= INSULT_THRESHOLD:
        warnings.append(f"🤬 ОСКОРБЛЕНИЯ ({insult_count})")
    if media_type and not poll_data:
        warnings.append("🚫 МЕДИА")
    
    warning_text = f"\n\n⚠️ {' | '.join(warnings)}" if warnings else ""

    try:
        if media_type == "photo":
            await callback.message.edit_caption(
                caption=callback.message.caption + warning_text + poll_preview + "\n\n🔄 <b>Рассматривается...</b>",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        elif media_type == "video":
            await callback.message.edit_caption(
                caption=callback.message.caption + warning_text + poll_preview + "\n\n🔄 <b>Рассматривается...</b>",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                text=callback.message.text + warning_text + poll_preview + "\n\n🔄 <b>Рассматривается...</b>",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Error editing message in review: {e}")
        await callback.answer("❌ Ошибка при редактировании", show_alert=True)
        return

# ================= ВОДЯНОЙ ЗНАК =================

@dp.callback_query(F.data.startswith("watermark_"))
async def approve_with_watermark(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])

    async with db_pool.acquire() as db:
        cursor = await db.execute(
            "SELECT text, user_id, reviewer, media_type, media_file_id FROM messages WHERE id=?",
            (msg_id,)
        )
        result = await cursor.fetchone()
        if not result:
            await callback.answer("❌ Сообщение не найдено", show_alert=True)
            return

        text, user_id, reviewer, media_type, media_file_id = result

        if reviewer != callback.from_user.id:
            await callback.answer("❌ Сначала нужно начать рассмотрение", show_alert=True)
            return

        if media_type != "photo":
            await callback.answer("❌ Водяной знак только для фото", show_alert=True)
            return

        await db.execute("BEGIN TRANSACTION")
        try:
            await db.execute(
                "UPDATE messages SET status='processing' WHERE id=? AND status='pending'",
                (msg_id,)
            )
            await db.commit()
        except:
            await db.execute("ROLLBACK")
            await callback.answer("❌ Ошибка блокировки сообщения", show_alert=True)
            return

    try:
        new_file_id = await add_watermark_to_photo(media_file_id)
    except Exception as e:
        logger.error(f"Watermark error: {e}")
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE messages SET status='pending', reviewer=NULL WHERE id=?",
                (msg_id,)
            )
            await db.commit()
        await callback.answer("❌ Ошибка при наложении водяного знака", show_alert=True)
        return

    async with db_pool.acquire() as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key='post_style'")
        style = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT value FROM settings WHERE key='post_counter'")
        counter = int((await cursor.fetchone())[0]) + 1
        
        await db.execute("BEGIN TRANSACTION")
        try:
            await db.execute("UPDATE settings SET value=? WHERE key='post_counter'", (str(counter),))
            await db.execute(
                "UPDATE messages SET status='approved', reviewed_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), msg_id)
            )
            await db.commit()
        except:
            await db.execute("ROLLBACK")
            await callback.answer("❌ Ошибка сохранения", show_alert=True)
            return

    escaped_text = escape_html(text) if text else ""
    
    if style == "1":
        header = f"💬 <b>Новое анонимное сообщение</b>\n\n"
        footer = f"\n\n━━━━━━━━━━━━━━\n✉ <a href='https://t.me/{BOT_USERNAME}'>Отправить сообщение</a>"
    elif style == "2":
        header = f"┌─────────────────┐\n│  ПОДСЛУШАНО  │\n└─────────────────┘\n\n"
        footer = f"\n\n➖➖➖➖➖➖➖➖➖\n✉ <a href='https://t.me/{BOT_USERNAME}'>Написать анонимно</a>"
    else:
        header = f"📌 <b>Анонимное сообщение</b>\n\n"
        footer = f"\n\n—\n<a href='https://t.me/{BOT_USERNAME}'>✉ Ответить</a>"

    try:
        await bot.send_photo(
            CHANNEL_ID,
            photo=new_file_id,
            caption=f"{header}{escaped_text}{footer}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error publishing watermarked photo: {e}")
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE messages SET status='processing', reviewed_at=NULL WHERE id=?",
                (msg_id,)
            )
            await db.commit()
        await callback.answer("❌ Ошибка публикации", show_alert=True)
        return

    center_status = " + фото-вставка" if os.path.exists("watermark_center.png") else ""
    
    try:
        if callback.message.photo or callback.message.video:
            await callback.message.edit_caption(
                caption=callback.message.caption.replace("\n\n🔄 <b>Рассматривается...</b>", "") + f"\n\n✅ <b>ОПУБЛИКОВАНО С ВОДЯНЫМ ЗНАКОМ{center_status}</b>",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                text=callback.message.text.replace("\n\n🔄 <b>Рассматривается...</b>", "") + f"\n\n✅ <b>ОПУБЛИКОВАНО С ВОДЯНЫМ ЗНАКОМ{center_status}</b>",
                reply_markup=None
            )
    except:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(f"✅ Фото #{msg_id} опубликовано с водяным знаком{center_status}")

    try:
        await bot.send_message(user_id, "✅ Ваше фото опубликовано в канале с водяным знаком!")
    except:
        pass

    await log_admin_action(callback.from_user.id, "approve_watermark", target_id=msg_id)

# ================= ПРОПУСК =================

@dp.callback_query(F.data.startswith("skip_"))
async def skip_message(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, пропустить", callback_data=f"confirm_skip_{msg_id}"),
         InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"cancel_skip_{msg_id}")]
    ])
    
    await callback.message.answer(
        f"⚠️ <b>Подтверждение пропуска</b>\n\n"
        f"Вы действительно хотите пропустить сообщение #{msg_id}?\n"
        f"Оно будет помечено как пропущенное и больше не появится в списке ожидающих.",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_skip_"))
async def confirm_skip(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[2])
    
    try:
        async with db_pool.acquire() as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                cursor = await db.execute(
                    "SELECT status FROM messages WHERE id=?",
                    (msg_id,)
                )
                result = await cursor.fetchone()
                
                if not result:
                    await db.execute("ROLLBACK")
                    await callback.answer("❌ Сообщение не найдено", show_alert=True)
                    return
                    
                status = result[0]
                if status != "pending":
                    await db.execute("ROLLBACK")
                    await callback.answer(f"❌ Сообщение уже {status}", show_alert=True)
                    return
                
                await db.execute(
                    "UPDATE messages SET skipped=1, reviewer=NULL WHERE id=?",
                    (msg_id,)
                )
                await db.commit()
            except:
                await db.execute("ROLLBACK")
                raise
    except Exception as e:
        logger.error(f"DB error in confirm_skip: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return
    
    cache_key = f"msg_{msg_id}"
    if cache_key in msg_cache:
        del msg_cache[cache_key]
    if "stats" in admin_cache:
        del admin_cache["stats"]
    pending_cache.clear()
    
    await callback.message.delete()
    await callback.message.answer(f"✅ Сообщение #{msg_id} пропущено")
    await log_admin_action(callback.from_user.id, "skip", target_id=msg_id)

@dp.callback_query(F.data.startswith("cancel_skip_"))
async def cancel_skip(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return
    msg_id = int(callback.data.split("_")[2])
    await callback.message.delete()
    await callback.message.answer(f"❌ Пропуск сообщения #{msg_id} отменен")
    await callback.answer()

# ================= ОТМЕНА РАССМОТРЕНИЯ =================

@dp.callback_query(F.data.startswith("cancel_review_"))
async def cancel_review(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[2])

    try:
        async with db_pool.acquire() as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                cursor = await db.execute(
                    "SELECT reviewer, user_id, media_type FROM messages WHERE id=?",
                    (msg_id,)
                )
                result = await cursor.fetchone()
                
                if not result:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сообщение не найдено", show_alert=True)
                    return
                    
                reviewer, user_id, media_type = result

                if reviewer != callback.from_user.id:
                    await db.execute("ROLLBACK")
                    await callback.answer("Вы не рассматриваете это сообщение", show_alert=True)
                    return

                await db.execute(
                    "UPDATE messages SET reviewer=NULL WHERE id=?",
                    (msg_id,)
                )
                await db.commit()
            except:
                await db.execute("ROLLBACK")
                raise
    except Exception as e:
        logger.error(f"DB error in cancel_review: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return

    cache_key = f"msg_{msg_id}"
    if cache_key in msg_cache:
        del msg_cache[cache_key]
    if "stats" in admin_cache:
        del admin_cache["stats"]
    pending_cache.clear()

    admin_name = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name
    review_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Перейти к рассмотрению", callback_data=f"review_{msg_id}")]
    ])

    for admin in ADMINS:
        if admin != callback.from_user.id:
            try:
                if admin == SUPER_ADMIN:
                    await bot.send_message(
                        admin,
                        f"🔄 <b>Рассмотрение отменено</b>\n\nАдмин {admin_name} отменил рассмотрение сообщения #{msg_id}\n\nСообщение снова доступно для проверки.\nОт пользователя: <code>{user_id}</code>",
                        reply_markup=review_keyboard,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await bot.send_message(
                        admin,
                        f"🔄 <b>Рассмотрение отменено</b>\n\nАдмин {admin_name} отменил рассмотрение сообщения #{msg_id}\n\nСообщение снова доступно для проверки.",
                        reply_markup=review_keyboard,
                        parse_mode=ParseMode.HTML
                    )
            except:
                pass

    try:
        if media_type in ["photo", "video"]:
            await callback.message.edit_caption(
                caption=callback.message.caption.replace("\n\n🔄 <b>Рассматривается...</b>", ""),
                reply_markup=review_keyboard
            )
        else:
            await callback.message.edit_text(
                text=callback.message.text.replace("\n\n🔄 <b>Рассматривается...</b>", ""),
                reply_markup=review_keyboard
            )
    except Exception as e:
        logger.error(f"Error editing message in cancel_review: {e}")
    
    await callback.answer("Рассмотрение отменено")
    await log_admin_action(callback.from_user.id, "cancel_review", target_id=msg_id)

# ================= ОДОБРЕНИЕ (включая опросы) =================

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])

    try:
        async with db_pool.acquire() as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                cursor = await db.execute(
                    "SELECT text, user_id, reviewer, media_type, media_file_id, poll_data FROM messages WHERE id=?",
                    (msg_id,)
                )
                result = await cursor.fetchone()

                if not result:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сообщение не найдено", show_alert=True)
                    return

                text, user_id, reviewer, media_type, media_file_id, poll_data = result

                if reviewer != callback.from_user.id:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сначала нужно начать рассмотрение", show_alert=True)
                    return

                await db.execute(
                    "UPDATE messages SET status='processing', reviewed_at=? WHERE id=? AND status='pending'",
                    (datetime.utcnow().isoformat(), msg_id)
                )

                cursor = await db.execute("SELECT value FROM settings WHERE key='post_counter'")
                counter = int((await cursor.fetchone())[0]) + 1
                await db.execute("UPDATE settings SET value=? WHERE key='post_counter'", (str(counter),))
                await db.commit()
            except:
                await db.execute("ROLLBACK")
                raise
    except Exception as e:
        logger.error(f"DB error in approve: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return

    cache_key = f"msg_{msg_id}"
    if cache_key in msg_cache:
        del msg_cache[cache_key]
    if "stats" in admin_cache:
        del admin_cache["stats"]
    pending_cache.clear()

    async with db_pool.acquire() as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key='post_style'")
        style = (await cursor.fetchone())[0]

    # Публикация опроса
    if poll_data:
        try:
            poll = json.loads(poll_data)
            
            # Получаем стиль
            async with db_pool.acquire() as db:
                cursor = await db.execute("SELECT value FROM settings WHERE key='post_style'")
                style = (await cursor.fetchone())[0]
            
            # Формируем заголовок и отправляем
            if style == "1":
                header = "💬 <b>Новый анонимный опрос</b>\n\n"
            elif style == "2":
                header = "┌─────────────────┐\n│  ПОДСЛУШАНО  │\n└─────────────────┘\n\n"
            else:
                header = "📌 <b>Анонимный опрос</b>\n\n"
            
            await bot.send_message(
                CHANNEL_ID,
                f"{header}<blockquote>{escape_html(poll['question'])}</blockquote>",
                parse_mode=ParseMode.HTML
            )
            
            # Отправляем опрос (без дублирования вопроса в заголовке)
            await bot.send_poll(
                CHANNEL_ID,
                question=" ",  # Пустой вопрос, вариант ответа - голосование снизу
                options=poll['options'],
                is_anonymous=True,
                allows_multiple_answers=poll.get('allows_multiple_answers', True),
                type='regular'
            )
            
            # Обновляем статус
            async with db_pool.acquire() as db:
                await db.execute(
                    "UPDATE messages SET status='approved' WHERE id=?",
                    (msg_id,)
                )
                await db.commit()
            
            try:
                await bot.send_message(user_id, "✅ Ваш опрос опубликован в канале!")
            except:
                pass
            
            for admin in ADMINS:
                try:
                    await bot.send_message(admin, f"📊 <b>Опубликован опрос #{counter}</b> (сообщение #{msg_id})")
                except:
                pass
            
            await log_admin_action(callback.from_user.id, "approve", target_id=msg_id, details=f"poll #{counter}")
            
            try:
                if callback.message.photo or callback.message.video:
                    await callback.message.edit_caption(
                        caption=callback.message.caption.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n✅ <b>ОПРОС ОПУБЛИКОВАН</b>",
                        reply_markup=None
                    )
                else:
                    await callback.message.edit_text(
                        text=callback.message.text.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n✅ <b>ОПРОС ОПУБЛИКОВАН</b>",
                        reply_markup=None
                    )
            except:
                pass
            
            await callback.answer()
            return
            
        except Exception as e:
            logger.error(f"Error publishing poll: {e}")
            async with db_pool.acquire() as db:
                await db.execute(
                    "UPDATE messages SET status='pending', reviewed_at=NULL WHERE id=?",
                    (msg_id,)
                )
                await db.commit()
            await callback.answer("❌ Ошибка при публикации опроса", show_alert=True)
            return

    # Обычное сообщение
    escaped_text = escape_html(text) if text else ""
    
    if style == "1":
        header = f"💬 <b>Новое анонимное сообщение</b>\n\n"
        footer = f"\n\n━━━━━━━━━━━━━━\n✉ <a href='https://t.me/{BOT_USERNAME}'>Отправить сообщение</a>"
    elif style == "2":
        header = f"┌─────────────────┐\n│  ПОДСЛУШАНО  │\n└─────────────────┘\n\n"
        footer = f"\n\n➖➖➖➖➖➖➖➖➖\n✉ <a href='https://t.me/{BOT_USERNAME}'>Написать анонимно</a>"
    else:
        header = f"📌 <b>Анонимное сообщение</b>\n\n"
        footer = f"\n\n—\n<a href='https://t.me/{BOT_USERNAME}'>✉ Ответить</a>"

    try:
        if media_type == "photo":
            caption = f"{header}{escaped_text}{footer}" if escaped_text else f"{header}{footer}"
            await bot.send_photo(
                CHANNEL_ID,
                photo=media_file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif media_type == "video":
            caption = f"{header}{escaped_text}{footer}" if escaped_text else f"{header}{footer}"
            await bot.send_video(
                CHANNEL_ID,
                video=media_file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        else:
            await bot.send_message(
                CHANNEL_ID,
                f"{header}<blockquote>{escaped_text}</blockquote>{footer}",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE messages SET status='approved' WHERE id=?",
                (msg_id,)
            )
            await db.commit()
            
    except Exception as e:
        logger.error(f"PUBLISH ERROR: {e}")
        async with db_pool.acquire() as db:
            await db.execute(
                "UPDATE messages SET status='processing', reviewed_at=NULL WHERE id=?",
                (msg_id,)
            )
            await db.commit()
        await callback.answer("❌ Ошибка при публикации", show_alert=True)
        return

    try:
        if callback.message.photo or callback.message.video:
            await callback.message.edit_caption(
                caption=callback.message.caption.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n✅ <b>ОДОБРЕНО</b>",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                text=callback.message.text.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n✅ <b>ОДОБРЕНО</b>",
                reply_markup=None
            )
    except:
        pass
    
    try:
        await bot.send_message(user_id, "✅ Ваше сообщение опубликовано в канале!")
    except:
        pass

    for admin in ADMINS:
        try:
            await bot.send_message(admin, f"📝 <b>Опубликован пост #{counter}</b> (сообщение #{msg_id})")
        except:
            pass

    await log_admin_action(callback.from_user.id, "approve", target_id=msg_id, details=f"post #{counter}")

# ================= ОТКЛОНЕНИЕ =================

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])

    try:
        async with db_pool.acquire() as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                cursor = await db.execute(
                    "SELECT user_id, reviewer, media_type FROM messages WHERE id=?",
                    (msg_id,)
                )
                result = await cursor.fetchone()

                if not result:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сообщение не найдено", show_alert=True)
                    return

                user_id, reviewer, media_type = result

                if reviewer != callback.from_user.id:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сначала нужно начать рассмотрение", show_alert=True)
                    return

                await db.execute(
                    "UPDATE messages SET status='rejected', reviewed_at=? WHERE id=?",
                    (datetime.utcnow().isoformat(), msg_id)
                )
                await db.commit()
            except:
                await db.execute("ROLLBACK")
                raise
    except Exception as e:
        logger.error(f"DB error in reject: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return

    cache_key = f"msg_{msg_id}"
    if cache_key in msg_cache:
        del msg_cache[cache_key]
    if "stats" in admin_cache:
        del admin_cache["stats"]
    pending_cache.clear()

    try:
        if callback.message.photo or callback.message.video:
            await callback.message.edit_caption(
                caption=callback.message.caption.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n❌ <b>ОТКЛОНЕНО</b>",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                text=callback.message.text.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n❌ <b>ОТКЛОНЕНО</b>",
                reply_markup=None
            )
    except:
        pass
    
    try:
        await bot.send_message(user_id, "❌ Ваше сообщение отклонено модератором.")
    except:
        pass

    await log_admin_action(callback.from_user.id, "reject", target_id=msg_id)

# ================= МУТ =================

@dp.callback_query(F.data.startswith("mute_"))
async def mute(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])

    try:
        async with db_pool.acquire() as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                cursor = await db.execute(
                    "SELECT user_id, reviewer, media_type FROM messages WHERE id=?",
                    (msg_id,)
                )
                result = await cursor.fetchone()

                if not result:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сообщение не найдено", show_alert=True)
                    return

                user_id, reviewer, media_type = result

                if reviewer != callback.from_user.id:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сначала нужно начать рассмотрение", show_alert=True)
                    return

                mute_until = datetime.utcnow() + timedelta(days=7)

                await db.execute(
                    "UPDATE users SET mute_until=? WHERE user_id=?",
                    (mute_until.isoformat(), user_id)
                )
                await db.execute(
                    "UPDATE messages SET status='muted', reviewed_at=? WHERE id=?",
                    (datetime.utcnow().isoformat(), msg_id)
                )
                await db.commit()
            except:
                await db.execute("ROLLBACK")
                raise
    except Exception as e:
        logger.error(f"DB error in mute: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return

    cache_key = f"msg_{msg_id}"
    if cache_key in msg_cache:
        del msg_cache[cache_key]
    if "stats" in admin_cache:
        del admin_cache["stats"]
    if user_id in user_cache:
        del user_cache[user_id]
    pending_cache.clear()

    try:
        if callback.message.photo or callback.message.video:
            await callback.message.edit_caption(
                caption=callback.message.caption.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n🔇 <b>МУТ 7 ДНЕЙ</b>",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                text=callback.message.text.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n🔇 <b>МУТ 7 ДНЕЙ</b>",
                reply_markup=None
            )
    except:
        pass

    try:
        await bot.send_message(user_id, f"⏳ Вы получили мут на 7 дней за нарушение правил.")
    except:
        pass

    await log_admin_action(callback.from_user.id, "mute", target_id=user_id, details="7 days")

# ================= БАН =================

@dp.callback_query(F.data.startswith("ban_"))
async def ban(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])

    try:
        async with db_pool.acquire() as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                cursor = await db.execute(
                    "SELECT user_id, reviewer, media_type FROM messages WHERE id=?",
                    (msg_id,)
                )
                result = await cursor.fetchone()

                if not result:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сообщение не найдено", show_alert=True)
                    return

                user_id, reviewer, media_type = result

                if reviewer != callback.from_user.id:
                    await db.execute("ROLLBACK")
                    await callback.answer("Сначала нужно начать рассмотрение", show_alert=True)
                    return

                if callback.from_user.id != SUPER_ADMIN:
                    await db.execute(
                        "INSERT INTO ban_requests(target_id, admin_id, message_id, created_at) VALUES(?,?,?,?)",
                        (user_id, callback.from_user.id, msg_id, datetime.utcnow().isoformat())
                    )
                    await db.commit()

                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Подтвердить бан", callback_data=f"confirmban_{user_id}"),
                         InlineKeyboardButton(text="❌ Отмена", callback_data="cancelban")]
                    ])

                    await bot.send_message(
                        SUPER_ADMIN,
                        f"⚠ Запрос на бан пользователя {user_id}\nОт админа: @{callback.from_user.username or callback.from_user.first_name}\nСообщение: #{msg_id}",
                        reply_markup=keyboard
                    )

                    await callback.answer("Запрос отправлен главному админу.")
                    return

                await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
                await db.execute(
                    "UPDATE messages SET status='banned', reviewed_at=? WHERE id=?",
                    (datetime.utcnow().isoformat(), msg_id)
                )
                await db.commit()
            except:
                await db.execute("ROLLBACK")
                raise
    except Exception as e:
        logger.error(f"DB error in ban: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return

    cache_key = f"msg_{msg_id}"
    if cache_key in msg_cache:
        del msg_cache[cache_key]
    if "stats" in admin_cache:
        del admin_cache["stats"]
    if user_id in user_cache:
        del user_cache[user_id]
    pending_cache.clear()

    try:
        if callback.message.photo or callback.message.video:
            await callback.message.edit_caption(
                caption=callback.message.caption.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n⛔ <b>ЗАБАНЕНО</b>",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                text=callback.message.text.replace("\n\n🔄 <b>Рассматривается...</b>", "") + "\n\n⛔ <b>ЗАБАНЕНО</b>",
                reply_markup=None
            )
    except:
        pass

    try:
        await bot.send_message(user_id, "⛔ Вы заблокированы за нарушение правил.")
    except:
        pass

    await log_admin_action(callback.from_user.id, "ban", target_id=user_id)

# ================= ПОДТВЕРЖДЕНИЕ БАНА =================

@dp.callback_query(F.data.startswith("confirmban_"))
async def confirm_ban(callback: CallbackQuery):
    if callback.from_user.id != SUPER_ADMIN:
        return

    user_id = int(callback.data.split("_")[1])

    try:
        async with db_pool.acquire() as db:
            await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
            await db.execute(
                "UPDATE ban_requests SET status='approved' WHERE target_id=? AND status='pending'",
                (user_id,)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in confirm_ban: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return

    if user_id in user_cache:
        del user_cache[user_id]

    await callback.message.edit_text(f"✅ Бан пользователя {user_id} подтвержден")
    
    try:
        await bot.send_message(user_id, "⛔ Вы заблокированы.")
    except:
        pass

@dp.callback_query(F.data == "cancelban")
async def cancel_ban(callback: CallbackQuery):
    if callback.from_user.id != SUPER_ADMIN:
        return
    await callback.message.edit_text("❌ Бан отменен")

# ================= ПОИСК ПОЛЬЗОВАТЕЛЯ =================

@dp.message(F.text == "👥 Управление пользователями")
async def admin_users(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="find_user")],
        [InlineKeyboardButton(text="📋 Список забаненных", callback_data="list_banned")],
        [InlineKeyboardButton(text="📋 Список замученных", callback_data="list_muted")]
    ])
    
    await message.answer(
        "👥 <b>Управление пользователями</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "find_user")
async def find_user_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return
    await state.set_state(AdminStates.waiting_for_user_search)
    await callback.message.answer(
        "🔍 Введите ID пользователя, username или имя для поиска:\n(или отправьте /cancel для отмены)"
    )
    await callback.answer()

@dp.message(AdminStates.waiting_for_user_search)
async def process_user_search(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await state.clear()
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Поиск отменен")
        return
    
    search = message.text.strip()
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("""
                SELECT user_id, username, first_name, banned, mute_until, maintenance_exception, captcha_passed
                FROM users 
                WHERE user_id LIKE ? OR username LIKE ? OR first_name LIKE ?
                LIMIT 10
            """, (f"%{search}%", f"%{search}%", f"%{search}%"))
            users = await cursor.fetchall()
    except Exception as e:
        logger.error(f"DB error in process_user_search: {e}")
        await message.answer("❌ Ошибка поиска")
        await state.clear()
        return
    
    if not users:
        await message.answer("❌ Пользователи не найдены")
        await state.clear()
        return
    
    for user in users:
        user_id, username, first_name, banned, mute_until, maintenance_exception, captcha_passed = user
        status = []
        if banned:
            status.append("⛔ Забанен")
        if maintenance_exception:
            status.append("⭐ Исключение")
        if captcha_passed:
            status.append("✅ Верифицирован")
        else:
            status.append("🤖 Не прошел капчу")
        
        if mute_until:
            try:
                mute_date = datetime.fromisoformat(mute_until)
                if mute_date > datetime.utcnow():
                    status.append(f"🔇 В муте до {mute_date.strftime('%d.%m.%Y %H:%M')}")
            except:
                pass
        
        if not status:
            status = ["✅ Активен"]
        
        display_name = first_name if first_name else "нет"
        if len(display_name) > 20:
            display_name = display_name[:20] + "..."
        
        text = (
            f"👤 <b>Пользователь</b>\n"
            f"ID: <code>{user_id}</code>\n"
            f"Username: @{username or 'нет'}\n"
            f"Имя: {display_name}\n"
            f"Статус: {', '.join(status)}"
        )
        
        keyboard_buttons = []
        
        if message.from_user.id == SUPER_ADMIN:
            keyboard_buttons = [
                [InlineKeyboardButton(
                    text="✅ Разбанить" if banned else "🔨 Забанить", 
                    callback_data=f"toggle_ban_{user_id}"
                )],
                [InlineKeyboardButton(
                    text="🔊 Размутить" if mute_until else "⏳ Замутить", 
                    callback_data=f"toggle_mute_{user_id}"
                )],
                [InlineKeyboardButton(
                    text="⭐ Убрать исключение" if maintenance_exception else "⭐ Добавить исключение", 
                    callback_data=f"toggle_exception_{user_id}"
                )]
            ]
        else:
            keyboard_buttons = [
                [InlineKeyboardButton(
                    text="🔊 Размутить" if mute_until else "⏳ Замутить", 
                    callback_data=f"toggle_mute_{user_id}"
                )]
            ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer(text, reply_markup=keyboard)
        await asyncio.sleep(0.2)
    
    await state.clear()

# ================= СПИСКИ ЗАБАНЕННЫХ/ЗАМУЧЕННЫХ =================

@dp.callback_query(F.data == "list_banned")
async def list_banned(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT user_id, username, first_name FROM users WHERE banned=1 ORDER BY user_id DESC LIMIT 20"
            )
            banned_users = await cursor.fetchall()
    except Exception as e:
        logger.error(f"DB error in list_banned: {e}")
        await callback.answer("❌ Ошибка получения списка")
        return
    
    if not banned_users:
        await callback.message.answer("📋 Список забаненных пуст")
        await callback.answer()
        return
    
    text = "📋 <b>Забаненные пользователи (последние 20):</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for user_id, username, first_name in banned_users:
        display_name = first_name if first_name else "без имени"
        if len(display_name) > 15:
            display_name = display_name[:15] + "..."
        
        text += f"• {display_name} (@{username or 'нет'}) - <code>{user_id}</code>\n"
        
        if callback.from_user.id == SUPER_ADMIN:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"✅ Разбанить {user_id}", 
                    callback_data=f"unban_{user_id}"
                )
            ])
    
    if keyboard.inline_keyboard:
        await callback.message.answer(text, reply_markup=keyboard)
    else:
        await callback.message.answer(text)
    
    await callback.answer()

@dp.callback_query(F.data == "list_muted")
async def list_muted(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("""
                SELECT user_id, username, first_name, mute_until 
                FROM users 
                WHERE mute_until > datetime('now') 
                ORDER BY mute_until DESC 
                LIMIT 20
            """)
            muted_users = await cursor.fetchall()
    except Exception as e:
        logger.error(f"DB error in list_muted: {e}")
        await callback.answer("❌ Ошибка получения списка")
        return
    
    if not muted_users:
        await callback.message.answer("📋 Список замученных пуст")
        await callback.answer()
        return
    
    text = "📋 <b>Пользователи в муте (последние 20):</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for user_id, username, first_name, mute_until in muted_users:
        display_name = first_name if first_name else "без имени"
        if len(display_name) > 15:
            display_name = display_name[:15] + "..."
        
        try:
            mute_date = datetime.fromisoformat(mute_until)
            date_str = mute_date.strftime('%d.%m.%Y %H:%M')
        except:
            date_str = mute_until[:16] if mute_until else "неизвестно"
        
        text += f"• {display_name} (@{username or 'нет'}) - <code>{user_id}</code>\n  до {date_str}\n"
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🔊 Размутить {user_id}", 
                callback_data=f"unmute_{user_id}"
            )
        ])
    
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

# ================= UNBAN/UNMUTE =================

@dp.callback_query(F.data.startswith("unban_"))
async def unban_user(callback: CallbackQuery):
    if callback.from_user.id != SUPER_ADMIN:
        await callback.answer("❌ Только главный админ", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])

    async with db_pool.acquire() as db:
        await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
        await db.commit()

    if user_id in user_cache:
        del user_cache[user_id]

    await callback.message.edit_text(f"✅ Пользователь {user_id} разбанен")
    await callback.answer()

@dp.callback_query(F.data.startswith("unmute_"))
async def unmute_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split("_")[1])

    async with db_pool.acquire() as db:
        await db.execute("UPDATE users SET mute_until=NULL WHERE user_id=?", (user_id,))
        await db.commit()

    if user_id in user_cache:
        del user_cache[user_id]

    await callback.message.edit_text(f"✅ Пользователь {user_id} размучен")
    await callback.answer()

# ================= ОЖИДАЮЩИЕ ПРОВЕРКИ =================

@dp.message(F.text == "📨 Ожидающие проверки")
async def admin_pending_messages(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE status='pending' AND skipped=0"
            )
            total_pending = (await cursor.fetchone())[0]
            
            cursor = await db.execute("""
                SELECT id, user_id, media_type, 
                       substr(text, 1, 50) as short_text, 
                       created_at, has_links, insult_count, poll_data
                FROM messages 
                WHERE status='pending' AND skipped=0
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            pending_messages = await cursor.fetchall()
    except Exception as e:
        logger.error(f"DB error in admin_pending_messages: {e}")
        await message.answer("❌ Ошибка получения списка сообщений")
        return
    
    if not pending_messages:
        await message.answer("📨 Нет сообщений, ожидающих проверки")
        return
    
    text = f"📨 Ожидают проверки: {total_pending}\n\n"
    if total_pending > 10:
        text += f"Показаны последние 10 из {total_pending}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for msg_id, user_id, media_type, short_text, created_at, has_links, insult_count, poll_data in pending_messages:
        try:
            msg_date = datetime.fromisoformat(created_at)
            date_str = msg_date.strftime('%d.%m %H:%M')
        except:
            date_str = created_at[:16] if created_at else "неизвестно"
        
        if media_type == "poll":
            emoji = "📊"
            content_type = "Опрос"
        elif media_type == "photo":
            emoji = "📸"
            content_type = "Фото"
        elif media_type == "video":
            emoji = "🎥"
            content_type = "Видео"
        else:
            emoji = "📝"
            content_type = "Текст"
        
        warnings = []
        if has_links:
            warnings.append("🔗")
        if insult_count >= INSULT_THRESHOLD:
            warnings.append(f"🤬{insult_count}")
        
        warning_str = f" {' '.join(warnings)}" if warnings else ""
        
        clean_text = re.sub(r'<[^>]+>', '', short_text) if short_text else ""
        display_text = clean_text.replace('\n', ' ').strip() if clean_text else "без текста"
        if len(display_text) > 30:
            display_text = display_text[:30] + "..."
        
        if message.from_user.id == SUPER_ADMIN:
            text += f"{emoji} #{msg_id}{warning_str} | {date_str}\n"
            text += f"👤 ID: {user_id}\n"
        else:
            text += f"{emoji} #{msg_id}{warning_str} | {date_str}\n"
        
        text += f"💬 {display_text}\n\n"
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🔍 Рассмотреть #{msg_id} ({content_type})",
                callback_data=f"review_{msg_id}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_pending")
    ])
    
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data == "refresh_pending")
async def refresh_pending(callback: CallbackQuery):
    """Обновить список ожидающих сообщений"""
    if callback.from_user.id not in ADMINS:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE status='pending' AND skipped=0"
            )
            total_pending = (await cursor.fetchone())[0]
            
            cursor = await db.execute("""
                SELECT id, user_id, media_type, 
                       substr(text, 1, 50) as short_text, 
                       created_at, has_links, insult_count, poll_data
                FROM messages 
                WHERE status='pending' AND skipped=0
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            pending_messages = await cursor.fetchall()
    except Exception as e:
        logger.error(f"DB error in refresh_pending: {e}")
        await callback.answer("❌ Ошибка обновления")
        return
    
    if not pending_messages:
        await callback.message.edit_text("📨 Нет сообщений, ожидающих проверки")
        await callback.answer()
        return
    
    text = f"📨 Ожидают проверки: {total_pending}\n\n"
    if total_pending > 10:
        text += f"Показаны последние 10 из {total_pending}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for msg_id, user_id, media_type, short_text, created_at, has_links, insult_count, poll_data in pending_messages:
        try:
            msg_date = datetime.fromisoformat(created_at)
            date_str = msg_date.strftime('%d.%m %H:%M')
        except:
            date_str = created_at[:16] if created_at else "неизвестно"
        
        if media_type == "poll":
            emoji = "📊"
            content_type = "Опрос"
        elif media_type == "photo":
            emoji = "📸"
            content_type = "Фото"
        elif media_type == "video":
            emoji = "🎥"
            content_type = "Видео"
        else:
            emoji = "📝"
            content_type = "Текст"
        
        warnings = []
        if has_links:
            warnings.append("🔗")
        if insult_count >= INSULT_THRESHOLD:
            warnings.append(f"🤬{insult_count}")
        
        warning_str = f" {' '.join(warnings)}" if warnings else ""
        
        clean_text = re.sub(r'<[^>]+>', '', short_text) if short_text else ""
        display_text = clean_text.replace('\n', ' ').strip() if clean_text else "без текста"
        if len(display_text) > 30:
            display_text = display_text[:30] + "..."
        
        if callback.from_user.id == SUPER_ADMIN:
            text += f"{emoji} #{msg_id}{warning_str} | {date_str}\n"
            text += f"👤 ID: {user_id}\n"
        else:
            text += f"{emoji} #{msg_id}{warning_str} | {date_str}\n"
        
        text += f"💬 {display_text}\n\n"
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🔍 Рассмотреть #{msg_id} ({content_type})",
                callback_data=f"review_{msg_id}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_pending")
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ================= УПРАВЛЕНИЕ ИСКЛЮЧЕНИЯМИ =================

@dp.message(F.text == "👥 Управление исключениями")
async def manage_exceptions(message: Message):
    if message.from_user.id != SUPER_ADMIN:
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT user_id, username, first_name FROM users WHERE maintenance_exception=1 LIMIT 20"
            )
            exceptions = await cursor.fetchall()
    except Exception as e:
        logger.error(f"DB error in manage_exceptions: {e}")
        exceptions = []
    
    text = "👥 Пользователи в исключении\n\n"
    if exceptions:
        for user_id, username, first_name in exceptions:
            text += f"• {first_name or '?'} (@{username or 'нет'}) - ID: {user_id}\n"
    else:
        text += "Список пуст"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить в исключение", callback_data="add_exception")],
        [InlineKeyboardButton(text="➖ Удалить из исключения", callback_data="remove_exception")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_exceptions")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data == "add_exception")
async def add_exception_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != SUPER_ADMIN:
        return
    await state.set_state(AdminStates.waiting_for_exception_add)
    await callback.message.answer("➕ Введите ID пользователя для добавления в исключение:\n(или отправьте /cancel для отмены)")
    await callback.answer()

@dp.callback_query(F.data == "remove_exception")
async def remove_exception_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != SUPER_ADMIN:
        return
    await state.set_state(AdminStates.waiting_for_exception_remove)
    await callback.message.answer("➖ Введите ID пользователя для удаления из исключения:\n(или отправьте /cancel для отмены)")
    await callback.answer()

@dp.callback_query(F.data == "close_exceptions")
async def close_exceptions(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@dp.message(AdminStates.waiting_for_exception_add)
async def process_add_exception(message: Message, state: FSMContext):
    if message.from_user.id != SUPER_ADMIN:
        await state.clear()
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число.")
        return
    
    try:
        async with db_pool.acquire() as db:
            await db.execute("UPDATE users SET maintenance_exception=1 WHERE user_id=?", (user_id,))
            await db.commit()
            maintenance_exceptions.add(user_id)
            
        await message.answer(f"✅ Пользователь {user_id} добавлен в исключение")
        await log_admin_action(message.from_user.id, "exception_add", user_id)
    except Exception as e:
        logger.error(f"DB error in process_add_exception: {e}")
        await message.answer("❌ Ошибка при добавлении в исключение")
    
    await state.clear()

@dp.message(AdminStates.waiting_for_exception_remove)
async def process_remove_exception(message: Message, state: FSMContext):
    if message.from_user.id != SUPER_ADMIN:
        await state.clear()
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число.")
        return
    
    try:
        async with db_pool.acquire() as db:
            await db.execute("UPDATE users SET maintenance_exception=0 WHERE user_id=?", (user_id,))
            await db.commit()
            
            if user_id in maintenance_exceptions:
                maintenance_exceptions.remove(user_id)
            
        await message.answer(f"✅ Пользователь {user_id} удален из исключения")
        await log_admin_action(message.from_user.id, "exception_remove", user_id)
    except Exception as e:
        logger.error(f"DB error in process_remove_exception: {e}")
        await message.answer("❌ Ошибка при удалении из исключения")
    
    await state.clear()

# ================= HTTP СЕРВЕР И API ДЛЯ WEB APP =================

async def verify_telegram_auth(data: dict) -> bool:
    """Проверяет подлинность данных из Telegram Web App"""
    try:
        check_hash = data.get('hash', '')
        data_check_string = '\n'.join([
            f"{k}={v}" for k, v in sorted(data.items()) 
            if k != 'hash'
        ])
        
        secret_key = hashlib.sha256(TOKEN.encode()).digest()
        hmac_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac_hash == check_hash
    except Exception as e:
        logger.error(f"Auth verification error: {e}")
        return False

async def run_http_server():
    """Запускает HTTP-сервер для health checks и Web App API"""
    try:
        from aiohttp import web
        
        # ==================== HEALTH CHECK ====================
        
        async def handle(request):
            uptime_seconds = time.time() - start_time
            uptime_str = str(timedelta(seconds=int(uptime_seconds)))
            
            try:
                async with db_pool.acquire() as db:
                    cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE status='pending'")
                    pending_count = (await cursor.fetchone())[0]
                    cursor = await db.execute("SELECT COUNT(*) FROM users")
                    users_count = (await cursor.fetchone())[0]
            except:
                pending_count = 0
                users_count = 0
            
            mode, interval = get_current_mode_and_interval()
            
            return web.json_response({
                "status": "ok",
                "bot_name": BOT_USERNAME,
                "uptime": uptime_str,
                "pending_in_db": pending_count,
                "total_users": users_count,
                "night_mode_enabled": night_mode_enabled,
                "auto_mode_enabled": auto_mode_enabled,
                "maintenance": maintenance_mode,
                "current_mode": mode,
                "auto_interval_minutes": interval,
                "blacklist_size": len(blacklist_cache),
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # ==================== API: ДАШБОРД ====================
        
        async def api_dashboard(request):
            """API для дашборда Web App"""
            try:
                async with db_pool.acquire() as db:
                    cursor = await db.execute("""
                        SELECT 
                            (SELECT COUNT(*) FROM messages WHERE date(created_at) = date('now')) as today_posts,
                            (SELECT COUNT(*) FROM messages WHERE status='pending' AND skipped=0) as pending_count,
                            (SELECT COUNT(*) FROM users WHERE banned=1) as banned_count,
                            (SELECT COUNT(*) FROM users) as total_users,
                            (SELECT value FROM settings WHERE key='post_counter') as total_posts
                    """)
                    result = await cursor.fetchone()
                    
                    cursor = await db.execute("""
                        SELECT admin_id, action, target_id, created_at
                        FROM admin_actions
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                    recent_actions = await cursor.fetchall()
                    
                    actions_list = []
                    for action in recent_actions:
                        actions_list.append({
                            "admin_id": action[0],
                            "action": action[1],
                            "target_id": action[2],
                            "created_at": action[3]
                        })
                    
                    mode, interval = get_current_mode_and_interval()
                    
                    return web.json_response({
                        "today_posts": result[0] or 0,
                        "pending_count": result[1] or 0,
                        "banned_count": result[2] or 0,
                        "total_users": result[3] or 0,
                        "total_posts": result[4] or 0,
                        "current_mode": mode,
                        "interval": interval,
                        "recent_actions": actions_list
                    })
            except Exception as e:
                logger.error(f"API dashboard error: {e}")
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: ОЧЕРЕДЬ МОДЕРАЦИИ ====================
        
        async def api_pending_messages(request):
            """API для получения очереди сообщений"""
            try:
                async with db_pool.acquire() as db:
                    cursor = await db.execute("""
                        SELECT id, media_type, substr(text, 1, 200) as preview, 
                               created_at, has_links, insult_count, poll_data
                        FROM messages
                        WHERE status='pending' AND skipped=0
                        ORDER BY created_at DESC
                        LIMIT 50
                    """)
                    messages = await cursor.fetchall()
                    
                    result = []
                    for msg in messages:
                        clean_text = re.sub(r'<[^>]+>', '', msg[2]) if msg[2] else ""
                        
                        msg_type = "text"
                        if msg[1] == "photo":
                            msg_type = "photo"
                        elif msg[1] == "video":
                            msg_type = "video"
                        elif msg[6]:  # poll_data
                            msg_type = "poll"
                        
                        result.append({
                            "id": msg[0],
                            "type": msg_type,
                            "preview": clean_text[:200],
                            "created_at": msg[3],
                            "has_links": bool(msg[4]),
                            "insult_count": msg[5] or 0
                        })
                    
                    return web.json_response({"messages": result})
            except Exception as e:
                logger.error(f"API pending error: {e}")
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: ОДОБРИТЬ ====================
        
        async def api_approve(request):
            """API для одобрения сообщения"""
            try:
                data = await request.json()
                msg_id = data.get('msg_id')
                admin_id = data.get('admin_id')
                
                async with db_pool.acquire() as db:
                    await db.execute("BEGIN TRANSACTION")
                    try:
                        cursor = await db.execute(
                            "SELECT text, user_id, media_type, media_file_id, poll_data FROM messages WHERE id=?",
                            (msg_id,)
                        )
                        msg = await cursor.fetchone()
                        
                        if not msg:
                            await db.execute("ROLLBACK")
                            return web.json_response({"error": "Сообщение не найдено"}, status=404)
                        
                        text, user_id, media_type, media_file_id, poll_data = msg
                        
                        # Помечаем как одобренное
                        await db.execute(
                            "UPDATE messages SET status='approved', reviewed_at=?, reviewer=? WHERE id=?",
                            (datetime.utcnow().isoformat(), admin_id, msg_id)
                        )
                        
                        # Обновляем счетчик
                        cursor = await db.execute("SELECT value FROM settings WHERE key='post_counter'")
                        counter = int((await cursor.fetchone())[0]) + 1
                        await db.execute("UPDATE settings SET value=? WHERE key='post_counter'", (str(counter),))
                        
                        await db.commit()
                        
                        await log_admin_action(admin_id, "approve", target_id=msg_id, details=f"web post #{counter}")
                        
                    except Exception as e:
                        await db.execute("ROLLBACK")
                        raise e
                
                return web.json_response({"success": True, "post_number": counter})
                
            except Exception as e:
                logger.error(f"API approve error: {e}")
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: ОТКЛОНИТЬ ====================
        
        async def api_reject(request):
            """API для отклонения сообщения"""
            try:
                data = await request.json()
                msg_id = data.get('msg_id')
                admin_id = data.get('admin_id')
                
                async with db_pool.acquire() as db:
                    await db.execute(
                        "UPDATE messages SET status='rejected', reviewed_at=?, reviewer=? WHERE id=?",
                        (datetime.utcnow().isoformat(), admin_id, msg_id)
                    )
                    await db.commit()
                    
                    await log_admin_action(admin_id, "reject", target_id=msg_id, details="web")
                
                return web.json_response({"success": True})
            except Exception as e:
                logger.error(f"API reject error: {e}")
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: ПРОПУСТИТЬ ====================
        
        async def api_skip(request):
            """API для пропуска сообщения"""
            try:
                data = await request.json()
                msg_id = data.get('msg_id')
                admin_id = data.get('admin_id')
                
                async with db_pool.acquire() as db:
                    await db.execute(
                        "UPDATE messages SET skipped=1, reviewer=? WHERE id=?",
                        (admin_id, msg_id)
                    )
                    await db.commit()
                    
                    await log_admin_action(admin_id, "skip", target_id=msg_id, details="web")
                
                return web.json_response({"success": True})
            except Exception as e:
                logger.error(f"API skip error: {e}")
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: МУТ ====================
        
        async def api_mute_user(request):
            """API для мута пользователя"""
            try:
                data = await request.json()
                user_id = data.get('user_id')
                admin_id = data.get('admin_id')
                days = data.get('days', 7)
                
                mute_until = datetime.utcnow() + timedelta(days=days)
                
                async with db_pool.acquire() as db:
                    await db.execute(
                        "UPDATE users SET mute_until=? WHERE user_id=?",
                        (mute_until.isoformat(), user_id)
                    )
                    await db.commit()
                    
                    if user_id in user_cache:
                        del user_cache[user_id]
                    
                    await log_admin_action(admin_id, "mute", target_id=user_id, details=f"web {days}d")
                
                return web.json_response({"success": True, "mute_until": mute_until.isoformat()})
            except Exception as e:
                logger.error(f"API mute error: {e}")
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: ПОИСК ПОЛЬЗОВАТЕЛЕЙ ====================
        
        async def api_user_search(request):
            """API для поиска пользователей"""
            try:
                query = request.query.get('q', '')
                
                async with db_pool.acquire() as db:
                    cursor = await db.execute("""
                        SELECT user_id, username, first_name, banned, mute_until, 
                               maintenance_exception, captcha_passed
                        FROM users 
                        WHERE user_id LIKE ? OR username LIKE ? OR first_name LIKE ?
                        LIMIT 10
                    """, (f"%{query}%", f"%{query}%", f"%{query}%"))
                    users = await cursor.fetchall()
                    
                    result = []
                    for user in users:
                        result.append({
                            "user_id": user[0],
                            "username": user[1],
                            "first_name": user[2],
                            "banned": bool(user[3]),
                            "mute_until": user[4],
                            "maintenance_exception": bool(user[5]),
                            "captcha_passed": bool(user[6])
                        })
                    
                    return web.json_response({"users": result})
            except Exception as e:
                logger.error(f"API user search error: {e}")
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: СПИСОК ЗАБАНЕННЫХ ====================
        
        async def api_banned_users(request):
            """API для списка забаненных"""
            try:
                async with db_pool.acquire() as db:
                    cursor = await db.execute(
                        "SELECT user_id, username, first_name FROM users WHERE banned=1 LIMIT 50"
                    )
                    users = await cursor.fetchall()
                    
                    result = [{"user_id": u[0], "username": u[1], "first_name": u[2]} for u in users]
                    return web.json_response({"users": result})
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: СПИСОК ЗАМУЧЕННЫХ ====================
        
        async def api_muted_users(request):
            """API для списка замученных"""
            try:
                async with db_pool.acquire() as db:
                    cursor = await db.execute("""
                        SELECT user_id, username, first_name, mute_until 
                        FROM users 
                        WHERE mute_until > datetime('now') 
                        LIMIT 50
                    """)
                    users = await cursor.fetchall()
                    
                    result = [{
                        "user_id": u[0], 
                        "username": u[1], 
                        "first_name": u[2],
                        "mute_until": u[3]
                    } for u in users]
                    return web.json_response({"users": result})
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: ПРОВЕРКА РОЛИ ====================
        
        async def api_check_role(request):
            """API для проверки роли админа"""
            try:
                user_id = request.query.get('user_id', '0')
                user_id = int(user_id)
                
                is_super = user_id == SUPER_ADMIN
                is_admin = user_id in ADMINS
                
                return web.json_response({
                    "is_admin": is_admin,
                    "is_super_admin": is_super,
                    "user_id": user_id
                })
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: БАН ====================
        
        async def api_ban_user(request):
            """API для бана пользователя"""
            try:
                data = await request.json()
                user_id = data.get('user_id')
                admin_id = data.get('admin_id')
                
                # Только супер-админ может банить
                if admin_id != SUPER_ADMIN:
                    return web.json_response({"error": "Только супер-админ"}, status=403)
                
                async with db_pool.acquire() as db:
                    await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
                    await db.commit()
                    
                    if user_id in user_cache:
                        del user_cache[user_id]
                    
                    await log_admin_action(admin_id, "ban", target_id=user_id, details="web")
                
                return web.json_response({"success": True})
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: РАЗБАН ====================
        
        async def api_unban_user(request):
            """API для разбана пользователя"""
            try:
                data = await request.json()
                user_id = data.get('user_id')
                admin_id = data.get('admin_id')
                
                if admin_id != SUPER_ADMIN:
                    return web.json_response({"error": "Только супер-админ"}, status=403)
                
                async with db_pool.acquire() as db:
                    await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
                    await db.commit()
                    
                    if user_id in user_cache:
                        del user_cache[user_id]
                    
                    await log_admin_action(admin_id, "unban", target_id=user_id, details="web")
                
                return web.json_response({"success": True})
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)
        
        # ==================== API: НАСТРОЙКИ ====================
   
        async def api_settings(request):
            if request.method == 'GET':
                try:
                    async with db_pool.acquire() as db:
                        cursor = await db.execute("SELECT key, value FROM settings")
                        settings = await cursor.fetchall()
                        result = {}
                        for key, value in settings:
                            result[key] = value
                        result['maintenance'] = '1' if maintenance_mode else '0'
                        return web.json_response(result)
                except Exception as e:
                    return web.json_response({"error": str(e)}, status=500)

            if request.method == 'POST':
                try:
                    data = await request.json()
                    async with db_pool.acquire() as db:
                        for key, value in data.items():
                            await db.execute(
                                "UPDATE settings SET value=? WHERE key=?",
                                (str(value), key)
                            )
                        await db.commit()
                    return web.json_response({"success": True})
                except Exception as e:
                    return web.json_response({"error": str(e)}, status=500)

            return web.json_response({"error": "Method not allowed"}, status=405)
        
        # ==================== НАСТРОЙКА ПРИЛОЖЕНИЯ ====================
        
        app = web.Application()
        
        # Health check endpoints
        app.router.add_get('/', handle)
        app.router.add_get('/health', handle)
        app.router.add_get('/ping', handle)
        app.router.add_get('/status', handle)
        
        # Web App API endpoints
        app.router.add_get('/api/dashboard', api_dashboard)
        app.router.add_get('/api/pending', api_pending_messages)
        app.router.add_post('/api/approve', api_approve)
        app.router.add_post('/api/reject', api_reject)
        app.router.add_post('/api/skip', api_skip)
        app.router.add_post('/api/mute', api_mute_user)
        app.router.add_get('/api/users/search', api_user_search)
        app.router.add_get('/api/users/banned', api_banned_users)
        app.router.add_get('/api/users/muted', api_muted_users)
        app.router.add_get('/api/check_role', api_check_role)
        app.router.add_post('/api/users/ban', api_ban_user)
        app.router.add_post('/api/users/unban', api_unban_user)
        app.router.add_get('/api/settings', api_settings)
        app.router.add_post('/api/settings', api_settings)
        
        # CORS middleware
        async def cors_middleware(app, handler):
            async def middleware(request):
                if request.method == 'OPTIONS':
                    response = web.Response()
                    response.headers['Access-Control-Allow-Origin'] = '*'
                    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Telegram-Auth, Authorization'
                    response.headers['Access-Control-Max-Age'] = '3600'
                    return response
                
                response = await handler(request)
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Telegram-Auth, Authorization'
                return response
            return middleware
        
        app.middlewares.append(cors_middleware)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"🌐 HTTP Server with Web App API started on port {port}")
        logger.info(f"📱 API Endpoints: /api/dashboard, /api/pending, /api/settings, etc.")
        
    except Exception as e:
        logger.error(f"Failed to start HTTP server: {e}")

# ================= ГЛАВНАЯ ФУНКЦИЯ =================

async def main():
    global night_mode_enabled, auto_mode_enabled, maintenance_mode, shutdown_flag
    
    logger.info("=" * 50)
    logger.info("BOT STARTING...")
    
    await init_db()
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key='night_mode'")
            result = await cursor.fetchone()
            if result:
                night_mode_enabled = bool(int(result[0]))
            
            cursor = await db.execute("SELECT value FROM settings WHERE key='auto_mode'")
            result = await cursor.fetchone()
            if result:
                auto_mode_enabled = bool(int(result[0]))
            
            cursor = await db.execute("SELECT value FROM settings WHERE key='maintenance'")
            result = await cursor.fetchone()
            if result:
                maintenance_mode = bool(int(result[0]))
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
    
    asyncio.create_task(auto_post_messages())
    asyncio.create_task(check_long_pending_messages())
    asyncio.create_task(heartbeat())
    asyncio.create_task(run_http_server())
    
    logger.info("=" * 50)
    logger.info(f"🤖 Бот запущен!")
    logger.info(f"📱 Web App: {WEB_APP_URL}")
    logger.info(f"👑 SUPER_ADMIN: {SUPER_ADMIN}")
    logger.info(f"👥 ADMINS: {ADMINS}")
    logger.info(f"🌙 Ночной режим: {'✅' if night_mode_enabled else '❌'}")
    logger.info(f"☀️ Авто-режим: {'✅' if auto_mode_enabled else '❌'}")
    logger.info(f"🛠 Техработы: {'✅' if maintenance_mode else '❌'}")
    logger.info(f"📚 Черный список: {len(blacklist_cache)} слов")
    logger.info(f"❓ FAQ записей: {len(faq_cache)}")
    logger.info("=" * 50)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        shutdown_flag = True
        await asyncio.sleep(2)
        await db_pool.close_all()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")