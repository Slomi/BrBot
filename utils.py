import logging
from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot

import config
import db

TZ = ZoneInfo(config.TIMEZONE)
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def now() -> datetime:
    return datetime.now(TZ)


def to_min(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def fmt_min(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def fmt_day(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{WEEKDAYS[d.weekday()]}, {d:%d.%m}"


def booking_dt(day: str, start: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{start}").replace(tzinfo=TZ)


def available_days() -> list[str]:
    today = now().date()
    days = (today + timedelta(days=i) for i in range(config.DAYS_AHEAD))
    return [d.isoformat() for d in days if d.weekday() not in config.DAYS_OFF]


async def free_slots(master_id: str, day: str, duration: int) -> list[str]:
    busy = [(to_min(b["start"]), to_min(b["start"]) + b["duration"])
            for b in await db.busy_bookings(master_id, day)]
    current = now()
    earliest = -1
    if day == current.date().isoformat():
        earliest = current.hour * 60 + current.minute + config.MIN_LEAD_MIN

    slots = []
    t, end = to_min(config.WORK_START), to_min(config.WORK_END)
    while t + duration <= end:
        if t >= earliest and all(t + duration <= s or t >= e for s, e in busy):
            slots.append(fmt_min(t))
        t += config.SLOT_STEP_MIN
    return slots


def booking_summary(service_id: str, master_id: str, day: str, start: str) -> str:
    s = config.SERVICES[service_id]
    return (
        f"💈 Услуга: <b>{s.title}</b> — {s.price} ₽\n"
        f"👤 Мастер: <b>{config.MASTERS[master_id]}</b>\n"
        f"📅 Когда: <b>{fmt_day(day)} в {start}</b>"
    )


def admin_line(b) -> str:
    s = config.SERVICES[b["service_id"]]
    return (f"{b['start']} — {s.title}, мастер {config.MASTERS[b['master_id']]}\n"
            f"    {escape(b['client_name'] or '')}, {escape(b['phone'] or '')}")


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            logging.exception("Не удалось отправить уведомление админу %s", admin_id)
