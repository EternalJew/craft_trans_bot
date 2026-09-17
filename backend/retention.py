"""How long a passenger's details stay with us.

Names, phones and home addresses are needed to run the trip and to answer a
claim afterwards — not forever. Passengers travel to the EU, so this is GDPR
territory: keep the personal fields for RETENTION_MONTHS, then blank them and
leave the row (city, seats, date) for the statistics.
"""
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

import models

RETENTION_MONTHS = int(os.getenv("RETENTION_MONTHS", "12"))
ANONYMIZED = "—"


def cutoff(now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) - timedelta(days=30 * RETENTION_MONTHS)


def anonymize_old_records(db: Session, now: datetime | None = None) -> tuple[int, int]:
    """Blank the personal fields on bookings and parcels older than the
    retention period. Returns (bookings, parcels) touched."""
    before = cutoff(now)

    bookings = (
        db.query(models.Booking)
        .filter(models.Booking.created_at < before, models.Booking.name != ANONYMIZED)
        .all()
    )
    for b in bookings:
        b.name = ANONYMIZED
        b.phone = ANONYMIZED
        b.from_address = None
        b.to_address = None
        b.comment = None
        b.telegram_id = None

    parcels = (
        db.query(models.Parcel)
        .filter(models.Parcel.created_at < before, models.Parcel.sender != ANONYMIZED)
        .all()
    )
    for p in parcels:
        p.sender = ANONYMIZED
        p.sender_phone = ANONYMIZED
        p.sender_address = None
        p.receiver = ANONYMIZED
        p.receiver_phone = ANONYMIZED
        p.receiver_address = None
        p.np_office = None
        p.sender_telegram_id = None

    # the phone→Telegram map is only useful while we still have the bookings
    db.query(models.TelegramContact).filter(models.TelegramContact.created_at < before).delete()

    db.commit()
    return len(bookings), len(parcels)
