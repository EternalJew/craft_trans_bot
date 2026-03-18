from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date as date_type

from database import get_db
from auth import get_current_user
import models, schemas

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


# ── Vehicles ──────────────────────────────────────────────────────────────────

@router.get("", response_model=List[schemas.VehicleOut])
def list_vehicles(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.Vehicle).all()


@router.post("", response_model=schemas.VehicleOut)
def create_vehicle(data: schemas.VehicleCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    v = models.Vehicle(**data.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.patch("/{vehicle_id}", response_model=schemas.VehicleOut)
def update_vehicle(vehicle_id: int, data: schemas.VehicleUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    v = db.get(models.Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    for k, val in data.model_dump(exclude_none=True).items():
        setattr(v, k, val)
    db.commit()
    db.refresh(v)
    return v


@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    v = db.get(models.Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    db.delete(v)
    db.commit()
    return {"ok": True}


# ── Maintenance records ────────────────────────────────────────────────────────

@router.get("/{vehicle_id}/maintenance", response_model=List[schemas.MaintenanceRecordOut])
def list_maintenance(vehicle_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    v = db.get(models.Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    return (
        db.query(models.MaintenanceRecord)
        .filter_by(vehicle_id=vehicle_id)
        .order_by(models.MaintenanceRecord.mileage.desc())
        .all()
    )


@router.post("/{vehicle_id}/maintenance", response_model=schemas.MaintenanceRecordOut)
def add_maintenance(vehicle_id: int, data: schemas.MaintenanceRecordCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    v = db.get(models.Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    rec = models.MaintenanceRecord(vehicle_id=vehicle_id, **data.model_dump())
    db.add(rec)
    # Update current mileage if this record is newer
    if data.mileage > v.mileage_current:
        v.mileage_current = data.mileage
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/maintenance/{record_id}")
def delete_maintenance(record_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rec = db.get(models.MaintenanceRecord, record_id)
    if not rec:
        raise HTTPException(404, "Record not found")
    db.delete(rec)
    db.commit()
    return {"ok": True}
