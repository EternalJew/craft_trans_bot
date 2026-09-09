from sqlalchemy import Column, Integer, String, Date, Time, ForeignKey, Text, DateTime, Boolean, Float
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    """Admin and Driver accounts."""
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name     = Column(String, nullable=True)
    phone         = Column(String, nullable=True)
    role          = Column(String, default="driver")  # "admin" | "driver"
    telegram_id   = Column(Integer, unique=True, nullable=True, index=True)

    assigned_rides = relationship("Ride", back_populates="driver", foreign_keys="Ride.driver_id")


class Route(Base):
    __tablename__ = "routes"
    id        = Column(Integer, primary_key=True, index=True)
    name      = Column(String, nullable=False)
    direction = Column(String, nullable=False)  # "UA->CZ" | "CZ->UA"
    is_active = Column(Boolean, default=True)

    stops = relationship("Stop", back_populates="route", order_by="Stop.order", cascade="all, delete-orphan")
    rides = relationship("Ride", back_populates="route", cascade="all, delete-orphan")


class Stop(Base):
    __tablename__ = "stops"
    id       = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    city     = Column(String, nullable=False)
    country  = Column(String, nullable=False)
    order    = Column(Integer, nullable=False)
    pickup   = Column(Boolean, default=True)
    dropoff  = Column(Boolean, default=True)
    lat      = Column(Float, nullable=True)   # latitude for map
    lng      = Column(Float, nullable=True)   # longitude for map

    route = relationship("Route", back_populates="stops")


class Ride(Base):
    __tablename__ = "rides"
    id          = Column(Integer, primary_key=True, index=True)
    route_id    = Column(Integer, ForeignKey("routes.id"), nullable=False)
    driver_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    date        = Column(Date, nullable=False)
    departure_time = Column(Time, nullable=True)
    seats_total = Column(Integer, nullable=False)
    seats_free  = Column(Integer, nullable=False)
    vehicle     = Column(String, nullable=True)
    price       = Column(Integer, nullable=True)
    status      = Column(String, default="active")  # "active" | "in_progress" | "completed" | "cancelled"
    started_at  = Column(DateTime, nullable=True)

    route    = relationship("Route", back_populates="rides")
    driver   = relationship("User", back_populates="assigned_rides", foreign_keys=[driver_id])
    bookings = relationship("Booking", back_populates="ride", cascade="all, delete-orphan")
    parcels  = relationship("Parcel", back_populates="ride")


class Booking(Base):
    __tablename__ = "bookings"
    id           = Column(Integer, primary_key=True, index=True)
    ride_id      = Column(Integer, ForeignKey("rides.id"), nullable=False)
    name         = Column(String, nullable=False)
    phone        = Column(String, nullable=False)
    seats        = Column(Integer, nullable=False)
    # Free text: one of the route's stops, or a town the passenger typed themselves.
    from_city    = Column(String, nullable=False)
    to_city      = Column(String, nullable=False)
    from_address = Column(String, nullable=True)   # door-to-door pickup address
    to_address   = Column(String, nullable=True)   # door-to-door dropoff address
    pickup_time  = Column(Time, nullable=True)     # ETA at the pickup address
    comment      = Column(String, nullable=True)
    telegram_id  = Column(Integer, nullable=True, index=True)
    source       = Column(String, default="bot")   # "bot" | "web" | "admin"
    # set by the driver on the road: waiting | picked_up | no_show | dropped_off
    pickup_status = Column(String, default="waiting")
    cash_collected = Column(Integer, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    status       = Column(String, default="confirmed")

    reminded_day_before = Column(Boolean, default=False)
    reminded_departure  = Column(Boolean, default=False)

    ride      = relationship("Ride", back_populates="bookings")


class Parcel(Base):
    __tablename__ = "parcels"
    id              = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String, unique=True, nullable=False, index=True)
    ride_id         = Column(Integer, ForeignKey("rides.id"), nullable=True)
    direction       = Column(String, nullable=False)
    sender          = Column(String, nullable=False)
    sender_phone    = Column(String, nullable=False)
    sender_address  = Column(String, nullable=True)   # where we pick it up
    receiver        = Column(String, nullable=False)
    receiver_phone  = Column(String, nullable=False)
    receiver_address = Column(String, nullable=True)  # door-to-door delivery
    np_office       = Column(String, nullable=True)   # or a Nova Poshta office
    description     = Column(Text, nullable=True)
    price           = Column(Integer, nullable=True)
    # accepted | in_transit | border_crossed | out_for_delivery | delivered
    status          = Column(String, default="accepted")
    cash_collected  = Column(Integer, nullable=True)
    sender_telegram_id = Column(Integer, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    delivered_at    = Column(DateTime, nullable=True)

    ride   = relationship("Ride", back_populates="parcels")
    photos = relationship("ParcelPhoto", back_populates="parcel", cascade="all, delete-orphan")


class ParcelPhoto(Base):
    __tablename__ = "parcel_photos"
    id         = Column(Integer, primary_key=True, index=True)
    parcel_id  = Column(Integer, ForeignKey("parcels.id"), nullable=False)
    filename   = Column(String, nullable=False)
    kind       = Column(String, default="intake")  # "intake" | "delivery"
    created_at = Column(DateTime, default=datetime.utcnow)

    parcel = relationship("Parcel", back_populates="photos")


# ── Notifications ──────────────────────────────────────────────────────────────

class Notification(Base):
    """Outbox: the API writes messages here, the bot polls and delivers them."""
    __tablename__ = "notifications"
    id          = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, nullable=False, index=True)
    text        = Column(Text, nullable=False)
    kind        = Column(String, nullable=False)  # day_before | departure | parcel_status
    status      = Column(String, default="pending", index=True)  # pending | sent | failed
    created_at  = Column(DateTime, default=datetime.utcnow)
    sent_at     = Column(DateTime, nullable=True)
    error       = Column(Text, nullable=True)


class TelegramContact(Base):
    """Maps a phone number to a Telegram account so we can reach people who
    booked through the website or were entered by an admin."""
    __tablename__ = "telegram_contacts"
    id          = Column(Integer, primary_key=True, index=True)
    phone       = Column(String, unique=True, nullable=False, index=True)
    telegram_id = Column(Integer, nullable=False)
    full_name   = Column(String, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


# ── Vehicle tracking ───────────────────────────────────────────────────────────

class Vehicle(Base):
    __tablename__ = "vehicles"
    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String, nullable=False)   # e.g. "Ford Transit #1"
    plate           = Column(String, nullable=False)
    make            = Column(String, nullable=True)    # Ford
    model_name      = Column(String, nullable=True)    # Transit
    year            = Column(Integer, nullable=True)
    mileage_current = Column(Integer, nullable=False, default=0)
    notes           = Column(Text, nullable=True)

    maintenance = relationship(
        "MaintenanceRecord", back_populates="vehicle",
        cascade="all, delete-orphan",
    )


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"
    id              = Column(Integer, primary_key=True, index=True)
    vehicle_id      = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    date            = Column(Date, nullable=False)
    mileage         = Column(Integer, nullable=False)   # km at time of service
    work_type       = Column(String, nullable=False)    # oil_change | brake_pads | timing_belt | tires | filters | battery | other
    description     = Column(Text, nullable=True)
    cost            = Column(Float, nullable=True)      # EUR
    next_service_km = Column(Integer, nullable=True)    # mileage at which to do it again
    created_at      = Column(DateTime, default=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="maintenance")
