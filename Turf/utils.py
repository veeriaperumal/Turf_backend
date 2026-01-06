# turf/utils.py
from datetime import datetime, timedelta, date

def generate_hour_slots(open_time, close_time):
    slots = []

    base_date = date(2000, 1, 1)
    current = datetime.combine(base_date, open_time)
    end = datetime.combine(base_date, close_time)

    if end <= current:
        end += timedelta(days=1)

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