from datetime import timedelta
from itertools import groupby

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
from utils import admin_line, fmt_day, now

router = Router()
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("🔧 <b>Админка</b>\nПоказать записи:", reply_markup=kb.admin_kb())


@router.callback_query(kb.AdminCB.filter())
async def show_period(cb: CallbackQuery, callback_data: kb.AdminCB):
    today = now().date()
    start, end = {
        "today": (today, today),
        "tomorrow": (today + timedelta(days=1), today + timedelta(days=1)),
        "week": (today, today + timedelta(days=6)),
    }[callback_data.period]
    bookings = await db.bookings_between(start.isoformat(), end.isoformat())

    if not bookings:
        text = "Записей нет."
    else:
        blocks = []
        for day, items in groupby(bookings, key=lambda b: b["day"]):
            items = list(items)
            revenue = sum(config.SERVICES[b["service_id"]].price for b in items)
            blocks.append(f"📅 <b>{fmt_day(day)}</b> — {len(items)} зап., ~{revenue} ₽\n"
                          + "\n".join(admin_line(b) for b in items))
        text = "\n\n".join(blocks)

    await cb.message.edit_text(text, reply_markup=kb.admin_kb())
    await cb.answer()
