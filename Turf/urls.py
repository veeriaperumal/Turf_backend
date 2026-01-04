from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BookingConfirmView, BookingPayView, BookingValidationView, BookingViewSet, TurfAvailabilityView, TurfDetailView, TurfListView, TurfImageUploadView

router = DefaultRouter()
router.register("bookings", BookingViewSet, basename="booking"),

# router.register("turfs/<int:turf_id>/availability/", TurfAvailabilityView, basename="turf"),

urlpatterns = [
    path("turfs/", include(router.urls)),
    path("turf/<int:turf_id>/availability/", TurfAvailabilityView.as_view()),
    path("list/turfs/", TurfListView.as_view()),
    path("turf/<int:pk>", TurfDetailView.as_view()),
    path('bookings/validate/', BookingValidationView.as_view(), name='booking-validate'),
    path("bookings/confirm/", BookingConfirmView.as_view()),
    path('bookings/pay/', BookingPayView.as_view(), name='booking-pay'),

    path("turfs/upload-image/", TurfImageUploadView.as_view(), name="turf-upload-image"),
]
