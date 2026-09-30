from datetime import datetime, timedelta, timezone

from app.flights import FLIGHTS
from app.models import Quote, QuoteRequest
from app.pricing import price_breakdown

# How long a quoted price is presented as valid. Quotes are informational and
# are not stored, so nothing is enforced against ``valid_until`` at booking time.
QUOTE_VALIDITY = timedelta(minutes=15)


def build_quote(request: QuoteRequest) -> Quote | None:
    """Price a party without touching inventory. Returns None for an unknown flight."""
    flight = FLIGHTS.get(request.flight_no.upper())
    if flight is None:
        return None

    per_passenger = price_breakdown(flight, request.bags, request.fare_class)
    return Quote(
        flight_no=flight.flight_no,
        fare_class=request.fare_class,
        passengers=request.passengers,
        per_passenger=per_passenger,
        total=round(per_passenger.total * request.passengers, 2),
        seats_available=flight.seats_available,
        bookable=flight.seats_available >= request.passengers,
        valid_until=datetime.now(timezone.utc) + QUOTE_VALIDITY,
    )
