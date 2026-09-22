from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SeatPreference = Literal["window", "aisle", "any"]
SeatPosition = Literal["window", "middle", "aisle"]
SeatZone = Literal["front", "exit", "standard"]


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


class BookingCreated(Booking):
    """Booking as returned right after creation.

    ``access_token`` is shown only in this response. The client must send it
    as a Bearer token to check in and to fetch the boarding pass, so it should
    be stored securely and never logged.
    """

    access_token: str


class Seat(BaseModel):
    seat: str
    row: int
    letter: str
    position: SeatPosition
    zone: SeatZone
    price: float
    available: bool


class SeatMap(BaseModel):
    flight_no: str
    rows: int
    seats_per_row: int
    available: int
    prices: dict[SeatZone, float]
    seats: list[Seat]


class SeatSelectionRequest(BaseModel):
    seat: str = Field(min_length=2, max_length=3, examples=["12A"])


class SeatSelection(BaseModel):
    booking_id: str
    flight_no: str
    seat: str
    position: SeatPosition
    zone: SeatZone
    price: float
    selected_at: datetime


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
    seat_selected_in_advance: bool = False
    seat_price: float = 0.0
    departure: datetime
    boarding_time: datetime
    checked_in_at: datetime
