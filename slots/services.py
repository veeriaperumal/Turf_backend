# from datetime import datetime, timedelta, time
# from Turf.models import Booking, MaintenanceBlock
# from Turf.utils import generate_hour_slots
# from slots.models import Slot

# def build_date_selector(selected_date):
#     start_date = selected_date - timedelta(days=1)

#     days = []
#     for i in range(6):
#         current = start_date + timedelta(days=i)
#         days.append({
#             "day_name": current.strftime("%a").upper(),
#             "day_number": current.strftime("%d"),
#             "full_date": current.isoformat(),
#             "is_selected": current == selected_date
#         })

#     return {
#         "current_date": selected_date.isoformat(),
#         "month_label": selected_date.strftime("%B %Y"),
#         "days": days
#     }


# def resolve_slot(turf, slot_date, slot_time):
#     maintenance = MaintenanceBlock.objects.filter(
#         turf=turf,
#         date=slot_date,
#         start_time__lte=slot_time,
#         end_time__gt=slot_time
#     ).first()

#     if maintenance:
#         return {
#             "status": "MAINTENANCE",
#             "title": "Turf Maintenance",
#             "subtitle": maintenance.reason,
#             "is_selectable": False,
#             "price": None
#         }

#     booking = Booking.objects.filter(
#         turf=turf,
#         booking_date=slot_date,
#         start_time=slot_time,
#         status="CONFIRMED"
#     ).first()

#     if booking:
#         return {
#             "status": "BOOKED",
#             "title": booking.booked_by_name,
#             "subtitle": "Standard • 5v5",
#             "is_selectable": False,
#             "price": None
#         }

#     return {
#         "status": "AVAILABLE",
#         "title": "Available Slot",
#         "subtitle": None,
#         "is_selectable": True,
#         "price": turf.price
#     }


# def format_slot(idx, slot_time, resolved):
#     return {
#         "id": f"slot_{idx:02}",
#         "time_label": slot_time.strftime("%I:%M\n%p"),
#         "title": resolved["title"],
#         "subtitle": resolved["subtitle"],
#         "status": resolved["status"],
#         "price_display": (
#             f"${resolved['price']:.2f}"
#             if resolved["price"] else None
#         ),
#         "is_selectable": resolved["is_selectable"]
#     }

# def format_existing_slot(slot):
#     return {
#         "slot_id": slot.id,
#         "from_time": slot.start_time.strftime("%I:%M %p"),
#         "to_time": slot.end_time.strftime("%I:%M %p"),
#         "status": slot.status,
#         "price": str(slot.price),
#         "label": slot.label
#     }

# def format_default_slot_range(turf, start_time, end_time):
#     return {
#         "slot_id": None,
#         "from_time": start_time.strftime("%I:%M %p"),
#         "to_time": end_time.strftime("%I:%M %p"),
#         "status": "AVAILABLE",
#         "price": str(turf.price),
#         "label": "Open Session"
#     }

    



# def generate_slots_for_date(open_time, close_time, selected_date):
#     """
#     Returns list of (start_time, end_time)
#     """
#     weekday = selected_date.weekday()  # Mon=0 ... Sat=5, Sun=6
#     slots = []

#     # -------------------------
#     # WEEKENDS (SAT, SUN)
#     # -------------------------
#     if weekday in (5, 6):
#         slots.extend([
#             (time(6, 0), time(10, 0)),
#             (time(10, 0), time(14, 0)),
#             (time(14, 0), time(18, 0)),
#         ])

#         current = datetime.combine(selected_date, time(18, 0))
#         end = datetime.combine(selected_date, close_time)

#         while current < end:
#             slots.append((
#                 current.time(),
#                 (current + timedelta(hours=1)).time()
#             ))
#             current += timedelta(hours=1)

#         return slots

#     # -------------------------
#     # WEEKDAYS (MON–FRI)
#     # -------------------------
#     current = datetime.combine(selected_date, open_time)
#     end = datetime.combine(selected_date, close_time)

#     while current < end:
#         slots.append((
#             current.time(),
#             (current + timedelta(hours=1)).time()
#         ))
#         current += timedelta(hours=1)

#     return slots



from datetime import datetime, timedelta, time
from slots.models import Slot


# -------------------------
# DATE SELECTOR (UI helper)
# -------------------------
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


# -------------------------
# SLOT FORMATTERS
# -------------------------
def format_existing_slot(slot):
    return {
        "slot_id": slot.id,
        "from_time": slot.start_time.strftime("%I:%M %p"),
        "to_time": slot.end_time.strftime("%I:%M %p"),
        "status": slot.status,
        "price": str(slot.price),
        "label": slot.label
    }


def format_default_slot_range(turf, start_time, end_time):
    return {
        "slot_id": None,
        "from_time": start_time.strftime("%I:%M %p"),
        "to_time": end_time.strftime("%I:%M %p"),
        "status": "AVAILABLE",
        "price": str(turf.price),
        "label": "Open Session"
    }


# -------------------------
# SLOT GENERATION LOGIC
# -------------------------
def generate_slots_for_date(open_time, close_time, selected_date):
    """
    Returns list of (start_time, end_time)
    """
    weekday = selected_date.weekday()  # Mon=0 ... Sat=5, Sun=6
    slots = []

    # WEEKENDS
    if weekday in (5, 6):
        slots.extend([
            (time(6, 0), time(10, 0)),
            (time(10, 0), time(14, 0)),
            (time(14, 0), time(18, 0)),
        ])

        current = datetime.combine(selected_date, time(18, 0))
        end = datetime.combine(selected_date, close_time)

        while current < end:
            slots.append((
                current.time(),
                (current + timedelta(hours=1)).time()
            ))
            current += timedelta(hours=1)

        return slots

    # WEEKDAYS
    current = datetime.combine(selected_date, open_time)
    end = datetime.combine(selected_date, close_time)

    while current < end:
        slots.append((
            current.time(),
            (current + timedelta(hours=1)).time()
        ))
        current += timedelta(hours=1)

    return slots


# -------------------------
# MAIN RESPONSE BUILDER
# -------------------------
def build_slots_response(turf, selected_date):
    date_selector = build_date_selector(selected_date)

    existing_slots = {
        slot.start_time: slot
        for slot in Slot.objects.filter(
            turf=turf,
            date=selected_date
        )
    }

    slot_ranges = generate_slots_for_date(
        turf.opening_time,
        turf.closing_time,
        selected_date
    )

    slots = []

    for start_time, end_time in slot_ranges:
        slot = existing_slots.get(start_time)

        if slot:
            slots.append(format_existing_slot(slot))
        else:
            slots.append(
                format_default_slot_range(
                    turf, start_time, end_time
                )
            )

    return {
        "turf_details": {
            "id": turf.id,
            "name": turf.name,
            "location": turf.address
        },
        "date_selector": date_selector,
        "slots": slots
    }
