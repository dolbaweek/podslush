import asyncio
import logging
from datetime import datetime, timedelta
import aiosqlite
from cachetools import TTLCache
import os
import re
import sys
import signal
from contextlib import asynccontextmanager
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramNetworkError
import aiohttp
from aiohttp import ClientConnectorError


# ================= КОНФИГУРАЦИЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =================

TOKEN = os.getenv('BOT_TOKEN', "8587934352:AAHdfiuD0VrNQ-Dp0801dYNnR7_nae92Aso")
CHANNEL_ID = int(os.getenv('CHANNEL_ID', "-1003713957228"))
SUPER_ADMIN = int(os.getenv('SUPER_ADMIN', "8438783644"))
ADMINS = [int(x) for x in os.getenv('ADMINS', "8438783644,8488564574,8283468381").split(',')]
BOT_USERNAME = os.getenv('BOT_USERNAME', "pods10_bot")

# Настройка логирования для Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ================= КОНСТАНТЫ =================

NIGHT_MODE_START = 0
NIGHT_MODE_END = 8
NIGHT_POST_INTERVAL = 30
INSULT_THRESHOLD = 4
LONG_MESSAGE_THRESHOLD = 60

# ================= ИНИЦИАЛИЗАЦИЯ БОТА =================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Кэши
user_cache = TTLCache(maxsize=1000, ttl=300)
msg_cache = TTLCache(maxsize=500, ttl=60)
admin_cache = TTLCache(maxsize=100, ttl=60)
pending_cache = TTLCache(maxsize=200, ttl=30)
blacklist_cache = TTLCache(maxsize=1000, ttl=300)

# Флаги
night_mode_enabled = False
maintenance_mode = False
maintenance_exceptions = set()
shutdown_flag = False

# ================= БАЗОВЫЕ СПИСКИ СЛОВ =================

# Базовый словарь оскорблений (можно расширять)
DEFAULT_INSULTS = [
    # ДУРАК / ТУПОСТЬ (все формы)
    "дурак", "дурака", "дураку", "дураком", "дураке", "дураки", "дураков", "дуракам", "дураками",
    "дура", "дуры", "дуре", "дуру", "дурой", "дур", "дурам", "дурами",
    "дурачок", "дурачка", "дурачку", "дурачком", "дурацкий", "дурацкого", "дурацкие",
    "идиот", "идиота", "идиоту", "идиотом", "идиоте", "идиоты", "идиотов", "идиотка", "идиотки",
    "идиотский", "идиотический", "идиотизм",
    "тупой", "тупого", "тупому", "тупым", "тупом", "тупая", "тупой", "тупую", "тупые", "тупых", "тупыми",
    "тупица", "тупицы", "тупице", "тупицу", "тупицей", "тупиц",
    "дебил", "дебила", "дебилу", "дебилом", "дебиле", "дебилы", "дебилов", "дебилка", "дебильной",
    "дебильный", "дебильного", "дебильные",
    "глупый", "глупого", "глупая", "глупой", "глупые", "глупых", "глупость",

    # ЖИВОТНЫЕ КАК ОСКОРБЛЕНИЯ
    "козел", "козла", "козлу", "козлом", "козле", "козлы", "козлов", "козлина", "козлище",
    "козявка", "козявки", "козявку",
    "баран", "барана", "барану", "бараном", "баране", "бараны", "баранов", "баранина",
    "осел", "осла", "ослу", "ослом", "осле", "ослы", "ослов", "ослица",
    "свинья", "свиньи", "свинье", "свинью", "свиньей", "свиней", "свиньям", "свиньями", "свин",
    "собака", "собаки", "собаке", "собаку", "собакой", "псина", "псины", "псине",
    "овца", "овцы", "овце", "овцу", "овцой", "овечка",
    "корова", "коровы", "корове", "корову", "коровой",
    "обезьяна", "обезьяны", "обезьяне", "обезьяну", "обезьяной",

    # НЕГАТИВНЫЕ ЛИЧНОСТИ
    "сволочь", "сволочи", "сволочью", "сволочей", "сволочам", "сволочами",
    "гад", "гада", "гаду", "гадом", "гаде", "гады", "гадов", "гадина", "гадине",
    "тварь", "твари", "тварью", "тварей", "тварям", "тварями",
    "урод", "урода", "уроду", "уродом", "уроде", "уроды", "уродов", "уродина", "уродский",
    "мудак", "мудака", "мудаку", "мудаком", "мудаке", "мудаки", "мудаков", "мудацкий",
    "придурок", "придурка", "придурку", "придурком", "придурке", "придурки", "придурков",
    "лох", "лоха", "лоху", "лохом", "лохе", "лохи", "лохов", "лошок", "лошпеды",
    "чмо", "чма", "чму", "чмом", "чмы", "чмов", "чмошник", "чмошный",
    "падла", "падлы", "падле", "падлу", "падлой", "падло", "падлы", "падлам",
    "гнида", "гниды", "гниде", "гниду", "гнидой", "гнид",
    "мразь", "мрази", "мразью", "мразей", "мразотный",
    "тварь", "твари", "тварью", "тварей",
    "скотина", "скотины", "скотине", "скотину", "скотиной", "скот",
    "стерва", "стервы", "стерве", "стерву", "стервой", "стервятник",

    # РУССКИЙ МАТ (все формы)
    # ХУЙ
    "хуй", "хуя", "хую", "хуем", "хуе", "хуи", "хуёв", "хуям", "хуями", "хуях",
    "хуйня", "хуйни", "хуйне", "хуйню", "хуйней", "хуйнуть", "хуйнул",
    "хуёвый", "хуёвого", "хуёвому", "хуёвым", "хуёвая", "хуёвой", "хуёвые",
    "нахуй", "нахуя", "похуй", "дохуя", "охуеть", "охуел", "охуела", "охуели", "охуенно",
    "ахуеть", "ахуел", "ахуела", "ахуели", "ахуенный",
    "распиздяй", "распиздяя",
    # ПИЗДА
    "пизда", "пизды", "пизде", "пизду", "пиздой", "пизд", "пиздам", "пиздами",
    "пиздец", "пиздеца", "пиздецу", "пиздецом", "пиздатый", "пиздатую",
    "пиздить", "пизжу", "пиздит", "пиздил", "пиздила", "пиздюк", "пиздюка", "пиздюки",
    "пиздюлька", "пиздобратия", "пиздобратии",
    "распиздяй", "распиздяя", "распиздяйство",
    "запиздярить", "запиздярил",
    "пропиздеть", "пропиздел",
    # БЛЯДЬ
    "блядь", "бляди", "блядью", "блядей", "блядям", "блядями",
    "бля", "блять", "блэ", "бляха",
    "блядский", "блядского", "блядские",
    "блядство", "блядства", "блядству",
    "блядовать", "блядует", "блядовал",
    "заблядовать", "проблядовать",
    # СУКА
    "сука", "суки", "суке", "суку", "сукой", "сук", "сукам", "суками",
    "сучка", "сучки", "сучке", "сучку", "сучкой", "сучек",
    "сучонок", "сучонка", "сучонку", "сучёныш",
    "сучья", "сучью", "сучьей",
    "сукин", "сукина", "сукину", "сукиным",
    # ЕБАТЬ
    "ебать", "ебу", "ебет", "ебут", "ебал", "ебала", "ебали", "еби", "ебите",
    "ебануть", "ебанул", "ебанула", "ебанёт",
    "ебанутый", "ебанутого", "ебанутая", "ебанутую", "ебанутые",
    "ёбаный", "ёбаного", "ёбаную", "ёбаные", "ёбаных",
    "заебать", "заебал", "заебала", "заебали", "заебёт", "заеби",
    "наебать", "наебал", "наебала", "наебут", "наебалово",
    "поебать", "поебал", "поебала",
    "разъебай", "разъебая", "разъебаи",
    "ебля", "ебли", "еблей",
    "ебарь", "ебарей",
    "ебло", "ебла", "ебу", "еблом", "еблет", "ебальник",
    # ПИДОР
    "пидор", "пидора", "пидору", "пидором", "пидоре", "пидоры", "пидоров",
    "пидорас", "пидораса", "пидорасу", "пидорасом", "пидорасе", "пидорасы",
    "пидрила", "пидрилы", "пидриле", "пидрилу", "пидрилой",
    "пидорня", "пидорни", "пидорне",
    "пидорский", "пидорского", "пидорские",
    "пидорашка", "пидорашки", "пидорашку",
    "pidor", "pidora", "pidoru", "pidorom",
    # ЗАЛУПА
    "залупа", "залупы", "залупе", "залупу", "залупой", "залуп",
    "залупень", "залупня", "залупню", "залупнем",
    "залупный", "залупного", "залупные",
    # ГАНДОН
    "гандон", "гандона", "гандону", "гандоном", "гандоне", "гандопень",
    "гондон", "гондона", "гондону", "гондоном",
    # ШЛЮХА
    "шлюха", "шлюхи", "шлюхе", "шлюху", "шлюхой", "шлюх", "шлюхам", "шлюхами",
    "шлюшка", "шлюшки", "шлюшку", "шлюшек",
    "проститутка", "проститутки", "проститутке", "проститутку", "проституткой", "проституток",
    "проститутский", "проституточный",
    "курва", "курвы", "курве", "курву", "курвой",
    "сучара", "сучары", "сучаре", "сучару", "сучарой",
    "потаскуха", "потаскухи", "потаскухе", "потаскуху", "потаскухой",
    "блядун", "блядуна", "блядуну", "блядуном",
    "блядища", "блядищи", "блядище", "блядищу",

    # ДОЛБОЕБ / ЕБЛАН
    "долбоеб", "долбоеба", "долбоебу", "долбоебом", "долбоебе", "долбоебы", "долбоебов",
    "долбоящер", "долбоящера", "долбоящеры",
    "еблан", "еблана", "еблану", "ебланом", "еблане", "ебланы", "ебланов",
    "ебланчик", "ебланский",
    "мудак", "мудака", "мудаку", "мудаком", "мудаке", "мудаки", "мудаков", "мудацкий",
    "мудила", "мудилы", "мудиле", "мудилу", "мудилой",
    "мудень", "мудня", "муднем",
    "мудозвон", "мудозвона", "мудозвоны",

    # РАЗНЫЕ ОСКОРБЛЕНИЯ
    "чурка", "чурки", "чурке", "чурку", "чуркой",
    "хач", "хача", "хачу", "хачем", "хачи", "хачей",
    "жид", "жида", "жиду", "жидом", "жиды", "жидов",
    "хохол", "хохла", "хохлу", "хохлом", "хохлы", "хохлов",
    "кацап", "кацапа", "кацапу", "кацапом",
    "пшек", "пшека", "пшеку", "пшеки",

    # УСИЛИТЕЛИ
    "ёбаный в рот", "ёбаного в рот", "ёбанные",
    "распидорасия", "пидоры",
    "охуительный", "охуительного",
    "наебениться", "наебенился"
]

# Словарь аморального контента (нельзя автоматически публиковать)
IMMORAL_CONTENT = [
    # СЕКС / ПОРНО / ЭРОТИКА
    "секс", "секса", "сексу", "сексом", "сексе", "сексуальный", "сексуального", "сексуальные",
    "порно", "порна", "порнуха", "порнухи", "порнушный", "порнографический",
    "эротика", "эротики", "эротикой", "эротичный", "эротического",
    "интим", "интима", "интимом", "интимный", "интимного", "интимные", "интимность",

    # ГОЛЫЙ / ОБНАЖЕННЫЙ
    "голая", "голой", "голую", "голые", "голых", "голыми", "голый", "голого", "голому", "голым",
    "обнаженная", "обнаженной", "обнаженную", "обнаженные", "обнаженных", "обнаженными",
    "обнаженный", "обнаженного", "обнаженному", "обнаженным", "обнажен",
    "нагая", "нагой", "нагую", "нагие", "нагих", "нагой", "нагое",

    # ЧАСТИ ТЕЛА (детские/сленг)
    "писька", "письки", "письке", "письку", "писькой", "писюн", "писюна", "писюнчик",
    "пися", "писи", "писе", "писю", "писей", "писям",
    "попа", "попы", "попе", "попу", "попой", "попка", "попки", "попку", "попке",
    "жопа", "жопы", "жопе", "жопу", "жопой", "жопка", "жопки", "жопный",
    "сиськи", "сисек", "сиськам", "сиськами", "сиськах", "сися", "сисы", "сисечка",
    "титьки", "тите", "титьками", "титькам", "сиськ",
    "член", "члена", "члену", "членом", "члене", "члены", "членов", "членам", "членами",
    "хуй", "хуя", "хую", "хуем", "хуе", "хуи", "хуёв", "хуйня", "хуйни",
    "пенис", "пениса", "пенису", "пенисом", "пенисе", "пенисы", "пенисов",
    "вагина", "вагины", "вагине", "вагину", "вагиной", "вагинальный",
    "влагалище", "влагалища", "влагалищу", "влагалищем", "влагалищ",

    # ДЕЙСТВИЯ (лизать, сосать)
    "лизнуть", "лизнул", "лизнула", "лизнули", "лизнешь", "лижет", "лижешь",
    "облизать", "оближу", "оближет", "облизал", "облизала", "оближи", "оближите",
    "лизать", "лижу", "лижет", "лижут", "лизал", "лизала", "лижи",
    "вылизать", "вылижу", "вылижет", "вылизал", "вылизала",
    "сосать", "сосу", "сосет", "сосут", "сосал", "сосала", "соси", "сосите",
    "отсосать", "отсосу", "отсосет", "отсосут", "отсосал", "отсосала", "отсоси",
    "засосать", "засосу", "засосет", "засосал", "засосала",

    # СЕМЯ / ЭЯКУЛЯЦИЯ
    "кончить", "кончу", "кончит", "кончат", "кончил", "кончила", "кончай",
    "сперма", "спермы", "сперме", "сперму", "спермой",
    "эякуляция", "эякуляции", "эякуляцией", "эякулировать", "эякулировал",
    "семяизвержение", "семяизвержения",
    "мастурбация", "мастурбации", "мастурбацией", "мастурбировать", "мастурбирует", "мастурбировал",
    "дрочить", "дрочу", "дрочит", "дрочат", "дрочил", "дрочила", "дрочи",
    "дрочка", "дрочки", "дрочке", "дрочку", "дрочкой",

    # НОГИ / СТУПНИ (фут-фетиш)
    "ножки", "ножек", "ножкам", "ножками", "ножках", "ножка", "ножку", "ножке",
    "ноги", "ног", "ногам", "ногами", "ногах", "нога", "ногу", "ногой",
    "ступни", "ступней", "ступням", "ступнями", "ступнях", "ступня", "ступню", "ступней",
    "пальцы ног", "пальцев ног", "пальцам ног", "пальцами ног", "пальчик ноги",
    "облизать ноги", "оближет ноги", "лижет ноги", "лизать ноги", "лижу ноги",

    # ПОЛОВОЙ АКТ (трахать, ебать)
    "трахнуть", "трахну", "трахнешь", "трахнет", "трахнут", "трахнул", "трахнула", "трахнули",
    "трахать", "трахаю", "трахает", "трахают", "трахал", "трахала", "трахали",
    "выебать", "выебу", "выебет", "выебут", "выебал", "выебала",
    "ебаться", "ебусь", "ебется", "ебутся", "ебался", "ебалась", "ебитесь",
    "совокупление", "совокупления", "совокуплению", "совокуплением",

    # ВИДЫ СЕКСА
    "оральный", "орального", "оральному", "оральным", "оральные",
    "анальный", "анального", "анальному", "анальным", "анальные",
    "минет", "минета", "минету", "минетом", "минете", "минетик",
    "кунилингус", "кунилингуса", "кунилингусу", "кунилингусом",

    # ПОРНОАКТЕРЫ
    "порноактриса", "порноактрисы", "порноактрисе", "порноактрису", "порноактрисой",
    "порноактер", "порноактера", "порноактеру", "порноактером", "порноактеры",

    # ОРИЕНТАЦИИ И ПРАКТИКИ
    "гей", "гея", "гею", "геем", "геи", "геев",
    "лесбиянка", "лесбиянки", "лесбиянке", "лесбиянку", "лесбиянкой", "лесбиянок",
    "бдсм", "бдсменит", "бдсмщик",
    "жесткий секс", "жесткого секса", "жесткому сексу", "жестким сексом",
    "групповуха", "групповухи", "групповухе", "групповуху", "групповухой",
    "оргия", "оргии", "оргией", "оргию", "оргий",

    # ПРЕДМЕТЫ
    "презерватив", "презерватива", "презервативу", "презервативом", "презервативе", "презервативы",
    "вибратор", "вибратора", "вибратору", "вибратором", "вибраторе", "вибраторы",
    "дилдо", "дилда", "дилду", "дилдом",
    "секс-игрушки", "секс-игрушек", "секс-игрушкам", "секс-игрушками",

    # ТАБУ
    "инцест", "инцеста", "инцесту", "инцестом",
    "насилие", "насилия", "насилию", "насилием",
    "изнасилование", "изнасилования", "изнасилованию", "изнасилованием",
    "педофилия", "педофилии", "педофилией", "педофил",
    "зоофилия", "зоофилии", "зоофилией", "зоофил",
    "некрофилия", "некрофилии", "некрофилией", "некрофил"
]

IMMORAL_PATTERNS = [re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE) for word in IMMORAL_CONTENT]

# Паттерны для ссылок
URL_PATTERNS = [
    r'https?://\S+',           # http:// или https://
    r't\.me/\S+',              # t.me ссылки
    r'@\w+',                   # упоминания
    r'(?:www\.)\S+',           # www.
    r'\S+\.(ru|com|org|net|рф|su|xyz|top|club|site)\b',  # домены
    r'(?:telegram|tg)\.me/\S+', # telegram.me
    r'bit\.ly/\S+',            # сокращатели ссылок
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
    "Вы можете отправить анонимное сообщение старым способом:\n"
    "✉ <a href='https://t.me/anonaskbot?start=koafguk'>Анонимные сообщения</a>\n\n"
    "Приносим извинения за неудобства!"
)

# ================= СОСТОЯНИЯ FSM =================

class AdminStates(StatesGroup):
    waiting_for_user_search = State()
    waiting_for_exception_add = State()
    waiting_for_exception_remove = State()
    waiting_for_blacklist_add = State()
    waiting_for_blacklist_remove = State()
    waiting_for_mute_duration = State()
    waiting_for_mute_user = State()
    waiting_for_reply = State()

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

def is_night_time() -> bool:
    now_utc = datetime.utcnow()
    now_msk = now_utc + timedelta(hours=3)
    hour = now_msk.hour
    if NIGHT_MODE_START <= NIGHT_MODE_END:
        return NIGHT_MODE_START <= hour < NIGHT_MODE_END
    return hour >= NIGHT_MODE_START or hour < NIGHT_MODE_END

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

# ================= ИНИЦИАЛИЗАЦИЯ БД =================

async def load_blacklist_to_cache():
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT word FROM blacklist")
            words = await cursor.fetchall()
            blacklist_cache.clear()
            for word in words:
                blacklist_cache[word[0]] = True
        logger.info(f"Загружено {len(blacklist_cache)} слов в черный список")
    except Exception as e:
        logger.error(f"Ошибка загрузки черного списка: {e}")

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
            maintenance_exception INTEGER DEFAULT 0
        )
        """)
        
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
            skipped INTEGER DEFAULT 0
        )
        """)
        
        try:
            await db.execute("ALTER TABLE messages ADD COLUMN notified_long INTEGER DEFAULT 0")
        except:
            pass
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_reviewer ON messages(reviewer)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
        
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
        await db.execute("INSERT OR IGNORE INTO settings VALUES('maintenance','0')")
        await db.commit()
    
    await load_blacklist_to_cache()

# ================= НОЧНОЙ РЕЖИМ =================

async def notify_admins_about_auto_post(msg_id: int, user_id: int, media_type: str, counter: int):
    if shutdown_flag:
        return
    text = (
        f"🤖 <b>Автоматическая публикация</b>\n\n"
        f"Сообщение #{msg_id} от пользователя <code>{user_id}</code>\n"
        f"Тип: {media_type}\n"
        f"Номер поста: #{counter}\n"
        f"Опубликовано в ночном режиме"
    )
    for admin in ADMINS:
        try:
            await bot.send_message(admin, text)
            await asyncio.sleep(0.1)
        except:
            pass

async def post_next_message():
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("""
                SELECT id, user_id, text, media_type, media_file_id, has_links, insult_count
                FROM messages 
                WHERE status='pending' AND reviewer IS NULL AND skipped=0
                ORDER BY created_at ASC 
                LIMIT 1
            """)
            message = await cursor.fetchone()
            
            if not message:
                return
            
            msg_id, user_id, text, media_type, media_file_id, has_links, insult_count = message
            has_immoral = has_immoral_content(text) if text else False
            
            can_auto_post = (
                media_type is None and
                not has_links and
                not has_immoral and
                insult_count < INSULT_THRESHOLD
            )
            
            if not can_auto_post:
                return
            
            await db.execute("""
                UPDATE messages 
                SET status='approved', reviewed_at=?, auto_posted=1 
                WHERE id=?
            """, (datetime.utcnow().isoformat(), msg_id))
            
            cursor = await db.execute("SELECT value FROM settings WHERE key='post_counter'")
            counter = int((await cursor.fetchone())[0]) + 1
            await db.execute("UPDATE settings SET value=? WHERE key='post_counter'", (str(counter),))
            await db.commit()
        
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key='post_style'")
            style = (await cursor.fetchone())[0]
        
        if style == "1":
            header = f"💬 <b>Новое анонимное сообщение</b>\n\n"
            footer = f"\n\n━━━━━━━━━━━━━━\n✉ <a href='https://t.me/{BOT_USERNAME}'>Отправить сообщение</a>"
        elif style == "2":
            header = f"┌─────────────────┐\n│  НОЧНОЕ ПОДСЛУШАНО  │\n└─────────────────┘\n\n"
            footer = f"\n\n➖➖➖➖➖➖➖➖➖\n✉ <a href='https://t.me/{BOT_USERNAME}'>Написать анонимно</a>"
        else:
            header = f"🌙 <b>Ночное сообщение</b>\n\n"
            footer = f"\n\n—\n<a href='https://t.me/{BOT_USERNAME}'>✉ Ответить</a>"
        
        await bot.send_message(
            CHANNEL_ID,
            f"{header}<blockquote>{text}</blockquote>{footer}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        
        await notify_admins_about_auto_post(msg_id, user_id, "текст", counter)
        logger.info(f"AUTO POST: #{counter} от пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка авто-публикации: {e}")
        await log_action(f"Ошибка авто-публикации: {e}")

async def auto_post_messages():
    global night_mode_enabled, shutdown_flag
    while not shutdown_flag:
        try:
            if night_mode_enabled and is_night_time() and not maintenance_mode:
                await post_next_message()
            for _ in range(NIGHT_POST_INTERVAL * 60):
                if shutdown_flag:
                    break
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка в ночном режиме: {e}")
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
                    
                    text = (
                        f"⚠️ <b>Долгое сообщение #{msg_id}</b>\n\n"
                        f"Висит в очереди больше {LONG_MESSAGE_THRESHOLD} минут!\n"
                        f"От пользователя: <code>{user_id}</code>\n"
                        f"Тип: {media_type or 'текст'}\n"
                        f"Время отправки: {created_at[:16]}\n"
                        f"Текст: {short_text}"
                    )
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔍 Перейти к рассмотрению", callback_data=f"review_{msg_id}")]
                    ])
                    
                    for admin in ADMINS:
                        try:
                            await bot.send_message(admin, text, reply_markup=keyboard)
                        except:
                            pass
                    
                    await db.execute(
                        "UPDATE messages SET notified_long=1 WHERE id=?",
                        (msg_id,)
                    )
                    
                    logger.info(f"Long message notification sent for #{msg_id}")
                
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
            logger.info(f"❤️ Heartbeat - Бот работает | Пользователей в кэше: {cache_size}")
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
    global night_mode_enabled, maintenance_mode  # ВАЖНО: В САМОМ НАЧАЛЕ!
    
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

    # Проверка техработ (теперь maintenance_mode определена)
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
            [KeyboardButton(text="📨 Ожидающие проверки")]
        ]
        
        if message.from_user.id == SUPER_ADMIN:
            night_status = "✅ Включен" if night_mode_enabled else "❌ Выключен"
            maint_status = "🔧 Включены" if maintenance_mode else "🔧 Выключены"
            keyboard_buttons.append([KeyboardButton(text=f"🌙 Ночной режим ({night_status})")])
            keyboard_buttons.append([KeyboardButton(text=f"🛠 Техработы ({maint_status})")])
            keyboard_buttons.append([KeyboardButton(text="👥 Управление исключениями")])
            keyboard_buttons.append([KeyboardButton(text="📝 Черный список слов")])
        
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

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ℹ Информация")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Отправьте сообщение, фото или видео..."
    )

    await message.answer(
        "👋 <b>Подслушано</b>\n\n"
        "Отправьте сообщение, фото или видео - они будут опубликованы анонимно после проверки.\n"
        "В ночное время (с 0 до 8 утра) текстовые сообщения без ссылок публикуются автоматически.",
        reply_markup=keyboard
    )

# ================= ПОЛЬЗОВАТЕЛЬСКИЕ КНОПКИ =================

@dp.message(F.text == "ℹ Информация")
async def info_text(message: Message):
    log_user_action(message.from_user.id, "INFO")
    await message.answer(
        "ℹ <b>Информация</b>\n\n"
        "Все сообщения проходят модерацию и публикуются анонимно.\n"
        "Можно отправлять:\n"
        "• Текстовые сообщения\n"
        "• Фотографии\n"
        "• Видео\n\n"
        "В ночное время (с 0 до 8 утра) текстовые сообщения без ссылок публикуются автоматически.\n"
        "Фото и видео всегда проверяются модераторами."
    )

@dp.message(F.text == "❓ Помощь")
async def help_text(message: Message):
    log_user_action(message.from_user.id, "HELP")
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "Просто отправьте текст, фото или видео. Они будут проверены модератором.\n"
        "Нельзя отправлять сообщения чаще, чем раз в 30 секунд.\n"
        "Максимальный размер видео: 50 МБ\n\n"
        "Запрещено:\n"
        "• Ссылки на сторонние ресурсы\n"
        "• Очень сильная травля\n"
        "• Реклама\n\n"
        "Фото и видео всегда проходят ручную проверку."
    )

# ================= АДМИНСКИЕ КНОПКИ =================

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

@dp.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    cache_key = "stats"
    if cache_key in admin_cache:
        await message.answer(admin_cache[cache_key])
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM users) as total_users,
                    (SELECT COUNT(*) FROM users WHERE banned=1) as banned_users,
                    (SELECT COUNT(*) FROM users WHERE mute_until > datetime('now')) as muted_users,
                    (SELECT COUNT(*) FROM users WHERE maintenance_exception=1) as exception_users,
                    (SELECT COUNT(*) FROM messages) as total_messages,
                    (SELECT COUNT(*) FROM messages WHERE status='pending') as pending_messages,
                    (SELECT COUNT(*) FROM messages WHERE media_type IS NOT NULL) as media_messages,
                    (SELECT COUNT(*) FROM messages WHERE auto_posted=1) as auto_posted,
                    (SELECT COUNT(*) FROM messages WHERE has_links=1) as with_links,
                    (SELECT COUNT(*) FROM messages WHERE skipped=1) as skipped_messages,
                    (SELECT COUNT(*) FROM messages WHERE insult_count >= ?) as heavy_insults,
                    (SELECT value FROM settings WHERE key='post_counter') as post_counter,
                    (SELECT COUNT(*) FROM blacklist) as blacklist_count,
                    (SELECT COUNT(*) FROM admin_actions WHERE date(created_at) = date('now')) as today_actions
            """, (INSULT_THRESHOLD,))
            
            result = await cursor.fetchone()
            total_users, banned_users, muted_users, exception_users, total_messages, pending_messages, media_messages, auto_posted, with_links, skipped_messages, heavy_insults, post_counter, blacklist_count, today_actions = result
    except Exception as e:
        logger.error(f"DB error in admin_stats: {e}")
        await message.answer("❌ Ошибка получения статистики")
        return
    
    stats_text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
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
        f"📋 Действий сегодня: {today_actions}\n"
        f"🌙 Ночной режим: {'✅' if night_mode_enabled else '❌'}\n"
        f"🛠 Техработы: {'✅' if maintenance_mode else '❌'}"
    )
    
    admin_cache[cache_key] = stats_text
    await message.answer(stats_text)
    logger.info(f"STATS requested by admin {message.from_user.id}")

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

@dp.message(F.text == "📨 Ожидающие проверки")
async def admin_pending_messages(message: Message):
    if message.from_user.id not in ADMINS:
        return
    
    cache_key = f"pending_list_{message.from_user.id}"
    if cache_key in pending_cache:
        cached = pending_cache[cache_key]
        await message.answer(cached["text"], reply_markup=cached["keyboard"])
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
                       created_at, has_links, insult_count,
                       julianday('now') - julianday(created_at) > 0.0417 as is_old
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
    
    text = f"📨 <b>Ожидают проверки: {total_pending}</b>\n\n"
    if total_pending > 10:
        text += f"<i>Показаны последние 10 из {total_pending}</i>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for msg_id, user_id, media_type, short_text, created_at, has_links, insult_count, is_old in pending_messages:
        try:
            msg_date = datetime.fromisoformat(created_at)
            date_str = msg_date.strftime('%d.%m %H:%M')
        except:
            date_str = created_at[:16] if created_at else "неизвестно"
        
        if media_type == "photo":
            emoji = "📸"
            content_type = "Фото"
            media_warning = " 🚫(авто-пост запрещен)"
        elif media_type == "video":
            emoji = "🎥"
            content_type = "Видео"
            media_warning = " 🚫(авто-пост запрещен)"
        else:
            emoji = "📝"
            content_type = "Текст"
            media_warning = ""
        
        warnings = []
        if has_links:
            warnings.append("🔗")
        if insult_count >= INSULT_THRESHOLD:
            warnings.append(f"🤬{insult_count}")
        if is_old:
            warnings.append("⚠️ СТАРОЕ")
        
        warning_str = f" {' '.join(warnings)}" if warnings else ""
        display_text = short_text.replace('\n', ' ').strip() if short_text else "без текста"
        if len(display_text) > 30:
            display_text = display_text[:30] + "..."
        
        text += f"{emoji} <b>#{msg_id}</b>{warning_str}{media_warning} | {date_str}\n"
        text += f"👤 ID: <code>{user_id}</code>\n"
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
    
    pending_cache[cache_key] = {"text": text, "keyboard": keyboard}
    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text == "❌ Закрыть меню")
async def close_menu(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    
    await state.clear()
    await message.answer(
        "Меню закрыто. Чтобы открыть снова, напишите /start",
        reply_markup=ReplyKeyboardRemove()
    )

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
            text += f"{i}. <code>{word}</code>\n"
    
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
        await message.answer(f"✅ Слово <code>{word}</code> добавлено в черный список")
        await log_admin_action(message.from_user.id, "blacklist_add", details=word)
        
    except aiosqlite.IntegrityError:
        await message.answer(f"❌ Слово <code>{word}</code> уже есть в черном списке")
    except Exception as e:
        logger.error(f"Error adding to blacklist: {e}")
        await message.answer("❌ Ошибка при добавлении слова")
    
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
        [InlineKeyboardButton(text="1 час", callback_data="mute_1h"),
         InlineKeyboardButton(text="3 часа", callback_data="mute_3h"),
         InlineKeyboardButton(text="6 часов", callback_data="mute_6h")],
        [InlineKeyboardButton(text="12 часов", callback_data="mute_12h"),
         InlineKeyboardButton(text="1 день", callback_data="mute_1d"),
         InlineKeyboardButton(text="3 дня", callback_data="mute_3d")],
        [InlineKeyboardButton(text="7 дней", callback_data="mute_7d"),
         InlineKeyboardButton(text="30 дней", callback_data="mute_30d"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="mute_cancel")]
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
            if "stats" in admin_cache:
                del admin_cache["stats"]
            
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
            "temporary_mute": "⏳", "reply": "💬"
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

# ================= ТЕХРАБОТЫ =================

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

# ================= НОЧНОЙ РЕЖИМ (TOGGLE) =================

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
    await message.answer(f"🌙 Ночной режим {status}")

# ================= ПОИСК ПОЛЬЗОВАТЕЛЯ =================

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
                SELECT user_id, username, first_name, banned, mute_until, maintenance_exception
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
        user_id, username, first_name, banned, mute_until, maintenance_exception = user
        status = []
        if banned:
            status.append("⛔ Забанен")
        if maintenance_exception:
            status.append("⭐ Исключение")
        
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

# ================= ОБРАБОТЧИК СООБЩЕНИЙ ПОЛЬЗОВАТЕЛЯ =================

@dp.message(F.photo | F.video | F.text)
async def handle_user_media(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return
    
    if message.from_user.id in ADMINS:
        return
    
    if message.text and message.text.startswith('/'):
        return
    
    if message.text and message.text in ["🎨 Сменить стиль", "📊 Статистика", "👥 Управление пользователями", 
                        "📨 Ожидающие проверки", "❌ Закрыть меню", "ℹ Информация", "❓ Помощь",
                        "⏳ Временный мут", "📋 История действий", "📝 Черный список слов"]:
        return
    
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

    now = datetime.utcnow()
    user_id = message.from_user.id

    log_user_action(user_id, "SEND_MESSAGE", f"Type: {'photo' if message.photo else 'video' if message.video else 'text'}")

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

            media_type = None
            media_file_id = None
            text = message.caption if message.caption else message.text
            
            formatted_text = None
            if text:
                formatted_text = f"<blockquote>{text}</blockquote>"
            
            if message.photo:
                media_type = "photo"
                media_file_id = message.photo[-1].file_id
            elif message.video:
                media_type = "video"
                media_file_id = message.video.file_id

            has_links_flag = has_links(text) if text else False
            insult_count = count_insults_with_blacklist(text) if text else 0
            has_immoral_flag = has_immoral_content(text) if text else False

            await db.execute("""
                INSERT INTO users (user_id, username, first_name, last_message) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_message=excluded.last_message
            """, (user_id, message.from_user.username, message.from_user.first_name, now.isoformat()))

            cursor = await db.execute("""
                INSERT INTO messages 
                (user_id, text, media_type, media_file_id, created_at, has_links, insult_count) 
                VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id
            """, (user_id, formatted_text or text, media_type, media_file_id, now.isoformat(), has_links_flag, insult_count))
            
            row = await cursor.fetchone()
            msg_id = row[0]
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in handle_user_media: {e}")
        await message.answer("❌ Ошибка при сохранении сообщения")
        return

    logger.info(f"MESSAGE SAVED: #{msg_id} from user {user_id}")

    user_cache[user_id] = {'banned': False, 'mute_until': None, 'last_message': now}
    
    if "stats" in admin_cache:
        del admin_cache["stats"]
    pending_cache.clear()

    if media_type == "photo":
        await message.answer("✅ Фото отправлено на модерацию.")
    elif media_type == "video":
        await message.answer("✅ Видео отправлено на модерацию.")
    else:
        await message.answer("✅ Сообщение отправлено на модерацию.")

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
        warnings.append("🚫 МЕДИА (только ручная проверка)")
    
    warning_text = f"\n\n⚠️ {' | '.join(warnings)}" if warnings else ""
    display_text = formatted_text if formatted_text else (text or "без текста")

    tasks = []
    for admin in ADMINS:
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
                    f"📨 <b>Новое сообщение</b>{warning_text}\n\n{display_text}\n\n🆔 <code>{user_id}</code>\n👤 @{message.from_user.username or 'нет'}",
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
                "SELECT reviewer, status, media_type, media_file_id, text, has_links, insult_count, skipped FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()

            if not result:
                await callback.answer("Сообщение не найдено", show_alert=True)
                return

            reviewer, status, media_type, media_file_id, text, has_links, insult_count, skipped = result

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

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{msg_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{msg_id}")],
        [InlineKeyboardButton(text="⏳ Мут 7д", callback_data=f"mute_{msg_id}"),
         InlineKeyboardButton(text="🔨 Бан", callback_data=f"ban_{msg_id}")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"skip_{msg_id}"),
         InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{msg_id}")],
        [InlineKeyboardButton(text="↩️ Отменить", callback_data=f"cancel_review_{msg_id}")]
    ])

    warnings = []
    if has_links:
        warnings.append("🔗 ССЫЛКИ")
    if insult_count >= INSULT_THRESHOLD:
        warnings.append(f"🤬 ОСКОРБЛЕНИЯ ({insult_count})")
    if media_type:
        warnings.append("🚫 МЕДИА")
    
    warning_text = f"\n\n⚠️ {' | '.join(warnings)}" if warnings else ""

    try:
        if media_type == "photo":
            await callback.message.edit_caption(
                caption=callback.message.caption + warning_text + "\n\n🔄 <b>Рассматривается...</b>",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        elif media_type == "video":
            await callback.message.edit_caption(
                caption=callback.message.caption + warning_text + "\n\n🔄 <b>Рассматривается...</b>",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            reply_hint = "\n\n💬 <i>Чтобы ответить пользователю, нажмите кнопку 'Ответить'</i>"
            await callback.message.edit_text(
                text=callback.message.text + warning_text + reply_hint + "\n\n🔄 <b>Рассматривается...</b>",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Error editing message in review: {e}")
        await callback.answer("❌ Ошибка при редактировании", show_alert=True)
        return

# ================= ОТВЕТ ПОЛЬЗОВАТЕЛЮ =================

@dp.callback_query(F.data.startswith("reply_"))
async def reply_to_user(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return
    
    msg_id = int(callback.data.split("_")[1])
    await state.update_data(reply_msg_id=msg_id)
    await state.set_state(AdminStates.waiting_for_reply)
    
    await callback.message.answer(
        "💬 Введите текст ответа пользователю (или /cancel для отмены):"
    )
    await callback.answer()

@dp.message(AdminStates.waiting_for_reply)
async def process_reply(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await state.clear()
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Ответ отменен")
        return
    
    data = await state.get_data()
    msg_id = data.get("reply_msg_id")
    
    if not msg_id:
        await state.clear()
        await message.answer("❌ Ошибка: сообщение не найдено")
        return
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT user_id FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()
            if not result:
                await message.answer("❌ Сообщение не найдено в базе")
                await state.clear()
                return
            user_id = result[0]
    except Exception as e:
        logger.error(f"Error getting user_id: {e}")
        await message.answer("❌ Ошибка базы данных")
        await state.clear()
        return
    
    try:
        await bot.send_message(
            user_id,
            f"📝 <b>Ответ от администратора</b>\n\n{message.text}"
        )
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}")
        await log_admin_action(message.from_user.id, "reply", user_id, message.text[:100])
    except Exception as e:
        logger.error(f"Error sending reply: {e}")
        await message.answer(f"❌ Не удалось отправить ответ. Пользователь {user_id} заблокировал бота?")
    
    await state.clear()

# ================= ПРОПУСК СООБЩЕНИЯ =================

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
            cursor = await db.execute(
                "SELECT status FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()
            
            if not result:
                await callback.answer("❌ Сообщение не найдено", show_alert=True)
                return
                
            status = result[0]
            if status != "pending":
                await callback.answer(f"❌ Сообщение уже {status}", show_alert=True)
                return
            
            await db.execute(
                "UPDATE messages SET skipped=1, reviewer=NULL WHERE id=?",
                (msg_id,)
            )
            await db.commit()
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

# ================= ОТМЕНА РАССМОТРЕНИЯ =================

@dp.callback_query(F.data.startswith("cancel_review_"))
async def cancel_review(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[2])

    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT reviewer, user_id, media_type FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()
            
            if not result:
                await callback.answer("Сообщение не найдено", show_alert=True)
                return
                
            reviewer, user_id, media_type = result

            if reviewer != callback.from_user.id:
                await callback.answer("Вы не рассматриваете это сообщение", show_alert=True)
                return

            await db.execute(
                "UPDATE messages SET reviewer=NULL WHERE id=?",
                (msg_id,)
            )
            await db.commit()
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

# ================= ОДОБРЕНИЕ =================

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    msg_id = int(callback.data.split("_")[1])

    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT text, user_id, reviewer, media_type, media_file_id FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()

            if not result:
                await callback.answer("Сообщение не найдено", show_alert=True)
                return

            text, user_id, reviewer, media_type, media_file_id = result

            if reviewer != callback.from_user.id:
                await callback.answer("Сначала нужно начать рассмотрение", show_alert=True)
                return

            await db.execute(
                "UPDATE messages SET status='approved', reviewed_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), msg_id)
            )

            cursor = await db.execute("SELECT value FROM settings WHERE key='post_counter'")
            counter = int((await cursor.fetchone())[0]) + 1
            await db.execute("UPDATE settings SET value=? WHERE key='post_counter'", (str(counter),))
            await db.commit()
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
            await bot.send_photo(
                CHANNEL_ID,
                photo=media_file_id,
                caption=f"{header}{text or ''}{footer}",
                parse_mode=ParseMode.HTML
            )
        elif media_type == "video":
            await bot.send_video(
                CHANNEL_ID,
                video=media_file_id,
                caption=f"{header}{text or ''}{footer}",
                parse_mode=ParseMode.HTML
            )
        else:
            await bot.send_message(
                CHANNEL_ID,
                f"{header}{text or ''}{footer}",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"PUBLISH ERROR: {e}")
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
        if media_type == "photo":
            await bot.send_message(user_id, "✅ Ваше фото опубликовано в канале!")
        elif media_type == "video":
            await bot.send_message(user_id, "✅ Ваше видео опубликовано в канале!")
        else:
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
            cursor = await db.execute(
                "SELECT user_id, reviewer, media_type FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()

            if not result:
                await callback.answer("Сообщение не найдено", show_alert=True)
                return

            user_id, reviewer, media_type = result

            if reviewer != callback.from_user.id:
                await callback.answer("Сначала нужно начать рассмотрение", show_alert=True)
                return

            await db.execute(
                "UPDATE messages SET status='rejected', reviewed_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), msg_id)
            )
            await db.commit()
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
        if media_type == "photo":
            await bot.send_message(user_id, "❌ Ваше фото отклонено модератором.")
        elif media_type == "video":
            await bot.send_message(user_id, "❌ Ваше видео отклонено модератором.")
        else:
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
            cursor = await db.execute(
                "SELECT user_id, reviewer, media_type FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()

            if not result:
                await callback.answer("Сообщение не найдено", show_alert=True)
                return

            user_id, reviewer, media_type = result

            if reviewer != callback.from_user.id:
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
        await bot.send_message(user_id, f"⏳ Вы получили мут на 7 дней за нарушение правил.\nДо: {mute_until.strftime('%d.%m.%Y %H:%M')} МСК")
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
            cursor = await db.execute(
                "SELECT user_id, reviewer, media_type FROM messages WHERE id=?",
                (msg_id,)
            )
            result = await cursor.fetchone()

            if not result:
                await callback.answer("Сообщение не найдено", show_alert=True)
                return

            user_id, reviewer, media_type = result

            if reviewer != callback.from_user.id:
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
    if "stats" in admin_cache:
        del admin_cache["stats"]

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

# ================= РАЗБАН =================

@dp.callback_query(F.data.startswith("unban_"))
async def unban_user(callback: CallbackQuery):
    if callback.from_user.id != SUPER_ADMIN:
        await callback.answer("❌ Только главный админ может разбанивать", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[1])
    
    try:
        async with db_pool.acquire() as db:
            await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in unban: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return
    
    if user_id in user_cache:
        del user_cache[user_id]
    if "stats" in admin_cache:
        del admin_cache["stats"]
    
    await callback.message.edit_text(f"✅ Пользователь {user_id} разбанен")
    
    try:
        await bot.send_message(user_id, "✅ Ваш бан снят. Теперь вы снова можете отправлять сообщения.")
    except:
        pass

# ================= РАЗМУТ =================

@dp.callback_query(F.data.startswith("unmute_"))
async def unmute_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return
    
    user_id = int(callback.data.split("_")[1])
    
    try:
        async with db_pool.acquire() as db:
            await db.execute("UPDATE users SET mute_until=NULL WHERE user_id=?", (user_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in unmute: {e}")
        await callback.answer("❌ Ошибка базы данных", show_alert=True)
        return
    
    if user_id in user_cache:
        del user_cache[user_id]
    if "stats" in admin_cache:
        del admin_cache["stats"]
    
    await callback.message.edit_text(f"✅ Пользователь {user_id} размучен")
    
    try:
        await bot.send_message(user_id, "✅ Ваш мут снят. Теперь вы снова можете отправлять сообщения.")
    except:
        pass

# ================= СМЕНА СТИЛЯ =================

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

# ================= ГЛАВНАЯ ФУНКЦИЯ =================

async def main():
    global night_mode_enabled, maintenance_mode, shutdown_flag
    
    logger.info("=" * 50)
    logger.info("BOT STARTING ON RAILWAY...")
    
    await init_db()
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key='night_mode'")
            result = await cursor.fetchone()
            if result:
                night_mode_enabled = bool(int(result[0]))
            
            cursor = await db.execute("SELECT value FROM settings WHERE key='maintenance'")
            result = await cursor.fetchone()
            if result:
                maintenance_mode = bool(int(result[0]))
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
    
    asyncio.create_task(auto_post_messages())
    asyncio.create_task(check_long_pending_messages())
    asyncio.create_task(heartbeat())
    
    logger.info("=" * 50)
    logger.info(f"🤖 Бот запущен на Railway!")
    logger.info(f"👑 SUPER_ADMIN: {SUPER_ADMIN}")
    logger.info(f"👥 ADMINS: {ADMINS}")
    logger.info(f"🌙 Ночной режим: {'✅' if night_mode_enabled else '❌'}")
    logger.info(f"🛠 Техработы: {'✅' if maintenance_mode else '❌'}")
    logger.info(f"📚 Черный список: {len(blacklist_cache)} слов")
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

# ================= ЗАПУСК =================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")