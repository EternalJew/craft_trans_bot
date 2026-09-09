from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime, time


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username:  str
    password:  str
    full_name: Optional[str] = None
    phone:     Optional[str] = None
    role:      str = "driver"

class UserOut(BaseModel):
    id:        int
    username:  str
    full_name: Optional[str] = None
    phone:     Optional[str] = None
    role:      str
    model_config = {"from_attributes": True}

class UserMe(UserOut):
    pass


# ── Stop ──────────────────────────────────────────────────────────────────────

class StopBase(BaseModel):
    city:    str
    country: str
    order:   int
    pickup:  bool = True
    dropoff: bool = True
    lat:     Optional[float] = None
    lng:     Optional[float] = None

class StopCreate(StopBase):
    pass

class StopOut(StopBase):
    id:       int
    route_id: int
    model_config = {"from_attributes": True}


# ── Route ─────────────────────────────────────────────────────────────────────

class RouteBase(BaseModel):
    name:      str
    direction: str
    is_active: bool = True

class RouteCreate(RouteBase):
    stops: List[StopCreate] = []

class RouteUpdate(RouteBase):
    stops: List[StopCreate] = []

class RouteOut(RouteBase):
    id:    int
    stops: List[StopOut] = []
    model_config = {"from_attributes": True}

class RouteShort(BaseModel):
    id:        int
    name:      str
    direction: str
    is_active: bool
    model_config = {"from_attributes": True}


# ── Ride ──────────────────────────────────────────────────────────────────────

class RideBase(BaseModel):
    route_id:       int
    date:           date
    departure_time: Optional[time] = None
    seats_total:    int
    vehicle:        Optional[str] = None
    price:          Optional[int] = None

class RideCreate(RideBase):
    pass

class RideOut(RideBase):
    id:         int
    seats_free: int
    status:     str
    started_at: Optional[datetime] = None
    driver_id:  Optional[int] = None
    driver:     Optional[UserOut] = None
    route:      RouteShort
    model_config = {"from_attributes": True}


# ── Booking ───────────────────────────────────────────────────────────────────

class BookingBase(BaseModel):
    ride_id:      int
    name:         str
    phone:        str
    seats:        int
    from_stop_id: Optional[int] = None
    to_stop_id:   Optional[int] = None
    from_address: Optional[str] = None
    to_address:   Optional[str] = None
    comment:      Optional[str] = None

class BookingCreate(BookingBase):
    telegram_id: Optional[int] = None
    source:      str = "bot"

class BookingUpdate(BaseModel):
    seats:        Optional[int] = None
    comment:      Optional[str] = None
    from_address: Optional[str] = None
    to_address:   Optional[str] = None
    pickup_time:  Optional[time] = None

class BookingOut(BookingBase):
    id:          int
    pickup_time: Optional[time] = None
    created_at:  datetime
    status:      str
    source:      str
    from_stop:   Optional[StopOut] = None
    to_stop:     Optional[StopOut] = None
    model_config = {"from_attributes": True}


# ── Parcel ────────────────────────────────────────────────────────────────────

class ParcelBase(BaseModel):
    direction:      str
    sender:         str
    sender_phone:   str
    receiver:       str
    receiver_phone: str
    np_office:      str
    description:    Optional[str] = None
    ride_id:        Optional[int] = None

class ParcelCreate(ParcelBase):
    pass

class ParcelStatusUpdate(BaseModel):
    status: str

class ParcelOut(ParcelBase):
    id:         int
    status:     str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Vehicle ───────────────────────────────────────────────────────────────────

class MaintenanceRecordCreate(BaseModel):
    date:            date
    mileage:         int
    work_type:       str
    description:     Optional[str] = None
    cost:            Optional[float] = None
    next_service_km: Optional[int] = None

class MaintenanceRecordOut(MaintenanceRecordCreate):
    id:         int
    vehicle_id: int
    created_at: datetime
    model_config = {"from_attributes": True}

class VehicleCreate(BaseModel):
    name:            str
    plate:           str
    make:            Optional[str] = None
    model_name:      Optional[str] = None
    year:            Optional[int] = None
    mileage_current: int = 0
    notes:           Optional[str] = None

class VehicleUpdate(BaseModel):
    name:            Optional[str] = None
    plate:           Optional[str] = None
    make:            Optional[str] = None
    model_name:      Optional[str] = None
    year:            Optional[int] = None
    mileage_current: Optional[int] = None
    notes:           Optional[str] = None

class VehicleOut(VehicleCreate):
    id:          int
    maintenance: List[MaintenanceRecordOut] = []
    model_config = {"from_attributes": True}


# ── Notifications ─────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id:          int
    telegram_id: int
    text:        str
    kind:        str
    status:      str
    created_at:  datetime
    model_config = {"from_attributes": True}

class NotificationAck(BaseModel):
    status: str                      # "sent" | "failed"
    error:  Optional[str] = None

class TelegramContactCreate(BaseModel):
    phone:       str
    telegram_id: int
    full_name:   Optional[str] = None

class TelegramContactOut(BaseModel):
    id:          int
    phone:       str
    telegram_id: int
    full_name:   Optional[str] = None
    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type:   str
    role:         str

class TokenData(BaseModel):
    username: Optional[str] = None
