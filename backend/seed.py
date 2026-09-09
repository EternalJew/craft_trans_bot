"""
Run once to create the admin user and sample route.
Usage: python seed.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from database import SessionLocal, engine
import models
from auth import hash_password
from datetime import date, timedelta, time as dt_time

models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

# ── Create admin manager ──────────────────────────────────────────────────────
admin_username = os.getenv("ADMIN_USERNAME", "admin")
admin_password = os.getenv("ADMIN_PASSWORD", "admin")

existing = db.query(models.User).filter(models.User.username == admin_username).first()
if not existing:
    admin = models.User(
        username=admin_username,
        password_hash=hash_password(admin_password),
        role="admin",
    )
    db.add(admin)
    db.commit()
    print(f"Created admin: {admin_username} / {admin_password}")
else:
    print(f"Admin '{admin_username}' already exists")

# ── Create the two real route pairs ───────────────────────────────────────────
# Bus A: Сарни / Рівне / Львів ↔ Hradec Králové / Mladá Boleslav / Liberec
# Bus B: Остріг / Рівне / Луцьк ↔ Brno / Praha / Chomutov
UA_A = ["Сарни", "Рівне", "Львів"]
CZ_A = ["Hradec Králové", "Mladá Boleslav", "Liberec"]
UA_B = ["Остріг", "Рівне", "Луцьк"]
CZ_B = ["Brno", "Praha", "Chomutov"]

ROUTES = [
    ("Захід UA → Чехія (північ)",  "UA->CZ", UA_A, CZ_A),
    ("Чехія (північ) → Захід UA",  "CZ->UA", CZ_A, UA_A),
    ("Захід UA → Чехія (Прага)",   "UA->CZ", UA_B, CZ_B),
    ("Чехія (Прага) → Захід UA",   "CZ->UA", CZ_B, UA_B),
]

existing_route = db.query(models.Route).first()
if not existing_route:
    for name, direction, pickup_cities, dropoff_cities in ROUTES:
        route = models.Route(name=name, direction=direction, is_active=True)
        db.add(route)
        db.flush()

        origin_country, dest_country = direction.split("->")
        order = 0
        for city in pickup_cities:
            db.add(models.Stop(route_id=route.id, city=city, country=origin_country,
                               order=order, pickup=True, dropoff=False))
            order += 1
        for city in dropoff_cities:
            db.add(models.Stop(route_id=route.id, city=city, country=dest_country,
                               order=order, pickup=False, dropoff=True))
            order += 1

    db.commit()
    print(f"Created {len(ROUTES)} routes with stops")

    # Upcoming rides: UA→CZ leaves Tue/Fri, CZ→UA leaves Thu/Sun
    DEPARTURE_WEEKDAYS = {"UA->CZ": (1, 4), "CZ->UA": (3, 6)}
    today = date.today()
    for route in db.query(models.Route).all():
        for offset in range(1, 15):
            day = today + timedelta(days=offset)
            if day.weekday() not in DEPARTURE_WEEKDAYS[route.direction]:
                continue
            db.add(models.Ride(
                route_id=route.id,
                date=day,
                departure_time=dt_time(6, 0),
                seats_total=8,
                seats_free=8,
                price=2000,
                status="active",
            ))
    db.commit()
    print("Created upcoming rides for the next two weeks")
else:
    print("Routes already seeded")

db.close()
print("Done.")
