"""Building and queueing Telegram notifications.

The API never talks to Telegram directly — it writes rows into the
``notifications`` outbox and the bot process delivers them.
"""
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


def enqueue(db: Session, telegram_id: int, text: str, kind: str) -> models.Notification:
    note = models.Notification(telegram_id=telegram_id, text=text, kind=kind)
    db.add(note)
    return note


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
    from_city = booking.from_stop.city if booking.from_stop else "—"
    to_city = booking.to_stop.city if booking.to_stop else "—"

    text = (
        f"Нагадування про поїздку\n\n"
        f"Завтра, {ride.date.strftime('%d.%m')}{when}\n"
        f"Маршрут: {from_city} → {to_city}\n"
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
