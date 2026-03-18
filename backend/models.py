from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text, DateTime, Boolean, Float
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
    seats_total = Column(Integer, nullable=False)
    seats_free  = Column(Integer, nullable=False)
    vehicle     = Column(String, nullable=True)
    price       = Column(Integer, nullable=True)
    status      = Column(String, default="active")  # "active" | "cancelled"

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
    from_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=True)
    to_stop_id   = Column(Integer, ForeignKey("stops.id"), nullable=True)
    comment      = Column(String, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    status       = Column(String, default="confirmed")

    ride      = relationship("Ride", back_populates="bookings")
    from_stop = relationship("Stop", foreign_keys=[from_stop_id])
    to_stop   = relationship("Stop", foreign_keys=[to_stop_id])


class Parcel(Base):
    __tablename__ = "parcels"
    id             = Column(Integer, primary_key=True, index=True)
    ride_id        = Column(Integer, ForeignKey("rides.id"), nullable=True)
    direction      = Column(String, nullable=False)
    sender         = Column(String, nullable=False)
    sender_phone   = Column(String, nullable=False)
    receiver       = Column(String, nullable=False)
    receiver_phone = Column(String, nullable=False)
    np_office      = Column(String, nullable=False)
    description    = Column(Text, nullable=True)
    status         = Column(String, default="pending")  # "pending" | "in_transit" | "delivered"
    created_at     = Column(DateTime, default=datetime.utcnow)

    ride = relationship("Ride", back_populates="parcels")


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
