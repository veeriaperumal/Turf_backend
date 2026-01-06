from django.db.models import Sum
from django.db.models.functions import TruncMonth

from Accounts.models import User
from Turf.models import Turf, Payment



class AdminDashboardService:
    """
    All dashboard-related queries live here.
    Views should NOT touch the database directly.
    """

    @staticmethod
    def get_profile(admin_user):
        return {
            "id": f"ADM-{admin_user.id}",
            "name": admin_user.full_name or "Admin",
            "email": admin_user.email,
            "role": "BUSINESS ADMIN",
            "avatar_url": None,
        }

    @staticmethod
    def get_user_management_data():
        pending_turf_approvals = Turf.objects.filter(
            is_active=False
        ).count()

        users = (
            User.objects
            .filter(role="business")
            .order_by("-created_at")[:5]
        )

        recent_users = []
        for user in users:
            name_value = user.full_name  # <- cannot be called accidentally

            recent_users.append({
                "id": f"u_{user.id}",
                "name": name_value if name_value else user.email,
                "email": user.email,
                "status": "active" if user.is_active else "inactive",
            })

        return {
            "pending_approvals_count": pending_turf_approvals,
            "pending_label": f"{pending_turf_approvals} New Turf Owners Waiting",
            "recent_users": recent_users,
        }


    @staticmethod
    def get_analytics_data():
        total_revenue = (
            Payment.objects
            .filter(status="success")
            .aggregate(total=Sum("amount_paid"))["total"]
            or 0
        )

        monthly_revenue = (
            Payment.objects
            .filter(status="success")
            .annotate(month=TruncMonth("paid_at"))
            .values("month")
            .annotate(total=Sum("amount_paid"))
            .order_by("month")
        )

        monthly_chart_data = [int(row["total"]) for row in monthly_revenue]

        return {
            "total_revenue": float(total_revenue),
            "currency": "USD",
            "display_revenue": f"${total_revenue:,.2f}",
            "monthly_chart_data": monthly_chart_data,
        }
