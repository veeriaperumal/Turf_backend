from django.urls import path
from .views import (
    BulkSlotUpdateView,
    SlotListView,
    BulkSlotSaveView,
    SlotCreateView,
    SlotUpdateView,
    SlotDeleteView,
    SmartSlotSaveView,
)

urlpatterns = [
    path("slots/", SlotListView.as_view()),
    path("slots/sync/", SlotCreateView.as_view()),
    path("slots/<int:slot_id>/", SlotUpdateView.as_view()),
    path("slots/<int:slot_id>/delete/", SlotDeleteView.as_view()),
    path("slots/bulk-save/", BulkSlotSaveView.as_view()),
    path("slots/bulk-update/", BulkSlotUpdateView.as_view()),
    path("slots/smart-save/", SmartSlotSaveView.as_view()),
]
