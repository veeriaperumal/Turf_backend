# users/views.py
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny

from Turf.models import Amenity, Sport, Turf
from .serializers import BusinessRegisterSerializer, BusinessUpdateByIDSerializer, CustomerRegisterSerializer, ProfileSerializer, ProfileUpdateSerializer
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import LoginSerializer


class CustomerRegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
            "status": "success",
            "message": "Customer profile created successfully",
            "data": {
                "user_id": f"cust_{user.id}",
                "full_name": user.full_name,
                "email": user.email,
                "token": str(refresh.access_token),
                "created_at": user.created_at
            }
        }, status=201)



# users/views.py
class BusinessRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BusinessRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        owner, turf_ids = serializer.save()
        refresh = RefreshToken.for_user(owner)

        return Response({
            "status": "success",
            "message": "Business profile and turfs created successfully",
            "data": {
                "business_id": f"biz_{owner.id}",
                "owner_name": owner.full_name,
                "total_turfs_created": len(turf_ids),
                "turf_ids": turf_ids,
                "token": str(refresh.access_token),
                "account_status": "pending_approval"
            }
        }, status=status.HTTP_201_CREATED)
        
        

class LoginView(TokenObtainPairView):
    permission_classes= [AllowAny]
    serializer_class = LoginSerializer


class ProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(
            user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            "status": "success",
            "message": "Profile updated successfully",
            "data": serializer.data
        }, status=200)
        
        
    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response({
            "status": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
        
    
        
class BusinessUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user

        if user.role != "business":
            return Response(
                {"detail": "Only business owners allowed"},
                status=403
            )

        serializer = BusinessUpdateByIDSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        response = {}

        # ---- OWNER UPDATE ----
        if "owner_id" in data:
            if data["owner_id"] != user.id:
                return Response(
                    {"detail": "Cannot update another owner"},
                    status=403
                )

            owner_data = data["owner_details"]
            owner_data.pop("role", None)
            owner_data.pop("email", None)

            for field, value in owner_data.items():
                if field == "password":
                    user.set_password(value)
                else:
                    setattr(user, field, value)
            user.save()

            response["owner_updated"] = True

        # ---- TURF UPDATE ----
        if "turf_id" in data:
            turf = get_object_or_404(
                Turf,
                id=data["turf_id"],
                owner=user
            )

            turf_data = data["turf_details"]

            # simple fields
            for field in [
                "name", "address", "price",
                "opening_time", "closing_time",
                "cancellation_policy", "rules"
            ]:
                if field in turf_data:
                    setattr(turf, field, turf_data[field])

            turf.save()

            # M2M replace
            if "sports_available" in turf_data:
                sports = [
                    Sport.objects.get_or_create(
                        name=name.strip().title()
                    )[0]
                    for name in turf_data["sports_available"]
                ]
                turf.sports.set(sports)

            if "amenities" in turf_data:
                amenities = [
                    Amenity.objects.get_or_create(
                        name=name.strip().title()
                    )[0]
                    for name in turf_data["amenities"]
                ]
                turf.amenities.set(amenities)

            response["turf_updated"] = turf.id

        return Response({
            "status": "success",
            "data": response
        })





class BusinessDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user

        if user.role != "business":
            return Response(
                {"detail": "Only business owners can delete"},
                status=403
            )

        with transaction.atomic():
            Turf.objects.filter(owner=user).delete()
            user.delete()

        return Response(
            {"message": "Business account deleted"},
            status=204
        )
