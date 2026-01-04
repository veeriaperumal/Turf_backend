from datetime import time
from decimal import Decimal

WEEKEND_DAYS = {5, 6}  # Saturday, Sunday


def is_weekend(date):
    return date.weekday() in WEEKEND_DAYS


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and a_end > b_start


def calculate_booking_price(booking):
    weekend = is_weekend(booking.booking_date)

    if booking.booking_type == booking.FULL_DAY:
        return Decimal("12000.00") if weekend else Decimal("10000.00")

    base = Decimal("1000.00") if weekend else Decimal("800.00")
    peak_multiplier = Decimal("1.5")
    peak_start = time(18, 0)
    peak_end = time(22, 0)

    total = Decimal("0.00")
    current = booking.start_time

    while current < booking.end_time:
        next_hour = time(current.hour + 1, 0)
        price = base

        if overlaps(current, next_hour, peak_start, peak_end):
            price *= peak_multiplier

        total += price
        current = next_hour

    return total



def calculate_amounts(turf, duration_hours):
    base = duration_hours * turf.price_per_hour
    platform_fee = (base * turf.platform_fee_percent) / 100
    total = base + platform_fee
    return base, platform_fee, total
