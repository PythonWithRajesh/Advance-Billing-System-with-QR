from django.contrib import admin

from .models import (
    PasswordResetOTP,
    DistributorProfile,
    Customer
)


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "otp",
        "created_at",
        "is_used",
    )

    list_filter = (
        "is_used",
        "created_at",
    )

    search_fields = (
        "user__username",
        "otp",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(DistributorProfile)
class DistributorProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "phone",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "phone",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "email",
        "phone",
        "city",
        "state",
        "pincode",
        "created_at",
    )

    search_fields = (
        "name",
        "email",
        "phone",
        "city",
        "pincode",
    )

    list_filter = (
        "state",
        "city",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )