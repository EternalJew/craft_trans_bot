from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db
from auth import require_driver

router = APIRouter(prefix="/api/driver", tags=["driver"])


@router.get("/rides", response_model=List[schemas.RideOut])
def my_rides(db: Session = Depends(get_db), user: models.User = Depends(require_driver)):
    return (
        db.query(models.Ride)
        .filter(models.Ride.driver_id == user.id)
        .order_by(models.Ride.date)
        .all()
    )


@router.get("/rides/{ride_id}")
def my_ride_detail(
    ride_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_driver),
):
    ride = db.query(models.Ride).filter(models.Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    # Admins can see any ride; drivers only their own
    if user.role == "driver" and ride.driver_id != user.id:
        raise HTTPException(status_code=403, detail="Not your ride")

    bookings = db.query(models.Booking).filter(models.Booking.ride_id == ride_id).all()
    parcels  = db.query(models.Parcel).filter(
        (models.Parcel.ride_id == ride_id) |
        (models.Parcel.direction == ride.route.direction)
    ).all()

    return {
        "ride":     schemas.RideOut.model_validate(ride),
        "route":    schemas.RouteOut.model_validate(ride.route),
        "bookings": [schemas.BookingOut.model_validate(b) for b in bookings],
        "parcels":  [schemas.ParcelOut.model_validate(p) for p in parcels],
    }


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
