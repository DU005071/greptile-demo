from datetime import datetime, timedelta, timezone

from app.models import Flight


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
