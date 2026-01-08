from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from Accounts.models import User
from Turf.service import calculate_booking_price
from .models import Booking, BookingSlot, Turf



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

class TurfSerializer(serializers.ModelSerializer):
    turf_name = serializers.CharField(source="name")
    cost_per_hour = serializers.IntegerField(source="price")

    operating_hours = serializers.SerializerMethodField()
    sports_available = serializers.SerializerMethodField()
    amenities = serializers.SerializerMethodField()

    class Meta:
        model = Turf
        fields = [
            "turf_name",
            "address",
            "cost_per_hour",
            "operating_hours",
            "sports_available",
            "amenities",
            "cancellation_policy",
        ]

    def get_operating_hours(self, obj):
        return {
            "open": obj.opening_time.strftime("%I:%M %p"),
            "close": obj.closing_time.strftime("%I:%M %p"),
        }

    def get_sports_available(self, obj):
        return list(obj.sports.values_list("name", flat=True))

    def get_amenities(self, obj):
        return list(obj.amenities.values_list("name", flat=True))
    
    
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



# -------------------------
# SLOT SERIALIZER (READ)
# -------------------------
class BookingSlotResponseSerializer(serializers.ModelSerializer):
    from_time = serializers.SerializerMethodField()
    to_time = serializers.SerializerMethodField()

    class Meta:
        model = BookingSlot
        fields = [
            "from_time",
            "to_time",
            "status",
            "price",
        ]

    def get_from_time(self, obj):
        return obj.start_time.strftime("%I:%M %p")

    def get_to_time(self, obj):
        return obj.end_time.strftime("%I:%M %p")


# -------------------------
# MAIN BOOKING SERIALIZER
# -------------------------
class BookingCreateSerializer(serializers.Serializer):

    turf_data = serializers.DictField()
    booking_details = serializers.DictField()
    slots_booked = serializers.ListField()
    price_breakdown = serializers.DictField()
    user_details = serializers.DictField()

    def validate(self, data):
        # Turf
        turf_id = data["turf_data"].get("turf_id")
        if not turf_id:
            raise serializers.ValidationError("turf_id is required")

        try:
            turf = Turf.objects.get(id=turf_id)
        except Turf.DoesNotExist:
            raise serializers.ValidationError("Invalid turf_id")

        # User
        user_id = data["user_details"].get("user_id")
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid user_id")

        # Date
        try:
            booking_date = datetime.strptime(
                data["booking_details"]["booking_date"],
                "%Y-%m-%d"
            ).date()
        except Exception:
            raise serializers.ValidationError("Invalid booking_date")

        # Slots
        if not data["slots_booked"]:
            raise serializers.ValidationError("At least one slot required")

        data["_validated"] = {
            "turf": turf,
            "user": user,
            "booking_date": booking_date,
        }

        return data

    @transaction.atomic
    def create(self, validated_data):
        turf = validated_data["_validated"]["turf"]
        user = validated_data["_validated"]["user"]
        booking_date = validated_data["_validated"]["booking_date"]

        slots_payload = validated_data["slots_booked"]
        total_amount = validated_data["price_breakdown"]["total_amount"]

        # -------------------------
        # CREATE BOOKING (PARENT)
        # -------------------------
        booking = Booking.objects.create(
            turf=turf,
            user=user,
            booking_type=Booking.HOURLY,
            booking_date=booking_date,
            base_amount=total_amount,
            platform_fee=0,
            total_amount=total_amount,
            status=Booking.PENDING,
        )

        # -------------------------
        # CREATE SLOTS (LOCKED)
        # -------------------------
        for slot in slots_payload:
            start_time = datetime.strptime(
                slot["from_time"], "%I:%M %p"
            ).time()
            end_time = datetime.strptime(
                slot["to_time"], "%I:%M %p"
            ).time()

            # HARD LOCK: no overlapping slot allowed
            exists = BookingSlot.objects.select_for_update().filter(
                turf=turf,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
            ).exists()

            if exists:
                raise serializers.ValidationError(
                    f"Slot {slot['from_time']} - {slot['to_time']} already booked"
                )

            BookingSlot.objects.create(
                booking=booking,
                turf=turf,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                price=slot["price"],
                status=BookingSlot.PENDING,
            )

        return booking
    
    

class BookingUpdateSerializer(serializers.ModelSerializer):
    """
    Allowed updates:
    - booking_date
    - slots (time change)
    """

    slots = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )

    class Meta:
        model = Booking
        fields = (
            "booking_date",
            "slots",
        )

    # -------------------------
    # VALIDATION
    # -------------------------
    def validate(self, data):
        booking = self.instance
        today = timezone.localdate()

        if booking.status in [Booking.COMPLETED, Booking.CANCELLED]:
            raise serializers.ValidationError(
                "Completed or cancelled bookings cannot be modified"
            )

        if booking.booking_date < today:
            raise serializers.ValidationError(
                "Past bookings cannot be updated"
            )

        return data

    # -------------------------
    # UPDATE LOGIC
    # -------------------------
    @transaction.atomic
    def update(self, instance, validated_data):
        slots_data = validated_data.pop("slots", None)

        # Update booking_date if provided
        if "booking_date" in validated_data:
            instance.booking_date = validated_data["booking_date"]

        # -------------------------
        # SLOT UPDATE
        # -------------------------
        if slots_data is not None:
            # DELETE old slots (locked)
            BookingSlot.objects.select_for_update().filter(
                booking=instance
            ).delete()

            total_amount = 0

            for slot in slots_data:
                try:
                    start_time = datetime.strptime(
                        slot["from_time"], "%I:%M %p"
                    ).time()
                    end_time = datetime.strptime(
                        slot["to_time"], "%I:%M %p"
                    ).time()
                except KeyError:
                    raise serializers.ValidationError(
                        "Slots must contain from_time and to_time"
                    )

                # Overlap protection
                conflict = BookingSlot.objects.filter(
                    turf=instance.turf,
                    booking_date=instance.booking_date,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                    status__in=[BookingSlot.PENDING, BookingSlot.CONFIRMED],
                ).exists()

                if conflict:
                    raise serializers.ValidationError(
                        f"Slot {slot['from_time']} - {slot['to_time']} already booked"
                    )

                price = calculate_booking_price(
                    turf=instance.turf,
                    start_time=start_time,
                    end_time=end_time,
                    booking_date=instance.booking_date,
                )

                BookingSlot.objects.create(
                    booking=instance,
                    turf=instance.turf,
                    booking_date=instance.booking_date,
                    start_time=start_time,
                    end_time=end_time,
                    price=price,
                    status=BookingSlot.PENDING,
                )

                total_amount += price

            instance.total_amount = total_amount

        instance.save()
        return instance
