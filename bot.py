import asyncio
import logging
from datetime import timedelta
from html import escape

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

import config
import db
from handlers import admin, client
from utils import booking_dt, booking_summary, now


async def send_reminders(bot: Bot) -> None:
    current = now()
    window = timedelta(minutes=config.REMIND_BEFORE_MIN)
    for b in await db.not_reminded(current.date().isoformat(), (current + window).date().isoformat()):
        left = booking_dt(b["day"], b["start"]) - current
        if left > window:
            continue
        if left > timedelta(0):
            try:
                await bot.send_message(
                    b["user_id"],
                    f"⏰ <b>Напоминание</b>, {escape(b['client_name'] or '')}!\n\n"
                    + booking_summary(b["service_id"], b["master_id"], b["day"], b["start"])
                    + f"\n📍 {config.ADDRESS}\n\nЕсли планы изменились — отмените запись в «Мои записи».",
                )
            except Exception:
                logging.exception("Не удалось отправить напоминание по записи #%s", b["id"])
        await db.mark_reminded(b["id"])


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            await send_reminders(bot)
        except Exception:
            logging.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(60)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан — впишите его в файл .env")

    await db.init()
    session = AiohttpSession(proxy=config.PROXY) if config.PROXY else None
    bot = Bot(config.BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(admin.router, client.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="myid", description="Узнать свой Telegram ID"),
    ])
    reminders = asyncio.create_task(reminder_loop(bot))
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        reminders.cancel()


if __name__ == "__main__":
    asyncio.run(main())
