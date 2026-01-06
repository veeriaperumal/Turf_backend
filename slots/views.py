from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from Turf.models import Turf
from .services import build_slots_response


class SlotListView(APIView):
    permission_classes=[AllowAny]
    def get(self, request):
        turf_id = request.query_params.get("turf_id")
        date_str = request.query_params.get("date")

        if not turf_id or not date_str:
            raise ValidationError("turf_id and date are required")

        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError("Invalid date format (YYYY-MM-DD)")

        turf = Turf.objects.filter(id=turf_id).first()
        if not turf:
            raise ValidationError("Invalid turf_id")

        data = build_slots_response(turf, selected_date)

        return Response({
            "status": "success",
            "data": data
        })
