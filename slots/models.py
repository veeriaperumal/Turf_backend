# slots/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from Turf.models import Turf
from .constants import SlotStatus


class Slot(models.Model):
    turf = models.ForeignKey(
        Turf,
        on_delete=models.CASCADE,
        related_name="slots"
    )

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    status = models.CharField(
        max_length=20,
        choices=SlotStatus.CHOICES,
        default=SlotStatus.AVAILABLE
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    label = models.CharField(
        max_length=100,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("turf", "date", "start_time")
        ordering = ["date", "start_time"]

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("start_time must be before end_time")

        if self.date < timezone.localdate():
            raise ValidationError("Cannot create or modify past slots")

    def __str__(self):
        return f"{self.turf.name} | {self.date} | {self.start_time}-{self.end_time}"
