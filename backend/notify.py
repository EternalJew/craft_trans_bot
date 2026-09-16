"""Building and queueing Telegram notifications.

The API never talks to Telegram directly — it writes rows into the
``notifications`` outbox and the bot process delivers them.
"""
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

import models


def normalize_phone(phone: str) -> str:
    """Last 9 digits — enough to match both UA (+380 XX XXX XX XX) and CZ numbers."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:]


def resolve_telegram_id(db: Session, booking: models.Booking) -> Optional[int]:
    if booking.telegram_id:
        return booking.telegram_id
    contact = (
        db.query(models.TelegramContact)
        .filter(models.TelegramContact.phone == normalize_phone(booking.phone))
        .first()
    )
    return contact.telegram_id if contact else None


def enqueue(db: Session, telegram_id: int, text: str, kind: str,
            entity_id: Optional[int] = None) -> models.Notification:
    note = models.Notification(telegram_id=telegram_id, text=text, kind=kind, entity_id=entity_id)
    db.add(note)
    return note


def owner_telegram_ids() -> list[int]:
    """Whoever keeps the paper book, plus anyone who should see the same queue."""
    raw = os.getenv("OWNER_TELEGRAM_IDS", "")
    return [int(part) for part in re.split(r"[,\s]+", raw) if part.strip().lstrip("-").isdigit()]


SOURCE_LABELS = {
    "web":    "сайт",
    "bot":    "Telegram-бот",
    "admin":  "дзвінок",
    "driver": "водій",
    "book":   "зошит",
}


def book_entry_text(booking: models.Booking, ride: models.Ride) -> str:
    """What the owner needs in front of him to copy a booking into the book."""
    when = ride.date.strftime("%d.%m")
    weekday = ["пн", "вт", "ср", "чт", "пт", "сб", "нд"][ride.date.weekday()]
    lines = [
        "ЗАПИСАТИ В КНИЖКУ",
        "",
        f"{weekday}, {when} · {ride.route.name}",
        f"{booking.name} — {booking.phone}",
        f"{booking.from_city} → {booking.to_city}",
        f"Місць: {booking.seats}",
    ]
    if booking.from_address:
        lines.append(f"Подача: {booking.from_address}")
    if booking.to_address:
        lines.append(f"Висадка: {booking.to_address}")
    if booking.comment:
        lines.append(f"Коментар: {booking.comment}")
    lines.append("")
    lines.append(f"Джерело: {SOURCE_LABELS.get(booking.source, booking.source)} · №{booking.id}")
    return "\n".join(lines)


def notify_owner_new_booking(db: Session, booking: models.Booking) -> int:
    """Every booking, whatever channel it came from, lands in the owner's Telegram."""
    ride = db.query(models.Ride).filter(models.Ride.id == booking.ride_id).first()
    if not ride:
        return 0
    text = book_entry_text(booking, ride)
    queued = 0
    for telegram_id in owner_telegram_ids():
        enqueue(db, telegram_id, text, "book_entry", entity_id=booking.id)
        queued += 1
    return queued


def _fmt_time(value) -> Optional[str]:
    return value.strftime("%H:%M") if value else None


def _driver_line(ride: models.Ride) -> str:
    if not ride.driver:
        return ""
    name = ride.driver.full_name or ride.driver.username
    phone = f", {ride.driver.phone}" if ride.driver.phone else ""
    return f"Водій: {name}{phone}\n"


def day_before_text(booking: models.Booking, ride: models.Ride) -> str:
    time_str = _fmt_time(booking.pickup_time) or _fmt_time(ride.departure_time)
    when = f" о {time_str}" if time_str else ""
    text = (
        f"Нагадування про поїздку\n\n"
        f"Завтра, {ride.date.strftime('%d.%m')}{when}\n"
        f"Маршрут: {booking.from_city} → {booking.to_city}\n"
    )
    if booking.from_address:
        text += f"Подача: {booking.from_address}\n"
    text += _driver_line(ride)
    text += f"Місць: {booking.seats}\n\nБудь ласка, будьте готові за 10 хвилин до часу подачі."
    return text


def departure_text(booking: models.Booking, ride: models.Ride) -> str:
    time_str = _fmt_time(booking.pickup_time)
    eta = f"Орієнтовно у вас о {time_str}.\n" if time_str else ""
    text = f"Водій виїхав.\n{eta}"
    text += _driver_line(ride)
    if booking.from_address:
        text += f"Подача: {booking.from_address}\n"
    return text.rstrip()


def generate_day_before_reminders(db: Session, target: Optional[date] = None) -> int:
    """Queue reminders for every confirmed booking on tomorrow's rides."""
    target = target or (date.today() + timedelta(days=1))
    rides = (
        db.query(models.Ride)
        .filter(models.Ride.date == target, models.Ride.status == "active")
        .all()
    )

    queued = 0
    for ride in rides:
        for booking in ride.bookings:
            if booking.status != "confirmed" or booking.reminded_day_before:
                continue
            telegram_id = resolve_telegram_id(db, booking)
            if not telegram_id:
                continue
            enqueue(db, telegram_id, day_before_text(booking, ride), "day_before")
            booking.reminded_day_before = True
            queued += 1

    db.commit()
    return queued


PARCEL_STATUS_TEXT = {
    "accepted":         "Посилку прийнято.",
    "in_transit":       "Посилка в дорозі.",
    "border_crossed":   "Посилка перетнула кордон.",
    "out_for_delivery": "Посилка сьогодні на доставці.",
    "delivered":        "Посилку доставлено.",
}

PARCEL_STATUSES = list(PARCEL_STATUS_TEXT)


def parcel_status_text(parcel: models.Parcel, for_receiver: bool) -> str:
    text = f"Посилка {parcel.tracking_number}\n\n{PARCEL_STATUS_TEXT[parcel.status]}\n"
    if for_receiver:
        text += f"Відправник: {parcel.sender}\n"
        destination = parcel.receiver_address or parcel.np_office
        if destination and parcel.status in ("out_for_delivery", "delivered"):
            text += f"Адреса: {destination}\n"
    else:
        text += f"Отримувач: {parcel.receiver}\n"
    return text.rstrip()


def notify_parcel_status(db: Session, parcel: models.Parcel) -> int:
    """Tell both sides about a status change; whoever we can reach on Telegram."""
    recipients = []
    if parcel.sender_telegram_id:
        recipients.append((parcel.sender_telegram_id, False))
    else:
        sender_contact = (
            db.query(models.TelegramContact)
            .filter(models.TelegramContact.phone == normalize_phone(parcel.sender_phone))
            .first()
        )
        if sender_contact:
            recipients.append((sender_contact.telegram_id, False))

    receiver_contact = (
        db.query(models.TelegramContact)
        .filter(models.TelegramContact.phone == normalize_phone(parcel.receiver_phone))
        .first()
    )
    if receiver_contact:
        recipients.append((receiver_contact.telegram_id, True))

    for telegram_id, for_receiver in recipients:
        enqueue(db, telegram_id, parcel_status_text(parcel, for_receiver), "parcel_status")

    db.commit()
    return len(recipients)


def notify_ride_departed(db: Session, ride: models.Ride) -> int:
    queued = 0
    for booking in ride.bookings:
        if booking.status != "confirmed" or booking.reminded_departure:
            continue
        telegram_id = resolve_telegram_id(db, booking)
        if not telegram_id:
            continue
        enqueue(db, telegram_id, departure_text(booking, ride), "departure")
        booking.reminded_departure = True
        queued += 1

    ride.status = "in_progress"
    ride.started_at = datetime.utcnow()
    db.commit()
    return queued
