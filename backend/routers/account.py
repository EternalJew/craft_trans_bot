"""The signed-in user's own account: password and sessions."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models, schemas
from database import get_db
from auth import (
    create_access_token, get_current_user, hash_password, revoke_all_tokens, verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=schemas.UserMe)
def me(user: models.User = Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=schemas.Token)
def change_password(
    body: schemas.PasswordChange,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Sets a new password and signs out every other session. The token in
    the response is the one session that survives."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поточний пароль невірний")
    user.password_hash = hash_password(body.new_password)
    revoke_all_tokens(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user), "token_type": "bearer", "role": user.role}


@router.post("/logout-all")
def logout_all(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """For a session left open on someone else's computer."""
    revoke_all_tokens(user)
    db.commit()
    return {"ok": True}
