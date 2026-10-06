from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Flight(BaseModel):
    flight_no: str
    origin: str
    destination: str
    departure: datetime
    base_price: float
    seats_available: int


class BookingRequest(BaseModel):
    flight_no: str
    passenger_name: str = Field(min_length=2, max_length=100)
    passenger_email: str
    bags: int = Field(default=0, ge=0, le=5)


class Booking(BaseModel):
    booking_id: str
    flight_no: str
    passenger_name: str
    passenger_email: str
    bags: int
    total_price: float
    created_at: datetime


WaitlistStatus = Literal["waiting", "promoted", "cancelled"]


class WaitlistRequest(BaseModel):
    passenger_name: str = Field(min_length=2, max_length=100)
    passenger_email: str
    bags: int = Field(default=0, ge=0, le=5)


class WaitlistEntry(BaseModel):
    entry_id: str
    flight_no: str
    passenger_name: str
    passenger_email: str
    bags: int
    status: WaitlistStatus
    position: int | None
    booking_id: str | None = None
    created_at: datetime


class WaitlistSummary(BaseModel):
    flight_no: str
    seats_available: int
    waiting: int
    max_size: int
