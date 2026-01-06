# dashboard/serializers.py
from rest_framework import serializers


class AdminProfileSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    avatar_url = serializers.URLField(allow_null=True)


class RecentUserSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    status = serializers.CharField()


class UserManagementModuleSerializer(serializers.Serializer):
    pending_approvals_count = serializers.IntegerField()
    pending_label = serializers.CharField()
    recent_users = RecentUserSerializer(many=True)


class AnalyticsModuleSerializer(serializers.Serializer):
    total_revenue = serializers.FloatField()
    currency = serializers.CharField()
    display_revenue = serializers.CharField()
    monthly_chart_data = serializers.ListField(
        child=serializers.IntegerField()
    )


class DashboardSerializer(serializers.Serializer):
    profile = AdminProfileSerializer()
    modules = serializers.DictField()
