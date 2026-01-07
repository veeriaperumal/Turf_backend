# slots/serializers.py
from datetime import datetime
from rest_framework import serializers
from .models import Slot
from .constants import SlotStatus


class SlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slot
        fields = [
            "id",
            "turf",
            "date",
            "start_time",
            "end_time",
            "status",
            "price",
            "label",
        ]

    def validate_status(self, value):
        if value not in dict(SlotStatus.CHOICES):
            raise serializers.ValidationError("Invalid slot status")
        return value
    
    
class BulkSlotUpdateSerializer(serializers.Serializer):
    turf_id = serializers.IntegerField()
    date = serializers.DateField()
    slots = serializers.ListField(min_length=1)

    def validate_slots(self, slots):
        parsed = []

        for slot in slots:
            for key in ("from", "to", "status", "price"):
                if key not in slot:
                    raise serializers.ValidationError(f"Missing field: {key}")

            try:
                start = datetime.strptime(slot["from"], "%I:%M %p").time()
                end = datetime.strptime(slot["to"], "%I:%M %p").time()
            except ValueError:
                raise serializers.ValidationError("Invalid time format")

            if start >= end:
                raise serializers.ValidationError(
                    "start_time must be before end_time"
                )

            if slot["status"] not in dict(SlotStatus.CHOICES):
                raise serializers.ValidationError("Invalid slot status")

            parsed.append({
                "start_time": start,
                "end_time": end,
                "status": slot["status"],
                "price": slot["price"],
                "label": slot.get("label", "")
            })

        return parsed
    

class BulkSlotPatchSerializer(serializers.Serializer):
    turf_id = serializers.IntegerField()
    date = serializers.DateField()
    slots = serializers.ListField(min_length=1)
    data = serializers.DictField()

    def validate_slots(self, slots):
        parsed = []

        for slot in slots:
            if "from" not in slot or "to" not in slot:
                raise serializers.ValidationError(
                    "Each slot must have from and to"
                )

            try:
                start = datetime.strptime(slot["from"], "%I:%M %p").time()
                end = datetime.strptime(slot["to"], "%I:%M %p").time()
            except ValueError:
                raise serializers.ValidationError("Invalid time format")

            if start >= end:
                raise serializers.ValidationError(
                    "start_time must be before end_time"
                )

            parsed.append({
                "start_time": start,
                "end_time": end,
            })

        return parsed

    def validate_data(self, data):
        allowed = {"status", "price", "label"}
        invalid = set(data.keys()) - allowed

        if invalid:
            raise serializers.ValidationError(
                f"Invalid fields: {', '.join(invalid)}"
            )

        if "status" in data and data["status"] not in dict(SlotStatus.CHOICES):
            raise serializers.ValidationError("Invalid slot status")

        return data



class SmartSlotSaveSerializer(serializers.Serializer):
    turf_id = serializers.IntegerField()
    date = serializers.DateField()
    slots = serializers.ListField(min_length=1)

    def validate_slots(self, slots):
        parsed = []

        for slot in slots:
            for key in ("from", "to", "status", "price"):
                if key not in slot:
                    raise serializers.ValidationError(f"Missing field: {key}")

            try:
                start = datetime.strptime(slot["from"], "%I:%M %p").time()
                end = datetime.strptime(slot["to"], "%I:%M %p").time()
            except ValueError:
                raise serializers.ValidationError("Invalid time format")

            if start >= end:
                raise serializers.ValidationError("start_time must be before end_time")

            if slot["status"] not in dict(SlotStatus.CHOICES):
                raise serializers.ValidationError("Invalid slot status")

            parsed.append({
                "start_time": start,
                "end_time": end,
                "status": slot["status"],
                "price": slot["price"],
                "label": slot.get("label", "")
            })

        return parsed
