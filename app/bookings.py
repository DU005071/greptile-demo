import uuid
from datetime import datetime, timezone

from app.flights import FLIGHTS
from app.models import Booking, BookingAmended, BookingRequest, BookingUpdate
from app.pricing import amendment_fee, calculate_total

BOOKINGS: dict[str, Booking] = {}


class BookingError(Exception):
    """Request cannot be fulfilled as sent (maps to 400)."""


class BookingNotFound(BookingError):
    """No booking with that ID (maps to 404)."""


class BookingConflict(BookingError):
    """Booking exists but its state forbids the action (maps to 409)."""


def create_booking(request: BookingRequest) -> Booking:
    flight = FLIGHTS.get(request.flight_no.upper())
    if flight is None:
        raise BookingError(f"Flight {request.flight_no} not found")
    if flight.seats_available < 1:
        raise BookingError(f"Flight {request.flight_no} is sold out")

    total = calculate_total(flight, request.bags, request.fare_class)
    booking = Booking(
        booking_id=uuid.uuid4().hex[:8].upper(),
        flight_no=flight.flight_no,
        passenger_name=request.passenger_name,
        passenger_email=request.passenger_email,
        bags=request.bags,
        fare_class=request.fare_class,
        total_price=total,
        created_at=datetime.now(timezone.utc),
    )
    flight.seats_available -= 1
    BOOKINGS[booking.booking_id] = booking
    return booking


def get_booking(booking_id: str) -> Booking | None:
    return BOOKINGS.get(booking_id.upper())


def amend_booking(booking_id: str, update: BookingUpdate) -> BookingAmended:
    """Apply a passenger's changes and reprice the booking.

    The fare is recalculated from scratch for the new bags/fare class, then the
    amendment fees paid so far are added on top. The fee for this amendment is
    decided by the fare class the booking holds *before* the change, so an
    economy passenger upgrading to flex pays the fee once, and a flex passenger
    never pays it. A request that changes nothing is a no-op and costs nothing.
    """
    booking = BOOKINGS.get(booking_id.upper())
    if booking is None:
        raise BookingNotFound(f"Booking {booking_id} not found")

    flight = FLIGHTS[booking.flight_no]
    if flight.departure <= datetime.now(timezone.utc):
        raise BookingConflict(f"Flight {flight.flight_no} has already departed")

    new_name = update.passenger_name or booking.passenger_name
    new_bags = booking.bags if update.bags is None else update.bags
    new_class = update.fare_class or booking.fare_class

    unchanged = (
        new_name == booking.passenger_name
        and new_bags == booking.bags
        and new_class == booking.fare_class
    )
    if unchanged:
        return BookingAmended(
            **booking.model_dump(),
            previous_total=booking.total_price,
            price_difference=0.0,
            amendment_fee_charged=0.0,
        )

    fee = amendment_fee(booking.fare_class)
    fees_paid = round(booking.amendment_fees + fee, 2)
    new_total = round(calculate_total(flight, new_bags, new_class) + fees_paid, 2)

    amended = booking.model_copy(
        update={
            "passenger_name": new_name,
            "bags": new_bags,
            "fare_class": new_class,
            "total_price": new_total,
            "amendment_fees": fees_paid,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    BOOKINGS[amended.booking_id] = amended
    return BookingAmended(
        **amended.model_dump(),
        previous_total=booking.total_price,
        price_difference=round(new_total - booking.total_price, 2),
        amendment_fee_charged=fee,
    )
