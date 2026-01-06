from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.forms import ModelForm

from .models import User


# ----------------------------------
# USER CHANGE FORM (ADMIN EDIT)
# ----------------------------------
class UserChangeForm(ModelForm):
    class Meta:
        model = User
        fields = "__all__"


# ----------------------------------
# CUSTOM USER ADMIN
# ----------------------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    model = User

    # Admin list view
    list_display = (
        "email",
        "full_name",
        "role",
        "is_active",
        "is_staff",
        "created_at",
    )

    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "full_name", "phone_number")
    ordering = ("-created_at",)

    # Admin detail view layout
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {
            "fields": (
                "full_name",
                "phone_number",
                "location",
                "profile_image_url",
            )
        }),
        ("Role & Permissions", {
            "fields": (
                "role",
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Important Dates", {"fields": ("last_login", "created_at")}),
    )

    readonly_fields = ("created_at", "last_login")

    # User creation form in admin
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "phone_number",
                    "role",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    filter_horizontal = ("groups", "user_permissions")
