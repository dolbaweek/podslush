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

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= КОНСТАНТЫ =================

NIGHT_MODE_START = 0
NIGHT_MODE_END = 8
NIGHT_POST_INTERVAL = 30  # 30 минут ночью
AUTO_POST_INTERVAL = 5     # 5 минут днём
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

# Флаги
night_mode_enabled = False  # Ночной режим (00:00-08:00, интервал 30 мин)
auto_mode_enabled = False   # Автоматический режим (08:01-23:59, интервал 5 мин)
maintenance_mode = False
maintenance_exceptions = set()
shutdown_flag = False
start_time = time.time()

# ================= БАЗОВЫЕ СПИСКИ СЛОВ =================

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

    # ЧАСТИ ТЕЛА
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

    # ДЕЙСТВИЯ
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

    # НОГИ / СТУПНИ
    "ножки", "ножек", "ножкам", "ножками", "ножках", "ножка", "ножку", "ножке",
    "ноги", "ног", "ногам", "ногами", "ногах", "нога", "ногу", "ногой",
    "ступни", "ступней", "ступням", "ступнями", "ступнях", "ступня", "ступню", "ступней",
    "пальцы ног", "пальцев ног", "пальцам ног", "пальцами ног", "пальчик ноги",
    "облизать ноги", "оближет ноги", "лижет ноги", "лизать ноги", "лижу ноги",

    # ПОЛОВОЙ АКТ
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

ADMIN_MESSAGE_INFO = (
    "📬 <b>Отправка сообщения администрации</b>\n\n"
    "Вы можете написать личное сообщение администрации канала.\n"
    "• Сообщение будет доставлено лично админам\n"
    "• Отправлять можно <b>раз в 30 минут</b>\n"
    "• Не злоупотребляйте, пожалуйста\n\n"
    "Напишите ваше сообщение одним текстом:"
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
    waiting_for_admin_message = State()

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
    """
    Определяет текущий режим работы и интервал публикации
    Возвращает: (режим, интервал в минутах)
    режим: 'night' (ночной), 'auto' (автоматический дневной), 'manual' (ручной)
    """
    now_utc = datetime.utcnow()
    now_msk = now_utc + timedelta(hours=3)
    hour = now_msk.hour
    
    # Ночной режим: 00:00 - 08:00
    if hour < 8:
        if night_mode_enabled:
            return 'night', NIGHT_POST_INTERVAL
        else:
            return 'night_disabled', NIGHT_POST_INTERVAL
    # Автоматический режим: 08:01 - 23:59
    else:
        if auto_mode_enabled:
            return 'auto', AUTO_POST_INTERVAL
        else:
            return 'auto_disabled', AUTO_POST_INTERVAL

def can_auto_post_now() -> bool:
    """Проверяет, можно ли сейчас публиковать автоматически"""
    now_utc = datetime.utcnow()
    now_msk = now_utc + timedelta(hours=3)
    hour = now_msk.hour
    
    if hour < 8:  # Ночное время
        return night_mode_enabled
    else:  # Дневное время
        return auto_mode_enabled

# ================= ВОДЯНОЙ ЗНАК (15 ТЕКСТОВЫХ + ЦЕНТРАЛЬНОЕ ФОТО) =================

async def add_watermark_to_photo(photo_file_id: str) -> str:
    """
    Накладывает:
    - 15 мелких полупрозрачных текстовых знаков @podslu10 (3 колонки по 5)
    - Полупрозрачное фото по центру (watermark_center.png) - теперь более заметное
    """
    try:
        # Скачиваем фото пользователя
        file = await bot.get_file(photo_file_id)
        photo_bytes = await bot.download_file(file.file_path)

        # Открываем изображение пользователя
        img = Image.open(photo_bytes).convert("RGBA")
        width, height = img.size

        # ===== 1. ТЕКСТОВЫЕ ВОДЯНЫЕ ЗНАКИ (15 штук) =====
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        # Текст водяного знака
        text = "@podslu10"
        
        # РАЗМЕР ШРИФТА - 4% от ширины
        font_size = max(16, int(width * 0.04))
        
        # Пробуем использовать разные шрифты
        font = None
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("C:\\Windows\\Fonts\\Arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()

        # Получаем размер текста
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # ПРОЗРАЧНОСТЬ ТЕКСТА - 50% (как в оригинале)
        fill_color = (0, 0, 0, 0)  # 50% opacity

        # ПОЗИЦИИ ПО ГОРИЗОНТАЛИ - три колонки
        positions_x = [
            int(width * 0.12),  # слева
            int(width * 0.5),   # центр
            int(width * 0.88)   # справа
        ]

        # ПОЗИЦИИ ПО ВЕРТИКАЛИ - 5 знаков
        positions_y = []
        for i in range(5):
            y = int(height * (0.1 + i * 0.2))  # 10%, 30%, 50%, 70%, 90%
            positions_y.append(y)

        # Заполняем все колонки
        for col, x in enumerate(positions_x):
            for row, y in enumerate(positions_y):
                # Небольшое случайное смещение
                offset_x = int(text_width * 0.2) * (hash(f"{col}{row}") % 3 - 1)
                offset_y = int(text_height * 0.2) * (hash(f"{col}{row}") % 3 - 1)
                
                final_x = x + offset_x
                final_y = y + offset_y
                
                # Центрируем текст
                draw_x = final_x - text_width // 2
                draw_y = final_y - text_height // 2
                
                draw.text(
                    (draw_x, draw_y), 
                    text, 
                    font=font, 
                    fill=fill_color
                )

        # ===== 2. ЦЕНТРАЛЬНОЕ ФОТО-ВСТАВКА =====
        center_watermark_path = "watermark_center.png"
        
        if os.path.exists(center_watermark_path):
            try:
                # Открываем центральный водяной знак
                center_img = Image.open(center_watermark_path).convert("RGBA")
                
                # Получаем размеры центрального фото
                c_width, c_height = center_img.size
                
                # Рассчитываем размер для центрального знака (40% от ширины фото - чуть больше)
                target_size = int(width * 0.4)
                
                # Сохраняем пропорции
                ratio = min(target_size / c_width, target_size / c_height)
                new_size = (int(c_width * ratio), int(c_height * ratio))
                
                # Изменяем размер с сохранением пропорций
                center_img = center_img.resize(new_size, Image.Resampling.LANCZOS)
                
                # ДЕЛАЕМ ЦЕНТРАЛЬНЫЙ ЗНАК БОЛЕЕ ЗАМЕТНЫМ (40% прозрачности)
                center_array = center_img.getdata()
                new_center_array = []
                for item in center_array:
                    # Если пиксель не полностью прозрачный
                    if item[3] > 0:
                        # Устанавливаем прозрачность 40% (102 из 255)
                        new_center_array.append((item[0], item[1], item[2], 155))
                    else:
                        new_center_array.append(item)
                
                center_img.putdata(new_center_array)
                
                # Позиция для центрального знака (строго по центру)
                center_x = (width - new_size[0]) // 2
                center_y = (height - new_size[1]) // 2
                
                # Создаем слой для центрального знака
                center_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
                center_layer.paste(center_img, (center_x, center_y), center_img)
                
                # Объединяем текстовый слой и центральный слой
                combined_layer = Image.alpha_composite(txt_layer, center_layer)
                
                logger.info(f"✅ Center watermark added: size={new_size[0]}x{new_size[1]}, opacity=40%")
                
            except Exception as e:
                logger.error(f"❌ Error adding center watermark: {e}")
                combined_layer = txt_layer
        else:
            logger.warning(f"⚠️ Center watermark file {center_watermark_path} not found. Using only text watermarks.")
            combined_layer = txt_layer

        # Объединяем оригинал со всеми водяными знаками
        watermarked = Image.alpha_composite(img, combined_layer).convert("RGB")

        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            temp_path = tmp_file.name
            watermarked.save(temp_path, format="JPEG", quality=95)

        # Отправляем обратно в Telegram
        msg = await bot.send_photo(
            chat_id=SUPER_ADMIN,
            photo=FSInputFile(temp_path)
        )
        
        new_file_id = msg.photo[-1].file_id
        os.unlink(temp_path)
        
        center_status = "with center photo (40% opacity)" if os.path.exists(center_watermark_path) else "without center photo"
        logger.info(f"✅ Watermark added - 15 text marks (50% opacity) + {center_status}, size: {font_size}px")
        return new_file_id

    except Exception as e:
        logger.error(f"❌ Watermark error: {e}")
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
        await db.execute("INSERT OR IGNORE INTO settings VALUES('auto_mode','0')")  # Новый флаг
        await db.execute("INSERT OR IGNORE INTO settings VALUES('maintenance','0')")
        await db.commit()
    
    await load_blacklist_to_cache()

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
    
    # Для обычных админов НЕ показываем ID пользователя
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
            header = f"┌─────────────────┐\n│  ПОДСЛУШАНО  │\n└─────────────────┘\n\n"
            footer = f"\n\n➖➖➖➖➖➖➖➖➖\n✉ <a href='https://t.me/{BOT_USERNAME}'>Написать анонимно</a>"
        else:
            header = f"📌 <b>Анонимное сообщение</b>\n\n"
            footer = f"\n\n—\n<a href='https://t.me/{BOT_USERNAME}'>✉ Ответить</a>"
        
        await bot.send_message(
            CHANNEL_ID,
            f"{header}<blockquote>{text}</blockquote>{footer}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        
        # Определяем режим для уведомления
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
            
            # Проверяем, можно ли публиковать сейчас
            if can_auto_post_now() and not maintenance_mode:
                # Получаем текущий интервал
                _, interval = get_current_mode_and_interval()
                
                # Проверяем, прошло ли достаточно времени
                if current_time - last_post_time >= interval * 60:
                    await post_next_message()
                    last_post_time = current_time
            
            # Проверяем каждые 30 секунд
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
                    
                    # Для SUPER_ADMIN показываем ID
                    for admin in ADMINS:
                        if admin == SUPER_ADMIN:
                            text = (
                                f"⚠️ <b>Долгое сообщение #{msg_id}</b>\n\n"
                                f"Висит в очереди больше {LONG_MESSAGE_THRESHOLD} минут!\n"
                                f"Тип: {media_type or 'текст'}\n"
                                f"Время отправки: {created_at[:16]}\n"
                                f"Текст: {short_text}\n"
                                f"От пользователя: <code>{user_id}</code>"
                            )
                        else:
                            text = (
                                f"⚠️ <b>Долгое сообщение #{msg_id}</b>\n\n"
                                f"Висит в очереди больше {LONG_MESSAGE_THRESHOLD} минут!\n"
                                f"Тип: {media_type or 'текст'}\n"
                                f"Время отправки: {created_at[:16]}\n"
                                f"Текст: {short_text}"
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
            [KeyboardButton(text="📨 Ожидающие проверки")]
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
            # [KeyboardButton(text="📩 Написать админу")]  # Функция отключена до починки
        ],
        resize_keyboard=True,
        input_field_placeholder="Отправьте сообщение, фото или видео..."
    )

    await message.answer(
        "👋 <b>Подслушано</b>\n\n"
        "Отправьте сообщение, фото или видео - они будут опубликованы анонимно после проверки.\n"
        "В автоматическом режиме (с 8:01 до 23:59) текстовые сообщения публикуются раз в 5 минут.\n"
        "В ночное время (с 0 до 8 утра) - раз в 30 минут.",
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
        "• Видео\n\n"
        "Режимы автоматической публикации:\n"
        "🌙 Ночной (00:00 - 08:00): текстовые сообщения без ссылок публикуются раз в 30 минут\n"
        "☀️ Автоматический (08:01 - 23:59): текстовые сообщения без ссылок публикуются раз в 5 минут\n\n"
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
        "• Очень сильная травля\n"
        "• Реклама\n\n"
        "Фото и видео всегда проходят ручную проверку."
    )

# ================= ФУНКЦИЯ "НАПИСАТЬ АДМИНУ" (ЗАКОММЕНТИРОВАНА) =================

# @dp.message(F.text == "📩 Написать админу")
# async def ask_admin(message: Message, state: FSMContext):
#     user_id = message.from_user.id
# 
#     if user_id in user_message_cooldown:
#         remaining = user_message_cooldown[user_id]
#         minutes = remaining // 60
#         seconds = remaining % 60
#         await message.answer(f"⏳ Вы уже отправляли сообщение. Подождите {minutes} мин {seconds} сек.")
#         return
# 
#     keyboard = ReplyKeyboardMarkup(
#         keyboard=[[KeyboardButton(text="❌ Отмена")]],
#         resize_keyboard=True,
#         one_time_keyboard=True
#     )
# 
#     await state.set_state(AdminStates.waiting_for_admin_message)
#     await message.answer(ADMIN_MESSAGE_INFO, reply_markup=keyboard)
# 
# @dp.message(AdminStates.waiting_for_admin_message)
# async def send_to_admin(message: Message, state: FSMContext):
#     user_id = message.from_user.id
# 
#     if message.text == "❌ Отмена":
#         await state.clear()
#         keyboard = ReplyKeyboardMarkup(
#             keyboard=[
#                 [KeyboardButton(text="ℹ Информация")],
#                 [KeyboardButton(text="❓ Помощь")],
#                 [KeyboardButton(text="📩 Написать админу")]
#             ],
#             resize_keyboard=True
#         )
#         await message.answer("❌ Отправка отменена", reply_markup=keyboard)
#         return
# 
#     text = message.text
#     if not text:
#         await message.answer("❌ Напишите текст сообщения")
#         return
# 
#     async with db_pool.acquire() as db:
#         await db.execute(
#             "INSERT INTO admin_messages (user_id, message, created_at) VALUES (?, ?, ?)",
#             (user_id, text, datetime.utcnow().isoformat())
#         )
#         await db.commit()
# 
#     keyboard = InlineKeyboardMarkup(inline_keyboard=[
#         [
#             InlineKeyboardButton(text="✅ Рассмотрено", callback_data=f"adminmsg_done_{user_id}"),
#             InlineKeyboardButton(text="🔇 Мут", callback_data=f"adminmsg_mute_{user_id}")
#         ],
#         [
#             InlineKeyboardButton(text="💬 Ответить", callback_data=f"adminmsg_reply_{user_id}")
#         ]
#     ])
# 
#     await bot.send_message(
#         SUPER_ADMIN,
#         f"📩 <b>Личное сообщение</b>\n\n"
#         f"👤 ID: <code>{user_id}</code>\n"
#         f"📛 Username: @{message.from_user.username or 'нет'}\n"
#         f"📝 Имя: {message.from_user.first_name or 'нет'}\n\n"
#         f"💬 <b>Сообщение:</b>\n{text}",
#         reply_markup=keyboard
#     )
# 
#     user_message_cooldown[user_id] = 1800
# 
#     keyboard_normal = ReplyKeyboardMarkup(
#         keyboard=[
#             [KeyboardButton(text="ℹ Информация")],
#             [KeyboardButton(text="❓ Помощь")],
#             [KeyboardButton(text="📩 Написать админу")]
#         ],
#         resize_keyboard=True
#     )
# 
#     await message.answer("✅ Сообщение отправлено администрации. Ожидайте ответа.", reply_markup=keyboard_normal)
#     await state.clear()
# 
# @dp.callback_query(F.data.startswith("adminmsg_done_"))
# async def admin_message_done(callback: CallbackQuery):
#     if callback.from_user.id != SUPER_ADMIN:
#         return
#     user_id = int(callback.data.split("_")[2])
#     
#     async with db_pool.acquire() as db:
#         await db.execute(
#             "UPDATE admin_messages SET status='reviewed' WHERE user_id=? AND status='new'",
#             (user_id,)
#         )
#         await db.commit()
#     
#     await callback.message.edit_text(
#         callback.message.text + "\n\n✅ <b>Рассмотрено</b>",
#         reply_markup=None
#     )
#     await callback.answer()
# 
# @dp.callback_query(F.data.startswith("adminmsg_mute_"))
# async def admin_message_mute(callback: CallbackQuery, state: FSMContext):
#     if callback.from_user.id != SUPER_ADMIN:
#         return
#     user_id = int(callback.data.split("_")[2])
# 
#     await state.update_data(mute_user_id=user_id)
#     await state.set_state(AdminStates.waiting_for_mute_duration)
# 
#     keyboard = InlineKeyboardMarkup(inline_keyboard=[
#         [
#             InlineKeyboardButton(text="1 час", callback_data="mute_1h"),
#             InlineKeyboardButton(text="3 часа", callback_data="mute_3h"),
#             InlineKeyboardButton(text="6 часов", callback_data="mute_6h")
#         ],
#         [
#             InlineKeyboardButton(text="12 часов", callback_data="mute_12h"),
#             InlineKeyboardButton(text="1 день", callback_data="mute_1d"),
#             InlineKeyboardButton(text="3 дня", callback_data="mute_3d")
#         ],
#         [
#             InlineKeyboardButton(text="7 дней", callback_data="mute_7d"),
#             InlineKeyboardButton(text="30 дней", callback_data="mute_30d"),
#             InlineKeyboardButton(text="❌ Отмена", callback_data="mute_cancel")
#         ]
#     ])
# 
#     await callback.message.answer(
#         f"⏳ Выберите длительность мута для пользователя {user_id}:",
#         reply_markup=keyboard
#     )
#     await callback.answer()

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
                    (SELECT COUNT(*) FROM admin_actions WHERE date(created_at) = date('now')) as today_actions,
                    (SELECT COUNT(*) FROM admin_messages WHERE status='new') as new_messages
            """, (INSULT_THRESHOLD,))
            
            result = await cursor.fetchone()
            total_users, banned_users, muted_users, exception_users, total_messages, pending_messages, media_messages, auto_posted, with_links, skipped_messages, heavy_insults, post_counter, blacklist_count, today_actions, new_messages = result
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
        f"📩 Новых личных сообщений: {new_messages}\n"
        f"🌙 Ночной режим: {'✅' if night_mode_enabled else '❌'}\n"
        f"☀️ Авто-режим: {'✅' if auto_mode_enabled else '❌'}\n"
        f"🛠 Техработы: {'✅' if maintenance_mode else '❌'}\n"
        f"⏱ Текущий режим: {mode_text} (интервал {interval} мин)"
    )
    
    await message.answer(stats_text)

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
    
    try:
        async with db_pool.acquire() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE status='pending' AND skipped=0"
            )
            total_pending = (await cursor.fetchone())[0]
            
            cursor = await db.execute("""
                SELECT id, user_id, media_type, 
                       substr(text, 1, 50) as short_text, 
                       created_at, has_links, insult_count
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
    
    for msg_id, user_id, media_type, short_text, created_at, has_links, insult_count in pending_messages:
        try:
            msg_date = datetime.fromisoformat(created_at)
            date_str = msg_date.strftime('%d.%m %H:%M')
        except:
            date_str = created_at[:16] if created_at else "неизвестно"
        
        if media_type == "photo":
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
        
        display_text = short_text.replace('\n', ' ').strip() if short_text else "без текста"
        if len(display_text) > 30:
            display_text = display_text[:30] + "..."
        
        # Для обычных админов НЕ показываем user_id
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

@dp.message(F.text == "❌ Закрыть меню")
async def close_menu(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    
    await state.clear()
    await message.answer(
        "Меню закрыто. Чтобы открыть снова, напишите /start",
        reply_markup=ReplyKeyboardRemove()
    )

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
        text += f"{i}. <code>{word}</code>\n"
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
        await message.answer(f"✅ Слово <code>{word}</code> добавлено в черный список")
        await log_admin_action(message.from_user.id, "blacklist_add", details=word)
        
    except aiosqlite.IntegrityError:
        await message.answer(f"❌ Слово <code>{word}</code> уже есть в черном списке")
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
                await message.answer(f"✅ Слово <code>{word}</code> удалено из черного списка")
                await log_admin_action(message.from_user.id, "blacklist_remove", details=word)
            else:
                await message.answer(f"❌ Слово <code>{word}</code> не найдено в черном списке")
        
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
            "night_mode_toggle": "🌙", "auto_mode_toggle": "☀️"
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
    
    import io
    file = io.BytesIO(text.encode('utf-8'))
    file.name = "admin_history.txt"
    
    await callback.message.answer_document(
        document=('admin_history.txt', file),
        caption="📊 Полная история действий"
    )
    
    await callback.answer()

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

# ================= СПИСОК ЗАБАНЕННЫХ =================

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

# ================= СПИСОК ЗАМУЧЕННЫХ =================

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

# ================= ОБРАБОТЧИКИ UNBAN/UNMUTE =================

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

# ================= ОБРАБОТЧИК СООБЩЕНИЙ ПОЛЬЗОВАТЕЛЯ =================

@dp.message(F.photo | F.video | F.text)
async def handle_user_media(message: Message, state: FSMContext):
    """Обработка сообщений от обычных пользователей"""
    
    # Пропускаем админов
    if message.from_user.id in ADMINS:
        return

    # Проверяем, не в состоянии ли FSM
    current_state = await state.get_state()
    if current_state is not None:
        return

    # Игнорируем команды и кнопки меню
    if message.text and (message.text.startswith('/') or message.text in 
        ["🎨 Сменить стиль", "📊 Статистика", "👥 Управление пользователями", 
         "📨 Ожидающие проверки", "❌ Закрыть меню", "ℹ Информация", "❓ Помощь",
         "⏳ Временный мут", "📋 История действий", "📝 Черный список слов",
         "❌ Отмена"]):
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

    now = datetime.utcnow()
    user_id = message.from_user.id

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
            
            formatted_text = f"<blockquote>{text}</blockquote>" if text else None
            
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
            """, (user_id, formatted_text or text, media_type, media_file_id, now.isoformat(), has_links_flag, insult_count))
            
            row = await cursor.fetchone()
            msg_id = row[0]
            await db.commit()
    except Exception as e:
        logger.error(f"DB error in handle_user_media: {e}")
        await message.answer("❌ Ошибка при сохранении сообщения")
        return

    # Обновляем кэш
    user_cache[user_id] = {'banned': False, 'mute_until': None, 'last_message': now}

    # Очищаем кэш
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

    # Предупреждения
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
    display_text = formatted_text if formatted_text else (text or "без текста")

    tasks = []
    for admin in ADMINS:
        # Для SUPER_ADMIN показываем полную информацию
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
                        f"📨 <b>Новое сообщение</b>{warning_text}\n\n{display_text}\n\n🆔 <code>{user_id}</code>\n👤 @{message.from_user.username or 'нет'}",
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                )
        # Для обычных админов НЕ показываем ID и username
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
                        f"📨 <b>Новое сообщение</b>{warning_text}\n\n{display_text}",
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

# ================= ОТВЕТЫ НА СООБЩЕНИЯ =================

# Словарь для временного хранения ответов
reply_storage = {}  # {admin_id: {"user_id": int, "msg_id": int, "type": str}}

@dp.callback_query(F.data.startswith("reply_"))
async def reply_to_message(callback: CallbackQuery):
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
    
    # Сохраняем в отдельный словарь
    reply_storage[callback.from_user.id] = {
        "user_id": user_id,
        "msg_id": msg_id,
        "type": "message"
    }
    
    await callback.message.answer(
        f"📝 Введите текст ответа для пользователя <code>{user_id}</code>\n"
        f"(или отправьте /cancel для отмены)"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("adminmsg_reply_"))
async def admin_message_reply(callback: CallbackQuery):
    """Ответ на личное сообщение"""
    if callback.from_user.id != SUPER_ADMIN:
        return
    
    user_id = int(callback.data.split("_")[2])
    
    # Сохраняем в отдельный словарь
    reply_storage[callback.from_user.id] = {
        "user_id": user_id,
        "type": "admin_message"
    }
    
    await callback.message.answer(
        f"📝 Введите текст ответа для пользователя <code>{user_id}</code>\n"
        f"(или отправьте /cancel для отмены)"
    )
    await callback.answer()


@dp.message()
async def handle_reply_input(message: Message):
    """Обрабатывает ввод ответа от админа"""
    
    # Проверяем, есть ли админ в режиме ответа
    if message.from_user.id not in reply_storage:
        return  # Не в режиме ответа, пропускаем дальше к другим обработчикам
    
    # Проверка на отмену
    if message.text == "/cancel":
        del reply_storage[message.from_user.id]
        await message.answer("❌ Ответ отменён")
        return
    
    # Получаем данные
    data = reply_storage[message.from_user.id]
    user_id = data["user_id"]
    
    if not user_id:
        del reply_storage[message.from_user.id]
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    # Отправляем ответ
    try:
        await bot.send_message(
            user_id,
            f"📝 <b>Ответ от администратора</b>\n\n{message.text}"
        )
        
        # Если это ответ на личное сообщение, обновляем статус
        if data.get("type") == "admin_message":
            async with db_pool.acquire() as db:
                await db.execute(
                    "UPDATE admin_messages SET status='replied' WHERE user_id=? AND status='new'",
                    (user_id,)
                )
                await db.commit()
        
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}")
        await log_admin_action(message.from_user.id, "reply", user_id)
        
    except Exception as e:
        logger.error(f"Reply error: {e}")
        await message.answer(f"❌ Ошибка: {e}")
    
    # Удаляем из хранилища
    del reply_storage[message.from_user.id]

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

    # Создаем клавиатуру
    if media_type == "photo":
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
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{msg_id}")
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
            await callback.message.edit_text(
                text=callback.message.text + warning_text + "\n\n🔄 <b>Рассматривается...</b>",
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

        try:
            new_file_id = await add_watermark_to_photo(media_file_id)
        except Exception as e:
            logger.error(f"Watermark error: {e}")
            await callback.answer("❌ Ошибка при наложении водяного знака", show_alert=True)
            return

        # Получаем стиль и счетчик
        async with db_pool.acquire() as db2:
            cursor = await db2.execute("SELECT value FROM settings WHERE key='post_style'")
            style = (await cursor.fetchone())[0]
            cursor = await db2.execute("SELECT value FROM settings WHERE key='post_counter'")
            counter = int((await cursor.fetchone())[0]) + 1
            await db2.execute("UPDATE settings SET value=? WHERE key='post_counter'", (str(counter),))
            
            await db2.execute(
                "UPDATE messages SET status='approved', reviewed_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), msg_id)
            )
            await db2.commit()

    # Форматируем пост
    if style == "1":
        header = f"💬 <b>Новое анонимное сообщение</b>\n\n"
        footer = f"\n\n━━━━━━━━━━━━━━\n✉ <a href='https://t.me/{BOT_USERNAME}'>Отправить сообщение</a>"
    elif style == "2":
        header = f"┌─────────────────┐\n│  ПОДСЛУШАНО  │\n└─────────────────┘\n\n"
        footer = f"\n\n➖➖➖➖➖➖➖➖➖\n✉ <a href='https://t.me/{BOT_USERNAME}'>Написать анонимно</a>"
    else:
        header = f"📌 <b>Анонимное сообщение</b>\n\n"
        footer = f"\n\n—\n<a href='https://t.me/{BOT_USERNAME}'>✉ Ответить</a>"

    # Публикуем фото с водяным знаком
    await bot.send_photo(
        CHANNEL_ID,
        photo=new_file_id,
        caption=f"{header}{text or ''}{footer}",
        parse_mode=ParseMode.HTML
    )

    # Проверяем тип сообщения для редактирования
    center_status = " + фото-вставка" if os.path.exists("watermark_center.png") else ""
    
    try:
        # Пытаемся отредактировать сообщение с кнопками
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
        # Если не получилось отредактировать, просто удаляем старое сообщение и шлём новое
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(f"✅ Фото #{msg_id} опубликовано с водяным знаком{center_status}")

    # Уведомляем пользователя
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
                # Для обычных админов не показываем user_id
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

# ================= ОБНОВЛЕНИЕ СПИСКА ОЖИДАЮЩИХ =================

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
                       created_at, has_links, insult_count
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
    
    for msg_id, user_id, media_type, short_text, created_at, has_links, insult_count in pending_messages:
        try:
            msg_date = datetime.fromisoformat(created_at)
            date_str = msg_date.strftime('%d.%m %H:%M')
        except:
            date_str = created_at[:16] if created_at else "неизвестно"
        
        if media_type == "photo":
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
        
        display_text = short_text.replace('\n', ' ').strip() if short_text else "без текста"
        if len(display_text) > 30:
            display_text = display_text[:30] + "..."
        
        # Для SUPER_ADMIN показываем ID
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
    await callback.message.answer(
        "➕ Введите ID пользователя для добавления в исключение:\n(или отправьте /cancel для отмены)"
    )
    await callback.answer()


@dp.callback_query(F.data == "remove_exception")
async def remove_exception_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != SUPER_ADMIN:
        return
    await state.set_state(AdminStates.waiting_for_exception_remove)
    await callback.message.answer(
        "➖ Введите ID пользователя для удаления из исключения:\n(или отправьте /cancel для отмены)"
    )
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
            await db.execute(
                "UPDATE users SET maintenance_exception=1 WHERE user_id=?",
                (user_id,)
            )
            await db.commit()
            
            # Обновляем кэш
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
            await db.execute(
                "UPDATE users SET maintenance_exception=0 WHERE user_id=?",
                (user_id,)
            )
            await db.commit()
            
            # Обновляем кэш
            if user_id in maintenance_exceptions:
                maintenance_exceptions.remove(user_id)
            
        await message.answer(f"✅ Пользователь {user_id} удален из исключения")
        await log_admin_action(message.from_user.id, "exception_remove", user_id)
        
    except Exception as e:
        logger.error(f"DB error in process_remove_exception: {e}")
        await message.answer("❌ Ошибка при удалении из исключения")
    
    await state.clear()

# ================= ГЛАВНАЯ ФУНКЦИЯ =================

async def run_http_server():
    """Запускает HTTP-сервер для health checks и пинга"""
    try:
        from aiohttp import web
        import time
        from datetime import timedelta
        
        async def handle(request):
            # Считаем аптайм
            uptime_seconds = time.time() - start_time
            uptime_str = str(timedelta(seconds=int(uptime_seconds)))
            
            # Собираем статистику из БД
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
                "users_in_cache": len(user_cache),
                "pending_in_cache": len(pending_cache),
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
        
        app = web.Application()
        app.router.add_get('/', handle)
        app.router.add_get('/health', handle)
        app.router.add_get('/ping', handle)
        app.router.add_get('/status', handle)
        app.router.add_get('/stats', handle)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"🌐 Advanced HTTP server started on port {port}")
        logger.info(f"📊 Status page: http://localhost:{port}/status")
        logger.info(f"🔗 Public URL: /health, /ping, /status, /stats")
        
    except Exception as e:
        logger.error(f"Failed to start HTTP server: {e}")

async def main():
    global night_mode_enabled, auto_mode_enabled, maintenance_mode, shutdown_flag
    
    logger.info("=" * 50)
    logger.info("BOT STARTING ON RAILWAY...")
    
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
    
    # Запускаем HTTP-сервер
    asyncio.create_task(run_http_server())
    
    logger.info("=" * 50)
    logger.info(f"🤖 Бот запущен на Railway!")
    logger.info(f"👑 SUPER_ADMIN: {SUPER_ADMIN}")
    logger.info(f"👥 ADMINS: {ADMINS}")
    logger.info(f"🌙 Ночной режим: {'✅' if night_mode_enabled else '❌'}")
    logger.info(f"☀️ Авто-режим: {'✅' if auto_mode_enabled else '❌'}")
    logger.info(f"🛠 Техработы: {'✅' if maintenance_mode else '❌'}")
    logger.info(f"📚 Черный список: {len(blacklist_cache)} слов")
    
    # Проверяем наличие файла с центральным водяным знаком
    if os.path.exists("watermark_center.png"):
        logger.info("🖼 Центральный водяной знак: watermark_center.png найден")
    else:
        logger.warning("🖼 Центральный водяной знак не найден. Будет использован только текстовый водяной знак.")
        logger.warning("   Поместите файл watermark_center.png в папку с ботом для активации фото-вставки.")
    
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