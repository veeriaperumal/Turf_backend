from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from Accounts.models import User

# =========================
# MASTER DATA MODELS
# =========================

class Sport(models.Model):
    """
    Represents a sport type (e.g., Football, Cricket).
    Used for filtering turfs by supported sports.
    """
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Amenity(models.Model):
    """
    Represents facilities available at a turf
    (e.g., Parking, Washroom, Flood Lights).
    """
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


# =========================
# TURF (BUSINESS ASSET)
# =========================

class Turf(models.Model):
    """
    Core business entity.
    Owned by a business user and used for bookings.
    """

    # Business owner (role should be validated at serializer level)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="turfs"
    )

    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="turf_images/", blank=True, null=True)
    address = models.CharField(max_length=255)

    # Operating hours (used for slot validation)
    opening_time = models.TimeField()
    closing_time = models.TimeField()

    # Base price (fallback if pricing rules fail)
    price = models.PositiveIntegerField()

    location_url = models.URLField(blank=True)
    cancellation_policy = models.TextField(blank=True)

    # Many-to-many relationships
    sports = models.ManyToManyField(Sport, related_name="turfs")
    amenities = models.ManyToManyField(Amenity, related_name="turfs")

    # Custom rules stored as JSON list
    rules = models.JSONField(default=list)

    # Aggregated review data
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    review_count = models.PositiveIntegerField(default=0)

    # Platform commission (percentage-based)
    platform_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        help_text="Platform commission percentage"
    )

    # Soft delete / availability flag
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# =========================
# BOOKING MODEL
# =========================

class Booking(models.Model):
    """
    Represents a reservation made by a user for a turf.
    Payment is linked separately.
    """

    # Booking types
    HOURLY = "hourly"
    FULL_DAY = "full_day"

    BOOKING_TYPE_CHOICES = [
        (HOURLY, "Hourly"),
        (FULL_DAY, "Full Day"),
    ]

    # Booking lifecycle states
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (CONFIRMED, "Confirmed"),
        (CANCELLED, "Cancelled"),
    ]

    turf = models.ForeignKey(
        Turf,
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    booking_type = models.CharField(
        max_length=10,
        choices=BOOKING_TYPE_CHOICES
    )

    booking_date = models.DateField()

    # Only applicable for hourly bookings
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    # Derived value (used for pricing + validation)
    duration_hours = models.PositiveSmallIntegerField()

    # Pricing breakdown (snapshotted at booking time)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=CONFIRMED
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Improves lookup for availability checks
        indexes = [
            models.Index(fields=["turf", "booking_date"]),
        ]

    def clean(self):
        """
        Business rule validation.
        Runs on full_clean() before save().
        """

        # Full-day bookings must NOT have time slots
        if self.booking_type == self.FULL_DAY:
            if self.start_time or self.end_time:
                raise ValidationError(
                    "Full day booking cannot have start/end time"
                )

        # Hourly bookings MUST have valid time range
        if self.booking_type == self.HOURLY:
            if not self.start_time or not self.end_time:
                raise ValidationError(
                    "Hourly booking requires start and end time"
                )
            if self.start_time >= self.end_time:
                raise ValidationError(
                    "Invalid time range"
                )

    def __str__(self):
        return f"{self.turf} | {self.booking_date} | {self.booking_type}"


# =========================
# DYNAMIC PRICING MODEL
# =========================

class TurfPricing(models.Model):
    """
    Pricing rules for a turf.
    Separated to keep Turf model clean.
    """

    turf = models.OneToOneField(
        Turf,
        on_delete=models.CASCADE
    )

    # Hourly pricing
    weekday_hour_price = models.DecimalField(max_digits=8, decimal_places=2)
    weekend_hour_price = models.DecimalField(max_digits=8, decimal_places=2)

    # Full-day pricing
    weekday_full_day_price = models.DecimalField(max_digits=8, decimal_places=2)
    weekend_full_day_price = models.DecimalField(max_digits=8, decimal_places=2)

    # Peak hour surge pricing
    peak_start = models.TimeField()
    peak_end = models.TimeField()
    peak_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.5
    )


# =========================
# PAYMENT MODEL
# =========================

class Payment(models.Model):
    """
    Stores payment transaction details.
    One-to-one with Booking.
    """

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"

    PAYMENT_STATUS_CHOICES = [
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
        (PENDING, "Pending"),
    ]

    # Supported payment methods
    UPI = "UPI"
    CARD = "CARD"
    NET_BANKING = "NET_BANKING"
    CASH = "CASH"

    PAYMENT_METHOD_CHOICES = [
        (UPI, "UPI"),
        (CARD, "Card"),
        (NET_BANKING, "Net Banking"),
        (CASH, "Cash"),
    ]

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="payment"
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES
    )

    # Gateway / manual transaction reference
    transaction_ref = models.CharField(
        max_length=100,
        unique=True
    )

    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    currency = models.CharField(
        max_length=10,
        default="INR"
    )

    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES
    )

    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.transaction_ref

class MaintenanceBlock(models.Model):
    turf = models.ForeignKey(Turf, on_delete=models.CASCADE)
    date = models.DateField()

    start_time = models.TimeField()
    end_time = models.TimeField()

    reason = models.CharField(max_length=100)

    def __str__(self):
        return f"Maintenance {self.turf.name}"
