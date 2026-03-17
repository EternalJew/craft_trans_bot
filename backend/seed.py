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
from datetime import date

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

# ── Create sample route UA → CZ ───────────────────────────────────────────────
existing_route = db.query(models.Route).first()
if not existing_route:
    route = models.Route(name="Київ → Прага", direction="UA->CZ", is_active=True)
    db.add(route)
    db.flush()

    stops_data = [
        ("Київ",    "UA", True,  False),
        ("Житомир", "UA", True,  False),
        ("Рівне",   "UA", True,  False),
        ("Львів",   "UA", True,  False),
        ("Краків",  "PL", False, True),
        ("Острава", "CZ", False, True),
        ("Прага",   "CZ", False, True),
    ]
    for i, (city, country, pickup, dropoff) in enumerate(stops_data):
        db.add(models.Stop(
            route_id=route.id,
            city=city,
            country=country,
            order=i,
            pickup=pickup,
            dropoff=dropoff,
        ))

    # Create a sample ride on that route
    ride = models.Ride(
        route_id=route.id,
        date=date.today(),
        seats_total=8,
        seats_free=8,
        vehicle="VW Crafter",
        price=1200,
        status="active",
    )
    db.add(ride)
    db.commit()
    print(f"Created route (id={route.id}) with {len(stops_data)} stops and 1 sample ride")
else:
    print("Routes already seeded")

db.close()
print("Done.")
