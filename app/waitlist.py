import uuid
from datetime import datetime, timezone

from app.bookings import BookingError, create_booking
from app.models import (
    Booking,
    BookingRequest,
    Flight,
    WaitlistEntry,
    WaitlistRequest,
    WaitlistSummary,
)

MAX_WAITLIST_SIZE = 20

WAITLIST: dict[str, WaitlistEntry] = {}
_QUEUES: dict[str, list[str]] = {}


class WaitlistError(Exception):
    """Raised when a waitlist operation conflicts with the current state."""


def _queue(flight_no: str) -> list[str]:
    return _QUEUES.setdefault(flight_no, [])


def _refresh_positions(flight_no: str) -> None:
    for index, entry_id in enumerate(_queue(flight_no), start=1):
        WAITLIST[entry_id].position = index


def join_waitlist(flight: Flight, request: WaitlistRequest) -> WaitlistEntry:
    """Queue a passenger for a sold-out flight and return their entry."""
    if flight.seats_available > 0:
        raise WaitlistError(
            f"Flight {flight.flight_no} still has seats available, book directly"
        )
    if flight.departure <= datetime.now(timezone.utc):
        raise WaitlistError(f"Flight {flight.flight_no} has already departed")

    queue = _queue(flight.flight_no)
    if len(queue) >= MAX_WAITLIST_SIZE:
        raise WaitlistError(f"Waitlist for flight {flight.flight_no} is full")

    email = request.passenger_email.strip().lower()
    for entry_id in queue:
        if WAITLIST[entry_id].passenger_email.strip().lower() == email:
            raise WaitlistError(
                f"{request.passenger_email} is already on the waitlist "
                f"for flight {flight.flight_no}"
            )

    entry = WaitlistEntry(
        entry_id=uuid.uuid4().hex[:8].upper(),
        flight_no=flight.flight_no,
        passenger_name=request.passenger_name,
        passenger_email=request.passenger_email,
        bags=request.bags,
        status="waiting",
        position=len(queue) + 1,
        created_at=datetime.now(timezone.utc),
    )
    WAITLIST[entry.entry_id] = entry
    queue.append(entry.entry_id)
    return entry


def get_entry(entry_id: str) -> WaitlistEntry | None:
    return WAITLIST.get(entry_id.upper())


def leave_waitlist(entry_id: str) -> WaitlistEntry | None:
    """Drop a waiting passenger from the queue and close the gap behind them."""
    entry = WAITLIST.get(entry_id.upper())
    if entry is None:
        return None
    if entry.status != "waiting":
        raise WaitlistError(
            f"Waitlist entry {entry.entry_id} is already {entry.status}"
        )

    _queue(entry.flight_no).remove(entry.entry_id)
    entry.status = "cancelled"
    entry.position = None
    _refresh_positions(entry.flight_no)
    return entry


def waitlist_summary(flight: Flight) -> WaitlistSummary:
    return WaitlistSummary(
        flight_no=flight.flight_no,
        seats_available=flight.seats_available,
        waiting=len(_queue(flight.flight_no)),
        max_size=MAX_WAITLIST_SIZE,
    )


def promote_next(flight_no: str) -> Booking | None:
    """Book the first waiting passenger once a seat on the flight is free."""
    queue = _queue(flight_no.upper())
    if not queue:
        return None

    entry = WAITLIST[queue[0]]
    try:
        booking = create_booking(
            BookingRequest(
                flight_no=entry.flight_no,
                passenger_name=entry.passenger_name,
                passenger_email=entry.passenger_email,
                bags=entry.bags,
            )
        )
    except BookingError:
        return None

    queue.pop(0)
    entry.status = "promoted"
    entry.position = None
    entry.booking_id = booking.booking_id
    _refresh_positions(entry.flight_no)
    return booking
