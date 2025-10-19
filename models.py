from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Ride(Base):
    __tablename__ = "rides"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    direction = Column(String, nullable=False)  # UA → CZ або CZ → UA
    seats_total = Column(Integer, default=8)
    seats_free = Column(Integer, default=8)

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"))
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    seats = Column(Integer, default=1)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    ride = relationship("Ride")

class Parcel(Base):
    __tablename__ = "parcels"
    id = Column(Integer, primary_key=True, index=True)
    direction = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    sender_phone = Column(String, nullable=False)
    receiver = Column(String, nullable=False)
    receiver_phone = Column(String, nullable=False)
    np_office = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)