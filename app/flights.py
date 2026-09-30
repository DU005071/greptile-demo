from datetime import date, datetime, timedelta, timezone
from typing import Literal

from app.models import Flight

SortKey = Literal["departure", "price"]


def _upcoming(days: int, hour: int) -> datetime:
    base = datetime.now(timezone.utc) + timedelta(days=days)
    return base.replace(hour=hour, minute=0, second=0, microsecond=0)


FLIGHTS: dict[str, Flight] = {
    "XQ140": Flight(
        flight_no="XQ140",
        origin="AYT",
        destination="FRA",
        departure=_upcoming(days=2, hour=9),
        base_price=120.0,
        seats_available=42,
    ),
    "XQ151": Flight(
        flight_no="XQ151",
        origin="FRA",
        destination="AYT",
        departure=_upcoming(days=3, hour=14),
        base_price=135.0,
        seats_available=8,
    ),
    "XQ970": Flight(
        flight_no="XQ970",
        origin="ADB",
        destination="DUS",
        departure=_upcoming(days=1, hour=6),
        base_price=99.0,
        seats_available=0,
    ),
}


def list_flights() -> list[Flight]:
    return list(FLIGHTS.values())


def get_flight(flight_no: str) -> Flight | None:
    return FLIGHTS.get(flight_no.upper())


def search_flights(
    origin: str | None = None,
    destination: str | None = None,
    departure_date: date | None = None,
    max_price: float | None = None,
    include_sold_out: bool = False,
    sort_by: SortKey = "departure",
) -> list[Flight]:
    """Filter the schedule. Every filter is optional; omitted filters match everything.

    ``departure_date`` is compared against the departure date in UTC. Sold-out
    flights are hidden unless ``include_sold_out`` is set. Sorting by price falls
    back to departure time for flights with the same base price.
    """
    matches = []
    for flight in FLIGHTS.values():
        if origin and flight.origin != origin.upper():
            continue
        if destination and flight.destination != destination.upper():
            continue
        if departure_date and flight.departure.date() != departure_date:
            continue
        if max_price is not None and flight.base_price > max_price:
            continue
        if not include_sold_out and flight.seats_available < 1:
            continue
        matches.append(flight)

    if sort_by == "price":
        return sorted(matches, key=lambda f: (f.base_price, f.departure))
    return sorted(matches, key=lambda f: f.departure)
