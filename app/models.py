from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class FareClass(str, Enum):
    """Fare families. ``flex`` costs more but includes a checked bag and free amendments."""

    ECONOMY = "economy"
    FLEX = "flex"


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
    fare_class: FareClass = FareClass.ECONOMY


class Booking(BaseModel):
    booking_id: str
    flight_no: str
    passenger_name: str
    passenger_email: str
    bags: int
    fare_class: FareClass = FareClass.ECONOMY
    total_price: float
    amendment_fees: float = 0.0
    created_at: datetime
    updated_at: datetime | None = None


class BookingUpdate(BaseModel):
    """Fields a passenger may change on an existing booking. At least one is required."""

    passenger_name: str | None = Field(default=None, min_length=2, max_length=100)
    bags: int | None = Field(default=None, ge=0, le=5)
    fare_class: FareClass | None = None

    @model_validator(mode="after")
    def _require_a_change(self) -> "BookingUpdate":
        if self.passenger_name is None and self.bags is None and self.fare_class is None:
            raise ValueError("Provide at least one of passenger_name, bags or fare_class")
        return self


class BookingAmended(Booking):
    """Booking after an amendment, with the price movement that the change caused."""

    previous_total: float
    price_difference: float
    amendment_fee_charged: float


class PriceBreakdown(BaseModel):
    base_fare: float
    fare_class_surcharge: float
    included_bags: int
    chargeable_bags: int
    bag_fees: float
    total: float


class QuoteRequest(BaseModel):
    flight_no: str
    passengers: int = Field(default=1, ge=1, le=9)
    bags: int = Field(default=0, ge=0, le=5, description="Checked bags per passenger")
    fare_class: FareClass = FareClass.ECONOMY


class Quote(BaseModel):
    flight_no: str
    fare_class: FareClass
    passengers: int
    per_passenger: PriceBreakdown
    total: float
    seats_available: int
    bookable: bool
    valid_until: datetime
