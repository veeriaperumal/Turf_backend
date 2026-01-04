# turf/utils.py
from datetime import date, datetime, timedelta

def generate_hour_slots(open_time, close_time):
    slots = []
    current = datetime.combine(datetime.today(), open_time)
    end = datetime.combine(datetime.today(), close_time)

    while current < end:
        slots.append(current.time())
        current += timedelta(hours=1)

    return slots


def expand_booking_slots(start, end):
        slots = []
        current = datetime.combine(date.today(), start)
        end_dt = datetime.combine(date.today(), end)

        while current < end_dt:
            slots.append(current.time())
            current += timedelta(hours=1)

        return slots