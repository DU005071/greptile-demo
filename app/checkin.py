"""Online check-in journey: advance seat selection, check-in window and boarding passes.

All state changes go through ``seats.INVENTORY_LOCK`` so that a seat can never
be selected and auto-assigned at the same time, and a booking cannot change
its seat while it is being checked in.
"""

from datetime import datetime, timedelta, timezone

from app.flights import FLIGHTS
from app.models import Booking, BoardingPass, CheckInRequest, SeatSelection
from app.seats import (
    INVENTORY_LOCK,
    SeatUnavailableError,
    assign_seat,
    normalize_seat,
    release_seat,
    seat_position,
    seat_price,
    seat_zone,
    take_seat,
)

CHECKIN_OPENS_BEFORE = timedelta(hours=24)
CHECKIN_CLOSES_BEFORE = timedelta(minutes=45)
BOARDING_BEFORE = timedelta(minutes=40)

BOARDING_PASSES: dict[str, BoardingPass] = {}
# booking_id -> seat the passenger picked (and paid for) before check-in
SEAT_SELECTIONS: dict[str, SeatSelection] = {}


class CheckInError(Exception):
    """Raised when a booking cannot be checked in or its seat cannot be changed."""


class AlreadyCheckedInError(CheckInError):
    """Raised when a booking already holds a boarding pass."""


def select_seat(booking: Booking, seat_no: str) -> SeatSelection:
    """Select or change the advance seat of a booking.

    Selection is open from the moment of booking until check-in closes. The
    new seat is taken before the previous one is released, so a failed change
    leaves the existing selection untouched. Selecting the current seat again
    is a no-op that returns the existing selection.
    """
    seat = normalize_seat(seat_no)
    flight = FLIGHTS.get(booking.flight_no)
    if flight is None:
        raise CheckInError(f"Flight {booking.flight_no} not found")

    with INVENTORY_LOCK:
        if booking.booking_id in BOARDING_PASSES:
            raise AlreadyCheckedInError("Seat cannot be changed after check-in")

        now = datetime.now(timezone.utc)
        _ensure_selection_open(flight.departure, now=now)

        current = SEAT_SELECTIONS.get(booking.booking_id)
        if current is not None and current.seat == seat:
            return current

        take_seat(flight.flight_no, seat)
        if current is not None:
            release_seat(flight.flight_no, current.seat)

        selection = SeatSelection(
            booking_id=booking.booking_id,
            flight_no=flight.flight_no,
            seat=seat,
            position=seat_position(seat),
            zone=seat_zone(seat),
            price=seat_price(seat),
            selected_at=now,
        )
        SEAT_SELECTIONS[booking.booking_id] = selection
        return selection


def get_seat_selection(booking_id: str) -> SeatSelection | None:
    """Return the advance seat selection of a booking, or None."""
    return SEAT_SELECTIONS.get(booking_id.upper())


def release_seat_selection(booking_id: str) -> bool:
    """Drop the advance selection and free the seat. Returns False if there was none."""
    with INVENTORY_LOCK:
        if booking_id in BOARDING_PASSES:
            raise AlreadyCheckedInError("Seat cannot be released after check-in")
        selection = SEAT_SELECTIONS.pop(booking_id, None)
        if selection is None:
            return False
        release_seat(selection.flight_no, selection.seat)
        return True


def check_in(booking: Booking, request: CheckInRequest) -> BoardingPass:
    """Check a booking in and return its boarding pass.

    A seat selected in advance is kept; otherwise the first free seat matching
    the preference is assigned. The whole operation runs under the inventory
    lock so concurrent requests can neither check the same booking in twice
    nor hand the same seat to two passengers.
    """
    with INVENTORY_LOCK:
        if booking.booking_id in BOARDING_PASSES:
            raise AlreadyCheckedInError(f"Booking {booking.booking_id} is already checked in")

        flight = FLIGHTS.get(booking.flight_no)
        if flight is None:
            raise CheckInError(f"Flight {booking.flight_no} not found")

        now = datetime.now(timezone.utc)
        _ensure_window_open(flight.departure, now=now)

        selection = SEAT_SELECTIONS.get(booking.booking_id)
        if selection is not None:
            seat = selection.seat
            preference_met = request.seat_preference == "any" or selection.position == request.seat_preference
        else:
            try:
                seat, preference_met = assign_seat(flight.flight_no, request.seat_preference)
            except SeatUnavailableError as exc:
                raise CheckInError(str(exc)) from exc

        boarding_pass = BoardingPass(
            booking_id=booking.booking_id,
            flight_no=flight.flight_no,
            passenger_name=booking.passenger_name,
            origin=flight.origin,
            destination=flight.destination,
            seat=seat,
            seat_preference_met=preference_met,
            seat_selected_in_advance=selection is not None,
            seat_price=selection.price if selection is not None else 0.0,
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


def _ensure_selection_open(departure: datetime, now: datetime) -> None:
    """Raise CheckInError once seat selection has closed, which coincides with check-in closing."""
    if now >= departure - CHECKIN_CLOSES_BEFORE:
        raise CheckInError("Seat selection is closed for this flight")
