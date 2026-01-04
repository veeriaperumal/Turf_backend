# users/models.py

from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)

# ----------------------------------
# CUSTOM USER MANAGER
# ----------------------------------
# Responsible for creating normal users and superusers.
# Enforces email-based authentication and role correctness.
class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        # Email is the primary identifier; it must be provided
        if not email:
            raise ValueError("Email is required")

        # Normalize email (lowercase domain, etc.)
        email = self.normalize_email(email)

        # Create user instance without saving password in plain text
        user = self.model(email=email, **extra_fields)

        # Hash and set password securely
        user.set_password(password)

        # Persist user using the correct database
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # Enforce admin-level flags for superusers
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")

        # Hard validation to prevent misconfigured superusers
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


# ----------------------------------
# CUSTOM USER MODEL
# ----------------------------------
# Email-based authentication user model with role support.
class User(AbstractBaseUser, PermissionsMixin):

    # Explicit role definitions to control system access
    ROLE_CHOICES = (
        ("customer", "Customer"),
        ("business", "Business"),
        ("admin", "Admin"),
    )

    # Primary login identifier (replaces username)
    email = models.EmailField(unique=True)

    # Human-readable name for display purposes
    full_name = models.CharField(max_length=255)

    # Contact number (not enforced unique due to shared numbers)
    phone_number = models.CharField(max_length=20)

    # Optional location metadata
    location = models.CharField(max_length=255, blank=True)

    # External profile image (supports S3/CDN URLs)
    profile_image_url = models.URLField(blank=True)

    # Role controls feature access across the platform
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # Standard Django auth flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Attach custom manager (REQUIRED for custom user models)
    objects = UserManager()

    # Audit field for user creation
    created_at = models.DateTimeField(auto_now_add=True)

    # Configure email as the unique login field
    USERNAME_FIELD = "email"
