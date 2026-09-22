import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from app.flights import FLIGHTS
from app.models import Booking, BookingCreated, BookingRequest
from app.pricing import calculate_total

BOOKINGS: dict[str, Booking] = {}
# booking_id -> SHA-256 hex digest of the booking's access token. Only the
# digest is kept, so an in-memory dump does not hand out usable credentials.
_ACCESS_TOKEN_HASHES: dict[str, str] = {}


class BookingError(Exception):
    pass


def create_booking(request: BookingRequest) -> BookingCreated:
    """Create a booking and issue the access token that authorizes later actions.

    The token is returned exactly once, in this response. Check-in and
    boarding-pass retrieval require it, so possession of the short booking ID
    alone is not enough to act on someone else's booking.
    """
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
    access_token = secrets.token_urlsafe(32)

    flight.seats_available -= 1
    BOOKINGS[booking.booking_id] = booking
    _ACCESS_TOKEN_HASHES[booking.booking_id] = _hash_token(access_token)
    return BookingCreated(**booking.model_dump(), access_token=access_token)


def get_booking(booking_id: str) -> Booking | None:
    return BOOKINGS.get(booking_id.upper())


def verify_access_token(booking_id: str, access_token: str) -> bool:
    """Return True only if ``access_token`` is the token issued for ``booking_id``.

    The comparison is constant-time so response timing does not reveal how
    much of a guessed token was correct.
    """
    expected = _ACCESS_TOKEN_HASHES.get(booking_id.upper())
    if expected is None:
        return False
    return secrets.compare_digest(expected, _hash_token(access_token))


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
