from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models, schemas, notify
from database import get_db
from auth import verify_bot_key, require_admin

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/pending", response_model=List[schemas.NotificationOut])
def pending(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _=Depends(verify_bot_key),
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.status == "pending")
        .order_by(models.Notification.created_at)
        .limit(limit)
        .all()
    )


@router.post("/{notification_id}/ack", response_model=schemas.NotificationOut)
def ack(
    notification_id: int,
    body: schemas.NotificationAck,
    db: Session = Depends(get_db),
    _=Depends(verify_bot_key),
):
    note = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Notification not found")
    if body.status not in {"sent", "failed"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    note.status = body.status
    note.sent_at = datetime.utcnow()
    note.error = body.error
    db.commit()
    db.refresh(note)
    return note


@router.post("/contacts", response_model=schemas.TelegramContactOut)
def upsert_contact(
    body: schemas.TelegramContactCreate,
    db: Session = Depends(get_db),
    _=Depends(verify_bot_key),
):
    """Bot registers phone → telegram_id so website bookings can be notified too."""
    phone = notify.normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phone")

    contact = db.query(models.TelegramContact).filter(models.TelegramContact.phone == phone).first()
    if contact:
        contact.telegram_id = body.telegram_id
        contact.full_name = body.full_name or contact.full_name
    else:
        contact = models.TelegramContact(
            phone=phone, telegram_id=body.telegram_id, full_name=body.full_name
        )
        db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/generate-reminders")
def generate_reminders(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Manual trigger — the same job the scheduler runs every morning."""
    return {"queued": notify.generate_day_before_reminders(db)}
