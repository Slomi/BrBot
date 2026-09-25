import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
DB_PATH = os.getenv("DB_PATH", "barbershop.db")
PROXY = os.getenv("PROXY", "").strip()

# --- Всё, что ниже, меняется под конкретного клиента ---

SALON_NAME = "Бритва"
ADDRESS = "г. Москва, ул. Примерная, 1"
PHONE = "+7 (900) 000-00-00"
MAP_URL = "https://yandex.ru/maps/"

WORK_START = "10:00"
WORK_END = "21:00"
SLOT_STEP_MIN = 30          # шаг сетки времени
DAYS_AHEAD = 7              # на сколько дней вперёд можно записаться
DAYS_OFF = set()            # выходные: 0 = Пн ... 6 = Вс, например {6}
MIN_LEAD_MIN = 30           # минимум минут от "сейчас" до записи
REMIND_BEFORE_MIN = 120     # за сколько минут напомнить клиенту


@dataclass(frozen=True)
class Service:
    id: str
    title: str
    price: int
    duration: int  # минуты


SERVICES = {s.id: s for s in [
    Service("haircut", "Мужская стрижка", 1800, 60),
    Service("buzz", "Стрижка машинкой", 1000, 30),
    Service("beard", "Моделирование бороды", 1200, 30),
    Service("combo", "Стрижка + борода", 2700, 90),
    Service("kids", "Детская стрижка", 1300, 45),
]}

MASTERS = {
    "alex": "Алексей",
    "dima": "Дмитрий",
    "artem": "Артём",
}
