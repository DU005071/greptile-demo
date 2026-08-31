from datetime import datetime, timezone

from app.discounts import redeem
from app.models import Flight

BAG_FEE = 25.0
LAST_MINUTE_SURCHARGE = 1.2
LAST_MINUTE_THRESHOLD_DAYS = 2


def calculate_total(flight: Flight, bags: int, codes: list[str] | None = None) -> float:
    """Total price = base fare + baggage fees, with last-minute surcharge
    and any valid discount codes applied."""
    total = flight.base_price + bags * BAG_FEE

    days_to_departure = (flight.departure - datetime.now(timezone.utc)).days
    if days_to_departure < LAST_MINUTE_THRESHOLD_DAYS:
        total *= LAST_MINUTE_SURCHARGE

    for code in codes or []:
        discount = redeem(code)
        if discount is not None:
            total *= 1 - discount.percent / 100

    return round(total, 2)
