from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from database import get_db
from auth import get_current_manager

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.get("", response_model=List[schemas.BookingOut])
def list_bookings(
    phone: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Booking)
    if phone:
        q = q.filter(models.Booking.phone == phone)
    return q.order_by(models.Booking.created_at.desc()).all()


@router.post("", response_model=schemas.BookingOut)
def create_booking(body: schemas.BookingCreate, db: Session = Depends(get_db)):
    ride = db.query(models.Ride).filter(models.Ride.id == body.ride_id).with_for_update().first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if ride.status == "cancelled":
        raise HTTPException(status_code=400, detail="Ride is cancelled")
    if ride.seats_free < body.seats:
        raise HTTPException(status_code=400, detail=f"Not enough seats. Available: {ride.seats_free}")

    booking = models.Booking(
        ride_id=body.ride_id,
        name=body.name,
        phone=body.phone,
        seats=body.seats,
        from_stop_id=body.from_stop_id,
        to_stop_id=body.to_stop_id,
        comment=body.comment,
        status="confirmed",
    )
    db.add(booking)
    ride.seats_free -= body.seats
    db.commit()
    db.refresh(booking)
    return booking


@router.patch("/{booking_id}", response_model=schemas.BookingOut)
def update_booking(
    booking_id: int,
    body: schemas.BookingUpdate,
    db: Session = Depends(get_db),
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

    db.commit()
    db.refresh(booking)
    return booking


@router.delete("/{booking_id}")
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ride = db.query(models.Ride).filter(models.Ride.id == booking.ride_id).first()
    if ride:
        ride.seats_free += booking.seats

    db.delete(booking)
    db.commit()
    return {"ok": True}
