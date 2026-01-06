from datetime import timedelta, time
from Turf.models import Booking, MaintenanceBlock
from Turf.utils import generate_hour_slots

def build_date_selector(selected_date):
    start_date = selected_date - timedelta(days=1)

    days = []
    for i in range(6):
        current = start_date + timedelta(days=i)
        days.append({
            "day_name": current.strftime("%a").upper(),
            "day_number": current.strftime("%d"),
            "full_date": current.isoformat(),
            "is_selected": current == selected_date
        })

    return {
        "current_date": selected_date.isoformat(),
        "month_label": selected_date.strftime("%B %Y"),
        "days": days
    }


def resolve_slot(turf, slot_date, slot_time):
    maintenance = MaintenanceBlock.objects.filter(
        turf=turf,
        date=slot_date,
        start_time__lte=slot_time,
        end_time__gt=slot_time
    ).first()

    if maintenance:
        return {
            "status": "MAINTENANCE",
            "title": "Turf Maintenance",
            "subtitle": maintenance.reason,
            "is_selectable": False,
            "price": None
        }

    booking = Booking.objects.filter(
        turf=turf,
        booking_date=slot_date,
        start_time=slot_time,
        status="CONFIRMED"
    ).first()

    if booking:
        return {
            "status": "BOOKED",
            "title": booking.booked_by_name,
            "subtitle": "Standard • 5v5",
            "is_selectable": False,
            "price": None
        }

    return {
        "status": "AVAILABLE",
        "title": "Available Slot",
        "subtitle": None,
        "is_selectable": True,
        "price": turf.price
    }


def format_slot(idx, slot_time, resolved):
    return {
        "id": f"slot_{idx:02}",
        "time_label": slot_time.strftime("%I:%M\n%p"),
        "title": resolved["title"],
        "subtitle": resolved["subtitle"],
        "status": resolved["status"],
        "price_display": (
            f"${resolved['price']:.2f}"
            if resolved["price"] else None
        ),
        "is_selectable": resolved["is_selectable"]
    }


def build_slots_response(turf, selected_date):
    date_selector = build_date_selector(selected_date)

    slot_times = generate_hour_slots(
        turf.opening_time,
        turf.closing_time
    )

    slots = []
    for idx, slot_time in enumerate(slot_times, start=1):
        resolved = resolve_slot(turf, selected_date, slot_time)
        slots.append(format_slot(idx, slot_time, resolved))

    return {
        "turf_details": {
            "id": turf.id,
            "name": turf.name,
            "location": turf.address
        },
        "date_selector": date_selector,
        "slots": slots
    }
