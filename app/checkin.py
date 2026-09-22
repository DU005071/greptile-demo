"""Online check-in: opens a fixed window before departure and assigns a seat."""

import threading
from datetime import datetime, timedelta, timezone

from app.flights import FLIGHTS
from app.models import Booking, BoardingPass, CheckInRequest, SeatPreference

CHECKIN_OPENS_BEFORE = timedelta(hours=24)
CHECKIN_CLOSES_BEFORE = timedelta(minutes=45)
BOARDING_BEFORE = timedelta(minutes=40)

ROWS = range(1, 31)
SEAT_LETTERS = "ABCDEF"
WINDOW_LETTERS = frozenset("AF")
AISLE_LETTERS = frozenset("CD")

BOARDING_PASSES: dict[str, BoardingPass] = {}
# flight_no -> seats already handed out on that flight
_TAKEN_SEATS: dict[str, set[str]] = {}
# Guards BOARDING_PASSES and _TAKEN_SEATS so that the duplicate check, the seat
# availability check and the seat assignment happen as one atomic step.
_CHECKIN_LOCK = threading.Lock()


class CheckInError(Exception):
    """Raised when a booking cannot be checked in (window closed, no flight, no seats)."""


class AlreadyCheckedInError(CheckInError):
    """Raised when a booking already holds a boarding pass."""


def check_in(booking: Booking, request: CheckInRequest) -> BoardingPass:
    """Check a booking in and return its boarding pass.

    The whole operation runs under a single lock so that concurrent requests
    can neither check the same booking in twice nor hand the same seat to two
    passengers.
    """
    with _CHECKIN_LOCK:
        if booking.booking_id in BOARDING_PASSES:
            raise AlreadyCheckedInError(f"Booking {booking.booking_id} is already checked in")

        flight = FLIGHTS.get(booking.flight_no)
        if flight is None:
            raise CheckInError(f"Flight {booking.flight_no} not found")

        now = datetime.now(timezone.utc)
        _ensure_window_open(flight.departure, now=now)

        seat, preference_met = _assign_seat(flight.flight_no, request.seat_preference)
        boarding_pass = BoardingPass(
            booking_id=booking.booking_id,
            flight_no=flight.flight_no,
            passenger_name=booking.passenger_name,
            origin=flight.origin,
            destination=flight.destination,
            seat=seat,
            seat_preference_met=preference_met,
            departure=flight.departure,
            boarding_time=flight.departure - BOARDING_BEFORE,
            checked_in_at=now,
        )
        BOARDING_PASSES[booking.booking_id] = boarding_pass
        return boarding_pass


def get_boarding_pass(booking_id: str) -> BoardingPass | None:
    """Return the stored boarding pass for a booking, or None if it is not checked in."""
    return BOARDING_PASSES.get(booking_id.upper())


def _ensure_window_open(departure: datetime, now: datetime) -> None:
    """Raise CheckInError unless ``now`` is inside the check-in window.

    The window opens exactly ``CHECKIN_OPENS_BEFORE`` before departure
    (inclusive) and closes exactly ``CHECKIN_CLOSES_BEFORE`` before departure
    (exclusive).
    """
    opens_at = departure - CHECKIN_OPENS_BEFORE
    closes_at = departure - CHECKIN_CLOSES_BEFORE
    if now < opens_at:
        raise CheckInError(f"Check-in opens at {opens_at.isoformat()}")
    if now >= closes_at:
        raise CheckInError("Check-in is closed for this flight")


def _assign_seat(flight_no: str, preference: SeatPreference) -> tuple[str, bool]:
    """Return the first free seat matching the preference, falling back to any seat.

    The caller must hold ``_CHECKIN_LOCK``: the availability check and the
    ``taken.add`` below are only atomic together under that lock.
    """
    taken = _TAKEN_SEATS.setdefault(flight_no, set())

    for seat in _seats_for(preference):
        if seat not in taken:
            taken.add(seat)
            return seat, True

    if preference != "any":
        seat, _ = _assign_seat(flight_no, "any")
        return seat, False

    raise CheckInError(f"No seats left to assign on flight {flight_no}")


def _seats_for(preference: SeatPreference):
    """Yield seat labels (e.g. ``1A``) row by row that satisfy the preference."""
    if preference == "window":
        letters = WINDOW_LETTERS
    elif preference == "aisle":
        letters = AISLE_LETTERS
    else:
        letters = frozenset(SEAT_LETTERS)

    for row in ROWS:
        for letter in SEAT_LETTERS:
            if letter in letters:
                yield f"{row}{letter}"
