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
    
    
def build_booking_response(booking):
    slots = booking.slots.all()

    return {
        "turf_data": {
            "turf_id": str(booking.turf.id),
            "turf_name": booking.turf.name,
        },
        "booking_details": {
            "booking_date": booking.booking_date.strftime("%Y-%m-%d"),
            "sport": "Football",
        },
        "slots_booked": [
            {
                "slot_id": s.id,
                "from_time": s.start_time.strftime("%I:%M %p"),
                "to_time": s.end_time.strftime("%I:%M %p"),
                "status": s.status,
                "price": f"{s.price:.2f}",
                "label": "Standard Booking",
            }
            for s in slots
        ],
        "price_breakdown": {
            "total_amount": float(booking.total_amount)
        },
        "user_details": {
            "user_id": booking.user.id
        }
    }

