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
CHUNK = 1024 * 1024


def _looks_like(extension: str, head: bytes) -> bool:
    """The file's first bytes have to agree with its name."""
    if extension == ".jpg":
        return head.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False

# Ambiguous characters (0/O, 1/I) left out — these get read out over the phone.
TRACKING_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def generate_tracking_number() -> str:
    return "CT-" + "".join(secrets.choice(TRACKING_ALPHABET) for _ in range(6))


def save_parcel_photo(upload: UploadFile) -> str:
    extension = ALLOWED_EXTENSIONS.get((upload.filename or "").rsplit(".", 1)[-1].lower())
    if not extension:
        raise HTTPException(status_code=400, detail="Only jpg, png or webp photos are accepted")

    head = upload.file.read(16)
    if not _looks_like(extension, head):
        raise HTTPException(status_code=400, detail="The file is not a jpg, png or webp image")

    os.makedirs(PARCEL_PHOTO_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    path = os.path.join(PARCEL_PHOTO_DIR, filename)
    # Copy in pieces and stop at the cap, so an oversized upload never sits
    # whole in memory or on disk.
    written = 0
    with open(path, "wb") as f:
        f.write(head)
        written += len(head)
        while chunk := upload.file.read(CHUNK):
            written += len(chunk)
            if written > MAX_PHOTO_BYTES:
                f.close()
                os.remove(path)
                raise HTTPException(status_code=400, detail="Photo is larger than 10 MB")
            f.write(chunk)
    return filename


def delete_parcel_photo(filename: str) -> None:
    path = os.path.join(PARCEL_PHOTO_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
