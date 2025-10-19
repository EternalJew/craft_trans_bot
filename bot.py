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
    from_city = State()   
    to_city = State()     
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
        [KeyboardButton(text='/автопарк')],  # додано
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
        [KeyboardButton(text='/автопарк')],  # додано
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
        BotCommand(command="avtopark", description="Переглянути автопарк"),  # додано (латинська команда для меню)
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
    # Перший крок після вибору рейсу — спитати звідки (місто)
    await state.set_state(BookingStates.from_city)
    await callback.message.answer("Звідки ви виїжджаєте? Введіть назву міста:")
    await callback.answer()


@dp.message(StateFilter(BookingStates.from_city))
async def booking_from_city(message: types.Message, state: FSMContext):
    from_city = message.text.strip()
    await state.update_data(from_city=from_city)
    await state.set_state(BookingStates.to_city)
    await message.answer("Куди ви прямуєте? Введіть назву міста:")


@dp.message(StateFilter(BookingStates.to_city))
async def booking_to_city(message: types.Message, state: FSMContext):
    to_city = message.text.strip()
    await state.update_data(to_city=to_city)
    await state.set_state(BookingStates.phone)
    await message.answer("Введіть, будь ласка, ваш телефонний номер:")


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
    from_city = data.get('from_city')
    to_city = data.get('to_city')

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
    booking = Booking(
        ride_id=ride_id,
        name=name,
        phone=phone,
        seats=seats,
        comment=comment,
        from_city=from_city,  # збереження звідки
        to_city=to_city       # збереження куди
    )
    db.add(booking)
    ride.seats_free -= seats
    db.commit()
    db.refresh(booking)

    # Підготуємо інформацію для користувача перед закриттям сесії БД
    ride_date = str(ride.date)
    ride_direction = ride.direction
    booking_id = booking.id

    db.close()

    # Повідомлення клієнту з деталями бронювання і нагадуванням
    msg = (
        f"Бронювання підтверджено. id={booking_id}\n"
        f"Рейс: {ride_date}  {ride_direction}\n"
        f"Звідки: {from_city}\n"
        f"Куди: {to_city}\n"
        f"ПІБ: {name}\n"
        f"Телефон: {phone}\n"
        f"Місць: {seats}\n\n"
        "За добу до виїзду ми з вами зв'яжемося для підтвердження та нагадування."
    )
    await message.answer(msg)
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
                BotCommand(command="avtopark", description="Переглянути автопарк"),  # додано
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
    # Якщо передали id як аргумент — показати деталі одразу
    if len(parts) >= 2:
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
        bookings = db.query(Booking).filter(Booking.ride_id == ride_id).all()
        lines = [f"Рейс {ride.id}: {ride.date} {ride.direction}\nМісць: {ride.seats_total}, вільно: {ride.seats_free}\n"]
        if not bookings:
            lines.append("Броней: 0")
        else:
            lines.append(f"Броней: {len(bookings)}")
            for b in bookings:
                lines.append(
                    f"- id={b.id} | {b.name} | тел: {b.phone} | місць: {b.seats} | {b.from_city or '-'} -> {b.to_city or '-'}"
                    + (f" | примітка: {b.comment}" if b.comment else "")
                )
        await message.answer("\n".join(lines))
        db.close()
        return

    # Якщо id не вказано — показати список рейсів для вибору
    db = SessionLocal()
    rides = db.query(Ride).order_by(Ride.date).all()
    if not rides:
        await message.answer("Немає рейсів")
        db.close()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{r.date} {r.direction} ({r.seats_free} вільно)", callback_data=f"ride_stats_select:{r.id}")]
        for r in rides
    ])
    await message.answer("Оберіть рейс для перегляду детальної інформації:", reply_markup=kb)
    db.close()


@dp.callback_query(lambda c: c.data and c.data.startswith("ride_stats_select:"))
async def ride_stats_select(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if not is_manager(uid):
        await callback.answer("Тільки менеджер може виконувати цю дію", show_alert=True)
        return
    ride_id = int(callback.data.split(":", 1)[1])
    db = SessionLocal()
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        await callback.answer("Рейс не знайдено")
        db.close()
        return
    bookings = db.query(Booking).filter(Booking.ride_id == ride_id).all()
    lines = [f"Рейс {ride.id}: {ride.date} {ride.direction}\nМісць: {ride.seats_total}, вільно: {ride.seats_free}\n"]
    if not bookings:
        lines.append("Броней: 0")
    else:
        lines.append(f"Броней: {len(bookings)}")
        for b in bookings:
            lines.append(
                f"- id={b.id} | {b.name} | тел: {b.phone} | місць: {b.seats} | {b.from_city or '-'} -> {b.to_city or '-'}"
                + (f" | примітка: {b.comment}" if b.comment else "")
            )
    await callback.message.answer("\n".join(lines))
    db.close()
    await callback.answer()


# Обробник для перегляду автопарку — читає фото з папки "media" у корені проекту
@dp.message(Command("автопарк"))
async def show_fleet(message: types.Message):
    images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
    if not os.path.isdir(images_dir):
        await message.answer(f"Папка з фото автопарку не знайдена: {images_dir}")
        return

    files = [
        os.path.join(images_dir, f)
        for f in sorted(os.listdir(images_dir))
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
    ]
    if not files:
        await message.answer("Поки немає фото автопарку.")
        return

    # Надсилаємо файли по одному (надійно для локальних шляхів)
    for idx, fp in enumerate(files):
        caption = "Наш автопарк — фото салону/бусу" if idx == 0 else None
        try:
            file = types.FSInputFile(fp)
            await bot.send_photo(chat_id=message.chat.id, photo=file, caption=caption)
        except Exception as e:
            await message.answer(f"Не вдалось надіслати {os.path.basename(fp)}: {e}")

    await message.answer("Якщо потрібно — зверніться за деталями по конкретному бусу.")


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
