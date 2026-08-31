from app.models import Flight

BAG_FEE = 25.0


def calculate_total(flight: Flight, bags: int) -> float:
    """Total price = base fare + checked baggage fees."""
    total = flight.base_price + bags * BAG_FEE
    return round(total, 2)
