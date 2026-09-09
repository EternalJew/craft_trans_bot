"""Parcel photo storage on the local filesystem, served from /media."""
import os
import secrets
import uuid

from fastapi import HTTPException, UploadFile

MEDIA_ROOT = os.getenv(
    "MEDIA_ROOT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media"),
)
PARCEL_PHOTO_DIR = os.path.join(MEDIA_ROOT, "parcels")

MAX_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg": ".jpg", "jpeg": ".jpg", "png": ".png", "webp": ".webp"}

# Ambiguous characters (0/O, 1/I) left out — these get read out over the phone.
TRACKING_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def generate_tracking_number() -> str:
    return "CT-" + "".join(secrets.choice(TRACKING_ALPHABET) for _ in range(6))


def save_parcel_photo(upload: UploadFile) -> str:
    extension = ALLOWED_EXTENSIONS.get((upload.filename or "").rsplit(".", 1)[-1].lower())
    if not extension:
        raise HTTPException(status_code=400, detail="Only jpg, png or webp photos are accepted")

    content = upload.file.read()
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Photo is larger than 10 MB")

    os.makedirs(PARCEL_PHOTO_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    with open(os.path.join(PARCEL_PHOTO_DIR, filename), "wb") as f:
        f.write(content)
    return filename


def delete_parcel_photo(filename: str) -> None:
    path = os.path.join(PARCEL_PHOTO_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
