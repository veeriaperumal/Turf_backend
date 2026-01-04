# turf/admin.py

from django.contrib import admin
from .models import (
    Sport,
    Amenity,
    Turf,
    Booking,
    TurfPricing,
)

# -------------------------------
# SPORT ADMIN
# -------------------------------
# Manages different sports a turf can support (e.g., Football, Cricket)
@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    # Display ID and name in admin list view
    list_display = ("id", "name")

    # Enable search by sport name
    search_fields = ("name",)


# -------------------------------
# AMENITY ADMIN
# -------------------------------
# Manages amenities available at a turf (e.g., Parking, Washroom)
@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


# -------------------------------
# TURF PRICING INLINE
# -------------------------------
# Inline pricing configuration shown inside Turf admin
# Enforces 1 pricing row per turf (no deletion, no duplicates)
class TurfPricingInline(admin.StackedInline):
    model = TurfPricing
    extra = 0              # Do not show empty extra forms
    can_delete = False     # Prevent accidental deletion of pricing


# -------------------------------
# TURF ADMIN
# -------------------------------
# Main Turf configuration screen
@admin.register(Turf)
class TurfAdmin(admin.ModelAdmin):
    # Fields visible in turf list view
    list_display = (
        "id",
        "name",
        "price",          # Base per-hour price
        "rating",
        "review_count",
    )

    # Enable filtering by sports and amenities
    list_filter = ("sports", "amenities")

    # Allow searching by turf name and address
    search_fields = ("name", "address")

    # Better UI for many-to-many relationships
    filter_horizontal = ("sports", "amenities")

    # Embed pricing configuration directly inside Turf admin
    inlines = [TurfPricingInline]


# -------------------------------
# BOOKING ADMIN
# -------------------------------
# Admin view for all turf bookings (critical operational view)
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "turf",
        "user",
        "booking_type",
        "booking_date",
        "start_time",
        "end_time",
        "status",
        "created_at",
    )

    # Enable filtering by booking state and date
    list_filter = (
        "booking_type",
        "status",
        "booking_date",
    )

    # Enable searching bookings by turf name or user email
    search_fields = (
        "turf__name",
        "user__email",
    )

    # Enables calendar-based navigation in admin
    date_hierarchy = "booking_date"

    # Prevent manual tampering with creation timestamp
    readonly_fields = ("created_at",)


# -------------------------------
# TURF PRICING ADMIN
# -------------------------------
# Standalone pricing admin (useful for auditing or debugging)
@admin.register(TurfPricing)
class TurfPricingAdmin(admin.ModelAdmin):
    list_display = (
        "turf",
        "weekday_hour_price",
        "weekend_hour_price",
        "weekday_full_day_price",
        "weekend_full_day_price",
        "peak_start",
        "peak_end",
        "peak_multiplier",
    )
