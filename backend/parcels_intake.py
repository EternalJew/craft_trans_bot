"""How a parcel physically reaches us, and by when.

Ukraine → Czechia has three ways in: Nova Poshta to our office, the sender
brings it to Rivne, or a driver collects it. Czechia → Ukraine has one: the
driver collects by address, since there is no Nova Poshta equivalent there.

The office, the collection days and the drop-off point live in .env so they
can change without a deploy.
"""
import os
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

import models
import schedule

# Ukrainian needs the accusative after "у" and "до": у понеділок, до четверга.
WEEKDAYS_NOM = ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя"]
WEEKDAYS_ACC = ["понеділок", "вівторок", "середу", "четвер", "п'ятницю", "суботу", "неділю"]
WEEKDAYS_GEN = ["понеділка", "вівторка", "середи", "четверга", "п'ятниці", "суботи", "неділі"]


def _days(raw: str) -> list[int]:
    return sorted({int(x) for x in raw.replace(" ", "").split(",") if x.isdigit() and 0 <= int(x) <= 6})


NP_OFFICE = os.getenv("PARCEL_NP_OFFICE", "").strip()
NP_DAYS = _days(os.getenv("PARCEL_NP_WEEKDAYS", ""))
DROPOFF = os.getenv("PARCEL_DROPOFF", "").strip()


def next_departure(db: Session, direction: str, after: Optional[date] = None) -> Optional[models.Ride]:
    after = after or date.today()
    return (
        db.query(models.Ride)
        .join(models.Route)
        .filter(models.Ride.date > after, models.Ride.status == "active",
                models.Route.direction == direction)
        .order_by(models.Ride.date)
        .first()
    )


def np_deadline(departure: date) -> Optional[date]:
    """The last day we collect from the post office before this departure."""
    if not NP_DAYS:
        return departure - timedelta(days=1)
    for back in range(1, 15):
        day = departure - timedelta(days=back)
        if day.weekday() in NP_DAYS and day >= date.today():
            return day
    return None


def np_days_text() -> str:
    if not NP_DAYS:
        return ""
    return " і ".join(WEEKDAYS_ACC[d] for d in NP_DAYS)


def intake_info(db: Session, direction: str) -> dict:
    """Everything the bot and the site need to tell a sender."""
    ride = next_departure(db, direction)
    departure = ride.date if ride else None
    deadline = np_deadline(departure) if departure else None
    return {
        "direction": direction,
        "np_office": NP_OFFICE or None,
        "np_days": np_days_text() or None,
        "dropoff": DROPOFF or None,
        "departure": departure.isoformat() if departure else None,
        "departure_weekday": WEEKDAYS_ACC[departure.weekday()] if departure else None,
        "np_deadline": deadline.isoformat() if deadline else None,
        "np_deadline_weekday": WEEKDAYS_GEN[deadline.weekday()] if deadline else None,
    }


def label_text(city: str, address: str, phone: str) -> str:
    """What the sender writes on the box: where it goes and who receives it."""
    where = ", ".join(x for x in [city.strip(), address.strip()] if x)
    return f"{where}\n{phone.strip()}"
