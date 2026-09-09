from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

import models, schemas, notify, storage
from database import get_db
from auth import get_current_user, oauth2_scheme, require_driver, require_driver_webapp

router = APIRouter(prefix="/api/driver", tags=["driver"])


async def current_driver(
    x_telegram_init_data: Optional[str] = Header(None),
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Drivers open the Mini App from Telegram; admins use their dashboard login."""
    if x_telegram_init_data:
        return await require_driver_webapp(x_telegram_init_data, db)
    user = await get_current_user(token, db)
    if user.role not in ("admin", "driver"):
        raise HTTPException(status_code=403, detail="Driver access required")
    return user


def _owned_ride(db: Session, ride_id: int, user: models.User) -> models.Ride:
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if user.role == "driver" and ride.driver_id != user.id:
        raise HTTPException(status_code=403, detail="Not your ride")
    return ride


@router.get("/rides", response_model=List[schemas.RideOut])
def my_rides(db: Session = Depends(get_db), user: models.User = Depends(require_driver)):
    return (
        db.query(models.Ride)
        .filter(models.Ride.driver_id == user.id)
        .order_by(models.Ride.date)
        .all()
    )


@router.get("/me")
async def me(user: models.User = Depends(current_driver), db: Session = Depends(get_db)):
    today = date.today()
    rides = (
        db.query(models.Ride)
        .filter(models.Ride.driver_id == user.id, models.Ride.date >= today)
        .order_by(models.Ride.date)
        .all()
    )
    return {
        "driver": schemas.UserOut.model_validate(user),
        "rides": [schemas.RideOut.model_validate(r) for r in rides],
    }


def _booking_point(booking: models.Booking, kind: str) -> dict:
    stop = booking.from_stop if kind == "pickup" else booking.to_stop
    address = booking.from_address if kind == "pickup" else booking.to_address
    return {
        "kind":     kind,
        "entity":   "booking",
        "id":       booking.id,
        "title":    booking.name,
        "phone":    booking.phone,
        "city":     stop.city if stop else None,
        "address":  address,
        "detail":   f"{booking.seats} місць" + (f" · {booking.comment}" if booking.comment else ""),
        "status":   booking.pickup_status,
        "cash_collected": booking.cash_collected,
        "photos":   [],
    }


def _parcel_point(parcel: models.Parcel, kind: str) -> dict:
    return {
        "kind":     kind,
        "entity":   "parcel",
        "id":       parcel.id,
        "title":    f"{parcel.tracking_number} · {parcel.sender if kind == 'pickup' else parcel.receiver}",
        "phone":    parcel.sender_phone if kind == "pickup" else parcel.receiver_phone,
        "city":     None,
        "address":  parcel.sender_address if kind == "pickup" else (parcel.receiver_address or parcel.np_office),
        "detail":   parcel.description or "",
        "status":   parcel.status,
        "cash_collected": parcel.cash_collected,
        "price":    parcel.price,
        "photos":   [p.filename for p in parcel.photos],
    }


@router.get("/rides/{ride_id}/manifest")
async def manifest(
    ride_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_driver),
):
    """Everything the driver does today, in the order they drive it."""
    ride = _owned_ride(db, ride_id, user)
    stop_order = {stop.id: stop.order for stop in ride.route.stops}

    bookings = [b for b in ride.bookings if b.status == "confirmed"]
    parcels = db.query(models.Parcel).filter(models.Parcel.ride_id == ride_id).all()

    pickups = sorted(
        (b for b in bookings if b.from_stop_id),
        key=lambda b: stop_order.get(b.from_stop_id, 0),
    )
    dropoffs = sorted(
        (b for b in bookings if b.to_stop_id),
        key=lambda b: stop_order.get(b.to_stop_id, 0),
    )

    points = (
        [_booking_point(b, "pickup") for b in pickups]
        + [_parcel_point(p, "pickup") for p in parcels if p.status == "accepted"]
        + [_parcel_point(p, "delivery") for p in parcels if p.status != "accepted"]
        + [_booking_point(b, "dropoff") for b in dropoffs]
    )

    expected = sum((ride.price or 0) * b.seats for b in bookings) + sum(p.price or 0 for p in parcels)
    collected = (
        sum(b.cash_collected or 0 for b in bookings)
        + sum(p.cash_collected or 0 for p in parcels)
    )

    return {
        "ride":   schemas.RideOut.model_validate(ride),
        "route":  schemas.RouteOut.model_validate(ride.route),
        "points": points,
        "cash":   {"expected": expected, "collected": collected},
    }


@router.post("/rides/{ride_id}/start")
async def start_ride(
    ride_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_driver),
):
    """Driver taps 'виїхав' — every passenger with Telegram gets an ETA message."""
    ride = _owned_ride(db, ride_id, user)
    if ride.status == "cancelled":
        raise HTTPException(status_code=400, detail="Ride is cancelled")

    notified = notify.notify_ride_departed(db, ride)
    return {"ok": True, "notified": notified, "status": ride.status}


@router.post("/rides/{ride_id}/finish")
async def finish_ride(
    ride_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_driver),
):
    ride = _owned_ride(db, ride_id, user)
    ride.status = "completed"
    db.commit()
    return {"ok": True, "status": ride.status}


@router.post("/bookings/{booking_id}", response_model=schemas.BookingOut)
async def update_booking_on_the_road(
    booking_id: int,
    body: schemas.DriverBookingUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_driver),
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    _owned_ride(db, booking.ride_id, user)

    if body.pickup_status is not None:
        if body.pickup_status not in {"waiting", "picked_up", "no_show", "dropped_off"}:
            raise HTTPException(status_code=400, detail="Invalid pickup status")
        booking.pickup_status = body.pickup_status
    if body.cash_collected is not None:
        booking.cash_collected = body.cash_collected

    db.commit()
    db.refresh(booking)
    return booking


@router.post("/parcels/{parcel_id}", response_model=schemas.ParcelOut)
async def update_parcel_on_the_road(
    parcel_id: int,
    body: schemas.DriverParcelUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_driver),
):
    parcel = db.query(models.Parcel).filter(models.Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    if parcel.ride_id:
        _owned_ride(db, parcel.ride_id, user)

    if body.cash_collected is not None:
        parcel.cash_collected = body.cash_collected

    if body.status is not None:
        if body.status not in notify.PARCEL_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        status_changed = parcel.status != body.status
        parcel.status = body.status
        if body.status == "delivered":
            parcel.delivered_at = datetime.utcnow()
        db.commit()
        if status_changed:
            notify.notify_parcel_status(db, parcel)
    else:
        db.commit()

    db.refresh(parcel)
    return parcel


@router.post("/parcels/{parcel_id}/photo", response_model=schemas.ParcelPhotoOut)
async def parcel_handover_photo(
    parcel_id: int,
    kind: str = Query("delivery", pattern="^(intake|delivery)$"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_driver),
):
    """Proof of handover, taken at the door."""
    parcel = db.query(models.Parcel).filter(models.Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    if parcel.ride_id:
        _owned_ride(db, parcel.ride_id, user)

    photo = models.ParcelPhoto(
        parcel_id=parcel.id, filename=storage.save_parcel_photo(file), kind=kind
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@router.patch("/rides/{ride_id}/stop/{stop_id}")
def update_stop_position(
    ride_id: int,
    stop_id: int,
    lat: float,
    lng: float,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_driver),
):
    """Driver can update lat/lng of a stop (drag on map)."""
    stop = db.query(models.Stop).filter(models.Stop.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    stop.lat = lat
    stop.lng = lng
    db.commit()
    return {"ok": True, "lat": lat, "lng": lng}
