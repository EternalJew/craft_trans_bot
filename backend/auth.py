import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import parse_qsl

from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import TokenData

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")
ALGORITHM = "HS256"
# Long enough that the admin is not thrown out in the middle of a departure day.
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 30
BOT_API_KEY = os.getenv("BOT_API_KEY", "bot-secret-key")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
INIT_DATA_MAX_AGE_SECONDS = 24 * 3600

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-Bot-Key", auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def create_access_token(user: models.User, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode = {"sub": user.username, "ver": user.token_version, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def revoke_all_tokens(user: models.User) -> None:
    """Every token this user holds stops working; the caller commits."""
    user.token_version = (user.token_version or 1) + 1


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise exc
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise exc
        token_data = TokenData(username=username)
        version = payload.get("ver")
    except JWTError:
        raise exc
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None or version != user.token_version:
        raise exc
    return user


async def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_driver(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role not in ("admin", "driver"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver access required")
    return user


def parse_telegram_init_data(init_data: str) -> dict:
    """Verify the signature Telegram puts on Mini App init data.

    Telegram signs the parameters with a key derived from the bot token, so a
    valid signature proves the request really came from Telegram and names the
    user who opened the app.
    """
    if not TELEGRAM_TOKEN:
        raise HTTPException(status_code=500, detail="TELEGRAM_TOKEN is not configured")

    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing init data hash")

    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status_code=401, detail="Invalid init data signature")

    auth_date = int(fields.get("auth_date", 0))
    if time.time() - auth_date > INIT_DATA_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Init data expired, reopen the app")

    return json.loads(fields.get("user", "{}"))


async def require_driver_webapp(
    x_telegram_init_data: str = Header(...),
    db: Session = Depends(get_db),
) -> models.User:
    """Authenticate a driver by the Telegram account that opened the Mini App."""
    telegram_user = parse_telegram_init_data(x_telegram_init_data)
    telegram_id = telegram_user.get("id")
    user = (
        db.query(models.User)
        .filter(models.User.telegram_id == telegram_id)
        .first()
        if telegram_id else None
    )
    if not user or user.role not in ("admin", "driver"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Цей Telegram-акаунт не зареєстрований як водій",
        )
    return user


def is_bot_key(x_bot_key: Optional[str]) -> bool:
    return bool(x_bot_key) and hmac.compare_digest(x_bot_key, BOT_API_KEY)


def verify_bot_key(x_bot_key: Optional[str] = Security(api_key_header)) -> bool:
    if is_bot_key(x_bot_key):
        return True
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bot API key")


async def require_staff_or_bot(
    x_bot_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """Guards customer data: reachable by the bot or by a logged-in staff member.

    These endpoints carry names, phones and home addresses, and the API is
    exposed to the internet by the public landing page.
    """
    if is_bot_key(x_bot_key):
        return None
    return await get_current_user(token, db)


async def trusted_caller(
    x_bot_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> bool:
    """For endpoints the public may call: True if the bot or a logged-in staff
    member is calling, False for an anonymous visitor. Never raises."""
    if is_bot_key(x_bot_key):
        return True
    if not token:
        return False
    try:
        await get_current_user(token, db)
        return True
    except HTTPException:
        return False
