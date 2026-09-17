from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import get_db
from auth import require_admin, require_staff_or_bot

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
def ride_bookings(ride_id: int, db: Session = Depends(get_db), _=Depends(require_staff_or_bot)):
    """The passenger list — names and phones, so never without a login or the bot key."""
    if not db.query(models.Ride).filter(models.Ride.id == ride_id).first():
        raise HTTPException(status_code=404, detail="Ride not found")
    return db.query(models.Booking).filter(models.Booking.ride_id == ride_id).all()


# ── Splitting a day between vans ──────────────────────────────────────────────

from pydantic import BaseModel
import notify
import split


class SplitOut(BaseModel):
    capacity: int
    vans: List[List[int]]      # booking ids per van, in route order
    drivers: List[Optional[int]]   # driver user id per van, same order
    saved: bool                # True if this is the stored split, not a fresh proposal
    suggested_vans: int        # what the owner's rule of thumb says for this many people
    total_seats: int


class SplitIn(BaseModel):
    vans: List[List[int]]
    drivers: List[Optional[int]] = []


def _drivers_for(ride: models.Ride, count: int) -> List[Optional[int]]:
    by_no = {v.van_no: v.driver_id for v in ride.vans}
    return [by_no.get(i + 1) for i in range(count)]


@router.get("/{ride_id}/split", response_model=SplitOut)
def ride_split(
    ride_id: int,
    vans: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """The saved split if there is one, otherwise a proposal. Pass ?vans=N to
    get a fresh proposal for exactly N vans, ignoring what is saved."""
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    confirmed = [b for b in ride.bookings if b.status == "confirmed"]
    total = sum(b.seats for b in confirmed)
    suggested = split.suggest_van_count(total)

    if vans is None and any(b.van_no for b in confirmed):
        by_van = {}
        for b in confirmed:
            by_van.setdefault(b.van_no or 0, []).append(b.id)
        # van 0 = not yet assigned; keep it last so it is visible
        stored = [by_van[k] for k in sorted(by_van) if k] + ([by_van[0]] if 0 in by_van else [])
        return SplitOut(capacity=split.CAPACITY, vans=stored, drivers=_drivers_for(ride, len(stored)),
                        saved=True, suggested_vans=suggested, total_seats=total)

    passengers = [{"id": b.id, "from_city": b.from_city, "to_city": b.to_city, "seats": b.seats}
                  for b in confirmed]
    proposal = split.propose(passengers, ride.route.direction, n_vans=vans)
    return SplitOut(capacity=split.CAPACITY, vans=proposal, drivers=_drivers_for(ride, len(proposal)),
                    saved=False, suggested_vans=suggested, total_seats=total)


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

    # one RideVan per van, driver optional
    existing = {v.van_no: v for v in ride.vans}
    for van_no in range(1, len(body.vans) + 1):
        driver_id = body.drivers[van_no - 1] if van_no - 1 < len(body.drivers) else None
        if van_no in existing:
            existing[van_no].driver_id = driver_id
        else:
            db.add(models.RideVan(ride_id=ride.id, van_no=van_no, driver_id=driver_id))
    for van_no, v in existing.items():
        if van_no > len(body.vans):
            db.delete(v)
    db.flush()
    db.refresh(ride)

    # the drivers hear about it straight away — that is the point of assigning them
    notify.notify_ride_drivers(db, ride)
    db.commit()
    db.refresh(ride)
    total = sum(b.seats for b in own.values() if b.status == "confirmed")
    return SplitOut(capacity=split.CAPACITY, vans=body.vans, drivers=_drivers_for(ride, len(body.vans)),
                    saved=True, suggested_vans=split.suggest_van_count(total), total_seats=total)
