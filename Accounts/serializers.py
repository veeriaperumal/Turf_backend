# users/serializers.py
from datetime import datetime
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from Turf.models import Amenity, Sport, Turf
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from Turf.service import build_business_login_payload

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


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone_number",
            "location",
            "profile_image_url",
            "role",
            "is_active",
            "created_at",
        )


# users/serializers.py


class OperatingHoursSerializer(serializers.Serializer):
    open = serializers.TimeField(input_formats=["%I:%M %p"])
    close = serializers.TimeField(input_formats=["%I:%M %p"])


class TurfCreateSerializer(serializers.Serializer):
    turf_name = serializers.CharField()
    address = serializers.CharField()
    cost_per_hour = serializers.IntegerField()
    operating_hours = OperatingHoursSerializer()
    sports_available = serializers.ListField(child=serializers.CharField())
    amenities = serializers.ListField(child=serializers.CharField(), required=False)
    turf_image_url = serializers.URLField(required=False)
    rules = serializers.ListField(child=serializers.CharField(), required=False)
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

    def get_profile_image_url(self, obj):
        request = self.context.get("request")
        if obj.profile_image and request:
            return request.build_absolute_uri(obj.profile_image.url)
        return None

    def create(self, validated_data):
        validated_data["role"] = "business"
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class BusinessRegisterSerializer(serializers.Serializer):
    business_key = serializers.CharField()
    owner_details = BusinessOwnerSerializer()
    turfs = TurfCreateSerializer(many=True)

    def save(self):
        with transaction.atomic():

            # ✅ validate & create owner properly
            owner_serializer = BusinessOwnerSerializer(
                data=self.validated_data["owner_details"], context=self.context
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

class BusinessOwnerUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "full_name",
            "phone_number",
            "location",
            "profile_image_url",
            "password",
        ]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class TurfUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    address = serializers.CharField(required=False)
    price = serializers.IntegerField(required=False, min_value=1)
    opening_time = serializers.TimeField(required=False)
    closing_time = serializers.TimeField(required=False)
    cancellation_policy = serializers.CharField(required=False)
    rules = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    sports_available = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    amenities = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )

    def validate(self, attrs):
        open_t = attrs.get("opening_time")
        close_t = attrs.get("closing_time")

        if open_t and close_t and open_t >= close_t:
            raise serializers.ValidationError(
                "opening_time must be before closing_time"
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
        request = self.context.get("request")

        profile_image_url = (
            request.build_absolute_uri(self.user.profile_image_url.url)
            if self.user.profile_image_url and request
            else None
        )

        data["user"] = {
            "id": self.user.id,
            "role": self.user.role,
            "full_name": self.user.full_name,
            "email": self.user.email,
            "phone_number": self.user.phone_number,
            "profile_image_url": profile_image_url,
            "business_id": f"biz_{self.user.id}" if self.user.role == "business" else None,
        }
        #  ROLE-BASED EXTENSION
        if self.user.role in ["admin", "business"]:
            data["business"] = build_business_login_payload(self.user)

        return data



class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name", "phone_number", "location", "profile_image_url"]

    def validate_phone_number(self, value):
        if value and len(value) < 10:
            raise serializers.ValidationError("Invalid phone number")
        return value


class BusinessProfileReadSerializer(serializers.ModelSerializer):
    turfs = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "phone_number",
            "location",
            "profile_image_url",
            "role",
            "turfs",
        ]

    def get_turfs(self, user):
        turfs = Turf.objects.filter(owner=user)

        return [
            {
                "id": turf.id,
                "name": turf.name,
                "address": turf.address,
                "price": turf.price,
                "opening_time": turf.opening_time,
                "closing_time": turf.closing_time,
                "sports": [s.name for s in turf.sports.all()],
                "amenities": [a.name for a in turf.amenities.all()],
            }
            for turf in turfs
        ]
