from datetime import datetime
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from Turf.models import Turf
from slots.constants import SlotStatus
from slots.models import Slot
from slots.serializers import BulkSlotPatchSerializer, BulkSlotUpdateSerializer, SlotSerializer, SmartSlotSaveSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction

from slots.services import build_slots_response



class SlotListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        turf_id = request.query_params.get("turf_id")
        date_str = request.query_params.get("date")

        if not turf_id or not date_str:
            raise ValidationError({
                "detail": "turf_id and date are required"
            })

        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({
                "detail": "Invalid date format. Use YYYY-MM-DD"
            })

        turf = Turf.objects.only(
            "id", "name", "address", "opening_time", "closing_time"
        ).filter(id=turf_id).first()

        if not turf:
            raise ValidationError({
                "detail": "Invalid turf_id"
            })

        data = build_slots_response(turf, selected_date)

        return Response({
            "status": "success",
            "data": data
        })


class BulkSlotSaveView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = BulkSlotUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        turf_id = serializer.validated_data["turf_id"]
        date = serializer.validated_data["date"]
        parsed_slots = serializer.validated_data["slots"]

        # ---------------------------------
        # 1. Fetch booked slots
        # ---------------------------------
        booked_slots = Slot.objects.filter(
            turf_id=turf_id,
            date=date,
            status=SlotStatus.BOOKED
        )

        # ---------------------------------
        # 2. Overlap protection
        # ---------------------------------
        for incoming in parsed_slots:
            for booked in booked_slots:
                if not (
                    incoming["end_time"] <= booked.start_time or
                    incoming["start_time"] >= booked.end_time
                ):
                    raise ValidationError(
                        "Cannot modify slots overlapping booked slots"
                    )

        # ---------------------------------
        # 3. Delete non-booked slots
        # ---------------------------------
        Slot.objects.filter(
            turf_id=turf_id,
            date=date
        ).exclude(status=SlotStatus.BOOKED).delete()

        # ---------------------------------
        # 4. Create new slots
        # ---------------------------------
        new_slots = [
            Slot(
                turf_id=turf_id,
                date=date,
                start_time=s["start_time"],
                end_time=s["end_time"],
                status=s["status"],
                price=s["price"],
                label=s["label"]
            )
            for s in parsed_slots
        ]

        Slot.objects.bulk_create(new_slots)

        return Response(
            {
                "status": "success",
                "message": "Slots updated successfully"
            },
            status=status.HTTP_200_OK
        )




class SlotCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SlotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slot = serializer.save()

        return Response(
            {"status": "success", "data": serializer.data},
            status=status.HTTP_201_CREATED
        )


class SlotUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slot_id):
        slot = get_object_or_404(Slot, id=slot_id)

        if slot.status == SlotStatus.BOOKED:
            raise ValidationError("Booked slots cannot be modified")

        serializer = SlotSerializer(
            slot, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"status": "success", "data": serializer.data}
        )


class SlotDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, slot_id):
        slot = get_object_or_404(Slot, id=slot_id)

        if slot.status == SlotStatus.BOOKED:
            raise ValidationError("Booked slots cannot be deleted")

        slot.delete()

        return Response(
            {"status": "success", "message": "Slot deleted"},
            status=status.HTTP_204_NO_CONTENT
        )
        
class BulkSlotUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request):
        serializer = BulkSlotPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        turf_id = serializer.validated_data["turf_id"]
        date = serializer.validated_data["date"]
        slot_ranges = serializer.validated_data["slots"]
        update_data = serializer.validated_data["data"]

        updated_count = 0

        for rng in slot_ranges:
            slot = Slot.objects.select_for_update().filter(
                turf_id=turf_id,
                date=date,
                start_time=rng["start_time"],
                end_time=rng["end_time"]
            ).first()

            if not slot:
                raise ValidationError(
                    f"Slot not found for {rng['start_time']} - {rng['end_time']}"
                )

            if slot.status == SlotStatus.BOOKED:
                raise ValidationError("Booked slots cannot be modified")

            for field, value in update_data.items():
                setattr(slot, field, value)

            slot.save()
            updated_count += 1

        return Response(
            {
                "status": "success",
                "updated_count": updated_count
            },
            status=status.HTTP_200_OK
        )



class SmartSlotSaveView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request):
        serializer = SmartSlotSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        turf_id = serializer.validated_data["turf_id"]
        date = serializer.validated_data["date"]
        slots = serializer.validated_data["slots"]

        updated = 0
        created = 0

        for s in slots:
            slot = Slot.objects.select_for_update().filter(
                turf_id=turf_id,
                date=date,
                start_time=s["start_time"],
                end_time=s["end_time"]
            ).first()

            if slot:
                if slot.status == SlotStatus.BOOKED:
                    raise ValidationError(
                        f"Booked slot cannot be modified: "
                        f"{s['start_time']} - {s['end_time']}"
                    )

                # UPDATE
                slot.status = s["status"]
                slot.price = s["price"]
                slot.label = s["label"]
                slot.save()
                updated += 1

            else:
                # CREATE
                Slot.objects.create(
                    turf_id=turf_id,
                    date=date,
                    start_time=s["start_time"],
                    end_time=s["end_time"],
                    status=s["status"],
                    price=s["price"],
                    label=s["label"]
                )
                created += 1

        return Response(
            {
                "status": "success",
                "created": created,
                "updated": updated
            },
            status=status.HTTP_200_OK
        )
