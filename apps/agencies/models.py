"""Agency and user models for Yakeey account management."""
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.text import slugify


def build_unique_slug(model_class, value: str, instance_pk=None) -> str:
    """Build a unique slug for agency profiles."""
    base_slug = slugify(value) or "agency"
    slug = base_slug
    counter = 2

    queryset = model_class.objects.filter(slug=slug)
    if instance_pk:
        queryset = queryset.exclude(pk=instance_pk)

    while queryset.exists():
        slug = f"{base_slug}-{counter}"
        queryset = model_class.objects.filter(slug=slug)
        if instance_pk:
            queryset = queryset.exclude(pk=instance_pk)
        counter += 1

    return slug


class UserManager(BaseUserManager):
    """Manager for email-based user accounts."""

    def create_user(self, email, password=None, **extra_fields):
        """Create a regular user with email as the login identifier."""
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create a superuser with staff and admin privileges."""
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class Agency(models.Model):
    """Real estate agency profile linked to listings after enrichment."""

    SOURCE_CHOICES = [
        ("propertyfinder", "PropertyFinder"),
        ("manual", "Manual"),
        ("self_registered", "Self Registered"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    logo_url = models.URLField(null=True, blank=True)
    sarouty_agency_id = models.CharField(max_length=100, null=True, blank=True)
    sarouty_profile_url = models.URLField(null=True, blank=True)
    total_listings = models.IntegerField(default=0)
    is_claimed = models.BooleanField(default=False)
    city = models.ForeignKey(
        "locations.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agencies",
    )
    is_verified = models.BooleanField(default=False)
    subscription_plan = models.ForeignKey(
        "subscriptions.SubscriptionPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agencies",
    )
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="manual")
    propertyfinder_id = models.CharField(max_length=120, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Agency"
        verbose_name_plural = "Agencies"

    def save(self, *args, **kwargs) -> None:
        """Auto-generate a unique slug from the agency name."""
        if not self.slug:
            self.slug = build_unique_slug(Agency, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class User(AbstractBaseUser, PermissionsMixin):
    """Email-login user linked optionally to an agency account."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        AGENCY_OWNER = "agency_owner", "Agency Owner"
        AGENCY_AGENT = "agency_agent", "Agency Agent"
        VIEWER = "viewer", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.VIEWER)
    agency = models.ForeignKey(
        Agency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["email"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.email
