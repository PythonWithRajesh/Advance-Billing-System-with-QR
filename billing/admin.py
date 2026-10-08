from django.contrib import admin

from .models import (
    PasswordResetOTP,
    DistributorProfile,
    Customer,
    Product,
    Invoice,
    InvoiceItem,
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


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "category",
        "price",
        "stock",
        "gst_rate",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "name",
        "category",
        "description",
    )

    list_filter = (
        "category",
        "gst_rate",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):

    list_display = (
        "invoice_number",
        "customer",
        "invoice_date",
        "subtotal",
        "gst_amount",
        "grand_total",
        "payment_status",
    )

    search_fields = (
        "invoice_number",
        "customer__name",
        "customer__email",
        "customer__phone",
    )

    list_filter = (
        "payment_status",
        "invoice_date",
    )

    readonly_fields = (
        "invoice_date",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-invoice_date",
    )


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):

    list_display = (
        "invoice",
        "product",
        "quantity",
        "unit_price",
        "gst_rate",
        "gst_amount",
        "total_price",
    )

    search_fields = (
        "invoice__invoice_number",
        "product__name",
    )

    list_filter = (
        "gst_rate",
    )