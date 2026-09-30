from app.models import FareClass, Flight, PriceBreakdown

BAG_FEE = 25.0
# Charged once per amendment on economy bookings; flex bookings amend for free.
AMENDMENT_FEE = 15.0

# Surcharge on the base fare, as a fraction of the base fare.
FARE_CLASS_SURCHARGE: dict[FareClass, float] = {
    FareClass.ECONOMY: 0.0,
    FareClass.FLEX: 0.35,
}
# Checked bags included in the fare before BAG_FEE applies.
INCLUDED_BAGS: dict[FareClass, int] = {
    FareClass.ECONOMY: 0,
    FareClass.FLEX: 1,
}


def price_breakdown(
    flight: Flight, bags: int, fare_class: FareClass = FareClass.ECONOMY
) -> PriceBreakdown:
    """Itemised fare for one passenger: base fare + fare-class surcharge + bag fees."""
    base_fare = flight.base_price
    surcharge = round(base_fare * FARE_CLASS_SURCHARGE[fare_class], 2)
    included = INCLUDED_BAGS[fare_class]
    chargeable = max(0, bags - included)
    bag_fees = chargeable * BAG_FEE
    return PriceBreakdown(
        base_fare=base_fare,
        fare_class_surcharge=surcharge,
        included_bags=included,
        chargeable_bags=chargeable,
        bag_fees=bag_fees,
        total=round(base_fare + surcharge + bag_fees, 2),
    )


def calculate_total(
    flight: Flight, bags: int, fare_class: FareClass = FareClass.ECONOMY
) -> float:
    """Total price for one passenger; see ``price_breakdown`` for the itemisation."""
    return price_breakdown(flight, bags, fare_class).total


def amendment_fee(fare_class: FareClass) -> float:
    """Fee for changing a booking that currently holds ``fare_class``."""
    return 0.0 if fare_class is FareClass.FLEX else AMENDMENT_FEE
