import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.types import BotCommand, BotCommandScopeChatMember, BotCommandScopeDefault
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, engine
from models import Base, Ride, Booking, Parcel
from datetime import datetime, date

load_dotenv()

# Ініціалізація БД
Base.metadata.create_all(bind=engine)

# Telegram бот
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)

# FSM storage & dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Просте in-memory відстеження менеджерів (user_id)
MANAGERS = set()
MANAGER_KEY = os.getenv("MANAGER_KEY")


# FSM states for interactive add_ride flow
class AddRideStates(StatesGroup):
    date = State()
    direction = State()
    seats = State()


# FSM for booking flow
class BookingStates(StatesGroup):
    choosing_ride = State()
    phone = State()
    name = State()
    seats = State()
    comment = State()


# FSM for manager login
class ManagerLoginStates(StatesGroup):
    await_key = State()


from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def get_public_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='/rides')],
        [KeyboardButton(text='/book')],
        [KeyboardButton(text='/parcel')],
        [KeyboardButton(text='/manager_login')],
        [KeyboardButton(text='/help')],
    ], resize_keyboard=True)
    return kb


def get_manager_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='/rides')],
        [KeyboardButton(text='/book')],
        [KeyboardButton(text='/parcel')],
        [KeyboardButton(text='/add_ride')],
        [KeyboardButton(text='/ride_stats')],
        [KeyboardButton(text='/parcels_stats')],
        [KeyboardButton(text='/manager_logout')],
        [KeyboardButton(text='/cancel')],
        [KeyboardButton(text='/help')],
    ], resize_keyboard=True)
    return kb


# Встановимо команди, які видно у меню Telegram
async def set_commands():
    # У загальному (default) пулі команд — базові команди для всіх користувачів
    await bot.set_my_commands([
        BotCommand(command="rides", description="Переглянути актуальні виїзди"),
        BotCommand(command="book", description="Забронювати місце"),
        BotCommand(command="parcel", description="Зареєструвати посилку"),
        BotCommand(command="manager_login", description="Вхід менеджера"),
        BotCommand(command="help", description="Отримати довідку"),
    ], scope=BotCommandScopeDefault())


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
    # show available rides as inline buttons
    db = SessionLocal()
    rides = db.query(Ride).filter(Ride.seats_free > 0).all()
    db.close()
    if not rides:
        await message.answer("Немає доступних рейсів для бронювання")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{r.date} {r.direction} ({r.seats_free} вільно)", callback_data=f"book_ride:{r.id}")]
        for r in rides
    ])
    await message.answer("Оберіть рейс:", reply_markup=kb)


@dp.callback_query(lambda c: c.data and c.data.startswith("book_ride:"))
async def book_select_ride(callback: types.CallbackQuery, state: FSMContext):
    ride_id = int(callback.data.split(":", 1)[1])
    await state.update_data(ride_id=ride_id)
    await state.set_state(BookingStates.phone)
    await callback.message.answer("Введіть, будь ласка, ваш телефонний номер:")
    await callback.answer()


@dp.message(StateFilter(BookingStates.phone))
async def booking_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)
    await state.set_state(BookingStates.name)
    await message.answer("Введіть ПІБ (Прізвище Ім'я):")


@dp.message(StateFilter(BookingStates.name))
async def booking_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(BookingStates.seats)
    await message.answer("Скільки місць бронюєте? (число)")


@dp.message(StateFilter(BookingStates.seats))
async def booking_seats(message: types.Message, state: FSMContext):
    try:
        seats = int(message.text.strip())
    except ValueError:
        await message.answer("Введіть, будь ласка, ціле число")
        return
    await state.update_data(seats=seats)
    await state.set_state(BookingStates.comment)
    await message.answer("Додатковий коментар (або надішліть '-' щоб пропустити):")


@dp.message(StateFilter(BookingStates.comment))
async def booking_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    comment = message.text.strip()
    if comment == '-':
        comment = None
    ride_id = data.get('ride_id')
    phone = data.get('phone')
    name = data.get('name')
    seats = data.get('seats')

    db = SessionLocal()
    ride = db.query(Ride).filter(Ride.id == ride_id).with_for_update().first()
    if not ride:
        await message.answer("Рейс не знайдено або вже відмінений")
        db.close()
        await state.clear()
        return
    if ride.seats_free < seats:
        await message.answer(f"Недостатньо місць. Вільно лише {ride.seats_free}")
        db.close()
        await state.clear()
        return
    booking = Booking(ride_id=ride_id, name=name, phone=phone, seats=seats, comment=comment)
    db.add(booking)
    ride.seats_free -= seats
    db.commit()
    db.refresh(booking)
    db.close()
    await message.answer(f"Бронювання підтверджено. id={booking.id}")
    await state.clear()


# /parcel – реєстрація посилки (поки заглушка)
@dp.message(Command("parcel"))
async def register_parcel(message: types.Message):
    await message.answer("Функція реєстрації посилки в процесі розробки")


# /help – показати команди
@dp.message(Command("help"))
async def help_message(message: types.Message):
    # show keyboard depending on role
    if is_manager(message.from_user.id):
        await message.answer("Доступні команди (менеджер):", reply_markup=get_manager_keyboard())
    else:
        await message.answer("Доступні команди:", reply_markup=get_public_keyboard())


def is_manager(user_id: int) -> bool:
    return user_id in MANAGERS


@dp.message(Command("manager_login"))
async def manager_login(message: types.Message, state: FSMContext):
    # Start interactive manager login (ask for key)
    await state.set_state(ManagerLoginStates.await_key)
    await message.answer("Введіть ключ менеджера:")


@dp.message(StateFilter(ManagerLoginStates.await_key))
async def manager_login_key(message: types.Message, state: FSMContext):
    key = message.text.strip()
    if MANAGER_KEY and key == MANAGER_KEY:
        MANAGERS.add(message.from_user.id)
        await message.answer("Успішний вхід як менеджер", reply_markup=get_manager_keyboard())
        # Показати цьому менеджеру повний набір команд (припускаємо приватний чат)
        try:
            full_cmds = [
                BotCommand(command="rides", description="Переглянути актуальні виїзди"),
                BotCommand(command="book", description="Забронювати місце"),
                BotCommand(command="parcel", description="Зареєструвати посилку"),
                BotCommand(command="cancel", description="Скасувати поточну операцію"),
                BotCommand(command="manager_logout", description="Вийти як менеджер"),
                BotCommand(command="add_ride", description="(менеджер) Додати рейс"),
                BotCommand(command="ride_stats", description="(менеджер) Статистика рейсу"),
                BotCommand(command="parcels_stats", description="(менеджер) Статистика посилок"),
                BotCommand(command="help", description="Отримати довідку")
            ]
            await bot.set_my_commands(full_cmds, scope=BotCommandScopeChatMember(chat_id=message.chat.id, user_id=message.from_user.id))
        except Exception:
            pass
    else:
        await message.answer("Невірний ключ менеджера")
    await state.clear()


@dp.message(Command("manager_logout"))
async def manager_logout(message: types.Message):
    uid = message.from_user.id
    if uid in MANAGERS:
        MANAGERS.remove(uid)
        await message.answer("Ви вийшли як менеджер", reply_markup=get_public_keyboard())
        # Видалити персанальне меню для цього користувача, щоб клієнт повернувся до глобального списку
        try:
            await bot.delete_my_commands(scope=BotCommandScopeChatMember(chat_id=message.chat.id, user_id=uid))
        except Exception:
            pass
    else:
        await message.answer("Ви не були в ролі менеджера")


@dp.message(Command("add_ride"))
async def add_ride_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if not is_manager(uid):
        await message.answer("Тільки менеджер може додавати рейси")
        return
    await state.clear()
    await state.set_state(AddRideStates.date)
    await message.answer("Додаємо рейс. Крок 1/3 — введіть дату у форматі YYYY-MM-DD (наприклад 2025-10-25).\nЩоб скасувати, надішліть /cancel")


@dp.message(Command("cancel"))
async def cancel_operation(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Немає активної операції для скасування")
        return
    await state.clear()
    await message.answer("Операцію скасовано")


@dp.message(StateFilter(AddRideStates.date))
async def add_ride_date(message: types.Message, state: FSMContext):
    text = message.text.strip()
    try:
        dt = date.fromisoformat(text)
    except Exception:
        await message.answer("Неправильний формат дати. Використовуйте YYYY-MM-DD або надішліть /cancel")
        return
    await state.update_data(date=dt)
    await state.set_state(AddRideStates.direction)
    await message.answer("Крок 2/3 — введіть напрямок (наприклад: UA -> CZ)")


@dp.message(StateFilter(AddRideStates.direction))
async def add_ride_direction(message: types.Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(direction=text)
    await state.set_state(AddRideStates.seats)
    await message.answer("Крок 3/3 — введіть кількість місць (ціле число)")


@dp.message(StateFilter(AddRideStates.seats))
async def add_ride_seats(message: types.Message, state: FSMContext):
    text = message.text.strip()
    try:
        seats = int(text)
    except ValueError:
        await message.answer("Кількість місць має бути цілим числом. Спробуйте ще або надішліть /cancel")
        return
    data = await state.get_data()
    dt = data.get("date")
    direction = data.get("direction")
    try:
        db = SessionLocal()
        ride = Ride(date=dt, direction=direction, seats_total=seats, seats_free=seats)
        db.add(ride)
        db.commit()
        db.refresh(ride)
        db.close()
        await state.clear()
        await message.answer(f"Рейс додано: id={ride.id}, {ride.date} {ride.direction}, місць: {ride.seats_total}")
    except Exception as e:
        await state.clear()
        await message.answer(f"Помилка при додаванні рейсу: {e}")


@dp.message(Command("ride_stats"))
async def ride_stats(message: types.Message):
    if not is_manager(message.from_user.id):
        await message.answer("Тільки менеджер може дивитися статистику")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Використання: /ride_stats <ride_id>")
        return
    try:
        ride_id = int(parts[1])
    except ValueError:
        await message.answer("ride_id має бути числом")
        return
    db = SessionLocal()
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        await message.answer("Рейсу не знайдено")
        db.close()
        return
    # Порахувати броні
    from models import Booking, Parcel
    bookings_count = db.query(Booking).filter(Booking.ride_id == ride_id).count()
    parcels_count = db.query(Parcel).filter(Parcel.direction == ride.direction).count()
    await message.answer(f"Рейс {ride.id}: {ride.date} {ride.direction}\nБроней: {bookings_count}\nПосилок (той самий напрям): {parcels_count}")
    db.close()


@dp.message(Command("parcels_stats"))
async def parcels_stats(message: types.Message):
    if not is_manager(message.from_user.id):
        await message.answer("Тільки менеджер може дивитися статистику посилок")
        return
    db = SessionLocal()
    from models import Parcel
    total = db.query(Parcel).count()
    by_dir = db.query(Parcel.direction, func.count(Parcel.id)).group_by(Parcel.direction).all()
    lines = [f"Всього посилок: {total}"]
    for direction, cnt in by_dir:
        lines.append(f"{direction}: {cnt}")
    await message.answer("\n".join(lines))
    db.close()


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
