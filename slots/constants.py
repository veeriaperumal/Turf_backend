# slots/constants.py
class SlotStatus:
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    MAINTENANCE = "MAINTENANCE"
    BLOCKED = "BLOCKED"
    TOURNAMENT = "TOURNAMENT"

    CHOICES = (
        (AVAILABLE, "Available"),
        (BOOKED, "Booked"),
        (MAINTENANCE, "Maintenance"),
        (BLOCKED, "Blocked"),
        (TOURNAMENT, "Tournament"),
    )
