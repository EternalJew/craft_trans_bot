from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

import models, schemas, notify, storage
from database import get_db
from auth import require_admin, require_driver

router = APIRouter(prefix="/api/parcels", tags=["parcels"])


def _get(db: Session, parcel_id: int) -> models.Parcel:
    parcel = db.query(models.Parcel).filter(models.Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@router.get("", response_model=List[schemas.ParcelOut])
def list_parcels(
    status: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Parcel)
    if status:
        q = q.filter(models.Parcel.status == status)
    if phone:
        normalized = notify.normalize_phone(phone)
        q = q.filter(
            models.Parcel.sender_phone.contains(normalized)
            | models.Parcel.receiver_phone.contains(normalized)
        )
    return q.order_by(models.Parcel.created_at.desc()).all()


@router.post("", response_model=schemas.ParcelOut)
def create_parcel(body: schemas.ParcelCreate, db: Session = Depends(get_db)):
    if not body.receiver_address and not body.np_office:
        raise HTTPException(
            status_code=400,
            detail="Provide either a delivery address or a Nova Poshta office",
        )

    for _ in range(5):
        tracking_number = storage.generate_tracking_number()
        if not db.query(models.Parcel).filter(
            models.Parcel.tracking_number == tracking_number
        ).first():
            break
    else:
        raise HTTPException(status_code=500, detail="Could not allocate a tracking number")

    parcel = models.Parcel(
        **body.model_dump(), tracking_number=tracking_number, status="accepted"
    )
    db.add(parcel)
    db.commit()
    db.refresh(parcel)

    notify.notify_parcel_status(db, parcel)
    return parcel


@router.get("/track/{tracking_number}", response_model=schemas.ParcelOut)
def track(tracking_number: str, db: Session = Depends(get_db)):
    parcel = (
        db.query(models.Parcel)
        .filter(models.Parcel.tracking_number == tracking_number.strip().upper())
        .first()
    )
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@router.get("/{parcel_id}", response_model=schemas.ParcelOut)
def get_parcel(parcel_id: int, db: Session = Depends(get_db)):
    return _get(db, parcel_id)


@router.post("/{parcel_id}/photos", response_model=schemas.ParcelPhotoOut)
def add_photo(
    parcel_id: int,
    kind: str = Query("intake", pattern="^(intake|delivery)$"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    parcel = _get(db, parcel_id)
    photo = models.ParcelPhoto(
        parcel_id=parcel.id, filename=storage.save_parcel_photo(file), kind=kind
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@router.patch("/{parcel_id}/status", response_model=schemas.ParcelOut)
def update_parcel_status(
    parcel_id: int,
    body: schemas.ParcelStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_driver),
):
    parcel = _get(db, parcel_id)
    if body.status not in notify.PARCEL_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    if parcel.status == body.status:
        return parcel

    parcel.status = body.status
    if body.status == "delivered":
        parcel.delivered_at = datetime.utcnow()
    db.commit()
    db.refresh(parcel)

    notify.notify_parcel_status(db, parcel)
    return parcel


@router.patch("/{parcel_id}", response_model=schemas.ParcelOut)
def update_parcel(
    parcel_id: int,
    body: schemas.ParcelUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    parcel = _get(db, parcel_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(parcel, field, value)
    db.commit()
    db.refresh(parcel)
    return parcel


@router.delete("/{parcel_id}")
def delete_parcel(parcel_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    parcel = _get(db, parcel_id)
    for photo in parcel.photos:
        storage.delete_parcel_photo(photo.filename)
    db.delete(parcel)
    db.commit()
    return {"ok": True}
