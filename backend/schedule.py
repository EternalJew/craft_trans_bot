"""The weekly departure schedule, and keeping rides generated from it.

Departures repeat every week, so nobody should have to create them by hand —
they are generated ahead of time and topped up daily. Only exceptions to the
pattern (a Friday we skip, a second van) are worth a human's attention.
"""
import os
from datetime import date, time, timedelta

from sqlalchemy.orm import Session

import models

# direction -> weekdays it leaves on (Monday is 0)
DEPARTURE_WEEKDAYS = {
    "UA->CZ": (1, 4),   # вівторок, п'ятниця
    "CZ->UA": (3, 6),   # четвер, неділя
}

DEPARTURE_TIME = time(6, 0)
SEATS_PER_VAN = 8

# How far ahead passengers can book.
WEEKS_AHEAD = int(os.getenv("SCHEDULE_WEEKS_AHEAD", "6"))


def ensure_upcoming_rides(db: Session, weeks: int = WEEKS_AHEAD) -> int:
    """Create any missing departure for the next `weeks` weeks. Idempotent."""
    today = date.today()
    horizon = today + timedelta(weeks=weeks)

    routes = db.query(models.Route).filter(models.Route.is_active.is_(True)).all()
    if not routes:
        return 0

    existing = {
        (r.route_id, r.date)
        for r in db.query(models.Ride.route_id, models.Ride.date)
        .filter(models.Ride.date >= today)
        .all()
    }

    created = 0
    for route in routes:
        weekdays = DEPARTURE_WEEKDAYS.get(route.direction)
        if not weekdays:
            continue
        day = today
        while day <= horizon:
            if day.weekday() in weekdays and (route.id, day) not in existing:
                db.add(models.Ride(
                    route_id=route.id,
                    date=day,
                    departure_time=DEPARTURE_TIME,
                    seats_total=SEATS_PER_VAN,
                    seats_free=SEATS_PER_VAN,
                    status="active",
                ))
                created += 1
            day += timedelta(days=1)

    if created:
        db.commit()
    return created
