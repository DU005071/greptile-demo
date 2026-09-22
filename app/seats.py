"""Seat catalogue and the seat inventory shared by advance selection and check-in.

Layout: 30 rows of six seats (A-F). A and F are window seats, C and D aisle
seats, B and E middle seats. Rows 1-3 form the "front" zone, rows 12 and 13
the overwing "exit" zone with extra legroom; everything else is "standard".

``_TAKEN_SEATS`` is the single source of truth for which seats are gone on a
flight, whether a passenger selected the seat in advance or check-in assigned
it. Every read-modify-write of it must happen under ``INVENTORY_LOCK``.
"""

import re
import threading
from collections.abc import Iterator

from app.flights import FLIGHTS
from app.models import Seat, SeatMap, SeatPosition, SeatPreference, SeatZone

ROWS = range(1, 31)
SEAT_LETTERS = "ABCDEF"
WINDOW_LETTERS = frozenset("AF")
AISLE_LETTERS = frozenset("CD")

FRONT_ROWS = frozenset(range(1, 4))
EXIT_ROWS = frozenset({12, 13})
SEAT_PRICES: dict[SeatZone, float] = {"front": 15.0, "exit": 10.0, "standard": 5.0}

_SEAT_NO = re.compile(r"^(\d{1,2})([A-F])$")

# flight_no -> seats no longer available on that flight
_TAKEN_SEATS: dict[str, set[str]] = {}
INVENTORY_LOCK = threading.Lock()


class SeatError(Exception):
    """Raised for a seat that does not exist on the aircraft."""


class SeatUnavailableError(SeatError):
    """Raised when the requested seat is already taken on that flight."""


def normalize_seat(seat_no: str) -> str:
    """Return ``seat_no`` in canonical form (``12a`` -> ``12A``).

    Raises SeatError when the row or letter is outside the aircraft layout.
    """
    match = _SEAT_NO.match(seat_no.strip().upper())
    if match is None or int(match.group(1)) not in ROWS:
        raise SeatError(f"Unknown seat {seat_no!r}: expected a row 1-30 followed by a letter A-F")
    return f"{int(match.group(1))}{match.group(2)}"


def seat_position(seat_no: str) -> SeatPosition:
    """Classify a seat as window, aisle or middle by its letter."""
    letter = seat_no[-1]
    if letter in WINDOW_LETTERS:
        return "window"
    if letter in AISLE_LETTERS:
        return "aisle"
    return "middle"


def seat_zone(seat_no: str) -> SeatZone:
    """Return the pricing zone of a seat by its row."""
    row = int(seat_no[:-1])
    if row in FRONT_ROWS:
        return "front"
    if row in EXIT_ROWS:
        return "exit"
    return "standard"


def seat_price(seat_no: str) -> float:
    """Price of selecting this seat in advance; auto-assignment at check-in is free."""
    return SEAT_PRICES[seat_zone(seat_no)]


def all_seats() -> Iterator[str]:
    """Yield every seat label row by row, ``1A`` through ``30F``."""
    for row in ROWS:
        for letter in SEAT_LETTERS:
            yield f"{row}{letter}"


def seats_for(preference: SeatPreference) -> Iterator[str]:
    """Yield seat labels row by row that satisfy the preference."""
    if preference == "window":
        letters = WINDOW_LETTERS
    elif preference == "aisle":
        letters = AISLE_LETTERS
    else:
        letters = frozenset(SEAT_LETTERS)

    for seat in all_seats():
        if seat[-1] in letters:
            yield seat


def take_seat(flight_no: str, seat_no: str) -> None:
    """Mark a seat as taken. The caller must hold ``INVENTORY_LOCK``."""
    taken = _TAKEN_SEATS.setdefault(flight_no, set())
    if seat_no in taken:
        raise SeatUnavailableError(f"Seat {seat_no} is no longer available on flight {flight_no}")
    taken.add(seat_no)


def release_seat(flight_no: str, seat_no: str) -> None:
    """Return a seat to the pool. The caller must hold ``INVENTORY_LOCK``."""
    _TAKEN_SEATS.get(flight_no, set()).discard(seat_no)


def assign_seat(flight_no: str, preference: SeatPreference) -> tuple[str, bool]:
    """Take the first free seat matching the preference, falling back to any seat.

    Returns the seat and whether the preference was met. The caller must hold
    ``INVENTORY_LOCK``: the availability check and the add below are only
    atomic together under that lock.
    """
    taken = _TAKEN_SEATS.setdefault(flight_no, set())

    for seat in seats_for(preference):
        if seat not in taken:
            taken.add(seat)
            return seat, True

    if preference != "any":
        seat, _ = assign_seat(flight_no, "any")
        return seat, False

    raise SeatUnavailableError(f"No seats left to assign on flight {flight_no}")


def get_seat_map(flight_no: str) -> SeatMap | None:
    """Return the full seat map of a flight with availability and prices, or None."""
    flight = FLIGHTS.get(flight_no.upper())
    if flight is None:
        return None

    with INVENTORY_LOCK:
        taken = frozenset(_TAKEN_SEATS.get(flight.flight_no, set()))

    seats = [
        Seat(
            seat=seat,
            row=int(seat[:-1]),
            letter=seat[-1],
            position=seat_position(seat),
            zone=seat_zone(seat),
            price=seat_price(seat),
            available=seat not in taken,
        )
        for seat in all_seats()
    ]
    return SeatMap(
        flight_no=flight.flight_no,
        rows=len(ROWS),
        seats_per_row=len(SEAT_LETTERS),
        available=sum(1 for seat in seats if seat.available),
        prices=SEAT_PRICES,
        seats=seats,
    )
