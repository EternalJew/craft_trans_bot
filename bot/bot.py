import os
import asyncio
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.types import (
    BotCommand, BotCommandScopeDefault,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_BASE       = os.getenv("API_BASE", "http://localhost:8000")
BOT_API_KEY    = os.getenv("BOT_API_KEY", "bot-secret-key")

bot     = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)

HEADERS = {"X-Bot-Key": BOT_API_KEY}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def api_get(path: str, params: dict = None):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_BASE}{path}", params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()


async def api_post(path: str, data: dict):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_BASE}{path}", json=data, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()


async def api_patch(path: str, data: dict):
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{API_BASE}{path}", json=data, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()


async def api_delete(path: str):
    async with httpx.AsyncClient() as c:
        r = await c.delete(f"{API_BASE}{path}", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()


# ── FSM States ────────────────────────────────────────────────────────────────

class BookingStates(StatesGroup):
    choosing_ride  = State()
    choosing_from  = State()
    choosing_to    = State()
    phone          = State()
    name           = State()
    seats          = State()
    comment        = State()


class CancelBookingStates(StatesGroup):
    await_phone = State()


class EditBookingStates(StatesGroup):
    await_phone = State()
    new_seats   = State()
    new_comment = State()


class ViewBookingStates(StatesGroup):
    await_phone = State()


class ParcelStates(StatesGroup):
    direction      = State()
    sender         = State()
    sender_phone   = State()
    receiver       = State()
    receiver_phone = State()
    np_office      = State()
    description    = State()


# ── Keyboards ─────────────────────────────────────────────────────────────────

def public_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='/rides')],
        [KeyboardButton(text='/book')],
        [KeyboardButton(text='/parcel')],
        [KeyboardButton(text='/my_bookings')],
        [KeyboardButton(text='/автопарк')],
        [KeyboardButton(text='/help')],
    ], resize_keyboard=True)


# ── Commands ──────────────────────────────────────────────────────────────────

@dp.message(Command("start", "help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Вітаємо у CraftTrans!\n\n"
        "/rides — переглянути рейси\n"
        "/book — забронювати місце\n"
        "/parcel — відправити посилку\n"
        "/my_bookings — мої бронювання\n"
        "/cancel_booking — скасувати бронювання\n"
        "/change_booking — змінити бронювання\n"
        "/автопарк — наш транспорт",
        reply_markup=public_kb()
    )


# ── /rides ────────────────────────────────────────────────────────────────────

@dp.message(Command("rides"))
async def cmd_rides(message: types.Message):
    try:
        rides = await api_get("/api/rides")
    except Exception:
        await message.answer("Не вдалося отримати список рейсів. Спробуйте пізніше.")
        return

    active = [r for r in rides if r["status"] == "active"]
    if not active:
        await message.answer("Наразі немає доступних рейсів")
        return

    lines = []
    for r in active:
        route_name = r.get("route", {}).get("name", "?")
        price = f"{r['price']} грн" if r.get("price") else "—"
        lines.append(
            f"🚐 {r['date']} | {route_name}\n"
            f"   Місць вільно: {r['seats_free']}/{r['seats_total']} | Ціна: {price}"
        )
    await message.answer("\n\n".join(lines))


# ── /book ─────────────────────────────────────────────────────────────────────

@dp.message(Command("book"))
async def cmd_book(message: types.Message, state: FSMContext):
    try:
        rides = await api_get("/api/rides")
    except Exception:
        await message.answer("Не вдалося завантажити рейси")
        return

    active = [r for r in rides if r["status"] == "active" and r["seats_free"] > 0]
    if not active:
        await message.answer("Немає доступних рейсів для бронювання")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{r['date']} {r['route']['name']} ({r['seats_free']} вільно)",
            callback_data=f"book_ride:{r['id']}"
        )]
        for r in active
    ])
    await state.set_state(BookingStates.choosing_ride)
    await message.answer("Оберіть рейс:", reply_markup=kb)


@dp.callback_query(lambda c: c.data and c.data.startswith("book_ride:"))
async def book_select_ride(callback: types.CallbackQuery, state: FSMContext):
    ride_id = int(callback.data.split(":", 1)[1])
    await state.update_data(ride_id=ride_id)

    # Fetch stops for this ride's route
    try:
        ride = await api_get(f"/api/rides/{ride_id}")
        route = await api_get(f"/api/routes/{ride['route_id']}")
        stops = route.get("stops", [])
    except Exception:
        await callback.message.answer("Помилка завантаження зупинок")
        await callback.answer()
        return

    pickup_stops = [s for s in stops if s.get("pickup")]
    if not pickup_stops:
        await state.update_data(from_stop_id=None, from_stop_city="?")
        await state.set_state(BookingStates.choosing_to)
        await callback.message.answer("Куди їдете? Введіть місто:")
        await callback.answer()
        return

    await state.update_data(all_stops=stops)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📍 {s['city']} ({s['country']})", callback_data=f"from_stop:{s['id']}:{s['city']}")]
        for s in pickup_stops
    ])
    await state.set_state(BookingStates.choosing_from)
    await callback.message.answer("Звідки виїжджаєте?", reply_markup=kb)
    await callback.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("from_stop:"))
async def book_from_stop(callback: types.CallbackQuery, state: FSMContext):
    _, stop_id, city = callback.data.split(":", 2)
    await state.update_data(from_stop_id=int(stop_id), from_stop_city=city)

    data = await state.get_data()
    all_stops = data.get("all_stops", [])
    from_order = next((s["order"] for s in all_stops if s["id"] == int(stop_id)), 0)
    dropoff_stops = [s for s in all_stops if s.get("dropoff") and s["order"] > from_order]

    if not dropoff_stops:
        await state.update_data(to_stop_id=None, to_stop_city="?")
        await state.set_state(BookingStates.phone)
        await callback.message.answer("Введіть ваш номер телефону:")
        await callback.answer()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📍 {s['city']} ({s['country']})", callback_data=f"to_stop:{s['id']}:{s['city']}")]
        for s in dropoff_stops
    ])
    await state.set_state(BookingStates.choosing_to)
    await callback.message.answer("Куди їдете?", reply_markup=kb)
    await callback.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("to_stop:"))
async def book_to_stop(callback: types.CallbackQuery, state: FSMContext):
    _, stop_id, city = callback.data.split(":", 2)
    await state.update_data(to_stop_id=int(stop_id), to_stop_city=city)
    await state.set_state(BookingStates.phone)
    await callback.message.answer("Введіть ваш номер телефону:")
    await callback.answer()


@dp.message(StateFilter(BookingStates.phone))
async def booking_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await state.set_state(BookingStates.name)
    await message.answer("Введіть ваше ПІБ:")


@dp.message(StateFilter(BookingStates.name))
async def booking_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(BookingStates.seats)
    await message.answer("Скільки місць бронюєте?")


@dp.message(StateFilter(BookingStates.seats))
async def booking_seats(message: types.Message, state: FSMContext):
    try:
        seats = int(message.text.strip())
    except ValueError:
        await message.answer("Введіть ціле число")
        return
    await state.update_data(seats=seats)
    await state.set_state(BookingStates.comment)
    await message.answer("Коментар (або '-' щоб пропустити):")


@dp.message(StateFilter(BookingStates.comment))
async def booking_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    if comment == '-':
        comment = None

    data = await state.get_data()
    payload = {
        "ride_id":      data["ride_id"],
        "name":         data["name"],
        "phone":        data["phone"],
        "seats":        data["seats"],
        "from_stop_id": data.get("from_stop_id"),
        "to_stop_id":   data.get("to_stop_id"),
        "comment":      comment,
    }

    try:
        booking = await api_post("/api/bookings", payload)
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Помилка бронювання")
        await message.answer(f"Помилка: {detail}")
        await state.clear()
        return

    from_city = data.get("from_stop_city", "?")
    to_city   = data.get("to_stop_city",   "?")
    await message.answer(
        f"Бронювання підтверджено! id={booking['id']}\n"
        f"ПІБ: {data['name']}\nТелефон: {data['phone']}\n"
        f"Маршрут: {from_city} → {to_city}\n"
        f"Місць: {data['seats']}\n\n"
        "За добу до виїзду ми вам зателефонуємо."
    )
    await state.clear()


# ── /my_bookings ──────────────────────────────────────────────────────────────

@dp.message(Command("my_bookings"))
async def cmd_my_bookings(message: types.Message, state: FSMContext):
    await state.set_state(ViewBookingStates.await_phone)
    await message.answer("Введіть ваш телефон для пошуку бронювань:")


@dp.message(StateFilter(ViewBookingStates.await_phone))
async def my_bookings_list(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    try:
        bookings = await api_get("/api/bookings", params={"phone": phone})
    except Exception:
        await message.answer("Помилка завантаження")
        await state.clear()
        return

    if not bookings:
        await message.answer("Бронювань за цим номером не знайдено.")
        await state.clear()
        return

    lines = []
    for b in bookings:
        from_c = b.get("from_stop", {}) or {}
        to_c   = b.get("to_stop",   {}) or {}
        lines.append(
            f"id={b['id']} | {from_c.get('city', '?')} → {to_c.get('city', '?')} | "
            f"{b['seats']} місць | {b['status']}"
        )
    await message.answer("\n".join(lines))
    await state.clear()


# ── /cancel_booking ───────────────────────────────────────────────────────────

@dp.message(Command("cancel_booking"))
async def cmd_cancel_booking(message: types.Message, state: FSMContext):
    await state.set_state(CancelBookingStates.await_phone)
    await message.answer("Введіть телефон для пошуку бронювань:")


@dp.message(StateFilter(CancelBookingStates.await_phone))
async def cancel_find(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    try:
        bookings = await api_get("/api/bookings", params={"phone": phone})
    except Exception:
        await message.answer("Помилка")
        await state.clear()
        return

    active = [b for b in bookings if b["status"] == "confirmed"]
    if not active:
        await message.answer("Активних бронювань не знайдено.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"id={b['id']} | {(b.get('from_stop') or {}).get('city', '?')} → {(b.get('to_stop') or {}).get('city', '?')} | {b['seats']} місць",
            callback_data=f"cancel_sel:{b['id']}"
        )]
        for b in active
    ])
    await message.answer("Оберіть бронювання для скасування:", reply_markup=kb)
    await state.clear()


@dp.callback_query(lambda c: c.data and c.data.startswith("cancel_sel:"))
async def cancel_select(callback: types.CallbackQuery):
    booking_id = int(callback.data.split(":", 1)[1])
    try:
        await api_delete(f"/api/bookings/{booking_id}")
        await callback.message.answer(f"Бронювання id={booking_id} скасовано.")
    except Exception:
        await callback.message.answer("Помилка скасування")
    await callback.answer()


# ── /change_booking ───────────────────────────────────────────────────────────

@dp.message(Command("change_booking"))
async def cmd_change_booking(message: types.Message, state: FSMContext):
    await state.set_state(EditBookingStates.await_phone)
    await message.answer("Введіть телефон для пошуку бронювань:")


@dp.message(StateFilter(EditBookingStates.await_phone))
async def change_find(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    try:
        bookings = await api_get("/api/bookings", params={"phone": phone})
    except Exception:
        await message.answer("Помилка")
        await state.clear()
        return

    active = [b for b in bookings if b["status"] == "confirmed"]
    if not active:
        await message.answer("Активних бронювань не знайдено.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"id={b['id']} | {(b.get('from_stop') or {}).get('city','?')} → {(b.get('to_stop') or {}).get('city','?')} | {b['seats']} місць",
            callback_data=f"change_sel:{b['id']}"
        )]
        for b in active
    ])
    await message.answer("Оберіть бронювання для зміни:", reply_markup=kb)
    await state.clear()


@dp.callback_query(lambda c: c.data and c.data.startswith("change_sel:"))
async def change_select(callback: types.CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split(":", 1)[1])
    await state.update_data(edit_booking_id=booking_id)
    await state.set_state(EditBookingStates.new_seats)
    await callback.message.answer("Нова кількість місць:")
    await callback.answer()


@dp.message(StateFilter(EditBookingStates.new_seats))
async def change_new_seats(message: types.Message, state: FSMContext):
    try:
        new_seats = int(message.text.strip())
    except ValueError:
        await message.answer("Введіть ціле число")
        return
    await state.update_data(new_seats=new_seats)
    await state.set_state(EditBookingStates.new_comment)
    await message.answer("Новий коментар (або '-' залишити без змін):")


@dp.message(StateFilter(EditBookingStates.new_comment))
async def change_new_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    data    = await state.get_data()
    booking_id = data["edit_booking_id"]
    new_seats  = data["new_seats"]

    payload = {"seats": new_seats}
    if comment != '-':
        payload["comment"] = comment

    try:
        await api_patch(f"/api/bookings/{booking_id}", payload)
        await message.answer(f"Бронювання id={booking_id} оновлено.")
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Помилка")
        await message.answer(f"Помилка: {detail}")

    await state.clear()


# ── /parcel ───────────────────────────────────────────────────────────────────

@dp.message(Command("parcel"))
async def cmd_parcel(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇦 → 🇨🇿  Україна → Чехія", callback_data="parcel_dir:UA->CZ")],
        [InlineKeyboardButton(text="🇨🇿 → 🇺🇦  Чехія → Україна", callback_data="parcel_dir:CZ->UA")],
    ])
    await state.set_state(ParcelStates.direction)
    await message.answer("Оберіть напрямок посилки:", reply_markup=kb)


@dp.callback_query(lambda c: c.data and c.data.startswith("parcel_dir:"))
async def parcel_direction(callback: types.CallbackQuery, state: FSMContext):
    direction = callback.data.split(":", 1)[1]
    await state.update_data(direction=direction)
    await state.set_state(ParcelStates.sender)
    await callback.message.answer("ПІБ відправника:")
    await callback.answer()


@dp.message(StateFilter(ParcelStates.sender))
async def parcel_sender(message: types.Message, state: FSMContext):
    await state.update_data(sender=message.text.strip())
    await state.set_state(ParcelStates.sender_phone)
    await message.answer("Телефон відправника:")


@dp.message(StateFilter(ParcelStates.sender_phone))
async def parcel_sender_phone(message: types.Message, state: FSMContext):
    await state.update_data(sender_phone=message.text.strip())
    await state.set_state(ParcelStates.receiver)
    await message.answer("ПІБ отримувача:")


@dp.message(StateFilter(ParcelStates.receiver))
async def parcel_receiver(message: types.Message, state: FSMContext):
    await state.update_data(receiver=message.text.strip())
    await state.set_state(ParcelStates.receiver_phone)
    await message.answer("Телефон отримувача:")


@dp.message(StateFilter(ParcelStates.receiver_phone))
async def parcel_receiver_phone(message: types.Message, state: FSMContext):
    await state.update_data(receiver_phone=message.text.strip())
    await state.set_state(ParcelStates.np_office)
    await message.answer("Відділення Нової Пошти (місто і номер):")


@dp.message(StateFilter(ParcelStates.np_office))
async def parcel_np_office(message: types.Message, state: FSMContext):
    await state.update_data(np_office=message.text.strip())
    await state.set_state(ParcelStates.description)
    await message.answer("Опис посилки (або '-' щоб пропустити):")


@dp.message(StateFilter(ParcelStates.description))
async def parcel_description(message: types.Message, state: FSMContext):
    desc = message.text.strip()
    if desc == '-':
        desc = None

    data = await state.get_data()
    payload = {
        "direction":      data["direction"],
        "sender":         data["sender"],
        "sender_phone":   data["sender_phone"],
        "receiver":       data["receiver"],
        "receiver_phone": data["receiver_phone"],
        "np_office":      data["np_office"],
        "description":    desc,
    }

    try:
        parcel = await api_post("/api/parcels", payload)
        await message.answer(
            f"Посилку зареєстровано! id={parcel['id']}\n"
            f"Напрямок: {parcel['direction']}\n"
            f"Відправник: {parcel['sender']} ({parcel['sender_phone']})\n"
            f"Отримувач: {parcel['receiver']} ({parcel['receiver_phone']})\n"
            f"НП офіс: {parcel['np_office']}"
        )
    except Exception:
        await message.answer("Помилка реєстрації посилки. Спробуйте пізніше.")

    await state.clear()


# ── /автопарк ─────────────────────────────────────────────────────────────────

@dp.message(Command("автопарк"))
async def cmd_fleet(message: types.Message):
    media_dir = os.path.join(os.path.dirname(__file__), '..', 'media')
    if not os.path.isdir(media_dir):
        await message.answer("Фото автопарку відсутні.")
        return
    files = sorted([
        os.path.join(media_dir, f)
        for f in os.listdir(media_dir)
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
    ])
    if not files:
        await message.answer("Поки немає фото автопарку.")
        return
    for idx, fp in enumerate(files):
        caption = "Наш автопарк" if idx == 0 else None
        try:
            await bot.send_photo(chat_id=message.chat.id, photo=types.FSInputFile(fp), caption=caption)
        except Exception as e:
            await message.answer(f"Не вдалось надіслати фото: {e}")


# ── /cancel (FSM reset) ───────────────────────────────────────────────────────

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Немає активної операції")
        return
    await state.clear()
    await message.answer("Операцію скасовано")


# ── Default ───────────────────────────────────────────────────────────────────

@dp.message()
async def default_response(message: types.Message):
    await message.answer("Використайте меню або /help")


# ── Entry point ───────────────────────────────────────────────────────────────

async def set_commands():
    await bot.set_my_commands([
        BotCommand(command="rides",          description="Переглянути рейси"),
        BotCommand(command="book",           description="Забронювати місце"),
        BotCommand(command="parcel",         description="Відправити посилку"),
        BotCommand(command="my_bookings",    description="Мої бронювання"),
        BotCommand(command="cancel_booking", description="Скасувати бронювання"),
        BotCommand(command="change_booking", description="Змінити бронювання"),
        BotCommand(command="автопарк",       description="Наш транспорт"),
        BotCommand(command="help",           description="Довідка"),
    ], scope=BotCommandScopeDefault())


async def main():
    await set_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
