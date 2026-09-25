import asyncio
import re
from datetime import timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import config
import db
import keyboards as kb
from utils import (available_days, booking_dt, booking_summary, fmt_day, free_slots, notify_admins,
                   now)

router = Router()
_booking_lock = asyncio.Lock()  # чтобы два клиента не заняли один слот одновременно


class Booking(StatesGroup):
    phone = State()
    confirm = State()


async def _get(state: FSMContext, cb: CallbackQuery, *keys: str) -> dict | None:
    """Достаёт данные записи; если их нет (старая кнопка, перезапуск) — просит начать заново."""
    data = await state.get_data()
    if all(k in data for k in keys):
        return data
    await cb.answer("Запись устарела, начните заново: «Записаться»", show_alert=True)
    return None


# ---------- Меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {escape(message.from_user.first_name)}! 👋\n\n"
        f"Я бот барбершопа <b>{config.SALON_NAME}</b>. Запишу вас к мастеру за пару кликов, "
        f"напомню о визите и помогу перенести запись.",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>")


@router.message(F.text == kb.MENU_PRICES)
async def show_prices(message: Message):
    lines = [f"• {s.title} — <b>{s.price} ₽</b> ({s.duration} мин)" for s in config.SERVICES.values()]
    await message.answer("💈 <b>Услуги и цены</b>\n\n" + "\n".join(lines))


@router.message(F.text == kb.MENU_CONTACTS)
async def show_contacts(message: Message):
    await message.answer(
        f"📍 <b>{config.SALON_NAME}</b>\n\n"
        f"Адрес: {config.ADDRESS}\n"
        f"Телефон: {config.PHONE}\n"
        f"Работаем ежедневно {config.WORK_START}–{config.WORK_END}\n\n"
        f'<a href="{config.MAP_URL}">Открыть на карте</a>',
        disable_web_page_preview=True,
    )


# ---------- Запись: услуга → мастер → день → время ----------

@router.message(F.text == kb.MENU_BOOK)
async def book_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите услугу:", reply_markup=kb.services_kb())


@router.callback_query(kb.ServiceCB.filter())
async def pick_service(cb: CallbackQuery, callback_data: kb.ServiceCB, state: FSMContext):
    if callback_data.id not in config.SERVICES:
        return await cb.answer("Услуга больше недоступна", show_alert=True)
    await state.update_data(service_id=callback_data.id)
    await cb.message.edit_text(
        f"Услуга: <b>{config.SERVICES[callback_data.id].title}</b>\n\nВыберите мастера:",
        reply_markup=kb.masters_kb(),
    )
    await cb.answer()


@router.callback_query(kb.MasterCB.filter())
async def pick_master(cb: CallbackQuery, callback_data: kb.MasterCB, state: FSMContext):
    if not await _get(state, cb, "service_id"):
        return
    await state.update_data(master_id=callback_data.id)
    await cb.message.edit_text(
        f"Мастер: <b>{config.MASTERS[callback_data.id]}</b>\n\nВыберите день:",
        reply_markup=kb.days_kb(available_days()),
    )
    await cb.answer()


@router.callback_query(kb.DayCB.filter())
async def pick_day(cb: CallbackQuery, callback_data: kb.DayCB, state: FSMContext):
    data = await _get(state, cb, "service_id", "master_id")
    if not data:
        return
    duration = config.SERVICES[data["service_id"]].duration
    slots = await free_slots(data["master_id"], callback_data.day, duration)
    if not slots:
        return await cb.answer("На этот день свободного времени нет, выберите другой 🙏", show_alert=True)
    await state.update_data(day=callback_data.day)
    await cb.message.edit_text(
        f"{fmt_day(callback_data.day)}, мастер <b>{config.MASTERS[data['master_id']]}</b>\n\n"
        f"Свободное время:",
        reply_markup=kb.slots_kb(slots),
    )
    await cb.answer()


@router.callback_query(kb.TimeCB.filter())
async def pick_time(cb: CallbackQuery, callback_data: kb.TimeCB, state: FSMContext):
    data = await _get(state, cb, "service_id", "master_id", "day")
    if not data:
        return
    start = f"{callback_data.hhmm[:2]}:{callback_data.hhmm[2:]}"
    await state.update_data(start=start)
    await cb.message.edit_text(booking_summary(data["service_id"], data["master_id"], data["day"], start))
    await state.set_state(Booking.phone)
    await cb.message.answer(
        "Остался номер телефона — нажмите кнопку ниже или введите его вручную:",
        reply_markup=kb.phone_kb(),
    )
    await cb.answer()


@router.callback_query(kb.BackCB.filter())
async def go_back(cb: CallbackQuery, callback_data: kb.BackCB, state: FSMContext):
    data = await state.get_data()
    if callback_data.to == "services" or "service_id" not in data:
        await cb.message.edit_text("Выберите услугу:", reply_markup=kb.services_kb())
    elif callback_data.to == "masters" or "master_id" not in data:
        await cb.message.edit_text(
            f"Услуга: <b>{config.SERVICES[data['service_id']].title}</b>\n\nВыберите мастера:",
            reply_markup=kb.masters_kb(),
        )
    else:  # days
        await cb.message.edit_text(
            f"Мастер: <b>{config.MASTERS[data['master_id']]}</b>\n\nВыберите день:",
            reply_markup=kb.days_kb(available_days()),
        )
    await cb.answer()


# ---------- Телефон и подтверждение ----------

@router.message(Booking.phone, F.text == kb.CANCEL)
@router.message(Booking.confirm, F.text == kb.CANCEL)
async def cancel_flow(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Запись отменена. Возвращайтесь, когда будет удобно 🙂", reply_markup=kb.main_menu())


@router.message(Booking.phone, F.contact | F.text)
async def got_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text.strip()
    digits = re.sub(r"\D", "", phone)
    if not 10 <= len(digits) <= 15:
        return await message.answer("Похоже, номер введён с ошибкой. Пример: +7 900 123-45-67")
    await state.update_data(phone=phone, client_name=message.from_user.full_name)
    await state.set_state(Booking.confirm)
    data = await state.get_data()
    await message.answer("Номер сохранён ✅", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "<b>Проверьте запись:</b>\n\n"
        + booking_summary(data["service_id"], data["master_id"], data["day"], data["start"])
        + f"\n📱 Телефон: {escape(phone)}",
        reply_markup=kb.confirm_kb(),
    )


@router.callback_query(Booking.confirm, kb.ConfirmCB.filter())
async def confirm(cb: CallbackQuery, callback_data: kb.ConfirmCB, state: FSMContext):
    if callback_data.action != "yes":
        await state.clear()
        await cb.message.edit_text("Запись отменена.")
        await cb.message.answer("Чем ещё помочь?", reply_markup=kb.main_menu())
        return await cb.answer()

    data = await _get(state, cb, "service_id", "master_id", "day", "start", "phone")
    if not data:
        return
    service = config.SERVICES[data["service_id"]]

    async with _booking_lock:
        if data["start"] not in await free_slots(data["master_id"], data["day"], service.duration):
            await cb.message.edit_text("😔 Это время только что заняли. Выберите другое:")
            slots = await free_slots(data["master_id"], data["day"], service.duration)
            await state.set_state(None)
            await cb.message.edit_reply_markup(reply_markup=kb.slots_kb(slots))
            return await cb.answer()
        starts_soon = booking_dt(data["day"], data["start"]) - now() <= timedelta(minutes=config.REMIND_BEFORE_MIN)
        booking_id = await db.add_booking(
            cb.from_user.id, data["client_name"], data["phone"], data["service_id"],
            data["master_id"], data["day"], data["start"], service.duration, reminded=starts_soon,
        )

    await state.clear()
    summary = booking_summary(data["service_id"], data["master_id"], data["day"], data["start"])
    await cb.message.edit_text(
        f"✅ <b>Вы записаны!</b>\n\n{summary}\n📍 {config.ADDRESS}\n\n"
        f"Напомню о визите за {config.REMIND_BEFORE_MIN // 60} ч. Отменить можно в «Мои записи»."
    )
    await cb.message.answer("До встречи! 💈", reply_markup=kb.main_menu())
    await cb.answer("Готово!")
    await notify_admins(
        cb.bot,
        f"🆕 <b>Новая запись #{booking_id}</b>\n\n{summary}\n"
        f"🙋 {escape(data['client_name'])}, {escape(data['phone'])}",
    )


# ---------- Мои записи ----------

async def _render_my(user_id: int) -> tuple[str, object]:
    current = now()
    bookings = await db.user_upcoming(user_id, current.date().isoformat(), current.strftime("%H:%M"))
    if not bookings:
        return "У вас нет предстоящих записей.", None
    lines = [f"• {fmt_day(b['day'])} в <b>{b['start']}</b> — {config.SERVICES[b['service_id']].title}, "
             f"мастер {config.MASTERS[b['master_id']]}" for b in bookings]
    return "📋 <b>Ваши записи:</b>\n\n" + "\n".join(lines), kb.my_bookings_kb(bookings)


@router.message(F.text == kb.MENU_MY)
async def my_bookings(message: Message):
    text, markup = await _render_my(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(kb.CancelBookingCB.filter())
async def cancel_booking(cb: CallbackQuery, callback_data: kb.CancelBookingCB):
    b = await db.get_booking(callback_data.id)
    if not b or b["user_id"] != cb.from_user.id or b["status"] != "active":
        return await cb.answer("Запись не найдена или уже отменена", show_alert=True)
    await db.cancel_booking(b["id"])
    text, markup = await _render_my(cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer("Запись отменена")
    await notify_admins(
        cb.bot,
        f"❌ <b>Отмена записи #{b['id']}</b>\n\n"
        + booking_summary(b["service_id"], b["master_id"], b["day"], b["start"])
        + f"\n🙋 {escape(b['client_name'] or '')}, {escape(b['phone'] or '')}",
    )
