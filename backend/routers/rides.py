from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import get_db
from auth import require_admin

router = APIRouter(prefix="/api/rides", tags=["rides"])


@router.get("", response_model=List[schemas.RideOut])
def list_rides(db: Session = Depends(get_db)):
    return db.query(models.Ride).order_by(models.Ride.date).all()


@router.post("", response_model=schemas.RideOut)
def create_ride(body: schemas.RideCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    route = db.query(models.Route).filter(models.Route.id == body.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    ride = models.Ride(
        route_id=body.route_id,
        date=body.date,
        seats_total=body.seats_total,
        seats_free=body.seats_total,
        vehicle=body.vehicle,
        price=body.price,
        status="active",
    )
    db.add(ride)
    db.commit()
    db.refresh(ride)
    return ride


@router.get("/{ride_id}", response_model=schemas.RideOut)
def get_ride(ride_id: int, db: Session = Depends(get_db)):
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return ride


@router.patch("/{ride_id}/assign-driver", response_model=schemas.RideOut)
def assign_driver(
    ride_id: int,
    driver_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    if driver_id is not None:
        driver = db.query(models.User).filter(models.User.id == driver_id, models.User.role == "driver").first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
    ride.driver_id = driver_id
    db.commit()
    db.refresh(ride)
    return ride


@router.delete("/{ride_id}")
def delete_ride(ride_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    db.delete(ride)
    db.commit()
    return {"ok": True}


@router.get("/{ride_id}/bookings", response_model=List[schemas.BookingOut])
def ride_bookings(ride_id: int, db: Session = Depends(get_db)):
    if not db.query(models.Ride).filter(models.Ride.id == ride_id).first():
        raise HTTPException(status_code=404, detail="Ride not found")
    return db.query(models.Booking).filter(models.Booking.ride_id == ride_id).all()


# ── Splitting a day between vans ──────────────────────────────────────────────

from pydantic import BaseModel
import split


class SplitOut(BaseModel):
    capacity: int
    vans: List[List[int]]      # booking ids per van, in route order
    saved: bool                # True if this is the stored split, not a fresh proposal


class SplitIn(BaseModel):
    vans: List[List[int]]


@router.get("/{ride_id}/split", response_model=SplitOut)
def ride_split(ride_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """The saved split if there is one, otherwise a proposal."""
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    confirmed = [b for b in ride.bookings if b.status == "confirmed"]

    if any(b.van_no for b in confirmed):
        by_van = {}
        for b in confirmed:
            by_van.setdefault(b.van_no or 0, []).append(b.id)
        # van 0 = not yet assigned; keep it last so it is visible
        vans = [by_van[k] for k in sorted(by_van) if k] + ([by_van[0]] if 0 in by_van else [])
        return SplitOut(capacity=split.CAPACITY, vans=vans, saved=True)

    passengers = [{"id": b.id, "from_city": b.from_city, "to_city": b.to_city, "seats": b.seats}
                  for b in confirmed]
    return SplitOut(capacity=split.CAPACITY,
                    vans=split.propose(passengers, ride.route.direction), saved=False)


@router.post("/{ride_id}/split", response_model=SplitOut)
def save_split(ride_id: int, body: SplitIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    own = {b.id: b for b in ride.bookings}
    for b in own.values():
        b.van_no = None
    for van_no, ids in enumerate(body.vans, start=1):
        for booking_id in ids:
            if booking_id in own:
                own[booking_id].van_no = van_no
    db.commit()
    return SplitOut(capacity=split.CAPACITY, vans=body.vans, saved=True)
