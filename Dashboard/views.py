from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import DashboardSerializer
from .services import AdminDashboardService


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        admin = request.user

        response_data = {
            "profile": AdminDashboardService.get_profile(admin),
            "modules": {
                "user_management": AdminDashboardService.get_user_management_data(),
                "analytics": AdminDashboardService.get_analytics_data(),
            },
        }

        serializer = DashboardSerializer(response_data)

        return Response(
            {"status": "success", "data": serializer.data},
            status=200
        )
