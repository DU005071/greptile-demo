"""Online check-in: opens a fixed window before departure and assigns a seat."""

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


class CheckInError(Exception):
    pass


class AlreadyCheckedInError(CheckInError):
    pass


def check_in(booking: Booking, request: CheckInRequest) -> BoardingPass:
    if booking.booking_id in BOARDING_PASSES:
        raise AlreadyCheckedInError(f"Booking {booking.booking_id} is already checked in")

    flight = FLIGHTS.get(booking.flight_no)
    if flight is None:
        raise CheckInError(f"Flight {booking.flight_no} not found")

    _ensure_window_open(flight.departure, now=datetime.now(timezone.utc))

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
        checked_in_at=datetime.now(timezone.utc),
    )
    BOARDING_PASSES[booking.booking_id] = boarding_pass
    return boarding_pass


def get_boarding_pass(booking_id: str) -> BoardingPass | None:
    return BOARDING_PASSES.get(booking_id.upper())


def _ensure_window_open(departure: datetime, now: datetime) -> None:
    opens_at = departure - CHECKIN_OPENS_BEFORE
    closes_at = departure - CHECKIN_CLOSES_BEFORE
    if now < opens_at:
        raise CheckInError(f"Check-in opens at {opens_at.isoformat()}")
    if now >= closes_at:
        raise CheckInError("Check-in is closed for this flight")


def _assign_seat(flight_no: str, preference: SeatPreference) -> tuple[str, bool]:
    """Return the first free seat matching the preference, falling back to any seat."""
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
