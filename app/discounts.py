from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class DiscountCode:
    code: str
    percent: int  # 10 means 10% off
    valid_until: datetime
    max_uses: int
    used: int = 0


DISCOUNT_CODES: dict[str, DiscountCode] = {
    "SUMMER10": DiscountCode(
        "SUMMER10", 10, datetime(2026, 9, 30, tzinfo=timezone.utc), max_uses=100
    ),
    "VIP25": DiscountCode(
        "VIP25", 25, datetime(2026, 12, 31, tzinfo=timezone.utc), max_uses=10
    ),
    "CREW50": DiscountCode(
        "CREW50", 50, datetime(2027, 1, 1, tzinfo=timezone.utc), max_uses=5
    ),
}


def redeem(code: str) -> DiscountCode | None:
    """Look up and consume a discount code. Returns None if the code
    is unknown, expired, or has reached its usage limit."""
    discount = DISCOUNT_CODES.get(code.strip().upper())
    if discount is None:
        return None
    if discount.used >= discount.max_uses:
        return None
    if datetime.now(timezone.utc) > discount.valid_until:
        return None
    discount.used += 1
    return discount
