from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SeatPreference = Literal["window", "aisle", "any"]


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


class CheckInRequest(BaseModel):
    seat_preference: SeatPreference = "any"


class BoardingPass(BaseModel):
    booking_id: str
    flight_no: str
    passenger_name: str
    origin: str
    destination: str
    seat: str
    seat_preference_met: bool
    departure: datetime
    boarding_time: datetime
    checked_in_at: datetime
