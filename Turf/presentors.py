from Turf.models import Turf
from Turf.serializers import TurfSerializer


def build_business_login_payload(user):
    turfs = Turf.objects.filter(owner=user).prefetch_related(
        "sports", "amenities"
    )

    return {
        "business_key": f"TURF{user.id}",
        "owner_details": {
            "full_name": user.full_name,
            "role": user.role,
            "email": user.email,
            "phone_number": user.phone_number,
            "location": getattr(user, "location", None),
        },
        "turfs": TurfSerializer(turfs, many=True).data,
    }