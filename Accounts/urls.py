# users/urls.py
from django.urls import path
from .views import BusinessDeleteView, BusinessUpdateView, CustomerRegisterView, BusinessRegisterView, LoginView, ProfileUpdateView

urlpatterns = [
    path("customer/register", CustomerRegisterView.as_view()),
    path("business/register", BusinessRegisterView.as_view()),
    
    
    path("login/", LoginView.as_view()),
    path("profile/update/", ProfileUpdateView.as_view()),
    path("profile/", ProfileUpdateView.as_view()),
    
    path("business/update/", BusinessUpdateView.as_view()),
    path("business/delete/", BusinessDeleteView.as_view()),

]
