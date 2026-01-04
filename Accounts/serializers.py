# users/serializers.py
from datetime import datetime
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from Turf.models import Amenity, Sport, Turf
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
User = get_user_model()

class CustomerRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            "role",
            "full_name",
            "email",
            "password",
            "phone_number",
            "location",
            "profile_image_url",
        )

    def validate_role(self, value):
        if value != "customer":
            raise serializers.ValidationError("Invalid role for customer registration")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user



# users/serializers.py


class OperatingHoursSerializer(serializers.Serializer):
    open = serializers.TimeField(input_formats=["%I:%M %p"])
    close = serializers.TimeField(input_formats=["%I:%M %p"])


class TurfCreateSerializer(serializers.Serializer):
    turf_name = serializers.CharField()
    address = serializers.CharField()
    cost_per_hour = serializers.IntegerField()
    operating_hours = OperatingHoursSerializer()
    sports_available = serializers.ListField(
        child=serializers.CharField()
    )
    amenities = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    turf_image_url = serializers.URLField(required=False)
    rules = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    cancellation_policy = serializers.CharField(required=False)


class BusinessOwnerSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "full_name",
            "email",
            "password",
            "phone_number",
            "location",
            "profile_image_url",
            "role",
        ]

    def create(self, validated_data):
        validated_data["role"] = "business"
        password = validated_data.pop("password")
        return User.objects.create_user(
            password=password,
            **validated_data
        )


class BusinessRegisterSerializer(serializers.Serializer):
    business_key = serializers.CharField()
    owner_details = BusinessOwnerSerializer()
    turfs = TurfCreateSerializer(many=True)

    def save(self):
        with transaction.atomic():

            # ✅ validate & create owner properly
            owner_serializer = BusinessOwnerSerializer(
                data=self.validated_data["owner_details"]
            )
            owner_serializer.is_valid(raise_exception=True)

            owner = owner_serializer.save(role="business")

            turf_ids = []

            for turf in self.validated_data["turfs"]:
                hours = turf["operating_hours"]

                turf_obj = Turf.objects.create(
                    owner=owner,
                    name=turf["turf_name"],
                    address=turf["address"],
                    price=turf["cost_per_hour"],
                    opening_time=hours["open"],
                    closing_time=hours["close"],
                    location_url=turf.get("turf_image_url", ""),
                    cancellation_policy=turf.get("cancellation_policy", ""),
                    rules=turf.get("rules", []),
                )

                sports = []
                for name in turf["sports_available"]:
                    clean = name.strip().title()
                    sport, _ = Sport.objects.get_or_create(name=clean)
                    sports.append(sport)
                turf_obj.sports.set(sports)

                amenities = []
                for name in turf.get("amenities", []):
                    clean = name.strip().title()
                    amenity, _ = Amenity.objects.get_or_create(name=clean)
                    amenities.append(amenity)
                turf_obj.amenities.set(amenities)

                turf_ids.append(turf_obj.id)

            return owner, turf_ids

class BusinessUpdateByIDSerializer(serializers.Serializer):
    owner_id = serializers.IntegerField(required=False)
    owner_details = BusinessOwnerSerializer(required=False)

    turf_id = serializers.IntegerField(required=False)
    turf_details = serializers.DictField(required=False)

    def validate(self, attrs):
        owner_id = attrs.get("owner_id")
        owner_details = attrs.get("owner_details")
        turf_id = attrs.get("turf_id")
        turf_details = attrs.get("turf_details")

        # ❌ No IDs at all
        if not owner_id and not turf_id:
            raise serializers.ValidationError(
                "owner_id or turf_id is required"
            )

        # ❌ Owner update without details
        if owner_id and not owner_details:
            raise serializers.ValidationError(
                "owner_details required when owner_id is provided"
            )

        # ❌ Turf update without details
        if turf_id and not turf_details:
            raise serializers.ValidationError(
                "turf_details required when turf_id is provided"
            )

        return attrs



class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        data["user"] = {
            "id": self.user.id,
            "role": self.user.role,
            "full_name": self.user.full_name,
            "email": self.user.email,
        }
        return data


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "full_name",
            "phone_number",
            "location",
        ]

    def validate_phone_number(self, value):
        if len(value) < 10:
            raise serializers.ValidationError("Invalid phone number")
        return value
    
    
