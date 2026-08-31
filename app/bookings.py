import uuid
from datetime import datetime, timezone

from app.flights import FLIGHTS
from app.models import Booking, BookingRequest
from app.pricing import calculate_total

BOOKINGS: dict[str, Booking] = {}


class BookingError(Exception):
    pass


def create_booking(request: BookingRequest) -> Booking:
    flight = FLIGHTS.get(request.flight_no.upper())
    if flight is None:
        raise BookingError(f"Flight {request.flight_no} not found")
    if flight.seats_available < 1:
        raise BookingError(f"Flight {request.flight_no} is sold out")

    total = calculate_total(flight, request.bags)
    booking = Booking(
        booking_id=uuid.uuid4().hex[:8].upper(),
        flight_no=flight.flight_no,
        passenger_name=request.passenger_name,
        passenger_email=request.passenger_email,
        bags=request.bags,
        total_price=total,
        created_at=datetime.now(timezone.utc),
    )
    flight.seats_available -= 1
    BOOKINGS[booking.booking_id] = booking
    return booking


def get_booking(booking_id: str) -> Booking | None:
    return BOOKINGS.get(booking_id.upper())
