import os
import asyncio
from datetime import date
import httpx
from html import escape as esc

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.types import (
    BotCommand, BotCommandScopeDefault, MenuButtonCommands,
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
NOTIFY_POLL_SECONDS = int(os.getenv("NOTIFY_POLL_SECONDS", "20"))
WEBAPP_URL     = os.getenv("WEBAPP_URL", "").rstrip("/")

# parse_mode stays off by default: most messages interpolate names, addresses and
# comments people typed, and a stray "<" would make Telegram reject the send.
# Messages that want formatting pass parse_mode=HTML and escape what they embed.
bot     = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(link_preview_is_disabled=True),
)
HTML = ParseMode.HTML
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


async def api_upload(path: str, content: bytes, filename: str):
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{API_BASE}{path}",
            files={"file": (filename, content, "image/jpeg")},
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "нд"]
MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня",
          "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]


def fmt_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{WEEKDAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]}"


PARCEL_STATUS_LABELS = {
    "accepted":         "прийнято",
    "in_transit":       "в дорозі",
    "border_crossed":   "перетнула кордон",
    "out_for_delivery": "сьогодні доставка",
    "delivered":        "доставлено",
}


# ── FSM States ────────────────────────────────────────────────────────────────

class BookingStates(StatesGroup):
    choosing_ride  = State()
    choosing_from  = State()
    typing_from    = State()
    from_address   = State()
    choosing_to    = State()
    typing_to      = State()
    to_address     = State()
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
    direction        = State()
    sender           = State()
    sender_phone     = State()
    sender_address   = State()
    receiver         = State()
    receiver_phone   = State()
    delivery_kind    = State()
    delivery_target  = State()
    description      = State()
    photo            = State()


class TrackStates(StatesGroup):
    await_number = State()


# ── Keyboards ─────────────────────────────────────────────────────────────────

# Menu labels double as filters, so the buttons read like words rather than
# slash commands while still routing to the same handlers.
BTN_BOOK   = "🎫 Забронювати місце"
BTN_RIDES  = "🗓 Найближчі рейси"
BTN_PARCEL = "📦 Відправити посилку"
BTN_TRACK  = "🔎 Де моя посилка"
BTN_MINE   = "📋 Мої бронювання"
BTN_FLEET  = "🚌 Наш автопарк"


def public_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BOOK)],
            [KeyboardButton(text=BTN_RIDES),  KeyboardButton(text=BTN_MINE)],
            [KeyboardButton(text=BTN_PARCEL), KeyboardButton(text=BTN_TRACK)],
            [KeyboardButton(text=BTN_FLEET)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Оберіть дію або напишіть /help",
    )


def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поділитися номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def link_contact(phone: str, tg_user: types.User):
    """Remember phone → telegram_id so we can reach this passenger later."""
    try:
        await api_post("/api/notifications/contacts", {
            "phone":       phone,
            "telegram_id": tg_user.id,
            "full_name":   tg_user.full_name,
        })
    except Exception:
        pass


# ── Commands ──────────────────────────────────────────────────────────────────

@dp.message(Command("start", "help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "<b>craft plus</b> — пасажири та посилки Україна ⇄ Чехія\n"
        "<i>Забираємо з-під дому й довозимо за адресою.</i>\n\n"
        "🚐 З України — <b>вівторок</b> і <b>п'ятниця</b>\n"
        "🚐 З Чехії — <b>четвер</b> і <b>неділя</b>\n\n"
        "Оберіть дію на клавіатурі нижче.\n\n"
        "<blockquote>Змінити чи скасувати бронювання: "
        "/change_booking, /cancel_booking</blockquote>",
        parse_mode=HTML,
        reply_markup=public_kb(),
    )


@dp.message(Command("whoami"))
async def cmd_whoami(message: types.Message):
    """Setup helper: the id that goes into OWNER_TELEGRAM_IDS or a driver's account."""
    await message.answer(
        f"{esc(message.from_user.full_name)}\n"
        f"Ваш Telegram id: <code>{message.from_user.id}</code>",
        parse_mode=HTML,
    )


# ── /rides ────────────────────────────────────────────────────────────────────

@dp.message(Command("rides"))
@dp.message(F.text == BTN_RIDES)
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

    # No seat counts: the paper book holds passengers this database never sees,
    # so any number shown here would be a promise we cannot keep.
    lines = [
        f"🚐 <b>{fmt_date(r['date'])}</b> · {esc(r.get('route', {}).get('name', '?'))}"
        for r in active[:12]
    ]
    await message.answer(
        "<b>Найближчі виїзди</b>\n\n" + "\n".join(lines) +
        "\n\n<i>Місце підтверджуємо дзвінком.</i>",
        parse_mode=HTML,
    )


# ── /book ─────────────────────────────────────────────────────────────────────

@dp.message(Command("book"))
@dp.message(F.text == BTN_BOOK)
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
            text=f"{fmt_date(r['date'])} · {r['route']['name']}",
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

    await state.update_data(all_stops=stops)
    await state.set_state(BookingStates.choosing_from)
    await callback.message.answer(
        "Звідки вас забрати?",
        reply_markup=_city_kb([s["city"] for s in stops if s.get("pickup")], "from"),
    )
    await callback.answer()


def _city_kb(cities: list, side: str) -> InlineKeyboardMarkup:
    """Suggested cities, two per row, plus a way to name a town that is not listed."""
    rows = [
        [InlineKeyboardButton(text=c, callback_data=f"{side}_city:{c}") for c in cities[i:i + 2]]
        for i in range(0, len(cities), 2)
    ]
    rows.append([InlineKeyboardButton(text="✏️ Інше місто або село", callback_data=f"{side}_city_other")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _ask_from_address(message: types.Message, state: FSMContext, city: str):
    await state.set_state(BookingStates.from_address)
    await message.answer(
        f"Вкажіть адресу подачі — {city}, вулиця й будинок.\n"
        "Якщо зручніше сісти на загальній зупинці — напишіть '-'."
    )


async def _ask_to_address(message: types.Message, state: FSMContext, city: str):
    await state.set_state(BookingStates.to_address)
    await message.answer(
        f"Вкажіть адресу висадки — {city}, вулиця й будинок.\n"
        "Якщо висадка на загальній зупинці — напишіть '-'."
    )


@dp.callback_query(lambda c: c.data and c.data.startswith("from_city:"))
async def book_from_city(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split(":", 1)[1]
    await state.update_data(from_city=city)
    await _ask_from_address(callback.message, state, city)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "from_city_other")
async def book_from_city_other(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.typing_from)
    await callback.message.answer("Напишіть назву вашого міста або села:")
    await callback.answer()


@dp.message(StateFilter(BookingStates.typing_from))
async def book_from_city_typed(message: types.Message, state: FSMContext):
    city = message.text.strip()
    await state.update_data(from_city=city)
    await _ask_from_address(message, state, city)


async def _ask_dropoff(message: types.Message, state: FSMContext):
    data = await state.get_data()
    stops = data.get("all_stops", [])
    await state.set_state(BookingStates.choosing_to)
    await message.answer(
        "Куди вас довезти?",
        reply_markup=_city_kb([s["city"] for s in stops if s.get("dropoff")], "to"),
    )


@dp.message(StateFilter(BookingStates.from_address))
async def book_from_address(message: types.Message, state: FSMContext):
    address = message.text.strip()
    await state.update_data(from_address=None if address == '-' else address)
    await _ask_dropoff(message, state)


@dp.callback_query(lambda c: c.data and c.data.startswith("to_city:"))
async def book_to_city(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split(":", 1)[1]
    await state.update_data(to_city=city)
    await _ask_to_address(callback.message, state, city)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "to_city_other")
async def book_to_city_other(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.typing_to)
    await callback.message.answer("Напишіть назву міста або села, куди їдете:")
    await callback.answer()


@dp.message(StateFilter(BookingStates.typing_to))
async def book_to_city_typed(message: types.Message, state: FSMContext):
    city = message.text.strip()
    await state.update_data(to_city=city)
    await _ask_to_address(message, state, city)


@dp.message(StateFilter(BookingStates.to_address))
async def book_to_address(message: types.Message, state: FSMContext):
    address = message.text.strip()
    await state.update_data(to_address=None if address == '-' else address)
    await state.set_state(BookingStates.phone)
    await message.answer("Ваш номер телефону:", reply_markup=phone_kb())


@dp.message(StateFilter(BookingStates.phone))
async def booking_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if not phone:
        await message.answer("Надішліть номер телефону текстом або кнопкою нижче:", reply_markup=phone_kb())
        return
    await state.update_data(phone=phone)
    await link_contact(phone, message.from_user)
    await state.set_state(BookingStates.name)

    suggested = message.from_user.full_name
    await message.answer(
        f"Введіть ваше ПІБ (або надішліть '-' щоб залишити «{suggested}»):",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@dp.message(StateFilter(BookingStates.name))
async def booking_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if name == '-':
        name = message.from_user.full_name
    await state.update_data(name=name)
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
        "from_city":    data["from_city"],
        "to_city":      data["to_city"],
        "from_address": data.get("from_address"),
        "to_address":   data.get("to_address"),
        "comment":      comment,
        "telegram_id":  message.from_user.id,
        "source":       "bot",
    }

    try:
        booking = await api_post("/api/bookings", payload)
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Помилка бронювання")
        await message.answer(f"Помилка: {detail}")
        await state.clear()
        return

    text = (
        f"Бронювання підтверджено! id={booking['id']}\n"
        f"ПІБ: {data['name']}\nТелефон: {data['phone']}\n"
        f"Маршрут: {data['from_city']} → {data['to_city']}\n"
    )
    if data.get("from_address"):
        text += f"Подача: {data['from_address']}\n"
    if data.get("to_address"):
        text += f"Висадка: {data['to_address']}\n"
    text += (
        f"Місць: {data['seats']}\n\n"
        "За добу до виїзду надішлемо нагадування з часом подачі, "
        "а в день виїзду — повідомлення коли водій вирушить."
    )
    await message.answer(text, reply_markup=public_kb())
    await state.clear()


# ── /my_bookings ──────────────────────────────────────────────────────────────

@dp.message(Command("my_bookings"))
@dp.message(F.text == BTN_MINE)
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

    lines = [
        f"id={b['id']} | {b['from_city']} → {b['to_city']} | {b['seats']} місць | {b['status']}"
        for b in bookings
    ]
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
            text=f"id={b['id']} | {b['from_city']} → {b['to_city']} | {b['seats']} місць",
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
            text=f"id={b['id']} | {b['from_city']} → {b['to_city']} | {b['seats']} місць",
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
@dp.message(F.text == BTN_PARCEL)
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
    await message.answer("Телефон відправника:", reply_markup=phone_kb())


@dp.message(StateFilter(ParcelStates.sender_phone))
async def parcel_sender_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if not phone:
        await message.answer("Надішліть номер текстом або кнопкою нижче:", reply_markup=phone_kb())
        return
    await state.update_data(sender_phone=phone)
    await link_contact(phone, message.from_user)
    await state.set_state(ParcelStates.sender_address)
    await message.answer(
        "Адреса, звідки забрати посилку (місто, вулиця, будинок):",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@dp.message(StateFilter(ParcelStates.sender_address))
async def parcel_sender_address(message: types.Message, state: FSMContext):
    await state.update_data(sender_address=message.text.strip())
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Доставка на адресу", callback_data="parcel_delivery:address")],
        [InlineKeyboardButton(text="📦 Відділення Нової Пошти", callback_data="parcel_delivery:np")],
    ])
    await state.set_state(ParcelStates.delivery_kind)
    await message.answer("Як доставити посилку?", reply_markup=kb)


@dp.callback_query(lambda c: c.data and c.data.startswith("parcel_delivery:"))
async def parcel_delivery_kind(callback: types.CallbackQuery, state: FSMContext):
    kind = callback.data.split(":", 1)[1]
    await state.update_data(delivery_kind=kind)
    await state.set_state(ParcelStates.delivery_target)
    prompt = ("Адреса доставки (місто, вулиця, будинок):" if kind == "address"
              else "Відділення Нової Пошти (місто і номер):")
    await callback.message.answer(prompt)
    await callback.answer()


@dp.message(StateFilter(ParcelStates.delivery_target))
async def parcel_delivery_target(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target = message.text.strip()
    if data.get("delivery_kind") == "address":
        await state.update_data(receiver_address=target)
    else:
        await state.update_data(np_office=target)
    await state.set_state(ParcelStates.description)
    await message.answer("Опис посилки — що всередині (або '-' щоб пропустити):")


@dp.message(StateFilter(ParcelStates.description))
async def parcel_description(message: types.Message, state: FSMContext):
    desc = message.text.strip()
    await state.update_data(description=None if desc == '-' else desc)
    await state.set_state(ParcelStates.photo)
    await message.answer(
        "Надішліть фото посилки — воно збережеться в системі як підтвердження.\n"
        "Якщо фото немає, напишіть '-'."
    )


async def _register_parcel(message: types.Message, state: FSMContext, photo_bytes: bytes = None):
    data = await state.get_data()
    payload = {
        "direction":          data["direction"],
        "sender":             data["sender"],
        "sender_phone":       data["sender_phone"],
        "sender_address":     data.get("sender_address"),
        "receiver":           data["receiver"],
        "receiver_phone":     data["receiver_phone"],
        "receiver_address":   data.get("receiver_address"),
        "np_office":          data.get("np_office"),
        "description":        data.get("description"),
        "sender_telegram_id": message.from_user.id,
    }

    try:
        parcel = await api_post("/api/parcels", payload)
    except Exception:
        await message.answer("Помилка реєстрації посилки. Спробуйте пізніше.")
        await state.clear()
        return

    photo_note = ""
    if photo_bytes:
        try:
            await api_upload(f"/api/parcels/{parcel['id']}/photos", photo_bytes, "parcel.jpg")
            photo_note = "Фото збережено.\n"
        except Exception:
            photo_note = "Фото не вдалося зберегти, менеджер додасть його вручну.\n"

    destination = parcel.get("receiver_address") or parcel.get("np_office") or "—"
    await message.answer(
        f"Посилку прийнято!\n\n"
        f"Трек-номер: {parcel['tracking_number']}\n"
        f"Напрямок: {parcel['direction']}\n"
        f"Забрати: {parcel.get('sender_address') or '—'}\n"
        f"Доставка: {destination}\n"
        f"Отримувач: {parcel['receiver']} ({parcel['receiver_phone']})\n"
        f"{photo_note}\n"
        f"Статус можна перевірити командою /track",
        reply_markup=public_kb(),
    )
    await state.clear()


@dp.message(StateFilter(ParcelStates.photo), lambda m: m.photo)
async def parcel_photo(message: types.Message, state: FSMContext):
    buffer = await bot.download(message.photo[-1].file_id)
    await _register_parcel(message, state, buffer.read())


@dp.message(StateFilter(ParcelStates.photo))
async def parcel_no_photo(message: types.Message, state: FSMContext):
    if (message.text or "").strip() != '-':
        await message.answer("Надішліть фото посилки або напишіть '-' щоб пропустити.")
        return
    await _register_parcel(message, state)


# ── /track ────────────────────────────────────────────────────────────────────

@dp.message(Command("track"))
@dp.message(F.text == BTN_TRACK)
async def cmd_track(message: types.Message, state: FSMContext):
    await state.set_state(TrackStates.await_number)
    await message.answer("Введіть трек-номер посилки (наприклад CT-7K4M2Q):")


@dp.message(StateFilter(TrackStates.await_number))
async def track_lookup(message: types.Message, state: FSMContext):
    number = (message.text or "").strip().upper()
    try:
        parcel = await api_get(f"/api/parcels/track/{number}")
    except Exception:
        await message.answer("Посилку з таким номером не знайдено. Перевірте номер.")
        await state.clear()
        return

    await message.answer(
        f"Посилка {parcel['tracking_number']}\n\n"
        f"Статус: {PARCEL_STATUS_LABELS.get(parcel['status'], parcel['status'])}\n"
        f"Напрямок: {parcel['direction']}\n"
        f"Прийнято: {parcel['created_at'][:10]}"
    )
    await state.clear()


# ── /driver ───────────────────────────────────────────────────────────────────

@dp.message(Command("driver"))
async def cmd_driver(message: types.Message):
    if not WEBAPP_URL:
        await message.answer("Водійський застосунок ще не налаштований (WEBAPP_URL).")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="🚐 Мій маніфест",
        web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/driver"),
    )]])
    await message.answer("Відкрийте маніфест на сьогодні:", reply_markup=kb)


# ── /fleet ─────────────────────────────────────────────────────────────────

@dp.message(Command("fleet"))
@dp.message(F.text == BTN_FLEET)
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

async def configure_bot():
    """Commands, profile texts and the menu button — everything Telegram shows
    around the conversation. /whoami and /driver stay unlisted on purpose."""
    await bot.set_my_commands([
        BotCommand(command="book",           description="🎫 Забронювати місце"),
        BotCommand(command="rides",          description="🗓 Найближчі рейси"),
        BotCommand(command="parcel",         description="📦 Відправити посилку"),
        BotCommand(command="track",          description="🔎 Де моя посилка"),
        BotCommand(command="my_bookings",    description="📋 Мої бронювання"),
        BotCommand(command="change_booking", description="✏️ Змінити бронювання"),
        BotCommand(command="cancel_booking", description="❌ Скасувати бронювання"),
        BotCommand(command="fleet",          description="🚌 Наш автопарк"),
        BotCommand(command="help",           description="ℹ️ Довідка"),
    ], scope=BotCommandScopeDefault())

    # Shown in an empty chat, before the first message.
    await bot.set_my_description(
        "craft plus — пасажирські перевезення та посилки Україна ⇄ Чехія.\n\n"
        "Забираємо з-під дому й довозимо за адресою. Мікроавтобуси на 8 місць.\n"
        "З України: вівторок, п'ятниця. З Чехії: четвер, неділя.\n\n"
        "Натисніть «Почати», щоб забронювати місце або відправити посилку."
    )
    # Shown under the bot name in its profile and in search.
    await bot.set_my_short_description(
        "Пасажири та посилки Україна ⇄ Чехія. Бронювання за хвилину."
    )
    await bot.set_my_name("craft plus")
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


def notification_kb(note: dict):
    """Some notifications carry an action; most are just text."""
    if note.get("kind") == "book_entry" and note.get("entity_id"):
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="✅ Записав у книжку",
            callback_data=f"book_written:{note['entity_id']}",
        )]])
    return None


@dp.callback_query(lambda c: c.data and c.data.startswith("book_written:"))
async def mark_book_written(callback: types.CallbackQuery):
    booking_id = int(callback.data.split(":", 1)[1])
    try:
        await api_patch(f"/api/bookings/{booking_id}/book", {})
    except Exception:
        await callback.answer("Не вдалося зберегти. Спробуйте ще раз.", show_alert=True)
        return

    # Keep the details, drop the button, and show it is done.
    text = callback.message.text.replace("ЗАПИСАТИ В КНИЖКУ", "✅ ЗАПИСАНО В КНИЖКУ", 1)
    await callback.message.edit_text(text)
    await callback.answer("Позначено як записане")


async def deliver_notifications():
    """Poll the API outbox and deliver queued messages to passengers."""
    while True:
        try:
            pending = await api_get("/api/notifications/pending")
        except Exception:
            await asyncio.sleep(NOTIFY_POLL_SECONDS)
            continue

        for note in pending:
            try:
                await bot.send_message(
                    chat_id=note["telegram_id"],
                    text=note["text"],
                    reply_markup=notification_kb(note),
                )
                ack = {"status": "sent"}
            except Exception as e:
                ack = {"status": "failed", "error": str(e)[:500]}
            try:
                await api_post(f"/api/notifications/{note['id']}/ack", ack)
            except Exception:
                pass
            await asyncio.sleep(0.05)   # stay under Telegram's rate limit

        await asyncio.sleep(NOTIFY_POLL_SECONDS)


async def main():
    await configure_bot()
    asyncio.create_task(deliver_notifications())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
