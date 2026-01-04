from datetime import datetime, timedelta, timezone
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from rest_framework import permissions, viewsets, status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response

from Turf.utils import expand_booking_slots, generate_hour_slots
from .models import Booking, Payment, Turf
from .serializers import (
    BookingConfirmSerializer,
    BookingPaySerializer,
    BookingSerializer,
    BookingValidationSerializer,
    TurfAvailabilityQuerySerializer,
    TurfDetailSerializer,
    TurfImageUploadSerializer,
)

# -------------------------------------------------------------------
# TURF DETAIL (SINGLE TURF)
# -------------------------------------------------------------------
class TurfDetailView(RetrieveAPIView):
    """
    Public API
    Fetch full turf details including sports & amenities
    """
    queryset = Turf.objects.prefetch_related("sports", "amenities")
    serializer_class = TurfDetailSerializer
    permission_classes = [AllowAny]


# -------------------------------------------------------------------
# TURF LIST (ALL TURFS)
# -------------------------------------------------------------------
class TurfListView(APIView):
    """
    Public API
    List all turfs
    """
    permission_classes = [AllowAny]

    def get(self, request):
        turfs = Turf.objects.all()
        serializer = TurfDetailSerializer(turfs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# -------------------------------------------------------------------
# TURF AVAILABILITY (DATE-BASED SLOT CHECK)
# -------------------------------------------------------------------
class TurfAvailabilityView(APIView):
    """
    Public API
    Returns booked slots for a turf on a given date
    """
    permission_classes = [AllowAny]

    def get(self, request, turf_id):
        # Validate query params (?date=YYYY-MM-DD)
        serializer = TurfAvailabilityQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        booking_date = serializer.validated_data["date"]
        turf = get_object_or_404(Turf, id=turf_id)

        # Fetch confirmed bookings only
        bookings = Booking.objects.filter(
            turf=turf,
            booking_date=booking_date,
            status=Booking.CONFIRMED,
        )

        # Generate all possible hourly slots based on turf timings
        all_slots = generate_hour_slots(
            turf.opening_time,
            turf.closing_time
        )
        all_labels = [s.strftime("%I:%M %p") for s in all_slots]

        # FULL DAY booking blocks the entire day
        if bookings.filter(booking_type=Booking.FULL_DAY).exists():
            return Response({
                "date": booking_date,
                "currency": "USD",
                "price_per_slot": turf.price,
                "booked_slots": all_labels,
                "blocked_slots": [],
                "operating_hours": {
                    "open": turf.opening_time.strftime("%I:%M %p"),
                    "close": turf.closing_time.strftime("%I:%M %p"),
                }
            })

        # Expand hourly bookings into individual slot labels
        booked_slots = set()
        hourly_bookings = bookings.filter(booking_type=Booking.HOURLY)

        for booking in hourly_bookings:
            slots = expand_booking_slots(
                booking.start_time,
                booking.end_time
            )
            booked_slots.update(slots)

        # Sort slots chronologically and format
        booked_slots = [
            t.strftime("%I:%M %p")
            for t in sorted(booked_slots)
        ]

        return Response({
            "date": booking_date,
            "currency": "USD",
            "price_per_slot": turf.price,
            "booked_slots": booked_slots,
            "blocked_slots": [],
            "operating_hours": {
                "open": turf.opening_time.strftime("%I:%M %p"),
                "close": turf.closing_time.strftime("%I:%M %p"),
            }
        })


# -------------------------------------------------------------------
# BOOKING VALIDATION (PRICE CHECK BEFORE PAYMENT)
# -------------------------------------------------------------------
class BookingValidationView(APIView):
    """
    Authenticated API
    Validates selected slots and returns pricing
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BookingValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        turf = serializer.validated_data["turf_id"]
        time_ranges = serializer.validated_data["time_ranges"]

        slot_count = len(time_ranges)
        total_price = slot_count * turf.price

        return Response({
            "turf_id": turf.id,
            "date": serializer.validated_data["selected_date"],
            "slots": [{"start": s, "end": e} for s, e in time_ranges],
            "slot_count": slot_count,
            "price_per_slot": turf.price,
            "total_price": total_price,
            "status": "AVAILABLE"
        }, status=200)


# -------------------------------------------------------------------
# BOOKING + PAYMENT (ATOMIC CONFIRMATION)
# -------------------------------------------------------------------
class BookingPayView(APIView):
    """
    Authenticated API
    Confirms booking and records payment in a single transaction
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BookingPaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        user = request.user

        turf = data["turf_id"]
        booking_details = data["booking_details"]
        payment_info = data["payment_info"]

        date = booking_details["date"]
        start = booking_details["start_time"]
        duration = booking_details["duration_hours"]

        payment_method = payment_info["method"]
        transaction_ref = payment_info["transaction_ref"]

        # Compute end time
        end = (
            datetime.combine(date, start)
            + timedelta(hours=duration)
        ).time()

        # Price calculation
        base_amount = duration * turf.price
        platform_fee = (base_amount * turf.platform_fee_percent) / 100
        total_amount = base_amount + platform_fee

        with transaction.atomic():
            # Lock conflicting rows to prevent race conditions
            conflicts = (
                Booking.objects
                .select_for_update()
                .filter(
                    turf=turf,
                    booking_date=date,
                    status=Booking.CONFIRMED,
                    booking_type=Booking.HOURLY,
                    start_time__lt=end,
                    end_time__gt=start,
                )
            )

            if conflicts.exists():
                return Response(
                    {"status": "failed", "message": "Slot no longer available"},
                    status=status.HTTP_409_CONFLICT
                )

            # Create booking
            booking = Booking.objects.create(
                user=user,
                turf=turf,
                booking_type=Booking.HOURLY,
                booking_date=date,
                start_time=start,
                end_time=end,
                duration_hours=duration,
                base_amount=base_amount,
                platform_fee=platform_fee,
                total_amount=total_amount,
                status=Booking.CONFIRMED,
            )

            # Idempotent payment handling
            existing_payment = Payment.objects.filter(
                transaction_ref=transaction_ref
            ).first()

            if existing_payment:
                return Response({
                    "status": "success",
                    "message": "Payment already processed",
                    "data": {
                        "booking_id": existing_payment.booking.id,
                        "payment_status": existing_payment.status,
                        "amount": float(existing_payment.amount_paid),
                        "currency": existing_payment.currency,
                    }
                }, status=200)

            try:
                Payment.objects.create(
                    booking=booking,
                    payment_method=payment_method,
                    transaction_ref=transaction_ref,
                    amount_paid=total_amount,
                    currency="INR",
                    status=Payment.SUCCESS,
                )
            except IntegrityError:
                return Response(
                    {"status": "success", "message": "Payment already recorded"},
                    status=200
                )

        return Response({
            "status": "success",
            "message": "Booking confirmed successfully",
            "data": {
                "booking_id": booking.id,
                "turf_name": turf.name,
                "location": turf.address,
                "image": turf.image.url if turf.image else None,
                "date": date,
                "time": start.strftime("%H:%M"),
                "grand_total": float(total_amount),
                "currency": "INR",
                "payment_status": "PAID",
            }
        }, status=status.HTTP_200_OK)


# -------------------------------------------------------------------
# LEGACY BOOKING CONFIRM (NO PAYMENT)
# -------------------------------------------------------------------
class BookingConfirmView(APIView):
    """
    Authenticated API
    Confirms booking without payment (legacy / internal use)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BookingConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        turf = serializer.validated_data["turf_id"]
        booking_date = serializer.validated_data["date"]
        start = serializer.validated_data["start_time"]
        duration = serializer.validated_data["duration_hours"]

        end = (
            datetime.combine(booking_date, start)
            + timedelta(hours=duration)
        ).time()

        with transaction.atomic():
            existing = Booking.objects.select_for_update().filter(
                turf=turf,
                booking_date=booking_date,
                status=Booking.CONFIRMED,
            )

            # FULL DAY blocks all bookings
            if existing.filter(booking_type=Booking.FULL_DAY).exists():
                return Response({
                    "status": "failed",
                    "error_code": "SLOT_NO_LONGER_AVAILABLE",
                    "message": "Turf already booked for full day"
                }, status=409)

            # HOURLY overlap check
            if existing.filter(
                booking_type=Booking.HOURLY,
                start_time__lt=end,
                end_time__gt=start,
            ).exists():
                return Response({
                    "status": "failed",
                    "error_code": "SLOT_NO_LONGER_AVAILABLE",
                    "message": "Selected time slot is no longer available"
                }, status=409)

            booking = Booking.objects.create(
                user=user,
                turf=turf,
                booking_type=Booking.HOURLY,
                booking_date=booking_date,
                start_time=start,
                end_time=end,
                price=duration * turf.price,
                status=Booking.CONFIRMED,
            )

        booking_id = f"bk_{booking.id}"

        return Response({
            "status": "success",
            "booking_id": booking_id,
            "message": "Booking confirmed successfully!",
            "receipt_url": f"https://api.turfapp.com/receipts/{booking_id}.pdf",
            "qr_code": f"https://api.turfapp.com/qr/{booking_id}.png",
        }, status=200)


# -------------------------------------------------------------------
# BOOKING CRUD (USER-BOUND)
# -------------------------------------------------------------------
class BookingViewSet(viewsets.ModelViewSet):
    """
    CRUD access for bookings
    Users see only their bookings
    Admins see all
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user = self.request.user
        qs = Booking.objects.select_related("turf", "user")
        return qs if user.is_staff else qs.filter(user=user)

    def perform_destroy(self, instance):
        # Soft delete
        instance.status = Booking.CANCELLED
        instance.save()
        return instance


# -------------------------------------------------------------------
# TURF IMAGE UPLOAD (BUSINESS OWNER ONLY)
# -------------------------------------------------------------------
class TurfImageUploadView(APIView):
    """
    Authenticated API
    Allows business owners to upload turf images
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user

        if user.role != "business":
            return Response(
                {"detail": "Only business owners allowed"},
                status=403
            )

        serializer = TurfImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        turf = get_object_or_404(
            Turf,
            id=serializer.validated_data["turf_id"],
            owner=user
        )

        turf.image = serializer.validated_data["image"]
        turf.save()

        return Response({
            "status": "success",
            "turf_id": turf.id,
            "image_url": turf.image.url
        })
