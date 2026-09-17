import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from database import engine, get_db, SessionLocal
import models
import schemas
import migrate
import notify
import parcels_intake
import ratelimit
import retention
import schedule
import storage
from auth import authenticate_user, create_access_token
from routers import routes, rides, bookings, parcels, users, driver, vehicles, notifications, book, account

# Create all tables on startup
models.Base.metadata.create_all(bind=engine)

added = migrate.run(engine)
if added:
    print("Added columns:", ", ".join(added))

REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "10"))


def queue_day_before_reminders():
    db = SessionLocal()
    try:
        notify.generate_day_before_reminders(db)
    finally:
        db.close()


def top_up_schedule():
    """Departures repeat weekly, so rides are generated rather than entered."""
    db = SessionLocal()
    try:
        created = schedule.ensure_upcoming_rides(db)
        if created:
            print(f"Scheduled {created} upcoming rides")
    finally:
        db.close()


def forget_old_passengers():
    db = SessionLocal()
    try:
        bookings, parcels = retention.anonymize_old_records(db)
        if bookings or parcels:
            print(f"Retention: anonymized {bookings} bookings, {parcels} parcels")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "Europe/Kyiv"))
    scheduler.add_job(queue_day_before_reminders, "cron", hour=REMINDER_HOUR, minute=0)
    scheduler.add_job(top_up_schedule, "cron", hour=3, minute=0)
    scheduler.add_job(forget_old_passengers, "cron", day=1, hour=4, minute=0)
    scheduler.start()
    top_up_schedule()
    yield
    scheduler.shutdown(wait=False)


# The interactive API docs are a map of everything; only for local development.
DEBUG = os.getenv("DEBUG", "0") == "1"

app = FastAPI(
    title="craft plus API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None,
    openapi_url="/openapi.json" if DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(rides.router)
app.include_router(bookings.router)
app.include_router(parcels.router)
app.include_router(users.router)
app.include_router(driver.router)
app.include_router(vehicles.router)
app.include_router(notifications.router)
app.include_router(book.router)
app.include_router(account.router)

os.makedirs(storage.PARCEL_PHOTO_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=storage.MEDIA_ROOT), name="media")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/driver", include_in_schema=False)
def driver_app():
    """Telegram Mini App the drivers open from the bot."""
    return FileResponse(os.path.join(STATIC_DIR, "driver.html"))


@app.get("/api/public/config")
def public_config(db: Session = Depends(get_db)):
    """What the landing and the bot both need to tell a sender where to send."""
    return {
        "bot_username": os.getenv("BOT_USERNAME", ""),
        "parcel_intake": {
            "UA->CZ": parcels_intake.intake_info(db, "UA->CZ"),
            "CZ->UA": parcels_intake.intake_info(db, "CZ->UA"),
        },
    }


@app.post("/auth/token", response_model=schemas.Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = ratelimit.client_ip(request)
    wait = ratelimit.login_guard.check(ip)
    if wait:
        raise ratelimit.too_many(wait)
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        ratelimit.login_guard.failed(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    ratelimit.login_guard.succeeded(ip)
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@app.get("/health")
def health():
    return {"status": "ok"}
