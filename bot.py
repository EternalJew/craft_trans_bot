import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BotCommand
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, Ride, Booking, Parcel
from datetime import datetime

load_dotenv()

# Ініціалізація БД
Base.metadata.create_all(bind=engine)

# Telegram бот
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Встановимо команди, які видно у меню Telegram
async def set_commands():
    await bot.set_my_commands([
        BotCommand(command="rides", description="Переглянути актуальні виїзди"),
        BotCommand(command="book", description="Забронювати місце"),
        BotCommand(command="parcel", description="Зареєструвати посилку"),
        BotCommand(command="help", description="Отримати довідку")
    ])

# /rides – показати рейси
@dp.message(Command("rides"))
async def show_rides(message: types.Message):
    db: Session = SessionLocal()
    rides = db.query(Ride).all()
    if not rides:
        await message.answer("Немає доступних виїздів")
    else:
        msg = "\n".join([f"{r.id}: {r.date} {r.direction}, вільно {r.seats_free}" for r in rides])
        await message.answer(msg)
    db.close()

# /book – бронювання (поки заглушка)
@dp.message(Command("book"))
async def book_place(message: types.Message):
    await message.answer("Функція бронювання місця в процесі розробки")

# /parcel – реєстрація посилки (поки заглушка)
@dp.message(Command("parcel"))
async def register_parcel(message: types.Message):
    await message.answer("Функція реєстрації посилки в процесі розробки")

# /help – показати команди
@dp.message(Command("help"))
async def help_message(message: types.Message):
    await message.answer(
        "Доступні команди:\n"
        "/rides – переглянути виїзди\n"
        "/book – забронювати місце\n"
        "/parcel – зареєструвати посилку\n"
        "/help – довідка"
    )

# Тестове повідомлення на будь-який текст
@dp.message()
async def default_response(message: types.Message):
    await message.answer("Використайте меню команд або /help")

# Запуск polling
if __name__ == "__main__":
    import asyncio

    async def main():
        await set_commands()  # встановлюємо команди
        await dp.start_polling(bot)  # запускаємо polling

    asyncio.run(main())