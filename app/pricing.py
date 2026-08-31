from app.discounts import redeem
from app.models import Flight

BAG_FEE = 25.0


def calculate_total(flight: Flight, bags: int, codes: list[str] | None = None) -> float:
    """Total price = base fare + baggage fees, with any valid
    discount codes applied."""
    total = flight.base_price + bags * BAG_FEE

    # Dedupe with the same normalization redeem applies, so a repeated
    # code can't compound its discount or consume extra uses.
    for code in dict.fromkeys(c.strip().upper() for c in codes or []):
        discount = redeem(code)
        if discount is not None:
            total *= 1 - discount.percent / 100

    return round(total, 2)
