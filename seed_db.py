from database import SessionLocal, engine, Base
from models import Ride
from datetime import date

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Check existing
    existing = db.query(Ride).first()
    if existing:
        print("Database already seeded. Ride id:", existing.id)
        db.close()
        return

    ride = Ride(date=date.today(), direction="UA -> CZ", seats_total=8, seats_free=8)
    db.add(ride)
    db.commit()
    print("Seeded ride with id:", ride.id)
    db.close()

if __name__ == '__main__':
    seed()
