"""The paper book, photographed: read a page, review it, import it.

Rows that come from the book are already in the book, so they enter as
book_status="written" and nobody is notified to copy them across. A row whose
phone already has a booking on that ride is the reconciliation case — the
passenger booked online and the owner copied them in — so it marks the
existing booking written rather than creating a twin.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
import notify
import ocr
import schedule
import schemas
from auth import require_admin
from database import get_db

router = APIRouter(prefix="/api/book", tags=["book"])

MAX_UPLOAD = 12 * 1024 * 1024


def _guess_ride_date(day: Optional[int], month: Optional[int]) -> Optional[date]:
    """The page prints day and month only. Assume this year unless that would be
    months in the past — then it is a page from the coming year."""
    if not day or not month:
        return None
    today = date.today()
    try:
        guess = date(today.year, month, day)
    except ValueError:
        return None
    if guess < today - timedelta(days=60):
        guess = date(today.year + 1, month, day)
    return guess


def _direction_for(day: date) -> Optional[str]:
    for direction, weekdays in schedule.DEPARTURE_WEEKDAYS.items():
        if day.weekday() in weekdays:
            return direction
    return None


class ScanResult(BaseModel):
    page: ocr.BookPage
    ride_date: Optional[date]
    direction: Optional[str]
    ride: Optional[schemas.RideOut]


@router.post("/scan", response_model=ScanResult)
async def scan_page(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Потрібне фото у форматі JPEG, PNG або WebP")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Фото завелике — до 12 МБ")

    known = [s.city for s in db.query(models.Stop).all()]
    page = ocr.read_page(data, media_type=file.content_type,
                         known_cities=sorted(set(known) | set(ocr.FREQUENT_CITIES)))

    ride_date = _guess_ride_date(page.day, page.month)
    direction = _direction_for(ride_date) if ride_date else None
    ride = None
    if ride_date and direction:
        ride = (
            db.query(models.Ride)
            .join(models.Route)
            .filter(models.Ride.date == ride_date, models.Route.direction == direction)
            .first()
        )
    return ScanResult(page=page, ride_date=ride_date, direction=direction, ride=ride)


class ImportRow(BaseModel):
    from_city: str
    to_city: str
    phone: Optional[str] = None
    seats: int = 1
    note: Optional[str] = None
    price: Optional[str] = None


class ImportRequest(BaseModel):
    ride_id: int
    rows: List[ImportRow]


class ImportResult(BaseModel):
    created: int
    matched: int
    skipped: List[str]


@router.post("/import", response_model=ImportResult)
def import_rows(body: ImportRequest, db: Session = Depends(get_db), _=Depends(require_admin)):
    ride = db.query(models.Ride).filter(models.Ride.id == body.ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Рейс не знайдено")

    existing = {
        notify.normalize_phone(b.phone): b
        for b in ride.bookings if b.status == "confirmed" and b.phone
    }

    created = matched = 0
    skipped: List[str] = []
    now = datetime.utcnow()

    for row in body.rows:
        if not row.from_city.strip() or not row.to_city.strip():
            skipped.append(f"{row.from_city} → {row.to_city}: без міста")
            continue
        key = notify.normalize_phone(row.phone or "")
        if key and key in existing:
            found = existing[key]
            if found.book_status != "written":
                found.book_status = "written"
                found.book_written_at = now
            matched += 1
            continue

        comment = " · ".join(x for x in [row.price, row.note] if x) or None
        booking = models.Booking(
            ride_id=ride.id,
            name=row.phone or "—",          # the book keeps no names; the phone is the handle
            phone=row.phone or "",
            seats=max(row.seats, 1),
            from_city=row.from_city.strip(),
            to_city=row.to_city.strip(),
            comment=comment,
            source="book",
            status="confirmed",
            book_status="written",
            book_written_at=now,
        )
        db.add(booking)
        ride.seats_free = max(ride.seats_free - booking.seats, 0)
        if key:
            existing[key] = booking
        created += 1

    db.commit()
    return ImportResult(created=created, matched=matched, skipped=skipped)
