from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import Slot
from .constants import SlotStatus


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "turf",
        "date",
        "start_time",
        "end_time",
        "status",
        "price",
    )

    list_filter = (
        "status",
        "date",
        "turf",
    )

    search_fields = (
        "turf__name",
    )

    ordering = ("date", "start_time")

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Slot Info", {
            "fields": (
                "turf",
                "date",
                "start_time",
                "end_time",
            )
        }),
        ("Status & Pricing", {
            "fields": (
                "status",
                "price",
                "label",
            )
        }),
        ("Meta", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    # ---------------------------------
    # HARD SAFETY RULES
    # ---------------------------------

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status == SlotStatus.BOOKED:
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and obj.status == SlotStatus.BOOKED:
            return False
        return super().has_change_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if change and obj.status == SlotStatus.BOOKED:
            raise ValidationError("Booked slots cannot be modified")
        super().save_model(request, obj, form, change)
