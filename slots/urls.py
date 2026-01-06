from django.urls import path
from .views import SlotListView

urlpatterns = [
    path("slots/", SlotListView.as_view(), name="slot-list"),
]
