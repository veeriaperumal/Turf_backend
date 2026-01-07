# users/urls.py
from django.urls import path
from .views import BusinessDeleteView, BusinessOwnerUpdateView, BusinessProfileView, CustomerRegisterView, BusinessRegisterView, LoginView, ProfileUpdateView, TurfUpdateView

urlpatterns = [
    path("customer/register", CustomerRegisterView.as_view()),
    path("business/register", BusinessRegisterView.as_view()),
    
    
    path("login/", LoginView.as_view()),
    path("profile/update/", ProfileUpdateView.as_view()),
    path("profile/", ProfileUpdateView.as_view()),
    path("business/profile/",BusinessProfileView.as_view()),
    
    path("business/delete/", BusinessDeleteView.as_view()),
    path(
        "business/owner/update/",
        BusinessOwnerUpdateView.as_view(),
        name="business-owner-update"
    ),
    path(
        "business/turfs/<int:turf_id>/update/",
        TurfUpdateView.as_view(),
        name="turf-update"
    ),

]
