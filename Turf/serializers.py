from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from Turf.exceptions import SlotAlreadyBooked
from .models import Booking, Turf
from .service import calculate_booking_price


# =========================================================
# BOOKING SERIALIZER
# Handles creation + validation of turf bookings
# =========================================================
class BookingSerializer(serializers.ModelSerializer):

    # Computed field (not stored in DB)
    total_price = serializers.SerializerMethodField()

    # Accept turf_id in request but map it to turf FK
    turf_id = serializers.PrimaryKeyRelatedField(
        queryset=Turf.objects.all(),
        source="turf"
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "turf_id",
            "booking_type",
            "booking_date",
            "start_time",
            "end_time",
            "total_price",
            "status",
            "created_at",
        ]
        # These are controlled by backend only
        read_only_fields = ("price", "status", "created_at")

    # -----------------------------------------------------
    # BUSINESS RULE VALIDATION (NO DB WRITES HERE)
    # -----------------------------------------------------
    def validate(self, data):
        today = timezone.localdate()

        booking_date = data.get("booking_date")
        booking_type = data.get("booking_type")
        turf = data.get("turf")

        # Mandatory fields check
        if not booking_date or not booking_type:
            raise serializers.ValidationError("Missing required fields")

        # Prevent past bookings
        if booking_date < today:
            raise serializers.ValidationError("Cannot book past dates")

        days_ahead = (booking_date - today).days

        # FULL DAY booking rules
        if booking_type == Booking.FULL_DAY:
            if days_ahead > 60:
                raise serializers.ValidationError(
                    "Full-day booking allowed only up to 2 months in advance"
                )

        # HOURLY booking rules
        if booking_type == Booking.HOURLY:
            if days_ahead > 7:
                raise serializers.ValidationError(
                    "Hourly booking allowed only up to 7 days in advance"
                )

            start = data.get("start_time")
            end = data.get("end_time")

            if not start or not end:
                raise serializers.ValidationError("Start and end time required")

            if start >= end:
                raise serializers.ValidationError("Invalid time range")

            # Respect turf operating hours
            if start < turf.opening_time or end > turf.closing_time:
                raise serializers.ValidationError("Outside operating hours")

        return data

    # -----------------------------------------------------
    # CREATE BOOKING (RACE-SAFE WITH DB LOCK)
    # -----------------------------------------------------
    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user

        turf = validated_data["turf"]
        booking_date = validated_data["booking_date"]
        booking_type = validated_data["booking_type"]

        # Atomic block prevents double booking under concurrency
        with transaction.atomic():
            existing = Booking.objects.select_for_update().filter(
                turf=turf,
                booking_date=booking_date,
                status=Booking.CONFIRMED,
            )

            # FULL DAY booking blocks everything
            if booking_type == Booking.FULL_DAY:
                if existing.exists():
                    raise serializers.ValidationError("Turf already booked")

                # 12 hours assumed as full-day base
                validated_data["price"] = turf.price * 12

            # HOURLY booking logic
            else:
                start = validated_data["start_time"]
                end = validated_data["end_time"]

                # If full-day already exists → reject
                if existing.filter(booking_type=Booking.FULL_DAY).exists():
                    raise serializers.ValidationError("Turf already booked")

                # Overlapping time check (core logic)
                if existing.filter(
                    booking_type=Booking.HOURLY,
                    start_time__lt=end,
                    end_time__gt=start,
                ).exists():
                    raise serializers.ValidationError("Time slot already booked")

                # Calculate duration
                duration_hours = (
                    datetime.combine(booking_date, end)
                    - datetime.combine(booking_date, start)
                ).total_seconds() / 3600

                validated_data["price"] = int(duration_hours * turf.price)

            return super().create(validated_data)

    # Used only for response display
    def get_total_price(self, obj):
        return obj.duration_hours * obj.turf.price


# =========================================================
# TURF DETAIL SERIALIZER (READ-ONLY)
# =========================================================
class TurfDetailSerializer(serializers.ModelSerializer):

    # Custom formatted ID
    id = serializers.SerializerMethodField()
    sports = serializers.SerializerMethodField()
    amenities = serializers.SerializerMethodField()

    class Meta:
        model = Turf
        fields = (
            "id",
            "name",
            "image",
            "address",
            "rating",
            "review_count",
            "price",
            "sports",
            "amenities",
            "location_url",
            "rules",
            "cancellation_policy",
        )

    def get_id(self, obj):
        return f"turf_{obj.id}"

    def get_sports(self, obj):
        return list(obj.sports.values_list("name", flat=True))

    def get_amenities(self, obj):
        return list(obj.amenities.values_list("name", flat=True))


# =========================================================
# TURF AVAILABILITY QUERY
# =========================================================
class TurfAvailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField()

    def validate_date(self, value):
        if value < date.today():
            raise serializers.ValidationError("Date cannot be in the past")
        return value


# =========================================================
# SLOT VALIDATION (PRE-BOOKING CHECK)
# =========================================================
class BookingValidationSerializer(serializers.Serializer):
    turf_id = serializers.PrimaryKeyRelatedField(
        queryset=Turf.objects.all()
    )
    selected_date = serializers.DateField()
    selected_slots = serializers.ListField(
        child=serializers.TimeField(),
        min_length=1
    )

    def validate(self, data):
        turf = data["turf_id"]
        booking_date = data["selected_date"]
        slots = sorted(data["selected_slots"])
        today = timezone.localdate()

        if booking_date < today:
            raise serializers.ValidationError("Cannot book past dates")

        # Convert slots → hourly ranges
        time_ranges = []
        for slot in slots:
            end_time = (
                datetime.combine(booking_date, slot)
                + timedelta(hours=1)
            ).time()

            if slot < turf.opening_time or end_time > turf.closing_time:
                raise serializers.ValidationError("Outside operating hours")

            time_ranges.append((slot, end_time))

        existing = Booking.objects.filter(
            turf=turf,
            booking_date=booking_date,
            status=Booking.CONFIRMED,
        )

        # Full-day blocks everything
        if existing.filter(booking_type=Booking.FULL_DAY).exists():
            raise serializers.ValidationError("Turf already booked for full day")

        # Hourly overlap check
        for start, end in time_ranges:
            if existing.filter(
                booking_type=Booking.HOURLY,
                start_time__lt=end,
                end_time__gt=start,
            ).exists():
                raise serializers.ValidationError(
                    f"Slot {start}–{end} already booked"
                )

        data["time_ranges"] = time_ranges
        return data


# =========================================================
# PAYMENT FLOW SERIALIZERS
# =========================================================
class BookingDetailsSerializer(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    duration_hours = serializers.IntegerField(min_value=1, max_value=12)


class PaymentInfoSerializer(serializers.Serializer):
    method = serializers.ChoiceField(
        choices=["UPI", "CARD", "NET_BANKING", "CASH"]
    )
    transaction_ref = serializers.CharField()


class BookingPaySerializer(serializers.Serializer):
    turf_id = serializers.PrimaryKeyRelatedField(
        queryset=Turf.objects.all()
    )
    booking_details = BookingDetailsSerializer()
    payment_info = PaymentInfoSerializer()
    device_timestamp = serializers.DateTimeField()


# =========================================================
# TURF IMAGE UPLOAD
# =========================================================
class TurfImageUploadSerializer(serializers.Serializer):
    turf_id = serializers.IntegerField()
    image = serializers.ImageField()

    def validate_turf_id(self, value):
        if not Turf.objects.filter(id=value).exists():
            raise serializers.ValidationError("Invalid turf_id")
        return value


# =========================================================
# FINAL BOOKING CONFIRMATION
# =========================================================
class BookingConfirmSerializer(serializers.Serializer):
    turf_id = serializers.PrimaryKeyRelatedField(
        queryset=Turf.objects.all()
    )
    date = serializers.DateField()
    slots = serializers.ListField(
        child=serializers.TimeField(),
        min_length=1
    )
    payment_method = serializers.CharField()
    transaction_id = serializers.CharField()
