"""Admin configuration for agency accounts and users."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.agencies.models import Agency, User


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "email", "city", "source", "is_verified", "subscription_plan", "created_at"]
    list_filter = ["city", "is_verified", "subscription_plan", "source", "created_at"]
    search_fields = ["name", "phone", "whatsapp", "email", "propertyfinder_id"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ["email", "first_name", "last_name", "role", "agency", "is_active", "is_staff", "last_login"]
    list_filter = ["role", "is_active", "is_staff", "agency", "created_at"]
    search_fields = ["email", "first_name", "last_name", "agency__name"]
    ordering = ["-created_at"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "agency", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role", "agency", "is_staff", "is_active"),
        }),
    )
    readonly_fields = ["created_at", "last_login"]
