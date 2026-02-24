from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db
from auth import require_admin

router = APIRouter(prefix="/api/parcels", tags=["parcels"])


@router.get("", response_model=List[schemas.ParcelOut])
def list_parcels(db: Session = Depends(get_db)):
    return db.query(models.Parcel).order_by(models.Parcel.created_at.desc()).all()


@router.post("", response_model=schemas.ParcelOut)
def create_parcel(body: schemas.ParcelCreate, db: Session = Depends(get_db)):
    parcel = models.Parcel(**body.model_dump())
    db.add(parcel)
    db.commit()
    db.refresh(parcel)
    return parcel


@router.get("/{parcel_id}", response_model=schemas.ParcelOut)
def get_parcel(parcel_id: int, db: Session = Depends(get_db)):
    parcel = db.query(models.Parcel).filter(models.Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@router.patch("/{parcel_id}/status", response_model=schemas.ParcelOut)
def update_parcel_status(parcel_id: int, body: schemas.ParcelStatusUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    parcel = db.query(models.Parcel).filter(models.Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    if body.status not in {"pending", "in_transit", "delivered"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    parcel.status = body.status
    db.commit()
    db.refresh(parcel)
    return parcel


@router.delete("/{parcel_id}")
def delete_parcel(parcel_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    parcel = db.query(models.Parcel).filter(models.Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    db.delete(parcel)
    db.commit()
    return {"ok": True}
