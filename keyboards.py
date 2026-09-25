from aiogram.filters.callback_data import CallbackData
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from utils import fmt_day

MENU_BOOK = "✂️ Записаться"
MENU_MY = "📋 Мои записи"
MENU_PRICES = "💈 Услуги и цены"
MENU_CONTACTS = "📍 Контакты"
CANCEL = "❌ Отмена"


class ServiceCB(CallbackData, prefix="svc"):
    id: str


class MasterCB(CallbackData, prefix="mst"):
    id: str


class DayCB(CallbackData, prefix="day"):
    day: str  # YYYY-MM-DD


class TimeCB(CallbackData, prefix="tm"):
    hhmm: str  # "1030" — двоеточие занято разделителем callback_data


class BackCB(CallbackData, prefix="back"):
    to: str


class ConfirmCB(CallbackData, prefix="cnf"):
    action: str  # yes / no


class CancelBookingCB(CallbackData, prefix="cxl"):
    id: int


class AdminCB(CallbackData, prefix="adm"):
    period: str  # today / tomorrow / week


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_BOOK)],
            [KeyboardButton(text=MENU_MY), KeyboardButton(text=MENU_PRICES)],
            [KeyboardButton(text=MENU_CONTACTS)],
        ],
        resize_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text=CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _back(to: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="« Назад", callback_data=BackCB(to=to).pack())


def services_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in config.SERVICES.values():
        b.button(text=f"{s.title} — {s.price} ₽", callback_data=ServiceCB(id=s.id))
    b.adjust(1)
    return b.as_markup()


def masters_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for mid, name in config.MASTERS.items():
        b.button(text=name, callback_data=MasterCB(id=mid))
    b.adjust(1)
    b.row(_back("services"))
    return b.as_markup()


def days_kb(days: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for d in days:
        b.button(text=fmt_day(d), callback_data=DayCB(day=d))
    b.adjust(3)
    b.row(_back("masters"))
    return b.as_markup()


def slots_kb(slots: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in slots:
        b.button(text=t, callback_data=TimeCB(hhmm=t.replace(":", "")))
    b.adjust(4)
    b.row(_back("days"))
    return b.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=ConfirmCB(action="yes"))
    b.button(text="❌ Отменить", callback_data=ConfirmCB(action="no"))
    return b.as_markup()


def my_bookings_kb(bookings) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for bk in bookings:
        b.button(text=f"❌ Отменить {fmt_day(bk['day'])} в {bk['start']}",
                 callback_data=CancelBookingCB(id=bk["id"]))
    b.adjust(1)
    return b.as_markup()


def admin_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Сегодня", callback_data=AdminCB(period="today"))
    b.button(text="Завтра", callback_data=AdminCB(period="tomorrow"))
    b.button(text="Неделя", callback_data=AdminCB(period="week"))
    return b.as_markup()
