from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

import models
import notify
import schemas
from database import get_db
from auth import require_staff_or_bot

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.get("", response_model=List[schemas.BookingOut])
def list_bookings(
    phone: Optional[str] = Query(None),
    book_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_staff_or_bot),
):
    q = db.query(models.Booking)
    if book_status:
        q = q.filter(models.Booking.book_status == book_status)
    rows = q.order_by(models.Booking.created_at.desc()).all()

    if phone:
        # People write the same number as +380…, 380… or 0… — compare the part
        # that is actually the same.
        wanted = notify.normalize_phone(phone)
        rows = [b for b in rows if notify.normalize_phone(b.phone) == wanted]
    return rows


@router.post("", response_model=schemas.BookingOut)
def create_booking(body: schemas.BookingCreate, db: Session = Depends(get_db)):
    ride = db.query(models.Ride).filter(models.Ride.id == body.ride_id).with_for_update().first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride.status == "cancelled":
        raise HTTPException(status_code=400, detail="Ride is cancelled")
    if ride.seats_free < body.seats:
        raise HTTPException(status_code=400, detail=f"Not enough seats. Available: {ride.seats_free}")

    # Cities are free text, so a village we have never heard of passes. But a
    # city we do know must be on the right end of this ride: boarding in
    # Славута on a Чехія → Україна departure is a mistake, not a request.
    pickups  = {s.city.casefold() for s in ride.route.stops if s.pickup}
    dropoffs = {s.city.casefold() for s in ride.route.stops if s.dropoff}
    from_key, to_key = body.from_city.strip().casefold(), body.to_city.strip().casefold()
    if from_key in dropoffs and from_key not in pickups:
        raise HTTPException(
            status_code=400,
            detail=f"Рейс {ride.route.name}: посадка в {body.from_city.strip()} неможлива — "
                   f"це місто прибуття. Оберіть інший напрямок.",
        )
    if to_key in pickups and to_key not in dropoffs:
        raise HTTPException(
            status_code=400,
            detail=f"Рейс {ride.route.name}: висадка в {body.to_city.strip()} неможлива — "
                   f"це місто відправлення. Оберіть інший напрямок.",
        )

    booking = models.Booking(
        ride_id=body.ride_id,
        name=body.name,
        phone=body.phone,
        seats=body.seats,
        from_city=body.from_city.strip(),
        to_city=body.to_city.strip(),
        from_address=body.from_address,
        to_address=body.to_address,
        comment=body.comment,
        telegram_id=body.telegram_id,
        source=body.source,
        status="confirmed",
    )
    db.add(booking)
    ride.seats_free -= body.seats
    db.flush()
    notify.notify_owner_new_booking(db, booking)
    db.commit()
    db.refresh(booking)
    return booking


@router.patch("/{booking_id}", response_model=schemas.BookingOut)
def update_booking(
    booking_id: int,
    body: schemas.BookingUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_staff_or_bot),
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if body.seats is not None:
        ride = db.query(models.Ride).filter(models.Ride.id == booking.ride_id).with_for_update().first()
        available = ride.seats_free + booking.seats
        if body.seats > available:
            raise HTTPException(status_code=400, detail=f"Not enough seats. Max available: {available}")
        ride.seats_free = available - body.seats
        booking.seats = body.seats

    if body.comment is not None:
        booking.comment = body.comment
    if body.from_address is not None:
        booking.from_address = body.from_address
    if body.to_address is not None:
        booking.to_address = body.to_address
    if body.pickup_time is not None:
        booking.pickup_time = body.pickup_time

    db.commit()
    db.refresh(booking)
    return booking


@router.patch("/{booking_id}/book", response_model=schemas.BookingOut)
def mark_written_in_book(
    booking_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_staff_or_bot),
):
    """The owner confirms this booking is now in the paper book."""
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.book_status = "written"
    booking.book_written_at = datetime.utcnow()
    db.commit()
    db.refresh(booking)
    return booking


@router.delete("/{booking_id}")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_staff_or_bot),
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ride = db.query(models.Ride).filter(models.Ride.id == booking.ride_id).first()
    if ride:
        ride.seats_free += booking.seats

    db.delete(booking)
    db.commit()
    return {"ok": True}
