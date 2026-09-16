from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import get_db
from auth import require_admin, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    return db.query(models.User).order_by(models.User.id).all()


@router.post("", response_model=schemas.UserOut)
def create_user(body: schemas.UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(models.User).filter(models.User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = models.User(
        username=body.username,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        phone=body.phone,
        role=body.role,
        telegram_id=body.telegram_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    body: schemas.UserUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"ok": True}


# ── Linking a driver's Telegram ───────────────────────────────────────────────

import os
import secrets
from pydantic import BaseModel
from auth import verify_bot_key


class InviteOut(BaseModel):
    code: str
    link: str


@router.post("/{user_id}/invite", response_model=InviteOut)
def invite_to_bot(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """A fresh one-time link. Tapping it in Telegram binds the driver's account
    to whoever tapped, so the admin never has to ask for a telegram_id."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.invite_code = secrets.token_urlsafe(9)
    db.commit()
    bot = os.getenv("BOT_USERNAME", "").lstrip("@")
    return InviteOut(code=user.invite_code, link=f"https://t.me/{bot}?start=drv_{user.invite_code}")


class ClaimIn(BaseModel):
    code: str
    telegram_id: int
    full_name: Optional[str] = None


@router.post("/claim-invite", response_model=schemas.UserOut)
def claim_invite(body: ClaimIn, db: Session = Depends(get_db), _=Depends(verify_bot_key)):
    user = db.query(models.User).filter(models.User.invite_code == body.code).first()
    if not user:
        raise HTTPException(status_code=404, detail="Запрошення не знайдено або вже використане")
    # the same Telegram account cannot be two drivers
    other = db.query(models.User).filter(models.User.telegram_id == body.telegram_id,
                                         models.User.id != user.id).first()
    if other:
        other.telegram_id = None
    user.telegram_id = body.telegram_id
    user.invite_code = None
    if body.full_name and not user.full_name:
        user.full_name = body.full_name
    db.commit()
    db.refresh(user)
    return user


@router.get("/by-telegram/{telegram_id}", response_model=schemas.UserOut)
def by_telegram(telegram_id: int, db: Session = Depends(get_db), _=Depends(verify_bot_key)):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Not a staff account")
    return user
