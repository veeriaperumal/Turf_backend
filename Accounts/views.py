# users/views.py
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from Turf.models import Amenity, Sport, Turf
from .serializers import BusinessOwnerUpdateSerializer, BusinessProfileReadSerializer, BusinessRegisterSerializer, CustomerRegisterSerializer, ProfileSerializer, ProfileUpdateSerializer, TurfUpdateSerializer
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
                "phone_number": owner.phone_number,
                "profile_image_url": (
                    request.build_absolute_uri(owner.profile_image_url.url)
                    if owner.profile_image_url else None
                ),
                "total_turfs_created": len(turf_ids),
                "turf_ids": turf_ids,
                "token": str(refresh.access_token),
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
        
    
class BusinessOwnerUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user

        if user.role != "business":
            return Response(
                {"detail": "Only business owners allowed"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BusinessOwnerUpdateSerializer(
            instance=user,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            "status": "success",
            "message": "Business owner updated successfully",
            "data":serializer.data
            
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


class TurfUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, turf_id):
        user = request.user

        if user.role != "business":
            return Response(
                {"detail": "Only business owners allowed"},
                status=status.HTTP_403_FORBIDDEN
            )

        turf = get_object_or_404(
            Turf,
            id=turf_id,
            owner=user
        )

        serializer = TurfUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():

            for field in [
                "name", "address", "price",
                "opening_time", "closing_time",
                "cancellation_policy", "rules"
            ]:
                if field in data:
                    setattr(turf, field, data[field])

            turf.save()

            if "sports_available" in data:
                sports = [
                    Sport.objects.get_or_create(
                        name=name.strip().title()
                    )[0]
                    for name in data["sports_available"]
                ]
                turf.sports.set(sports)

            if "amenities" in data:
                amenities = [
                    Amenity.objects.get_or_create(
                        name=name.strip().title()
                    )[0]
                    for name in data["amenities"]
                ]
                turf.amenities.set(amenities)

        return Response({
            "status": "success",
            "message": "Turf updated successfully",
            "turf_id": turf.id
        })

class BusinessProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != "business":
            raise PermissionDenied("Not a business account")

        serializer = BusinessProfileReadSerializer(user)

        return Response(
            {
                "status": "success",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )